"""Collect branch results and paired contrasts from one or more batches.

Usage: .venv/bin/python tools/summarize_branches.py .mae/runs/<batch> [...] [--csv branches.csv] [--contrasts c.csv]

Rows: one per branch (K, BC update, seed, arm, fork hash, final P1/q/c/C4/R4, actions).
Contrasts (per K, BC update, seed with all four arms present and one shared fork; replicate jobs
ending in "-rep" are excluded and reported as replicate-minus-original differences of arm 00):
  reset Y10-Y00, preserve Y01-Y00, combined Y11-Y00, interaction (Y11-Y01)-(Y10-Y00),
  Y11-Y10, Y11-Y01.
"""
import argparse
import csv
import json
from pathlib import Path


def load(batches):
    rows = []
    for b in batches:
        for d in sorted(Path(b).iterdir()):
            s = d / "summary.json"
            if not s.exists():
                continue
            s = json.loads(s.read_text())
            if s.get("mode") != "branch":
                continue
            cfg = json.loads((d / "config.resolved.json").read_text())
            f = s["final"]
            rows.append({"batch": Path(b).name, "job": d.name, "variant": cfg.get("variant", ""), "K": s["K"],
                         "bc_update": s["bc_update"], "seed": s["seed"], "arm": s["arm"], "alpha": cfg["alpha"],
                         "kl_coef": cfg["kl_coef"], "fork_hash": s["fork_hash"][:16], "P1": f["P1"], "q": f["q"],
                         "c": f["c"], "C4": f["C4"], "R4": f["R4"], "succ_given_arrival": f["P_success_given_arrival"],
                         "continuation_actions": s["continuation_actions"],
                         "eval_actions": s["actions"]["eval_diagnostic"] + s["actions"]["eval_final"],
                         "wall_s": round(s["wall_seconds"])})
    return rows


def contrasts(rows):
    groups = {}
    for r in rows:
        if r["job"].endswith("-rep"):
            continue
        groups.setdefault((r["K"], r["bc_update"], r["seed"], r["fork_hash"]), {})[r["arm"]] = r["P1"]
    out = []
    for (K, u, seed, fh), y in sorted(groups.items()):
        if set(y) != {"00", "10", "01", "11"}:
            continue
        out.append({"K": K, "bc_update": u, "seed": seed, "fork_hash": fh,
                    "reset": y["10"] - y["00"], "preserve": y["01"] - y["00"], "combined": y["11"] - y["00"],
                    "interaction": (y["11"] - y["01"]) - (y["10"] - y["00"]),
                    "combined_vs_reset": y["11"] - y["10"], "combined_vs_preserve": y["11"] - y["01"]})
    return out


def replicates(rows):
    orig = {(r["fork_hash"], r["arm"]): r["P1"] for r in rows if not r["job"].endswith("-rep")}
    return [{"K": r["K"], "bc_update": r["bc_update"], "seed": r["seed"], "arm": r["arm"], "fork_hash": r["fork_hash"],
             "rep_minus_orig": r["P1"] - orig[(r["fork_hash"], r["arm"])]}
            for r in rows if r["job"].endswith("-rep") and (r["fork_hash"], r["arm"]) in orig]


def write(path, rows):
    if rows:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batches", nargs="+")
    ap.add_argument("--csv")
    ap.add_argument("--contrasts")
    a = ap.parse_args()
    rows = load(a.batches)
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
    keys = ["variant", "K", "bc_update", "seed", "arm", "alpha", "kl_coef", "P1", "q", "c", "C4", "R4", "continuation_actions"]
    print(" ".join(keys))
    for r in rows:
        print(" ".join(fmt(r[k]) for k in keys))
    cs = contrasts(rows)
    for c in cs:
        print("contrast", " ".join(f"{k}={fmt(v)}" for k, v in c.items()))
    for r in replicates(rows):
        print("replicate", " ".join(f"{k}={fmt(v)}" for k, v in r.items()))
    if a.csv:
        write(a.csv, rows)
    if a.contrasts:
        write(a.contrasts, cs)


if __name__ == "__main__":
    main()
