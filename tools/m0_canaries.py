"""Run the M0 resource canaries through the mae runner and check each response.

Usage (outer root, clean tree): .venv/bin/python tools/m0_canaries.py
Temporarily lowers limits for the wall and memory canaries, then restores the owner limits
(4 cores, 6 GiB, 1 job, 8 h). Writes .mae/canaries/<timestamp>.json.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

import psutil

ROOT = Path(__file__).resolve().parents[1]
MAE = [sys.executable, str(ROOT / "mac-agentic-engineering/bin/mae")]
OWNER = ["--cpus", "4", "--memory-gb", "6", "--jobs", "1", "--hours", "8"]

CANARIES = [
    # name, configure override, expected batch reason, owner-stop delay
    ("cpu-throttle", None, None, None),
    ("owner-stop", None, "owner_stop", 10),
    ("wall-limit", ["--hours", "0.006"], "wall_limit", None),
    ("memory-stop", ["--memory-gb", "1"], "memory_pressure", None),
    ("mps-no-telemetry", None, "missing_or_stale_mps_telemetry", None),
    ("mps-stale-telemetry", None, "missing_or_stale_mps_telemetry", None),
    ("mps-telemetry-ok", None, None, None),
]


def configure(override):
    args = list(OWNER)
    for i in range(0, len(override or []), 2):
        args[args.index(override[i]) + 1] = override[i + 1]
    subprocess.run(MAE + ["configure", *args], check=True, capture_output=True, cwd=ROOT)


def alive(record):
    try:
        return psutil.Process(record["pid"]).create_time() == record["created"]
    except psutil.NoSuchProcess:
        return False


def main():
    results = []
    try:
        for name, override, expected, stop_after in CANARIES:
            configure(override)
            t0 = time.monotonic()
            proc = subprocess.Popen(MAE + ["run", f"experiments/m0/canary-{name}.json"], cwd=ROOT,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if stop_after:
                time.sleep(stop_after)
                subprocess.run(MAE + ["stop"], cwd=ROOT, check=True, capture_output=True)
            out, _ = proc.communicate()
            wall = time.monotonic() - t0
            state = json.loads((ROOT / ".mae/current.json").read_text())
            run_dir = Path(state["out"])
            job_dir = run_dir / f"m0-canary-{name}"
            res = [json.loads(line) for line in (run_dir / "resources.jsonl").read_text().splitlines()]
            children = json.loads((job_dir / "children.json").read_text()) if (job_dir / "children.json").exists() else []
            time.sleep(0.5)
            leaked = [c["pid"] for c in children if alive(c)]
            cpu = [r["cpu_cores"] for r in res]
            row = dict(canary=name, batch=state["batch"], reason=state.get("reason"), expected=expected,
                       status=state["status"], exit_code=proc.returncode, wall_seconds=round(wall, 1),
                       samples=len(res), mean_cpu_cores=round(sum(cpu) / len(cpu), 2) if cpu else None,
                       max_conservative_memory_gb=round(max(r["conservative_memory_gb"] for r in res), 3) if res else None,
                       max_mps_driver_gb=round(max(r["mps_driver_gb"] for r in res), 3) if res else None,
                       min_available_gb=round(min(r["available_gb"] for r in res), 2) if res else None,
                       children=len(children), leaked_children=leaked,
                       completed=(job_dir / "summary.json").exists(), passed=None)
            ok = row["reason"] == expected and not leaked
            if name == "cpu-throttle":
                # 6 busy children against a 4-core budget: averaged usage must be throttled.
                ok = ok and row["completed"] and row["mean_cpu_cores"] <= 4.6
            if name == "mps-telemetry-ok":
                ok = ok and row["completed"] and row["max_mps_driver_gb"] > 0
            row["passed"] = bool(ok)
            results.append(row)
            print(json.dumps(row), flush=True)
    finally:
        configure(None)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = ROOT / ".mae/canaries" / f"{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, indent=2) + "\n")
    print("wrote", path)
    print("restored", (ROOT / ".mae/resources.json").read_text().strip())
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
