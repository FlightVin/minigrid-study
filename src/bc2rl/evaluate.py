"""Batched stochastic evaluation from normal starts and from fixed competence-bank snapshots.

Each attempt (item i, attempt j) has its own uniform stream rng([eval_seed, i, j]). Actions are
sampled by inverse CDF from the policy's categorical distribution with that stream. The same
eval_seed therefore gives every policy the same random numbers on the same attempt (common random
numbers for paired comparisons), independent of batch composition. Gradients are disabled.
Greedy action choice is available only as an explicitly secondary analysis.
"""
from math import comb

import numpy as np
import torch

from bc2rl import model as M
from bc2rl import task as T


def _sample(probs, u):
    c = np.cumsum(probs, axis=1)
    c[:, -1] = 1.0
    return (u[:, None] > c).sum(axis=1)


@torch.no_grad()
def run_attempts(actor, starts, attempts, eval_seed, device, batch=128, greedy=False, heartbeat=None, capture=False):
    """starts: list of ("layout", Layout) or ("snapshot", dict). Returns list of per-attempt dicts.
    capture=True stores the complete env snapshot at the first boundary crossing (original clock kept)."""
    actor.eval()
    jobs = [(i, j) for i in range(len(starts)) for j in range(attempts)]
    results = [None] * len(jobs)
    envs, slots = [], []          # active (env, job index, rng, record)
    nxt = 0
    actions = 0

    def launch(k):
        i, j = jobs[k]
        env = T.StageTask()
        kind, x = starts[i]
        obs, info = env.reset(options={kind: x})
        rec = {"item": i, "attempt": j, "start_kind": kind, "start_step": info["step_count"],
               "start_accessed": info["accessed"], "limit": env.layout.limit, "K": env.layout.K,
               "arrival": None}
        return [env, k, np.random.default_rng([eval_seed, i, j]), rec, obs]

    while nxt < len(jobs) or slots:
        while len(slots) < batch and nxt < len(jobs):
            slots.append(launch(nxt))
            nxt += 1
        obs = {k: np.stack([s[4][k] for s in slots]) for k in ("grid", "aux", "time")}
        logits = actor(*M.obs_to_torch(obs, device))
        probs = torch.softmax(logits.float(), -1).cpu().numpy().astype(np.float64)
        if greedy:
            acts = probs.argmax(1)
        else:
            acts = _sample(probs, np.array([s[2].random() for s in slots]))
        keep = []
        for s, a in zip(slots, acts):
            env, k, _, rec, _ = s
            o, r, term, _, info = env.step(int(a))
            actions += 1
            s[4] = o
            if info["crossed"]:
                rec["arrival"] = {"tau": info["tau"], "remaining": info["remaining"],
                                  "pos": [int(v) for v in env.agent_pos], "dir": int(env.agent_dir),
                                  "carrying": None if env.carrying is None else [env.carrying.type, env.carrying.color]}
                if capture:
                    rec["arrival"]["snapshot"] = env.snapshot()
            if term:
                rec.update(success=bool(info["success"]), accessed=bool(info["accessed"]), tau=info["tau"],
                           end_step=info["step_count"], actions=info["step_count"] - rec["start_step"],
                           timeout=bool(info["deadline"]))
                results[k] = rec
            else:
                keep.append(s)
        slots = keep
        if heartbeat is not None:
            heartbeat()
    return results, actions


def pass_estimators(n, z, k):
    """Unbiased per-task pass@k (coverage) and pass^k (reliability) estimates."""
    ck = 1 - (comb(n - z, k) / comb(n, k) if n - z >= k else 0.0)
    rk = comb(z, k) / comb(n, k) if z >= k else 0.0
    return ck, rk


def summarize(results, n_items, ks=(4,)):
    """Equal weight per item. Returns P1, q, Ck, Rk and attempt counts."""
    by_item = {}
    for r in results:
        by_item.setdefault(r["item"], []).append(r)
    p1, q, cov, rel = [], [], {k: [] for k in ks}, {k: [] for k in ks}
    for i in range(n_items):
        rs = by_item[i]
        n, z = len(rs), sum(r["success"] for r in rs)
        p1.append(z / n)
        q.append(sum(r["accessed"] and not r["start_accessed"] for r in rs) / n)
        for k in ks:
            if k <= n:
                c, rr = pass_estimators(n, z, k)
                cov[k].append(c)
                rel[k].append(rr)
    out = {"P1": float(np.mean(p1)), "q": float(np.mean(q)), "items": n_items, "attempts": len(results)}
    for k in ks:
        if cov[k]:
            out[f"C{k}"] = float(np.mean(cov[k]))
            out[f"R{k}"] = float(np.mean(rel[k]))
    arrived = [r for r in results if r["arrival"] is not None]
    out["n_arrivals"] = len(arrived)
    out["P_success_given_arrival"] = (float(np.mean([r["success"] for r in arrived])) if arrived else None)
    out["timeouts"] = int(sum(r["timeout"] for r in results))
    return out
