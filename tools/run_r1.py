"""Runs R1 batch files in order with the Amendment 3 budget admission rule. One batch (and one job) at a time.

Usage: .venv/bin/python tools/run_r1.py BATCH_FILE [BATCH_FILE ...] [--plan seed-s15-rest seed-s16 ...] [--dry-run]

Hard incremental budget: 28.4M environment actions from START_TOTAL (the ledger total recorded before any R1 work).
Before admitting a batch (all of its jobs together):
  spent + conservative(this batch) + expected(every later planned batch) + AUDIT + reserve <= 28.4M,
  reserve = 2.0M unless completion is secure: spent + conservative(this and every later batch) + AUDIT <= 28.4M.
Never admitted if spent + conservative(this batch) > 28.4M. After a batch: it must have exited normally and cost
<= 1.10 x its conservative estimate; otherwise stop and report. Never stops for an outcome.
--plan names the batches still to run after the given ones (for the expected-commitment term); the batch files
given are always part of the plan.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv/bin/python")
START_TOTAL = 93_199_203     # ledger total before any R1 work (PROTOCOL_FREEZE Amendment 3, C6)
BUDGET = 28_400_000
RESERVE = 2_000_000
AUDIT = 200_000               # final test suite through the runner and any interactive checks (conservative)
# Per-job conservative and expected costs from the M4 K=3 jobs (5 seeds): train exact; evaluation parts are the
# M4 maxima x 1.10 (new panel); warm-up bound 17,100 (max 17,058). Expected = M4 means.
COST = {  # pattern: (conservative, expected)
    r"r1-bc-s\d+": (166_032, 147_934),
    r"r1-probe-K3-u4000-s\d+": (151_898, 140_824),
    r"r1-probe-K3-u16000-s\d+": (130_078, 122_151),
    r"r1-K3-u4000-s\d+-(00|01-kl0p01)": (746_654, 715_246),
    r"r1-K3-u16000-s\d+-(00|01-kl0p01)": (696_417, 668_697),
    r"r1-data-r1-v1": (100_000, 60_000),
    r"r1-tests": (100_000, 50_000),
}


def job_cost(jid):
    for pat, c in COST.items():
        if re.fullmatch(pat, jid):
            return c
    raise KeyError(f"no cost for job {jid}")


def batch_cost(path):
    jobs = json.loads(Path(path).read_text())["jobs"]
    return tuple(sum(job_cost(j["id"])[k] for j in jobs) for k in (0, 1))


def ledger_total():
    out = subprocess.run([PY, "tools/ledger.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return json.loads(out[out.index("{"):])["total_env_actions"]


def admit(spent, this, later):
    """this: (cons, exp) of the batch; later: list of (cons, exp). Returns (ok, details)."""
    secure = spent + this[0] + sum(c for c, _ in later) + AUDIT <= BUDGET
    reserve = 0 if secure else RESERVE
    need = spent + this[0] + sum(e for _, e in later) + AUDIT + reserve
    ok = need <= BUDGET and spent + this[0] <= BUDGET
    return ok, {"spent": spent, "batch_conservative": this[0], "later_expected": sum(e for _, e in later),
                "later_conservative": sum(c for c, _ in later), "audit": AUDIT, "reserve": reserve,
                "completion_secure": secure, "need": need, "budget": BUDGET, "admit": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="+")
    ap.add_argument("--plan", nargs="*", default=[], help="later batch files not run by this call")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    assert START_TOTAL is not None, "START_TOTAL must be frozen before R1 work"
    files = list(a.batches)
    for i, f in enumerate(files):
        later = [batch_cost(x) for x in files[i + 1:] + a.plan]
        this = batch_cost(f)
        before = ledger_total()
        ok, det = admit(before - START_TOTAL, this, later)
        print(json.dumps({"batch_file": f, **det}), flush=True)
        if not ok:
            print(json.dumps({"stop": "admission rule failed; report the shortfall to the owner", "batch_file": f}), flush=True)
            sys.exit(2)
        if a.dry_run:
            continue
        r = subprocess.run([PY, "mac-agentic-engineering/bin/mae", "run", f], cwd=ROOT)
        after = ledger_total()
        cost = after - before
        print(json.dumps({"batch_file": f, "returncode": r.returncode, "batch_actions": cost,
                          "batch_conservative": this[0], "r1_spent": after - START_TOTAL}), flush=True)
        if r.returncode != 0:
            print(json.dumps({"stop": "batch did not exit normally", "batch_file": f}), flush=True)
            sys.exit(3)
        if cost > 1.10 * this[0]:
            print(json.dumps({"stop": "batch cost above 1.10 x conservative estimate", "batch_file": f}), flush=True)
            sys.exit(4)


if __name__ == "__main__":
    main()
