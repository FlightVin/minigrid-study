"""Figures for the 2026-11-01 programme (SVG; no plotting dependency). Reads only the analysis outputs.

Usage: .venv/bin/python tools/plot_program.py [--which r2 crosspanel comp]

r2:         reports/r2/paired_effects.svg  per-seed d = P1(01) - P1(00) at 251,904 and 501,760 (dots), mean and 95%
            t-interval; reference lines 0, 0.03, 0.05; R1 and M4 study estimates as separate labelled markers
            (not pooled).
            reports/r2/endpoints.svg  per-seed P1 of each arm at 251,904 and 501,760 (one line per seed and arm).
crosspanel: reports/crosspanel/cells.svg  per-seed d in the four cohort x panel cells, mean and 95% t-interval.
comp:       reports/comp/contrasts.svg  per-seed prefix, suffix, both and interaction contrasts (3 seeds), mean.
a3:         reports/a3/paired_effects.svg  per-seed P1 contrasts (B-A, C-A, D-A, E-A, D-C, interaction) at 251,904
            and 501,760, mean and 95% t-interval; C-A at 251,904 is the confirmatory H1, the rest are descriptive.
            reports/a3/diagnostics.svg  per-arm means of training anchor KL (prefix, suffix), applied penalty and
            update size (successive-policy KL on prefix and suffix anchor rows, actor parameter-change norm), to
            251,904 and over the whole run. Small multiples, one scale each.
cal:        reports/cal/access_entry.svg  initial normal-start access q (x) against fixed-bank boundary-entry competence
            (y) for each calibration variant (rho, BC updates), one panel per K; seeds as small dots, the three-seed
            mean as a large marker; the frozen target region shaded. Development only.
pilot:      reports/pilot/contrasts.svg  per-seed normal-start P1 contrasts 10-00 (resets), 01s-00 (suffix
            preservation), 11s-00 (both) and the interaction at 251,904, one panel per K; mean and 95% t-interval
            (df 2, wide). Exploratory.
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


A3_COL = {"B-A": ORANGE, "C-A": BLUE, "D-A": GREEN, "E-A": VIOLET, "D-C": GREY, "interaction D-B-C+A": GREY}


def a3(d=None):
    d = Path(d) if d else ROOT / "reports/a3"
    S = json.loads((d / "a3_summary.json").read_text())
    assert S["primary_computed"], "A3 analysis is blinded or incomplete; no figure"
    rows = list(csv.DictReader(open(d / "a3_contrasts.csv")))
    sec = S["secondary_contrasts"]
    names = list(A3_COL)
    W, H, PL, PT, PB = 880, 360, 50, 34, 74
    vals = [float(r["d_P1"]) for r in rows if r["d_P1"] not in ("", "None")]
    vals += [sec[e][n]["P1"][k] for e in ("E250", "E500") for n in names for k in ("t95_lo", "t95_hi")]
    lo_y, hi_y = min(-0.10, min(vals) - 0.01), max(0.10, max(vals) + 0.01)
    sy = lambda v: PT + (H - PT - PB) * (hi_y - v) / (hi_y - lo_y)
    ticks = [x / 100 for x in range(int(lo_y * 100) // 5 * 5, int(hi_y * 100) + 1, 5)]
    body = [f'<text x="{PL}" y="20" class="t1">A3: paired P1 contrasts (K=3, early BC, normal starts; '
            f'{S["n"]} seeds; a3_final 128 x 4)</text>']
    body += axis(PL, W - 40, sy, ticks, (0.03,))
    for i, n in enumerate(names):
        for j, ep in enumerate(("E250", "E500")):
            b = sec[ep][n]["P1"]
            cx = PL + 55 + i * 130 + j * 58
            pts = [(f"seed {r['seed']}", float(r["d_P1"])) for r in rows
                   if r["endpoint"] == ep and r["contrast"] == n and r["d_P1"] not in ("", "None")]
            lab = f"{n} at {'251,904' if ep == 'E250' else '501,760'}" + (" (confirmatory H1)" if (n, ep) == ("C-A", "E250") else "")
            body += group(cx, sy, pts, b["estimate"], b["t95_lo"], b["t95_hi"], A3_COL[n], lab)
            body.append(f'<text x="{cx}" y="{H - PB + 16}" class="tick" text-anchor="middle">{"250k" if ep == "E250" else "500k"}</text>')
        short = "interaction" if n.startswith("inter") else n
        body.append(f'<text x="{PL + 55 + i * 130 + 29}" y="{H - PB + 32}" class="t1" text-anchor="middle">{short}</text>')
    h1 = S["H1"]
    cap = (f"H1 (C-A at 251,904): {h1['estimate']:+.4f} [{h1['t95_lo']:+.4f}, {h1['t95_hi']:+.4f}], p {h1['p']:.3f}, "
           f"{h1['decision']}. Other contrasts descriptive. Dots: seeds; bar: 95% t-interval; dashed: 0.03.")
    (d / "paired_effects.svg").write_text(svg(W, H, "A3 paired contrasts", "\n".join(body), cap))
    metrics = [("anchor_kl_prefix", "anchor KL, prefix rows"), ("anchor_kl_suffix", "anchor KL, suffix rows"),
               ("anchor_penalty", "applied penalty"), ("update_kl_prefix", "update KL, prefix rows"),
               ("update_kl_suffix", "update KL, suffix rows"), ("actor_update_norm", "actor update norm")]
    arms = [("A", "A 00", GREY), ("B", "B prefix", ORANGE), ("C", "C suffix", BLUE), ("D", "D both", GREEN), ("E", "E 0.75x", VIOLET)]
    PW, PH, W2 = 270, 190, 860
    H2 = 40 + 2 * PH + 30
    body2 = ['<text x="16" y="20" class="t1">A3 training diagnostics: per-arm mean over seeds (solid: to 251,904; '
             'outline: whole run to 501,760)</text>']
    for k, (m, title) in enumerate(metrics):
        ox, oy = 16 + (k % 3) * (PW + 6), 36 + (k // 3) * PH
        v = [(S["arms"][f"E500/{a}"]["training"].get(f"{m}_mean_to_251904"), S["arms"][f"E500/{a}"]["training"].get(f"{m}_mean"))
             for a, _, _ in arms]
        top = max([x for pair in v for x in pair if x is not None] + [1e-12]) * 1.15
        x0, y0, y1 = ox + 44, oy + 24, oy + PH - 36
        sy2 = lambda u: y1 - (y1 - y0) * u / top
        body2.append(f'<text x="{ox}" y="{oy + 12}" class="t1">{title}</text>')
        for f in (0, 0.5, 1):
            body2.append(f'<line x1="{x0}" x2="{ox + PW - 8}" y1="{sy2(top * f):.1f}" y2="{sy2(top * f):.1f}" class="{"zero" if f == 0 else "grid"}"/>')
            body2.append(f'<text x="{x0 - 4}" y="{sy2(top * f) + 4:.1f}" class="tick" text-anchor="end">{top * f:.2g}</text>')
        for i, ((a, lab, col), (h, w)) in enumerate(zip(arms, v)):
            cx = x0 + 22 + i * 42
            if h is not None:
                body2.append(f'<g><title>{lab}, {title}, to 251,904: {h:.4g}</title><rect x="{cx - 8}" y="{sy2(h):.1f}" width="8" '
                             f'height="{max(y1 - sy2(h), 0):.1f}" rx="2" fill="{col}"/></g>')
            if w is not None:
                body2.append(f'<g><title>{lab}, {title}, whole run: {w:.4g}</title><rect x="{cx + 2}" y="{sy2(w):.1f}" width="8" '
                             f'height="{max(y1 - sy2(w), 0):.1f}" rx="2" fill="none" stroke="{col}" stroke-width="1.5"/></g>')
            body2.append(f'<text x="{cx + 1}" y="{y1 + 14}" class="tick" text-anchor="middle">{a}</text>')
    body2.append(f'<text x="16" y="{H2 - 26}" class="tick">' + "  ".join(
        f'<tspan fill="{c}">\u25a0</tspan> {l}' for _, l, c in arms) + '</text>')
    (d / "diagnostics.svg").write_text(svg(W2, H2, "A3 training diagnostics", "\n".join(body2),
                                           "Means over seeds of per-update values from the branch metrics. Each panel has its own scale."))


def cal(d=None):
    d = Path(d) if d else ROOT / "reports/cal"
    S = json.loads((d / "cal_summary.json").read_text())
    rows = list(csv.DictReader(open(d / "cal_variants.csv")))
    T = S["targets"]
    col = {0.2: ORANGE, 0.5: BLUE, 0.8: GREEN}
    PW, PH, W = 380, 300, 800
    H = 36 + PH + 70
    body = ['<text x="16" y="20" class="t1">Calibration: initial access q vs boundary-entry competence (seeds 67-69; development roles)</text>']
    for k, K in enumerate((1, 3)):
        ox, oy = 16 + k * (PW + 16), 36
        x0, x1, y0, y1 = ox + 40, ox + PW - 10, oy + 20, oy + PH - 30
        sx = lambda v: x0 + (x1 - x0) * v
        sy = lambda v: y1 - (y1 - y0) * v
        qlo, qhi = (T["K1_q_min"], 1.0) if K == 1 else (T["K3_q_min"], T["K3_q_max"])
        body.append(f'<rect x="{sx(qlo):.1f}" y="{sy(1):.1f}" width="{sx(qhi) - sx(qlo):.1f}" height="{sy(T["entry_min"]) - sy(1):.1f}" '
                    f'fill="var(--grid)" opacity="0.6"><title>K={K} target region: q in [{qlo}, {qhi}], entry &gt;= {T["entry_min"]}</title></rect>')
        body.append(f'<text x="{ox}" y="{oy + 12}" class="t1">K={K}</text>')
        for f in (0, 0.25, 0.5, 0.75, 1):
            body.append(f'<line x1="{x0}" x2="{x1}" y1="{sy(f):.1f}" y2="{sy(f):.1f}" class="{"zero" if f == 0 else "grid"}"/>')
            body.append(f'<text x="{x0 - 4}" y="{sy(f) + 4:.1f}" class="tick" text-anchor="end">{f:.2f}</text>')
            body.append(f'<text x="{sx(f):.1f}" y="{y1 + 14}" class="tick" text-anchor="middle">{f:.2f}</text>')
        body.append(f'<text x="{(x0 + x1) / 2}" y="{y1 + 28}" class="tick" text-anchor="middle">access q (normal starts)</text>')
        for r in rows:
            rho, u = float(r["rho"]), int(r["update"])
            q, e = float(r[f"K{K}_q"]), float(r[f"K{K}_entry"])
            fill = col[rho] if u == 4000 else "none"
            body.append(f'<g><title>rho {rho}, {u} updates, seed {r["seed"]}: q {q:.3f}, entry {e:.3f}, P1 {float(r[f"K{K}_P1"]):.3f}</title>'
                        f'<circle cx="{sx(q):.1f}" cy="{sy(e):.1f}" r="2.6" fill="{fill}" stroke="{col[rho]}" stroke-width="1" opacity="0.7"/></g>')
        for key, v in S["variants"].items():
            rho, u = float(key.split("/")[0][3:]), int(key.split("/")[1][1:])
            m = v["means"][str(K)] if str(K) in v["means"] else v["means"][K]
            sel = S["selected"] == {"rho": rho, "update": u}
            fill = col[rho] if u == 4000 else "var(--surface)"
            body.append(f'<g><title>rho {rho}, {u} updates (3-seed mean): q {m["q"]:.3f}, entry {m["entry"]:.3f}, P1 {m["P1"]:.3f}; '
                        f'{"qualifies" if v["qualifies"] else "fails " + ", ".join(v["shortfalls"])}{"; SELECTED" if sel else ""}</title>'
                        f'<circle cx="{sx(m["q"]):.1f}" cy="{sy(m["entry"]):.1f}" r="{7 if sel else 5.5}" fill="{fill}" stroke="{col[rho]}" '
                        f'stroke-width="{3 if sel else 2}"/></g>')
    leg = "  ".join(f'<tspan fill="{c}">\u25cf</tspan> rho {r}' for r, c in col.items())
    body.append(f'<text x="16" y="{H - 28}" class="tick">{leg}. Filled: 4,000 BC updates; hollow: 8,000; large: three-seed mean; '
                f'shaded: target region (entry target applies to both K)</text>')
    sel = S["selected"]
    cap = f"Selected: rho {sel['rho']}, {sel['update']} updates." if sel else "No variant met every target (see cal_summary.json shortfalls)."
    (d / "access_entry.svg").write_text(svg(W, H, "Calibration access vs entry", "\n".join(body), cap + " Room-to-learn (P1) target is in the hover text."))


def pilot(d=None):
    d = Path(d) if d else ROOT / "reports/pilot"
    S = json.loads((d / "pilot_summary.json").read_text())
    names = [("10-00", "resets (10-00)", ORANGE), ("01s-00", "suffix (01s-00)", BLUE), ("11s-00", "both (11s-00)", GREEN),
             ("interaction", "interaction", GREY)]
    Ks = [K for K in ("K1", "K3") if K in S["conditions"]]
    vals = []
    for K in Ks:
        for n, _, _ in names:
            b = S["conditions"][K]["contrasts"][n]["P1"]
            vals += b["per_seed"] + [b.get("t95_lo", 0), b.get("t95_hi", 0)]
    lo_y, hi_y = min(-0.10, min(vals) - 0.01), max(0.10, max(vals) + 0.01)
    PW, H, PT, PB = 420, 340, 50, 64
    W = 16 + len(Ks) * (PW + 10)
    sy = lambda v: PT + (H - PT - PB) * (hi_y - v) / (hi_y - lo_y)
    ticks = [x / 100 for x in range(int(lo_y * 100) // 5 * 5, int(hi_y * 100) + 1, 5)]
    body = ['<text x="16" y="20" class="t1">Pilot (calibrated regime): normal-start P1 contrasts at 251,904 (3 seeds; exploratory)</text>']
    for k, K in enumerate(Ks):
        ox = 16 + k * (PW + 10)
        body.append(f'<text x="{ox}" y="{PT - 12}" class="t1">{K[0]}={K[1]}</text>')
        body += axis(ox + 40, ox + PW - 10, sy, ticks, (), labels=True)
        for i, (n, lab, col) in enumerate(names):
            b = S["conditions"][K]["contrasts"][n]["P1"]
            cx = ox + 80 + i * 92
            body += group(cx, sy, [(f"seed {j}", v) for j, v in enumerate(b["per_seed"])], b.get("estimate", float("nan")),
                          b.get("t95_lo"), b.get("t95_hi"), col, f"{K}: {lab}")
            body.append(f'<text x="{cx}" y="{H - PB + 26}" class="tick" text-anchor="middle">{lab.split(" ")[0]}</text>')
    cap = "Dots: seeds; marker and bar: mean, 95% t-interval with df 2. Assisted (reset) access is not part of these normal-start values."
    (d / "contrasts.svg").write_text(svg(W, H, "Pilot contrasts", "\n".join(body), cap))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--which", nargs="*", default=["r2", "crosspanel", "comp"])
    a = ap.parse_args()
    for w in a.which:
        {"r2": r2, "crosspanel": crosspanel, "comp": comp, "a3": a3, "cal": cal, "pilot": pilot}[w]()
        print(w, "done")
