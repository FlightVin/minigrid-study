"""Augmented controllers on frozen policies (owner instruction 2026-11-02b; PROTOCOL_FREEZE Amendment 8). No training.

python -m bc2rl.controller --config experiments/p6/ctrl-v1.json --policy a4_s70

Every episode starts from the layout's normal start. The episode clock, observations, action semantics, reward and
termination are those of bc2rl.task. A controller condition decides, before each action, whether the frozen policy or
a planner helper acts:

  base         the frozen policy (inverse-CDF sampling, as bc2rl.evaluate).
  key_mid      key-acquisition assistance (KA) in the middle prerequisite module (structural index 1 of 3).
  door_mid     door-transition assistance (DA) in the middle module.
  both_mid     KA and DA in the middle module.
  key_all      KA in every prerequisite module (0, 1, 2).
  door_all     DA in every prerequisite module.
  both_all     KA and DA in every prerequisite module.
  mask_prefix  physical-action masking (physical_mask) while the boundary has not been crossed; the unmasked frozen
               policy afterwards.

KA for module j is evaluated once, at the first decision point at which the agent stands in module j's interior
(module 0: the start). If the module's key is already held the status is "not_needed". Otherwise an exact BFS in a
module-local abstraction (module interior only; the module key pickable; a carried object droppable on an empty
interior cell other than the cells in front of the module's entry and exit doors, which layout generation keeps free;
every other object fixed) plans until the key is held.
DA for module j is evaluated once, at the first decision point at which the agent stands in module j's interior,
holds module j's key and has never stood beyond module j's door. The BFS plans within the interior, the door cell
and the first cell beyond the door, until the agent stands on that cell (toggling the door open if needed). For the
last module that cell is the first suffix cell, so the final helper action is the boundary crossing.
Status of each evaluation (deterministic, recorded, the episode always continues):
  assisted              plan found with length <= remaining time; executed with legal env.step actions on the
                        original clock; afterwards the goal is checked (ok true/false); control returns.
  certified_impossible  a relaxed lower bound (all non-wall cells passable; objects and locks ignored; +1 pickup and
                        +1 drop if carrying for KA; +1 toggle if the door is closed for DA) exceeds the remaining time.
  unresolved            otherwise (no module-local plan, or a plan longer than the remaining time while the bound does
                        not exclude success). Search failure is not proof of impossibility.
  not_needed            KA only: the key is already held at first entry.
Modules never eligible (not reached, or for DA the key never held there) are reported as not eligible.
Helper actions never use random numbers. The policy's action at absolute step t uses u[t] from
rng([eval_seed, item, attempt]).random(limit) (common random numbers indexed by absolute environment step), so base
reproduces bc2rl.evaluate.run_attempts exactly and helper steps do not shift other draws.

Arrivals are certified with bc2rl.suffix_cert (executed planner replays are counted).
Output per (policy, condition) unit: ctrl_<policy>_<condition>.jsonl (one compact row per episode), written atomically
when the unit completes; completed units are skipped on restart. summary.json at the end ("complete": true only when
every unit exists). A pause flag or SIGTERM stops before the next unit / immediately (exit 75); a unit whose
conservative bound would exceed the job's action cap is not started (exit 5).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import time

import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import suffix_cert as SC
from bc2rl import task as T
from bc2rl import trace as TR
from bc2rl.telemetry import Heartbeat, resource_heartbeat

LEFT, RIGHT, FORWARD, PICKUP, DROP, TOGGLE, DONE = range(7)
MID = 1
CONDITIONS = {
    "base": {"ka": (), "da": (), "mask": False},
    "key_mid": {"ka": (MID,), "da": (), "mask": False},
    "door_mid": {"ka": (), "da": (MID,), "mask": False},
    "both_mid": {"ka": (MID,), "da": (MID,), "mask": False},
    "key_all": {"ka": (0, 1, 2), "da": (), "mask": False},
    "door_all": {"ka": (), "da": (0, 1, 2), "mask": False},
    "both_all": {"ka": (0, 1, 2), "da": (0, 1, 2), "mask": False},
    "mask_prefix": {"ka": (), "da": (), "mask": True},
}


# -- physical-action mask --------------------------------------------------------------------------------------------
def physical_mask(env):
    """Boolean[7]: True where the action has a permitted physical effect under MiniGrid semantics, from the current
    observable state only (front cell, carried object). No task-solution knowledge.
      left/right  always (they change the direction)
      forward     front cell empty or overlappable (open door, floor)
      pickup      nothing carried and the front object can be picked up (any key or ball, wrong keys included)
      drop        an object is carried and the front cell is empty
      toggle      front object is a door that is unlocked (open or closed), or locked while a key of its colour is
                  carried (keys, balls, walls and floor ignore toggle)
      done        never (it has no effect)
    """
    f = env.grid.get(*env.front_pos)
    c = env.carrying
    m = np.zeros(7, bool)
    m[LEFT] = m[RIGHT] = True
    m[FORWARD] = f is None or f.can_overlap()
    m[PICKUP] = c is None and f is not None and f.can_pickup()
    m[DROP] = c is not None and f is None
    m[TOGGLE] = f is not None and f.type == "door" and (not f.is_locked or (c is not None and c.type == "key"
                                                                             and c.color == f.color))
    return m


def masked_probs(p, m):
    """Renormalized policy probabilities over permitted actions; uniform over permitted actions if they carry no
    mass. Returns (probs, removed_mass)."""
    kept = p * m
    s = kept.sum()
    removed = float(1.0 - s)
    if s <= 1e-12:
        return m / m.sum(), removed
    return kept / s, removed


def sample(p, u):
    c = np.cumsum(p)
    c[-1] = 1.0
    return int((u > c).sum())


# -- module geometry ---------------------------------------------------------------------------------------------------
def module_of(env, pos=None):
    """Active-module index whose interior contains pos (None outside every module interior)."""
    x = int((pos if pos is not None else env.agent_pos)[0])
    L = env.layout
    for j, s in enumerate(L.active_slots()):
        if T.SLOT_X0[s] <= x < T.SLOT_X0[s] + 3:
            return j
    return None


def interior(L, j):
    x0 = T.SLOT_X0[L.active_slots()[j]]
    return {(x, y) for x in range(x0, x0 + 3) for y in T.ROWS}


def door_cell(L, j):
    return (T.DOOR_X[L.active_slots()[j]], L.door_rows[j])


def holds_key(env, j):
    c = env.carrying
    return c is not None and c.type == "key" and c.color == env.layout.colors()[j]


def _free_cells(env):
    return {(k % T.WIDTH, k // T.WIDTH) for k, v in enumerate(env.grid.grid) if v is None or v.type != "wall"}


def _pose(env):
    return (int(env.agent_pos[0]), int(env.agent_pos[1]), int(env.agent_dir))


# -- helpers: planning and bounds -------------------------------------------------------------------------------------
def plan_key(env, j, seed=0):
    """Module-local exact BFS until module j's key is held. Returns (actions or None, reason)."""
    L = env.layout
    cells = interior(L, j)
    if (int(env.agent_pos[0]), int(env.agent_pos[1])) not in cells:
        return None, "agent outside module"
    color = L.colors()[j]
    kcell, passable, droppable = None, set(), set()
    for c in cells:
        v = env.grid.get(*c)
        if v is None:
            passable.add(c)
            droppable.add(c)
        elif v.type == "key" and v.color == color and kcell is None:
            kcell = c
            passable.add(c)
        elif v.type == "floor":
            passable.add(c)
    if kcell is None:
        return None, "module key not in module"
    # never drop on the cells in front of the module's exit and entry doors (kept free by layout generation)
    x0 = T.SLOT_X0[L.active_slots()[j]]
    droppable -= {(x0 + 2, L.door_rows[j])} | ({(x0, L.door_rows[j - 1])} if j > 0 else set())
    x, y, d = _pose(env)
    if env.carrying is None:
        start, mp, md = (x, y, d, P.HELD, (kcell,), True), [True], [False]
    else:
        start, mp, md = (x, y, d, 1, (kcell, P.HELD), True), [True, False], [False, True]
    try:
        return P._bfs(start, passable, droppable, mp, md, None, lambda st: st[3] == 0,
                      np.random.default_rng([seed, 2, j])), "planned"
    except RuntimeError:
        return None, "no module-local plan"


def lb_key(env, j):
    L = env.layout
    color = L.colors()[j]
    kcell = None
    for c in interior(L, j):
        v = env.grid.get(*c)
        if v is not None and v.type == "key" and v.color == color:
            kcell = c
    if kcell is None:
        return np.inf
    free = _free_cells(env)
    d0 = SC._pose_bfs(free, [_pose(env)])
    best = min((d0[(kcell[0] - P.DIRS[d][0], kcell[1] - P.DIRS[d][1], d)] for d in range(4)
                if (kcell[0] - P.DIRS[d][0], kcell[1] - P.DIRS[d][1], d) in d0), default=np.inf)
    return best + 1 + (1 if env.carrying is not None else 0)


def plan_door(env, j, seed=0):
    """Module-local exact BFS through module j's door to the first cell beyond it. Returns (actions or None, reason)."""
    L = env.layout
    cells = interior(L, j)
    if (int(env.agent_pos[0]), int(env.agent_pos[1])) not in cells:
        return None, "agent outside module"
    dc = door_cell(L, j)
    nc = (dc[0] + 1, dc[1])
    door = env.grid.get(*dc)
    if door is None or door.type != "door":
        return None, "no door"
    if env.grid.get(*nc) is not None:
        return None, "cell beyond the door occupied"
    passable = {c for c in cells if env.grid.get(*c) is None or env.grid.get(*c).type == "floor"} | {nc}
    x, y, d = _pose(env)
    start = (x, y, d, 0, (P.HELD,), bool(door.is_open))
    try:
        return P._bfs(start, passable, set(), [False], [False], (dc, 0), lambda st: (st[0], st[1]) == nc,
                      np.random.default_rng([seed, 3, j])), "planned"
    except RuntimeError:
        return None, "no module-local plan"


def lb_door(env, j):
    L = env.layout
    dc = door_cell(L, j)
    nc = (dc[0] + 1, dc[1])
    d0 = SC._pose_bfs(_free_cells(env), [_pose(env)])
    best = min((d0[(nc[0], nc[1], d)] for d in range(4) if (nc[0], nc[1], d) in d0), default=np.inf)
    door = env.grid.get(*dc)
    return best + (0 if door is not None and door.type == "door" and door.is_open else 1)


def episode_bound(layout):
    """Hard bound on executed actions for one controlled episode: the time limit plus the longest possible
    certification replay. Every first boundary crossing enters (13, 4) facing east from the gateway with an untouched
    suffix, so the replay is the exact suffix-abstraction plan from that pose, carrying an object or nothing."""
    env = T.StageTask()
    env.reset(options={"layout": layout})
    for v in env.grid.grid:
        if v is not None and v.type == "door":
            v.is_locked, v.is_open = False, True
    env.agent_pos, env.agent_dir = (T.SUFFIX_X0, T.GATEWAY[1]), 0
    lens = []
    for carry in (T.Key("yellow"), None):
        env.carrying = carry
        p = SC.abstract_plan(env)
        assert p is not None
        lens.append(len(p))
    return layout.limit + max(lens)


# -- episode bookkeeping -----------------------------------------------------------------------------------------------
class Episode:
    def __init__(self, layout, item, attempt, eval_seed, cond):
        self.env = T.StageTask()
        self.obs, _ = self.env.reset(options={"layout": layout})
        self.cond = CONDITIONS[cond]
        self.u = np.random.default_rng([eval_seed, item, attempt]).random(layout.limit)
        self.tr = TR.Tracker(self.env)
        self.queue, self.helper = [], None
        self.acts, self.who = [], []
        self.entered, self.passed = {}, set()
        self.ka_done, self.da_done = set(), set()
        self.assists = []
        self.c = {"learner_steps": 0, "helper_steps": 0, "learner_ineffective_prefix": 0, "learner_ineffective_suffix": 0,
                  "ineffective_mass_prefix": 0.0, "learner_locked_toggles": 0, "learner_key_pickups": 0,
                  "learner_wrong_key_pickups": 0, "learner_key_drops": 0, "key_lost_after_ka": 0,
                  "backtrack_after_da": 0, "mask_steps": 0, "mask_removed_sum": 0.0, "mask_removed_max": 0.0,
                  "mask_changed_action": 0}
        self.rec = {"item": item, "attempt": attempt, "seed": layout.gen_seed, "limit": layout.limit, "arrival": None}
        self.snapshot = None
        self._entry_update()

    def _entry_update(self):
        env = self.env
        j = module_of(env)
        if j is not None and j not in self.entered:
            self.entered[j] = env.step_count
        L = env.layout
        for k, s in enumerate(L.active_slots()):
            if env.agent_pos[0] > T.DOOR_X[s] and k not in self.passed:
                self.passed.add(k)

    def decide(self):
        """Before an action: possibly start a helper. Returns True when a helper action is queued."""
        if self.queue:
            return True
        env = self.env
        j = module_of(env)
        if j is None or env.accessed:
            return False
        if j in self.cond["ka"] and j not in self.ka_done:
            self.ka_done.add(j)
            if holds_key(env, j):
                self.assists.append({"m": j, "type": "ka", "step": env.step_count, "status": "not_needed"})
            else:
                self._start("ka", j, *plan_key(env, j), lb_key(env, j))
                if self.queue:
                    return True
        if j in self.cond["da"] and j not in self.da_done and holds_key(env, j) and j not in self.passed:
            self.da_done.add(j)
            self._start("da", j, *plan_door(env, j), lb_door(env, j))
        return bool(self.queue)

    def _start(self, kind, j, plan, reason, lb):
        env = self.env
        rem = env.remaining()
        a = {"m": j, "type": kind, "step": env.step_count, "remaining": int(rem), "reason": reason,
             "plan_len": None if plan is None else len(plan), "lb": None if not np.isfinite(lb) else int(lb)}
        if plan is not None and len(plan) <= rem:
            a.update(status="assisted", n_exec=0)
            self.queue = list(plan)
            self.helper = a
        elif lb > rem:
            a["status"] = "certified_impossible"
        else:
            a["status"] = "unresolved"
        self.assists.append(a)

    def _finish_helper(self):
        env, a = self.env, self.helper
        j = a["m"]
        if a["type"] == "ka":
            a["ok"] = holds_key(env, j)
        else:
            dc = door_cell(env.layout, j)
            a["ok"] = (tuple(int(v) for v in env.agent_pos) == (dc[0] + 1, dc[1])
                       and env.grid.get(*dc).is_open)
        a["end"] = [*_pose(env), None if env.carrying is None else env.carrying.color]
        self.helper = None

    def step(self, action, by):
        """by: 'p' policy, 'k' KA helper, 'd' DA helper."""
        env = self.env
        before_mod = module_of(env)
        front = env.grid.get(*env.front_pos)
        carry = env.carrying
        if by == "p":
            self.c["learner_steps"] += 1
            if action == TOGGLE and front is not None and front.type == "door" and front.is_locked and not (
                    carry is not None and carry.type == "key" and carry.color == front.color):
                self.c["learner_locked_toggles"] += 1
            if action == PICKUP and carry is None and front is not None and front.type == "key":
                self.c["learner_key_pickups"] += 1
                locked = [c for k, c in enumerate(env.layout.colors())
                          if env.grid.get(*door_cell(env.layout, k)).is_locked]
                if not locked or front.color != locked[0]:
                    self.c["learner_wrong_key_pickups"] += 1
            if action == DROP and carry is not None and carry.type == "key" and front is None:
                self.c["learner_key_drops"] += 1
                if before_mod is not None and carry.color == env.layout.colors()[before_mod] and any(
                        x["type"] == "ka" and x["m"] == before_mod and x["status"] == "assisted" for x in self.assists):
                    self.c["key_lost_after_ka"] += 1
        else:
            self.c["helper_steps"] += 1
        self.tr.before(env, action)
        self.obs, r, term, _, info = env.step(int(action))
        self.tr.after(env)
        self.acts.append(str(int(action)))
        self.who.append(by)
        if by == "p":
            for x in self.assists:
                if x["type"] == "da" and x["status"] == "assisted" and x.get("ok") and not x.get("backtracked"):
                    if env.agent_pos[0] < door_cell(env.layout, x["m"])[0]:
                        x["backtracked"] = True
                        self.c["backtrack_after_da"] += 1
        if self.helper is not None:
            self.helper["n_exec"] += 1
            self.queue.pop(0)
            if not self.queue:
                self._finish_helper()
        self._entry_update()
        if info["crossed"]:
            self.rec["arrival"] = {"tau": info["tau"], "remaining": info["remaining"],
                                   "carrying": None if env.carrying is None else [env.carrying.type, env.carrying.color],
                                   "helper_cross": by != "p"}
            self.snapshot = env.snapshot()
        if term:
            if self.helper is not None:          # cannot happen when plan length <= remaining; recorded if it does
                self.helper["interrupted"] = True
                self._finish_helper()
            self.rec.update(success=bool(info["success"]), accessed=bool(info["accessed"]), tau=info["tau"],
                            end_step=info["step_count"], timeout=bool(info["deadline"]),
                            mod_entry=[self.entered.get(k) for k in range(env.layout.K)],
                            assists=self.assists, counts=self.c, trace=self.tr.summary(env),
                            actions="".join(self.acts), who="".join(self.who))
        return term


@torch.no_grad()
def run_unit(actor, layouts, attempts, eval_seed, cond, device, batch=128, heartbeat=None):
    """All (item, attempt) episodes of one condition. Returns (rows, executed actions incl. certification)."""
    jobs = [(i, j) for i in range(len(layouts)) for j in range(attempts)]
    rows, active, nxt, n_cert = [None] * len(jobs), [], 0, 0
    steps = 0
    while nxt < len(jobs) or active:
        while len(active) < batch and nxt < len(jobs):
            i, j = jobs[nxt]
            active.append((nxt, Episode(layouts[i], i, j, eval_seed, cond)))
            nxt += 1
        need = [(k, e) for k, e in active if not e.decide()]
        acts = {}
        if need:
            obs = {key: np.stack([e.obs[key] for _, e in need]) for key in ("grid", "aux", "time")}
            probs = torch.softmax(actor(*M.obs_to_torch(obs, device)).float(), -1).cpu().numpy().astype(np.float64)
            for (k, e), p in zip(need, probs):
                env = e.env
                u = e.u[env.step_count]
                m = physical_mask(env)
                if not env.accessed:
                    e.c["ineffective_mass_prefix"] += float(1.0 - (p * m).sum())
                if e.cond["mask"] and not env.accessed:
                    q, removed = masked_probs(p, m)
                    a = sample(q, u)
                    e.c["mask_steps"] += 1
                    e.c["mask_removed_sum"] += removed
                    e.c["mask_removed_max"] = max(e.c["mask_removed_max"], removed)
                    e.c["mask_changed_action"] += int(a != sample(p, u))
                else:
                    a = sample(p, u)
                if not m[a]:
                    e.c["learner_ineffective_suffix" if env.accessed else "learner_ineffective_prefix"] += 1
                acts[k] = (a, "p")
        keep = []
        for k, e in active:
            if k in acts:
                a, by = acts[k]
            else:
                a, by = e.queue[0], ("k" if e.helper["type"] == "ka" else "d")
            steps += 1
            if e.step(a, by):
                if e.snapshot is not None:
                    c = SC.certify(e.snapshot)
                    n_cert += c["replay_actions"]
                    e.rec["arrival"]["cert"] = c
                rows[k] = e.rec
            else:
                keep.append((k, e))
        active = keep
        if heartbeat is not None:
            heartbeat()
    return rows, steps + n_cert, {"episode": steps, "certification": n_cert}


def load_actor(project, spec):
    from bc2rl import diag5
    return diag5.load_policy(project, spec)


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--policy", action="append", required=True)
    ap.add_argument("--cap", type=int, default=None, help="job action cap (default: the job's conservative bound)")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("controller")
    project = Path(os.environ.get("MAE_PROJECT", "."))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    device = torch.device(os.environ.get("MAE_DEVICE", "cpu"))
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))
    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    lay_file = project / "data" / cfg["dataset_id"] / "layouts.json"
    items = [it for it in json.loads(lay_file.read_text())[cfg["role"]] if it["layout"]["K"] == 3][:cfg["n_layouts"]]
    layouts = [T.Layout.from_dict(it["layout"]) for it in items]
    panel_hash = hashlib.sha256(json.dumps([it["layout"] for it in items], sort_keys=True).encode()).hexdigest()
    if cfg.get("panel_sha256"):
        assert panel_hash == cfg["panel_sha256"], "panel hash differs from the frozen value"
    unit_bound = cfg["attempts"] * sum(episode_bound(L) for L in layouts)
    cap = a.cap if a.cap is not None else unit_bound * len(cfg["conditions"]) * len(a.policy)
    used, actions = 0, {"episode": 0, "certification": 0}
    out = {"units": {}, "panel_sha256": panel_hash, "dataset_manifest_sha256": file_sha(
        project / "data" / cfg["dataset_id"] / "manifest.json"), "code_sha256": file_sha(__file__),
        "policies": {}, "unit_bound": unit_bound, "cap": cap}
    last = [time.time()]

    def hb():
        if stop["flag"]:
            raise SystemExit(BAT.PAUSED_EXIT)
        if time.time() - last[0] > 5:
            resource_heartbeat()
            last[0] = time.time()

    t0 = time.time()
    reason = None
    with Heartbeat(interval=5):
        for name in a.policy:
            spec = cfg["policies"][name]
            actor = load_actor(project, spec).to(device)
            out["policies"][name] = spec
            for cond in cfg["conditions"]:
                f = run_dir / f"ctrl_{name}_{cond}.jsonl"
                if f.exists():
                    out["units"][f.name] = {"skipped_existing": True}
                    continue
                if BAT.flag_path(project).exists() or stop["flag"]:
                    reason = "pause"
                    break
                if used + unit_bound > cap:
                    reason = "action cap"
                    break
                rows, n, parts = run_unit(actor, layouts, cfg["attempts"], cfg["eval_seed"], cond, device, heartbeat=hb)
                for r in rows:
                    r.update(policy=name, condition=cond)
                used += n
                for k in parts:
                    actions[k] += parts[k]
                tmp = f.with_name(f.name + ".tmp")
                tmp.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in rows))
                os.replace(tmp, f)
                out["units"][f.name] = {"rows": len(rows), "actions": n, **parts,
                                        "P1": float(np.mean([r["success"] for r in rows]))}
                print(json.dumps({"unit": f.name, "actions": n}), flush=True)
            if reason:
                break
    expected = [f"ctrl_{n}_{c}.jsonl" for n in a.policy for c in cfg["conditions"]]
    complete = all((run_dir / e).exists() for e in expected)
    BAT.write_atomic(run_dir / "summary.json", {"mode": "controller", **out, "actions": actions,
                                                "actions_total": used, "complete": complete, "stopped": reason,
                                                "wall_seconds": time.time() - t0, "config": cfg})
    if reason == "pause":
        raise SystemExit(BAT.PAUSED_EXIT)
    if not complete:
        raise SystemExit(5)


if __name__ == "__main__":
    main()
