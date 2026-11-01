"""R2 power and precision (PROTOCOL_FREEZE Amendment 4; owner instruction 2026-11-01 section 4). Planning only.

Design: n = 20 paired training seeds, one two-sided paired t-test at alpha 0.05 (df 19) and its 95% interval.
Planning effect 0.03. Seed SD scenarios 0.035, 0.043 (R1), 0.05, 0.06. True effects 0, 0.02, 0.03, 0.04, 0.0453.
Paired seed differences are simulated as (a) normal, (b) scaled Student t with 4 df (heavy tails), and (c) the R1
seed differences, centred and rescaled to the scenario SD and resampled (the R1 shape; not the R1 effect).
The t-test is conditional on the panel; the R1 seed SD already contains panel-by-seed noise at 128 x 4.
Outcomes per scenario (probabilities): positive supported (lower > 0), lower > 0.03, lower > 0.05,
informative null (upper < 0.03), inconclusive (interval includes 0 and 0.03), wrong-sign (upper < 0).
Self-checks: the df-19 quantile; type I error near 0.05 under effect 0; an analytic normal-approximation power for
comparison. No observed R2 effect enters any computation.

Usage: .venv/bin/python tools/power_r2.py -> reports/r2/power.json, reports/r2/power.md
"""
import json
from math import erf, sqrt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/r2"
N, REPS, RNG = 20, 200_000, 20261103
SDS = (0.035, 0.043, 0.05, 0.06)
EFFECTS = (0.0, 0.02, 0.03, 0.04, 0.0453)
R1_D = np.array([0.001953125, 0.025390625, 0.1015625, 0.0859375, 0.03515625, -0.005859375, 0.080078125, -0.001953125])


def phi(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def simulate(kind, mu, sd, rng):
    if kind == "normal":
        x = rng.normal(0, 1, (REPS, N))
    elif kind == "t4":
        x = rng.standard_t(4, (REPS, N)) / sqrt(4 / 2)          # unit variance
    else:
        z = (R1_D - R1_D.mean()) / R1_D.std(ddof=1)
        x = z[rng.integers(0, len(z), (REPS, N))]
    return mu + sd * x


def main():
    q = R.t_quantile_two_sided(0.95, N - 1)
    assert abs(q - 2.093024) < 1e-5, q
    rng = np.random.default_rng(RNG)
    rows = []
    for kind in ("normal", "t4", "r1_shape"):
        for sd in SDS:
            for mu in EFFECTS:
                d = simulate(kind, mu, sd, rng)
                m, se = d.mean(1), d.std(1, ddof=1) / sqrt(N)
                lo, hi = m - q * se, m + q * se
                rows.append({"shape": kind, "sd": sd, "effect": mu,
                             "P_positive_supported": float((lo > 0).mean()), "P_lower_gt_0.03": float((lo > 0.03).mean()),
                             "P_lower_gt_0.05": float((lo > 0.05).mean()), "P_informative_null": float((hi < 0.03).mean()),
                             "P_inconclusive": float(((lo <= 0) & (hi >= 0.03)).mean()), "P_wrong_sign": float((hi < 0).mean()),
                             "normal_approx_power": (1 - phi(1.96 - mu / (sd / sqrt(N))) + phi(-1.96 - mu / (sd / sqrt(N))))
                             if kind == "normal" else None,
                             "expected_halfwidth": float((q * se).mean())})
    t1 = [r["P_positive_supported"] + r["P_wrong_sign"] for r in rows if r["effect"] == 0 and r["shape"] == "normal"]
    assert all(0.04 < x < 0.06 for x in t1), t1
    res = {"n": N, "alpha": 0.05, "df": N - 1, "t975": q, "reps": REPS, "rng": RNG, "rows": rows,
           "type_I_normal": t1, "planning_effect": 0.03,
           "note": "Planning only; no R2 outcome used. R1 shape = R1 seed differences centred and rescaled."}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "power.json").write_text(json.dumps(res, indent=1))
    lines = ["# R2 power and precision (planning; n = 20, one two-sided paired t-test at 0.05)", "",
             f"t(0.975, 19) = {q:.6f}. {REPS:,} simulated studies per cell (RNG {RNG}). Type I error under effect 0 "
             f"(normal): {', '.join(f'{x:.3f}' for x in t1)}.", "",
             "| shape | seed SD | true effect | P(lower > 0) | P(lower > 0.03) | P(lower > 0.05) | P(upper < 0.03) | "
             "P(inconclusive) | mean half-width |", "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['shape']} | {r['sd']} | {r['effect']} | {r['P_positive_supported']:.3f} | "
                     f"{r['P_lower_gt_0.03']:.3f} | {r['P_lower_gt_0.05']:.3f} | {r['P_informative_null']:.3f} | "
                     f"{r['P_inconclusive']:.3f} | {r['expected_halfwidth']:.4f} |")
    (OUT / "power.md").write_text("\n".join(lines) + "\n")
    for r in rows:
        if r["shape"] == "normal" and r["effect"] in (0.03, 0.04):
            print(r["sd"], r["effect"], round(r["P_positive_supported"], 3), round(r["normal_approx_power"], 3),
                  round(r["expected_halfwidth"], 4))
    return res


if __name__ == "__main__":
    main()
