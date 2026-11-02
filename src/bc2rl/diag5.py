"""Failure diagnostics and assisted evaluation references on frozen A4 ordinary-PPO checkpoints
(owner instruction 2026-11-02, section 3; PROTOCOL_FREEZE Amendment 7). No training.

python -m bc2rl.diag5 --config experiments/p5/diag-v1.json

Policies (fixed rule, not performance): A4 seeds 70-73, arm 00, at the post-probe fork (probe fork.pt, hash checked
against the probe summary) and at the final state (state_1001472.pt, hash checked against the branch summary).
Layouts: the d5_trace K=3 layouts (separate from every A4 role). For each policy:
  normal  : attempts x traced normal starts (bc2rl.trace), eval seed S; every actual arrival is captured and
            certified (bc2rl.suffix_cert): reference 2 = learned prefix, then the validated planner attempts the suffix
            from the actual arrival state with the remaining time (feasible / impossible / unresolved; the planner
            replay of feasible arrivals is executed and counted).
  ref1    : reference 1 = the planner executes the prefix (once per layout; shared by all policies, counted once),
            then the frozen policy executes the suffix from the planner's arrival state, original clock, attempts x,
            eval seed S + 1.
No clock refresh, no reward change. Both references are diagnostic conditions, not normal-start performance;
reference 1 changes the arrival state and timing and is not an upper bound.
Outputs: attempts_<policy>_{normal,ref1}.jsonl, summary.json (actions by role).
"""
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import ppo as PP
from bc2rl import suffix_cert as SC
from bc2rl import task as T
from bc2rl.telemetry import Heartbeat, resource_heartbeat


def load_policy(project, spec):
    runs = project / ".mae/runs"
    if spec["kind"] == "probe":
        d = runs / spec["run"]
        st = torch.load(d / "fork.pt", map_location="cpu", weights_only=False)
        assert PP.state_hash(st) == json.loads((d / "summary.json").read_text())["fork_hash"], "fork hash"
        actor_state = st["actor"]
    else:
        d = runs / spec["run"]
        saved = torch.load(d / f"state_{spec['at']}.pt", map_location="cpu", weights_only=False)
        assert PP.state_hash(saved["state"]) == saved["hash"] == json.loads((d / "summary.json").read_text())["state_hashes"][str(spec["at"])]
        actor_state = saved["state"]["actor"]
    a = M.Actor()
    a.load_state_dict(actor_state)
    a.eval()
    return a


def planner_entries(layouts, items):
    """Reference 1 starts: replay the planner's prefix in the real env; snapshot at the first crossing."""
    env, out, n = T.StageTask(), [], 0
    for L, it in zip(layouts, items):
        acts, tau = P.plan(L, it["planner_seed"])
        assert tau == it["tau"]
        env.reset(options={"layout": L})
        for a in acts[:tau]:
            _, _, term, _, info = env.step(a)
            n += 1
            assert not term
        assert info["crossed"] and env.step_count == tau
        out.append(env.snapshot())
    return out, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("diag5")
    project = Path(os.environ.get("MAE_PROJECT", "."))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    device = torch.device(os.environ.get("MAE_DEVICE", "cpu"))
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))
    lay = json.loads((project / "data" / cfg["dataset_id"] / "layouts.json").read_text())[cfg["role"]]
    items = [it for it in lay if it["layout"]["K"] == 3]
    layouts = [T.Layout.from_dict(it["layout"]) for it in items]
    assert len(layouts) == cfg["n_layouts"]
    actions = {"planner_prefix": 0, "normal": 0, "certification": 0, "ref1": 0}
    last = [time.time()]

    def hb():
        if time.time() - last[0] > 5:
            resource_heartbeat()
            last[0] = time.time()

    out = {"policies": {}}
    t0 = time.time()
    with Heartbeat(interval=5):
        entries, actions["planner_prefix"] = planner_entries(layouts, items)
        for name, spec in cfg["policies"].items():
            actor = load_policy(project, spec).to(device)
            res, n = E.run_attempts(actor, [("layout", L) for L in layouts], cfg["attempts"], cfg["eval_seed"], device,
                                    heartbeat=hb, capture=True, trace=True)
            actions["normal"] += n
            for r in res:
                if r["arrival"] is not None:
                    c = SC.certify(r["arrival"].pop("snapshot"))
                    actions["certification"] += c["replay_actions"]
                    r["arrival"]["cert"] = c
            r1, n1 = E.run_attempts(actor, [("snapshot", s) for s in entries], cfg["attempts"], cfg["eval_seed"] + 1,
                                    device, heartbeat=hb, trace=True)
            actions["ref1"] += n1
            for tag, rows in (("normal", res), ("ref1", r1)):
                tmp = run_dir / f"attempts_{name}_{tag}.jsonl.tmp"
                tmp.write_text("".join(json.dumps(r) + "\n" for r in rows))
                os.replace(tmp, run_dir / f"attempts_{name}_{tag}.jsonl")
            out["policies"][name] = {"spec": spec, "normal_P1": float(np.mean([r["success"] for r in res])),
                                     "ref1_P1": float(np.mean([r["success"] for r in r1]))}
            print(json.dumps({"policy": name, **out["policies"][name]}), flush=True)
    BAT.write_atomic(run_dir / "summary.json", {"mode": "diag5", **out, "actions": actions,
                                                "wall_seconds": time.time() - t0, "config": cfg})


if __name__ == "__main__":
    main()
