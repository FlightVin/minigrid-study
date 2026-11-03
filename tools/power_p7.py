"""Power of the frozen confirmation tests (owner instruction 2026-11-02c, section 7; Amendment 9). No actions.
Two-sided paired t-test at 0.05 over n = 20 seeds; planning scenarios for the paired seed SD 0.03, 0.045, 0.06 (the
2026-11-02 pilot's paired SDs were 0.023-0.041 on 6 seeds; these are scenarios, not guarantees for a new
intervention). Monte Carlo with normal paired differences. The fixed-sequence second test (C-R) has the same power
function, applied only after C-A is rejected.
Output: reports/p7/power.json and power.md."""
import json
from pathlib import Path

import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analyze_p6 import t_crit    # noqa: E402  (Simpson-integrated Student t; no scipy in the lock)
REPS = 400_000
N, ALPHA = 20, 0.05
SDS = (0.03, 0.045, 0.06)
EFFECTS = (0.02, 0.03, 0.05, 0.08)


C = t_crit(N - 1)
_Z = np.random.default_rng(20261102).standard_normal((REPS, N))
_T0 = None


def power(delta, sd, n=N):
    """Monte Carlo (400,000 fixed normal samples, common across cells): P(|t| > t_crit) for normal differences."""
    d = delta + sd * _Z
    t = d.mean(1) / (d.std(1, ddof=1) / n ** 0.5)
    return float((np.abs(t) > C).mean())


def mde(sd, target=0.8):
    lo, hi = 0.0, 0.5
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if power(m, sd) < target else (lo, m)
    return hi


def main():
    out = {"n": N, "alpha": ALPHA, "power": {f"sd={s}": {f"delta={d}": power(d, s) for d in EFFECTS} for s in SDS},
           "mde_80": {f"sd={s}": mde(s) for s in SDS},
           "ci_halfwidth_expected": {f"sd={s}": float(C * s / N ** 0.5) for s in SDS}}
    md = ["# Confirmation power (n = 20 paired seeds, two-sided 0.05)", "",
          "| Paired seed SD | " + " | ".join(f"power at +{d:.2f}" for d in EFFECTS) + " | 80% MDE | expected 95% CI half-width |",
          "|---|" + "---|" * (len(EFFECTS) + 2)]
    for s in SDS:
        k = f"sd={s}"
        md.append(f"| {s} | " + " | ".join(f"{out['power'][k][f'delta={d}']:.2f}" for d in EFFECTS)
                  + f" | {out['mde_80'][k]:.3f} | {out['ci_halfwidth_expected'][k]:.3f} |")
    md += ["", "Scenarios only. Twenty seeds do not guarantee resolution of a +0.03 effect: at SD 0.06 power is "
           f"{out['power']['sd=0.06']['delta=0.03']:.2f}."]
    (ROOT / "reports/p7/power.json").write_text(json.dumps(out, indent=1))
    (ROOT / "reports/p7/power.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
