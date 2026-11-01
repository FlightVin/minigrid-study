"""R1 power and precision (PROTOCOL_FREEZE Amendment 3). Executable; reads only M4 artifacts; no R1 data.

Usage: .venv/bin/python tools/power_r1.py [--reps 20000] [--out reports/r1]

Inputs from M4 (tools/postm4_audit.load, raw attempts):
  - seed-level SDs of the paired preservation effect (01 - 00) in every K x checkpoint x endpoint cell (n=5 each);
  - seed-level SD of the within-K=3 checkpoint interaction (early effect - extended effect);
  - the layout-level SD of the per-layout effect (mean over seeds) on conf_final K=3, raw and corrected for
    seed-by-layout noise; R1 uses a 128-layout panel, so the panel deviation has SD sigma_L / sqrt(128).
Model per simulated replication: panel effects = true effect + N(0, sigma_L^2 / 128) (one draw per panel, shared
by all seeds); seed i: early = panel_early + e_i, extended = panel_extended + x_i, corr(e, x) = rho.
H1: t-test (df 7) on the 8 early effects; H2: t-test on the 8 interactions; Holm over the two at 0.05.
Scenarios cross the true effects (M4 post hoc values and shrunken values), three seed SDs (the selected subgroup's
unusually small SD, the median and the maximum over the 8 M4 preservation cells), rho in {-0.4 (near the noisy
M4 estimate), 0, 0.5}, and sigma_L in {0 (conditional on the panel), the M4 estimate corrected for seed-by-layout
noise, the raw M4 SD (an upper bound)}. No single scenario is a power promise. Under the null, the layout rows show
how often the paired t-test detects a nonzero panel-specific effect: the t-test is inference conditional on the
frozen panel; the crossed bootstrap addresses layout sampling.
Outputs: power.json (all scenarios and inputs), power.md (main table).
"""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import postm4_audit as A            # noqa: E402
import r1_stats as R                # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
L_R1 = 128


def m4_inputs():
    D, _ = A.load()
    cells = {}
    for ep in A.EP:
        for K, u in A.STRATA:
            d = np.array([(D[(s, K, u, "01", ep)]["p"] - D[(s, K, u, "00", ep)]["p"]).mean() for s in A.SEEDS])
            cells[f"{ep}/K{K}/u{u}"] = {"mean": float(d.mean()), "sd": float(d.std(ddof=1))}
    out = {"cells": cells}
    for ep in A.EP:
        e = np.array([(D[(s, 3, 4000, "01", ep)]["p"] - D[(s, 3, 4000, "00", ep)]["p"]) for s in A.SEEDS])     # (5, 64)
        x = np.array([(D[(s, 3, 16000, "01", ep)]["p"] - D[(s, 3, 16000, "00", ep)]["p"]) for s in A.SEEDS])
        i = e - x
        rho = float(np.corrcoef(e.mean(1), x.mean(1))[0, 1])
        lay = {}
        for name, m in (("early", e), ("extended", x), ("interaction", i)):
            raw = float(m.mean(0).std(ddof=1))                     # SD over 64 layouts of the seed-mean effect
            resid = float(np.mean(m.var(0, ddof=1)) / m.shape[0])  # seed-by-layout part of that variance
            lay[name] = {"sd_raw": raw, "sd_corrected": float(np.sqrt(max(raw ** 2 - resid, 0.0)))}
        out[ep] = {"interaction_mean": float(i.mean()), "interaction_seed_sd": float(i.mean(1).std(ddof=1)),
                   "early_extended_seed_corr": rho, "layout": lay}
    sds = sorted(c["sd"] for c in cells.values())
    out["seed_sd_summary"] = {"min": sds[0], "median": float(np.median(sds)), "max": sds[-1]}
    return out


def simulate(dE, dX, sE, sX, rho, sLE, sLX, reps, rng):
    """Returns P(H1 supported), P(H2 supported), P(both), P(H1 unadjusted p<0.05) under Holm-2."""
    cov = np.array([[sE * sE, rho * sE * sX], [rho * sE * sX, sX * sX]])
    z = rng.multivariate_normal([0, 0], cov, size=(reps, R.N_SEEDS))                  # (reps, 8, 2)
    pe = dE + rng.normal(0, sLE / np.sqrt(L_R1), reps)                                 # panel deviations
    px = dX + rng.normal(0, sLX / np.sqrt(L_R1), reps)
    early = pe[:, None] + z[..., 0]
    inter = early - (px[:, None] + z[..., 1])

    def pvals(m):
        t = m.mean(1) / (m.std(1, ddof=1) / np.sqrt(R.N_SEEDS))
        return np.array([1 - R.t_cdf_abs(abs(v)) for v in t])

    p1, p2 = pvals(early), pvals(inter)
    lo, hi = np.minimum(p1, p2), np.maximum(p1, p2)
    rej_lo, rej_hi = 2 * lo < 0.05, (2 * lo < 0.05) & (hi < 0.05)
    h1 = np.where(p1 <= p2, rej_lo, rej_hi)
    h2 = np.where(p2 < p1, rej_lo, rej_hi)
    return {"H1": float(h1.mean()), "H2": float(h2.mean()), "both": float((h1 & h2).mean()),
            "H1_unadjusted": float((p1 < 0.05).mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20000)
    ap.add_argument("--out", default=str(ROOT / "reports/r1"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    m4 = m4_inputs()
    E5 = m4["E500"]
    sd = m4["seed_sd_summary"]
    sd_sel = m4["cells"]["E500/K3/u4000"]["sd"]
    sd_scen = {"M4 selected subgroup (unusually small)": sd_sel, "median of 8 M4 cells": sd["median"],
               "maximum of 8 M4 cells": sd["max"]}
    lay_scen = {"conditional on panel": (0.0, 0.0),
                "M4 layout SD (corrected)": (E5["layout"]["early"]["sd_corrected"], E5["layout"]["extended"]["sd_corrected"]),
                "M4 layout SD (raw, upper bound)": (E5["layout"]["early"]["sd_raw"], E5["layout"]["extended"]["sd_raw"])}
    eff_scen = {"M4 post hoc (+0.045 early, -0.027 extended)": (m4["cells"]["E500/K3/u4000"]["mean"], m4["cells"]["E500/K3/u16000"]["mean"]),
                "half of M4 early, extended 0": (m4["cells"]["E500/K3/u4000"]["mean"] / 2, 0.0),
                "+0.03 early, extended 0": (0.03, 0.0),
                "null (0, 0)": (0.0, 0.0)}
    rng = np.random.default_rng(20261101)
    rows = []
    for en, (dE, dX) in eff_scen.items():
        for sn, s in sd_scen.items():
            for rho in (-0.4, 0.0, 0.5):
                for ln, (lE, lX) in lay_scen.items():
                    r = simulate(dE, dX, s, s, rho, lE, lX, a.reps, rng)
                    rows.append({"effects": en, "true_early": dE, "true_extended": dX, "true_interaction": dE - dX,
                                 "seed_sd": sn, "seed_sd_value": s, "rho": rho, "layout": ln,
                                 "layout_sd_early": lE, "layout_sd_extended": lX, **r})
    # approximate minimum detectable early effect for 80% power at the Holm worst case (alpha 0.025), conditional
    t_a, t_b = R.t_quantile_two_sided(0.975), R.t_quantile_two_sided(0.60)    # two-sided 0.025; one-sided 0.80
    mde = {sn: (t_a + t_b) * s / np.sqrt(R.N_SEEDS) for sn, s in sd_scen.items()}
    res = {"m4_inputs": m4, "reps": a.reps, "rng": 20261101, "layouts_r1": L_R1, "scenarios": rows,
           "approx_mde_80pct_holm_worst_case_conditional": mde,
           "panel_se_early_at_128_layouts": E5["layout"]["early"]["sd_raw"] / np.sqrt(L_R1),
           "note": "Conditional power treats the frozen panel as fixed (the paired t-test's inference). Layout rows add "
                   "the panel's sampling deviation from the population effect. The selected subgroup SD is reported "
                   "but is not the planning value."}
    (out / "power.json").write_text(json.dumps(res, indent=1))
    lines = ["| true effects | seed SD | rho | layout | P(H1) | P(H2) | P(both) |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['effects']} | {r['seed_sd']} ({r['seed_sd_value']:.4f}) | {r['rho']} | {r['layout']} | "
                     f"{r['H1']:.2f} | {r['H2']:.2f} | {r['both']:.2f} |")
    (out / "power.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"seed_sd_summary": sd, "selected_sd": sd_sel, "E500": E5, "mde": mde,
                      "panel_se_early_128": res["panel_se_early_at_128_layouts"]}, indent=1))


if __name__ == "__main__":
    main()
