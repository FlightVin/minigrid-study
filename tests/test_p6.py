"""Controller semantics (owner instruction 2026-11-02b; Amendment 8): physical mask, helpers, fallbacks, clocks,
common random numbers, budget interruption and pause."""
import json
import os
from pathlib import Path
import sys

import numpy as np
import pytest
import torch

from bc2rl import battery as BAT
from bc2rl import controller as C
from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import suffix_cert as SC
from bc2rl import task as T

ROOT = Path(__file__).resolve().parents[1]


def planned(seed=11):
    L = T.generate_layout(3, seed)
    lay, rec = P.plan_and_verify(L, seed, 24, 80)
    return lay, rec


def env_at(lay):
    env = T.StageTask()
    env.reset(options={"layout": lay})
    return env


def face(env, pos, d):
    env.agent_pos, env.agent_dir = tuple(pos), d


def test_mask_edge_cases():
    lay, _ = planned()
    env = env_at(lay)
    j = 0
    dc = C.door_cell(lay, j)
    # facing the locked door from the cell to its left, nothing carried
    face(env, (dc[0] - 1, dc[1]), 0)
    m = C.physical_mask(env)
    assert m[C.LEFT] and m[C.RIGHT] and not m[C.FORWARD] and not m[C.TOGGLE] and not m[C.PICKUP]
    assert not m[C.DROP] and not m[C.DONE]
    env.carrying = T.Key("blue")                       # wrong colour: toggle has no effect
    assert not C.physical_mask(env)[C.TOGGLE]
    env.carrying = T.Key(lay.colors()[j])               # matching key: toggle unlocks
    m = C.physical_mask(env)
    assert m[C.TOGGLE] and not m[C.DROP]                # the door blocks the drop cell
    env.grid.get(*dc).is_locked, env.grid.get(*dc).is_open = False, True
    m = C.physical_mask(env)
    assert m[C.FORWARD] and m[C.TOGGLE]                 # open door: pass or close
    # facing a key (wrong colour pickups stay available)
    kx, ky = lay.key_pos[1]
    env.carrying = None
    env.grid.set(kx, ky, None)
    env.grid.set(dc[0] - 1, (dc[1] % 7) + 1, None)
    x, y = dc[0] - 1, dc[1]
    env.grid.set(x, y + 1 if y < 7 else y - 1, T.Key("yellow"))
    face(env, (x, y), 1 if y < 7 else 3)
    m = C.physical_mask(env)
    assert m[C.PICKUP] and not m[C.FORWARD] and not m[C.DROP]
    env.carrying = T.Key("red")
    m = C.physical_mask(env)
    assert not m[C.PICKUP] and not m[C.DROP]
    # facing a wall
    face(env, (T.SLOT_X0[0], 1), 3)
    m = C.physical_mask(env)
    assert not m[C.FORWARD] and m.sum() >= 2


def test_masked_probs():
    p = np.array([0.1, 0.1, 0.5, 0.1, 0.1, 0.05, 0.05])
    m = np.array([1, 1, 0, 0, 0, 0, 0], bool)
    q, removed = C.masked_probs(p, m)
    assert np.isclose(q.sum(), 1) and np.allclose(q[:2], 0.5) and np.isclose(removed, 0.8)
    q, removed = C.masked_probs(np.array([0, 0, 1.0, 0, 0, 0, 0]), m)
    assert np.allclose(q[:2], 0.5) and np.isclose(removed, 1.0)


def run_helper(env, plan):
    for a in plan:
        _, _, term, _, info = env.step(a)
        assert not term
    return info


def test_key_plan_with_inventory_change():
    lay, rec = planned()
    env = env_at(lay)
    plan, why = C.plan_key(env, 0)
    assert why == "planned" and C.lb_key(env, 0) <= len(plan)
    run_helper(env, plan)
    assert C.holds_key(env, 0)
    # walk the planner to the first cell of module 1 carrying the red key; KA must drop it and pick blue
    env = env_at(lay)
    for a in rec["actions"]:
        env.step(a)
        if C.module_of(env) == 1:
            break
    if env.carrying is None:                             # the planner may have dropped it in module 0
        env.carrying = T.Key("red")
        env.carrying.cur_pos = np.array([-1, -1])
    plan, why = C.plan_key(env, 1)
    assert C.DROP in plan and C.PICKUP in plan
    run_helper(env, plan)
    assert C.holds_key(env, 1)


def test_door_plan_locked_and_already_open():
    lay, _ = planned()
    env = env_at(lay)
    run_helper(env, C.plan_key(env, 0)[0])
    plan, _ = C.plan_door(env, 0)
    assert C.TOGGLE in plan and C.lb_door(env, 0) <= len(plan)
    run_helper(env, plan)
    dc = C.door_cell(lay, 0)
    assert tuple(env.agent_pos) == (dc[0] + 1, dc[1]) and env.grid.get(*dc).is_open
    # already open: back into module 0, then the plan passes without toggling
    env2 = env_at(lay)
    run_helper(env2, C.plan_key(env2, 0)[0])
    env2.grid.get(*dc).is_locked, env2.grid.get(*dc).is_open = False, True
    plan2, _ = C.plan_door(env2, 0)
    assert C.TOGGLE not in plan2
    run_helper(env2, plan2)
    assert tuple(env2.agent_pos) == (dc[0] + 1, dc[1])


def test_unavailable_and_impossible_assistance():
    lay, _ = planned()
    ep = C.Episode(lay, 0, 0, 1, "key_all")
    kx, ky = lay.key_pos[0]
    ep.env.grid.set(kx, ky, None)                        # key absent: no plan, bound infinite -> impossible
    assert not ep.decide()
    a = ep.assists[-1]
    assert a["status"] == "certified_impossible" and a["reason"] == "module key not in module"
    for s in range(12, 40):                              # a layout whose start does not already face the key
        lay = planned(s)[0]
        ep = C.Episode(lay, 0, 0, 1, "key_all")
        lb = C.lb_key(ep.env, 0)
        if lb >= 3:
            break
    assert lb >= 3
    ep.env.step_count = lay.limit - (lb - 1)             # remaining one less than the bound
    assert not ep.decide()
    assert ep.assists[-1]["status"] == "certified_impossible"
    ep = C.Episode(lay, 0, 0, 1, "key_all")              # unresolved: the key is walled in, the bound ignores walls?
    plan, _ = C.plan_key(ep.env, 0)
    ep.env.step_count = lay.limit - (len(plan) - 1)      # plan one step too long, bound may still fit
    ep.decide()
    st = ep.assists[-1]
    assert st["status"] in ("unresolved", "certified_impossible") and not ep.queue
    assert (st["status"] == "unresolved") == (st["lb"] <= st["remaining"])


def test_final_step_arrival_by_helper():
    lay, rec = planned()
    env = env_at(lay)
    ep = C.Episode(lay, 0, 0, 1, "door_all")
    for a in rec["actions"]:                             # drive the planner into module 2 holding the yellow key
        if C.module_of(ep.env) == 2 and C.holds_key(ep.env, 2):
            break
        ep.step(a, "p")
    plan, _ = C.plan_door(ep.env, 2)
    ep.env.step_count = lay.limit - len(plan)           # exactly enough time: the last helper action crosses
    ep.da_done = {0, 1}
    assert ep.decide()
    term = False
    while not term:
        term = ep.step(ep.queue[0], "d")
    assert ep.rec["arrival"]["remaining"] == 0 and ep.rec["arrival"]["helper_cross"]
    assert ep.rec["timeout"] and ep.assists[-1]["ok"] and ep.assists[-1]["n_exec"] == len(plan)
    c = SC.certify(ep.snapshot)
    assert c["status"] == "impossible" and c["replay_actions"] == 0


def tiny_actor(seed=0):
    torch.manual_seed(seed)
    a = M.Actor()
    a.eval()
    return a


def test_base_reproduces_evaluate_and_crn():
    lays = [planned(s)[0] for s in (11, 12)]
    actor = tiny_actor()
    ref, _ = E.run_attempts(actor, [("layout", L) for L in lays], 1, 77, torch.device("cpu"))
    rows, n, parts = C.run_unit(actor, lays, 1, 77, "base", torch.device("cpu"))
    for a, b in zip(ref, rows):
        assert (a["success"], a["end_step"], a["tau"]) == (b["success"], b["end_step"], b["tau"])
    assert n == sum(r["end_step"] for r in rows) + parts["certification"]
    # helpers draw no random numbers: before the first helper action, key_all and base choose identical actions
    rows2, _, _ = C.run_unit(actor, lays, 1, 77, "door_all", torch.device("cpu"))
    for a, b in zip(rows, rows2):
        k = b["who"].find("d")
        k = len(b["who"]) if k < 0 else k
        assert a["actions"][:k] == b["actions"][:k]
        # after the helper, policy steps use u[t] by absolute step: recompute nothing here, but steps must match clock
        assert len(b["actions"]) == b["end_step"] and len(b["who"]) == b["end_step"]


def test_mask_condition_records_and_respects_mask():
    lays = [planned(s)[0] for s in (11, 12)]
    rows, _, _ = C.run_unit(tiny_actor(1), lays, 1, 5, "mask_prefix", torch.device("cpu"))
    for r in rows:
        c = r["counts"]
        assert c["learner_ineffective_prefix"] == 0 and c["mask_steps"] > 0 and 0 <= c["mask_removed_max"] <= 1


def _main(tmp_path, monkeypatch, extra, flag=False, existing=()):
    proj = tmp_path / "proj"
    (proj / "data").mkdir(parents=True)
    os.symlink(ROOT / "data/r6-v1", proj / "data/r6-v1")
    if flag:
        BAT.set_pause({"reason": "test"}, proj)
    run = tmp_path / "run"
    run.mkdir()
    for e in existing:
        (run / e).write_text("")
    cfg = {"dataset_id": "r6-v1", "role": "d6_ctrl", "n_layouts": 2, "attempts": 1, "eval_seed": 3,
           "conditions": ["base", "key_mid"], "policies": {"rand": {"kind": "test"}}}
    (tmp_path / "c.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("MAE_PROJECT", str(proj))
    monkeypatch.setenv("MAE_RUN_DIR", str(run))
    monkeypatch.setattr(C, "load_actor", lambda project, spec: tiny_actor())
    monkeypatch.setattr(BAT, "require_admission", lambda what: None)
    monkeypatch.setattr(sys, "argv", ["x", "--config", str(tmp_path / "c.json"), "--policy", "rand", *extra])
    code = 0
    try:
        C.main()
    except SystemExit as e:
        code = e.code
    return code, json.loads((run / "summary.json").read_text()), run


def test_budget_interruption(tmp_path, monkeypatch):
    code, s, run = _main(tmp_path, monkeypatch, ["--cap", "10"])
    assert code == 5 and s["stopped"] == "action cap" and not s["complete"] and s["actions_total"] == 0
    assert not list(run.glob("ctrl_*.jsonl"))


def test_pause_flag_and_resume(tmp_path, monkeypatch):
    code, s, _ = _main(tmp_path, monkeypatch, [], flag=True)
    assert code == BAT.PAUSED_EXIT and s["stopped"] == "pause" and not s["complete"]


def test_resume_skips_completed_units(tmp_path, monkeypatch):
    code, s, run = _main(tmp_path, monkeypatch, [], existing=("ctrl_rand_base.jsonl",))
    assert code == 0 and s["units"]["ctrl_rand_base.jsonl"] == {"skipped_existing": True} and s["complete"]
    assert len((run / "ctrl_rand_key_mid.jsonl").read_text().splitlines()) == 2


def test_replay_reproduces_controller_rows():
    from bc2rl import ctrl_replay as R
    lays = [planned(s)[0] for s in (11, 12, 13)]
    actor = tiny_actor(2)
    for cond in ("both_all", "mask_prefix", "key_all"):
        rows, _, _ = C.run_unit(actor, lays, 1, 9, cond, torch.device("cpu"))
        for r in rows:
            r.update(policy="t", condition=cond)
            out, n = R.replay(actor, lays[r["item"]], r, 9, cond == "mask_prefix")
            assert out["matches_record"] and out["helper_checks_ok"] and out.get("cert_matches", True)
            assert out["policy_mismatches"] == 0 and n >= r["end_step"]
    env = env_at(lays[0])
    rng = np.random.default_rng(0)
    for _ in range(300):
        m = C.physical_mask(env)
        assert all(m[b] == R.effective(env, b) for b in range(7))
        a = int(rng.integers(7))
        _, _, term, _, _ = env.step(a)
        if term:
            break


def test_key_helper_keeps_door_fronts_free():
    for s in range(11, 31):
        lay, rec = planned(s)
        env = env_at(lay)
        for a in rec["actions"]:
            env.step(a)
            if C.module_of(env) == 1:
                break
        if env.carrying is None:
            env.carrying = T.Key("red")
            env.carrying.cur_pos = np.array([-1, -1])
        plan, _ = C.plan_key(env, 1)
        run_helper(env, plan)
        x0 = T.SLOT_X0[lay.active_slots()[1]]
        assert env.grid.get(x0 + 2, lay.door_rows[1]) is None and env.grid.get(x0, lay.door_rows[0]) is None
        assert C.plan_door(env, 1)[0] is not None
