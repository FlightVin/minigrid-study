"""Deterministic, quiet batch watcher. No model calls, no retries, no retuning.

Usage: .venv/bin/python tools/watch_batch.py [--stall SECONDS] [--poll SECONDS] [--expect FILE ...]

Watches the current mae batch (.mae/current.json). Every poll it checks the supervisor identity
(pid + create time), each running job's identity, the age of its last stdout write (progress)
and of its telemetry file, and resource stops. It prints one JSON line and exits only when:
  - the batch finishes (reports status, reason, per-job exit codes and missing expected files),
  - the supervisor disappears,
  - a running job's progress or telemetry is older than --stall seconds.
"""
import argparse
import json
from pathlib import Path
import sys
import time

import psutil

ROOT = Path(__file__).resolve().parents[1]


def identity_ok(pid, created):
    try:
        return created is not None and abs(psutil.Process(pid).create_time() - created) < 1e-3
    except psutil.NoSuchProcess:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stall", type=float, default=600)
    ap.add_argument("--poll", type=float, default=20)
    ap.add_argument("--expect", nargs="*", default=["summary.json"])
    a = ap.parse_args()
    cur = ROOT / ".mae/current.json"
    first = json.loads(cur.read_text())
    batch = first["batch"]
    while True:
        s = json.loads(cur.read_text())
        if s["batch"] != batch:
            print(json.dumps({"event": "batch_replaced", "old": batch, "new": s["batch"]}))
            return 3
        out = Path(s["out"])
        if s["status"] != "running":
            jobs = {}
            for jid, rec in s["jobs"].items():
                missing = [f for f in a.expect if not (out / jid / f).exists()]
                jobs[jid] = {"status": rec.get("status"), "returncode": rec.get("returncode"), "missing": missing}
            print(json.dumps({"event": "batch_finished", "batch": batch, "status": s["status"],
                              "reason": s.get("reason"), "wall_seconds": round(s.get("wall_seconds", 0)), "jobs": jobs}))
            return 0 if s["status"] == "exited" and not any(j["missing"] for j in jobs.values()) else 1
        if not identity_ok(s["supervisor_pid"], s["supervisor_created"]):
            print(json.dumps({"event": "supervisor_lost", "batch": batch,
                              "jobs": {j: (r.get("pid"), r.get("created")) for j, r in s["jobs"].items()}}))
            return 2
        now = time.time()
        for jid, rec in s["jobs"].items():
            if rec.get("status") != "running":
                continue
            d = out / jid
            progress = max([p.stat().st_mtime for p in (d / "stdout.log", d / "metrics.jsonl") if p.exists()] or [now])
            tele = d / "telemetry.json"
            stale = {"progress_age": now - progress}
            if tele.exists():
                stale["telemetry_age"] = now - tele.stat().st_mtime
            if max(stale.values()) > a.stall and identity_ok(rec["pid"], rec.get("created")):
                print(json.dumps({"event": "stall", "batch": batch, "job": jid,
                                  **{k: round(v) for k, v in stale.items()}}))
                return 4
        time.sleep(a.poll)


if __name__ == "__main__":
    sys.exit(main())
