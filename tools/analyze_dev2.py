"""Analysis of the 2026-10-31 development campaign (E1 long runs) with the M3 originals.

Usage: .venv/bin/python tools/analyze_dev2.py BATCH [--out reports]

Rows are selected by explicit job-name keys; duplicates are errors. Outputs:
  dev2_long_evals.csv      every scheduled evaluation of every E1 branch (P1, q, c, C4, R4, P(success|arrival),
                           arrivals, remaining-time quantiles), plus the M3 original at 251,904 for the same fork/arm.
  dev2_long_contrasts.csv  per seed and endpoint: the six paired contrasts with a within-seed layout-resampling
                           95% interval (2,000 paired resamples of the 32 layouts; seed 20261031). That interval
                           covers evaluation layouts and attempts only, not training variation.
  dev2_path_repeats.csv    new run at 251,904 minus M3 original at 251,904 (same fork, arm, settings).
Seeds are the independent unit; with two seeds no across-seed interval is computed.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
M3, M3B = "20261030T214937-19577", "20261030T232600-96083"
ORIG = {"00": f"{M3}/m3-K3-u16000-s{{s}}-00", "01": f"{M3}/m3-K3-u16000-s{{s}}-01-kl0p01",
        "10": f"{M3}/m3-K3-u16000-s{{s}}-10-a0p25", "11": f"{M3B}/m3-K3-u16000-s{{s}}-11-a0p25-kl0p01"}
ARMS = ("00", "10", "01", "11")
CONTRASTS = {"reset": lambda y: y["10"] - y["00"], "preserve": lambda y: y["01"] - y["00"],
             "combined": lambda y: y["11"] - y["00"],
             "interaction": lambda y: (y["11"] - y["01"]) - (y["10"] - y["00"]),
             "combined_vs_reset": lambda y: y["11"] - y["10"], "combined_vs_preserve": lambda y: y["11"] - y["01"]}


def per_layout(path):
    by = {}
    for l in Path(path).read_text().splitlines():
        r = json.loads(l)
        if r["kind"] == "normal":
            by.setdefault(r["item"], []).append(r)
    items = sorted(by)
    p = np.array([np.mean([x["success"] for x in by[i]]) for i in items])
    arr = [x for i in items for x in by[i] if x["arrival"]]
    rem = [x["arrival"]["remaining"] for x in arr]
    return items, p, {"n_attempts": sum(len(by[i]) for i in items), "n_arrivals": len(arr),
                      "p_succ_given_arrival": float(np.mean([x["success"] for x in arr])) if arr else None,
                      "rem_q10": float(np.quantile(rem, .1)) if rem else None,
                      "rem_q50": float(np.quantile(rem, .5)) if rem else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()
    B = Path(a.batch)
    evals, layouts = [], {}
    for s in (0, 1):
        for arm in ARMS:
            d = B / f"e1-K3-u16000-s{s}-{arm}-to501760"
            if not (d / "summary.json").exists():
                continue
            sm = json.loads((d / "summary.json").read_text())
            assert sm["arm"] == arm and sm["seed"] == s and sm["continuation_actions"] == 501760
            for e in sm["evals"]:
                items, p, x = per_layout(d / f"attempts_{e['tag']}.jsonl")
                assert abs(p.mean() - e["P1"]) < 1e-12
                key = (s, arm, e["actions"], "new")
                assert key not in layouts
                layouts[key] = (items, p)
                evals.append({"seed": s, "arm": arm, "post_probe_actions": e["actions"], "run": "new", "job": d.name,
                              "attempts_per_layout": e["attempts"], "P1": e["P1"], "q": e["q"], "c": e["c"],
                              "C4": e["C4"], "R4": e["R4"], **x})
            od = RUNS / ORIG[arm].format(s=s)
            om = json.loads((od / "summary.json").read_text())
            assert om["arm"] == arm and om["seed"] == s and om["K"] == 3 and om["bc_update"] == 16000
            items, p, x = per_layout(od / "attempts_final.jsonl")
            layouts[(s, arm, 251904, "m3")] = (items, p)
            evals.append({"seed": s, "arm": arm, "post_probe_actions": 251904, "run": "m3_original", "job": od.name,
                          "attempts_per_layout": 8, "P1": om["final"]["P1"], "q": om["final"]["q"], "c": om["final"]["c"],
                          "C4": om["final"]["C4"], "R4": om["final"]["R4"], **x})
    rng = np.random.default_rng(20261031)
    contr = []
    for s in (0, 1):
        for t, run in ((251904, "m3"), (251904, "new"), (501760, "new")):
            if not all((s, arm, t, run) in layouts for arm in ARMS):
                continue
            items = layouts[(s, "00", t, run)][0]
            assert all(layouts[(s, arm, t, run)][0] == items for arm in ARMS)
            P = {arm: layouts[(s, arm, t, run)][1] for arm in ARMS}
            idx = rng.integers(0, len(items), size=(2000, len(items)))
            for name, f in CONTRASTS.items():
                per = f(P)
                boot = per[idx].mean(1)
                contr.append({"seed": s, "post_probe_actions": t, "run": run, "contrast": name, "estimate": float(per.mean()),
                              "layout_ci_lo": float(np.quantile(boot, .025)), "layout_ci_hi": float(np.quantile(boot, .975))})
    reps = []
    for s in (0, 1):
        for arm in ARMS:
            if (s, arm, 251904, "new") in layouts:
                n, o = layouts[(s, arm, 251904, "new")][1], layouts[(s, arm, 251904, "m3")][1]
                reps.append({"seed": s, "arm": arm, "new_minus_original_P1": float(n.mean() - o.mean())})
    out = Path(a.out)
    for name, rows in (("dev2_long_evals.csv", evals), ("dev2_long_contrasts.csv", contr), ("dev2_path_repeats.csv", reps)):
        if rows:
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
    print(f"{len(evals)} evaluations, {len(contr)} contrast rows, {len(reps)} path repeats")


if __name__ == "__main__":
    main()
