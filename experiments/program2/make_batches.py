"""Writes the batch files and the plan of the second 2026-11-01 programme (PROTOCOL_FREEZE Amendment 5). Deterministic;
run from the project root.

A3 (experiments/a3/):
  data.batch.json          r3-v1 generation (CPU)
  tests.batch.json         a3-tests (default suite) + a3-smoke (opt-in RL smoke tests incl. exact resume; CPU)
  canary-s43.batch.json    engineering canary = planned seed 43: BC, probe, the five branches
  seed-s<S>.batch.json     S = 44..66: BC, probe, five branches
  Branch order per seed: a balanced Latin rotation of (A, B, C, D, E) over seeds (seed S uses rotation (S - 43) mod 5,
  then the rotated list is reversed for odd S), so every arm runs in every position across the 24 seeds.
Calibration (experiments/cal/): cal-s<S>.batch.json, S = 67, 68, 69: three BC jobs (rho 0.2, 0.5, 0.8), order rotated.
Pilot (experiments/pilot/): written only after calibration selects a variant (--pilot RHO UPDATE --cal-batches ...):
  pilot-s<S>.batch.json: for K = 1 then 3: probe pl-probe-K<K>-s<S>, then branches 00, 10, 01s, 11s (rotated order).
Final: experiments/program2/final-tests.batch.json (p2-tests).
plan.json: every batch file in execution order with its study and whether it is required.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
A3C = "experiments/a3/a3-v1.json"
BC = "experiments/a3/bc-a3.json"
PLC = "experiments/pilot/pilot-v1.json"
A3_ARMS = ["00", "01p", "01s", "01", "01w"]
PL_ARMS = ["00", "10", "01s", "11s"]
CAL = {2: "experiments/cal/bc-cal-p2.json", 5: "experiments/cal/bc-cal-p5.json", 8: "experiments/cal/bc-cal-p8.json"}


def job(i, cmd, device="mps", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def write(path, jobs):
    (ROOT / path).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
    return path


def rotation(items, k, reverse):
    r = items[k % len(items):] + items[:k % len(items)]
    return r[::-1] if reverse else r


def a3_seed(s):
    jobs = [job(f"a3-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)]),
            job(f"a3-probe-K3-u4000-s{s}", ["bc2rl.rl", "probe", "--config", A3C, "--K", "3", "--bc-run", f"@/a3-bc-s{s}",
                                            "--bc-update", "4000", "--seed", str(s)])]
    for arm in rotation(A3_ARMS, s - 43, s % 2 == 1):
        jobs.append(job(f"a3-K3-u4000-s{s}-{arm}", ["bc2rl.rl", "branch", "--config", A3C, "--probe-run",
                                                    f"@/a3-probe-K3-u4000-s{s}", "--arm", arm]))
    return jobs


def pilot_seed(s, rho, update, bc_run):
    jobs = []
    for K in (1, 3):
        jobs.append(job(f"pl-probe-K{K}-s{s}", ["bc2rl.rl", "probe", "--config", PLC, "--K", str(K), "--bc-run", bc_run,
                                                "--bc-update", str(update), "--seed", str(s)]))
        for arm in rotation(PL_ARMS, s - 67 + K, K == 3):
            jobs.append(job(f"pl-K{K}-s{s}-{arm}", ["bc2rl.rl", "branch", "--config", PLC, "--probe-run",
                                                    f"@/pl-probe-K{K}-s{s}", "--arm", arm]))
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", nargs=2, metavar=("RHO", "UPDATE"))
    ap.add_argument("--cal-batches", nargs=3, metavar="BATCH", help="calibration batch ids for seeds 67, 68, 69")
    a = ap.parse_args()
    if a.pilot:
        rho, update = float(a.pilot[0]), int(a.pilot[1])
        p = {0.2: 2, 0.5: 5, 0.8: 8}[rho]
        for s, b in zip((67, 68, 69), a.cal_batches):
            write(f"experiments/pilot/pilot-s{s}.batch.json", pilot_seed(s, rho, update, f"{b}/cal-bc-p{p}-s{s}"))
        return
    plan = []
    add = lambda path, study, required=True: plan.append({"file": path, "study": study, "required": required})
    add(write("experiments/a3/data.batch.json", [job("a3-data-r3-v1", ["bc2rl.data", "--config", "experiments/a3/data-r3-v1.json"], "cpu", 2)]), "a3")
    smoke = {"id": "a3-smoke", "cpu_threads": 1, "memory_gb": 2, "device": "cpu",
             "command": ["env", "BC2RL_SMOKE=1", "{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_rl_smoke.py"]}
    add(write("experiments/a3/tests.batch.json", [job("a3-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2), smoke]), "a3")
    add(write("experiments/a3/canary-s43.batch.json", a3_seed(43)), "a3")
    for s in range(44, 67):
        add(write(f"experiments/a3/seed-s{s}.batch.json", a3_seed(s)), "a3")
    for s in (67, 68, 69):
        ps = rotation([2, 5, 8], s - 67, False)
        add(write(f"experiments/cal/cal-s{s}.batch.json",
                  [job(f"cal-bc-p{p}-s{s}", ["bc2rl.bc", "--config", CAL[p], "--seed", str(s)]) for p in ps]), "cal")
    for s in (67, 68, 69):        # placeholders until calibration selects a variant; rewritten with --pilot before running
        add(write(f"experiments/pilot/pilot-s{s}.batch.json", pilot_seed(s, 0.5, 4000, f"CAL_BATCH/cal-bc-p5-s{s}")), "pl", False)
    add(write("experiments/program2/final-tests.batch.json", [job("p2-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2)]), "p2")
    (ROOT / "experiments/program2/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")


if __name__ == "__main__":
    main()
