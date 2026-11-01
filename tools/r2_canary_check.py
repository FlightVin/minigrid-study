"""R2 engineering canary check (PROTOCOL_FREEZE Amendment 4, E). Prints no performance outcome.
Adapted from tools/r1_canary_check.py: BC stops at 4k; one probe; anchor-component stats present and finite.

Usage: .venv/bin/python tools/r2_canary_check.py BATCH [--out reports/r2/canary_check.json]

Checks the canary batch (r2-bc-s23, r2-probe-K3-u4000-s23, r2-K3-u4000-s23-01-kl0p01): exit codes; resolved
configurations (dataset, roles, K, seed, checkpoint, arm, alpha, kl_coef); fork and saved-state hashes; evaluation
schedule, layout roles and panel shapes (per-item limits equal to r2-v1 r2_select / r2_final K=3, bank r2_bank with
32/16/16 bins); attempt-record schema; counters (env_steps records equal the summaries' action counts; training
counters equal probe + continuation actions); telemetry and metrics schemas; the ledger's reading of each job.
Writes only pass/fail facts and counts.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

ATT_KEYS = {"kind", "item", "attempt", "start_kind", "start_step", "start_accessed", "limit", "K", "arrival", "success",
            "accessed", "tau", "end_step", "actions", "timeout"}
UPD_KEYS = {"phase", "actions", "pg_loss", "v_loss", "entropy", "approx_kl", "clipfrac", "anchor_kl", "grad_norm_actor",
            "explained_var", "frac_suffix_steps", "counters"}


def main():
    import torch
    from bc2rl import ppo as PP
    import analyze_r1 as A
    import ledger as L
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--out", default=str(ROOT / "reports/r2/canary_check.json"))
    a = ap.parse_args()
    b = ROOT / ".mae/runs" / a.batch
    chk, fail = {}, []

    def ok(name, cond):
        chk[name] = bool(cond)
        if not cond:
            fail.append(name)

    ex = json.loads((b / "execution.json").read_text())
    ok("batch_finished", ex["status"] in ("finished", "complete", "completed", "exited"))
    ok("all_jobs_exit_0", all(j.get("returncode") == 0 for j in ex["jobs"].values()))
    lay = json.loads((ROOT / "data/r2-v1/layouts.json").read_text())
    lim = {r: [it["layout"]["limit"] for it in lay[r] if it["layout"]["K"] == 3] for r in ("r2_select", "r2_final")}
    bank = json.loads((ROOT / "data/r2-v1/bank_competence_r2_bank.json").read_text())["3"]
    bc, pj, br = b / "r2-bc-s23", b / "r2-probe-K3-u4000-s23", b / "r2-K3-u4000-s23-01-kl0p01"
    # BC
    bcc = json.loads((bc / "config.resolved.json").read_text())
    ok("bc_dataset_conf-v1", bcc.get("dataset_id") == "conf-v1")
    ok("bc_checkpoints_saved", (bc / "actor_u4000.pt").exists() and not (bc / "actor_u16000.pt").exists())
    bcm = [json.loads(l) for l in (bc / "metrics.jsonl").read_text().splitlines() if l.strip()]
    ok("bc_metric_updates", [r["update"] for r in bcm] == [4000])
    ok("bc_losses_finite", all(r["train_loss"] == r["train_loss"] and abs(r["train_loss"]) < 1e6 for r in bcm))
    bcs = A.env_steps(bc)
    ok("bc_env_steps_equal_eval_actions", bcs == sum(r["eval_env_actions"] for r in bcm))
    # probe
    pc = json.loads((pj / "config.resolved.json").read_text())
    ps = json.loads((pj / "summary.json").read_text())
    ok("probe_config", (pc["dataset_id"], pc["diag_role"], pc["eval_role"], pc["bank_role"], pc["K"], pc["seed"],
                        pc["bc_update"], pc["bc_seed"], pc["bc_run"], pc["alpha"]) ==
       ("r2-v1", "r2_select", "r2_final", "r2_bank", 3, 23, 4000, 23, "@/r2-bc-s23", 0.0))
    fork = torch.load(pj / "fork.pt", map_location="cpu", weights_only=False)
    ok("fork_hash", PP.state_hash(fork) == ps["fork_hash"])
    for tag in ("pi0", "probe"):
        n, bk = A.read_attempts(pj / f"attempts_{tag}.jsonl")
        ok(f"probe_{tag}_on_r2_select_64x2", [n[i][0]["limit"] for i in sorted(n)] == lim["r2_select"]
           and all(len(v) == 2 for v in n.values()))
        ok(f"probe_{tag}_bank_64x4", sorted(bk) == list(range(64)) and all(len(v) == 4 for v in bk.values())
           and [bk[i][0]["bin"] for i in range(64)] == [x["bin"] for x in bank])
        ok(f"probe_{tag}_record_schema", all(set(r) >= ATT_KEYS for v in n.values() for r in v)
           and all(r["K"] == 3 for v in n.values() for r in v))
    ok("probe_env_steps_equal_summary", A.env_steps(pj) == sum(ps["actions"].values()))
    ok("probe_ledger_reading", sum(L.job_actions(pj)[0].values()) == sum(ps["actions"].values()))
    # branch
    cf = json.loads((br / "config.resolved.json").read_text())
    sm = json.loads((br / "summary.json").read_text())
    ok("branch_config", (cf["arm"], cf["alpha"], cf["kl_coef"], cf["anchor_component"], cf["dataset_id"], cf["eval_role"],
                         cf["bank_role"], cf["diag_role"], cf["K"], cf["seed"], cf["bc_update"], cf["probe_run"], cf["eval_seed"]) ==
       ("01", 0.0, 0.01, "both", "r2-v1", "r2_final", "r2_bank", "r2_select", 3, 23, 4000, str(pj), 949000))
    ok("branch_fork_hash", sm["fork_hash"] == ps["fork_hash"])
    tags = [(e["tag"], e["actions"], e["layouts"], bool(e.get("endpoint")), e["attempts"], e["bank_attempts"]) for e in sm["evals"]]
    ok("eval_schedule", tags == [("curve_126976", 126976, "diag", False, 1, 1), ("final_251904", 251904, "eval", True, 4, 4),
                                 ("curve_376832", 376832, "diag", False, 1, 1), ("final_501760", 501760, "eval", True, 4, 4)])
    for e in sm["evals"]:
        n, bk = A.read_attempts(br / f"attempts_{e['tag']}.jsonl")
        want = lim["r2_select" if e["layouts"] == "diag" else "r2_final"]
        ok(f"{e['tag']}_panel", [n[i][0]["limit"] for i in sorted(n)] == want
           and all(len(v) == e["attempts"] for v in n.values()) and all(r["K"] == 3 for v in n.values() for r in v))
        ok(f"{e['tag']}_bank", [bk[i][0]["bin"] for i in range(64)] == [x["bin"] for x in bank]
           and all(len(v) == e["bank_attempts"] for v in bk.values()))
        if e.get("endpoint"):
            try:
                A.endpoint_record(br, sm, e["tag"])
                ok(f"{e['tag']}_recomputation", True)
            except AssertionError as err:
                ok(f"{e['tag']}_recomputation ({err})", False)
    for at in (251904, 501760):
        st = torch.load(br / f"state_{at}.pt", map_location="cpu", weights_only=False)
        ok(f"state_{at}_hash", PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(at)])
    acts = sm.get("actions_this_job", sm["actions"])
    ok("branch_env_steps_equal_summary", A.env_steps(br) == sum(acts.values()))
    ok("branch_ledger_reading", sum(L.job_actions(br)[0].values()) == sum(sm["actions"].values()))
    mt = [json.loads(l) for l in (br / "metrics.jsonl").read_text().splitlines() if l.strip()]
    up = [r for r in mt if r.get("phase") == "branch"]
    ok("update_record_schema", up and all(set(r) >= UPD_KEYS for r in up))
    ok("training_counter", up[-1]["counters"]["env_actions"] == 51200 + 501760 and up[-1]["actions"] == 501760)
    ok("anchor_kl_present", all(r["anchor_kl"] is not None for r in up))
    fin = lambda x: x is not None and x == x and abs(x) < 1e9
    ok("losses_finite", all(fin(r["pg_loss"]) and fin(r["v_loss"]) and fin(r["entropy"]) for r in up))
    ok("anchor_stage_kl_and_penalty_present", all(fin(r.get("anchor_kl_prefix")) and fin(r.get("anchor_kl_suffix"))
                                                  and fin(r.get("anchor_penalty")) for r in up))
    for d in (bc, pj, br):
        t = d / "telemetry.json"
        ok(f"telemetry_{d.name}", t.exists() and "timestamp" in json.loads(t.read_text()))
    res = {"batch": a.batch, "pass": not fail, "failed": fail, "checks": chk,
           "counts": {"bc_env_steps": bcs, "probe_env_steps": A.env_steps(pj), "branch_env_steps": A.env_steps(br)}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({"pass": res["pass"], "failed": fail, "counts": res["counts"]}, indent=1))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
