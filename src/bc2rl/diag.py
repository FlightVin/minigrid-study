"""Development diagnostics on saved M3 policies (no training).

reeval:   python -m bc2rl.diag reeval --config C --branch BATCH/JOB --eval-seed S --tag T
          Re-evaluates a saved branch actor (final.pt) on dev_eval / dev_bank with the config's final
          allocation. With the original eval seed it tests evaluation repeatability (attempt by attempt);
          with a new seed it measures Monte Carlo variation for one fixed policy.
arrival:  python -m bc2rl.diag arrival --config C --probe BATCH/JOB --branches 00=B/J 01=B/J 10=B/J 11=B/J
          Builds first-crossing banks from normal starts on dev_eval for sources pi0, 00 and 11 (each
          32 layouts x 2 attempts; every crossing is kept, success is never consulted; the attempt stops
          at the crossing). Evaluates pi0, the post-probe actor and the four arms from every source bank,
          2 attempts per state, original clocks kept. Then a separately labelled condition,
          "clock_extended": the same states from sources 00 and 11 with remaining time set to 104 (the
          planner-bank entry value; the time input changes accordingly), for policies 00 and 11 only.
          This is a new task condition and is never merged with the original one.
crosspanel: python -m bc2rl.diag crosspanel --config C --branch BATCH/JOB
          Cross-panel study (owner instruction 2026-11-01, section 6). Loads the branch's saved complete state at
          cfg["policy_actions"] (hash checked against the file and the branch summary) and evaluates its actor
          on every role in cfg["panels"] (K of the branch only) with cfg["attempts"] attempts per layout and the
          study's own eval seed. New records only (attempts_crosspanel_<role>.jsonl); originals are untouched.
          C4/R4 only when attempts >= 4.
gradcheck: python -m bc2rl.diag gradcheck --config C --probe BATCH/JOB --branches 00=B/J 01=B/J
          No environment actions. On 16 anchor batches of 128 (the training anchor distribution), the
          anchor KL to pi0 and the norm of the gradient of lambda * KL for each saved actor.
"""
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import ppo as PP
from bc2rl import task as T
from bc2rl.rl import Ctx, run_path
from bc2rl.telemetry import Heartbeat

ENTRY_REMAINING = 104


def load_actor(state, device):
    a = M.Actor().to(device)
    a.load_state_dict(state)
    a.eval()
    return a


def collect_arrivals(actor, layouts, attempts, seed, device, hb):
    """First-crossing snapshots from normal starts. Attempt (i, j) uses rng([seed, i, j])."""
    jobs = [(i, j) for i in range(len(layouts)) for j in range(attempts)]
    slots, out, actions = [], [], 0
    for i, j in jobs:
        env = T.StageTask()
        obs, _ = env.reset(options={"layout": layouts[i]})
        slots.append([env, (i, j), np.random.default_rng([seed, i, j]), obs])
    while slots:
        obs = {k: np.stack([s[3][k] for s in slots]) for k in ("grid", "aux", "time")}
        with torch.no_grad():
            probs = torch.softmax(actor(*M.obs_to_torch(obs, device)).float(), -1).cpu().numpy().astype(np.float64)
        acts = E._sample(probs, np.array([s[2].random() for s in slots]))
        keep = []
        for s, a in zip(slots, acts):
            o, _, term, _, info = s[0].step(int(a))
            actions += 1
            s[3] = o
            if info["crossed"] and not term:      # a crossing on the deadline step leaves no time to restore
                out.append({"item": s[1][0], "attempt": s[1][1], "remaining": info["remaining"], "tau": info["tau"],
                            "snapshot": s[0].snapshot()})
            elif not term:
                keep.append(s)
        slots = keep
        hb()
    return out, actions, len(jobs)


def extend_clock(snap):
    s = json.loads(json.dumps(snap))
    s["step_count"] = s["layout"]["limit"] - ENTRY_REMAINING
    s["tau"] = s["step_count"]
    return s


def arrival(a, cfg):
    pdir = run_path(a.probe)
    psum = json.loads((pdir / "summary.json").read_text())
    ctx = Ctx(cfg, psum["K"], psum["seed"])
    fork = torch.load(pdir / "fork.pt", map_location="cpu", weights_only=False)
    assert PP.state_hash(fork) == psum["fork_hash"]
    pols = {"pi0": load_actor(fork["pi0"], ctx.device), "probe": load_actor(fork["actor"], ctx.device)}
    for spec in a.branches:
        arm, rel = spec.split("=")
        bdir = run_path(rel)
        bs = json.loads((bdir / "summary.json").read_text())
        assert bs["fork_hash"] == psum["fork_hash"] and bs["arm"] == arm
        pols[arm] = load_actor(torch.load(bdir / "final.pt", map_location="cpu", weights_only=False)["actor"], ctx.device)
    seed = cfg["arrival_seed"]
    res = {"K": psum["K"], "seed": psum["seed"], "bc_update": psum["bc_update"], "fork_hash": psum["fork_hash"],
           "sources": {}, "eval": {}, "clock_extended": {}}
    actions = {"collect": 0, "eval": 0, "eval_clock_extended": 0}
    t0 = time.time()
    with Heartbeat(interval=5):
        banks = {}
        for k, src in enumerate(("pi0", "00", "11")):
            layouts = ctx.eval_layouts[:cfg.get("arrival_layouts", len(ctx.eval_layouts))]   # all unless a test limits it
            states, n, tried = collect_arrivals(pols[src], layouts, 2, seed + k, ctx.device, ctx.hb)
            actions["collect"] += n
            banks[src] = states
            rem = [s["remaining"] for s in states]
            res["sources"][src] = {"attempts": tried, "crossings": len(states),
                                   "layouts_with_crossing": len({s["item"] for s in states}),
                                   "remaining_q10_50_90": [float(np.quantile(rem, x)) for x in (.1, .5, .9)] if rem else None}
        with (ctx.run_dir / "arrival_banks.jsonl").open("w") as f:
            for src, states in banks.items():
                for s in states:
                    f.write(json.dumps({"source": src, **s}) + "\n")
        for b, (src, states) in enumerate(banks.items()):
            if not states:
                continue
            starts = [("snapshot", s["snapshot"]) for s in states]
            for name, pol in pols.items():
                r, n = E.run_attempts(pol, starts, 2, seed + 100 + b, ctx.device, heartbeat=ctx.hb)
                actions["eval"] += n
                res["eval"][f"{src}|{name}"] = summarize_bank(r, states)
                write_attempts(ctx.run_dir / f"attempts_arrival_{src}_{name}.jsonl", r)
            if src in ("00", "11"):
                ext = [("snapshot", extend_clock(s["snapshot"])) for s in states]
                for name in ("00", "11"):
                    r, n = E.run_attempts(pols[name], ext, 2, seed + 100 + b, ctx.device, heartbeat=ctx.hb)
                    actions["eval_clock_extended"] += n
                    res["clock_extended"][f"{src}|{name}"] = summarize_bank(r, states)
                    write_attempts(ctx.run_dir / f"attempts_clockext_{src}_{name}.jsonl", r)
    res.update(actions=actions, total_actions=sum(actions.values()), wall_seconds=time.time() - t0)
    (ctx.run_dir / "summary.json").write_text(json.dumps({"mode": "diag_arrival", **res}, indent=1))
    print(json.dumps({k: res[k] for k in ("sources", "total_actions")}), flush=True)


def summarize_bank(r, states):
    """Equal weight per state; also split by original remaining time (< 80 vs >= 80)."""
    per = {}
    for x in r:
        per.setdefault(x["item"], []).append(x["success"])
    p = {i: float(np.mean(v)) for i, v in per.items()}
    lo = [p[i] for i, s in enumerate(states) if s["remaining"] < 80]
    hi = [p[i] for i, s in enumerate(states) if s["remaining"] >= 80]
    return {"P1": float(np.mean(list(p.values()))), "states": len(p), "attempts": len(r),
            "P1_rem_lt80": float(np.mean(lo)) if lo else None, "n_rem_lt80": len(lo),
            "P1_rem_ge80": float(np.mean(hi)) if hi else None, "n_rem_ge80": len(hi)}


def write_attempts(path, r):
    with open(path, "w") as f:
        for x in r:
            f.write(json.dumps(x) + "\n")


def reeval(a, cfg):
    bdir = run_path(a.branch)
    bs = json.loads((bdir / "summary.json").read_text())
    ctx = Ctx({**cfg, "eval_seed": a.eval_seed}, bs["K"], bs["seed"])
    actor = load_actor(torch.load(bdir / "final.pt", map_location="cpu", weights_only=False)["actor"], ctx.device)
    t0 = time.time()
    with Heartbeat(interval=5):
        ev = ctx.evaluate(actor, cfg["final_attempts"], cfg["final_bank_attempts"], "eval_diagnostic", a.tag)
    out = {"mode": "diag_reeval", "branch": str(bdir), "eval_seed": a.eval_seed, "P1": ev["normal"]["P1"],
           "q": ev["normal"]["q"], "c": ev["bank"]["P1"], "original_final": bs["final"], "actions": ctx.actions,
           "wall_seconds": time.time() - t0}
    if a.eval_seed == json.loads((bdir / "config.resolved.json").read_text())["eval_seed"]:
        old = (bdir / "attempts_final.jsonl").read_text().splitlines()
        new = (ctx.run_dir / f"attempts_{a.tag}.jsonl").read_text().splitlines()
        out["identical_attempts"] = sum(x == y for x, y in zip(old, new))
        out["compared_attempts"] = len(old)
    (ctx.run_dir / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in out if k != "original_final"}), flush=True)


def crosspanel(a, cfg):
    bdir = run_path(a.branch)
    bs = json.loads((bdir / "summary.json").read_text())
    n = cfg["policy_actions"]
    saved = torch.load(bdir / f"state_{n}.pt", map_location="cpu", weights_only=False)
    assert PP.state_hash(saved["state"]) == saved["hash"] == bs["state_hashes"][str(n)], "saved state hash mismatch"
    ctx = Ctx(cfg, bs["K"], bs["seed"])
    actor = load_actor(saved["state"]["actor"], ctx.device)
    lay = json.loads((ctx.ds / "layouts.json").read_text())
    ks = (4,) if cfg["attempts"] >= 4 else ()
    out = {"mode": "diag_crosspanel", "branch": str(bdir), "arm": bs["arm"], "K": bs["K"], "seed": bs["seed"],
           "bc_update": bs["bc_update"], "policy_actions": n, "state_hash": saved["hash"],
           "eval_seed": cfg["eval_seed"], "attempts": cfg["attempts"], "panels": {}}
    t0 = time.time()
    with Heartbeat(interval=5):
        for role in cfg["panels"]:
            L = [T.Layout.from_dict(it["layout"]) for it in lay[role] if it["layout"]["K"] == bs["K"]]
            res, m = E.run_attempts(actor, [("layout", x) for x in L], cfg["attempts"], cfg["eval_seed"], ctx.device,
                                    heartbeat=ctx.hb)
            ctx.actions["eval_diagnostic"] += m
            write_attempts(ctx.run_dir / f"attempts_crosspanel_{role}.jsonl", res)
            out["panels"][role] = {**E.summarize(res, len(L), ks=ks), "layouts": len(L), "actions": m}
    out.update(actions=ctx.actions, wall_seconds=time.time() - t0)
    (ctx.run_dir / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"arm": out["arm"], "seed": out["seed"], "actions": ctx.actions}), flush=True)


def gradcheck(a, cfg):
    pdir = run_path(a.probe)
    psum = json.loads((pdir / "summary.json").read_text())
    ctx = Ctx(cfg, psum["K"], psum["seed"])
    fork = torch.load(pdir / "fork.pt", map_location="cpu", weights_only=False)
    pi0 = load_actor(fork["pi0"], ctx.device)
    A, _ = ctx.anchors(pi0)
    rng = np.random.default_rng([psum["seed"], 77])
    batches = [torch.as_tensor(rng.choice(len(A["weights"]), size=cfg["anchor_batch"], p=A["weights"]), device=ctx.device)
               for _ in range(16)]
    lam = cfg["kl_coef"]
    out = {"mode": "diag_gradcheck", "K": psum["K"], "seed": psum["seed"], "bc_update": psum["bc_update"],
           "lambda": lam, "actions": {}, "policies": {}}
    pols = {"probe": fork["actor"]}
    for spec in a.branches:
        arm, rel = spec.split("=")
        pols[arm] = torch.load(run_path(rel) / "final.pt", map_location="cpu", weights_only=False)["actor"]
    for name, sd in pols.items():
        actor = M.Actor().to(ctx.device)
        actor.load_state_dict(sd)
        kls, norms = [], []
        for idx in batches:
            kl = PP.categorical_kl(A["ref_logp"][idx], torch.log_softmax(actor(A["grid"][idx], A["aux"][idx], A["time"][idx]), -1)).mean()
            actor.zero_grad()
            (lam * kl).backward()
            norms.append(float(torch.sqrt(sum((p.grad ** 2).sum() for p in actor.parameters() if p.grad is not None))))
            kls.append(kl.item())
        out["policies"][name] = {"anchor_kl": float(np.mean(kls)), "lambda_kl_grad_norm": float(np.mean(norms))}
    (ctx.run_dir / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["reeval", "arrival", "gradcheck", "crosspanel"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--branch")
    ap.add_argument("--probe")
    ap.add_argument("--branches", nargs="*", default=[])
    ap.add_argument("--eval-seed", type=int)
    ap.add_argument("--tag", default="reeval")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    {"reeval": reeval, "arrival": arrival, "gradcheck": gradcheck, "crosspanel": crosspanel}[a.mode](a, cfg)


if __name__ == "__main__":
    main()
