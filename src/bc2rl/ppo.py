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
- Anchor components (2026-11-01, component experiment): arms 01p / 01s keep only the prefix / suffix anchor
  rows of the same sampled batch in the penalty, divided by the full batch size (the original denominator), so
  the expected penalty is lambda * w_stage * E_stage KL with the original stage weight (0.25 prefix, 0.75 suffix).
  Arm 01 ("both") uses the original expression unchanged. All arms draw the same anchor batches from np_rng,
  which no other part of training uses, so the environment-action stream does not depend on the component.
- Environment actions are counted exactly. A restored state does not count its skipped prefix.
"""
import copy
import json
import os
from pathlib import Path

import numpy as np
import torch

from bc2rl import data as D
from bc2rl import model as M
from bc2rl import task as T

ARMS = {"00": (False, False), "10": (True, False), "01": (False, True), "11": (True, True),
        "01p": (False, True), "01s": (False, True), "01w": (False, True), "11s": (True, True)}
COMPONENT = {"01p": "prefix", "01s": "suffix", "11s": "suffix"}   # every other arm: "both" (the original loss)
# Arm 01w (anchor-allocation study A3, arm E): the original mixed penalty with base coefficient 0.75 x config
# (0.0075 for 0.01), i.e. 0.001875 E_prefix + 0.005625 E_suffix. Every other preservation arm uses the config value.
KL_SCALE = {"01w": 0.75}


def arm_kl_coef(arm, cfg):
    """Base coefficient passed to anchor_penalty for this arm (0 without preservation)."""
    return cfg["kl_coef"] * KL_SCALE.get(arm, 1.0) if ARMS[arm][1] else 0.0


def effective_coefficients(arm, cfg):
    """Expected-loss coefficients (prefix, suffix) on E_stage[KL] under the mixed anchor sampler."""
    w = cfg["anchor_prefix_weight"]
    b = arm_kl_coef(arm, cfg)
    comp = COMPONENT.get(arm, "both")
    return (b * w if comp in ("both", "prefix") else 0.0, b * (1 - w) if comp in ("both", "suffix") else 0.0)


class StartSampler:
    """Chooses each episode start. Normal: uniform rl_train layout of the condition's K.
    Assisted (prob alpha): bin by fixed mixture, then a reset-bank state uniformly within the bin.

    Three independent streams (coin, normal layout, bank state) make the k-th normal layout the
    same in every arm that forks from one state, whatever the assist coin does."""

    def __init__(self, layouts, reset_bank, alpha, mixture, seed):
        self.layouts = layouts
        self.bank = reset_bank           # dict bin -> list of snapshot builders (callables)
        self.alpha = alpha
        self.mixture = mixture
        base = [int(s) for s in np.atleast_1d(seed)]      # int or flat sequence of ints
        self.rngs = {k: np.random.default_rng(base + [i]) for i, k in enumerate(("coin", "layout", "bank"))}

    def draw(self):
        if self.alpha > 0 and self.rngs["coin"].random() < self.alpha:
            r = self.rngs["bank"]
            b = r.choice(len(self.mixture), p=[m[1] for m in self.mixture])
            items = self.bank[self.mixture[b][0]]
            return "snapshot", items[r.integers(len(items))](), True
        return "layout", self.layouts[self.rngs["layout"].integers(len(self.layouts))], False

    def get_state(self):
        return {k: r.bit_generator.state for k, r in self.rngs.items()}

    def set_state(self, st):
        for k, s in st.items():
            self.rngs[k].bit_generator.state = s


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


def gae(reward, value, done, last_value, gamma, lam):
    """(S, N) tensors. done[s] = episode ended at step s (success or deadline): no bootstrap and
    no advantage flow from s+1 (the next episode). The last step bootstraps from last_value."""
    S = reward.shape[0]
    adv = torch.zeros_like(reward)
    acc = torch.zeros_like(last_value)
    for s in reversed(range(S)):
        next_v = last_value if s == S - 1 else value[s + 1]
        nonterminal = (~done[s]).float()
        delta = reward[s] + gamma * next_v * nonterminal - value[s]
        acc = delta + gamma * lam * nonterminal * acc
        adv[s] = acc
    return adv


def categorical_kl(ref_logp, logp):
    """Exact KL(ref || current) over all actions, from log-softmax values."""
    return (ref_logp.exp() * (ref_logp - logp)).sum(-1)


def anchor_penalty(kl_rows, is_prefix, component, coef):
    """Preservation penalty on one sampled anchor batch. "both": coef * mean KL (the original loss, same
    operations). "prefix" / "suffix": the other stage's rows are zeroed and the sum is divided by the full batch
    size, so prefix + suffix = both and neither component is renormalized."""
    if component == "both":
        return coef * kl_rows.mean()
    keep = (is_prefix if component == "prefix" else ~is_prefix).to(kl_rows.dtype)
    return coef * (kl_rows * keep).sum() / kl_rows.shape[0]


class PPO:
    def __init__(self, actor, critic, cfg, device, sampler, anchors=None, use_kl=False, seed=0, component="both"):
        self.actor, self.critic, self.cfg, self.device = actor, critic, cfg, device
        self.opt_a = torch.optim.Adam(actor.parameters(), lr=cfg["actor_lr"], eps=1e-5)
        self.opt_c = torch.optim.Adam(critic.parameters(), lr=cfg["critic_lr"], eps=1e-5)
        self.sampler = sampler
        self.anchors = anchors           # dict(grid, aux, time, ref_logp, stage_weights) on device
        self.use_kl = use_kl
        assert component in ("both", "prefix", "suffix")
        self.component = component
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
        data["adv"] = gae(data["reward"], data["value"], data["done"], last_value,
                          self.cfg["gamma"], self.cfg["gae_lambda"])
        data["ret"] = data["adv"] + data["value"]
        return data

    # -- update -----------------------------------------------------------------------------------
    def _probe_rows(self, n=256):
        """Fixed anchor rows for update-size diagnostics: n evenly spaced prefix rows and n suffix rows."""
        if not self.anchors or "is_prefix" not in self.anchors or not self.cfg.get("update_diagnostics"):
            return None
        if getattr(self, "_probe_idx", None) is None:
            pre = torch.nonzero(self.anchors["is_prefix"]).squeeze(1).cpu().numpy()
            suf = torch.nonzero(~self.anchors["is_prefix"]).squeeze(1).cpu().numpy()
            pick = lambda r: r[np.linspace(0, len(r) - 1, min(n, len(r))).round().astype(int)]
            self._probe_idx = torch.as_tensor(np.concatenate([pick(pre), pick(suf)]), device=self.device)
        return self._probe_idx

    def _anchor_batch(self, n):
        A = self.anchors
        idx = torch.as_tensor(self.np_rng.choice(len(A["weights"]), size=n, p=A["weights"]), device=self.device)
        pre = A["is_prefix"][idx] if "is_prefix" in A else None
        return A["grid"][idx], A["aux"][idx], A["time"][idx], A["ref_logp"][idx], pre

    def update(self, data):
        cfg = self.cfg
        flat = {k: v.reshape(-1, *v.shape[2:]) for k, v in data.items()}
        B = flat["action"].shape[0]
        adv = flat["adv"]
        if cfg.get("adv_norm", True):
            adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        dev = lambda x: x.to(self.device)
        g, a, t = dev(flat["grid"]), dev(flat["aux"]), dev(flat["time"])
        act, old_logp, ret, adv = dev(flat["action"]), dev(flat["logp"]), dev(flat["ret"]), dev(adv)
        stats = {k: [] for k in ("pg_loss", "v_loss", "entropy", "approx_kl", "clipfrac", "anchor_kl",
                                 "anchor_kl_prefix", "anchor_kl_suffix", "anchor_penalty",
                                 "grad_norm_actor", "grad_norm_critic", "kl_grad_norm", "ratio_max", "ratio_min")}
        target_kl = cfg.get("target_kl")
        stopped = False
        probe_rows = self._probe_rows()
        if probe_rows is not None:      # policy change on fixed anchor states (no RNG, no gradient)
            before = [p.detach().clone() for p in self.actor.parameters()]
            with torch.no_grad():
                pg_, pa_, pt_ = (self.anchors[k][probe_rows] for k in ("grid", "aux", "time"))
                logp_before = torch.log_softmax(self.actor(pg_, pa_, pt_).float(), -1)
        for _ in range(cfg["epochs"]):
            if stopped:
                break
            perm = torch.randperm(B, generator=self.torch_gen).to(self.device)
            for mb in perm.split(cfg["minibatch"]):
                logits = self.actor(g[mb], a[mb], t[mb])
                logp_all = torch.log_softmax(logits, -1)
                logp = logp_all.gather(1, act[mb, None]).squeeze(1)
                ratio = (logp - old_logp[mb]).exp()
                pg = -torch.min(ratio * adv[mb], ratio.clamp(1 - cfg["clip"], 1 + cfg["clip"]) * adv[mb]).mean()
                ent = -(logp_all.exp() * logp_all).sum(-1).mean()
                loss = pg - cfg["ent_coef"] * ent
                ag, aa, at, ref, pre = self._anchor_batch(cfg["anchor_batch"])
                if self.use_kl:
                    kl_rows = categorical_kl(ref, torch.log_softmax(self.actor(ag, aa, at), -1))
                    kl = kl_rows.mean()
                    pen = anchor_penalty(kl_rows, pre, self.component, cfg["kl_coef"])
                    loss = loss + pen
                    stats["anchor_penalty"].append(pen.item())
                else:
                    with torch.no_grad():
                        kl_rows = categorical_kl(ref, torch.log_softmax(self.actor(ag, aa, at), -1))
                        kl = kl_rows.mean()
                if pre is not None:
                    with torch.no_grad():
                        for name, m in (("anchor_kl_prefix", pre), ("anchor_kl_suffix", ~pre)):
                            if m.any():
                                stats[name].append(kl_rows.detach()[m].mean().item())
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
                # Same rule in every arm: stop this update once the sampled-action KL is too large.
                if target_kl is not None and stats["approx_kl"][-1] > 1.5 * target_kl:
                    stopped = True
                    break
        self.counters["updates"] += 1
        out = {k: float(np.mean(v)) for k, v in stats.items() if v}
        if probe_rows is not None:
            with torch.no_grad():
                kl_upd = categorical_kl(logp_before, torch.log_softmax(self.actor(pg_, pa_, pt_).float(), -1))
                pre = self.anchors["is_prefix"][probe_rows]
                out["update_kl_prefix"] = kl_upd[pre].mean().item()
                out["update_kl_suffix"] = kl_upd[~pre].mean().item()
                out["actor_update_norm"] = float(sum(((p.detach() - b) ** 2).sum() for p, b in
                                                     zip(self.actor.parameters(), before)) ** 0.5)
        out["minibatches"] = len(stats["pg_loss"])
        out["ratio_max"], out["ratio_min"] = max(stats["ratio_max"]), min(stats["ratio_min"])
        y, yhat = flat["ret"], flat["value"]
        var = y.var().item()
        out["explained_var"] = (1 - (y - yhat).var().item() / var) if var > 1e-12 else None
        out["batch_successes"] = flat["reward"].sum().item()
        out["frac_suffix_steps"] = (flat["stage"] > 0).float().mean().item()
        out["frac_assisted_steps"] = flat["assisted"].float().mean().item()
        return out

    # -- exact state for forks and resumption ------------------------------------------------------------
    def state(self):
        # Deep copies: state_dict() and Optimizer.load_state_dict() alias live tensors, so a fork
        # held in memory would otherwise change when either learner trains.
        return copy.deepcopy({"actor": self.actor.state_dict(), "critic": self.critic.state_dict(),
                "opt_a": self.opt_a.state_dict(), "opt_c": self.opt_c.state_dict(),
                "torch_gen": self.torch_gen.get_state(), "np_rng": self.np_rng.bit_generator.state,
                "sampler_rng": self.sampler.get_state(),
                "envs": [e.snapshot() for e in self.envs], "assisted": list(self.assisted),
                "counters": dict(self.counters)})

    def load(self, st, load_sampler_rng=True):
        st = copy.deepcopy(st)
        self.actor.load_state_dict(st["actor"]); self.critic.load_state_dict(st["critic"])
        self.opt_a.load_state_dict(st["opt_a"]); self.opt_c.load_state_dict(st["opt_c"])
        self.torch_gen.set_state(st["torch_gen"])
        self.np_rng.bit_generator.state = st["np_rng"]
        if load_sampler_rng:
            self.sampler.set_state(st["sampler_rng"])
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
    h.update(json.dumps(st["sampler_rng"], sort_keys=True, default=str).encode())
    return h.hexdigest()
