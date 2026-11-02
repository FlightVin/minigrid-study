"""Programme 2026-11-02 (PROTOCOL_FREEZE Amendment 7): module-entry reset banks, the shared withdrawal schedule,
suffix certification and the progress tracker. Uses r4-v1 (or dev-v2) planner data; no learned policy."""
import json
from pathlib import Path

import numpy as np
import pytest

from bc2rl import planner as P
from bc2rl import ppo as PP
from bc2rl import suffix_cert as SC
from bc2rl import task as T
from bc2rl import trace as TR

ROOT = Path(__file__).resolve().parents[1]
DS = next((ROOT / "data" / d for d in ("r4-v1", "dev-v2") if (ROOT / "data" / d / "traj_reset_donor.npz").exists()), None)
need = pytest.mark.skipif(DS is None, reason="needs planner data with reset donors")


@need
def test_module_entry_banks_are_valid_planner_states():
    rb = PP.ResetBank(DS, "reset_donor", 3, "reset")
    n_donors = sum(1 for it in rb.meta.values() if it["layout"]["K"] == 3)
    env = T.StageTask()
    for j in range(3):
        rows = rb.module_rows(j)
        assert len(rows) == n_donors
        slot = j                        # K = 3: modules occupy slots 0, 1, 2
        for r in rows[:64]:
            snap = rb.builder(int(r))()
            obs, info = env.reset(options={"snapshot": snap})
            assert np.array_equal(obs["grid"], rb.grid[r]) and np.array_equal(obs["aux"], rb.aux[r])
            assert abs(obs["time"][0] - rb.d["time"][r]) < 1e-6           # original clock
            assert T.SLOT_X0[slot] <= env.agent_pos[0] < T.SLOT_X0[slot] + 3 and not info["accessed"]
            doors = TR._door_states(env)
            assert doors == [True] * j + [False] * (3 - j)                  # earlier modules done, this one locked
            c = env.carrying
            assert c is None or c.color != T.MODULE_COLORS[slot]            # module key not given
            if j == 0:
                assert env.step_count == 0
            # the remaining planner plan from this state still succeeds within the original deadline
            it = rb.meta[int(rb.traj[r])]
            acts, _ = P.plan(T.Layout.from_dict(it["layout"]), it["planner_seed"])
            for a in acts[env.step_count:]:
                _, rew, term, _, info = env.step(a)
            assert info["success"]


def test_shared_withdrawal_schedule_and_streams():
    sched = [{"until": 100, "alpha": 0.25, "mixture": [["mod2", 1.0]]},
             {"until": 200, "alpha": 0.25, "mixture": [["mod1", 1.0]]},
             {"until": 300, "alpha": 0.25, "mixture": [["mod0", 1.0]]}]
    bank = {f"mod{j}": [lambda j=j: {"m": j}] for j in range(3)}
    s = PP.StartSampler(list(range(50)), bank, 0.25, None, [7, 31], schedule=sched)
    s0 = PP.StartSampler(list(range(50)), {}, 0.0, None, [7, 31])
    now = [0]
    s.clock = lambda: now[0]
    seen = {}
    normal, normal0 = [], []
    for t in range(0, 400):
        now[0] = t
        kind, x, tag = s.draw()
        if kind == "snapshot":
            seen.setdefault(tag, []).append(t)
            assert x["m"] == int(tag[3:])
        else:
            normal.append(x)
    for _ in range(len(normal)):
        normal0.append(s0.draw()[1])
    assert set(seen) == {"mod2", "mod1", "mod0"}
    assert max(seen["mod2"]) < 100 <= min(seen["mod1"]) and max(seen["mod1"]) < 200 <= min(seen["mod0"])
    assert max(seen["mod0"]) < 300                                         # no new assisted starts after 75%
    assert normal == normal0                                               # the normal-layout stream is arm-invariant
    frac = sum(len(v) for v in seen.values()) / 300
    assert 0.15 < frac < 0.35


@need
def test_certification_feasible_impossible_and_tracker():
    bank = json.loads((DS / "layouts.json").read_text())["reset_donor"]
    items = [it for it in bank if it["layout"]["K"] == 3][:20]
    env = T.StageTask()
    for it in items:
        L = T.Layout.from_dict(it["layout"])
        acts, tau = P.plan(L, it["planner_seed"])
        env.reset(options={"layout": L})
        tr = TR.Tracker(env)
        for k, a in enumerate(acts, start=1):
            tr.before(env, a)
            env.step(a)
            tr.after(env)
            if k == tau:
                snap = env.snapshot()
        sm = tr.summary(env)
        assert sm["wrong_key_pickups"] == sm["locked_toggles"] == sm["door_closes"] == sm["noop_actions"] == 0
        assert sm["doors_open_end"] == 3 and sm["stage_end"] == "carrying"
        c = SC.certify(snap)
        assert c["status"] == "feasible" and c["plan_length"] == len(acts) - tau and c["lower_bound"] <= c["plan_length"]
        short = {**snap, "step_count": L.limit - c["lower_bound"] + 1}
        assert SC.certify(short)["status"] == "impossible"
