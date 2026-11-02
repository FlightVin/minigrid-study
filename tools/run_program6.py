"""Runs the 2026-11-02b frozen-policy controller diagnostics (owner instruction 2026-11-02b; PROTOCOL_FREEZE
Amendment 8) with battery, discharge-margin and budget admission. One batch (and one job) at a time.

Usage: .venv/bin/python tools/run_program6.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program6.py --status

Budget: 2,000,000 executed environment actions from START_TOTAL (ledger total before this authorization; earlier
allowances do not carry over). Data planning replay, tests, canary, evaluation, certification replays, failed runs and
verification replays all count (bc2rl.accounting via the runner and .mae/unmanaged_actions for local runs).
Admission before each batch:
  spent + conservative(batch) + conservative(every other incomplete required batch) + AUDIT <= BUDGET.
Conservative costs are hard bounds (bc2rl.controller.episode_bound): every episode runs to its time limit, and each
certified arrival adds a planner replay bounded by the remaining time at the earliest physically possible arrival.
Battery (bc2rl.battery; 31% or lower stops execution, also on AC): the guard must be alive with its recorded identity
and a fresh "ok" status; the pause flag or hold refuses; a direct reading must be above 31%. Discharge margin: the
batch's conservative wall time (conservative actions / MIN_THROUGHPUT) times the guard's recent discharge rate (or
FALLBACK_RATE when no recent negative rate exists) must leave at least MARGIN_PCT above 31%.
After a batch: a pause (flag or job exit 75) exits 10; abnormal exit 3; completion criteria unmet 5; cost above
1.10 x conservative 4.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from bc2rl import battery as B    # noqa: E402
from run_program5 import guard_ok, ledger_total, paused_after    # noqa: E402  (shared, unchanged helpers)

PY = str(ROOT / ".venv/bin/python")
PLAN = ROOT / "experiments/p6/plan.json"
START_TOTAL = 328_228_453      # ledger total after the 2026-11-02 programme, before this authorization
BUDGET = 2_000_000
AUDIT = 60_000                 # local tests and checks outside batches (conservative)
DATA = ROOT / "data/r6-v1"
K3_MAX_LIMIT = 157
MIN_THROUGHPUT = 150.0         # actions per second, conservative (for the discharge margin only)
FALLBACK_RATE = 20.0           # percent per hour when no recent discharge estimate exists
MARGIN_PCT = 5.0


def panel():
    import bc2rl.task as T
    lay = json.loads((DATA / "layouts.json").read_text())["d6_ctrl"]
    return [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3]


def ctrl_cfg(name):
    return json.loads((ROOT / f"experiments/p6/{name}.json").read_text())


def eval_bound(cfg, layouts):
    from bc2rl import controller as CT
    per = sum(CT.episode_bound(L) for L in layouts[:cfg["n_layouts"]])
    return per * cfg["attempts"] * len(cfg["conditions"]) * len(cfg["policies"])


def cost(jid):
    """(conservative, expected) actions for one job id."""
    if jid == "p6-data-r6-v1":
        return 2 * 128 * K3_MAX_LIMIT + 20_000, 25_000
    if jid in ("p6-tests", "p6-final-tests"):
        return 150_000, 70_000
    if jid == "p6-canary":
        import bc2rl.task as T
        cfg = ctrl_cfg("canary-v1")
        lay = json.loads((ROOT / "data/r6-v1/layouts.json").read_text())[cfg["role"]]
        ls = [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3]
        return eval_bound(cfg, ls), eval_bound(cfg, ls) // 3
    m = re.fullmatch(r"p6-ctrl-(\w+)", jid)
    if m:
        cfg = ctrl_cfg("ctrl-v1")
        cfg = {**cfg, "policies": {m.group(1): cfg["policies"][m.group(1)]}}
        b = eval_bound(cfg, panel())
        return b, b // 3
    if jid == "p6-verify-replay":
        from bc2rl import controller as CT
        cfg = ctrl_cfg("ctrl-v1")
        n = cfg["verify_sample_per_cell"] * len(cfg["policies"]) * len(cfg["conditions"])
        return n * max(CT.episode_bound(L) for L in panel()), n * 120
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
        if jid == "p6-data-r6-v1" and (DATA / "manifest.json").exists():
            return True
        if (jid == "p6-canary" or jid.startswith("p6-ctrl-")) and s.get("complete") is True:
            return True
        if jid == "p6-verify-replay" and s.get("complete") is True:
            return True
    if jid in ("p6-tests", "p6-final-tests"):
        for ex in (ROOT / ".mae/runs").glob("*/execution.json"):
            if json.loads(ex.read_text()).get("jobs", {}).get(jid, {}).get("returncode") == 0:
                return True
    return False


def discharge_margin(conservative):
    st = json.loads((ROOT / ".mae/monitor/battery_status.json").read_text())
    rate = st.get("rate_pct_per_hour")
    used_rate = -rate if (rate is not None and rate < 0) else (0.0 if st.get("source") == "AC" and rate is not None
                                                                 else FALLBACK_RATE)
    hours = conservative / MIN_THROUGHPUT / 3600
    predicted = st["percent"] - used_rate * hours
    ok = predicted >= B.LIMIT + MARGIN_PCT
    return ok, {"percent": st["percent"], "source": st.get("source"), "rate_used_pct_per_hour": used_rate,
                "conservative_hours": round(hours, 3), "predicted_end_percent": round(predicted, 2),
                "required": B.LIMIT + MARGIN_PCT, "margin_ok": ok}


def battery_admission(conservative):
    ok, det = guard_ok()
    if not ok:
        return False, {"reason": det}
    ok, det = B.admission(ROOT)
    if not ok:
        return False, det
    ok2, det2 = discharge_margin(conservative)
    return ok2, {**det, **det2}


def admit(path, plan, spent_total):
    this = batch_cost(path)
    others = [p for p in plan if p.get("required", True) and p["file"] != path
              and not all(job_complete(j) for j in jobs_of(p["file"]))]
    committed = sum(batch_cost(p["file"])[0] for p in others) + AUDIT
    need = spent_total + this[0] + committed
    return need <= BUDGET, {"batch_file": path, "spent_total": spent_total, "batch_conservative": this[0],
                            "batch_expected": this[1], "committed_other_required_and_audit": committed,
                            "incomplete_required_other": len(others), "need": need, "budget": BUDGET,
                            "protection_left_worst_case": BUDGET - need, "admit": need <= BUDGET}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text())["batches"]
    files = {p["file"] for p in plan}
    if a.status:
        tot = ledger_total() - START_TOTAL
        inc = [p["file"] for p in plan if p.get("required", True) and not all(job_complete(j) for j in jobs_of(p["file"]))]
        try:
            rem = sum(batch_cost(f)[0] for f in inc)
        except (FileNotFoundError, KeyError) as e:
            rem = f"unavailable: {e}"
        print(json.dumps({"spent_total": tot, "incomplete_batches": inc, "remaining_conservative": rem,
                          "battery_pause_flag": B.flag_path(ROOT).exists(), "budget": BUDGET}, indent=1))
        return
    for f in a.batches:
        assert f in files, f"{f} is not in the programme plan"
        if all(job_complete(j) for j in jobs_of(f)):
            print(json.dumps({"batch_file": f, "skip": "all jobs already complete"}), flush=True)
            continue
        before = ledger_total()
        ok, det = admit(f, plan, before - START_TOTAL)
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
        r = subprocess.run([PY, "mac-agentic-engineering/bin/mae", "run", f], cwd=ROOT)
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
