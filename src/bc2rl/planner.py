"""Privileged, deterministic, seeded planner for StageTask layouts.

The task is solved as a fixed sequence of segments:
  module j (j = 0..K-1): holding key j-1 (or nothing) -> drop it, pick key j, unlock door j;
  suffix: holding the yellow key -> drop it, pick the target, stand on the delivery cell.
Each segment is solved by exact breadth-first search over (pose, carried object, positions of the
objects that can move in that segment, door state). A segment always ends in a forced pose (facing
the door just unlocked), so joining segment optima gives a shortest plan among plans that respect
this event order and do not move objects dropped in earlier segments. The planner never picks up
the distractor, drops the target, or closes doors; none of these can shorten a plan.

Shortest-path ties are broken by shuffling the action order at each expansion with a seeded RNG.
Every plan is verified by replay through StageTask (see `plan_and_verify`).
"""
from collections import deque

import numpy as np

from bc2rl import task as T

LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE, DONE = range(7)
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
HELD = -1


def _bfs(start, passable, droppable, mobile_pickable, mobile_droppable, door, goal, rng):
    """start = (x, y, d, carry, positions(tuple), door_open). Returns list of actions."""
    parent = {start: None}
    q = deque([start])
    order = [LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE]
    while q:
        s = q.popleft()
        if goal(s):
            path = []
            while parent[s] is not None:
                s, a = parent[s]
                path.append(a)
            return path[::-1]
        x, y, d, carry, pos, open_ = s
        fx, fy = x + DIRS[d][0], y + DIRS[d][1]
        f = (fx, fy)
        occupied = {p: i for i, p in enumerate(pos) if p != HELD}
        rng.shuffle(order)
        for a in order:
            n = None
            if a == LEFT:
                n = (x, y, (d - 1) % 4, carry, pos, open_)
            elif a == RIGHT:
                n = (x, y, (d + 1) % 4, carry, pos, open_)
            elif a == FORWARD:
                if f not in occupied and (f in passable or (door is not None and f == door[0] and open_)):
                    n = (fx, fy, d, carry, pos, open_)
            elif a == PICKUP:
                if carry == HELD and f in occupied and mobile_pickable[occupied[f]]:
                    i = occupied[f]
                    n = (x, y, d, i, pos[:i] + (HELD,) + pos[i + 1:], open_)
            elif a == DROP:
                if carry != HELD and mobile_droppable[carry] and f in droppable and f not in occupied:
                    n = (x, y, d, HELD, pos[:carry] + (f,) + pos[carry + 1:], open_)
            elif a == TOGGLE:
                if door is not None and not open_ and f == door[0] and carry == door[1]:
                    n = (x, y, d, carry, pos, True)
            if n is not None and n not in parent:
                parent[n] = (s, a)
                q.append(n)
    raise RuntimeError("planner: segment unsolvable")


def _static(layout, dropped):
    """Passable and droppable cell sets before any door opens, given objects fixed in place."""
    g = T.build_grid(layout)
    passable, droppable = set(), set()
    fixed = set(dropped) | {tuple(layout.distractor_pos)}
    for k, v in enumerate(g.grid):
        c = (k % T.WIDTH, k // T.WIDTH)
        if v is None or v.type in ("key", "ball"):
            if c not in fixed:
                passable.add(c)
                droppable.add(c)
        elif v.type == "floor":
            passable.add(c)
    return passable, droppable


def plan(layout, seed):
    """Return (actions, tau_index) where tau_index is the action count at first boundary crossing."""
    rng = np.random.default_rng(seed)
    actions = []
    x, y = layout.agent_pos
    d = layout.agent_dir
    dropped = []                 # positions of keys left behind in earlier segments
    opened = set()               # door cells already unlocked
    held_prev = False
    slots = layout.active_slots()
    for j, s in enumerate(slots):
        passable, droppable = _static(layout, dropped)
        passable |= opened
        droppable -= opened
        door = (T.DOOR_X[s], layout.door_rows[j])
        # mobile objects: 0 = key j, 1 = previous key (held at start, if any)
        pos = (tuple(layout.key_pos[j]),) + ((HELD,) if held_prev else ())
        carry = 1 if held_prev else HELD
        start = (x, y, d, carry, pos, False)
        n_mobile = len(pos)
        path = _bfs(start, passable, droppable, [True] * n_mobile, [True] * n_mobile,
                    (door, 0), lambda st: st[5], rng)
        x, y, d, carry, pos, _ = _replay_abstract(start, path, passable, droppable, door)
        assert carry == 0
        if held_prev:
            dropped.append(pos[1])
        opened.add(door)
        held_prev = True
        actions += path
    passable, droppable = _static(layout, dropped)
    passable |= opened
    droppable -= opened
    # mobile: 0 = target, 1 = yellow key (held)
    start = (x, y, d, 1, (tuple(layout.target_pos), HELD), True)
    delivery = tuple(layout.delivery_pos)
    path = _bfs(start, passable, droppable, [True, False], [False, True], None,
                lambda st: (st[0], st[1]) == delivery and st[3] == 0, rng)
    actions += path
    tau = _first_crossing(layout, actions)
    return actions, tau


def _replay_abstract(start, path, passable, droppable, door):
    x, y, d, carry, pos, open_ = start
    for a in path:
        f = (x + DIRS[d][0], y + DIRS[d][1])
        if a == LEFT:
            d = (d - 1) % 4
        elif a == RIGHT:
            d = (d + 1) % 4
        elif a == FORWARD:
            x, y = f
        elif a == PICKUP:
            i = pos.index(f)
            carry, pos = i, pos[:i] + (HELD,) + pos[i + 1:]
        elif a == DROP:
            pos, carry = pos[:carry] + (f,) + pos[carry + 1:], HELD
        elif a == TOGGLE:
            open_ = True
    return x, y, d, carry, pos, open_


def _first_crossing(layout, actions):
    x, y = layout.agent_pos
    d = layout.agent_dir
    # Only forward moves change position; a planner forward move is always legal.
    for t, a in enumerate(actions, start=1):
        if a == LEFT:
            d = (d - 1) % 4
        elif a == RIGHT:
            d = (d + 1) % 4
        elif a == FORWARD:
            x, y = x + DIRS[d][0], y + DIRS[d][1]
            if x >= T.SUFFIX_X0:
                return t
    raise RuntimeError("plan never crosses the boundary")


def time_limit(tau, prefix_slack, suffix_allowance):
    return tau + prefix_slack + suffix_allowance


def plan_and_verify(layout, seed, prefix_slack, suffix_allowance, env=None):
    """Plan, set H_x, and replay through the real environment. Returns (layout_with_limit, record)."""
    actions, tau = plan(layout, seed)
    limit = time_limit(tau, prefix_slack, suffix_allowance)
    if len(actions) > limit:
        raise RuntimeError(f"insufficient time: plan {len(actions)} > limit {limit}")
    planned = layout.with_limit(limit)
    env = env or T.StageTask()
    env.reset(options={"layout": planned})
    info = None
    for t, a in enumerate(actions, start=1):
        _, r, term, trunc, info = env.step(a)
        assert not trunc
        if t < len(actions):
            assert r == 0 and not term, f"early termination at {t}"
        if t == tau:
            assert info["crossed"] and info["tau"] == tau
    assert r == 1.0 and term and info["success"] and info["accessed"] and info["tau"] == tau
    return planned, {"actions": actions, "tau": tau, "length": len(actions),
                     "suffix_length": len(actions) - tau, "planner_seed": int(seed)}
