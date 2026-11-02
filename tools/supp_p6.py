"""Post-hoc supplementary contrasts for the controller diagnostics (added after outcomes; exploratory; not part of the
Amendment 8 frozen analysis). No actions. Per-layout paired differences between two modified conditions, cohort mean
over the 4 policies with a 95% t interval over layouts (df 63). Also: among base episodes that ended before the
boundary, the shares whose learner actions were dominated by pickups or toggles (descriptive, from action strings).
Output: reports/p6/supplementary.json."""
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_p6 as A    # noqa: E402

PAIRS = [("key_all", "mask_prefix"), ("both_all", "key_all"), ("both_mid", "key_mid"), ("key_mid", "mask_prefix")]


def main():
    out = {"note": "post hoc, exploratory; added after outcomes", "contrasts": {}, "base_prefix_failure_actions": {}}
    c95 = A.t_crit(63)
    for coh, pols in A.CFG["cohorts"].items():
        PL, R = {}, {}
        for p in pols:
            d = A.job_dir(f"p6-ctrl-{p}")
            for c in A.CONDS:
                R[(p, c)] = A.jl(d / f"ctrl_{p}_{c}.jsonl")
                PL[(p, c)] = A.per_layout(R[(p, c)], 64)
        for a, b in PAIRS:
            D = np.mean([PL[(p, a)] - PL[(p, b)] for p in pols], axis=0)
            m, se = D.mean(), D.std(ddof=1) / sqrt(64)
            out["contrasts"][f"{coh}|{a}-{b}"] = {"mean": float(m), "lo": float(m - c95 * se), "hi": float(m + c95 * se)}
        fails = [r for p in pols for r in R[(p, "base")] if r["arrival"] is None]
        dom = {"pickup": 0, "toggle": 0, "forward": 0, "turn": 0, "other": 0}
        for r in fails:
            s = r["actions"]
            cnt = {k: s.count(k) for k in "0123456"}
            top = max(cnt, key=cnt.get)
            dom[{"3": "pickup", "5": "toggle", "2": "forward", "0": "turn", "1": "turn"}.get(top, "other")] += 1
        out["base_prefix_failure_actions"][coh] = {"n": len(fails), "most_frequent_learner_action": dom}
    (ROOT / "reports/p6/supplementary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
