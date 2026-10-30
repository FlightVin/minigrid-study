"""Probe and branch jobs.

probe:  python -m bc2rl.rl probe  --config C --K 1 --bc-run DIR --bc-update U --seed S
        pi0 evaluation -> critic pre-fit on pi0 normal-start returns (held-out calibration) ->
        fixed ordinary-PPO probe -> post-probe evaluation -> hashed fork state.
branch: python -m bc2rl.rl branch --config C --probe-run DIR --arm 10
        load fork (verify hash) -> continuation with the arm's interventions -> evaluations.

Paths: --bc-run / --probe-run are relative to $MAE_PROJECT/.mae/runs. All evaluation uses the
same eval seeds for every policy (common random numbers). Every environment action is counted by
role: critic_warmup, probe/continuation training, and evaluation (diagnostic or final).
"""
import argparse
import copy
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
from bc2rl.telemetry import Heartbeat, resource_heartbeat

RESET_MIXTURE = [("entry", 0.5), ("retrieval", 0.25), ("carrying", 0.25)]


class Ctx:
    def __init__(self, cfg, K, seed):
        self.cfg, self.K, self.seed = cfg, K, seed
        self.project = Path(os.environ.get("MAE_PROJECT", "."))
        self.ds = self.project / "data" / cfg["dataset_id"]
        self.run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
        threads = int(os.environ.get("OMP_NUM_THREADS", "1"))
        torch.set_num_threads(threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:              # already set in this process (in-process tests only)
            assert torch.get_num_interop_threads() == 1
        self.device = torch.device(os.environ.get("MAE_DEVICE", "cpu"))
        lay = json.loads((self.ds / "layouts.json").read_text())
        pick = lambda role: [T.Layout.from_dict(it["layout"]) for it in lay[role] if it["layout"]["K"] == K]
        self.train_layouts = pick("rl_train")
        self.eval_layouts = pick(cfg["eval_role"])
        self.bank = json.loads((self.ds / f"bank_competence_{cfg['bank_role']}.json").read_text())[str(K)]
        self.metrics = (self.run_dir / "metrics.jsonl").open("a")
        self.actions = {"critic_warmup": 0, "train": 0, "eval_diagnostic": 0, "eval_final": 0}
        self.compute = {"actor_minibatches": 0, "critic_fit_steps": 0}
        self._last = time.time()

    def hb(self):
        if time.time() - self._last > 5:
            resource_heartbeat()
            self._last = time.time()

    def log(self, rec):
        self.metrics.write(json.dumps(rec) + "\n")
        self.metrics.flush()

    def anchors(self, pi0):
        bank = PP.ResetBank(self.ds, "anchor_donor", self.K, "anchor")
        pre, suf = bank.rows("prefix"), bank.rows("suffix")
        rows = np.concatenate([pre, suf])
        w = np.concatenate([np.full(len(pre), self.cfg["anchor_prefix_weight"] / len(pre)),
                            np.full(len(suf), (1 - self.cfg["anchor_prefix_weight"]) / len(suf))])
        dev = self.device
        A = {"grid": torch.as_tensor(bank.grid[rows], device=dev), "aux": torch.as_tensor(bank.aux[rows], device=dev),
             "time": torch.as_tensor(bank.d["time"][rows][:, None], device=dev), "weights": w / w.sum()}
        with torch.inference_mode():
            pi0.eval()
            A["ref_logp"] = torch.cat([torch.log_softmax(pi0(A["grid"][s:s + 1024], A["aux"][s:s + 1024],
                                                                A["time"][s:s + 1024]).float(), -1)
                                       for s in range(0, len(rows), 1024)]).clone()
        return A, {"prefix_states": int(len(pre)), "suffix_states": int(len(suf)),
                   "prefix_weight": self.cfg["anchor_prefix_weight"]}

    def sampler(self, alpha):
        bins = PP.ResetBank(self.ds, "reset_donor", self.K, "reset").bins([b for b, _ in RESET_MIXTURE]) if alpha > 0 else {}
        return PP.StartSampler(self.train_layouts, bins, alpha, RESET_MIXTURE, [self.seed, 31])

    def evaluate(self, actor, attempts, bank_attempts, role, tag):
        starts = [("layout", L) for L in self.eval_layouts]
        res, n1 = E.run_attempts(actor, starts, attempts, self.cfg["eval_seed"], self.device, heartbeat=self.hb)
        snaps = [("snapshot", s["snapshot"]) for s in self.bank]
        bres, n2 = E.run_attempts(actor, snaps, bank_attempts, self.cfg["eval_seed"] + 1, self.device, heartbeat=self.hb)
        self.actions[role] += n1 + n2
        out = {"tag": tag, "normal": E.summarize(res, len(starts)), "bank": E.summarize(bres, len(snaps)),
               "bank_bins": {b: float(np.mean([r["success"] for r in bres if self.bank[r["item"]]["bin"] == b]))
                             for b in ("entry", "retrieval", "carrying")},
               "eval_actions": n1 + n2}
        with (self.run_dir / f"attempts_{tag}.jsonl").open("w") as f:
            for r in res:
                f.write(json.dumps({"kind": "normal", **r}) + "\n")
            for r in bres:
                f.write(json.dumps({"kind": "bank", "bin": self.bank[r["item"]]["bin"], **r}) + "\n")
        return out


def critic_prefit(ctx, pi0, critic):
    """Fit the critic to pi0's actual normal-start returns (gamma = 1: 1 if the episode later succeeds).
    Episodes are split 80/20 for held-out calibration. Returns diagnostics."""
    cfg = ctx.cfg
    sampler = ctx.sampler(0.0)
    rng = np.random.default_rng([ctx.seed, 41])
    obs_all, ret_all, ep_all, stage_all, rem_all = [], [], [], [], []
    envs = [T.StageTask() for _ in range(cfg["n_envs"])]
    cur = [[] for _ in envs]
    obs = []
    for e in envs:
        kind, x, _ = sampler.draw()
        obs.append(e.reset(options={kind: x})[0])
    n_ep, actions, active = 0, 0, [True] * len(envs)
    pi0.eval()
    while any(active):
        b = {k: np.stack([o[k] for o in obs]) for k in ("grid", "aux", "time")}
        with torch.inference_mode():
            probs = torch.softmax(pi0(*M.obs_to_torch(b, ctx.device)).float(), -1).cpu().numpy().astype(np.float64)
        acts = E._sample(probs, rng.random(len(envs)))
        for i, e in enumerate(envs):
            if not active[i]:
                continue
            cur[i].append(({k: obs[i][k] for k in obs[i]}, e.stage(), e.remaining()))
            o, r, term, _, info = e.step(int(acts[i]))
            actions += 1
            obs[i] = o
            if term:
                for ob, st, rem in cur[i]:
                    obs_all.append(ob); ret_all.append(r); ep_all.append(n_ep); stage_all.append(st); rem_all.append(rem)
                n_ep += 1
                cur[i] = []
                if actions >= cfg["critic_warmup_actions"]:
                    active[i] = False      # finish in-flight episodes, then stop
                else:
                    kind, x, _ = sampler.draw()
                    obs[i] = e.reset(options={kind: x})[0]
        ctx.hb()
    ctx.actions["critic_warmup"] += actions
    ep = np.array(ep_all)
    # Episode-level split: 60% fit, 20% early-stopping validation, 20% held-out calibration.
    u_ep = rng.random(n_ep)
    is_test, is_val = (u_ep < 0.2)[ep], ((u_ep >= 0.2) & (u_ep < 0.4))[ep]
    G = {k: torch.as_tensor(np.stack([o[k] for o in obs_all]), device=ctx.device) for k in ("grid", "aux", "time")}
    y = torch.as_tensor(np.array(ret_all, np.float32), device=ctx.device)
    tr, va, te = np.nonzero(~is_test & ~is_val)[0], np.nonzero(is_val)[0], np.nonzero(is_test)[0]

    def predict():
        with torch.inference_mode():
            return torch.cat([critic(G["grid"][s:s + 2048], G["aux"][s:s + 2048], G["time"][s:s + 2048])
                              for s in range(0, len(y), 2048)]).float().cpu().numpy()

    yy = y.cpu().numpy()
    opt = torch.optim.Adam(critic.parameters(), lr=cfg["critic_prefit_lr"])
    best = (float(np.mean((predict()[va] - yy[va]) ** 2)), 0, copy.deepcopy(critic.state_dict()))
    for step in range(1, cfg["critic_prefit_steps"] + 1):
        idx = torch.as_tensor(rng.choice(tr, 256), device=ctx.device)
        loss = ((critic(G["grid"][idx], G["aux"][idx], G["time"][idx]) - y[idx]) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(critic.parameters(), cfg["max_grad_norm"])
        opt.step()
        if step % 25 == 0:
            ctx.hb()
            v = float(np.mean((predict()[va] - yy[va]) ** 2))
            if v < best[0]:
                best = (v, step, copy.deepcopy(critic.state_dict()))
    critic.load_state_dict(best[2])
    ctx.compute["critic_fit_steps"] += cfg["critic_prefit_steps"]
    pred = predict()
    stage, rem = np.array(stage_all), np.array(rem_all)
    ep_return = {}
    for r, e in zip(ret_all, ep_all):
        ep_return[e] = r
    diag = {"episodes": n_ep, "actions": actions,
            "episode_success_rate": float(np.mean(list(ep_return.values()))) if ep_return else None,
            "state_mean_return": float(np.mean(ret_all)) if ret_all else None, "train_states": int(len(tr)), "val_states": int(len(va)),
            "test_states": int(len(te)), "best_step": best[1], "best_val_mse": best[0]}
    if len(te):
        base = float(yy[tr].mean())
        diag.update(test_mse=float(np.mean((pred[te] - yy[te]) ** 2)), test_mse_constant=float(np.mean((base - yy[te]) ** 2)))
        cal = {}
        for name, m in (("prefix", stage == 0), ("suffix_pre_pickup", stage == 1), ("carrying", stage == 2)):
            mm = m & is_test
            cal[name] = {"n": int(mm.sum()), "mean_pred": float(pred[mm].mean()) if mm.any() else None,
                         "mean_return": float(yy[mm].mean()) if mm.any() else None}
        for lo, hi in ((0, 40), (40, 80), (80, 200)):
            mm = (rem >= lo) & (rem < hi) & is_test
            cal[f"remaining_{lo}_{hi}"] = {"n": int(mm.sum()), "mean_pred": float(pred[mm].mean()) if mm.any() else None,
                                           "mean_return": float(yy[mm].mean()) if mm.any() else None}
        diag["calibration"] = cal
    return diag


def train_loop(ctx, learner, budget, tag, eval_every=None, eval_fn=None):
    start = learner.counters["env_actions"]
    t0 = time.time()
    while learner.counters["env_actions"] - start < budget:
        data = learner.collect()
        stats = learner.update(data)
        done = learner.counters["env_actions"] - start
        rec = {"phase": tag, "actions": done, "wall": time.time() - t0, **stats,
               "counters": dict(learner.counters)}
        ctx.log(rec)
        ctx.hb()
        if not all(np.isfinite(v) for v in stats.values() if isinstance(v, float)):
            raise FloatingPointError(f"non-finite PPO statistics: {stats}")
        if eval_every and eval_fn and done // eval_every != (done - learner.n_envs * learner.n_steps) // eval_every:
            eval_fn(done)
    ctx.actions["train"] += learner.counters["env_actions"] - start
    return time.time() - t0


def probe(a, cfg):
    ctx = Ctx(cfg, a.K, a.seed)
    bc_path = ctx.project / ".mae/runs" / a.bc_run / f"actor_u{a.bc_update}.pt"
    bc = torch.load(bc_path, map_location="cpu", weights_only=False)
    torch.manual_seed(a.seed * 1000 + 17)
    pi0 = M.Actor().to(ctx.device)
    pi0.load_state_dict(bc["actor"])
    for p in pi0.parameters():
        p.requires_grad_(False)
    actor = M.Actor().to(ctx.device)
    actor.load_state_dict(bc["actor"])
    critic = M.Critic().to(ctx.device)
    (ctx.run_dir / "config.resolved.json").write_text(json.dumps({**cfg, "mode": "probe", "K": a.K, "seed": a.seed,
        "bc_run": a.bc_run, "bc_update": a.bc_update, "bc_seed": bc["seed"], "device": str(ctx.device),
        "threads": torch.get_num_threads(), "actor_params": M.n_params(actor), "critic_params": M.n_params(critic)}, indent=1))
    t0 = time.time()
    with Heartbeat(interval=5):
        ev0 = ctx.evaluate(pi0, cfg["diag_attempts"], cfg["diag_bank_attempts"], "eval_diagnostic", "pi0")
        ctx.log({"phase": "eval", **ev0})
        cdiag = critic_prefit(ctx, pi0, critic)
        ctx.log({"phase": "critic_prefit", **cdiag})
        anchors, anchor_info = ctx.anchors(pi0)
        learner = PP.PPO(actor, critic, cfg, ctx.device, ctx.sampler(0.0), anchors, use_kl=False, seed=a.seed)
        probe_wall = train_loop(ctx, learner, cfg["probe_actions"], "probe")
        ev1 = ctx.evaluate(actor, cfg["diag_attempts"], cfg["diag_bank_attempts"], "eval_diagnostic", "probe")
        ctx.log({"phase": "eval", **ev1})
        st = learner.state()
        st["pi0"] = pi0.state_dict()
        fork_hash = PP.state_hash(st)
        tmp = ctx.run_dir / "fork.pt.tmp"
        torch.save(st, tmp)
        os.replace(tmp, ctx.run_dir / "fork.pt")
    ctx.compute["actor_minibatches"] += learner.counters["actor_minibatches"]
    summary = {"mode": "probe", "K": a.K, "seed": a.seed, "bc_update": a.bc_update, "fork_hash": fork_hash,
               "pi0": {"p": ev0["normal"]["P1"], "q": ev0["normal"]["q"], "c": ev0["bank"]["P1"], "bins": ev0["bank_bins"]},
               "probe": {"p": ev1["normal"]["P1"], "q": ev1["normal"]["q"], "c": ev1["bank"]["P1"], "bins": ev1["bank_bins"]},
               "delta_c": ev1["bank"]["P1"] - ev0["bank"]["P1"], "critic_prefit": cdiag, "anchors": anchor_info,
               "actions": ctx.actions, "compute": ctx.compute, "probe_wall_seconds": probe_wall,
               "wall_seconds": time.time() - t0, "counters": learner.counters}
    (ctx.run_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("pi0", "probe", "delta_c", "fork_hash")}), flush=True)


def branch(a, cfg):
    probe_dir = Path(os.environ.get("MAE_PROJECT", ".")) / ".mae/runs" / a.probe_run
    psum = json.loads((probe_dir / "summary.json").read_text())
    pcfg = json.loads((probe_dir / "config.resolved.json").read_text())
    K, seed = psum["K"], psum["seed"]
    ctx = Ctx(cfg, K, seed)
    st = torch.load(probe_dir / "fork.pt", map_location="cpu", weights_only=False)
    assert PP.state_hash(st) == psum["fork_hash"], "fork state does not match recorded hash"
    use_reset, use_kl = PP.ARMS[a.arm]
    pi0 = M.Actor().to(ctx.device)
    pi0.load_state_dict(st["pi0"])
    for p in pi0.parameters():
        p.requires_grad_(False)
    actor, critic = M.Actor().to(ctx.device), M.Critic().to(ctx.device)
    anchors, anchor_info = ctx.anchors(pi0)
    alpha = cfg["alpha"] if use_reset else 0.0
    learner = PP.PPO(actor, critic, {**cfg, "kl_coef": cfg["kl_coef"] if use_kl else 0.0}, ctx.device,
                     ctx.sampler(alpha), anchors, use_kl=use_kl, seed=seed)
    learner.load(st)
    loaded_hash = PP.state_hash({**learner.state(), "pi0": st["pi0"]})
    assert loaded_hash == psum["fork_hash"], "loaded learner state differs from fork"
    base_actions = learner.counters["env_actions"]
    (ctx.run_dir / "config.resolved.json").write_text(json.dumps({**cfg, "mode": "branch", "arm": a.arm,
        "alpha": alpha, "kl_coef": cfg["kl_coef"] if use_kl else 0.0, "probe_run": a.probe_run,
        "fork_hash": psum["fork_hash"], "K": K, "seed": seed, "bc_update": pcfg["bc_update"],
        "device": str(ctx.device)}, indent=1))
    curve = []
    t0 = time.time()
    with Heartbeat(interval=5):
        def eval_fn(done):
            ev = ctx.evaluate(learner.actor, cfg["curve_attempts"], cfg["curve_bank_attempts"], "eval_diagnostic", f"curve_{done}")
            curve.append({"actions": done, "p": ev["normal"]["P1"], "q": ev["normal"]["q"], "c": ev["bank"]["P1"]})
            ctx.log({"phase": "eval", **ev})
        wall = train_loop(ctx, learner, cfg["continuation_actions"], "branch", cfg.get("curve_every"), eval_fn)
        evf = ctx.evaluate(learner.actor, cfg["final_attempts"], cfg["final_bank_attempts"], "eval_final", "final")
        ctx.log({"phase": "eval", **evf})
        tmp = ctx.run_dir / "final.pt.tmp"
        torch.save({"actor": learner.actor.state_dict(), "critic": learner.critic.state_dict(),
                    "counters": learner.counters}, tmp)
        os.replace(tmp, ctx.run_dir / "final.pt")
    c = learner.counters
    summary = {"mode": "branch", "arm": a.arm, "K": K, "seed": seed, "bc_update": pcfg["bc_update"],
               "fork_hash": psum["fork_hash"], "final": {"P1": evf["normal"]["P1"], "q": evf["normal"]["q"],
               "C4": evf["normal"].get("C4"), "R4": evf["normal"].get("R4"), "c": evf["bank"]["P1"],
               "bins": evf["bank_bins"], "P_success_given_arrival": evf["normal"]["P_success_given_arrival"]},
               "curve": curve, "continuation_actions": c["env_actions"] - base_actions,
               "actions": ctx.actions, "counters": c, "anchors": anchor_info,
               "train_wall_seconds": wall, "wall_seconds": time.time() - t0}
    (ctx.run_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"arm": a.arm, "final": summary["final"]}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["probe", "branch"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--K", type=int)
    ap.add_argument("--bc-run")
    ap.add_argument("--bc-update", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--probe-run")
    ap.add_argument("--arm", choices=list(PP.ARMS))
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    (probe if a.mode == "probe" else branch)(a, cfg)


if __name__ == "__main__":
    main()
