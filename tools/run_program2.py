"""Runs batch files of the second 2026-11-01 programme (A3 anchor allocation, initialization calibration, pilot)
with budget admission. One batch (and one job) at a time. PROTOCOL_FREEZE Amendment 5, section B.
Adapted from tools/run_program.py (Amendment 4).

Usage: .venv/bin/python tools/run_program2.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program2.py --status

Hard incremental budget: 130,000,000 environment actions from START_TOTAL (ledger total before any work under this
authorization). Unused earlier allowances are not added. Actions run outside the runner after the start (local
tests) count through the ledger. Every batch file is listed in experiments/program2/plan.json with its study.
A job is complete with a summary.json, or with exit code 0 in a batch's execution record.
Before a batch (all of its jobs together):
  committed = conservative cost of every incomplete required A3 batch and of the final test batch, other than this
              one, + AUDIT
  A3 / final batch:      spent + conservative(batch) + committed <= BUDGET              (may use the 12M reserve)
  calibration / pilot:   spent + conservative(batch) + committed + RESERVE <= BUDGET    (never touches the reserve)
                         and cal + pilot spent + conservative(batch) <= 15M
                         and no required A3 batch is incomplete (the fixed study completes first)
  every batch:           spent + conservative(batch) <= BUDGET
The ledger includes every finished, failed or stopped job and the running batch up to its last record.
After a batch: exit 0 and cost <= 1.10 x its conservative estimate; otherwise stop and report. Never stops for an
outcome. Spend by study comes from the job-name prefixes (a3-, cal-, pl-, p2-) via tools/ledger.job_actions.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ledger    # noqa: E402

PY = str(ROOT / ".venv/bin/python")
PLAN = ROOT / "experiments/program2/plan.json"
START_TOTAL = 158_314_282      # ledger total at the end of the Amendment 4 programme, before this authorization
BUDGET = 130_000_000
RESERVE = 12_000_000
AUDIT = 300_000                # independent verification and diagnostics outside batches (conservative)
CEILING = {"a3": 103_000_000, "dev": 15_000_000, "p2": 1_000_000}
# (conservative, expected) per job. A3: R2 maxima (BC, probe, branch incl. 2 curve evaluations that A3 omits).
# cal: two BC evaluations (2 x R2 BC maximum, rounded up). pl: probe = R2 maximum; branch = 251,904 + hard bound of
# one endpoint evaluation (64 x 4 normal + 64 x 4 bank attempts at <= 150 actions) + margin.
COST = {
    r"a3-bc-s\d+": (95_906, 85_534),
    r"a3-probe-K3-u4000-s\d+": (153_954, 142_973),
    r"a3-K3-u4000-s\d+-(00|01p|01s|01|01w)": (740_904, 690_000),
    r"a3-data-r3-v1": (100_000, 40_000),
    r"a3-tests": (100_000, 70_000),
    r"a3-smoke": (300_000, 220_000),
    r"cal-bc-p[258]-s\d+": (200_000, 180_000),
    r"pl-probe-K[13]-s\d+": (153_954, 142_973),
    r"pl-K[13]-s\d+-(00|10|01s|11s)": (340_000, 300_000),
    r"p2-tests": (100_000, 70_000),
}
STUDY = {"a3": "a3", "cal": "dev", "pl": "dev", "p2": "p2"}


def job_cost(jid):
    for pat, c in COST.items():
        if re.fullmatch(pat, jid):
            return c
    raise KeyError(f"no cost for job {jid}")


def jobs_of(path):
    return [j["id"] for j in json.loads((ROOT / path).read_text())["jobs"]]


def batch_cost(path):
    return tuple(sum(job_cost(j)[k] for j in jobs_of(path)) for k in (0, 1))


def done_jobs():
    """Jobs that completed: a summary.json, or exit code 0 in a batch's execution record (pytest jobs write no
    summary; fixed 2026-11-01 at review 8, when the test batch counted as incomplete for ever)."""
    done = {d.name for d in (ROOT / ".mae/runs").glob("*/*") if (d / "summary.json").exists()}
    for ex in (ROOT / ".mae/runs").glob("*/execution.json"):
        jobs = json.loads(ex.read_text()).get("jobs", {})
        done |= {j for j, r in jobs.items() if r.get("returncode") == 0}
    return done


def study_of(path):
    s = {STUDY[j.split("-")[0]] for j in jobs_of(path)}
    assert len(s) == 1, f"{path} mixes studies {s}"
    return s.pop()


def ledger_total():
    out = subprocess.run([PY, "tools/ledger.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return json.loads(out[out.index("{"):])["total_env_actions"]


def study_spent():
    spent = {k: 0 for k in CEILING}
    for d in (ROOT / ".mae/runs").glob("*/*"):
        pre = d.name.split("-")[0]
        if d.is_dir() and pre in STUDY and d.name.startswith(("a3-", "cal-", "pl-", "p2-")):
            acts, _ = ledger.job_actions(d)
            spent[STUDY[pre]] += sum(acts.values())
    return spent


def admit(path, plan, done, spent_total, spent_by):
    st = study_of(path)
    this = batch_cost(path)
    later = [p for p in plan if p["study"] in ("a3", "p2") and p.get("required", True) and p["file"] != path
             and not set(jobs_of(p["file"])) <= done]
    committed = sum(batch_cost(p["file"])[0] for p in later) + AUDIT
    a3_open = [p for p in later if p["study"] == "a3"]
    need = spent_total + this[0] + committed + (0 if st in ("a3", "p2") else RESERVE)
    ok = need <= BUDGET and spent_total + this[0] <= BUDGET
    if st == "dev":
        ok &= spent_by["dev"] + this[0] <= CEILING["dev"] and not a3_open
    return ok, {"batch_file": path, "study": st, "spent_total": spent_total, "spent_study": spent_by[st],
                "batch_conservative": this[0], "batch_expected": this[1], "committed_open_required_and_audit": committed,
                "incomplete_required_other": len(later), "reserve_held": 0 if st in ("a3", "p2") else RESERVE,
                "need": need, "budget": BUDGET, "admit": ok}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text())["batches"]
    files = {p["file"] for p in plan}
    if a.status:
        done = done_jobs()
        tot = ledger_total() - START_TOTAL
        inc = [p["file"] for p in plan if p.get("required", True) and not set(jobs_of(p["file"])) <= done]
        rem = sum(batch_cost(f)[0] for f in inc)
        print(json.dumps({"spent_total": tot, "spent_by_study": study_spent(), "incomplete_batches": inc,
                          "remaining_conservative": rem, "projected_conservative_total": tot + rem + AUDIT,
                          "budget": BUDGET}, indent=1))
        return
    for f in a.batches:
        assert f in files, f"{f} is not in the programme plan"
        done = done_jobs()
        if set(jobs_of(f)) <= done:
            print(json.dumps({"batch_file": f, "skip": "all jobs already complete"}), flush=True)
            continue
        before = ledger_total()
        ok, det = admit(f, plan, done, before - START_TOTAL, study_spent())
        print(json.dumps(det), flush=True)
        if not ok:
            print(json.dumps({"stop": "admission rule failed; report the shortfall", "batch_file": f}), flush=True)
            sys.exit(2)
        if a.dry_run:
            continue
        r = subprocess.run([PY, "mac-agentic-engineering/bin/mae", "run", f], cwd=ROOT)
        after = ledger_total()
        cost = after - before
        print(json.dumps({"batch_file": f, "returncode": r.returncode, "batch_actions": cost,
                          "batch_conservative": det["batch_conservative"], "program_spent": after - START_TOTAL}), flush=True)
        if r.returncode != 0:
            print(json.dumps({"stop": "batch did not exit normally", "batch_file": f}), flush=True)
            sys.exit(3)
        if cost > 1.10 * det["batch_conservative"]:
            print(json.dumps({"stop": "batch cost above 1.10 x conservative estimate", "batch_file": f}), flush=True)
            sys.exit(4)


if __name__ == "__main__":
    main()
