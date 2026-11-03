"""Corrective prefix imitation study (owner instruction 2026-11-02c, sections 4-5; Amendment 9): label planner, label
validity on constructed learner-error states, auxiliary loss sign and scale, gradient flow, schedule matching, cap
enforcement, read-only queries and planner-free evaluation. Self-contained layouts (no data files) except the
demonstration-replay test, which needs data/conf-v1 under MAE_PROJECT. Executes a few counted environment actions."""
import copy
import os
from pathlib import Path

import numpy as np
import pytest
import torch

from bc2rl import aux_sup as AS
from bc2rl import corrective as CR
from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import ppo as PP
from bc2rl import task as T

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("MAE_PROJECT", ROOT))
CFG = {"actor_lr": 3e-4, "critic_lr": 3e-4, "n_envs": 2, "n_steps": 32, "gamma": 1.0, "gae_lambda": 0.95,
       "epochs": 2, "minibatch": 16, "clip": 0.2, "ent_coef": 0.0, "max_grad_norm": 0.5, "anchor_batch": 8,
       "kl_coef": 0.0}


def layout(seed=1000):
    return P.plan_and_verify(T.generate_layout(3, seed), seed, 24, 80)[0]


def fresh(L):
    env = T.StageTask()
    env.reset(options={"layout": L})
    return env


def unlock(env, j):
    L = env.layout
    d = env.grid.get(T.DOOR_X[L.active_slots()[j]], L.door_rows[j])
    d.is_locked, d.is_open = False, True


def remove_key(env, j):
    env.grid.set(*env.layout.key_pos[j], None)


def place(env, cell, d=0):
    env.agent_pos, env.agent_dir = cell, d


def interior_free(env, j):
    x0 = T.SLOT_X0[env.layout.active_slots()[j]]
    ff = CR._front_free_cells(env.layout)
    return [(x, y) for x in range(x0, x0 + 3) for y in T.ROWS if env.grid.get(x, y) is None and (x, y) not in ff]


def follow(env, limit=60):
    """Execute the lowest label action until the frontier changes or the boundary is crossed."""
    j0, acts = CR.frontier(env), []
    for _ in range(limit):
        q = CR.query(env)
        assert q["status"] == "labelled", q
        a = min(b for b in range(6) if (q["mask"] >> b) & 1)
        acts.append(a)
        env.step(a)
        if env.accessed or CR.frontier(env) != j0:
            break
    return acts


def test_fresh_start_frontier_and_plan_reaches_first_door():
    env = fresh(layout())
    assert CR.frontier(env) == 0 and CR.category(env) == "in_module_empty"
    q = CR.query(env)
    acts = follow(env)
    assert CR.frontier(env) == 1
    # the unlock toggle changes the frontier one step before the door cell: plan length = actions + 1
    assert len(acts) + 1 == q["plan_len"] and acts[-1] == CR.TOGGLE


def test_wrong_key_possession_drops_then_fetches():
    env = fresh(layout())
    unlock(env, 0)
    remove_key(env, 0)
    env.carrying = T.Key("red")
    place(env, interior_free(env, 1)[0])
    assert CR.category(env) == "in_module_obsolete_key"
    acts = follow(env)
    assert CR.DROP in acts and CR.PICKUP in acts and acts.index(CR.DROP) < acts.index(CR.PICKUP)
    assert CR.frontier(env) == 2


def test_backtracking_returns_to_frontier_module():
    env = fresh(layout())
    unlock(env, 0)
    remove_key(env, 0)
    place(env, interior_free(env, 0)[0])
    assert CR.category(env).startswith("behind")
    follow(env)
    assert CR.frontier(env) == 2


def test_premature_key_loss_fetches_displaced_key():
    env = fresh(layout())
    unlock(env, 0)
    remove_key(env, 0)
    remove_key(env, 1)
    cell = interior_free(env, 0)[-1]
    env.grid.set(*cell, T.Key("blue"))                     # module 1's key carried back and dropped in module 0
    place(env, interior_free(env, 1)[0])
    assert CR.category(env).endswith("_key_displaced")
    follow(env, 80)
    assert CR.frontier(env) == 2


def test_all_unlocked_goal_is_the_crossing():
    env = fresh(layout())
    for j in range(3):
        unlock(env, j)
    assert CR.frontier(env) is None
    follow(env, 80)
    assert env.accessed


def test_time_exceeded_and_blocked_goal_give_no_label():
    L = layout()
    env = fresh(L)
    q = CR.query(env)
    env.step_count = L.limit - q["plan_len"] + 1
    assert CR.query(env)["status"] == "time_exceeded"
    env = fresh(L)
    for j in range(3):
        unlock(env, j)
    env.grid.set(T.SUFFIX_X0, T.GATEWAY[1], T.Ball("green"))
    r = CR.query(env)
    assert r["status"] == "unresolved" and r["mask"] == 0


def test_label_sets_are_exact_and_queries_read_only():
    L = layout(1001)
    env = fresh(L)
    rng = np.random.default_rng(0)
    n = 0
    while not env.accessed and env.step_count < L.limit and n < 60:
        before = env.snapshot()
        q = CR.query(env)
        assert env.snapshot() == before
        if q["status"] == "labelled":
            assert not CR.check_label(before, q)
            assert not (q["mask"] >> CR.DONE) & 1
            n += 1
        env.step(int(rng.choice(7, p=[.2, .2, .3, .1, .08, .1, .02])))
    assert n > 10


def _ppo(source, seed=0):
    layouts = [layout(1100 + s) for s in range(3)]
    torch.manual_seed(seed)
    sampler = PP.StartSampler(layouts, {}, 0.0, None, seed)
    anchors = {"grid": torch.zeros(8, T.WIDTH, T.HEIGHT, 4, dtype=torch.uint8), "aux": torch.zeros(8, 3, dtype=torch.int8),
               "time": torch.full((8, 1), 0.5), "ref_logp": torch.log_softmax(torch.zeros(8, 7), -1),
               "weights": np.full(8, 1 / 8)}
    learner = PP.PPO(M.Actor(), M.Critic(), CFG, torch.device("cpu"), sampler, anchors, seed=seed)
    learner.aux = source
    return learner


def test_aux_loss_sign_scale_gradient_and_intact_behaviour_records():
    a = _ppo(AS.Corrections(0, 0.1, cap=1000, quota=64))
    data = a.collect()
    b = copy.deepcopy(a)
    b.aux.coef = 0.0
    flat = {k: v.reshape(-1, *v.shape[2:]) for k, v in data.items()}
    ab = copy.deepcopy(a.aux).batch(flat, a.n_envs, a.device)
    assert ab is not None and ab["n"] > 0
    acts = data["action"].clone()
    sa, sb = a.update(data), b.update(copy.deepcopy(data))
    assert torch.equal(data["action"], acts)                       # behaviour actions untouched
    assert sa["aux_grad_norm"] > 0 and sa["aux_n"] == ab["n"] and np.isfinite(sa["aux_ce"])
    ce = lambda L: float(AS.cross_entropy(L.actor(ab["grid"], ab["aux"], ab["time"]), ab["target"]).detach())
    assert ce(a) < ce(b)                                           # the auxiliary term lowers the label loss
    assert any(not torch.equal(p, q) for p, q in zip(a.actor.parameters(), b.actor.parameters()))
    # every example is used once per epoch
    src = AS.Corrections(0, 0.1)
    parts = src.chunks(ab["n"], 4)
    assert len(parts) == 4 and sorted(np.concatenate(parts).tolist()) == list(range(ab["n"]))


def test_cap_quota_and_stride_are_enforced():
    a = _ppo(AS.Corrections(0, 0.1, cap=5, quota=3))
    for _ in range(3):
        a.update(a.collect())
    h = a.aux.history
    assert a.aux.total_queried <= 5 and all(x["queried"] <= 3 and x["stride"] >= 4 for x in h)
    assert sum(x["queried"] for x in h) == a.aux.total_queried
    with pytest.raises(AssertionError):
        AS.Corrections(0, 0.1, cap=75_001)


def test_corrections_state_round_trip():
    a = _ppo(AS.Corrections(0, 0.1, cap=1000, quota=64))
    a.update(a.collect())
    st = a.state()
    b = _ppo(AS.Corrections(0, 0.1, cap=1000, quota=64))
    b.load(st)
    assert b.aux.state() == a.aux.state()
    d1, d2 = a.collect(), b.collect()
    assert torch.equal(d1["action"], d2["action"])
    assert [(s, i) for s, i, _ in a.aux.items] == [(s, i) for s, i, _ in b.aux.items]
    assert all(np.array_equal(x, y) for (_, _, x), (_, _, y) in zip(a.aux.items, b.aux.items))


@pytest.mark.skipif(not (PROJECT / "data/conf-v1/traj_bc_train.npz").exists(), reason="needs data/conf-v1")
def test_demo_replay_matches_the_c_schedule():
    src = AS.DemoReplay(0, 0.1, PROJECT / "data/conf-v1", [3, 0, 5])
    assert src.n_rows == 18357
    out = [src.batch(None, 2, torch.device("cpu")) for _ in range(3)]
    assert out[0]["n"] == 3 and out[1] is None and out[2]["n"] == 5
    assert src.schedule() == [3, 0, 5] and src.summary()["matched_to_C"]
    assert torch.allclose(out[2]["target"].sum(1), torch.ones(5))
    with pytest.raises(AssertionError):
        src.batch(None, 2, torch.device("cpu"))


def test_evaluation_never_uses_the_planner(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("planner called during evaluation")
    monkeypatch.setattr(CR, "query", boom)
    actor = M.Actor()
    res, n = E.run_attempts(actor, [("layout", layout())], 1, 5, torch.device("cpu"))
    assert len(res) == 1 and n > 0
    src = (ROOT / "src/bc2rl/evaluate.py").read_text()
    assert "corrective" not in src and "aux_sup" not in src


def test_trace_classifies_key_drops_by_door_state():
    from bc2rl import trace as TR
    env = fresh(layout())
    remove_key(env, 0)
    env.carrying = T.Key("red")
    free = interior_free(env, 0)
    tr = TR.Tracker(env)
    for d in range(4):                                  # face an empty interior cell, then drop
        env.agent_dir = d
        if tuple(env.front_pos) in free:
            break
    tr.before(env, CR.DROP)
    env.step(CR.DROP)
    tr.after(env)
    assert tr.summary(env)["key_drops"] == {"premature": 1, "unlocked_unpassed": 0, "obsolete": 0}
