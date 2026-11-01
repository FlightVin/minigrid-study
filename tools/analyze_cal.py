"""Initialization-calibration analysis and frozen selection rule (PROTOCOL_FREEZE Amendment 5, C). Written before
any calibration training. Development only.

Usage: .venv/bin/python tools/analyze_cal.py [--runs .mae/runs] [--out reports/cal]

Jobs cal-bc-p{2|5|8}-s{67|68|69}: BC with prefix-sampling probability rho = 0.2 / 0.5 / 0.8 within each K (K-balanced
batches), checkpoints 4000 and 8000 on one path. Each checkpoint is evaluated by the BC job itself on bc_val (50
layouts per K x 4 attempts, eval seed 525000) and dev_bank (64 states per K x 4 attempts: 32 entry, 16 retrieval,
16 carrying). Metrics are recomputed here from attempts_u<update>.jsonl and must equal the job's metrics record.

Per seed, variant (rho, update) and K: normal-start P1 and access q (fraction of attempts with an actual arrival at
the stage boundary); fixed-bank boundary-entry competence (entry bin), retrieval and carrying, and the mixed bank c.
Variant value = mean over the three seeds (every seed is kept; per-seed values and counts are reported).

Frozen development targets (feasibility, not confirmation), all on the three-seed means:
  K=1 access q >= 0.75;  K=3 access 0.05 <= q <= 0.40;  entry competence >= 0.55 for K=1 and for K=3;
  room for full-task learning: normal-start P1 <= 0.60 for K=1 and for K=3.
Selection among qualifying variants (fixed before training): fewer BC updates first (4000 before 8000), then rho
closest to 0.5, then the smaller rho. If no variant qualifies, none is selected; the report states which targets
fail and by how much. No intervention outcome is used.
Outputs: reports/cal/cal_variants.csv, cal_summary.json.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (67, 68, 69)
RHOS = {2: 0.2, 5: 0.5, 8: 0.8}
UPDATES = (4000, 8000)
BINS = ("entry", "retrieval", "carrying")
TARGET = {"K1_q_min": 0.75, "K3_q_min": 0.05, "K3_q_max": 0.40, "entry_min": 0.55, "P1_max": 0.60}


def metrics(path, rec):
    rows = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    out = {}
    for K in (1, 3):
        nrm = [r for r in rows if r["kind"] == "normal" and r["K"] == K]
        bank = [r for r in rows if r["kind"] == "bank" and r["bank_K"] == K]
        assert len(nrm) == 200 and len(bank) == 256, (path, K, len(nrm), len(bank))
        m = {"P1": float(np.mean([r["success"] for r in nrm])), "q": float(np.mean([r["arrival"] is not None for r in nrm])),
             "c": float(np.mean([r["success"] for r in bank]))}
        for b in BINS:
            m[b] = float(np.mean([r["success"] for r in bank if r["bin"] == b]))
        assert abs(m["P1"] - rec[f"normal_K{K}"]["P1"]) < 1e-12 and abs(m["c"] - rec[f"bank_K{K}"]["P1"]) < 1e-12, path
        for b in BINS:
            assert abs(m[b] - rec[f"bank_K{K}_{b}"]) < 1e-12, (path, b)
        out[K] = m
    return out


def qualifies(v):
    fails = {}
    if v[1]["q"] < TARGET["K1_q_min"]:
        fails["K1_access"] = v[1]["q"] - TARGET["K1_q_min"]
    if not TARGET["K3_q_min"] <= v[3]["q"] <= TARGET["K3_q_max"]:
        fails["K3_access"] = v[3]["q"] - (TARGET["K3_q_min"] if v[3]["q"] < TARGET["K3_q_min"] else TARGET["K3_q_max"])
    for K in (1, 3):
        if v[K]["entry"] < TARGET["entry_min"]:
            fails[f"K{K}_entry"] = v[K]["entry"] - TARGET["entry_min"]
        if v[K]["P1"] > TARGET["P1_max"]:
            fails[f"K{K}_room"] = v[K]["P1"] - TARGET["P1_max"]
    return not fails, fails


def select(variants):
    """variants: {(rho, update): (qualifies, ...)}; fixed order: update, |rho - 0.5|, rho."""
    ok = [k for k, v in variants.items() if v[0]]
    return min(ok, key=lambda k: (k[1], abs(k[0] - 0.5), k[0])) if ok else None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--out", default=str(ROOT / "reports/cal"))
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for d in sorted(runs.glob("*/cal-bc-*")):
        if (d / "summary.json").exists():
            assert d.name not in jobs, f"duplicate job {d.name}"
            jobs[d.name] = d
    per, rows, missing, problems = {}, [], [], []
    for p, rho in RHOS.items():
        for s in SEEDS:
            d = jobs.get(f"cal-bc-p{p}-s{s}")
            if d is None:
                missing.append(f"rho {rho} seed {s}")
                continue
            cf = json.loads((d / "config.resolved.json").read_text())
            if (cf.get("prefix_prob"), cf["seed"], cf["checkpoints"], cf["eval_seed"], cf["dataset_id"]) != (rho, s, [4000, 8000], 525000, "conf-v1"):
                problems.append(f"config {d.name}")
            recs = {r["update"]: r for r in (json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip())}
            for u in UPDATES:
                m = metrics(d / f"attempts_u{u}.jsonl", recs[u])
                per[(rho, u, s)] = m
                rows.append({"rho": rho, "update": u, "seed": s, "job": f"{d.parent.name}/{d.name}",
                             **{f"K{K}_{k}": m[K][k] for K in (1, 3) for k in ("P1", "q", "c") + BINS}})
    variants = {}
    for rho in RHOS.values():
        for u in UPDATES:
            ss = [s for s in SEEDS if (rho, u, s) in per]
            if len(ss) < len(SEEDS):
                continue                  # a variant needs all three seeds; no seed is dropped to qualify
            v = {K: {k: float(np.mean([per[(rho, u, s)][K][k] for s in ss])) for k in ("P1", "q", "c") + BINS} for K in (1, 3)}
            q, fails = qualifies(v)
            seeds_meeting = sum(qualifies(per[(rho, u, s)])[0] for s in ss)
            variants[(rho, u)] = (q, fails, v, seeds_meeting)
    chosen = select(variants)
    res = {"targets": TARGET, "missing": missing, "problems": problems,
           "variants": {f"rho{rho}/u{u}": {"qualifies": v[0], "shortfalls": v[1], "means": v[2], "seeds_meeting_all_targets": v[3]}
                        for (rho, u), v in variants.items()},
           "selected": None if chosen is None else {"rho": chosen[0], "update": chosen[1]},
           "rule": "qualifying variants ordered by BC updates, then |rho - 0.5|, then rho; all three seeds kept"}
    (out / "cal_summary.json").write_text(json.dumps(res, indent=1))
    if rows:
        with open(out / "cal_variants.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(json.dumps({"selected": res["selected"], "missing": missing, "problems": problems,
                      "qualifying": [k for k, v in res["variants"].items() if v["qualifies"]]}, indent=1))
    return res


if __name__ == "__main__":
    main()
