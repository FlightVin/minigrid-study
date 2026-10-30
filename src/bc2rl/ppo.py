"""Clipped PPO with GAE, separate actor/critic, optional demonstration-state starts and BC-reference KL.

Contract (project.md sections 6-7):
- gamma = 1, GAE lambda. The deadline is a true terminal: no bootstrap. A collection-batch boundary
  is not terminal: bootstrap with the critic on the next observation. GAE never crosses an episode
  boundary (normal or assisted reset).
- Advantage normalization over the rollout batch. No reward/value normalization or value clipping.
  Value targets are the completion returns only; the preservation penalty never enters them.
- Arm (a, b): a = demonstration-state starts with probability alpha at each reset; b = add
  lambda_kl * mean_s KL(pi0(.|s) || pi_theta(.|s)) on anchor states (128 per actor minibatch).
  The anchor KL is also computed without gradient in arms with b = 0, for diagnostics.
- Environment actions are counted exactly. A restored state does not count its skipped prefix.
"""
import json
import os
from pathlib import Path

import numpy as np
import torch

from bc2rl import data as D
from bc2rl import model as M
from bc2rl import task as T

ARMS = {"00": (False, False), "10": (True, False), "01": (False, True), "11": (True, True)}


class StartSampler:
    """Chooses each episode start. Normal: uniform rl_train layout of the condition's K.
    Assisted (prob alpha): bin by fixed mixture, then a reset-bank state uniformly within the bin."""

    def __init__(self, layouts, reset_bank, alpha, mixture, seed):
        self.layouts = layouts
        self.bank = reset_bank           # dict bin -> list of snapshot builders (callables)
        self.alpha = alpha
        self.mixture = mixture
        self.rng = np.random.default_rng(seed)

    def draw(self):
        if self.alpha > 0 and self.rng.random() < self.alpha:
            b = self.rng.choice(len(self.mixture), p=[m[1] for m in self.mixture])
            items = self.bank[self.mixture[b][0]]
            return "snapshot", items[self.rng.integers(len(items))](), True
        return "layout", self.layouts[self.rng.integers(len(self.layouts))], False


class ResetBank:
    """Builds snapshots on demand from donor trajectories and bin indices."""

    def __init__(self, ds, role, K, kind):
        self.d = np.load(ds / f"traj_{role}.npz")
        self.grid, self.aux, self.step = self.d["grid"], self.d["aux"], self.d["step_count"]
        self.traj = self.d["traj"]
        meta = json.loads((ds / "layouts.json").read_text())[role]
        self.meta = {it["traj_index"]: it for it in meta if "traj_index" in it}
        self.idx = np.load(ds / "banks_index.npz")
        self.kind, self.K = kind, K

    def rows(self, name):
        return self.idx[f"{self.kind}_K{self.K}_{name}"]

    def builder(self, r):
        def build():
            it = self.meta[int(self.traj[r])]
            return D.snapshot_from_record(T.Layout.from_dict(it["layout"]), self.grid[r], self.aux[r],
                                          int(self.step[r]), it["tau"])
        return build

    def bins(self, names):
        return {n: [self.builder(int(r)) for r in self.rows(n)] for n in names}


def categorical_kl(ref_logp, logp):
    """Exact KL(ref || current) over all actions, from log-softmax values."""
    return (ref_logp.exp() * (ref_logp - logp)).sum(-1)


class PPO:
    def __init__(self, actor, critic, cfg, device, sampler, anchors=None, use_kl=False, seed=0):
        self.actor, self.critic, self.cfg, self.device = actor, critic, cfg, device
        self.opt_a = torch.optim.Adam(actor.parameters(), lr=cfg["actor_lr"], eps=1e-5)
        self.opt_c = torch.optim.Adam(critic.parameters(), lr=cfg["critic_lr"], eps=1e-5)
        self.sampler = sampler
        self.anchors = anchors           # dict(grid, aux, time, ref_logp, stage_weights) on device
        self.use_kl = use_kl
        self.n_envs, self.n_steps = cfg["n_envs"], cfg["n_steps"]
        self.envs = [T.StageTask() for _ in range(self.n_envs)]
        self.obs = [None] * self.n_envs
        self.assisted = [False] * self.n_envs
        self.torch_gen = torch.Generator(device="cpu").manual_seed(seed)
        self.np_rng = np.random.default_rng([seed, 11])
        self.counters = {"env_actions": 0, "episodes": 0, "successes": 0, "assisted_episodes": 0,
                         "assisted_successes": 0, "normal_episodes": 0, "normal_successes": 0,
                         "normal_accessed": 0, "updates": 0, "actor_minibatches": 0, "timeouts": 0}
        for i in range(self.n_envs):
            self._reset(i)

    # -- environment management ------------------------------------------------------------------
    def _reset(self, i):
        kind, x, assisted = self.sampler.draw()
        self.obs[i], _ = self.envs[i].reset(options={kind: x})
        self.assisted[i] = assisted

    def _obs_batch(self, obs_list):
        b = {k: np.stack([o[k] for o in obs_list]) for k in ("grid", "aux", "time")}
        return M.obs_to_torch(b, self.device)

    # -- rollout ------------------------------------------------------------------------------------
    @torch.no_grad()
    def collect(self):
        N, S = self.n_envs, self.n_steps
        buf = {k: [] for k in ("grid", "aux", "time", "action", "logp", "value", "reward", "done", "stage", "assisted")}
        for _ in range(S):
            g, a, t = self._obs_batch(self.obs)
            logits = self.actor(g, a, t)
            value = self.critic(g, a, t)
            u = torch.rand(N, generator=self.torch_gen)
            probs = torch.softmax(logits.float(), -1).cpu()
            act = torch.searchsorted(probs.cumsum(-1).contiguous(), u[:, None]).squeeze(1).clamp(max=T.N_ACTIONS - 1)
            logp = torch.log_softmax(logits.float(), -1).cpu().gather(1, act[:, None]).squeeze(1)
            buf["grid"].append(g.cpu()); buf["aux"].append(a.cpu()); buf["time"].append(t.cpu())
            buf["action"].append(act); buf["logp"].append(logp); buf["value"].append(value.float().cpu())
            rew, done, stage, assisted = [], [], [], []
            for i, env in enumerate(self.envs):
                stage.append(env.stage())
                assisted.append(self.assisted[i])
                o, r, term, trunc, info = env.step(int(act[i]))
                assert not trunc
                self.counters["env_actions"] += 1
                rew.append(r)
                done.append(term)
                if term:
                    c = self.counters
                    c["episodes"] += 1
                    c["successes"] += int(info["success"])
                    c["timeouts"] += int(info["deadline"])
                    if self.assisted[i]:
                        c["assisted_episodes"] += 1
                        c["assisted_successes"] += int(info["success"])
                    else:
                        c["normal_episodes"] += 1
                        c["normal_successes"] += int(info["success"])
                        c["normal_accessed"] += int(info["accessed"])
                    self._reset(i)       # the next observation is the new episode's; GAE is cut by done
                else:
                    self.obs[i] = o
            buf["reward"].append(torch.tensor(rew)); buf["done"].append(torch.tensor(done, dtype=torch.bool))
            buf["stage"].append(torch.tensor(stage)); buf["assisted"].append(torch.tensor(assisted))
        g, a, t = self._obs_batch(self.obs)
        last_value = self.critic(g, a, t).float().cpu()
        data = {k: torch.stack(v) for k, v in buf.items()}            # (S, N, ...)
        adv = torch.zeros(S, N)
        gae = torch.zeros(N)
        for s in reversed(range(S)):
            next_v = last_value if s == S - 1 else data["value"][s + 1]
            nonterminal = (~data["done"][s]).float()
            delta = data["reward"][s] + self.cfg["gamma"] * next_v * nonterminal - data["value"][s]
            gae = delta + self.cfg["gamma"] * self.cfg["gae_lambda"] * nonterminal * gae
            adv[s] = gae
        data["adv"] = adv
        data["ret"] = adv + data["value"]
        return data

    # -- update -----------------------------------------------------------------------------------
    def _anchor_batch(self, n):
        A = self.anchors
        idx = torch.as_tensor(self.np_rng.choice(len(A["weights"]), size=n, p=A["weights"]), device=self.device)
        return A["grid"][idx], A["aux"][idx], A["time"][idx], A["ref_logp"][idx]

    def update(self, data):
        cfg = self.cfg
        flat = {k: v.reshape(-1, *v.shape[2:]) for k, v in data.items()}
        B = flat["action"].shape[0]
        adv = flat["adv"]
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        dev = lambda x: x.to(self.device)
        g, a, t = dev(flat["grid"]), dev(flat["aux"]), dev(flat["time"])
        act, old_logp, ret, adv = dev(flat["action"]), dev(flat["logp"]), dev(flat["ret"]), dev(adv)
        stats = {k: [] for k in ("pg_loss", "v_loss", "entropy", "approx_kl", "clipfrac", "anchor_kl",
                                 "grad_norm_actor", "grad_norm_critic", "kl_grad_norm", "ratio_max", "ratio_min")}
        for _ in range(cfg["epochs"]):
            perm = torch.randperm(B, generator=self.torch_gen).to(self.device)
            for mb in perm.split(cfg["minibatch"]):
                logits = self.actor(g[mb], a[mb], t[mb])
                logp_all = torch.log_softmax(logits, -1)
                logp = logp_all.gather(1, act[mb, None]).squeeze(1)
                ratio = (logp - old_logp[mb]).exp()
                pg = -torch.min(ratio * adv[mb], ratio.clamp(1 - cfg["clip"], 1 + cfg["clip"]) * adv[mb]).mean()
                ent = -(logp_all.exp() * logp_all).sum(-1).mean()
                loss = pg - cfg["ent_coef"] * ent
                ag, aa, at, ref = self._anchor_batch(cfg["anchor_batch"])
                if self.use_kl:
                    kl = categorical_kl(ref, torch.log_softmax(self.actor(ag, aa, at), -1)).mean()
                    loss = loss + cfg["kl_coef"] * kl
                else:
                    with torch.no_grad():
                        kl = categorical_kl(ref, torch.log_softmax(self.actor(ag, aa, at), -1)).mean()
                self.opt_a.zero_grad()
                loss.backward()
                gn = torch.nn.utils.clip_grad_norm_(self.actor.parameters(), cfg["max_grad_norm"])
                self.opt_a.step()
                v = self.critic(g[mb], a[mb], t[mb])
                v_loss = 0.5 * ((v - ret[mb]) ** 2).mean()
                self.opt_c.zero_grad()
                v_loss.backward()
                gc = torch.nn.utils.clip_grad_norm_(self.critic.parameters(), cfg["max_grad_norm"])
                self.opt_c.step()
                with torch.no_grad():
                    lr = logp - old_logp[mb]
                    stats["approx_kl"].append(((lr.exp() - 1) - lr).mean().item())
                    stats["clipfrac"].append(((ratio - 1).abs() > cfg["clip"]).float().mean().item())
                    stats["ratio_max"].append(ratio.max().item()); stats["ratio_min"].append(ratio.min().item())
                stats["pg_loss"].append(pg.item()); stats["v_loss"].append(v_loss.item())
                stats["entropy"].append(ent.item()); stats["anchor_kl"].append(kl.item())
                stats["grad_norm_actor"].append(gn.item()); stats["grad_norm_critic"].append(gc.item())
                self.counters["actor_minibatches"] += 1
        self.counters["updates"] += 1
        out = {k: float(np.mean(v)) for k, v in stats.items() if v}
        out["ratio_max"], out["ratio_min"] = max(stats["ratio_max"]), min(stats["ratio_min"])
        y, yhat = flat["ret"], flat["value"]
        var = y.var().item()
        out["explained_var"] = (1 - (y - yhat).var().item() / var) if var > 1e-12 else None
        out["batch_return_mean"] = flat["reward"].sum().item()
        out["frac_suffix_steps"] = (flat["stage"] > 0).float().mean().item()
        out["frac_assisted_steps"] = flat["assisted"].float().mean().item()
        return out

    # -- exact state for forks and resumption ------------------------------------------------------------
    def state(self):
        return {"actor": self.actor.state_dict(), "critic": self.critic.state_dict(),
                "opt_a": self.opt_a.state_dict(), "opt_c": self.opt_c.state_dict(),
                "torch_gen": self.torch_gen.get_state(), "np_rng": self.np_rng.bit_generator.state,
                "sampler_rng": self.sampler.rng.bit_generator.state,
                "envs": [e.snapshot() for e in self.envs], "assisted": list(self.assisted),
                "counters": dict(self.counters)}

    def load(self, st, load_sampler_rng=True):
        self.actor.load_state_dict(st["actor"]); self.critic.load_state_dict(st["critic"])
        self.opt_a.load_state_dict(st["opt_a"]); self.opt_c.load_state_dict(st["opt_c"])
        self.torch_gen.set_state(st["torch_gen"])
        self.np_rng.bit_generator.state = st["np_rng"]
        if load_sampler_rng:
            self.sampler.rng.bit_generator.state = st["sampler_rng"]
        for i, snap in enumerate(st["envs"]):
            self.obs[i], _ = self.envs[i].reset(options={"snapshot": snap})
        self.assisted = list(st["assisted"])
        self.counters = dict(st["counters"])


def state_hash(st):
    """Hash of the parts that must be identical at a fork."""
    import hashlib
    h = hashlib.sha256()
    for key in ("actor", "critic"):
        for k, v in st[key].items():
            h.update(k.encode()); h.update(v.detach().cpu().numpy().tobytes())
    for key in ("opt_a", "opt_c"):
        for sid, s in sorted(st[key]["state"].items()):
            for k in sorted(s):
                v = s[k]
                h.update(v.detach().cpu().numpy().tobytes() if torch.is_tensor(v) else str(v).encode())
    h.update(json.dumps(st["envs"], sort_keys=True, default=str).encode())
    h.update(json.dumps(st["counters"], sort_keys=True).encode())
    h.update(st["torch_gen"].numpy().tobytes())
    h.update(json.dumps(st["np_rng"], sort_keys=True, default=str).encode())
    return h.hexdigest()
