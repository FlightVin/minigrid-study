"""Per-attempt progress and error trace (owner instruction 2026-11-02, sections 3 and 6). Diagnostic only.

Tracker(env) is created after reset and called around each env.step. summary() returns, relative to the attempt start:
  mod_entry      first step at which the agent stood in each active module slot (slot of the start: 0)
  door_open      step at which each module door was first unlocked (None if never)
  doors_open_end number of unlocked module doors at the end
  key_pickups    [(color, step)] in order; wrong_key_pickups: pickups of a key other than the one for the first
                 still-locked door (inventory errors)
  locked_toggles toggles on a locked door without its key; door_closes: toggles that closed an open door
  noop_actions   actions that changed neither pose, inventory nor grid (bumps, empty pickup/drop/toggle, done)
  pose_repeat_frac  1 - distinct (x, y, dir) / steps; max_cell_visits: most visits to one cell (navigation loops)
  stage_end      "prefix_m<j>" (in module j, j = index of the first locked door), "suffix_no_target" or "carrying"
"""
from bc2rl import task as T


def _slot_of(x):
    for s, x0 in enumerate(T.SLOT_X0):
        if x0 <= x < x0 + 3:
            return s
    return None


def _door_states(env):
    L = env.layout
    out = []
    for j, s in enumerate(L.active_slots()):
        v = env.grid.get(T.DOOR_X[s], L.door_rows[j])
        out.append(v is not None and v.type == "door" and not v.is_locked)
    return out


class Tracker:
    def __init__(self, env):
        L = env.layout
        self.slots = L.active_slots()
        self.colors = L.colors()
        self.t = 0
        self.mod_entry = [None] * L.K
        self.door_open = [None] * L.K
        for j, o in enumerate(_door_states(env)):
            if o:
                self.door_open[j] = 0
        self.key_pickups, self.wrong = [], 0
        self.locked_toggles = self.door_closes = self.noop = 0
        self.poses, self.cells = set(), {}
        self._enter(env)

    def _enter(self, env):
        s = _slot_of(env.agent_pos[0])
        if s in self.slots:
            j = self.slots.index(s)
            if self.mod_entry[j] is None:
                self.mod_entry[j] = self.t
        c = tuple(int(v) for v in env.agent_pos)
        self.cells[c] = self.cells.get(c, 0) + 1
        self.poses.add((*c, int(env.agent_dir)))

    def before(self, env, action):
        fx, fy = env.front_pos
        self._front = env.grid.get(fx, fy)
        self._front_state = None if self._front is None or self._front.type != "door" else (self._front.is_open, self._front.is_locked)
        self._carry = None if env.carrying is None else (env.carrying.type, env.carrying.color)
        self._pose = (tuple(int(v) for v in env.agent_pos), int(env.agent_dir))
        self._doors = _door_states(env)
        self._action = int(action)

    def after(self, env):
        self.t += 1
        carry = None if env.carrying is None else (env.carrying.type, env.carrying.color)
        pose = (tuple(int(v) for v in env.agent_pos), int(env.agent_dir))
        doors = _door_states(env)
        f, fs = self._front, self._front_state
        changed_door = f is not None and f.type == "door" and (f.is_open, f.is_locked) != fs
        if pose == self._pose and carry == self._carry and doors == self._doors and not changed_door:
            self.noop += 1
        if carry != self._carry and carry is not None and carry[0] == "key":
            self.key_pickups.append((carry[1], self.t))
            need = next((self.colors[j] for j, o in enumerate(self._doors) if not o), None)
            self.wrong += carry[1] != need
        if self._action == 5 and f is not None and f.type == "door":     # toggle
            if fs[1] and f.is_locked:
                self.locked_toggles += 1
            if fs[0] and not f.is_open:
                self.door_closes += 1
        for j, (a, b) in enumerate(zip(self._doors, doors)):
            if b and not a and self.door_open[j] is None:
                self.door_open[j] = self.t
        self._enter(env)

    def summary(self, env):
        doors = _door_states(env)
        st = env.stage()
        if st == 0:
            j = next((j for j, o in enumerate(doors) if not o), len(doors))
            stage = f"prefix_m{j}"
        else:
            stage = "carrying" if st == 2 else "suffix_no_target"
        return {"mod_entry": self.mod_entry, "door_open": self.door_open, "doors_open_end": int(sum(doors)),
                "key_pickups": self.key_pickups, "wrong_key_pickups": self.wrong, "locked_toggles": self.locked_toggles,
                "door_closes": self.door_closes, "noop_actions": self.noop,
                "pose_repeat_frac": 1 - len(self.poses) / max(1, self.t + 1), "max_cell_visits": max(self.cells.values()),
                "stage_end": stage}
