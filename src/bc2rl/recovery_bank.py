"""Held-out recovery-state bank (owner instruction 2026-11-02c, section 8; PROTOCOL_FREEZE Amendment 9).

python -m bc2rl.recovery_bank --config experiments/p7/recov-v1.json

Source states: prefix states visited by fixed frozen policies that take no part in this study (the A4 arm-00 finals of
seeds 70-73, the 2026-11-02b controller cohort) on the held-out layouts of role r7_recov (64 K=3 layouts, one normal
start per policy; actions by inverse-CDF sampling with u = rng([sample_seed, policy index, item]).random(limit)).
Every decision before the boundary is a candidate. Each candidate is labelled with bc2rl.corrective.query and given a
stratum from bc2rl.corrective.category:
  on_track       in the frontier module, empty-handed or holding the frontier key, frontier key not displaced
  wrong_key      in the frontier module, holding an obsolete key or another object
  key_lost       the frontier key is not held and lies away from its layout position
  backtracked    the agent stands west of the frontier module (in an earlier module or on an earlier door cell)
  all_unlocked   every door unlocked, boundary not yet crossed
Only labelled candidates enter; duplicates (same observation) are removed (first kept, in policy, item, step order).
Then up to `per_stratum` states per stratum are drawn without replacement with rng([sample_seed, 1, stratum index]).
The bank is used only for agreement evaluation; its labels never enter training. Every bank label is verified in the
real environment with bc2rl.corrective.check_label (each action executed once from the snapshot). Executed actions
are counted.
Output: data/<bank file> (states with obs, mask, stratum, policy, item, step, snapshot) with its sha256, and
summary.json in the run directory (candidate counts by stratum and status).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import corrective as CR
from bc2rl import diag5
from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import task as T

STRATA = ("on_track", "wrong_key", "key_lost", "backtracked", "all_unlocked")


def stratum(cat):
    if cat.startswith("all_unlocked"):
        return "all_unlocked"
    if cat.startswith("behind"):
        return "backtracked"
    if cat.endswith("_key_displaced"):
        return "key_lost"
    if cat in ("in_module_obsolete_key", "in_module_other_object"):
        return "wrong_key"
    return "on_track"


def _env(snap):
    env = T.StageTask()
    env.reset(options={"snapshot": snap})
    return env


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("recovery_bank")
    torch.set_num_threads(1)
    project = Path(os.environ.get("MAE_PROJECT", "."))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    lay = json.loads((project / "data" / cfg["dataset_id"] / "layouts.json").read_text())[cfg["role"]]
    layouts = [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3][:cfg["n_layouts"]]
    cands, seen, counts, actions = {s: [] for s in STRATA}, set(), {}, 0
    for pi, (name, spec) in enumerate(cfg["policies"].items()):
        actor = diag5.load_policy(project, spec)
        for item, L in enumerate(layouts):
            env = T.StageTask()
            obs, _ = env.reset(options={"layout": L})
            u = np.random.default_rng([cfg["sample_seed"], pi, item]).random(L.limit)
            term = False
            while not term and not env.accessed:
                q = CR.query(env)
                cat = CR.category(env)
                st = stratum(cat)
                counts[f"{st}|{q['status']}"] = counts.get(f"{st}|{q['status']}", 0) + 1
                key = CR.obs_key(obs)
                if q["status"] == "labelled" and key not in seen:
                    seen.add(key)
                    cands[st].append({"obs": {"grid": obs["grid"].tolist(), "aux": obs["aux"].tolist(),
                                              "time": obs["time"].tolist()},
                                      "mask": int(q["mask"]), "plan_len": q["plan_len"], "stratum": st,
                                      "category": cat, "policy": name, "item": item, "step": int(env.step_count),
                                      "snapshot": env.snapshot()})
                o = {k: obs[k][None] for k in ("grid", "aux", "time")}
                p = torch.softmax(actor(*M.obs_to_torch(o, torch.device("cpu"))).float(), -1).numpy().astype(np.float64)
                act = int(E._sample(p, u[env.step_count:env.step_count + 1])[0])
                obs, _, term, _, _ = env.step(act)
                actions += 1
    states = []
    for k, s in enumerate(STRATA):
        c = cands[s]
        pick = sorted(np.random.default_rng([cfg["sample_seed"], 1, k]).choice(len(c), min(len(c), cfg["per_stratum"]),
                                                                             replace=False).tolist()) if c else []
        states += [c[i] for i in pick]
    violations = []
    for x in states:
        b = CR.check_label(x["snapshot"], {"mask": x["mask"], "plan_len": x["plan_len"],
                                           "frontier": CR.frontier(_env(x["snapshot"]))})
        if b:
            violations.append({"stratum": x["stratum"], "policy": x["policy"], "item": x["item"], "step": x["step"],
                               "violations": b})
    body = json.dumps(states, sort_keys=True)
    sha = hashlib.sha256(body.encode()).hexdigest()
    out = project / cfg["bank_path"]
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps({"config": cfg, "sha256": sha, "states": states}))
    os.replace(tmp, out)
    BAT.write_atomic(run_dir / "summary.json", {
        "complete": True, "bank_path": cfg["bank_path"], "sha256": sha, "n_states": len(states),
        "by_stratum": {s: sum(1 for x in states if x["stratum"] == s) for s in STRATA},
        "candidates_labelled_unique": {s: len(cands[s]) for s in STRATA}, "candidate_status": counts,
        "label_check": {"states": len(states), "with_violations": len(violations), "examples": violations[:20]},
        "rollout_actions": actions})


if __name__ == "__main__":
    main()
