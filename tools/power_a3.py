"""A3 precision planning (PROTOCOL_FREEZE Amendment 5; owner instruction 2026-11-01 section 6). Planning only.

Design: n = 24 paired training seeds; H1 = one two-sided paired t-test at alpha 0.05 (df 23) and its 95% interval;
gatekeeping to H2a/H2b (Holm over two) only if H1 is supported. Seed SD scenarios 0.03, 0.05, 0.07, 0.08 (the
three-seed E2 SD of ~0.008 is not used). True H1 effects 0, 0.02, 0.03, 0.04, 0.055 (0.055 = the E2 exploratory
point estimate, which is likely inflated). Paired differences simulated as normal and as scaled t(4) (heavy tails).
Outcomes: P(H1 supported) = P(lower > 0); P(upper < 0.03); expected 95% half-width. Joint gate power for H2a is
reported for one scenario family: H1 effect delta1 and C - D effect delta2 with the same SD and correlation 0.5
between the two paired differences (both measured against shared arms). No observed A3 outcome enters this file.

Usage: .venv/bin/python tools/power_a3.py -> reports/a3/power.json, reports/a3/power.md
"""
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/a3"
N, REPS, RNG = 24, 100_000, 20261104
SDS = (0.03, 0.05, 0.07, 0.08)
EFFECTS = (0.0, 0.02, 0.03, 0.04, 0.055)


def simulate(effect, sd, dist, rng):
    if dist == "normal":
        x = rng.normal(effect, sd, size=(REPS, N))
    else:
        x = effect + sd * rng.standard_t(4, size=(REPS, N)) / sqrt(2.0)     # t(4) has variance 2
    m, s = x.mean(1), x.std(1, ddof=1)
    q = R.t_quantile_two_sided(0.95, N - 1)
    lo, hi = m - q * s / sqrt(N), m + q * s / sqrt(N)
    return {"P_supported": float((lo > 0).mean()), "P_upper_below_0.03": float((hi < 0.03).mean()),
            "P_wrong_sign": float((hi < 0).mean()), "mean_half_width": float((q * s / sqrt(N)).mean())}


def gate_power(d1, d2, sd, rho, rng):
    cov = sd ** 2 * np.array([[1, rho], [rho, 1]])
    x = rng.multivariate_normal([d1, d2], cov, size=(REPS, N))
    q = R.t_quantile_two_sided(0.95, N - 1)
    m, s = x.mean(1), x.std(1, ddof=1)
    h1 = m[:, 0] - q * s[:, 0] / sqrt(N) > 0
    t2 = np.abs(m[:, 1] / (s[:, 1] / sqrt(N)))
    q975_holm = R.t_quantile_two_sided(0.975, N - 1)        # Holm's first step at 0.025; conservative bound
    return {"P_H1_and_H2a_at_holm_first_step": float((h1 & (t2 > q975_holm)).mean()), "P_H1": float(h1.mean())}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RNG)
    q = R.t_quantile_two_sided(0.95, N - 1)
    res = {"n": N, "df": N - 1, "t_crit_95": q, "reps": REPS, "rng": RNG, "scenarios": {}}
    for dist in ("normal", "t4"):
        for sd in SDS:
            for e in EFFECTS:
                res["scenarios"][f"{dist}/sd{sd}/effect{e}"] = simulate(e, sd, dist, rng)
    res["gate"] = {f"sd{sd}/d1_{d1}/d2_{d2}": gate_power(d1, d2, sd, 0.5, rng)
                   for sd in (0.05, 0.07) for d1, d2 in ((0.03, 0.03), (0.055, 0.03), (0.055, 0.055))}
    res["analytic_half_width"] = {str(sd): q * sd / sqrt(N) for sd in SDS}
    t1 = res["scenarios"]["normal/sd0.05/effect0.0"]["P_supported"] + res["scenarios"]["normal/sd0.05/effect0.0"]["P_wrong_sign"]
    res["self_check_type_I_two_sided"] = t1
    assert abs(q - 2.0687) < 1e-3 and abs(t1 - 0.05) < 0.005
    (OUT / "power.json").write_text(json.dumps(res, indent=1))
    lines = ["# A3 precision planning (n = 24, df 23)", "",
             f"95% half-width = {q:.4f} x SD / sqrt(24): " + ", ".join(f"SD {sd}: {res['analytic_half_width'][str(sd)]:.4f}" for sd in SDS), "",
             "| SD | true effect | P(H1 supported), normal | t(4) | P(upper < 0.03), normal |", "|---|---|---|---|---|"]
    for sd in SDS:
        for e in EFFECTS:
            a, b = res["scenarios"][f"normal/sd{sd}/effect{e}"], res["scenarios"][f"t4/sd{sd}/effect{e}"]
            lines.append(f"| {sd} | {e} | {a['P_supported']:.3f} | {b['P_supported']:.3f} | {a['P_upper_below_0.03']:.3f} |")
    lines += ["", "Gate (H1 then H2a at Holm's first step 0.025; correlation 0.5):", ""]
    for k, v in res["gate"].items():
        lines.append(f"- {k}: P(H1) {v['P_H1']:.3f}; P(H1 and H2a) {v['P_H1_and_H2a_at_holm_first_step']:.3f}")
    (OUT / "power.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
