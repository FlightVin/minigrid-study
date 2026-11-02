"""A4 canary engineering checks (seed 70 batch; PROTOCOL_FREEZE Amendment 6). Reads no treatment outcome:
P1, q, r and bank success rates are never printed or compared.

Usage: .venv/bin/python tools/a4_canary_check.py BATCH_ID [--seed 70]  -> reports/a4/canary_check.json
Checks: BC (rho 0.2, one checkpoint 8000, actor saved); probe (fork saved, K3, bc_update 8000, a4_select
diagnostics 64 x 2, entry bank 128 x 2, arrival bank n x 2 for pi0 and post-probe); both branches (fork hash, arm
identity and effective coefficients, alpha 0, 1,001,472 executed actions, three endpoint evaluations with
512 + 256 + 2n rows on the a4_final panel, three saved states with matching hashes, no recovery.pt left, update
diagnostics present, no penalty for 00 and 0 < penalty <= 0.01 x mean anchor KL for 01s); step records = summary
actions for every job; measured cost per job versus the driver's conservative bound.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import run_program4 as D    # noqa: E402


def rows(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def steps(d):
    return sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--seed", type=int, default=70)
    a = ap.parse_args()
    import torch
    from bc2rl import ppo as PP
    b, s = ROOT / ".mae/runs" / a.batch, a.seed
    n_arr = len(json.loads(D.ARRIVAL.read_text())["states"])
    limits = [it["layout"]["limit"] for it in D._layouts()["a4_final"] if it["layout"]["K"] == 3]
    fails, rep = [], {"batch": a.batch, "seed": s, "arrival_states": n_arr, "jobs": {}}
    chk = lambda cond, msg: None if cond else fails.append(msg)
    bc = b / f"a4-bc-s{s}"
    cf = json.loads((bc / "config.resolved.json").read_text())
    chk((bc / "summary.json").exists() and (bc / "actor_u8000.pt").exists(), "BC outputs")
    chk((cf.get("prefix_prob"), cf["checkpoints"], cf["seed"]) == (0.2, [8000], s), "BC config")
    pr = b / f"a4-probe-K3-s{s}"
    ps = json.loads((pr / "summary.json").read_text())
    chk((pr / "fork.pt").exists() and (ps["K"], ps["bc_update"], ps["seed"]) == (3, 8000, s), "probe identity")
    for tag in ("pi0", "probe"):
        r = rows(pr / f"attempts_{tag}.jsonl")
        k = [x["kind"] for x in r]
        chk((k.count("normal"), k.count("bank"), k.count("bank_extra")) == (128, 256, 2 * n_arr), f"probe {tag} rows")
        chk("extra_c" in ps[tag] and "arrival" in ps[tag]["extra_c"], f"probe {tag} arrival summary")
    jobs = {"bc": bc, "probe": pr}
    for arm in ("00", "01s"):
        d = b / f"a4-K3-s{s}-{arm}"
        jobs[arm] = d
        sm = json.loads((d / "summary.json").read_text())
        chk(sm["fork_hash"] == ps["fork_hash"] and sm["continuation_actions"] == D.TARGET, f"{arm} fork/allowance")
        chk(sm["actions"]["train"] == D.TARGET, f"{arm} train actions {sm['actions']['train']}")
        eff = (0.0, 0.0) if arm == "00" else (0.0, 0.0075)
        chk(sm["arm"] == arm and sm["alpha"] == 0.0 and tuple(sm["kl_effective_prefix_suffix"]) == eff
            and sm["anchor_component"] == ("both" if arm == "00" else "suffix"), f"{arm} identity")
        chk([e["actions"] for e in sm["evals"]] == list(D.ENDPOINTS) and all(e["endpoint"] for e in sm["evals"]), f"{arm} evals")
        for at in D.ENDPOINTS:
            r = rows(d / f"attempts_final_{at}.jsonl")
            k = [x["kind"] for x in r]
            chk((k.count("normal"), k.count("bank"), k.count("bank_extra")) == (512, 256, 2 * n_arr), f"{arm} rows at {at}")
            lim = {x["item"]: x["limit"] for x in r if x["kind"] == "normal"}
            chk([lim[i] for i in range(256)] == limits, f"{arm} panel at {at}")
            st = torch.load(d / f"state_{at}.pt", map_location="cpu", weights_only=False)
            chk(PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(at)], f"{arm} state hash at {at}")
        chk(not (d / "recovery.pt").exists() and not (d / "paused.json").exists(), f"{arm} recovery/paused left")
        tr = [x for x in rows(d / "metrics.jsonl") if x.get("phase") == "branch"]
        chk(len(tr) == D.TARGET // 2048, f"{arm} update count {len(tr)}")
        chk(all(k in tr[-1] for k in ("update_kl_prefix", "update_kl_suffix", "actor_update_norm")), f"{arm} update diagnostics")
        pen = [x.get("anchor_penalty") for x in tr]
        if arm == "00":
            chk(all(p is None for p in pen), "00 applied a penalty")
        else:          # suffix rows only, full-batch denominator: 0 < penalty <= base x mean KL over all anchor rows
            chk(all(p is not None and 0 < p <= 0.01 * x["anchor_kl"] * (1 + 1e-6) for p, x in zip(pen, tr)), "01s penalty")
    for name, d in jobs.items():
        sm = json.loads((d / "summary.json").read_text())
        acts = sum(sm["actions"].values()) if isinstance(sm.get("actions"), dict) else None
        st = steps(d)
        jid = d.name
        rep["jobs"][name] = {"step_records": st, "summary_actions": acts, "conservative": D.cost(jid)[0],
                             "expected": D.cost(jid)[1]}
        if acts is not None:
            chk(st == acts, f"{name} step records {st} != summary {acts}")
        chk(st <= D.cost(jid)[0], f"{name} above conservative bound")
    rep.update(failures=fails, passed=not fails)
    out = ROOT / "reports/a4/canary_check.json"
    out.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
    sys.exit(0 if not fails else 1)


if __name__ == "__main__":
    main()
