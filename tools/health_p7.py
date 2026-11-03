"""Execution-health summary of 2026-11-02c branches (Amendment 9). Prints no success outcomes. No actions.

Usage: .venv/bin/python tools/health_p7.py PREFIX SEED     (PREFIX p7 or c7)
For each arm: updates, raw PPO approx KL / clip fraction / entropy / actor grad norm (mean and max), auxiliary CE,
auxiliary and PPO gradient norms on the first supervised minibatch, label argmax agreement, examples per update,
query counts, failures by status, observation conflicts, planner seconds and wall time.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main():
    prefix, seed = sys.argv[1], sys.argv[2]
    for arm in ("00", "C7", "R7"):
        ds = sorted((ROOT / ".mae/runs").glob(f"*/{prefix}-K3-s{seed}-{arm}"))
        if not ds:
            print(arm, "missing")
            continue
        d = ds[-1]
        recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
        upd = [r for r in recs if r.get("phase") == "branch"]
        out = {"arm": arm, "dir": d.parent.name, "updates": len(upd), "complete": (d / "summary.json").exists()}
        for k in ("approx_kl", "clipfrac", "entropy", "grad_norm_actor", "aux_ce", "aux_grad_norm", "pg_grad_norm",
                  "aux_label_argmax", "aux_n", "update_kl_prefix", "update_kl_suffix"):
            v = [r[k] for r in upd if r.get(k) is not None]
            if v:
                out[k] = [round(float(np.mean(v)), 5), round(float(np.max(v)), 5)]
        if out["complete"]:
            s = json.loads((d / "summary.json").read_text())
            out["wall_s"] = round(s["wall_seconds"])
            ax = s.get("aux")
            if ax:
                out["aux"] = {k: ax[k] for k in ax if k not in ("planner",)}
                if "planner" in ax:
                    out["planner"] = {k: ax["planner"][k] for k in ("status", "reasons", "failed_categories",
                                                                    "label_sizes", "planner_seconds")}
        print(json.dumps(out))


if __name__ == "__main__":
    main()
