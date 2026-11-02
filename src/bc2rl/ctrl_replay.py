"""Verification replay of a predetermined sample of controller episodes (owner instruction 2026-11-02b, section 9;
Amendment 8). Executes environment actions (counted).

python -m bc2rl.ctrl_replay --config experiments/p6/ctrl-v1.json

Sample (fixed before outcomes): for every (policy, condition) cell, `verify_sample_per_cell` episodes chosen by
rng([verify_seed, policy index, condition index]).choice(n_episodes) from the rows sorted by (item, attempt).
For each sampled episode, a fresh StageTask is reset from the frozen panel and the recorded action string is executed
step by step with its own loop (no code from bc2rl.controller's episode loop):
  - policy steps: the frozen policy is re-run on the single observation (CPU, batch 1); the action is re-derived from
    u[t] = rng([eval_seed, item, attempt]).random(limit)[t] with inverse-CDF sampling, after this module's own
    effect rules when the condition masks the prefix; mismatches are counted, with the distance of u[t] to the nearest
    CDF boundary (floating-point ties are reported, not hidden);
  - helper steps: executed as recorded; afterwards each recorded helper's claimed result is re-checked;
  - outcome, boundary time, end step and remaining time at arrival are recomputed; the arrival is re-certified with
    bc2rl.suffix_cert (shared code: not an independent check of certification).
The effect rules here restate MiniGrid's step semantics by object type; they share that upstream definition with
bc2rl.controller.physical_mask but not its code.
Writes replay.jsonl and summary.json ("complete": true when every sampled episode was replayed).
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import diag5
from bc2rl import model as M
from bc2rl import suffix_cert as SC
from bc2rl import task as T


def effective(env, a):
    """Does action a change the world under MiniGrid semantics? (own restatement)"""
    if a in (0, 1):
        return True
    if a == 6:
        return False
    fx, fy = env.front_pos
    obj = env.grid.get(fx, fy)
    held = env.carrying
    if a == 2:
        return obj is None or obj.type == "floor" or (obj.type == "door" and obj.is_open)
    if a == 3:
        return held is None and obj is not None and obj.type in ("key", "ball")
    if a == 4:
        return held is not None and obj is None
    if obj is None or obj.type != "door":
        return False
    if obj.is_locked:
        return held is not None and held.type == "key" and held.color == obj.color
    return True


def find_rows(project, name, cond):
    hits = [p for p in sorted((project / ".mae/runs").glob(f"*/p6-ctrl-{name}/ctrl_{name}_{cond}.jsonl"))]
    assert len(hits) == 1, (name, cond, hits)
    return [json.loads(l) for l in hits[0].read_text().splitlines() if l.strip()]


@torch.no_grad()
def replay(actor, layout, row, eval_seed, mask_prefix):
    env = T.StageTask()
    obs, _ = env.reset(options={"layout": layout})
    u = np.random.default_rng([eval_seed, row["item"], row["attempt"]]).random(layout.limit)
    mism, near, arrival = 0, [], None
    info = {}
    helpers = [x for x in row["assists"] if x["status"] == "assisted"]
    runs, helper_checks = [], []
    for t, w in enumerate(row["who"]):
        if w != "p" and (t == 0 or row["who"][t - 1] != w):
            runs.append([w, t, t])
        elif w != "p":
            runs[-1][2] = t
    assert len(runs) == len(helpers), "helper segments do not match recorded activations"
    run_end = {r[2]: (r[0], h) for r, h in zip(runs, helpers)}
    for t, (ch, who) in enumerate(zip(row["actions"], row["who"])):
        a = int(ch)
        if who == "p":
            o = {k: obs[k][None] for k in ("grid", "aux", "time")}
            p = torch.softmax(actor(*M.obs_to_torch(o, torch.device("cpu"))).float(), -1).numpy()[0].astype(np.float64)
            if mask_prefix and not env.accessed:
                ok = np.array([effective(env, b) for b in range(7)])
                p = p * ok
                p = p / p.sum() if p.sum() > 1e-12 else ok / ok.sum()
            c = np.cumsum(p)
            c[-1] = 1.0
            b = int((u[env.step_count] > c).sum())
            if b != a:
                mism += 1
                near.append(float(np.min(np.abs(c - u[env.step_count]))))
        obs, _, term, _, info = env.step(a)
        if t in run_end:
            kind, h = run_end[t]
            j = h["m"]
            if kind == "k":
                c = env.carrying
                ok = c is not None and c.type == "key" and c.color == layout.colors()[j]
            else:
                s = layout.active_slots()[j]
                ok = (int(env.agent_pos[0]), int(env.agent_pos[1])) == (T.DOOR_X[s] + 1, layout.door_rows[j])
            helper_checks.append(ok == bool(h.get("ok")) and (kind == "k") == (h["type"] == "ka"))
        if info["crossed"]:
            arrival = {"tau": info["tau"], "remaining": info["remaining"], "snapshot": env.snapshot()}
        if term:
            assert t == len(row["actions"]) - 1, "episode ended before the recorded actions"
    out = {"policy": row["policy"], "condition": row["condition"], "item": row["item"], "attempt": row["attempt"],
           "steps": len(row["actions"]), "policy_steps": row["who"].count("p"), "policy_mismatches": mism,
           "helper_checks_ok": all(helper_checks), "helper_segments": len(helper_checks), "mismatch_cdf_distance": near,
           "success": bool(info.get("success")), "end_step": int(env.step_count),
           "tau": None if arrival is None else arrival["tau"],
           "remaining_at_arrival": None if arrival is None else arrival["remaining"]}
    out["matches_record"] = (out["success"] == row["success"] and out["end_step"] == row["end_step"]
                             and out["tau"] == row["tau"]
                             and out["remaining_at_arrival"] == (row["arrival"] or {}).get("remaining"))
    cert_actions = 0
    if arrival is not None:
        c = SC.certify(arrival["snapshot"])
        cert_actions = c["replay_actions"]
        out["cert_status"] = c["status"]
        out["cert_matches"] = c["status"] == row["arrival"]["cert"]["status"]
    return out, len(row["actions"]) + cert_actions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("ctrl_replay")
    project = Path(os.environ.get("MAE_PROJECT", "."))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    torch.set_num_threads(1)
    items = [it for it in json.loads((project / "data" / cfg["dataset_id"] / "layouts.json").read_text())[cfg["role"]]
             if it["layout"]["K"] == 3][:cfg["n_layouts"]]
    layouts = [T.Layout.from_dict(it["layout"]) for it in items]
    res, n_actions = [], 0
    for pi, (name, spec) in enumerate(cfg["policies"].items()):
        if BAT.flag_path(project).exists():
            raise SystemExit(BAT.PAUSED_EXIT)
        actor = diag5.load_policy(project, spec)
        for ci, cond in enumerate(cfg["conditions"]):
            rows = sorted(find_rows(project, name, cond), key=lambda r: (r["item"], r["attempt"]))
            pick = np.random.default_rng([cfg["verify_seed"], pi, ci]).choice(len(rows), cfg["verify_sample_per_cell"],
                                                                               replace=False)
            for k in sorted(int(x) for x in pick):
                r = rows[k]
                out, n = replay(actor, layouts[r["item"]], r, cfg["eval_seed"], cond == "mask_prefix")
                n_actions += n
                res.append(out)
    (run_dir / "replay.jsonl").write_text("".join(json.dumps(r) + "\n" for r in res))
    expected = len(cfg["policies"]) * len(cfg["conditions"]) * cfg["verify_sample_per_cell"]
    BAT.write_atomic(run_dir / "summary.json", {
        "mode": "ctrl_replay", "complete": len(res) == expected, "episodes": len(res), "actions": n_actions,
        "outcome_mismatches": sum(not r["matches_record"] for r in res),
        "cert_mismatches": sum(not r.get("cert_matches", True) for r in res),
        "policy_action_mismatches": sum(r["policy_mismatches"] for r in res),
        "helper_check_failures": sum(not r["helper_checks_ok"] for r in res),
        "policy_steps": sum(r["policy_steps"] for r in res)})


if __name__ == "__main__":
    main()
