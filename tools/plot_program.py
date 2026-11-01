"""Figures for the 2026-11-01 programme (SVG; no plotting dependency). Reads only the analysis outputs.

Usage: .venv/bin/python tools/plot_program.py [--which r2 crosspanel comp]

r2:         reports/r2/paired_effects.svg  per-seed d = P1(01) - P1(00) at 251,904 and 501,760 (dots), mean and 95%
            t-interval; reference lines 0, 0.03, 0.05; R1 and M4 study estimates as separate labelled markers
            (not pooled).
            reports/r2/endpoints.svg  per-seed P1 of each arm at 251,904 and 501,760 (one line per seed and arm).
crosspanel: reports/crosspanel/cells.svg  per-seed d in the four cohort x panel cells, mean and 95% t-interval.
comp:       reports/comp/contrasts.svg  per-seed prefix, suffix, both and interaction contrasts (3 seeds), mean.
Intervals are the analysis scripts' t-intervals. Hover titles give values.
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GREEN, ORANGE, BLUE, GREY, VIOLET = "#1baf7a", "#eb6834", "#3b7dd8", "#8a8984", "#9b59b6"
STYLE = """<style>
:root{--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--zero:#8a8984}
@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3a37;--zero:#8a8984}}
svg{background:var(--surface)} .t1{font:600 13px system-ui;fill:var(--ink)} .tick{font:11px system-ui;fill:var(--ink2)}
.grid{stroke:var(--grid);stroke-width:1} .zero{stroke:var(--zero);stroke-width:1.2} .ref{stroke:var(--zero);stroke-width:1;stroke-dasharray:4 3}
</style>"""


def svg(w, h, label, body, caption):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-label="{label}">\n{STYLE}\n<rect width="100%" height="100%" fill="var(--surface)"/>\n{body}\n'
            f'<text x="16" y="{h - 10}" class="tick">{caption}</text>\n</svg>\n')


def axis(x0, x1, sy, ticks, refs, labels=True):
    out = []
    for v in ticks:
        cls = "zero" if v == 0 else ("ref" if any(abs(v - r) < 1e-9 for r in refs) else "grid")
        out.append(f'<line x1="{x0}" x2="{x1}" y1="{sy(v):.1f}" y2="{sy(v):.1f}" class="{cls}"/>')
        if labels:
            out.append(f'<text x="{x0 - 6}" y="{sy(v) + 4:.1f}" class="tick" text-anchor="end">{v:+.2f}</text>')
    for r in refs:
        if not any(abs(r - v) < 1e-9 for v in ticks):
            out.append(f'<line x1="{x0}" x2="{x1}" y1="{sy(r):.1f}" y2="{sy(r):.1f}" class="ref"/>')
            out.append(f'<text x="{x1 + 3}" y="{sy(r) + 4:.1f}" class="tick">{r:.2f}</text>')
    return out


def group(cx, sy, vals, m, lo, hi, color, name):
    out = []
    n = len(vals)
    for j, (lab, v) in enumerate(vals):
        dx = (j - (n - 1) / 2) * (24 / max(n, 1))
        out.append(f'<g><title>{name}, {lab}: {v:+.4f}</title><circle cx="{cx - 14 + dx:.1f}" cy="{sy(v):.1f}" r="2.4" '
                   f'fill="{color}" opacity="0.7"/></g>')
    if lo is not None:
        out.append(f'<line x1="{cx + 14:.1f}" x2="{cx + 14:.1f}" y1="{sy(lo):.1f}" y2="{sy(hi):.1f}" stroke="{color}" stroke-width="2"/>')
    out.append(f'<g><title>{name}: mean {m:+.4f}' + (f', 95% t [{lo:+.4f}, {hi:+.4f}]' if lo is not None else '') +
               f'</title><circle cx="{cx + 14:.1f}" cy="{sy(m):.1f}" r="5" fill="{color}" stroke="var(--surface)" stroke-width="1.5"/></g>')
    return out


def r2():
    d = ROOT / "reports/r2"
    S = json.loads((d / "r2_summary.json").read_text())
    rows = list(csv.DictReader(open(d / "r2_seeds.csv")))
    W, H, PL, PT, PB = 560, 340, 50, 34, 60
    vals = [float(r["d"]) for r in rows] + [S[e][k] for e in ("E250", "E500") for k in ("t95_lo", "t95_hi")]
    lo_y, hi_y = min(-0.10, min(vals) - 0.01), max(0.12, max(vals) + 0.01)
    sy = lambda v: PT + (H - PT - PB) * (hi_y - v) / (hi_y - lo_y)
    ticks = [x / 100 for x in range(int(lo_y * 100) // 5 * 5, int(hi_y * 100) + 1, 5)]
    body = [f'<text x="{PL}" y="20" class="t1">R2: preservation minus ordinary PPO, P1 (K=3, early BC; 20 paired seeds)</text>']
    body += axis(PL, W - 40, sy, ticks, (0.03, 0.05))
    slots = [("E250", "251,904 (descriptive)", GREY), ("E500", "501,760 (primary)", GREEN)]
    for i, (ep, lab, col) in enumerate(slots):
        cx = PL + 70 + i * 150
        pts = [(f"seed {r['seed']}", float(r["d"])) for r in rows if r["endpoint"] == ep]
        body += group(cx, sy, pts, S[ep]["estimate"], S[ep]["t95_lo"], S[ep]["t95_hi"], col, f"R2 {lab}")
        body.append(f'<text x="{cx}" y="{H - PB + 18}" class="tick" text-anchor="middle">{lab}</text>')
    for j, (key, col) in enumerate((("R1", BLUE), ("M4", VIOLET))):
        ref = S["references_not_pooled"][key]
        cx = PL + 360 + j * 70
        body += group(cx, sy, [], ref["estimate"], ref["t95"][0], ref["t95"][1], col, f"{key} (separate study, not pooled)")
        body.append(f'<text x="{cx + 14}" y="{H - PB + 18}" class="tick" text-anchor="middle">{key} E500</text>')
    cap = "Dots: seeds. Marker and bar: mean, 95% t-interval. Dashed: 0.03 (planning), 0.05."
    (d / "paired_effects.svg").write_text(svg(W, H, "R2 paired effects", "\n".join(body), cap))
    br = list(csv.DictReader(open(d / "r2_branches.csv")))
    W2, H2 = 420, 320
    ys = [float(r["P1"]) for r in br]
    lo2, hi2 = 0.0, max(ys) + 0.05
    sy2 = lambda v: 34 + (H2 - 34 - 60) * (hi2 - v) / (hi2 - lo2)
    xs = {"E250": 110, "E500": 330}
    body2 = [f'<text x="50" y="20" class="t1">R2: P1 by arm at both endpoints (r2_final 128 x 4)</text>']
    body2 += axis(50, W2 - 30, sy2, [x / 10 for x in range(0, int(hi2 * 10) + 1)], ())
    for arm, col in (("00", GREY), ("01", GREEN)):
        for s in sorted({r["seed"] for r in br}):
            p = {r["endpoint"]: float(r["P1"]) for r in br if r["seed"] == s and r["arm"] == arm}
            body2.append(f'<g><title>seed {s}, arm {arm}: {p["E250"]:.3f} -> {p["E500"]:.3f}</title><line x1="{xs["E250"]}" '
                         f'x2="{xs["E500"]}" y1="{sy2(p["E250"]):.1f}" y2="{sy2(p["E500"]):.1f}" stroke="{col}" '
                         f'stroke-width="1.2" opacity="0.55"/></g>')
    for ep, x in xs.items():
        body2.append(f'<text x="{x}" y="{H2 - 42}" class="tick" text-anchor="middle">{"251,904" if ep == "E250" else "501,760"}</text>')
    body2.append(f'<text x="60" y="{H2 - 24}" class="tick"><tspan fill="{GREY}">grey: ordinary PPO (00)</tspan>  '
                 f'<tspan fill="{GREEN}">green: preservation (01)</tspan></text>')
    (d / "endpoints.svg").write_text(svg(W2, H2, "R2 P1 by arm and endpoint", "\n".join(body2),
                                         "One line per seed and arm. Same panel and attempt seeds for every policy."))


def crosspanel():
    d = ROOT / "reports/crosspanel"
    S = json.loads((d / "crosspanel_summary.json").read_text())
    rows = list(csv.DictReader(open(d / "crosspanel_policies.csv")))
    W, H, PL, PT, PB = 620, 330, 50, 34, 60
    cells = [("m4", "conf_final"), ("m4", "r1_final"), ("r1", "conf_final"), ("r1", "r1_final")]
    per = {}
    for r in rows:
        per.setdefault((r["cohort"], r["panel"], r["seed"]), {})[r["arm"]] = float(r["P1"])
    vals = [v["01"] - v["00"] for v in per.values() if len(v) == 2] + \
           [S["cells"][f"{c}/{p}"]["d"][k] for c, p in cells if f"{c}/{p}" in S["cells"] for k in ("t95_lo", "t95_hi")]
    lo_y, hi_y = min(-0.10, min(vals) - 0.01), max(0.12, max(vals) + 0.01)
    sy = lambda v: PT + (H - PT - PB) * (hi_y - v) / (hi_y - lo_y)
    body = [f'<text x="{PL}" y="20" class="t1">Cross-panel: preservation minus ordinary PPO, P1 (K=3, early BC, 501,760; new eval seed)</text>']
    body += axis(PL, W - 40, sy, [x / 100 for x in range(int(lo_y * 100) // 5 * 5, int(hi_y * 100) + 1, 5)], (0.03, 0.05))
    for i, (co, pn) in enumerate(cells):
        c = S["cells"].get(f"{co}/{pn}")
        if not c:
            continue
        cx = PL + 70 + i * 135
        pts = [(f"seed {k[2]}", v["01"] - v["00"]) for k, v in per.items() if k[:2] == (co, pn) and len(v) == 2]
        body += group(cx, sy, pts, c["d"]["estimate"], c["d"]["t95_lo"], c["d"]["t95_hi"], BLUE if co == "r1" else VIOLET,
                      f"{co.upper()} policies on {pn}")
        body.append(f'<text x="{cx}" y="{H - PB + 18}" class="tick" text-anchor="middle">{co.upper()} on {pn}</text>')
    (d / "cells.svg").write_text(svg(W, H, "Cross-panel cells", "\n".join(body),
                                     "Exploratory: already observed policies and panels. 4 attempts per layout. Dots: seeds."))


def comp():
    d = ROOT / "reports/comp"
    S = json.loads((d / "comp_summary.json").read_text())
    W, H, PL, PT, PB = 620, 330, 50, 34, 60
    names = [("prefix", "prefix (01p-00)", ORANGE), ("suffix", "suffix (01s-00)", BLUE), ("both", "both (01-00)", GREEN),
             ("interaction", "interaction", GREY)]
    vals = []
    for n, _, _ in names:
        b = S["contrasts"][n]["P1"]
        vals += [v for v in b["per_seed"].values() if v is not None] + [b.get("t95_lo", 0), b.get("t95_hi", 0)]
    lo_y, hi_y = min(-0.10, min(vals) - 0.01), max(0.10, max(vals) + 0.01)
    sy = lambda v: PT + (H - PT - PB) * (hi_y - v) / (hi_y - lo_y)
    body = [f'<text x="{PL}" y="20" class="t1">Anchor components: P1 contrasts at 251,904 (3 seeds; development panel)</text>']
    body += axis(PL, W - 40, sy, [x / 100 for x in range(int(lo_y * 100) // 5 * 5, int(hi_y * 100) + 1, 5)], ())
    for i, (n, lab, col) in enumerate(names):
        b = S["contrasts"][n]["P1"]
        cx = PL + 70 + i * 135
        body += group(cx, sy, [(f"seed {k}", v) for k, v in b["per_seed"].items() if v is not None], b["estimate"],
                      b.get("t95_lo"), b.get("t95_hi"), col, lab)
        body.append(f'<text x="{cx}" y="{H - PB + 18}" class="tick" text-anchor="middle">{lab}</text>')
    (d / "contrasts.svg").write_text(svg(W, H, "Anchor component contrasts", "\n".join(body),
                                         "Exploratory, 3 seeds; bars are 95% t-intervals with df 2 (wide). Dots: seeds."))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", nargs="*", default=["r2", "crosspanel", "comp"])
    a = ap.parse_args()
    for w in a.which:
        {"r2": r2, "crosspanel": crosspanel, "comp": comp}[w]()
        print(w, "done")
