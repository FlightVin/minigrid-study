"""Planner certification of suffix completion from an actual state (owner instruction 2026-11-02, section 3).

certify(snapshot) -> {"status": "feasible" | "impossible" | "unresolved", "lower_bound", "plan_length", "remaining",
                      "replay_actions", "replay_success"}

- feasible:   an exact search in the planner's suffix abstraction (gateway column and suffix only; the distractor
              and any other non-target object fixed; the target never dropped) finds a plan, and replaying that plan
              in the real environment from the snapshot (original clock, no refresh, no reward change) succeeds within
              the remaining time. The replay is executed and its actions are counted.
- impossible: a relaxed lower bound exceeds the remaining time. The relaxation ignores every object and door
              (all non-wall cells passable) and counts one drop if a non-target object is carried, the moves to a
              pose facing the target, one pickup, and the moves onto the delivery cell. Every real plan needs at
              least that many steps, so the bound proves impossibility.
- An arrival on the final step (no remaining time) is impossible without search.
- unresolved: neither holds (no abstraction plan within the remaining time, but the bound does not exclude one).
              A failed or too-long abstraction search is not proof of impossibility.
"""
from collections import deque

import numpy as np

from bc2rl import planner as P
from bc2rl import task as T


def _pose_bfs(free, start_poses):
    """Unit-cost shortest distances over poses (x, y, d) with turns and forward moves on `free` cells."""
    dist = {p: 0 for p in start_poses}
    q = deque(start_poses)
    while q:
        x, y, d = q.popleft()
        k = dist[(x, y, d)] + 1
        nbrs = [(x, y, (d - 1) % 4), (x, y, (d + 1) % 4)]
        fx, fy = x + P.DIRS[d][0], y + P.DIRS[d][1]
        if (fx, fy) in free:
            nbrs.append((fx, fy, d))
        for n in nbrs:
            if n not in dist:
                dist[n] = k
                q.append(n)
    return dist


def lower_bound(env):
    """Relaxed lower bound on the steps to success from the env's current state."""
    free = {(k % T.WIDTH, k // T.WIDTH) for k, v in enumerate(env.grid.grid) if v is None or v.type != "wall"}
    cur = (int(env.agent_pos[0]), int(env.agent_pos[1]), int(env.agent_dir))
    delivery = tuple(env.layout.delivery_pos)
    c = env.carrying
    d0 = _pose_bfs(free, [cur])
    if c is not None and (c.type, c.color) == T.TARGET:
        return min(d0.get((*delivery, d), np.inf) for d in range(4))
    tgt = None
    for k, v in enumerate(env.grid.grid):
        if v is not None and (v.type, v.color) == T.TARGET:
            tgt = (k % T.WIDTH, k // T.WIDTH)
    assert tgt is not None, "target neither carried nor on the grid"
    best = np.inf
    for d in range(4):
        px, py = tgt[0] - P.DIRS[d][0], tgt[1] - P.DIRS[d][1]
        p = (px, py, d)
        if (px, py) not in free or p not in d0:
            continue
        d1 = _pose_bfs(free, [p])
        to_del = min(d1.get((*delivery, e), np.inf) for e in range(4))
        best = min(best, d0[p] + 1 + to_del)
    return best + (1 if c is not None else 0)


def abstract_plan(env, seed=0):
    """Exact BFS in the suffix abstraction from the env's current state. Returns actions or None."""
    x, y, d = int(env.agent_pos[0]), int(env.agent_pos[1]), int(env.agent_dir)
    if x < T.GATEWAY[0]:
        return None
    passable, droppable, target = set(), set(), None
    for k, v in enumerate(env.grid.grid):
        c = (k % T.WIDTH, k // T.WIDTH)
        if c[0] < T.GATEWAY[0]:
            continue
        if v is None:
            passable.add(c)
            if c[0] >= T.SUFFIX_X0:
                droppable.add(c)
        elif v.type == "floor" or (v.type == "door" and v.is_open):
            passable.add(c)
        elif (v.type, v.color) == T.TARGET:
            target = c
            passable.add(c)
            droppable.add(c)
    carried = env.carrying
    delivery = tuple(env.layout.delivery_pos)
    rng = np.random.default_rng([seed, 1])
    if carried is not None and (carried.type, carried.color) == T.TARGET:
        start = (x, y, d, 0, (P.HELD,), True)
        mp, md = [False], [False]
    elif carried is not None:
        assert target is not None
        start = (x, y, d, 1, (target, P.HELD), True)
        mp, md = [True, False], [False, True]
    else:
        assert target is not None
        start = (x, y, d, P.HELD, (target,), True)
        mp, md = [True], [False]
    try:
        return P._bfs(start, passable, droppable, mp, md, None,
                      lambda st: (st[0], st[1]) == delivery and st[3] == 0, rng)
    except RuntimeError:
        return None


def certify(snapshot, seed=0):
    remaining = snapshot["layout"]["limit"] - snapshot["step_count"]
    if remaining <= 0:             # arrival on the final step: no action remains, so completion is impossible
        return {"remaining": int(remaining), "lower_bound": None, "plan_length": None, "replay_actions": 0,
                "replay_success": None, "status": "impossible", "reason": "no remaining time"}
    env = T.StageTask()
    env.reset(options={"snapshot": snapshot})
    remaining = env.remaining()
    lb = lower_bound(env)
    plan = abstract_plan(env, seed)
    out = {"remaining": int(remaining), "lower_bound": None if not np.isfinite(lb) else int(lb),
           "plan_length": None if plan is None else len(plan), "replay_actions": 0, "replay_success": None}
    if plan is not None and len(plan) <= remaining:
        info, n = None, 0
        for a in plan:
            _, r, term, _, info = env.step(a)
            n += 1
            if term:
                break
        out.update(replay_actions=n, replay_success=bool(info["success"]))
        assert info["success"] and n == len(plan), "abstraction plan failed in the real environment"
        out["status"] = "feasible"
    elif lb > remaining:
        out["status"] = "impossible"
    else:
        out["status"] = "unresolved"
    return out
