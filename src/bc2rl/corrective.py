"""Corrective prefix labels for learner-visited states (owner instruction 2026-11-02c, section 4; PROTOCOL_FREEZE
Amendment 9). Privileged planner; it never acts in the environment and draws no random numbers.

query(env) labels the current state of a live StageTask (before the learner's action is executed) with the set of
first actions of every shortest plan that completes the current unfinished prefix module. Frozen rules:

Current unfinished module (frontier). j* = the lowest-index active module whose door is locked. The goal is to stand
on door j*'s cell (only possible once it is unlocked and open). If no door is locked, the goal is the boundary
crossing: stand on (13, 4). Both are functions of the observable grid. The learner's history is never used.

Recovery and handoff are implicit in the plan, because the search starts from the actual state:
  - backtracking (the agent is in an earlier module or on an earlier door cell): the plan walks back to module j*,
    toggling closed (unlocked) doors open on the way;
  - wrong-key possession (carrying any object other than j*'s key while door j* is locked): the plan drops it on an
    allowed cell and then fetches j*'s key; if no door is locked, carrying anything is allowed;
  - premature key loss (j*'s key lies anywhere in the reachable prefix, not held): the plan fetches it there;
  - handoff between key acquisition and door passage is not a separate rule: one search covers drop, pickup,
    unlock (toggle while holding j*'s key and facing the locked door) and the step onto the door cell.

Abstraction (fixed; exact search inside it). Region: every non-wall cell with x <= DOOR_X of module j* (all of the
prefix to the gateway for the crossing goal, plus (13, 4)). Mobile objects: j*'s key (pickable; never dropped once
held) and the object carried at the query (droppable; never picked up again). Drops are allowed on empty interior
cells of modules 0..j* except the cells directly in front of any door (the cells layout generation keeps free).
Every other object is a fixed obstacle. Doors: the locked door j* opens by toggle while holding its key; earlier
doors that are closed (unlocked) open by toggle; the planner never closes a door. Plans that move other objects,
re-pick a dropped object or close doors are excluded; none can be needed to complete the module, but they could in
rare layouts shorten it, so labels are shortest within this abstraction.

Ties. A layered breadth-first search propagates, for every state, the set of first actions that reach it at its
shortest depth. The label is the union of those sets over goal states at the minimal goal depth: every first action
of some shortest plan. The training target is uniform over that set (no tie-breaking, no random numbers). The done
action (6) is never in a label.

Outcomes (status):
  labelled       a plan exists with length <= remaining time; label set returned.
  time_exceeded  the shortest plan in the abstraction is longer than the remaining time (no label).
  unresolved     no plan in the abstraction (for example, the goal cell or a needed cell is blocked by a dropped
                 object), or the search reached MAX_NODES (no label). Not a proof of impossibility.
No fallback label is ever produced. Every outcome carries a state category (category()).

The label is a function of the observation (full grid with door states, agent pose, carried object, remaining
time). Hidden context: none is used. The only unobserved quantity in this task, env.accessed, decides eligibility
(prefix states only), not labels. Conflicts are audited by observation hash in the training job.
"""
from collections import Counter

import numpy as np

from bc2rl import task as T

LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE, DONE = range(7)
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))
MAX_NODES = 200_000
N_LABEL_ACTIONS = 6
NOTHING, KEY, OTHER = 0, 1, 2
HELD = None


def frontier(env):
    """Index of the first locked active door, or None when every door is unlocked."""
    L = env.layout
    for j, s in enumerate(L.active_slots()):
        v = env.grid.get(T.DOOR_X[s], L.door_rows[j])
        if v is not None and v.type == "door" and v.is_locked:
            return j
    return None


def _door_cells(L):
    return [(T.DOOR_X[s], L.door_rows[j]) for j, s in enumerate(L.active_slots())]


def _front_free_cells(L):
    """Cells directly in front of every door (both sides)."""
    out = set()
    for (x, y) in _door_cells(L):
        out |= {(x - 1, y), (x + 1, y)}
    return out


def category(env):
    """State category of a prefix state (for records, failure analysis and the recovery bank)."""
    L = env.layout
    j = frontier(env)
    c = env.carrying
    x = int(env.agent_pos[0])
    if j is None:
        return "all_unlocked_" + ("carrying" if c is not None else "empty")
    s = L.active_slots()[j]
    x0 = T.SLOT_X0[s]
    where = "behind" if x < x0 - (1 if j > 0 else 0) else "in_module"
    color = L.colors()[j]
    if c is None:
        inv = "empty"
    elif c.type == "key" and c.color == color:
        inv = "frontier_key"
    elif c.type == "key" and c.color in L.colors()[:j]:
        inv = "obsolete_key"
    else:
        inv = "other_object"
    displaced = False
    if inv != "frontier_key":
        kpos = _find_key(env, color)
        displaced = kpos is not None and tuple(kpos) != tuple(L.key_pos[j])
    return f"{where}_{inv}" + ("_key_displaced" if displaced else "")


def _find_key(env, color):
    for k, v in enumerate(env.grid.grid):
        if v is not None and v.type == "key" and v.color == color:
            return (k % T.WIDTH, k // T.WIDTH)
    return None


def query(env, max_nodes=MAX_NODES, target=None):
    """Label the current (prefix) state. Returns dict(status, mask, plan_len, nodes, frontier).
    target (verification only): a fixed goal module index j, or "cross", instead of the current frontier."""
    assert not env.accessed, "corrective labels are defined only before the boundary"
    L = env.layout
    j = frontier(env) if target is None else (None if target == "cross" else target)
    doors = _door_cells(L)
    if j is None:
        xmax, goal = T.DOOR_X[L.active_slots()[-1]], (T.SUFFIX_X0, T.GATEWAY[1])
        key_color = None
    else:
        xmax, goal = T.DOOR_X[L.active_slots()[j]], doors[j]
        key_color = L.colors()[j]
    upto = len(doors) if j is None else j + 1
    front_free = _front_free_cells(L)
    interiors = set()
    for s in L.active_slots()[:upto]:
        interiors |= {(x, y) for x in range(T.SLOT_X0[s], T.SLOT_X0[s] + 3) for y in T.ROWS}
    # static map of the region: free (empty/floor), door cells by index, fixed obstacles everything else
    free, droppable = set(), set()
    door_idx, closed0, locked_door = {}, 0, None
    kpos0 = None
    for k, v in enumerate(env.grid.grid):
        c = (k % T.WIDTH, k // T.WIDTH)
        if c[0] > xmax and c != goal:
            continue
        if v is None or v.type == "floor":
            free.add(c)
            if v is None and c in interiors and c not in front_free:
                droppable.add(c)
        elif v.type == "door":
            i = len(door_idx)
            door_idx[c] = i
            if v.is_locked:
                locked_door = c                  # only door j* can be locked inside the region
            elif not v.is_open:
                closed0 |= 1 << i
        elif v.type == "key" and key_color is not None and v.color == key_color:
            kpos0 = c                            # free once picked up; blocked while kpos == c
            free.add(c)
            if c in interiors and c not in front_free:
                droppable.add(c)
    if goal not in free and goal not in door_idx:
        return {"status": "unresolved", "reason": "goal cell blocked", "mask": 0, "plan_len": None, "nodes": 0,
                "frontier": j}
    c = env.carrying
    if c is None:
        carry0 = NOTHING
    elif key_color is not None and c.type == "key" and c.color == key_color:
        carry0 = KEY
    else:
        carry0 = OTHER
    if key_color is not None and carry0 != KEY and kpos0 is None:
        return {"status": "unresolved", "reason": "frontier key not reachable", "mask": 0, "plan_len": None,
                "nodes": 0, "frontier": j}
    # state: (x, y, d, carry, kpos, opos, closed_mask, unlocked)
    x, y = int(env.agent_pos[0]), int(env.agent_pos[1])
    if (x, y) == goal:
        return {"status": "at_goal", "mask": 0, "plan_len": 0, "nodes": 0, "frontier": j}
    start = (x, y, int(env.agent_dir), carry0, kpos0 if carry0 != KEY else HELD, HELD, closed0,
             locked_door is None)

    def succ(s):
        x, y, d, carry, kpos, opos, closed, unlocked = s
        fx, fy = x + DIRS[d][0], y + DIRS[d][1]
        f = (fx, fy)
        yield LEFT, (x, y, (d - 1) % 4, carry, kpos, opos, closed, unlocked)
        yield RIGHT, (x, y, (d + 1) % 4, carry, kpos, opos, closed, unlocked)
        blocked = f == kpos or f == opos
        if not blocked:
            if f in free:
                yield FORWARD, (fx, fy, d, carry, kpos, opos, closed, unlocked)
            elif f in door_idx:
                is_open = (f != locked_door or unlocked) and not (closed >> door_idx[f]) & 1
                if is_open:
                    yield FORWARD, (fx, fy, d, carry, kpos, opos, closed, unlocked)
        if carry == NOTHING and f == kpos:
            yield PICKUP, (x, y, d, KEY, HELD, opos, closed, unlocked)
        if carry == OTHER and f in droppable and not blocked:
            yield DROP, (x, y, d, NOTHING, kpos, f, closed, unlocked)
        if f in door_idx:
            if f == locked_door and not unlocked:
                if carry == KEY:
                    yield TOGGLE, (x, y, d, carry, kpos, opos, closed, True)
            elif (closed >> door_idx[f]) & 1:
                yield TOGGLE, (x, y, d, carry, kpos, opos, closed & ~(1 << door_idx[f]), unlocked)

    visited = {start}
    layer = {}
    for a, n in succ(start):
        if n not in visited:
            layer[n] = layer.get(n, 0) | (1 << a)
    depth = 1
    while layer:
        hit = 0
        for n, m in layer.items():
            if (n[0], n[1]) == goal:
                hit |= m
        if hit:
            if depth > env.remaining():
                return {"status": "time_exceeded", "mask": 0, "plan_len": depth, "nodes": len(visited),
                        "frontier": j}
            return {"status": "labelled", "mask": hit, "plan_len": depth, "nodes": len(visited), "frontier": j}
        visited.update(layer)
        if len(visited) > max_nodes:
            return {"status": "unresolved", "reason": "search limit", "mask": 0, "plan_len": None,
                    "nodes": len(visited), "frontier": j}
        nxt = {}
        for s, m in layer.items():
            for a, n in succ(s):
                if n not in visited:
                    nxt[n] = nxt.get(n, 0) | m
        layer = nxt
        depth += 1
    return {"status": "unresolved", "reason": "no plan in abstraction", "mask": 0, "plan_len": None,
            "nodes": len(visited), "frontier": j}


def check_label(snapshot, q):
    """Verify a label against the real environment (executes up to 6 counted actions). From the snapshot, every
    action is executed once; the remaining shortest-plan length to the same goal (fixed target) is recomputed.
    Requirements: each label action is effective and reduces it by exactly 1; each other action leaves it >= the
    original (or makes the goal unreachable in the abstraction). Returns a list of violations."""
    tgt = "cross" if q["frontier"] is None else q["frontier"]
    bad = []
    for a in range(N_LABEL_ACTIONS):
        env = T.StageTask()
        env.reset(options={"snapshot": snapshot})
        env.step(a)
        if env.accessed:
            n = 0 if tgt == "cross" else None
        else:
            r = query(env, target=tgt)
            n = r["plan_len"] if r["status"] in ("labelled", "at_goal", "time_exceeded") else None
        if (q["mask"] >> a) & 1:
            if n != q["plan_len"] - 1:
                bad.append({"action": a, "in_label": True, "new_len": n, "plan_len": q["plan_len"]})
        elif n is not None and n < q["plan_len"]:
            bad.append({"action": a, "in_label": False, "new_len": n, "plan_len": q["plan_len"]})
    return bad


def mask_to_target(mask):
    """Uniform target distribution over the label set (7 actions; done never labelled)."""
    t = np.zeros(T.N_ACTIONS, np.float32)
    bits = [a for a in range(N_LABEL_ACTIONS) if (mask >> a) & 1]
    t[bits] = 1.0 / len(bits)
    return t


def obs_key(obs):
    """Hash key of the actor's observation (grid, aux, time) for conflict auditing and caching."""
    return hash((obs["grid"].tobytes(), obs["aux"].tobytes(), obs["time"].tobytes()))


class Stats:
    """Counters for the supervision cost record."""

    def __init__(self):
        self.status = Counter()
        self.reasons = Counter()
        self.categories = Counter()
        self.failed_categories = Counter()
        self.label_sizes = Counter()
        self.nodes = 0
        self.seconds = 0.0

    def to_dict(self):
        return {"status": dict(self.status), "reasons": dict(self.reasons), "categories": dict(self.categories),
                "failed_categories": dict(self.failed_categories),
                "label_sizes": {str(k): v for k, v in self.label_sizes.items()}, "nodes": self.nodes,
                "planner_seconds": self.seconds}

    @staticmethod
    def from_dict(d):
        s = Stats()
        s.status.update(d["status"]); s.reasons.update(d["reasons"]); s.categories.update(d["categories"])
        s.failed_categories.update(d["failed_categories"])
        s.label_sizes.update({int(k): v for k, v in d["label_sizes"].items()})
        s.nodes, s.seconds = d["nodes"], d["planner_seconds"]
        return s
