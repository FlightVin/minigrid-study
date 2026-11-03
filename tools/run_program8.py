"""Runs the actor capability audit (owner instruction 2026-11-03; PROTOCOL_FREEZE Amendment 10) with battery,
discharge-margin, action and fitting-compute admission. One batch (and one job) at a time.

Usage: .venv/bin/python tools/run_program8.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program8.py --status

Actions: at most CAP = 500,000 executed environment actions from START_TOTAL (ledger before the instruction), including
local tests and checks outside batches (counted by the ledger). Admission of a batch:
  spent + conservative(batch) + conservative(every other incomplete required action batch) + LOCAL <= CAP.
Conservative action bounds: every episode runs to its layout limit; check_label executes 6 actions per state.
Fitting compute: at most FIT_CAP_S = 21,600 s. Spent = wall seconds of executed fit batches (runner execution records;
an upper bound on active fitting compute). Admission: spent + conservative(batch) <= FIT_CAP_S.
Battery: the 2026-11-02c rule and helpers (31% or lower stops, also on AC; pause flag; discharge margin).
After a batch: pause exits 10; abnormal exit 3; completion unmet 5; actions above 1.10 x conservative 4.
The driver never prints fit or rollout outcomes.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from bc2rl import battery as B    # noqa: E402
from run_program5 import ledger_total, paused_after    # noqa: E402
from run_program7 import battery_admission    # noqa: E402

PY = str(ROOT / ".venv/bin/python")
PLAN = ROOT / "experiments/p8/plan.json"
START_TOTAL = 342_196_148      # ledger total after the 2026-11-02d write-up, before this instruction
CAP = 500_000
LOCAL = 20_000                 # local tests and checks outside batches (conservative allowance)
FIT_CAP_S = 21_600
TEST_BOUND = 30_000
FIT_S = {128: 0.030, 1024: 0.045}   # conservative seconds per update incl. evaluation (measured 0.011 / 0.019)


def _cfg(p):
    return json.loads((ROOT / p).read_text())


def _limits(group):
    import os
    os.environ.setdefault("MAE_PROJECT", str(ROOT))
    from bc2rl import capability as CP
    lays, _ = CP.group_layouts(ROOT, group)
    return [L.limit for L in lays]


def cost(jid):
    """(conservative actions, conservative fit seconds) of one job."""
    if jid == "p8-tests":
        return TEST_BOUND, 0
    if jid == "p8-collect":
        tot = 0
        for g in _cfg("experiments/p8/collect-v1.json")["groups"]:
            lim = _limits(g)
            tot += g["action_budget"] + g["per_layout"] * max(lim) if g.get("action_budget") else g["per_layout"] * sum(lim)
        return tot, 0
    if jid == "p8-validate":
        v = _cfg("experiments/p8/validate-v1.json")
        return 6 * 5 * v["check"]["per_stratum"] + sum(_limits(v["expert_panel"])), 0
    if jid == "p8-rollout":
        r = _cfg("experiments/p8/rollout-v1.json")
        lim = _limits(r["panel"])
        det = sum(sum(lim[:n]) for n in r.get("determinism_attempts", {}).values())
        return len(r["controllers"]) * sum(lim) + det, 0
    f = _cfg("experiments/p8/fit-v1.json")
    if jid.startswith("p8-tiny"):
        return 0, f["tiny"]["updates"] * FIT_S[128] + 120
    if jid.startswith("p8-fit"):
        h = 1024 if "1024" in jid else 128
        return 0, f["updates"] * FIT_S[h] + 120
    if jid == "p8-test":
        return 0, 600
    raise KeyError(jid)


def jobs_of(path):
    return [j["id"] for j in json.loads((ROOT / path).read_text())["jobs"]]


def batch_cost(path):
    c = [cost(j) for j in jobs_of(path)]
    return sum(x[0] for x in c), sum(x[1] for x in c)


def job_complete(jid):
    for d in sorted((ROOT / ".mae/runs").glob(f"*/{jid}")):
        s = d / "summary.json"
        if s.exists() and json.loads(s.read_text()).get("complete"):
            return True
        if s.exists() and jid == "p8-tests":
            return True
    if jid == "p8-tests":
        for ex in (ROOT / ".mae/runs").glob("*/execution.json"):
            if json.loads(ex.read_text()).get("jobs", {}).get(jid, {}).get("returncode") == 0:
                return True
    return False


def fit_seconds_spent(plan):
    fit_jobs = {j for p in plan if p["kind"] == "fit" for j in jobs_of(p["file"])}
    tot = 0.0
    for ex in (ROOT / ".mae/runs").glob("*/execution.json"):
        e = json.loads(ex.read_text())
        if set(e.get("jobs", {})) & fit_jobs and e.get("wall_seconds"):
            tot += e["wall_seconds"]
    return tot


def status(plan):
    return {"actions_spent": ledger_total() - START_TOTAL, "cap": CAP, "fit_seconds_spent": round(fit_seconds_spent(plan)),
            "fit_cap_s": FIT_CAP_S, "battery_pause_flag": B.flag_path(ROOT).exists(),
            "incomplete": [p["file"] for p in plan if not all(job_complete(j) for j in jobs_of(p["file"]))]}


def admit(path, plan):
    entry = next(p for p in plan if p["file"] == path)
    this = batch_cost(path)
    spent = ledger_total() - START_TOTAL
    others = [p for p in plan if p["file"] != path and p["kind"] == "actions"
              and not all(job_complete(j) for j in jobs_of(p["file"]))]
    committed = 0
    for p in others:
        try:
            committed += batch_cost(p["file"])[0]
        except FileNotFoundError:          # rollout config written after the fits: bounded by its frozen maximum
            committed += ROLLOUT_MAX
    need = spent + this[0] + committed + LOCAL
    fs = fit_seconds_spent(plan)
    ok = need <= CAP and (entry["kind"] != "fit" or fs + this[1] <= FIT_CAP_S)
    return ok, {"batch_file": path, "kind": entry["kind"], "actions_spent": spent, "batch_conservative_actions": this[0],
                "committed_other_actions": committed, "local_allowance": LOCAL, "need_actions": need, "cap": CAP,
                "fit_seconds_spent": round(fs), "batch_conservative_fit_seconds": round(this[1]),
                "fit_cap_s": FIT_CAP_S, "admit": ok}


ROLLOUT_MAX = 19 * 64 * 163 + 2 * 8 * 163     # 19 controllers x 64 layouts x the largest K=3 limit + determinism


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    plan = json.loads(PLAN.read_text())["batches"]
    if a.status:
        print(json.dumps(status(plan), indent=1))
        return
    files = {p["file"] for p in plan}
    for f in a.batches:
        assert f in files, f"{f} is not in the plan"
        if all(job_complete(j) for j in jobs_of(f)):
            print(json.dumps({"batch_file": f, "skip": "complete"}), flush=True)
            continue
        before = ledger_total()
        ok, det = admit(f, plan)
        print(json.dumps(det), flush=True)
        if not ok:
            print(json.dumps({"stop": "admission failed; report the shortfall", "batch_file": f}), flush=True)
            sys.exit(2)
        ok, bdet = battery_admission(max(det["batch_conservative_actions"], 1))
        print(json.dumps({"battery_admission": ok, **bdet}), flush=True)
        if not ok:
            print(json.dumps({"stop": "battery_pause", "batch_file": f}), flush=True)
            sys.exit(10)
        if a.dry_run:
            continue
        r = subprocess.run([PY, "mac-agentic-engineering/bin/mae", "run", f], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        after = ledger_total()
        cur = json.loads((ROOT / ".mae/current.json").read_text())
        print(json.dumps({"batch_file": f, "batch": cur.get("batch"), "returncode": r.returncode,
                          "batch_actions": after - before, "actions_spent": after - START_TOTAL,
                          "fit_seconds_spent": round(fit_seconds_spent(plan))}), flush=True)
        if r.returncode != 0:
            if paused_after(cur.get("out")):
                print(json.dumps({"stop": "battery_pause", "batch_file": f, "note": "resume only on the owner's instruction"}), flush=True)
                sys.exit(10)
            print(json.dumps({"stop": "batch did not exit normally", "batch_file": f}), flush=True)
            sys.exit(3)
        inc = [j for j in jobs_of(f) if not job_complete(j)]
        if inc:
            print(json.dumps({"stop": "completion criteria not met", "jobs": inc}), flush=True)
            sys.exit(5)
        if after - before > 1.10 * max(det["batch_conservative_actions"], 1) and det["batch_conservative_actions"]:
            print(json.dumps({"stop": "actions above 1.10 x conservative", "batch_file": f}), flush=True)
            sys.exit(4)


if __name__ == "__main__":
    main()
