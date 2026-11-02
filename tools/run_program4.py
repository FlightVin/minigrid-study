"""Runs the A4 batch files (owner instruction 2026-11-01c; PROTOCOL_FREEZE Amendment 6) with battery and budget
admission. One batch (and one job) at a time.

Usage: .venv/bin/python tools/run_program4.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program4.py --status

Budget: 70,000,000 environment actions from START_TOTAL (ledger total before any work under this authorization;
earlier allowances are not carried over). Failures, retries, tests and diagnostics count.
Battery (bc2rl.battery; 31% or lower stops execution, also on AC). Before every batch the driver refuses to start
when: the persistent pause flag exists; the admission hold exists; the guard (tools/battery_guard.py) is not alive
with its recorded identity or its status is older than 60 s or not "ok"; or a direct reading is 31% or lower or
unavailable after retries. Every job also checks admission at start. After a batch that stopped with the pause
flag present, or with a job that exited 75 (checkpoint-and-pause), the driver exits 10 ("battery_pause"): the work
is paused, never complete, and nothing restarts until the owner instructs a resume.
Budget admission before each batch:
  spent + conservative(batch) + conservative(every other incomplete required batch) + AUDIT <= BUDGET
so the remaining fixed study always fits in the worst case; what is left is the protection for failures and
validation. Conservative costs are hard bounds: every evaluation attempt runs to its time limit (remaining time
for bank states), training runs its exact executed actions, the critic warm-up adds one full episode per
environment, data generation replays every planned layout at its time limit; BC evaluation from the frozen roles.
After a batch: exit 0 and cost <= 1.10 x conservative; otherwise stop and report.
Completion (never exit code alone): BC = summary + actor_u8000.pt; probe = summary + fork.pt; branch = a lineage
(the branch job and any resume jobs -r1, -r2, ...) whose last job has summary.json with continuation_actions
1,001,472 and whose jobs together hold the three endpoint attempt files with the planned row counts; data and bank =
summary + output manifest; tests = exit 0.
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
import ledger    # noqa: E402
from bc2rl import battery as B    # noqa: E402

PY = str(ROOT / ".venv/bin/python")
PLAN = ROOT / "experiments/a4/plan.json"
START_TOTAL = 255_665_568      # ledger total at the end of the 2026-11-01b programme, before this authorization
BUDGET = 70_000_000
AUDIT = 300_000                # verification and diagnostics outside batches (conservative)
TARGET = 1_001_472
ENDPOINTS = (251_904, 501_760, 1_001_472)
DATA = ROOT / "data/r4-v1"
ARRIVAL = ROOT / "data/a4-arrival-v1/arrival_bank.json"
ARRIVAL_CAP, K3_MAX_LIMIT = 96, 157
GUARD_STALE_S = 60


def _layouts():
    return json.loads((DATA / "layouts.json").read_text())


ROLE_N = {"a4_select": 64, "a4_final": 256}


def normal_bound(role, attempts=2):
    if not DATA.exists():            # before r4-v1 exists: every layout at the K=3 maximum limit
        return attempts * ROLE_N[role] * K3_MAX_LIMIT
    return attempts * sum(it["layout"]["limit"] for it in _layouts()[role] if it["layout"]["K"] == 3)


def banks_bound(attempts=2):
    """Entry bank + actual-arrival bank, every attempt to the state's remaining time (cap x max limit before the
    arrival bank exists)."""
    entry = (attempts * sum(s["remaining"] for s in json.loads((DATA / "bank_competence_a4_bank.json").read_text())["3"])
             if DATA.exists() else attempts * 128 * K3_MAX_LIMIT)
    arr = (attempts * sum(s["remaining"] for s in json.loads(ARRIVAL.read_text())["states"]) if ARRIVAL.exists()
           else attempts * ARRIVAL_CAP * K3_MAX_LIMIT)
    return entry + arr


def eval_bound():
    """Hard bound of one A4 endpoint evaluation (a4_final 256 x 2 + both banks x 2)."""
    return normal_bound("a4_final") + banks_bound()


def diag_bound():
    """Hard bound of one probe diagnostic (pi0 or post-probe): a4_select 64 x 2 + both banks x 2."""
    return normal_bound("a4_select") + banks_bound()


def bc_bound():
    lay = json.loads((ROOT / "data/conf-v1/layouts.json").read_text())
    bank = json.loads((ROOT / "data/conf-v1/bank_competence_dev_bank.json").read_text())
    return 4 * sum(it["layout"]["limit"] for it in lay["bc_val"]) + 4 * sum(s["remaining"] for K in bank for s in bank[K])


def cost(jid):
    """(conservative, expected) actions for one job id."""
    if re.fullmatch(r"a4-data-r4-v1", jid):
        return 320_000, 130_000
    if re.fullmatch(r"a4-arrival-v1", jid):
        return 512 * K3_MAX_LIMIT, 70_000
    if re.fullmatch(r"a4-tests", jid):
        return 100_000, 70_000
    if re.fullmatch(r"a4-smoke", jid):
        return 450_000, 300_000
    if re.fullmatch(r"p4-tests", jid):
        return 100_000, 70_000
    if re.fullmatch(r"a4-bc-s\d+", jid):
        return bc_bound(), 80_000
    if re.fullmatch(r"a4-probe-K3-s\d+", jid):
        return 16_000 + 16 * K3_MAX_LIMIT + 51_200 + 2 * diag_bound(), 185_000
    if re.fullmatch(r"a4-K3-s\d+-(00|01s)(-r\d+)?", jid):
        return TARGET + len(ENDPOINTS) * eval_bound(), TARGET + 3 * 110_000
    raise KeyError(f"no cost for job {jid}")


def jobs_of(path):
    return [j["id"] for j in json.loads((ROOT / path).read_text())["jobs"]]


def batch_cost(path):
    return tuple(sum(cost(j)[k] for j in jobs_of(path)) for k in (0, 1))


def job_dirs(name):
    return sorted(d for d in (ROOT / ".mae/runs").glob(f"*/{name}") if d.is_dir())


def rows(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def branch_complete(base):
    """base: a4-K3-s<S>-<arm>. Complete only with the full allowance and all endpoint artifacts across its lineage."""
    chain = job_dirs(base) + [d for k in range(1, 10) for d in job_dirs(f"{base}-r{k}")]
    last = [d for d in chain if (d / "summary.json").exists()
            and json.loads((d / "summary.json").read_text()).get("continuation_actions") == TARGET]
    if not last:
        return False
    n_arr = len(json.loads(ARRIVAL.read_text())["states"]) if ARRIVAL.exists() else None
    for at in ENDPOINTS:
        files = [d / f"attempts_final_{at}.jsonl" for d in chain if (d / f"attempts_final_{at}.jsonl").exists()]
        good = False
        for f in files:
            r = rows(f)
            kinds = [x["kind"] for x in r]
            if kinds.count("normal") == 512 and kinds.count("bank") == 256 and kinds.count("bank_extra") == 2 * n_arr:
                good = True
        if not good:
            return False
    return True


def job_complete(jid):
    if re.fullmatch(r"a4-K3-s\d+-(00|01s)(-r\d+)?", jid):
        return branch_complete(re.sub(r"-r\d+$", "", jid))
    for d in job_dirs(jid):
        if not (d / "summary.json").exists():
            continue
        if jid.startswith("a4-bc-") and (d / "actor_u8000.pt").exists():
            return True
        if jid.startswith("a4-probe-") and (d / "fork.pt").exists():
            return True
        if jid in ("a4-data-r4-v1",) and (DATA / "manifest.json").exists():
            return True
        if jid == "a4-arrival-v1" and (ROOT / "data/a4-arrival-v1/manifest.json").exists():
            return True
    if jid in ("a4-tests", "a4-smoke", "p4-tests"):
        for ex in (ROOT / ".mae/runs").glob("*/execution.json"):
            if json.loads(ex.read_text()).get("jobs", {}).get(jid, {}).get("returncode") == 0:
                return True
    return False


def ledger_total():
    out = subprocess.run([PY, "tools/ledger.py"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return json.loads(out[out.index("{"):])["total_env_actions"]


def guard_ok(now=None):
    """The battery guard is alive (pid + start time) and its last status is fresh and ok."""
    import psutil
    now = now or time.time()
    pidf, stf = ROOT / ".mae/monitor/battery_guard.pid", ROOT / ".mae/monitor/battery_status.json"
    if not (pidf.exists() and stf.exists()):
        return False, "battery guard not started"
    g = json.loads(pidf.read_text())
    try:
        p = psutil.Process(g["pid"])
        alive = abs(p.create_time() - g["started"]) < 5 and "battery_guard" in " ".join(p.cmdline())
    except psutil.NoSuchProcess:
        alive = False
    if not alive:
        return False, "battery guard not alive"
    st = json.loads(stf.read_text())
    if now - st["unix"] > GUARD_STALE_S:
        return False, "battery guard status stale"
    if st["decision"] != "ok":
        return False, f"battery guard decision {st['decision']}"
    return True, st


def battery_admission():
    ok, det = guard_ok()
    if not ok:
        return False, {"reason": det}
    return B.admission(ROOT)


def paused_after(out_dir):
    if B.flag_path(ROOT).exists():
        return True
    ex = Path(out_dir) / "execution.json" if out_dir else None
    if ex and ex.exists():
        return any(r.get("returncode") == B.PAUSED_EXIT for r in json.loads(ex.read_text()).get("jobs", {}).values())
    return False


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
            exp = sum(batch_cost(f)[1] for f in inc)
        except RuntimeError as e:
            rem = exp = str(e)
        print(json.dumps({"spent_total": tot, "incomplete_batches": inc, "remaining_conservative": rem,
                          "remaining_expected": exp, "battery_pause_flag": B.flag_path(ROOT).exists(),
                          "budget": BUDGET}, indent=1))
        return
    for f in a.batches:
        assert f in files, f"{f} is not in the A4 plan"
        if all(job_complete(j) for j in jobs_of(f)):
            print(json.dumps({"batch_file": f, "skip": "all jobs already complete"}), flush=True)
            continue
        ok, det = battery_admission()
        print(json.dumps({"battery_admission": ok, **det}), flush=True)
        if not ok:
            print(json.dumps({"stop": "battery_pause", "batch_file": f, "detail": det}), flush=True)
            sys.exit(10)
        before = ledger_total()
        ok, det = admit(f, plan, before - START_TOTAL)
        print(json.dumps(det), flush=True)
        if not ok:
            print(json.dumps({"stop": "admission rule failed; report the shortfall", "batch_file": f}), flush=True)
            sys.exit(2)
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
