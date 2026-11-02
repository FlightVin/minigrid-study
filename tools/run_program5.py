"""Runs the 2026-11-02 programme batch files (owner instruction 2026-11-02; PROTOCOL_FREEZE Amendment 7) with
battery and budget admission. One batch (and one job) at a time.

Usage: .venv/bin/python tools/run_program5.py BATCH_FILE [BATCH_FILE ...] [--dry-run]
       .venv/bin/python tools/run_program5.py --status

Budget: 70,000,000 environment actions from START_TOTAL (ledger total before any work under this authorization;
earlier allowances are not carried over). Failures, retries, tests and diagnostics count.
Battery (bc2rl.battery; 31% or lower stops execution, also on AC): as tools/run_program4.py. Before every batch the
driver refuses to start when the pause flag or hold exists, the guard is not alive with its recorded identity, its
status is stale or not "ok", or a direct reading is 31% or lower or unavailable. After a batch with the flag present
or a job that exited 75, the driver exits 10 ("battery_pause"); nothing restarts without the owner's instruction.
Budget admission before each batch:
  spent + conservative(batch) + conservative(every other incomplete required batch)
        + RESERVE_CONFIRMATION (until the gate is recorded) + AUDIT <= BUDGET
RESERVE_CONFIRMATION is the conservative cost of the complete conditional confirmation (20 seeds, two arms); it is
held back until reports/p5/gate.json exists (then the confirmation batches, if any, are in the plan instead).
Conservative costs are hard bounds: every evaluation attempt runs to its time limit (remaining time for bank
states); each certified arrival adds a planner replay bounded by the attempt's time limit; training runs its exact
executed actions; the critic warm-up adds one full episode per environment.
After a batch: exit 0 and cost <= 1.10 x conservative; otherwise stop and report.
Completion (never exit code alone): BC = summary + actor_u8000.pt; probe = summary + fork.pt; branch = a lineage (the
branch job and any resume jobs -r1, ...) whose last job has summary.json with continuation_actions 501,760 and whose
jobs together hold both endpoint attempt files with the planned row counts; data/diagnostics = summary + outputs;
tests = exit 0.
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
PLAN = ROOT / "experiments/p5/plan.json"
START_TOTAL = 311_392_581      # ledger total at the end of A4 (2026-11-02), before this authorization
BUDGET = 70_000_000
AUDIT = 300_000                # verification and analysis outside batches (conservative)
TARGET = 501_760
DATA = ROOT / "data/r5-v1"
K3_MAX_LIMIT = 157
GUARD_STALE_S = 60
ROLE_N = {"p5_select": 64, "p5_eval": 64, "c5_select": 64, "c5_final": 256, "d5_trace": 64}
# study prefix -> (eval role, attempts, bank role, endpoint tags, normal rows, bank rows)
STUDY = {"p5": ("p5_eval", 4, "p5_bank", ("dev_251904", "dev_501760"), 256, 256),
         "c5": ("c5_final", 2, "c5_bank", ("conf_251904", "conf_501760"), 512, 256)}
SELECT = {"p5": "p5_select", "c5": "c5_select"}
CONF_SEEDS = 20


def _layouts():
    return json.loads((DATA / "layouts.json").read_text())


def normal_bound(role, attempts):
    if not DATA.exists():            # before r5-v1 exists: every layout at the K=3 maximum limit
        return attempts * ROLE_N[role] * K3_MAX_LIMIT
    return attempts * sum(it["layout"]["limit"] for it in _layouts()[role] if it["layout"]["K"] == 3)


def bank_bound(role, attempts=2):
    if not DATA.exists():
        return attempts * 128 * K3_MAX_LIMIT
    return attempts * sum(s["remaining"] for s in json.loads((DATA / f"bank_competence_{role}.json").read_text())["3"])


def eval_bound(study, certify=True):
    """One endpoint evaluation: normal starts (x2 with certification: each replay is bounded by the attempt's time
    limit) + entry bank."""
    role, att, bank, *_ = STUDY[study]
    return (2 if certify else 1) * normal_bound(role, att) + bank_bound(bank)


def diag_bound(study):
    """pi0 or post-probe diagnostic: select role 64 x 2 (x2 when certified: pilot only) + entry bank x 2."""
    return (2 if study == "p5" else 1) * normal_bound(SELECT[study], 2) + bank_bound(STUDY[study][2])


def bc_bound():
    lay = json.loads((ROOT / "data/conf-v1/layouts.json").read_text())
    bank = json.loads((ROOT / "data/conf-v1/bank_competence_dev_bank.json").read_text())
    return 4 * sum(it["layout"]["limit"] for it in lay["bc_val"]) + 4 * sum(s["remaining"] for K in bank for s in bank[K])


def probe_bound(study):
    return 16_000 + 16 * K3_MAX_LIMIT + 51_200 + 2 * diag_bound(study)


def branch_bound(study):
    if study == "c5":            # certification at the primary endpoint only
        return TARGET + eval_bound(study, False) + eval_bound(study, True)
    return TARGET + 2 * eval_bound(study)


def diag5_bound():
    n = normal_bound("d5_trace", 2)
    return 64 * K3_MAX_LIMIT + 8 * (2 * n + n)       # planner prefixes; per policy: normal + certification + ref1


def confirmation_reserve():
    return CONF_SEEDS * (bc_bound() + probe_bound("c5") + 2 * branch_bound("c5"))


def cost(jid):
    """(conservative, expected) actions for one job id."""
    if jid == "p5-data-r5-v1":
        return 2 * 768 * K3_MAX_LIMIT + 50_000, 110_000
    if jid in ("p5-tests", "p5-final-tests"):
        return 150_000, 70_000
    if jid == "p5-smoke":
        return 500_000, 300_000
    if jid == "p5-diag-v1":
        return diag5_bound(), 250_000
    m = re.fullmatch(r"(p5|c5)-bc-s\d+", jid)
    if m:
        return bc_bound(), 80_000
    m = re.fullmatch(r"(p5|c5)-probe-K3-s\d+", jid)
    if m:
        return probe_bound(m.group(1)), 185_000
    m = re.fullmatch(r"(p5|c5)-K3-s\d+-(00|B5|C5|D5)(-r\d+)?", jid)
    if m:
        return branch_bound(m.group(1)), TARGET + 2 * (110_000 if m.group(1) == "c5" else 60_000)
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
    """base: <study>-K3-s<S>-<arm>. Complete only with the full allowance and both endpoint artifacts in its lineage."""
    study = base[:2]
    _, _, _, tags, n_norm, n_bank = STUDY[study]
    chain = job_dirs(base) + [d for k in range(1, 10) for d in job_dirs(f"{base}-r{k}")]
    last = [d for d in chain if (d / "summary.json").exists()
            and json.loads((d / "summary.json").read_text()).get("continuation_actions") == TARGET]
    if not last:
        return False
    for tag in tags:
        good = False
        for d in chain:
            f = d / f"attempts_{tag}.jsonl"
            if f.exists():
                kinds = [x["kind"] for x in rows(f)]
                good |= kinds.count("normal") == n_norm and kinds.count("bank") == n_bank
        if not good:
            return False
    return True


def job_complete(jid):
    if re.fullmatch(r"(p5|c5)-K3-s\d+-(00|B5|C5|D5)(-r\d+)?", jid):
        return branch_complete(re.sub(r"-r\d+$", "", jid))
    for d in job_dirs(jid):
        if not (d / "summary.json").exists():
            continue
        if re.fullmatch(r"(p5|c5)-bc-s\d+", jid) and (d / "actor_u8000.pt").exists():
            return True
        if re.fullmatch(r"(p5|c5)-probe-K3-s\d+", jid) and (d / "fork.pt").exists():
            return True
        if jid == "p5-data-r5-v1" and (DATA / "manifest.json").exists():
            return True
        if jid == "p5-diag-v1" and len(list(d.glob("attempts_*_ref1.jsonl"))) == 8:
            return True
    if jid in ("p5-tests", "p5-smoke", "p5-final-tests"):
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
    reserve = 0 if (ROOT / "reports/p5/gate.json").exists() else confirmation_reserve()
    committed = sum(batch_cost(p["file"])[0] for p in others) + AUDIT + reserve
    need = spent_total + this[0] + committed
    return need <= BUDGET, {"batch_file": path, "spent_total": spent_total, "batch_conservative": this[0],
                            "batch_expected": this[1], "committed_other_required_audit_and_reserve": committed,
                            "confirmation_reserve": reserve,
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
        reserve = 0 if (ROOT / "reports/p5/gate.json").exists() else confirmation_reserve()
        print(json.dumps({"spent_total": tot, "incomplete_batches": inc, "remaining_conservative": rem,
                          "confirmation_reserve": reserve,
                          "remaining_expected": exp, "battery_pause_flag": B.flag_path(ROOT).exists(),
                          "budget": BUDGET}, indent=1))
        return
    for f in a.batches:
        assert f in files, f"{f} is not in the programme plan"
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
