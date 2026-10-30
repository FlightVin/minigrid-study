"""Locked-door prefix + retrieval/delivery suffix on a fixed MiniGrid canvas.

Canvas (x right, y down), identical for every K:

    x=0 wall | slot0 x=1..3 | wall x=4 | slot1 x=5..7 | wall x=8 | slot2 x=9..11 | wall x=12 | suffix x=13..19 | x=20 wall
    y=0 and y=8 are walls; interiors use y=1..7.

The K active modules occupy the last K slots; inactive slots are solid wall. Module j has a key of
color MODULE_COLORS[3-K+j] inside its slot and a locked door of the same color in the slot's right
wall. The last module's door is the gateway at (12, 4) and is always yellow. The suffix has an
internal wall at x=16 with one gap; the target (purple ball) and a distractor (green ball) are in
x=17..19; the delivery cell (purple floor) is in x=13..15.

Boundary: the first step that puts the agent at x >= SUFFIX_X0. The chain makes this possible only
after every door is unlocked, so grid door states certify the prefix (no hidden progress flag).
Success: agent on the delivery cell while carrying the target. Reward 1 on success, else 0.
The episode ends on success or when step_count reaches the layout's limit H (a true deadline).
"""
from dataclasses import asdict, dataclass
import hashlib
import json

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from minigrid.core.constants import COLOR_TO_IDX, OBJECT_TO_IDX
from minigrid.core.grid import Grid
from minigrid.core.mission import MissionSpace
from minigrid.core.world_object import Ball, Door, Floor, Key, Wall, WorldObj
from minigrid.minigrid_env import MiniGridEnv

WIDTH, HEIGHT = 21, 9
N_SLOTS = 3
SLOT_X0 = (1, 5, 9)            # first interior column of each slot
DOOR_X = (4, 8, 12)            # wall column to the right of each slot
GATEWAY = (12, 4)
SUFFIX_X0 = 13                 # boundary: first column of the suffix
INNER_WALL_X = 16
NEAR_X = (13, 14, 15)
FAR_X = (17, 18, 19)
ROWS = tuple(range(1, 8))
MODULE_COLORS = ("red", "blue", "yellow")   # final module is always yellow
TARGET = ("ball", "purple")
DISTRACTOR = ("ball", "green")
DELIVERY_COLOR = "purple"
H_NORM = 200                   # common time normalizer for every K
SNAPSHOT_VERSION = 1
N_ACTIONS = 7
OBS_GRID_CHANNELS = 4          # object type, color, state, agent marker (0 none, 1+dir)


@dataclass(frozen=True)
class Layout:
    """One complete map. `limit` is H_x; it is set after planning (0 = not yet planned)."""
    K: int
    family: str
    door_rows: tuple            # one per active module; last is GATEWAY row
    key_pos: tuple              # ((x, y), ...) one per active module
    agent_pos: tuple
    agent_dir: int
    gap_row: int
    target_pos: tuple
    distractor_pos: tuple
    delivery_pos: tuple
    gen_seed: int
    limit: int = 0

    def to_json(self):
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))

    @staticmethod
    def from_dict(d):
        tup = lambda v: tuple(tuple(x) if isinstance(x, list) else x for x in v)
        return Layout(K=d["K"], family=d["family"], door_rows=tuple(d["door_rows"]),
                      key_pos=tup(d["key_pos"]), agent_pos=tuple(d["agent_pos"]),
                      agent_dir=d["agent_dir"], gap_row=d["gap_row"], target_pos=tuple(d["target_pos"]),
                      distractor_pos=tuple(d["distractor_pos"]), delivery_pos=tuple(d["delivery_pos"]),
                      gen_seed=d["gen_seed"], limit=d["limit"])

    def structure_hash(self):
        """Hash of the map itself, excluding seed and limit (for split-overlap checks)."""
        d = asdict(self)
        d.pop("gen_seed"), d.pop("limit")
        return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()[:16]

    def with_limit(self, limit):
        return Layout(**{**asdict(self), "limit": int(limit)})

    def active_slots(self):
        return tuple(range(N_SLOTS - self.K, N_SLOTS))

    def colors(self):
        return MODULE_COLORS[N_SLOTS - self.K:]


def generate_layout(K, seed, family="gap"):
    """Sample a layout from (K, seed).

    The suffix uses its own RNG stream, so one seed gives the same suffix for every K.
    """
    assert 1 <= K <= N_SLOTS and family == "gap"
    rng = np.random.default_rng([seed, 0])
    slots = range(N_SLOTS - K, N_SLOTS)
    door_rows = tuple(int(rng.integers(1, 8)) for _ in range(K - 1)) + (GATEWAY[1],)
    key_pos, agent_pos = [], None
    for j, s in enumerate(slots):
        x0 = SLOT_X0[s]
        cells = [(x, y) for x in range(x0, x0 + 3) for y in ROWS]
        # Keep the cells directly in front of the entry and exit doors free.
        blocked = {(x0 + 2, door_rows[j])}
        if j > 0:
            blocked.add((x0, door_rows[j - 1]))
        cells = [c for c in cells if c not in blocked]
        if j == 0:
            agent_pos = cells[int(rng.integers(len(cells)))]
            cells = [c for c in cells if c != agent_pos]
        key_pos.append(cells[int(rng.integers(len(cells)))])
    agent_dir = int(rng.integers(4))
    rng = np.random.default_rng([seed, 1])
    gap_row = int(rng.integers(1, 8))
    far = [(x, y) for x in FAR_X for y in ROWS if (x, y) != (FAR_X[0], gap_row)]
    i, j = rng.choice(len(far), size=2, replace=False)
    near = [(x, y) for x in NEAR_X for y in ROWS if (x, y) != (SUFFIX_X0, GATEWAY[1])]
    delivery = near[int(rng.integers(len(near)))]
    return Layout(K=K, family=family, door_rows=door_rows, key_pos=tuple(key_pos), agent_pos=agent_pos,
                  agent_dir=agent_dir, gap_row=gap_row, target_pos=far[i], distractor_pos=far[j],
                  delivery_pos=delivery, gen_seed=int(seed))


def build_grid(layout):
    g = Grid(WIDTH, HEIGHT)
    g.wall_rect(0, 0, WIDTH, HEIGHT)
    first = N_SLOTS - layout.K
    for x in range(1, SLOT_X0[first]):           # inactive slots and their walls
        for y in ROWS:
            g.set(x, y, Wall())
    for x in DOOR_X[first:]:
        for y in ROWS:
            g.set(x, y, Wall())
    for y in ROWS:
        if y != layout.gap_row:
            g.set(INNER_WALL_X, y, Wall())
    for j, (s, color) in enumerate(zip(layout.active_slots(), layout.colors())):
        g.set(DOOR_X[s], layout.door_rows[j], Door(color, is_locked=True))
        g.set(*layout.key_pos[j], Key(color))
    g.set(*layout.target_pos, Ball(TARGET[1]))
    g.set(*layout.distractor_pos, Ball(DISTRACTOR[1]))
    g.set(*layout.delivery_pos, Floor(DELIVERY_COLOR))
    return g


def encode_grid(grid):
    """Fast equivalent of Grid.encode() for a fully visible grid."""
    arr = np.zeros((WIDTH, HEIGHT, 3), dtype=np.uint8)
    arr[:, :, 0] = OBJECT_TO_IDX["empty"]
    for k, v in enumerate(grid.grid):
        if v is not None:
            arr[k % WIDTH, k // WIDTH] = v.encode()
    return arr


class StageTask(MiniGridEnv):
    """Gymnasium env. reset(options={"layout": Layout}) or reset(options={"snapshot": dict})."""

    def __init__(self):
        super().__init__(mission_space=MissionSpace(mission_func=lambda: "deliver the purple ball"),
                         width=WIDTH, height=HEIGHT, max_steps=10 ** 9, see_through_walls=True,
                         agent_view_size=3)
        self.observation_space = spaces.Dict({
            "grid": spaces.Box(0, 255, (WIDTH, HEIGHT, OBS_GRID_CHANNELS), np.uint8),
            "aux": spaces.MultiDiscrete([4, len(OBJECT_TO_IDX), len(COLOR_TO_IDX) + 1]),
            "time": spaces.Box(0.0, 1.0, (1,), np.float32),
        })
        self.layout = None

    # -- generation and restoration -------------------------------------------------------------
    def _gen_grid(self, width, height):
        L = self.layout
        self.grid = build_grid(L)
        self.agent_pos, self.agent_dir = tuple(L.agent_pos), L.agent_dir

    def reset(self, *, seed=None, options=None):
        options = options or {}
        if "snapshot" in options:
            return self._restore(options["snapshot"], seed)
        self.layout = options.get("layout", self.layout)
        assert self.layout is not None and self.layout.limit > 0, "reset needs a planned layout"
        obs, _ = super().reset(seed=seed)
        self.accessed, self.tau, self.succeeded = False, None, False
        return obs, self._info()

    def snapshot(self):
        """Complete, versioned state. Remaining time is implied by step_count and layout.limit."""
        c = self.carrying
        return {"version": SNAPSHOT_VERSION, "layout": json.loads(self.layout.to_json()),
                "grid": encode_grid(self.grid).tolist(),
                "carrying": None if c is None else [OBJECT_TO_IDX[c.type], COLOR_TO_IDX[c.color]],
                "agent_pos": [int(v) for v in self.agent_pos], "agent_dir": int(self.agent_dir),
                "step_count": int(self.step_count), "accessed": bool(self.accessed), "tau": self.tau,
                "np_random": self.np_random.bit_generator.state if self._np_random is not None else None}

    def _restore(self, snap, seed):
        assert snap["version"] == SNAPSHOT_VERSION
        gym.Env.reset(self, seed=seed)
        self.layout = Layout.from_dict(snap["layout"])
        self.grid, _ = Grid.decode(np.array(snap["grid"], dtype=np.uint8))
        c = snap["carrying"]
        self.carrying = None if c is None else WorldObj.decode(c[0], c[1], 0)
        if self.carrying is not None:
            self.carrying.cur_pos = np.array([-1, -1])
        self.agent_pos, self.agent_dir = tuple(snap["agent_pos"]), snap["agent_dir"]
        self.step_count = snap["step_count"]   # original remaining time is kept, never refreshed
        self.accessed, self.tau, self.succeeded = snap["accessed"], snap["tau"], False
        if snap["np_random"] is not None and seed is None:
            self.np_random.bit_generator.state = snap["np_random"]
        assert self.step_count < self.layout.limit, "snapshot has no remaining time"
        return self.gen_obs(), self._info()

    # -- dynamics --------------------------------------------------------------------------------
    def step(self, action):
        assert not self.succeeded and self.step_count < self.layout.limit, "step after episode end"
        _, base_reward, base_term, _, _ = super().step(int(action))
        assert base_reward == 0 and not base_term   # no goal/lava objects exist in this task
        crossed = False
        if not self.accessed and self.agent_pos[0] >= SUFFIX_X0:
            assert self.all_doors_unlocked(), "boundary crossed with a locked door"
            self.accessed, self.tau, crossed = True, self.step_count, True
        c = self.carrying
        self.succeeded = (tuple(self.agent_pos) == tuple(self.layout.delivery_pos) and c is not None
                          and (c.type, c.color) == TARGET)
        deadline = self.step_count >= self.layout.limit
        reward = 1.0 if self.succeeded else 0.0
        info = self._info()
        info.update(crossed=crossed, deadline=deadline and not self.succeeded)
        # The deadline is a true terminal event (time is observed), not a truncation.
        return self.gen_obs(), reward, self.succeeded or deadline, False, info

    def all_doors_unlocked(self):
        return not any(v is not None and v.type == "door" and v.is_locked for v in self.grid.grid)

    def stage(self):
        """0 prefix, 1 suffix before target pickup, 2 carrying target (diagnostic only)."""
        if not self.accessed:
            return 0
        c = self.carrying
        return 2 if c is not None and (c.type, c.color) == TARGET else 1

    def remaining(self):
        return self.layout.limit - self.step_count

    def _info(self):
        return {"accessed": self.accessed, "tau": self.tau, "success": self.succeeded,
                "step_count": self.step_count, "remaining": self.remaining()}

    def gen_obs(self):
        grid = np.zeros((WIDTH, HEIGHT, OBS_GRID_CHANNELS), dtype=np.uint8)
        grid[:, :, :3] = encode_grid(self.grid)
        grid[self.agent_pos[0], self.agent_pos[1], 3] = 1 + self.agent_dir
        c = self.carrying
        aux = np.array([self.agent_dir, 0 if c is None else OBJECT_TO_IDX[c.type],
                        0 if c is None else 1 + COLOR_TO_IDX[c.color]], dtype=np.int64)
        t = np.array([self.remaining() / H_NORM], dtype=np.float32)
        return {"grid": grid, "aux": aux, "time": t}
