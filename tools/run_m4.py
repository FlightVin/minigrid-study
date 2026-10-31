"""Runs the M4 seed batches in order with the Amendment 2 (B5) budget checks. One batch at a time.

Usage: .venv/bin/python tools/run_m4.py [--seeds 10 11 12 13 14]

Before each batch: the ledger total (tools/ledger.py) must be <= 109M. After each batch: the batch must have
exited normally and cost <= 1.25 x its conservative estimate (12.24M). Otherwise stop and report; no later
batch is submitted. Never stops for an outcome.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python")
STOP_TOTAL = 109_000_000
# 8 K=1 branches x 684,962 + 8 K=3 x 748,388 + 4 probes x 148,100 + BC evaluation 180,000
BATCH_EST = 8 * 684_962 + 8 * 748_388 + 4 * 148_100 + 180_000


def ledger_total():
    out = subprocess.run([PY, "tools/ledger.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return json.loads(out[out.index("{"):])["total_env_actions"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[10, 11, 12, 13, 14])
    a = ap.parse_args()
    for s in a.seeds:
        before = ledger_total()
        print(json.dumps({"seed": s, "ledger_before": before, "batch_estimate": BATCH_EST}), flush=True)
        if before > STOP_TOTAL:
            print(json.dumps({"stop": "ledger above 109M", "seed": s}), flush=True)
            sys.exit(2)
        r = subprocess.run([PY, "mac-agentic-engineering/bin/mae", "run", f"experiments/m4/seed-s{s}.batch.json"], cwd=ROOT)
        after = ledger_total()
        print(json.dumps({"seed": s, "returncode": r.returncode, "batch_actions": after - before, "ledger_after": after}), flush=True)
        if r.returncode != 0:
            print(json.dumps({"stop": "batch did not exit normally", "seed": s}), flush=True)
            sys.exit(3)
        if after - before > 1.25 * BATCH_EST:
            print(json.dumps({"stop": "batch cost above 1.25 x estimate", "seed": s}), flush=True)
            sys.exit(4)


if __name__ == "__main__":
    main()
