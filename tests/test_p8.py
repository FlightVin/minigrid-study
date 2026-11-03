"""Actor capability audit (owner instruction 2026-11-03; PROTOCOL_FREEZE Amendment 10). Few counted actions."""
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest
import torch

from bc2rl import capability as CP
from bc2rl import capfit as CF
from bc2rl import corrective as CR
from bc2rl import model as M
from bc2rl import task as T

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("MAE_PROJECT", ROOT)) / "data/r7-v1/layouts.json"   # runner jobs run from a code snapshot
pytestmark = pytest.mark.skipif(not DATA.exists(), reason="dataset r7-v1 not generated")


def _layouts(n=3):
    lay = json.loads(DATA.read_text())["rl_train"]
    return [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3][:n]


def _walk(L, steps, seed):
    env = T.StageTask()
    obs, _ = env.reset(options={"layout": L})
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(steps):
        if env.accessed:
            break
        out.append((obs, env.snapshot(), CR.query(env)))
        obs, _, term, _, _ = env.step(int(rng.integers(6)))
        if term:
            break
    return out


def test_snapshot_from_obs_rebuilds_planner_state():
    L = _layouts(1)[0]
    for obs, snap, q in _walk(L, 40, 0):
        rs = CP.snapshot_from_obs(obs["grid"], obs["aux"], obs["time"][0], L)
        env = CP.env_from(rs)
        o2 = env.gen_obs()
        assert np.array_equal(o2["grid"], obs["grid"]) and np.array_equal(o2["aux"], obs["aux"])
        assert np.allclose(o2["time"], obs["time"])
        q2 = CR.query(env)
        assert (q2["status"], q2["mask"]) == (q["status"], q["mask"])


def test_relaxed_lower_bound_never_exceeds_plan():
    for L in _layouts(2):
        for obs, snap, q in _walk(L, 30, 1):
            if q["status"] != "labelled":
                continue
            env = CP.env_from(snap)
            gl, _ = CP.goals(env)
            assert CP.relaxed_lb(env, gl) <= q["plan_len"]


def test_set_loss_floor_and_uniform():
    lg = torch.tensor([[10.0, -10, -10, -10, -10, -10, -10], [0.0] * 7])
    valid = CF.mask_bits(np.array([1, 0b11]))
    loss = CF.set_loss(lg, valid)
    assert loss[0] < 1e-3
    assert abs(float(loss[1]) - (-math.log(2 / 7))) < 1e-5


def test_capactor_128_matches_actor_keys():
    a, c = M.Actor(), CF.CapActor(128)
    c.load_state_dict(a.state_dict())
    g = torch.zeros(2, T.WIDTH, T.HEIGHT, 4, dtype=torch.uint8)
    x = torch.zeros(2, 3, dtype=torch.long)
    t = torch.ones(2, 1)
    assert torch.allclose(a(g, x, t), c(g, x, t))
    assert M.n_params(CF.CapActor(1024)) > 6 * M.n_params(a)


def test_expert_controller_crosses_from_normal_start():
    for L in _layouts(2):
        e, n = CP.expert_episode(L)
        assert e["crossed"] and e["stop"] is None and n == e["tau"]


def test_label_types():
    assert CP.label_types(0b000011) == {"turn"}
    assert CP.label_types(0b101000) == {"pickup", "toggle"}
