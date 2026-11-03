"""Verification replay of evaluation episodes (owner instruction 2026-11-02c, section 10; Amendment 9). Reserve
spending. Executes environment actions (counted).

python -m bc2rl.eval_replay --config experiments/p7/verify-v1.json

For every complete branch of this study (development p7-K3-s<S>-<arm>; confirmation c7-K3-s<S>-<arm> when present),
`per_branch` normal-start episodes of the 501,760 evaluation are chosen by
rng([verify_seed, seed, arm index]).choice(n rows, per_branch, replace=False) from the rows sorted by (item, attempt).
Each is re-executed with this module's own loop: the saved actor (state_501760.pt, hash checked against the
branch summary) on CPU with batch 1, the layout from the branch's evaluation role, and inverse-CDF sampling from
u = rng([eval_seed, item, attempt]) drawn one value per step (the evaluator's common random numbers). No planner,
mask or auxiliary source is loaded. Recorded success, end step and boundary time are compared; policy-sampling
mismatches are reported with the distance of u to the nearest CDF boundary (the branch evaluated on MPS; CPU
floating point may differ near a boundary). Writes replay.jsonl and summary.json ("complete": true).
"""
import argparse
import json
import os
from pathlib import Path

import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import model as M
from bc2rl import ppo as PP
from bc2rl import task as T

ARMS = ("00", "C7", "R7")


def branches(project):
    out = []
    for prefix in ("p7", "c7"):
        for d in sorted((project / ".mae/runs").glob(f"*/{prefix}-K3-s*")):
            s = d / "summary.json"
            if s.exists() and json.loads(s.read_text()).get("continuation_actions") == 501_760:
                out.append(d)
    return out


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("eval_replay")
    torch.set_num_threads(1)
    project = Path(os.environ.get("MAE_PROJECT", "."))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    res, n_actions = [], 0
    for d in branches(project):
        if BAT.flag_path(project).exists():
            raise SystemExit(BAT.PAUSED_EXIT)
        sm = json.loads((d / "summary.json").read_text())
        rc = json.loads((d / "config.resolved.json").read_text())
        saved = torch.load(d / "state_501760.pt", map_location="cpu", weights_only=False)
        assert PP.state_hash(saved["state"]) == saved["hash"] == sm["state_hashes"]["501760"], f"{d}: state hash"
        actor = M.Actor()
        actor.load_state_dict(saved["state"]["actor"])
        actor.eval()
        lay = json.loads((project / "data" / rc["dataset_id"] / "layouts.json").read_text())[rc["eval_role"]]
        layouts = [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3]
        tag = [e["tag"] for e in rc["eval_schedule"] if e["at"] == 501_760][0]
        rows = sorted((json.loads(l) for l in (d / f"attempts_{tag}.jsonl").read_text().splitlines() if l.strip()),
                      key=lambda r: (r["item"], r["attempt"]))
        rows = [r for r in rows if r["kind"] == "normal"]
        pick = np.random.default_rng([cfg["verify_seed"], sm["seed"], ARMS.index(sm["arm"])]).choice(
            len(rows), cfg["per_branch"], replace=False)
        for k in sorted(int(x) for x in pick):
            r = rows[k]
            env = T.StageTask()
            obs, _ = env.reset(options={"layout": layouts[r["item"]]})
            rng = np.random.default_rng([rc["eval_seed"], r["item"], r["attempt"]])
            term, info, near, tau = False, {}, [], None
            while not term:
                o = {x: obs[x][None] for x in ("grid", "aux", "time")}
                p = torch.softmax(actor(*M.obs_to_torch(o, torch.device("cpu"))).float(), -1).numpy()[0].astype(np.float64)
                c = np.cumsum(p)
                c[-1] = 1.0
                u = rng.random()
                near.append(float(np.min(np.abs(c - u))))
                obs, _, term, _, info = env.step(int((u > c).sum()))
                n_actions += 1
                if info["crossed"]:
                    tau = info["tau"]
            out = {"branch": d.name, "seed": sm["seed"], "arm": sm["arm"], "item": r["item"], "attempt": r["attempt"],
                   "success": bool(info["success"]), "end_step": int(info["step_count"]), "tau": tau,
                   "min_cdf_distance": min(near)}
            out["matches_record"] = (out["success"] == r["success"] and out["end_step"] == r["end_step"]
                                     and out["tau"] == r["tau"])
            res.append(out)
    (run_dir / "replay.jsonl").write_text("".join(json.dumps(r) + "\n" for r in res))
    BAT.write_atomic(run_dir / "summary.json", {
        "mode": "eval_replay", "complete": True, "branches": len(branches(project)), "episodes": len(res),
        "actions": n_actions, "mismatches": sum(not r["matches_record"] for r in res),
        "mismatch_min_cdf_distance": [r["min_cdf_distance"] for r in res if not r["matches_record"]]})


if __name__ == "__main__":
    main()
