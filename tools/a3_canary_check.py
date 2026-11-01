"""A3 engineering canary check (PROTOCOL_FREEZE Amendment 5). Prints no performance outcome.
Adapted from tools/r2_canary_check.py. The canary is planned seed 43 (BC, probe, all five branches in one batch).

Usage: .venv/bin/python tools/a3_canary_check.py BATCH [--out reports/a3/canary_check.json]

Checks: exit codes; resolved configurations (dataset r3-v1, roles a3_*, K, seed, checkpoint, arm, alpha, base and
effective coefficients, component); fork and saved-state hashes, and that each saved state holds every part needed
for exact resumption (exact CPU resume itself is tested by the RL smoke tests); evaluation schedule (251,904 and 501,760 only, no curve points); panel shapes
(per-item limits equal to r3-v1 a3_select / a3_final K=3; bank a3_bank 32/16/16); attempt-record schema; counters
(env_steps records equal summaries; training counters equal probe + continuation actions); per-update statistics
finite; applied penalty consistent with the arm (A: none; D and E: penalty = base coefficient x anchor KL on the same
rows; B and C: 0 <= penalty <= base x anchor KL); update-size diagnostics present; telemetry; ledger reading.
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
    ap.add_argument("--out", default=str(ROOT / "reports/a3/canary_check.json"))
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
    lay = json.loads((ROOT / "data/r3-v1/layouts.json").read_text())
    lim = {r: [it["layout"]["limit"] for it in lay[r] if it["layout"]["K"] == 3] for r in ("a3_select", "a3_final")}
    bank = json.loads((ROOT / "data/r3-v1/bank_competence_a3_bank.json").read_text())["3"]
    S = 43
    bc, pj = b / f"a3-bc-s{S}", b / f"a3-probe-K3-u4000-s{S}"
    # BC
    bcc = json.loads((bc / "config.resolved.json").read_text())
    ok("bc_dataset_conf-v1", bcc.get("dataset_id") == "conf-v1" and "prefix_prob" not in bcc)
    ok("bc_checkpoint_saved", (bc / "actor_u4000.pt").exists())
    bcm = [json.loads(l) for l in (bc / "metrics.jsonl").read_text().splitlines() if l.strip()]
    ok("bc_metric_updates", [r["update"] for r in bcm] == [4000])
    ok("bc_losses_finite", all(r["train_loss"] == r["train_loss"] and abs(r["train_loss"]) < 1e6 for r in bcm))
    bcs = A.env_steps(bc)
    ok("bc_env_steps_equal_eval_actions", bcs == sum(r["eval_env_actions"] for r in bcm))
    ok("bc_raw_attempts_saved", (bc / "attempts_u4000.jsonl").exists())
    # probe
    pc = json.loads((pj / "config.resolved.json").read_text())
    ps = json.loads((pj / "summary.json").read_text())
    ok("probe_config", (pc["dataset_id"], pc["diag_role"], pc["eval_role"], pc["bank_role"], pc["K"], pc["seed"],
                        pc["bc_update"], pc["bc_seed"], pc["bc_run"], pc["alpha"]) ==
       ("r3-v1", "a3_select", "a3_final", "a3_bank", 3, S, 4000, S, f"@/a3-bc-s{S}", 0.0))
    fork = torch.load(pj / "fork.pt", map_location="cpu", weights_only=False)
    ok("fork_hash", PP.state_hash(fork) == ps["fork_hash"])
    for tag in ("pi0", "probe"):
        n, bk = A.read_attempts(pj / f"attempts_{tag}.jsonl")
        ok(f"probe_{tag}_on_a3_select_64x2", [n[i][0]["limit"] for i in sorted(n)] == lim["a3_select"]
           and all(len(v) == 2 for v in n.values()))
        ok(f"probe_{tag}_bank_64x4", sorted(bk) == list(range(64)) and all(len(v) == 4 for v in bk.values())
           and [bk[i][0]["bin"] for i in range(64)] == [x["bin"] for x in bank])
        ok(f"probe_{tag}_record_schema", all(set(r) >= ATT_KEYS for v in n.values() for r in v)
           and all(r["K"] == 3 for v in n.values() for r in v))
    ok("probe_env_steps_equal_summary", A.env_steps(pj) == sum(ps["actions"].values()))
    ok("probe_ledger_reading", sum(L.job_actions(pj)[0].values()) == sum(ps["actions"].values()))
    import analyze_a3 as A3
    counts = {"bc_env_steps": bcs, "probe_env_steps": A.env_steps(pj)}
    for arm, tag in A3.ARMS.items():
        br = b / f"a3-K3-u4000-s{S}-{tag}"
        base, comp, eff = A3.IDENT[arm]
        cf = json.loads((br / "config.resolved.json").read_text())
        sm = json.loads((br / "summary.json").read_text())
        ok(f"{arm}_config", (cf["arm"], cf["alpha"], cf["anchor_component"], cf["dataset_id"], cf["eval_role"], cf["bank_role"],
                             cf["diag_role"], cf["K"], cf["seed"], cf["bc_update"], cf["probe_run"], cf["eval_seed"]) ==
           (tag, 0.0, comp, "r3-v1", "a3_final", "a3_bank", "a3_select", 3, S, 4000, str(pj), 959000)
           and abs(cf["kl_coef"] - base) < 1e-15 and all(abs(x - y) < 1e-15 for x, y in zip(sm["kl_effective_prefix_suffix"], eff)))
        ok(f"{arm}_fork_hash", sm["fork_hash"] == ps["fork_hash"])
        tags = [(e["tag"], e["actions"], e["layouts"], bool(e.get("endpoint")), e["attempts"], e["bank_attempts"]) for e in sm["evals"]]
        ok(f"{arm}_eval_schedule", tags == [("final_251904", 251904, "eval", True, 4, 4), ("final_501760", 501760, "eval", True, 4, 4)])
        for e in sm["evals"]:
            n, bk = A.read_attempts(br / f"attempts_{e['tag']}.jsonl")
            ok(f"{arm}_{e['tag']}_panel", [n[i][0]["limit"] for i in sorted(n)] == lim["a3_final"]
               and all(len(v) == 4 for v in n.values()) and all(r["K"] == 3 for v in n.values() for r in v))
            ok(f"{arm}_{e['tag']}_bank", [bk[i][0]["bin"] for i in range(64)] == [x["bin"] for x in bank]
               and all(len(v) == 4 for v in bk.values()))
            try:
                A.endpoint_record(br, sm, e["tag"])
                ok(f"{arm}_{e['tag']}_recomputation", True)
            except AssertionError as err:
                ok(f"{arm}_{e['tag']}_recomputation ({err})", False)
        for at in (251904, 501760):
            st = torch.load(br / f"state_{at}.pt", map_location="cpu", weights_only=False)
            ok(f"{arm}_state_{at}_hash", PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(at)])
            need = {"actor", "critic", "opt_a", "opt_c", "torch_gen", "np_rng", "sampler_rng", "envs", "assisted", "counters", "pi0"}
            ok(f"{arm}_state_{at}_complete", need <= set(st["state"]) and st["meta"]["post_probe_actions"] == at)
        acts = sm.get("actions_this_job", sm["actions"])
        ok(f"{arm}_env_steps_equal_summary", A.env_steps(br) == sum(acts.values()))
        ok(f"{arm}_ledger_reading", sum(L.job_actions(br)[0].values()) == sum(sm["actions"].values()))
        mt = [json.loads(l) for l in (br / "metrics.jsonl").read_text().splitlines() if l.strip()]
        up = [r for r in mt if r.get("phase") == "branch"]
        ok(f"{arm}_update_record_schema", up and all(set(r) >= UPD_KEYS | {"update_kl_prefix", "update_kl_suffix",
                                                                            "actor_update_norm"} for r in up))
        ok(f"{arm}_training_counter", up[-1]["counters"]["env_actions"] == 51200 + 501760 and up[-1]["actions"] == 501760)
        fin = lambda x: x is not None and x == x and abs(x) < 1e9
        ok(f"{arm}_losses_finite", all(fin(r["pg_loss"]) and fin(r["v_loss"]) and fin(r["entropy"]) and fin(r["anchor_kl"])
                                       and fin(r["actor_update_norm"]) for r in up))
        if arm == "A":
            ok("A_no_penalty", all(r.get("anchor_penalty") is None for r in up))
        else:
            pen = [r["anchor_penalty"] for r in up]
            kl = [r["anchor_kl"] for r in up]
            if comp == "both":
                ok(f"{arm}_penalty_equals_base_times_kl", all(abs(p - base * k) <= 1e-6 * max(1e-12, base * k) for p, k in zip(pen, kl)))
            else:
                ok(f"{arm}_penalty_within_component_bounds", all(-1e-12 <= p <= base * k * (1 + 1e-6) for p, k in zip(pen, kl)))
        counts[f"{arm}_env_steps"] = A.env_steps(br)
    for d in [bc, pj] + [b / f"a3-K3-u4000-s{S}-{t}" for t in A3.ARMS.values()]:
        t = d / "telemetry.json"
        ok(f"telemetry_{d.name}", t.exists() and "timestamp" in json.loads(t.read_text()))
    res = {"batch": a.batch, "pass": not fail, "failed": fail, "checks": chk,
           "counts": counts}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=1))
    print(json.dumps({"pass": res["pass"], "failed": fail, "counts": res["counts"]}, indent=1))
    sys.exit(0 if not fail else 1)


if __name__ == "__main__":
    main()
