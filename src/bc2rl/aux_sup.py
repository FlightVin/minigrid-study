"""Auxiliary prefix supervision for PPO (owner instruction 2026-11-02c, sections 3-4; PROTOCOL_FREEZE Amendment 9).

Two sources share one loss and one schedule; ordinary PPO (arm A, "00") has no source and is unchanged.

  Corrections (arm C, "C7"): during each rollout, eligible transitions are normal-start transitions taken before the
      boundary (env.accessed false at the decision). They are counted in rollout order (step-major, then env index).
      Eligible transition number e (0-based, per rollout) is queried when e % stride == 0, while the rollout has fewer
      than QUOTA queries and the branch has fewer than CAP queries. stride = max(4, ceil(E_prev / QUOTA)), where
      E_prev is the previous rollout's eligible count (first rollout: 4), so at most every fourth eligible transition
      is queried. QUOTA = floor(CAP / 245) = 306 per rollout; CAP = 75,000 queried states per branch, enforced here.
      The query (bc2rl.corrective.query) reads the live environment before the learner's sampled action is executed;
      it never steps, resets or edits the environment. Labelled queries become examples (rollout row, uniform target
      over the label set). Failed queries (time_exceeded, unresolved) are recorded and never trained.
  DemoReplay (arm R, "R7"): the original prefix demonstrations: every K=3 bc_train row with stage 0 (the expert
      planner's recorded action as a one-hot target; 18,357 rows in conf-v1). For update t it samples, uniformly with
      replacement, exactly n_t rows, where n_t is the number of labelled examples arm C used in update t of the same
      seed (read from C's completed aux_schedule.json). R therefore matches C's example count per update, loss,
      coefficient, normalization and reuse schedule; it differs in the states (demonstration vs learner-visited) and
      in the label form (one recorded expert action vs every shortest first action).

Loss and reuse (both sources): within an update, each epoch draws a permutation of the update's n_t examples from the
source's own generator and splits it into as many nearly equal chunks (numpy array_split) as the epoch has PPO
minibatches; minibatch k adds coef * mean over its chunk of the cross-entropy H(target, pi_theta). Every example is
used once per epoch (4 times per update) and only in the update of its own rollout (no replay buffer). Empty chunks
add nothing. The PPO terms, behaviour actions, old log-probabilities, rewards, values and advantages are untouched.
"""
from collections import Counter
import json
from math import ceil
from pathlib import Path
import time

import numpy as np
import torch

from bc2rl import corrective as CR
from bc2rl import task as T

CAP = 75_000
UPDATES = 245                      # 501,760 / 2,048
QUOTA = CAP // UPDATES             # 306
MIN_STRIDE = 4


def cross_entropy(logits, target):
    return -(target * torch.log_softmax(logits, -1)).sum(-1).mean()


class _Base:
    collects = False

    def __init__(self, seed, coef, salt):
        self.coef = coef
        self.rng = np.random.default_rng([seed, salt])
        self.update_index = 0
        self.history = []                # per update: dict of counts

    def chunks(self, n, n_minibatches):
        return np.array_split(self.rng.permutation(n), n_minibatches) if n else [np.zeros(0, np.int64)] * n_minibatches

    def base_state(self):
        return {"rng": self.rng.bit_generator.state, "update_index": self.update_index, "history": list(self.history)}

    def base_load(self, st):
        self.rng.bit_generator.state = st["rng"]
        self.update_index = st["update_index"]
        self.history = list(st["history"])


class Corrections(_Base):
    collects = True

    def __init__(self, seed, coef, cap=CAP, quota=QUOTA):
        super().__init__(seed, coef, 61)
        assert 0 < cap <= CAP and 0 < quota, "the owner's hard cap is 75,000 queried states per branch"
        self.cap, self.quota = cap, quota
        self.total_queried = 0
        self.prev_eligible = None
        self.stats = CR.Stats()
        self.seen = {}                   # observation key -> (status, mask): conflict audit
        self.conflicts = 0
        self.failures = []               # first 200 failed queries: category, status, reason, snapshot
        self._reset_rollout()

    def _reset_rollout(self):
        self.eligible = 0
        self.items = []                  # (s, i, target)
        self.r = Counter()

    def begin_rollout(self):
        self._reset_rollout()
        self.stride = MIN_STRIDE if self.prev_eligible is None else max(MIN_STRIDE, ceil(self.prev_eligible / self.quota))

    def observe(self, s, i, env, obs, probs, action):
        """Called before the learner's action at rollout step s for env i (normal starts only)."""
        if env.accessed:
            return
        e = self.eligible
        self.eligible += 1
        if e % self.stride or self.r["queried"] >= self.quota or self.total_queried >= self.cap:
            return
        before = (env.step_count, tuple(env.agent_pos), env.agent_dir)
        t0 = time.perf_counter()
        q = CR.query(env)
        self.stats.seconds += time.perf_counter() - t0
        assert before == (env.step_count, tuple(env.agent_pos), env.agent_dir), "planner query changed the env"
        self.total_queried += 1
        self.r["queried"] += 1
        cat = CR.category(env)
        st = self.stats
        st.status[q["status"]] += 1
        st.categories[cat] += 1
        st.nodes += q["nodes"]
        key = CR.obs_key(obs)
        val = (q["status"], q["mask"])
        if key in self.seen and self.seen[key] != val:
            self.conflicts += 1
        self.seen.setdefault(key, val)
        if q["status"] != "labelled":
            st.failed_categories[cat] += 1
            st.reasons[q.get("reason", q["status"])] += 1
            self.r["failed"] += 1
            if len(self.failures) < 200:
                self.failures.append({"category": cat, "status": q["status"], "reason": q.get("reason"),
                                      "plan_len": q["plan_len"], "snapshot": env.snapshot()})
            return
        tgt = CR.mask_to_target(q["mask"])
        st.label_sizes[int(tgt.astype(bool).sum())] += 1
        self.r["labelled"] += 1
        self.r["exec_in_label"] += int((q["mask"] >> action) & 1)
        self.r["mass_milli"] += int(round(1000 * float(probs[tgt > 0].sum())))
        self.items.append((s, i, tgt))

    def batch(self, flat, n_envs, device):
        """Examples of the rollout just collected (rows of the flattened (S*N) buffer)."""
        assert self.total_queried <= self.cap
        rows = np.array([s * n_envs + i for s, i, _ in self.items], np.int64)
        n = len(rows)
        self.history.append({"update": self.update_index, "eligible": self.eligible, "stride": self.stride,
                             "queried": self.r["queried"], "labelled": n, "failed": self.r["failed"],
                             "exec_in_label": self.r["exec_in_label"], "mass_milli": self.r["mass_milli"]})
        self.prev_eligible = self.eligible
        self.update_index += 1
        if not n:
            return None
        idx = torch.as_tensor(rows)
        tgt = torch.as_tensor(np.stack([t for _, _, t in self.items]))
        return {"grid": flat["grid"][idx].to(device), "aux": flat["aux"][idx].to(device),
                "time": flat["time"][idx].to(device), "target": tgt.to(device), "n": n}

    def schedule(self):
        return [h["labelled"] for h in self.history]

    def state(self):
        return {**self.base_state(), "kind": "C7", "total_queried": self.total_queried,
                "prev_eligible": self.prev_eligible, "stats": self.stats.to_dict(),
                "seen": [[k, list(v)] for k, v in self.seen.items()], "conflicts": self.conflicts,
                "failures": self.failures}

    def load(self, st):
        assert st["kind"] == "C7"
        self.base_load(st)
        self.total_queried, self.prev_eligible = st["total_queried"], st["prev_eligible"]
        self.stats = CR.Stats.from_dict(st["stats"])
        self.seen = {k: tuple(v) for k, v in st["seen"]}
        self.conflicts, self.failures = st["conflicts"], list(st["failures"])

    def summary(self):
        h = self.history
        tot = lambda k: int(sum(x[k] for x in h))
        return {"queried_states": self.total_queried, "cap": self.cap, "quota_per_update": self.quota,
                "updates": len(h), "eligible_transitions": tot("eligible"), "labelled_examples": tot("labelled"),
                "failed_queries": tot("failed"), "example_uses": 4 * tot("labelled"),
                "executed_action_in_label_set": tot("exec_in_label") / max(1, tot("labelled")),
                "policy_mass_on_label_set": tot("mass_milli") / 1000 / max(1, tot("labelled")),
                "distinct_observations_queried": len(self.seen), "observation_conflicts": self.conflicts,
                "planner": self.stats.to_dict()}


class DemoReplay(_Base):
    def __init__(self, seed, coef, ds, schedule):
        super().__init__(seed, coef, 62)
        from bc2rl import bc as BC
        d, _ = BC.load_role(Path(ds), "bc_train")
        rows = np.nonzero((d["K"] == 3) & (d["stage"] == 0))[0]
        self.grid, self.aux_ = d["grid"][rows], d["aux"][rows].astype(np.int64)
        self.time_ = d["time"][rows][:, None].astype(np.float32)
        self.action = d["action"][rows].astype(np.int64)
        self.schedule_ = list(schedule)
        self.n_rows = len(rows)

    def begin_rollout(self):
        pass

    def batch(self, flat, n_envs, device):
        assert self.update_index < len(self.schedule_), "R has no matched C count for this update"
        n = int(self.schedule_[self.update_index])
        idx = self.rng.integers(0, self.n_rows, n)
        self.history.append({"update": self.update_index, "labelled": n})
        self.update_index += 1
        if not n:
            return None
        tgt = np.zeros((n, T.N_ACTIONS), np.float32)
        tgt[np.arange(n), self.action[idx]] = 1.0
        return {"grid": torch.as_tensor(self.grid[idx]).to(device), "aux": torch.as_tensor(self.aux_[idx]).to(device),
                "time": torch.as_tensor(self.time_[idx]).to(device), "target": torch.as_tensor(tgt).to(device), "n": n}

    def schedule(self):
        return [h["labelled"] for h in self.history]

    def state(self):
        return {**self.base_state(), "kind": "R7"}

    def load(self, st):
        assert st["kind"] == "R7"
        self.base_load(st)

    def summary(self):
        n = sum(h["labelled"] for h in self.history)
        return {"labelled_examples": n, "example_uses": 4 * n, "updates": len(self.history),
                "demo_rows": self.n_rows, "matched_to_C": self.schedule() == self.schedule_[:len(self.history)]}


def load_c_schedule(path, updates=UPDATES):
    s = json.loads(Path(path).read_text())
    assert s["complete"] and len(s["labelled_per_update"]) == updates
    return s["labelled_per_update"]
