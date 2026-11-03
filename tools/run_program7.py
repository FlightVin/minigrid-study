"""Runs the 2026-11-02c corrective prefix imitation programme (owner instruction 2026-11-02c; PROTOCOL_FREEZE
Amendment 9) with battery, discharge-margin and budget admission. One batch (and one job) at a time.

Usage: .venv/bin/python tools/run_program7.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program7.py --status
       .venv/bin/python tools/run_program7.py --costs       (conservative and expected cost of every planned stage)

Budget: ceiling 80,000,000 executed environment actions from START_TOTAL (the ledger total before this authorization;
earlier allowances do not carry over). Scientific batches (category "scientific" in plan.json: data, recovery bank,
tests and smoke, BC, probes, branches, evaluation) may not take scientific spending above SCI_CAP = 72,000,000.
The remaining 8,000,000 are reserve for verification, interruptions and close-out (category "reserve"); reserve
batches may not take total spending above 80,000,000 and never fund new hypotheses, doses or seeds.
  scientific spent = (ledger total - START_TOTAL) - reserve spent; reserve spent = actions of jobs in reserve batches.
Admission of a scientific batch:
  scientific spent + conservative(batch) + conservative(every other incomplete required scientific batch)
  + AUDIT <= SCI_CAP.
Conservative costs are hard bounds: every evaluation episode runs to its limit and each certified arrival adds a
planner replay bounded by bc2rl.controller.episode_bound (limit + longest abstract suffix plan); training is the
executed whole-rollout target; warm-up episodes in flight finish (n_envs x the largest K=3 limit).
Battery (bc2rl.battery; 31% or lower stops execution, also on AC): the guard must be alive with its recorded identity
and a fresh "ok" status; the pause flag or hold refuses; a direct reading must be above 31%. Discharge margin: the
batch's conservative wall time (conservative actions / MIN_THROUGHPUT) times the guard's recent discharge rate (or
FALLBACK_RATE when no recent negative rate exists) must leave at least MARGIN_PCT above 31%.
After a batch: a pause (flag or job exit 75) exits 10; abnormal exit 3; completion criteria unmet 5; cost above
1.10 x conservative 4. The driver never prints evaluation outcomes.
"""
import argparse
from functools import lru_cache
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from bc2rl import battery as B    # noqa: E402
from run_program5 import bc_bound, guard_ok, ledger_total, paused_after    # noqa: E402  (shared, unchanged helpers)
from run_program6 import discharge_margin    # noqa: E402

PY = str(ROOT / ".venv/bin/python")
PLAN = ROOT / "experiments/p7/plan.json"
START_TOTAL = 329_624_666      # ledger total after the 2026-11-02b programme, before this authorization
CEILING = 80_000_000
SCI_CAP = 72_000_000
AUDIT = 400_000                # local checks and analysis outside batches (conservative; scientific)
DATA = ROOT / "data/r7-v1"
K3_MAX_LIMIT = 157
TARGET = 501_760
CONF_SEEDS = 20
SMOKE = 400_000
N_NEW_LAYOUTS = 64 + 64 + 256 + 64


def _cfg(name):
    return json.loads((ROOT / f"experiments/p7/{name}.json").read_text())


@lru_cache(maxsize=None)
def role_bound(role, attempts):
    """Normal-start evaluation plus certification replays: attempts x sum over layouts of episode_bound."""
    if not (DATA / "layouts.json").exists():
        return attempts * {"r7_select": 64, "r7_dev": 64, "r7_conf": 256, "r7_recov": 64}[role] * 2 * K3_MAX_LIMIT
    import bc2rl.task as T
    from bc2rl import controller as CT
    lay = json.loads((DATA / "layouts.json").read_text())[role]
    return attempts * sum(CT.episode_bound(T.Layout.from_dict(it["layout"])) for it in lay if it["layout"]["K"] == 3)


@lru_cache(maxsize=None)
def p5_bank_bound(attempts=2):
    src = DATA if (DATA / "bank_competence_p5_bank.json").exists() else ROOT / "data/r5-v1"
    return attempts * sum(s["remaining"] for s in json.loads((src / "bank_competence_p5_bank.json").read_text())["3"])


def probe_bound():
    diag = role_bound("r7_select", 2) + p5_bank_bound(2)
    return 16_000 + 16 * K3_MAX_LIMIT + 51_200 + 2 * diag


def branch_bound(study):
    cfg = _cfg("p7-v1" if study == "p7" else "c7-v1")
    return TARGET + sum(role_bound(cfg["eval_role"], e["attempts"]) for e in cfg["eval_schedule"])


def seed_bound(study, n_arms=3):
    return bc_bound() + probe_bound() + n_arms * branch_bound(study)


def confirmation_bound(selected):
    return CONF_SEEDS * seed_bound("c7", 3 if selected == "C7" else 2)


def cost(jid):
    """(conservative, expected) actions for one job id."""
    jid = re.sub(r"-r\d+$", "", jid)           # a documented retry has the cost of the original job
    if jid == "p7-data-r7-v1":
        return 2 * N_NEW_LAYOUTS * K3_MAX_LIMIT + 50_000, 140_000
    if jid == "p7-recov-v1":
        return 4 * 64 * K3_MAX_LIMIT + 6 * 5 * 96, 25_000
    if jid in ("p7-tests", "p7-final-tests"):
        return 150_000, 72_000
    if jid == "p7-smoke":
        return SMOKE, 120_000
    m = re.fullmatch(r"(p7|c7)-bc-s\d+", jid)
    if m:
        return bc_bound(), 80_000
    m = re.fullmatch(r"(p7|c7)-probe-K3-s\d+", jid)
    if m:
        return probe_bound(), 185_000
    m = re.fullmatch(r"(p7|c7)-K3-s\d+-(00|C7|R7)", jid)
    if m:
        b = branch_bound(m.group(1))
        return b, TARGET + (b - TARGET) // 2
    if jid == "p7-verify-replay":
        v = _cfg("verify-v1")
        return v["episodes"] * 2 * K3_MAX_LIMIT, v["episodes"] * 150
    raise KeyError(f"no cost for job {jid}")


def jobs_of(path):
    return [j["id"] for j in json.loads((ROOT / path).read_text())["jobs"]]


def batch_cost(path):
    return tuple(sum(cost(j)[k] for j in jobs_of(path)) for k in (0, 1))


def job_dirs(name):
    return sorted(d for d in (ROOT / ".mae/runs").glob(f"*/{name}") if d.is_dir())


def job_complete(jid):
    for d in job_dirs(jid):
        if not (d / "summary.json").exists():
            continue
        s = json.loads((d / "summary.json").read_text())
        if jid == "p7-data-r7-v1" and (DATA / "manifest.json").exists():
            return True
        if jid in ("p7-recov-v1", "p7-verify-replay") and s.get("complete") is True:
            return True
        if re.fullmatch(r"(p7|c7)-bc-s\d+", jid) and s.get("updates") == 8000:
            return True
        if re.fullmatch(r"(p7|c7)-probe-K3-s\d+", jid) and s.get("fork_hash"):
            return True
        if re.fullmatch(r"(p7|c7)-K3-s\d+-(00|C7|R7)", jid) and s.get("continuation_actions") == TARGET:
            return True
    if jid in ("p7-tests", "p7-smoke", "p7-final-tests"):
        for ex in (ROOT / ".mae/runs").glob("*/execution.json"):
            if json.loads(ex.read_text()).get("jobs", {}).get(jid, {}).get("returncode") == 0:
                return True
    return False


def reserve_spent(plan):
    from ledger import job_actions
    ids = {j for p in plan if p.get("category") == "reserve" for j in jobs_of(p["file"])}
    tot = 0
    for jid in ids:
        for d in job_dirs(jid):
            tot += sum(job_actions(d)[0].values())
    return tot


def spent(plan):
    total = ledger_total() - START_TOTAL
    res = reserve_spent(plan)
    return {"total": total, "reserve": res, "scientific": total - res}


def battery_admission(conservative):
    ok, det = guard_ok()
    if not ok:
        return False, {"reason": det}
    ok, det = B.admission(ROOT)
    if not ok:
        return False, det
    ok2, det2 = discharge_margin(conservative)
    return ok2, {**det, **det2}


def admit(path, plan, sp):
    entry = next(p for p in plan if p["file"] == path)
    this = batch_cost(path)
    if entry.get("category") == "reserve":
        need = sp["total"] + this[0]
        return need <= CEILING, {"batch_file": path, "category": "reserve", "spent": sp, "batch_conservative": this[0],
                                 "need_total": need, "ceiling": CEILING, "admit": need <= CEILING}
    others = [p for p in plan if p.get("required", True) and p["file"] != path and p.get("category") != "reserve"
              and not all(job_complete(j) for j in jobs_of(p["file"]))]
    committed = sum(batch_cost(p["file"])[0] for p in others) + AUDIT
    need = sp["scientific"] + this[0] + committed
    return need <= SCI_CAP, {"batch_file": path, "category": "scientific", "spent": sp, "batch_conservative": this[0],
                             "batch_expected": this[1], "committed_other_required_and_audit": committed,
                             "incomplete_required_other": len(others), "need_scientific": need, "sci_cap": SCI_CAP,
                             "protection_left_worst_case": SCI_CAP - need, "admit": need <= SCI_CAP}


def costs():
    dev = 6 * seed_bound("p7")
    prep = sum(cost(j)[0] for j in ("p7-data-r7-v1", "p7-recov-v1", "p7-tests", "p7-smoke"))
    return {"bc": bc_bound(), "probe": probe_bound(), "branch_dev": branch_bound("p7"), "branch_conf": branch_bound("c7"),
            "seed_dev": seed_bound("p7"), "prep": prep, "dev_total": dev, "audit_allowance": AUDIT,
            "confirmation_C7": confirmation_bound("C7"), "confirmation_R7": confirmation_bound("R7"),
            "planned_scientific_worst_case_C7": prep + dev + AUDIT + confirmation_bound("C7"),
            "sci_cap": SCI_CAP, "ceiling": CEILING, "data_bounds_exact": (DATA / "layouts.json").exists()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--costs", action="store_true")
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text())["batches"]
    files = {p["file"] for p in plan}
    if a.costs:
        print(json.dumps(costs(), indent=1))
        return
    if a.status:
        inc = [p["file"] for p in plan if p.get("required", True) and not all(job_complete(j) for j in jobs_of(p["file"]))]
        print(json.dumps({"spent": spent(plan), "incomplete_batches": inc,
                          "battery_pause_flag": B.flag_path(ROOT).exists(), "sci_cap": SCI_CAP, "ceiling": CEILING},
                         indent=1))
        return
    for f in a.batches:
        assert f in files, f"{f} is not in the programme plan"
        if all(job_complete(j) for j in jobs_of(f)):
            print(json.dumps({"batch_file": f, "skip": "all jobs already complete"}), flush=True)
            continue
        before = ledger_total()
        ok, det = admit(f, plan, spent(plan))
        print(json.dumps(det), flush=True)
        if not ok:
            print(json.dumps({"stop": "admission rule failed; report the shortfall", "batch_file": f}), flush=True)
            sys.exit(2)
        ok, bdet = battery_admission(det["batch_conservative"])
        print(json.dumps({"battery_admission": ok, **bdet}), flush=True)
        if not ok:
            print(json.dumps({"stop": "battery_pause", "batch_file": f, "detail": bdet}), flush=True)
            sys.exit(10)
        if a.dry_run:
            continue
        r = subprocess.run([PY, "mac-agentic-engineering/bin/mae", "run", f], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        after = ledger_total()
        cur = json.loads((ROOT / ".mae/current.json").read_text())
        print(json.dumps({"batch_file": f, "batch": cur.get("batch"), "returncode": r.returncode,
                          "batch_actions": after - before, "batch_conservative": det["batch_conservative"],
                          "program_spent": after - START_TOTAL}), flush=True)
        if r.returncode != 0:
            if paused_after(cur.get("out")):
                print(json.dumps({"stop": "battery_pause", "batch_file": f, "batch": cur.get("batch"),
                                  "note": "paused, not complete; resume only on the owner's instruction"}), flush=True)
                sys.exit(10)
            print(json.dumps({"stop": "batch did not exit normally", "batch_file": f}), flush=True)
            sys.exit(3)
        incomplete = [j for j in jobs_of(f) if not job_complete(j)]
        if incomplete:
            print(json.dumps({"stop": "exit 0 but completion criteria not met", "jobs": incomplete}), flush=True)
            sys.exit(5)
        if after - before > 1.10 * det["batch_conservative"]:
            print(json.dumps({"stop": "batch cost above 1.10 x conservative estimate", "batch_file": f}), flush=True)
            sys.exit(4)


if __name__ == "__main__":
    main()
