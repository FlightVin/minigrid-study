"""Paired condition-level effects (SVG; no plotting dependency).

Usage: .venv/bin/python tools/plot_postm4.py [--out reports/postm4/effects.svg]

Reads reports/postm4/strata.csv and strata_seeds.csv (from tools/postm4_audit.py). One panel per condition
(K x BC checkpoint). In each panel, three intervention-minus-ordinary-PPO contrasts at the two prespecified
endpoints (251,904 and 501,760 continuation actions). Small dots: the five paired seed differences. Large marker
and bar: mean and pointwise 95% t-interval (df 4). Dashed lines: the +-0.05 P1 margin of the primary claim.
Per-condition intervals are pointwise and descriptive (no multiplicity adjustment). Hover titles give values.
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CON = [("reset", "reset (10-00)", "#eb6834", "square"), ("preservation", "preservation (01-00)", "#1baf7a", "diamond"),
       ("combined", "combined (11-00)", "#eda100", "triangle")]
STRATA = [("1", "4000", "K=1, early BC"), ("1", "16000", "K=1, extended BC"),
          ("3", "4000", "K=3, early BC"), ("3", "16000", "K=3, extended BC")]
W, H, PL, PR, PT, PB = 230, 300, 44, 10, 40, 46
YMIN, YMAX = -0.16, 0.12


def marker(shape, x, y, color, title, r=5.0):
    c = f'fill="{color}" stroke="var(--surface)" stroke-width="1.5"'
    if shape == "square":
        m = f'<rect x="{x - r + 0.5:.1f}" y="{y - r + 0.5:.1f}" width="{2 * r - 1:.1f}" height="{2 * r - 1:.1f}" rx="1" {c}/>'
    elif shape == "diamond":
        m = f'<path d="M{x:.1f},{y - r - 1:.1f} L{x + r + 1:.1f},{y:.1f} L{x:.1f},{y + r + 1:.1f} L{x - r - 1:.1f},{y:.1f} Z" {c}/>'
    else:
        m = f'<path d="M{x:.1f},{y - r - 1:.1f} L{x + r:.1f},{y + r - 0.5:.1f} L{x - r:.1f},{y + r - 0.5:.1f} Z" {c}/>'
    return f'<g><title>{title}</title>{m}</g>'


def panel(k, u, label, summ, seeds, ox):
    sy = lambda v: PT + (H - PT - PB) * (YMAX - v) / (YMAX - YMIN)
    x0, x1 = ox + PL, ox + W - PR
    out = [f'<text x="{x0}" y="22" class="t1">{label}</text>']
    for v in (-0.15, -0.10, -0.05, 0.0, 0.05, 0.10):
        cls = "zero" if v == 0 else ("margin" if abs(v) == 0.05 else "grid")
        out.append(f'<line x1="{x0}" x2="{x1}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" class="{cls}"/>')
        if ox == 0:
            out.append(f'<text x="{x0 - 6}" y="{sy(v) + 4:.1f}" class="tick" text-anchor="end">{v:+.2f}</text>')
    gw = (x1 - x0) / 2
    for gi, (ep, eplab) in enumerate((("E250", "251,904"), ("E500", "501,760"))):
        gx = x0 + gw * gi
        out.append(f'<text x="{gx + gw / 2:.1f}" y="{H - PB + 18}" class="tick" text-anchor="middle">{eplab}</text>')
        for ci, (c, name, color, shape) in enumerate(CON):
            cx = gx + gw * (ci + 1) / 4
            s = summ[(ep, k, u, c)]
            lo, hi, m = float(s["t95_lo"]), float(s["t95_hi"]), float(s["estimate"])
            pts = [r for r in seeds if (r["endpoint"], r["K"], r["bc_update"], r["contrast"]) == (ep, k, u, c)]
            for j, r in enumerate(sorted(pts, key=lambda r: r["seed"])):
                dx = (j - 2) * 2.2
                out.append(f'<g><title>{name}, {eplab}, seed {r["seed"]}: {float(r["diff"]):+.4f}</title>'
                           f'<circle cx="{cx + dx - 7:.1f}" cy="{sy(float(r["diff"])):.1f}" r="2.2" fill="{color}" opacity="0.75"/></g>')
            out.append(f'<line x1="{cx + 3:.1f}" x2="{cx + 3:.1f}" y1="{sy(lo):.1f}" y2="{sy(hi):.1f}" stroke="{color}" stroke-width="2"/>')
            out.append(marker(shape, cx + 3, sy(m), color,
                              f"{name}, {label}, {eplab}: mean {m:+.4f}, 95% t-interval [{lo:+.4f}, {hi:+.4f}]"))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports/postm4/effects.svg"))
    a = ap.parse_args()
    d = ROOT / "reports/postm4"
    summ = {(r["endpoint"], r["K"], r["bc_update"], r["contrast"]): r for r in csv.DictReader(open(d / "strata.csv"))}
    seeds = list(csv.DictReader(open(d / "strata_seeds.csv")))
    for r in seeds:
        r["seed"] = int(r["seed"])
    vals = [float(r["diff"]) for r in seeds] + [float(s[k]) for s in summ.values() for k in ("t95_lo", "t95_hi")]
    assert YMIN <= min(vals) and max(vals) <= YMAX, (min(vals), max(vals))
    legend = " ".join(f'<g transform="translate({16 + i * 200},{H + 14})">{marker(shape, 0, 0, color, name)}'
                      f'<text x="11" y="4" class="tick">{name}</text></g>' for i, (_, name, color, shape) in enumerate(CON))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {4 * W} {H + 50}" width="{4 * W}" height="{H + 50}"
 role="img" aria-label="Intervention minus ordinary PPO P1 by condition and endpoint, with paired seed differences and 95% t-intervals">
<style>
:root{{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--zero:#8a8984}}
@media (prefers-color-scheme: dark){{:root{{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3a37;--zero:#8a8984}}}}
svg{{background:var(--surface)}} .t1{{font:600 13px system-ui;fill:var(--ink)}} .tick{{font:11px system-ui;fill:var(--ink2)}}
.grid{{stroke:var(--grid);stroke-width:1}} .zero{{stroke:var(--zero);stroke-width:1.2}} .margin{{stroke:var(--zero);stroke-width:1;stroke-dasharray:4 3}}
</style>
<rect width="100%" height="100%" fill="var(--surface)"/>
{"".join(panel(k, u, lab, summ, seeds, i * W) for i, (k, u, lab) in enumerate(STRATA))}
{legend}
<text x="16" y="{H + 40}" class="tick">P1 difference vs ordinary PPO (5 paired seeds; mean and pointwise 95% t-interval, df 4). Dashed: ±0.05 margin. x: continuation actions. M4 confirmation data.</text>
</svg>'''
    Path(a.out).write_text(svg)
    print(a.out)


if __name__ == "__main__":
    main()
