"""A4 within-panel learning change (owner instruction 2026-11-02, section 2). No actions; reads frozen A4 outputs.

Usage: .venv/bin/python tools/a4_longitudinal.py  -> reports/a4/longitudinal.{json,md}

All three A4 endpoints (251,904, 501,760, 1,001,472) were evaluated on the same a4_final panel (256 K=3 layouts x
2 attempts, common random numbers). Per seed and arm, p, q and r are attempt-pooled on that panel (p = successes /
512, q = arrivals / 512, r = successes / arrivals; success requires arrival, so p = q r exactly). Learning change
between two endpoints: dp = p1 - p0, decomposed exactly as dq (r1 + r0)/2 + dr (q1 + q0)/2 (descriptive, not
mediation). Summaries are means over the 20 seeds with 95% t-intervals (same weighting at every endpoint). Failure
accounting: the share of failed attempts that never reached the boundary, (1 - q) / (1 - p); this is accounting, not
evidence that any access intervention would recover those failures. The post-probe diagnostics (a4_select panel)
are not compared with these endpoints. K=3 calibration targets are reported separately from K=1.
"""
import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_r1 import t_two_sided_p    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/a4"
EPS = ("E250", "E500", "E1M")
CAL = {"K3_q_min": 0.05, "K3_q_max": 0.40, "entry_min": 0.55, "P1_max": 0.60}


def t_crit(df):
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_two_sided_p(mid, df) > 0.05 else (lo, mid)
    return (lo + hi) / 2


def tsum(x):
    x = np.asarray(x, float)
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    c = t_crit(len(x) - 1)
    return {"mean": float(m), "lo": float(m - c * se), "hi": float(m + c * se), "n": len(x)}


def main():
    rows = list(csv.DictReader((OUT / "a4_branches.csv").open()))
    V = {}
    for r in rows:
        n_att = 512
        n_arr = int(r["n_arrivals"])
        p = float(r["P1"])
        V[(int(r["seed"]), r["arm"], r["endpoint"])] = {"p": p, "q": n_arr / n_att, "r": p * n_att / n_arr, "n_arr": n_arr}
        assert abs(float(r["q"]) - n_arr / n_att) < 1e-12
    seeds = sorted({k[0] for k in V})
    assert seeds == list(range(70, 90))
    res = {"panel": "a4_final, 256 K=3 layouts x 2 attempts (common to all endpoints, arms and seeds)",
           "levels": {}, "changes": {}, "failure_accounting": {}}
    for arm in ("A", "C"):
        res["levels"][arm] = {e: {m: tsum([V[(s, arm, e)][m] for s in seeds]) for m in ("p", "q", "r")} for e in EPS}
        res["failure_accounting"][arm] = {e: tsum([(1 - V[(s, arm, e)]["q"]) / (1 - V[(s, arm, e)]["p"]) for s in seeds])
                                          for e in EPS}
        for e0, e1 in (("E250", "E500"), ("E500", "E1M"), ("E250", "E1M")):
            dp, acc, comp = [], [], []
            for s in seeds:
                a, b = V[(s, arm, e0)], V[(s, arm, e1)]
                dp.append(b["p"] - a["p"])
                acc.append((b["q"] - a["q"]) * (b["r"] + a["r"]) / 2)
                comp.append((b["r"] - a["r"]) * (b["q"] + a["q"]) / 2)
                assert abs(dp[-1] - acc[-1] - comp[-1]) < 1e-12
            res["changes"][f"{arm}:{e0}->{e1}"] = {"dp": tsum(dp), "access_term": tsum(acc), "completion_term": tsum(comp),
                                                   "access_share_of_mean": float(np.mean(acc) / np.mean(dp))}
    coh = list(csv.DictReader((OUT / "a4_cohort.csv").open()))
    k3 = {"K3_access": 0, "K3_entry": 0, "K3_room": 0, "all_K3": 0}
    for c in coh:
        acc = CAL["K3_q_min"] <= float(c["bc_K3_q"]) <= CAL["K3_q_max"]
        ent = float(c["bc_K3_entry"]) >= CAL["entry_min"]
        room = float(c["bc_K3_P1"]) <= CAL["P1_max"]
        k3["K3_access"] += acc
        k3["K3_entry"] += ent
        k3["K3_room"] += room
        k3["all_K3"] += acc and ent and room
    res["cohort_K3_targets"] = {**k3, "n": len(coh), "targets": CAL,
                                "note": "BC checkpoint at 8,000 on bc_val / dev_bank, as in calibration; K=1 targets reported separately in F25"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "longitudinal.json").write_text(json.dumps(res, indent=1))
    f = lambda d: f"{d['mean']:+.4f} [{d['lo']:+.4f}, {d['hi']:+.4f}]"
    g = lambda d: f"{d['mean']:.4f} [{d['lo']:.4f}, {d['hi']:.4f}]"
    md = ["# A4 within-panel learning (a4_final; 20 seeds; mean [95% t])", "",
          "| arm | endpoint | p | q | r | failures before boundary / all failures |", "|---|---|---|---|---|---|"]
    for arm in ("A", "C"):
        for e in EPS:
            L = res["levels"][arm][e]
            md.append(f"| {arm} | {e} | {g(L['p'])} | {g(L['q'])} | {g(L['r'])} | {g(res['failure_accounting'][arm][e])} |")
    md += ["", "| change | dp | access term | completion term |", "|---|---|---|---|"]
    for k, v in res["changes"].items():
        md.append(f"| {k} | {f(v['dp'])} | {f(v['access_term'])} | {f(v['completion_term'])} |")
    md += ["", f"K=3 calibration targets at BC 8,000 (n = {len(coh)}): access {k3['K3_access']}, entry {k3['K3_entry']}, "
           f"room {k3['K3_room']}, all three {k3['all_K3']}."]
    (OUT / "longitudinal.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
