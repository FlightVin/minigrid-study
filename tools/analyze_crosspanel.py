"""Cross-panel study analysis (PROTOCOL_FREEZE Amendment 4, E1; exploratory). Written before any cross-panel data.

Usage: .venv/bin/python tools/analyze_crosspanel.py [--runs .mae/runs] [--out reports/crosspanel]

Jobs xp-{cohort}-s{S}-{00|01} (cohort m4: seeds 10-14; r1: seeds 15-22) evaluate the saved 501,760 actor of the
K=3/early-BC branch on conf_final (64 K=3 layouts) and r1_final (128 K=3 layouts), 4 attempts each, eval seed 969000.
Metrics are recomputed from attempts_crosspanel_<panel>.jsonl and must equal the job summary.

Per cohort x panel cell (4 cells), seed is the unit: mean P1 of arm 00 and arm 01, the paired effect d = 01 - 00
(mean, seed SD, 95% t-interval, n positive), q, r = P(success | arrival), C4/R4 (4 attempts), and the exact
decomposition of d into access and completion parts. Contrasts (descriptive): within a panel, cohort difference in
mean d and in seed SD; within a cohort, panel difference in mean d (paired by seed) and in baseline P1.
Repeatability (descriptive): each cohort on its own panel, new seed versus the original final record.
No p-value is used for a decision. These are already observed policies and panels, not a replication.
Outputs: crosspanel_policies.csv, crosspanel_cells.csv, crosspanel_summary.json.
"""
import argparse
import csv
import json
from math import comb
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COHORTS = {"m4": tuple(range(10, 15)), "r1": tuple(range(15, 23))}
PANELS = {"conf_final": 64, "r1_final": 128}
OWN = {"m4": "conf_final", "r1": "r1_final"}
ARMS = ("00", "01")
ATT = 4


def metrics(rows, n_items):
    by = {}
    for r in rows:
        by.setdefault(r["item"], []).append(r)
    assert sorted(by) == list(range(n_items)) and all(len(v) == ATT for v in by.values())
    z = np.array([sum(r["success"] for r in by[i]) for i in range(n_items)], float)
    a = np.array([sum(r["accessed"] and not r["start_accessed"] for r in by[i]) for i in range(n_items)], float)
    for r in rows:
        assert r["K"] == 3 and (not r["success"] or r["arrival"] is not None)
    return {"P1": float(z.mean() / ATT), "q": float(a.mean() / ATT), "r": float(z.sum() / a.sum()) if a.sum() else None,
            "C4": float(np.mean([1 - comb(ATT - int(k), 4) / comb(ATT, 4) for k in z])),
            "R4": float(np.mean([comb(int(k), 4) / comb(ATT, 4) for k in z])), "p_items": (z / ATT).tolist()}


def original_final(branch_dir):
    sm = json.loads((Path(branch_dir) / "summary.json").read_text())
    e = next(x for x in sm["evals"] if x["tag"] == "final_501760")
    return e["P1"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--out", default=str(ROOT / "reports/crosspanel"))
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for d in sorted(runs.glob("*/xp-*")):
        if (d / "summary.json").exists():
            assert d.name not in jobs, f"duplicate job {d.name}"
            jobs[d.name] = d
    P, rows, problems, missing = {}, [], [], []
    for co, seeds in COHORTS.items():
        for s in seeds:
            for arm in ARMS:
                d = jobs.get(f"xp-{co}-s{s}-{arm}")
                if d is None:
                    missing.append(f"{co} s{s} {arm}")
                    continue
                sm = json.loads((d / "summary.json").read_text())
                if (sm["seed"], sm["arm"], sm["K"], sm["bc_update"], sm["policy_actions"], sm["eval_seed"], sm["attempts"]) != \
                        (s, arm, 3, 4000, 501760, 969000, ATT):
                    problems.append(f"identity {d.name}")
                for pn, n in PANELS.items():
                    recs = [json.loads(l) for l in (d / f"attempts_crosspanel_{pn}.jsonl").read_text().splitlines() if l.strip()]
                    m = metrics(recs, n)
                    sp = sm["panels"][pn]
                    if abs(sp["P1"] - m["P1"]) > 1e-12 or abs(sp["q"] - m["q"]) > 1e-12:
                        problems.append(f"summary mismatch {d.name} {pn}")
                    P[(co, s, arm, pn)] = m
                    rows.append({"cohort": co, "seed": s, "arm": arm, "panel": pn, "job": f"{d.parent.name}/{d.name}",
                                 **{k: m[k] for k in ("P1", "q", "r", "C4", "R4")},
                                 "original_final_P1_own_panel": original_final(sm["branch"]) if pn == OWN[co] else None})
    cells, D = {}, {}
    for co, seeds in COHORTS.items():
        for pn in PANELS:
            ok = [s for s in seeds if all((co, s, arm, pn) in P for arm in ARMS)]
            if len(ok) < 2:
                continue
            g = lambda arm, k: [P[(co, s, arm, pn)][k] for s in ok]
            d = np.array(g("01", "P1")) - np.array(g("00", "P1"))
            D[(co, pn)] = dict(zip(ok, d))
            dec = []
            for s in ok:
                x, y = P[(co, s, "01", pn)], P[(co, s, "00", pn)]
                if x["r"] is not None and y["r"] is not None:
                    dec.append(((x["q"] - y["q"]) * (x["r"] + y["r"]) / 2, (x["r"] - y["r"]) * (x["q"] + y["q"]) / 2))
            cells[f"{co}/{pn}"] = {
                "n": len(ok), "P1_00": float(np.mean(g("00", "P1"))), "P1_01": float(np.mean(g("01", "P1"))),
                "d": R.t_test(d), "d_n_positive": int((d > 0).sum()),
                "q_00": float(np.mean(g("00", "q"))), "q_01": float(np.mean(g("01", "q"))),
                "C4_00": float(np.mean(g("00", "C4"))), "C4_01": float(np.mean(g("01", "C4"))),
                "R4_00": float(np.mean(g("00", "R4"))), "R4_01": float(np.mean(g("01", "R4"))),
                "access_part_mean": float(np.mean([x for x, _ in dec])) if dec else None,
                "completion_part_mean": float(np.mean([y for _, y in dec])) if dec else None,
                "decomposition_n": len(dec)}
    contrasts = {}
    for pn in PANELS:
        if ("m4", pn) in D and ("r1", pn) in D:
            a_, b_ = np.array(list(D[("m4", pn)].values())), np.array(list(D[("r1", pn)].values()))
            contrasts[f"cohort_r1_minus_m4_on_{pn}"] = {"mean_d": float(b_.mean() - a_.mean()),
                                                         "sd_d_m4": float(a_.std(ddof=1)), "sd_d_r1": float(b_.std(ddof=1)),
                                                         "baseline_00": cells[f"r1/{pn}"]["P1_00"] - cells[f"m4/{pn}"]["P1_00"]}
    for co in COHORTS:
        if (co, "conf_final") in D and (co, "r1_final") in D:
            ss = sorted(set(D[(co, "conf_final")]) & set(D[(co, "r1_final")]))
            x = [D[(co, "r1_final")][s] - D[(co, "conf_final")][s] for s in ss]
            contrasts[f"panel_r1_minus_conf_within_{co}"] = {"d_change": R.t_test(x) if len(x) >= 2 else None,
                                                             "baseline_00_change": cells[f"{co}/r1_final"]["P1_00"] - cells[f"{co}/conf_final"]["P1_00"]}
    repeat = {}
    for co in COHORTS:
        pn = OWN[co]
        pairs = [(r["P1"], r["original_final_P1_own_panel"]) for r in rows if r["cohort"] == co and r["panel"] == pn]
        if pairs:
            x = np.array(pairs)
            repeat[co] = {"panel": pn, "n_policies": len(x), "mean_new": float(x[:, 0].mean()), "mean_original": float(x[:, 1].mean()),
                          "mean_abs_diff": float(np.abs(x[:, 0] - x[:, 1]).mean()), "corr": float(np.corrcoef(x.T)[0, 1]) if len(x) > 2 else None}
    res = {"cells": cells, "contrasts": contrasts, "repeatability_own_panel": repeat, "missing": missing,
           "problems": problems, "status": "exploratory; already observed policies and panels; not a replication"}
    (out / "crosspanel_summary.json").write_text(json.dumps(res, indent=1, default=float))
    if rows:
        with open(out / "crosspanel_policies.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(json.dumps({"cells": {k: {"P1_00": v["P1_00"], "P1_01": v["P1_01"], "d": v["d"]["estimate"], "sd": v["d"]["sd"]}
                                for k, v in cells.items()}, "missing": missing, "problems": problems}, indent=1, default=float))
    return res


if __name__ == "__main__":
    main()
