"""M0 correctness tests: reward/time/boundary contract, route invariants, restore and replay."""
from collections import deque
import json

import numpy as np
import pytest

from bc2rl import planner as P
from bc2rl import task as T

SLACK, SUFFIX = 24, 80
LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE, DONE = range(7)


def planned(K, seed):
    layout, rec = P.plan_and_verify(T.generate_layout(K, seed), seed, SLACK, SUFFIX)
    return layout, rec


def obs_equal(a, b):
    return all(np.array_equal(a[k], b[k]) for k in ("grid", "aux", "time"))


def reachable(grid, start, passable_doors=False):
    """Cells reachable by walking, ignoring pickups; doors count as walls unless passable_doors."""
    seen, q = {start}, deque([start])
    while q:
        x, y = q.popleft()
        for dx, dy in P.DIRS:
            c = (x + dx, y + dy)
            v = grid.get(*c)
            ok = v is None or v.type == "floor" or (passable_doors and v.type == "door")
            if c not in seen and ok:
                seen.add(c)
                q.append(c)
    return seen


# --- layout and observation ---------------------------------------------------------------------

@pytest.mark.parametrize("K", [1, 2, 3])
def test_generation_is_deterministic_and_suffix_shared_across_K(K):
    a, b = T.generate_layout(K, 11), T.generate_layout(K, 11)
    assert a == b
    ref = T.generate_layout(1, 11)
    for f in ("gap_row", "target_pos", "distractor_pos", "delivery_pos"):
        assert getattr(a, f) == getattr(ref, f)
    assert a.door_rows[-1] == T.GATEWAY[1] and a.colors()[-1] == "yellow"


@pytest.mark.parametrize("K", [1, 3])
def test_observation_shape_and_time_scale_do_not_depend_on_K(K):
    layout, _ = planned(K, 3)
    env = T.StageTask()
    obs, info = env.reset(options={"layout": layout})
    assert obs["grid"].shape == (T.WIDTH, T.HEIGHT, 4) and obs["aux"].shape == (3,)
    assert obs["time"][0] == pytest.approx(layout.limit / T.H_NORM)
    assert layout.limit < T.H_NORM
    assert (obs["grid"][:, :, 3] > 0).sum() == 1 and obs["grid"][layout.agent_pos][3] == 1 + layout.agent_dir


# --- route invariants -----------------------------------------------------------------------------

@pytest.mark.parametrize("K,seed", [(k, s) for k in (1, 2, 3) for s in range(25)])
def test_no_alternate_routes(K, seed):
    layout = T.generate_layout(K, seed)
    g = T.build_grid(layout)
    start = tuple(layout.agent_pos)
    closed = reachable(g, start)
    first_slot = layout.active_slots()[0]
    x0 = T.SLOT_X0[first_slot]
    # With all doors closed, only the first module's room is reachable.
    assert all(x0 <= x <= x0 + 2 for x, _ in closed)
    assert tuple(layout.key_pos[0]) in {(x, y) for x in range(x0, x0 + 3) for y in T.ROWS}
    # Each later key lies only behind its preceding door.
    for j in range(1, K):
        s = layout.active_slots()[j]
        assert T.SLOT_X0[s] <= layout.key_pos[j][0] <= T.SLOT_X0[s] + 2
    # With every door open, the far region is reachable only through the inner-wall gap.
    open_all = reachable(g, start, passable_doors=True)
    assert (T.SUFFIX_X0, T.GATEWAY[1]) in open_all
    g.set(T.INNER_WALL_X, layout.gap_row, T.Wall())
    no_gap = reachable(g, start, passable_doors=True)
    assert not any(x > T.INNER_WALL_X for x, _ in no_gap)
    # The only suffix entry is the gateway door.
    assert [y for y in T.ROWS if g.get(T.DOOR_X[2], y).type == "door"] == [T.GATEWAY[1]]


@pytest.mark.parametrize("K,seed", [(k, s) for k in (1, 2, 3) for s in range(40)])
def test_planner_solves_within_limit(K, seed):
    layout, rec = planned(K, seed)
    assert rec["length"] <= layout.limit
    assert layout.limit == rec["tau"] + SLACK + SUFFIX


# --- reward, time and boundary contract ----------------------------------------------------------------

def run(env, actions):
    out = []
    for a in actions:
        out.append(env.step(a))
        if out[-1][2]:
            break
    return out


def test_random_rollouts_reward_contract():
    env = T.StageTask()
    rng = np.random.default_rng(0)
    for i in range(60):
        layout, _ = planned(1 + i % 3, 100 + i)
        env.reset(options={"layout": layout})
        steps = 0
        while True:
            _, r, term, trunc, info = env.step(int(rng.integers(7)))
            steps += 1
            assert not trunc and r in (0.0, 1.0)
            assert (r == 1.0) == info["success"]
            if info["success"]:
                assert info["accessed"] and info["tau"] < steps + 1
            if term:
                break
        assert info["success"] or (info["deadline"] and steps == layout.limit)


def test_success_requires_access_and_pickup_is_not_terminal():
    layout, rec = planned(3, 5)
    env = T.StageTask()
    env.reset(options={"layout": layout})
    acts = rec["actions"]
    picked = False
    for t, a in enumerate(acts, start=1):
        _, r, term, _, info = env.step(a)
        if env.carrying is not None and (env.carrying.type, env.carrying.color) == T.TARGET and not picked:
            picked = True
            assert r == 0 and not term, "target pickup must not be terminal"
        if t < rec["tau"]:
            assert not info["accessed"]
    assert picked and info["success"] and info["tau"] == rec["tau"]


def _walk_to_suffix(layout, rec):
    env = T.StageTask()
    env.reset(options={"layout": layout})
    for a in rec["actions"][:rec["tau"]]:
        env.step(a)
    return env


def test_only_first_crossing_counts():
    layout, rec = planned(1, 2)
    env = _walk_to_suffix(layout, rec)
    tau = env.tau
    assert env.accessed and tau == rec["tau"]
    # Turn around, go back through the gateway into the prefix, then re-enter.
    _, _, _, _, info = env.step(LEFT)
    env.step(LEFT)
    _, _, _, _, info = env.step(FORWARD)       # onto the door cell
    assert env.agent_pos[0] == T.GATEWAY[0]
    _, _, _, _, info = env.step(FORWARD)       # back into the last module room
    assert env.agent_pos[0] < T.GATEWAY[0] and info["accessed"] and info["tau"] == tau
    env.step(LEFT)
    env.step(LEFT)
    env.step(FORWARD)
    _, _, _, _, info = env.step(FORWARD)
    assert env.agent_pos[0] >= T.SUFFIX_X0 and not info["crossed"] and info["tau"] == tau


def test_wrong_objects_on_delivery_are_not_success():
    layout, rec = planned(1, 4)
    env = _walk_to_suffix(layout, rec)     # cross legitimately; teleport only inside the suffix
    for carried in (T.Key("yellow"), T.Ball("green"), None):
        env.carrying = carried
        env.agent_pos = tuple(layout.delivery_pos)
        env.agent_dir = 0
        env.succeeded = False
        _, r, term, _, info = env.step(DONE)
        assert r == 0 and not info["success"]


def test_drop_and_reacquire_target_then_deliver():
    layout, rec = planned(1, 9)
    env = T.StageTask()
    env.reset(options={"layout": layout})
    acts = rec["actions"]
    # Execute until the target is first carried.
    for i, a in enumerate(acts):
        env.step(a)
        if env.carrying is not None and (env.carrying.type, env.carrying.color) == T.TARGET:
            break
    rest = acts[i + 1:]
    # Drop it in front if possible (after turning toward a free cell), pick it up again.
    for turn in range(4):
        if env.grid.get(*env.front_pos) is None:
            break
        env.step(LEFT)
    else:
        pytest.skip("no free adjacent cell")
    _, r, term, _, _ = env.step(DROP)
    assert env.carrying is None and r == 0 and not term
    _, r, term, _, _ = env.step(PICKUP)
    assert (env.carrying.type, env.carrying.color) == T.TARGET and r == 0 and not term
    for _ in range(turn):
        env.step(RIGHT)
    for a in rest:
        _, r, term, _, info = env.step(a)
    assert r == 1.0 and term and info["success"]


def test_deadline_is_terminal_and_success_on_last_step_counts():
    layout, rec = planned(1, 6)
    tight = layout.with_limit(rec["length"])
    env = T.StageTask()
    env.reset(options={"layout": tight})
    for a in rec["actions"]:
        _, r, term, _, info = env.step(a)
    assert r == 1.0 and term and info["success"] and not info["deadline"] and info["remaining"] == 0
    env.reset(options={"layout": tight})
    for a in rec["actions"][:-1]:
        env.step(a)
    _, r, term, _, info = env.step(DONE)   # wasted last action
    assert r == 0 and term and info["deadline"] and not info["success"]
    with pytest.raises(AssertionError):
        env.step(DONE)


# --- snapshot and restore ---------------------------------------------------------------------------

def rollout_records(env, actions):
    recs = []
    for a in actions:
        obs, r, term, trunc, info = env.step(a)
        recs.append((obs, r, term, trunc, {k: info[k] for k in ("accessed", "tau", "success", "step_count", "remaining")}))
        if term:
            break
    return recs


def same(a, b):
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert obs_equal(x[0], y[0]) and x[1:] == y[1:]


@pytest.mark.parametrize("K,seed,kind", [(k, s, kind) for k in (1, 3) for s in range(6) for kind in ("planner", "random")])
def test_restore_reproduces_continuations(K, seed, kind):
    layout, rec = planned(K, seed)
    rng = np.random.default_rng(seed)
    if kind == "planner":
        actions = rec["actions"]
    else:
        actions = [int(a) for a in rng.integers(7, size=layout.limit)]
    env = T.StageTask()
    env.reset(options={"layout": layout})
    full = rollout_records(env, actions)
    cuts = sorted({1, len(full) // 3, len(full) // 2, rec["tau"] if kind == "planner" else 2, len(full) - 1})
    for cut in cuts:
        if not 0 < cut < len(full):
            continue
        env = T.StageTask()
        env.reset(options={"layout": layout})
        rollout_records(env, actions[:cut])
        snap = json.loads(json.dumps(env.snapshot()))           # through JSON, as stored on disk
        restored = T.StageTask()
        obs, info = restored.reset(options={"snapshot": snap})
        assert obs_equal(obs, full[cut - 1][0])
        assert info["remaining"] == layout.limit - cut
        same(rollout_records(restored, actions[cut:]), full[cut:])
        # Restoring and re-snapshotting gives the identical snapshot.
        again = T.StageTask()
        again.reset(options={"snapshot": snap})
        assert json.loads(json.dumps(again.snapshot())) == snap


def test_almost_expired_snapshot_gets_no_extra_time():
    layout, rec = planned(3, 1)
    env = T.StageTask()
    env.reset(options={"layout": layout})
    for _ in range(layout.limit - 1):
        env.step(DONE)
    snap = env.snapshot()
    restored = T.StageTask()
    obs, info = restored.reset(options={"snapshot": snap})
    assert info["remaining"] == 1 and obs["time"][0] == pytest.approx(1 / T.H_NORM)
    _, r, term, _, info = restored.step(FORWARD)
    assert term and info["deadline"] and r == 0
    expired = dict(snap, step_count=layout.limit)
    with pytest.raises(AssertionError):
        T.StageTask().reset(options={"snapshot": expired})


def test_snapshot_keeps_access_history_and_carrying():
    layout, rec = planned(1, 8)
    env = _walk_to_suffix(layout, rec)
    snap = env.snapshot()
    assert snap["accessed"] and snap["tau"] == rec["tau"] and snap["carrying"] is not None
    restored = T.StageTask()
    restored.reset(options={"snapshot": snap})
    assert restored.accessed and restored.tau == rec["tau"]
    assert (restored.carrying.type, restored.carrying.color) == ("key", "yellow")
    assert restored.stage() == 1


def test_suffix_plan_identical_across_K_for_shared_seed():
    a, ra = planned(1, 21)
    b, rb = planned(3, 21)
    assert ra["actions"][ra["tau"]:] == rb["actions"][rb["tau"]:]
    assert a.limit - ra["tau"] == b.limit - rb["tau"] == SLACK + SUFFIX


def test_dynamics_do_not_consume_env_rng():
    layout, rec = planned(3, 2)
    env = T.StageTask()
    env.reset(options={"layout": layout})
    state = env.np_random.bit_generator.state
    rng = np.random.default_rng(0)
    for a in rng.integers(7, size=layout.limit):
        if env.step(int(a))[2]:
            break
    assert env.np_random.bit_generator.state == state


def test_snapshot_from_record_matches_env_snapshot():
    from bc2rl import data as D
    layout, rec = planned(3, 12)
    env = T.StageTask()
    rows, pickup_t = D.record_trajectory(env, layout, rec["actions"])
    env.reset(options={"layout": layout})
    for t, a in enumerate(rec["actions"]):
        snap = env.snapshot()
        rebuilt = D.snapshot_from_record(layout, rows["grid"][t], rows["aux"][t], rows["step_count"][t], rec["tau"])
        snap["np_random"] = None
        assert json.loads(json.dumps(rebuilt)) == json.loads(json.dumps(snap))
        env.step(a)
    assert rows["event"].count(D.EVENT_CROSS) == 1 and rows["event"][-1] == D.EVENT_SUCCESS
    for b in D.BINS:
        t = D.competence_choice(rec["tau"], pickup_t, rec["length"], b, 12)
        assert rec["tau"] <= t < rec["length"] - 1 or b == "entry"
        assert {"entry": t == rec["tau"], "retrieval": rec["tau"] < t < pickup_t,
                "carrying": pickup_t <= t < rec["length"]}[b]


@pytest.mark.parametrize("K", [1, 3])
def test_restricted_suffix_search_loses_no_length(K):
    for s in range(150):
        lay = T.generate_layout(K, 5000 + s)
        a, ta = P.plan(lay, s, restrict_suffix=True)
        b, tb = P.plan(lay, s, restrict_suffix=False)
        # Same total length. Ties may drop the key before the boundary when unrestricted; the
        # restricted planner always carries the final key across (a fixed arrival convention).
        assert len(a) == len(b) and ta <= tb
        env = T.StageTask()
        lay2, _ = P.plan_and_verify(lay, s, 24, 80, env)
        env.reset(options={"layout": lay2})
        for act in a[:ta]:
            env.step(act)
        assert (env.carrying.type, env.carrying.color) == ("key", "yellow")


def test_suffix_plans_identical_across_K_for_many_seeds():
    for s in range(200):
        a, ta = P.plan(T.generate_layout(1, 7000 + s), 7000 + s)
        b, tb = P.plan(T.generate_layout(3, 7000 + s), 7000 + s)
        assert a[ta:] == b[tb:], s
