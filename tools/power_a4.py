"""A4 planning scenarios (owner instruction 2026-11-01c, section 7). n = 20 paired seeds, two-sided paired t, alpha 0.05.
Scenarios only: the seed SD of d at 1,001,472 is unknown. The 3-seed pilot (K3 01s-00 at 251,904: +0.012, -0.035,
+0.031; SD about 0.034) and A3 (SD 0.021 at 251,904, a different regime) are context, not a power promise.
Power by Monte Carlo of the paired t-test (200,000 draws per cell, RNG 20261105) under normal d_i.
Writes reports/a4/power.json and power.md."""
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
N, SDS, EFFECTS = 20, (0.03, 0.05, 0.07, 0.08, 0.10), (0.01, 0.02, 0.03, 0.05)


def main():
    q = R.t_quantile_two_sided(0.95, N - 1)
    rng = np.random.default_rng(20261105)
    z = rng.standard_normal((200_000, N))
    zm, zs = z.mean(1), z.std(1, ddof=1)
    rows = []
    for sd in SDS:
        hw = q * sd / sqrt(N)
        row = {"sd": sd, "half_width_95": hw}
        for e in EFFECTS:
            t = (e / sd + zm) / (zs / sqrt(N))
            row[f"power_at_{e}"] = float((np.abs(t) > q).mean())
        rows.append(row)
    out = ROOT / "reports/a4"
    out.mkdir(parents=True, exist_ok=True)
    (out / "power.json").write_text(json.dumps({"n": N, "t975_df19": q, "rows": rows}, indent=1))
    md = ["| seed SD of d | 95% half-width | power +0.01 | +0.02 | +0.03 | +0.05 |", "|---|---|---|---|---|---|"]
    md += [f"| {r['sd']:.2f} | {r['half_width_95']:.3f} | " + " | ".join(f"{r[f'power_at_{e}']:.2f}" for e in EFFECTS) + " |" for r in rows]
    (out / "power.md").write_text("A4 planning scenarios (n = 20, two-sided paired t, alpha 0.05; Monte Carlo).\n\n" + "\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
