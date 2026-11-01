"""Runs batch files of the 2026-11-01 programme (R2, cross-panel E1, components E2) with budget admission.
One batch (and one job) at a time. PROTOCOL_FREEZE Amendment 4, section B.

Usage: .venv/bin/python tools/run_program.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program.py --status

Hard incremental budget: 50,000,000 environment actions from START_TOTAL (corrected ledger total before any work
under the 2026-11-01 authorization). The unused R1 allowance is not added.
Every batch file of the programme is listed in experiments/program/plan.json with its study. A batch is complete
when every job in it has a summary.json (in any batch directory). Before a batch (all of its jobs together):
  committed = conservative cost of every incomplete R2 batch in the plan other than this one + AUDIT
  R2 batch:          spent + conservative(batch) + committed <= BUDGET            (may use the 4M reserve)
  exploratory batch: spent + conservative(batch) + committed + RESERVE <= BUDGET  (never touches the reserve)
                     and study spent + conservative(batch) <= the study ceiling (E1 4M, E2 4M)
                     and no R2 batch in the plan is incomplete (R2 completes first)
  every batch:       spent + conservative(batch) <= BUDGET
After a batch: exit 0 and cost <= 1.10 x its conservative estimate; otherwise stop and report. Never stops for an
outcome. Spend by study comes from the job-name prefixes (r2-, xp-, comp-, prog-) via tools/ledger.job_actions.
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
PLAN = ROOT / "experiments/program/plan.json"
START_TOTAL = 118_670_430      # corrected ledger total before the programme (R1 audit, 2026-11-01)
BUDGET = 50_000_000
RESERVE = 4_000_000
AUDIT = 300_000                # final runner test job + independent verification (conservative)
CEILING = {"r2": 38_000_000, "xp": 4_000_000, "comp": 4_000_000, "prog": 1_000_000}
# (conservative, expected) per job. R2: R1 early-job maxima, evaluation x 1.10, train exact, warm-up bound 17,100.
# xp / comp: hard upper bounds (every episode at its time limit) from the frozen panels.
COST = {
    r"r2-bc-s\d+": (95_906, 85_534),
    r"r2-probe-K3-u4000-s\d+": (153_954, 142_973),
    r"r2-K3-u4000-s\d+-(00|01-kl0p01)": (740_904, 709_313),
    r"r2-data-r2-v1": (100_000, 40_000),
    r"r2-tests": (100_000, 60_000),
    r"r2-smoke": (300_000, 220_000),
    r"r2-drill": (0, 0),
    r"xp-(m4|r1)-s\d+-(00|01)": (111_548, 100_000),
    r"comp-K3-u4000-s\d+-(00|01p|01s|01)": (283_302, 275_000),
    r"prog-tests": (100_000, 60_000),
}
STUDY = {"r2": "r2", "xp": "xp", "comp": "comp", "prog": "prog"}


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
    return {d.name for d in (ROOT / ".mae/runs").glob("*/*") if (d / "summary.json").exists()}


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
        if d.is_dir() and pre in STUDY and (d.name.startswith(("r2-", "xp-", "comp-", "prog-"))):
            acts, _ = ledger.job_actions(d)
            spent[STUDY[pre]] += sum(acts.values())
    return spent


def admit(path, plan, done, spent_total, spent_by):
    st = study_of(path)
    this = batch_cost(path)
    later_r2 = [p for p in plan if p["study"] == "r2" and p["file"] != path and not set(jobs_of(p["file"])) <= done]
    committed = sum(batch_cost(p["file"])[0] for p in later_r2) + AUDIT
    need = spent_total + this[0] + committed + (0 if st in ("r2", "prog") else RESERVE)
    ok = need <= BUDGET and spent_total + this[0] <= BUDGET
    if st in ("xp", "comp"):
        ok &= spent_by[st] + this[0] <= CEILING[st] and not later_r2
    return ok, {"batch_file": path, "study": st, "spent_total": spent_total, "spent_study": spent_by[st],
                "batch_conservative": this[0], "batch_expected": this[1], "committed_r2_and_audit": committed,
                "incomplete_r2_batches_other": len(later_r2), "reserve_held": 0 if st in ("r2", "prog") else RESERVE,
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
        inc = [p["file"] for p in plan if not set(jobs_of(p["file"])) <= done]
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
