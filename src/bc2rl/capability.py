"""Actor capability audit: environment-side jobs (owner instruction 2026-11-03; PROTOCOL_FREEZE Amendment 10).
Every env.step is a counted executed action.

python -m bc2rl.capability collect  --config experiments/p8/collect-v1.json
python -m bc2rl.capability validate --config experiments/p8/validate-v1.json
python -m bc2rl.capability rollout  --config experiments/p8/rollout-v1.json

collect   Learner-visited prefix states. Each episode runs one frozen policy (inverse-CDF sampling with
          u = rng([sample_seed, group index, episode]).random(limit)) from a normal start until the first boundary
          crossing or the deadline. Every visited prefix state (before the action) is recorded with its observation,
          planner query (bc2rl.corrective.query), category, stratum, remaining time and two relaxed lower bounds.
          A group either runs a fixed layout list (per_layout episodes each) or, with action_budget, visits layouts
          in their frozen order and starts no new layout once its actions reach the budget (the current episode
          finishes). With stall_steps, an episode ends early after that many consecutive steps without a new
          configuration (grid, pose, inventory; time excluded) in the episode: later loop states repeat earlier ones.
          Output: data/<out_dir>/collect_<group>.npz (one row per visited state, repeats kept) + summary.json.
validate  Zero-action checks on every collected row (state rebuilt from the observation alone; planner re-run; layout
          door rows and colours equal to the grid; conflicts by observation), check_label in the real environment on a
          predetermined stratified sample, and the expert prefix controller on a predetermined validation panel.
rollout   Unassisted prefix execution of controllers on the final panel: deterministic argmax (fitted actors and BC
          actors) or the expert prefix controller (lowest-index label action). Stops at the first boundary crossing or
          the deadline. No planner, mask, reset or hidden input reaches a learned controller.

Relaxed lower bound (certification): the number of forward moves on a grid where every non-wall cell is passable
(doors, keys and balls included), from the agent's cell to the goal cell. Any real plan needs at least that many
actions. lb_goal > remaining certifies that the current module cannot be completed in time; lb_cross > remaining
certifies that the boundary cannot be reached in time. Planner statuses time_exceeded and unresolved are not
certificates by themselves.
"""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import time

from minigrid.core.constants import COLOR_TO_IDX, OBJECT_TO_IDX
import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import corrective as CR
from bc2rl import model as M
from bc2rl import task as T
from bc2rl import trace as TR
from bc2rl.recovery_bank import STRATA, stratum

STATUS = ("labelled", "time_exceeded", "unresolved", "at_goal")
REASONS = ("", "goal cell blocked", "frontier key not reachable", "search limit", "no plan in abstraction")
LABEL_TYPES = ("turn", "forward", "pickup", "drop", "toggle")


def project_dir():
    return Path(os.environ.get("MAE_PROJECT", "."))


def run_dir():
    return Path(os.environ.get("MAE_RUN_DIR", "."))


def find_run(project, name):
    ds = sorted(d for d in (project / ".mae/runs").glob(f"*/{name}") if (d / "summary.json").exists())
    assert ds, f"no complete run {name}"
    return ds[-1]


def role_layouts(project, dataset_id, role):
    lay = json.loads((project / "data" / dataset_id / "layouts.json").read_text())[role]
    return [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3]


def group_layouts(project, g):
    """(layout list, role indices) of a group spec: {"role", "indices"} or {"role", "perm_seed", "start", "count"}."""
    lays = role_layouts(project, g["dataset_id"], g["role"])
    if "indices" in g:
        idx = list(g["indices"])
    else:
        perm = np.random.default_rng(g["perm_seed"]).permutation(len(lays))
        idx = [int(i) for i in perm[g["start"]:g["start"] + g["count"]]]
    return [lays[i] for i in idx], idx


def load_policy(project, spec):
    d = find_run(project, spec["job"])
    if spec["kind"] == "bc":
        st = torch.load(d / f"actor_u{spec['update']}.pt", map_location="cpu", weights_only=False)
        sd = st["actor"] if "actor" in st else st["state"]
    else:
        from bc2rl import ppo as PP
        saved = torch.load(d / f"state_{spec['at']}.pt", map_location="cpu", weights_only=False)
        assert PP.state_hash(saved["state"]) == saved["hash"], "state hash"
        sd = saved["state"]["actor"]
    a = M.Actor()
    a.load_state_dict(sd)
    a.eval()
    return a


def relaxed_lb(env, goal):
    """Forward moves from the agent's cell to goal with every non-wall cell passable (a lower bound on actions)."""
    start = (int(env.agent_pos[0]), int(env.agent_pos[1]))
    if start == goal:
        return 0
    seen, q = {start}, deque([(start, 0)])
    while q:
        (x, y), d = q.popleft()
        for dx, dy in CR.DIRS:
            n = (x + dx, y + dy)
            if n in seen or not (0 <= n[0] < T.WIDTH and 0 <= n[1] < T.HEIGHT):
                continue
            v = env.grid.get(*n)
            if v is not None and v.type == "wall":
                continue
            if n == goal:
                return d + 1
            seen.add(n)
            q.append((n, d + 1))
    return 10 ** 4


def goals(env):
    j = CR.frontier(env)
    L = env.layout
    cross = (T.SUFFIX_X0, T.GATEWAY[1])
    if j is None:
        return cross, cross
    return (T.DOOR_X[L.active_slots()[j]], L.door_rows[j]), cross


def label_types(mask):
    out = set()
    for a in range(CR.N_LABEL_ACTIONS):
        if (mask >> a) & 1:
            out.add({CR.LEFT: "turn", CR.RIGHT: "turn", CR.FORWARD: "forward", CR.PICKUP: "pickup", CR.DROP: "drop",
                     CR.TOGGLE: "toggle"}[a])
    return out


def snapshot_from_obs(grid, aux, time_, layout):
    """Rebuild a StageTask snapshot from the actor's observation and the layout (limit only through remaining)."""
    pos = np.argwhere(grid[:, :, 3] > 0)
    assert len(pos) == 1, "exactly one agent marker"
    remaining = int(round(float(time_) * T.H_NORM))
    carry = None if int(aux[1]) == 0 else [int(aux[1]), int(aux[2]) - 1]
    return {"version": T.SNAPSHOT_VERSION, "layout": json.loads(layout.to_json()),
            "grid": grid[:, :, :3].astype(int).tolist(), "carrying": carry,
            "agent_pos": [int(pos[0][0]), int(pos[0][1])], "agent_dir": int(aux[0]),
            "step_count": layout.limit - remaining, "accessed": False, "tau": None, "np_random": None}


def obs_key(grid, aux, time_):
    """Full observation (grid, aux, time)."""
    return hashlib.sha1(grid.tobytes() + aux.astype(np.int64).tobytes() + np.float32(time_).tobytes()).hexdigest()


def cfg_key(grid, aux):
    """Configuration without time: the label set does not depend on time (only the status does). The unit of
    unique states in the audit dataset."""
    return hashlib.sha1(grid.tobytes() + aux.astype(np.int64).tobytes()).hexdigest()


def env_from(snap):
    env = T.StageTask()
    env.reset(options={"snapshot": snap})
    return env


# -- collect -------------------------------------------------------------------------------------------------------
@torch.no_grad()
def collect(cfg):
    project = project_dir()
    out = project / cfg["out_dir"]
    out.mkdir(parents=True, exist_ok=True)
    policies = [load_policy(project, p) for p in cfg["policies"]]
    summary = {"complete": False, "groups": {}}
    total = 0
    for gi, g in enumerate(cfg["groups"]):
        lays, idx = group_layouts(project, g)
        rows = {k: [] for k in ("grid", "aux", "time", "status", "reason", "mask", "plan_len", "stratum", "category",
                                "layout", "episode", "step", "policy", "action", "lb_goal", "lb_cross", "remaining")}
        cats, eps, n_actions = {}, [], 0
        episode = 0
        budget, stall = g.get("action_budget"), g.get("stall_steps")
        for li, (L, ri) in enumerate(zip(lays, idx)):
            if budget is not None and n_actions >= budget:
                break
            for pi in _schedule(g, li):
                if BAT.flag_path(project).exists():
                    raise SystemExit(BAT.PAUSED_EXIT)
                actor = policies[pi]
                env = T.StageTask()
                obs, _ = env.reset(options={"layout": L})
                u = np.random.default_rng([cfg["sample_seed"], gi, episode]).random(L.limit)
                term, stalled, ep_cfgs, since_new = False, False, set(), 0
                while not term and not env.accessed:
                    ck = cfg_key(obs["grid"], obs["aux"])
                    since_new = 0 if ck not in ep_cfgs else since_new + 1
                    ep_cfgs.add(ck)
                    if stall is not None and since_new >= stall:
                        stalled = True                      # no new configuration for `stall` steps: end early
                        break
                    q = CR.query(env)
                    cat = CR.category(env)
                    gl, gc = goals(env)
                    rows["grid"].append(obs["grid"].copy()); rows["aux"].append(obs["aux"].astype(np.int8))
                    rows["time"].append(float(obs["time"][0]))
                    rows["status"].append(STATUS.index(q["status"]))
                    rows["reason"].append(REASONS.index(q.get("reason", "")))
                    rows["mask"].append(int(q["mask"])); rows["plan_len"].append(-1 if q["plan_len"] is None else q["plan_len"])
                    rows["stratum"].append(STRATA.index(stratum(cat)))
                    rows["category"].append(cats.setdefault(cat, len(cats)))
                    rows["layout"].append(ri); rows["episode"].append(episode); rows["step"].append(int(env.step_count))
                    rows["policy"].append(pi)
                    rows["lb_goal"].append(relaxed_lb(env, gl)); rows["lb_cross"].append(relaxed_lb(env, gc))
                    rows["remaining"].append(env.remaining())
                    o = {k: obs[k][None] for k in ("grid", "aux", "time")}
                    p = torch.softmax(actor(*M.obs_to_torch(o, torch.device("cpu"))).float(), -1).numpy()[0]
                    c = np.cumsum(p.astype(np.float64))
                    c[-1] = 1.0
                    act = int((u[env.step_count] > c).sum())
                    rows["action"].append(act)
                    obs, _, term, _, info = env.step(act)
                    n_actions += 1
                eps.append({"episode": episode, "layout": ri, "policy": pi, "crossed": bool(env.accessed),
                            "stalled": stalled, "steps": int(env.step_count)})
                episode += 1
        arr = {"grid": np.array(rows["grid"], np.uint8), "aux": np.array(rows["aux"], np.int8),
               "time": np.array(rows["time"], np.float32)}
        for k in rows:
            if k not in arr:
                arr[k] = np.array(rows[k], np.int32)
        path = out / f"collect_{g['name']}.npz"
        np.savez_compressed(path, **arr, categories=np.array(sorted(cats, key=cats.get)))
        summary["groups"][g["name"]] = {
            "role": g["role"], "layouts_available": len(lays), "layouts_used": len({e["layout"] for e in eps}),
            "layout_indices_used": sorted({e["layout"] for e in eps}),
            "episodes": len(eps), "crossed": sum(e["crossed"] for e in eps),
            "stalled": sum(e["stalled"] for e in eps), "rows": len(arr["status"]),
            "actions": n_actions, "file": str(path.relative_to(project)), "sha256": _sha(path),
            "status_counts": {s: int((arr["status"] == i).sum()) for i, s in enumerate(STATUS)}}
        total += n_actions
    summary.update(complete=True, actions=total)
    BAT.write_atomic(run_dir() / "summary.json", summary)


def _schedule(g, li):
    """Policy indices for layout li: "rotate" gives per_layout consecutive policies in a fixed rotation; "table"
    cycles through the rows of policy_table."""
    if g.get("mode", "rotate") == "rotate":
        return [(li * g["per_layout"] + k) % g["n_policies"] for k in range(g["per_layout"])]
    return list(g["policy_table"][li % len(g["policy_table"])])


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# -- expert prefix controller -------------------------------------------------------------------------------------
def expert_episode(L):
    """Lowest-index label action each step. Stops at the boundary, the deadline or the first unlabelled state."""
    env = T.StageTask()
    env.reset(options={"layout": L})
    tr = TR.Tracker(env)
    statuses, stop, n = [], None, 0
    while not env.accessed:
        if env.step_count >= L.limit:
            stop = "deadline"
            break
        q = CR.query(env)
        if q["status"] != "labelled":
            stop = "no_label:" + q["status"] + ":" + q.get("reason", "")
            break
        a = min(b for b in range(CR.N_LABEL_ACTIONS) if (q["mask"] >> b) & 1)
        tr.before(env, a)
        _, _, term, _, _ = env.step(a)
        tr.after(env)
        n += 1
        if term and not env.accessed:
            stop = "deadline"
            break
    return {"crossed": bool(env.accessed), "tau": env.tau, "steps": int(env.step_count), "stop": stop,
            "end_category": None if env.accessed else CR.category(env), "trace": tr.summary(env)}, n


# -- validate -----------------------------------------------------------------------------------------------------
def validate(cfg):
    project = project_dir()
    res, actions = {}, 0
    t0 = time.time()
    layouts_by_role = {}
    for gname in cfg["groups"]:
        z = np.load(project / cfg["data_dir"] / f"collect_{gname}.npz")
        role = cfg["group_roles"][gname]
        lays = layouts_by_role.setdefault(role, role_layouts(project, cfg["dataset_id"], role))
        n = len(z["status"])
        mism, door_bad, conflicts, seen = 0, 0, 0, {}
        cfg_masks, cfg_conflicts = {}, 0
        mism_examples = []
        for i in range(n):
            if BAT.flag_path(project).exists():
                raise SystemExit(BAT.PAUSED_EXIT)
            g, a, t = z["grid"][i], z["aux"][i], z["time"][i]
            key = obs_key(g, a, t)
            val = (int(z["status"][i]), int(z["mask"][i]))
            if val[0] == 0:                                   # same configuration at another time: same label set
                ck = cfg_key(g, a)
                if ck in cfg_masks and cfg_masks[ck] != val[1]:
                    cfg_conflicts += 1
                cfg_masks.setdefault(ck, val[1])
            if key in seen:
                if seen[key] != val:
                    conflicts += 1
                continue
            seen[key] = val
            L = lays[int(z["layout"][i])]
            env = env_from(snapshot_from_obs(g, a, t, L))
            q = CR.query(env)
            if (STATUS.index(q["status"]), int(q["mask"])) != val:
                mism += 1
                if len(mism_examples) < 10:
                    mism_examples.append({"row": i, "recorded": val, "rebuilt": [q["status"], q["mask"]]})
            for j, s in enumerate(L.active_slots()):       # the planner's layout reads are visible in the grid
                v = g[T.DOOR_X[s], L.door_rows[j]]
                if v[0] != OBJECT_TO_IDX["door"] or v[1] != COLOR_TO_IDX[L.colors()[j]]:
                    door_bad += 1
        res[gname] = {"rows": n, "unique_observations": len(seen), "unique_labelled_configurations": len(cfg_masks),
                      "rebuilt_query_mismatches": mism, "mismatch_examples": mism_examples,
                      "observation_conflicts": conflicts, "configuration_label_conflicts_across_time": cfg_conflicts,
                      "door_rows_or_colours_not_visible": door_bad}
    res["zero_action_seconds"] = time.time() - t0
    # check_label on a predetermined stratified sample of unique labelled training states
    ck = cfg["check"]
    z = np.load(project / cfg["data_dir"] / f"collect_{ck['group']}.npz")
    lays = layouts_by_role[cfg["group_roles"][ck["group"]]]
    first = {}
    for i in range(len(z["status"])):
        if z["status"][i] != 0:
            continue
        first.setdefault(cfg_key(z["grid"][i], z["aux"][i]), i)
    uniq = np.array(sorted(first.values()))
    checked = []
    for si, st in enumerate(STRATA):
        pool = uniq[z["stratum"][uniq] == si]
        k = min(len(pool), ck["per_stratum"])
        pick = np.sort(np.random.default_rng([ck["seed"], si]).choice(len(pool), k, replace=False)) if k else []
        for p in pick:
            i = int(pool[p])
            L = lays[int(z["layout"][i])]
            snap = snapshot_from_obs(z["grid"][i], z["aux"][i], z["time"][i], L)
            env = env_from(snap)
            q = {"mask": int(z["mask"][i]), "plan_len": int(z["plan_len"][i]), "frontier": CR.frontier(env)}
            bad = CR.check_label(snap, q)
            actions += CR.N_LABEL_ACTIONS
            checked.append({"row": i, "stratum": st, "types": sorted(label_types(q["mask"])),
                            "label_size": bin(q["mask"]).count("1"), "violations": bad})
    by = {}
    for c in checked:
        for key in ["stratum:" + c["stratum"]] + ["type:" + t for t in c["types"]] + ["all"]:
            b = by.setdefault(key, {"checked": 0, "with_violations": 0})
            b["checked"] += 1
            b["with_violations"] += bool(c["violations"])
    res["check_label"] = {"by": by, "violation_examples": [c for c in checked if c["violations"]][:20],
                          "audited_rows": [c["row"] for c in checked if not c["violations"]]}
    # expert prefix controller on the validation panel
    elays, eidx = group_layouts(project, cfg["expert_panel"])
    eps = []
    for L, ri in zip(elays, eidx):
        e, n = expert_episode(L)
        actions += n
        e["layout"] = ri
        eps.append(e)
    res["expert"] = {"episodes": len(eps), "crossed": sum(e["crossed"] for e in eps), "results": eps}
    res.update(complete=True, actions=actions)
    BAT.write_atomic(run_dir() / "summary.json", res)


# -- rollout ------------------------------------------------------------------------------------------------------
@torch.no_grad()
def rollout(cfg):
    from bc2rl import capfit as CF
    project = project_dir()
    lays, idx = group_layouts(project, cfg["panel"])
    out, actions = [], 0
    for ci, c in enumerate(cfg["controllers"]):
        if c["kind"] == "fit":
            actor = CF.load_selected(project, c["job"])
        elif c["kind"] == "bc":
            actor = load_policy(project, {"kind": "bc", "job": c["job"], "update": c["update"]})
        attempts = cfg.get("determinism_attempts", {}).get(c["name"], 0)
        for li, (L, ri) in enumerate(zip(lays, idx)):
            for att in range(1 + (1 if li < attempts else 0)):
                if BAT.flag_path(project).exists():
                    raise SystemExit(BAT.PAUSED_EXIT)
                if c["kind"] == "expert":
                    e, n = expert_episode(L)
                else:
                    e, n = greedy_episode(actor, L)
                actions += n
                e.update(controller=c["name"], layout=ri, item=li, attempt=att)
                out.append(e)
    (run_dir() / "rollouts.jsonl").write_text("".join(json.dumps(r) + "\n" for r in out))
    BAT.write_atomic(run_dir() / "summary.json", {"complete": True, "episodes": len(out), "actions": actions,
                                                  "controllers": [c["name"] for c in cfg["controllers"]]})


def greedy_episode(actor, L):
    env = T.StageTask()
    obs, _ = env.reset(options={"layout": L})
    tr = TR.Tracker(env)
    term, n = False, 0
    while not term and not env.accessed:
        o = {k: obs[k][None] for k in ("grid", "aux", "time")}
        a = int(torch.argmax(actor(*M.obs_to_torch(o, torch.device("cpu"))), -1)[0])
        tr.before(env, a)
        obs, _, term, _, _ = env.step(a)
        tr.after(env)
        n += 1
    return {"crossed": bool(env.accessed), "tau": env.tau, "steps": int(env.step_count),
            "stop": "crossed" if env.accessed else "deadline",
            "end_category": None if env.accessed else CR.category(env), "trace": tr.summary(env)}, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("collect", "validate", "rollout"))
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("capability_" + a.mode)
    torch.set_num_threads(1)
    {"collect": collect, "validate": validate, "rollout": rollout}[a.mode](cfg)


if __name__ == "__main__":
    main()
