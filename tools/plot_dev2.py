"""SVG learning curves for the E1 long runs (no plotting dependency).

Usage: .venv/bin/python tools/plot_dev2.py [--out reports/dev2_curves.svg]

Reads reports/dev2_long_evals.csv and the M3 probe summaries. One panel per seed; normal-start P1
against post-probe actions for the four selected arms. Point at 0 = post-probe p (32 x 4, shared by all
arms). Points at 126,976 and 376,832 use 32 x 2 attempts; at 251,904 and 501,760, 32 x 8. Hollow markers
at 251,904 = M3 original runs from the same fork (a separate training path). Hover titles give values.
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = [("00", "ordinary PPO (00)", "#2a78d6", "circle"), ("10", "reset (10)", "#eb6834", "square"),
        ("01", "preserve (01)", "#1baf7a", "diamond"), ("11", "combined (11)", "#eda100", "triangle")]
W, H, PAD_L, PAD_R, PAD_T, PAD_B = 460, 300, 48, 132, 34, 44
XMAX, YMAX = 501760, 0.6


def marker(shape, x, y, color, hollow, title):
    fill = "var(--surface)" if hollow else color
    common = f'fill="{fill}" stroke="{color}" stroke-width="2"'
    if shape == "circle":
        m = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" {common}/>'
    elif shape == "square":
        m = f'<rect x="{x - 4:.1f}" y="{y - 4:.1f}" width="8" height="8" rx="1" {common}/>'
    elif shape == "diamond":
        m = f'<path d="M{x:.1f},{y - 5.5:.1f} L{x + 5.5:.1f},{y:.1f} L{x:.1f},{y + 5.5:.1f} L{x - 5.5:.1f},{y:.1f} Z" {common}/>'
    else:
        m = f'<path d="M{x:.1f},{y - 5.5:.1f} L{x + 5:.1f},{y + 4:.1f} L{x - 5:.1f},{y + 4:.1f} Z" {common}/>'
    return f'<g><title>{title}</title>{m}</g>'


def panel(seed, rows, probe_p, ox):
    sx = lambda a: ox + PAD_L + (W - PAD_L - PAD_R) * a / XMAX
    sy = lambda p: PAD_T + (H - PAD_T - PAD_B) * (1 - p / YMAX)
    out = [f'<text x="{ox + PAD_L}" y="20" class="t1">Seed {seed} · K=3, extended BC</text>']
    for p in (0, 0.2, 0.4, 0.6):
        out.append(f'<line x1="{ox + PAD_L}" x2="{ox + W - PAD_R}" y1="{sy(p):.1f}" y2="{sy(p):.1f}" class="grid"/>')
        out.append(f'<text x="{ox + PAD_L - 6}" y="{sy(p) + 4:.1f}" class="tick" text-anchor="end">{p:.1f}</text>')
    for a in (0, 251904, 501760):
        out.append(f'<text x="{sx(a):.1f}" y="{H - PAD_B + 16}" class="tick" text-anchor="middle">{a // 1000}k</text>')
    out.append(f'<text x="{ox + (W - PAD_R + PAD_L) / 2:.0f}" y="{H - 8}" class="tick" text-anchor="middle">post-probe actions</text>')
    labels = []
    for arm, name, color, shape in ARMS:
        pts = [(0, probe_p)] + sorted((int(r["post_probe_actions"]), float(r["P1"])) for r in rows
                                      if r["seed"] == str(seed) and r["arm"] == arm and r["run"] == "new")
        d = " ".join(f'{"M" if i == 0 else "L"}{sx(a):.1f},{sy(p):.1f}' for i, (a, p) in enumerate(pts))
        out.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2"/>')
        for a, p in pts[1:]:
            out.append(marker(shape, sx(a), sy(p), color, False, f"{name}, {a:,} actions: P1 {p:.3f}"))
        orig = [float(r["P1"]) for r in rows if r["seed"] == str(seed) and r["arm"] == arm and r["run"] == "m3_original"]
        for p in orig:
            out.append(marker(shape, sx(251904) + 12, sy(p), color, True, f"{name}, M3 original path at 251,904: P1 {p:.3f}"))
        labels.append((pts[-1][1], name, color))
    placed = []
    for p, name, color in sorted(labels, key=lambda t: -t[0]):
        y = sy(p) + 4
        if placed and y - placed[-1] < 13:
            y = placed[-1] + 13
        placed.append(y)
        out.append(f'<text x="{ox + W - PAD_R + 8}" y="{y:.1f}" class="lab">{name.split(" (")[0]} {p:.2f}</text>')
    out.append(marker("circle", sx(0), sy(probe_p), "var(--ink2)", False, f"post-probe p (all arms): {probe_p:.3f}"))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports/dev2_curves.svg"))
    a = ap.parse_args()
    rows = list(csv.DictReader(open(ROOT / "reports/dev2_long_evals.csv")))
    probe = {s: json.loads((ROOT / f".mae/runs/20261030T214937-19577/m3-probe-K3-u16000-s{s}/summary.json").read_text())["probe"]["p"]
             for s in (0, 1)}
    legend = " ".join(
        f'<g transform="translate({20 + i * 190},{H + 18})">{marker(shape, 0, 0, color, False, name)}'
        f'<text x="10" y="4" class="tick">{name}</text></g>' for i, (_, name, color, shape) in enumerate(ARMS))
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {2 * W} {H + 56}" width="{2 * W}" height="{H + 56}"
 role="img" aria-label="Normal-start success P1 against post-probe actions for four arms, two seeds">
<style>
:root{{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df}}
@media (prefers-color-scheme: dark){{:root{{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3a37}}}}
svg{{background:var(--surface)}} .t1{{font:600 13px system-ui;fill:var(--ink)}}
.tick{{font:11px system-ui;fill:var(--ink2)}} .lab{{font:11px system-ui;fill:var(--ink)}} .grid{{stroke:var(--grid);stroke-width:1}}
</style>
<rect width="100%" height="100%" fill="var(--surface)"/>
{panel(0, rows, probe[0], 0)}
{panel(1, rows, probe[1], W)}
{legend}
<text x="20" y="{H + 44}" class="tick">Hollow markers: M3 original path at 251,904 (same fork). 126,976 / 376,832: 32 x 2 attempts; 251,904 / 501,760: 32 x 8. Development data.</text>
</svg>'''
    Path(a.out).write_text(svg)
    print(a.out)


if __name__ == "__main__":
    main()
