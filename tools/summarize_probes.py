"""Tabulate probe jobs in a batch: pi0 and post-probe p/q/c, training successes, update statistics.

Usage: .venv/bin/python tools/summarize_probes.py .mae/runs/<batch> [--csv out.csv]
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch")
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = []
    for d in sorted(Path(a.batch).iterdir()):
        s = d / "summary.json"
        if not s.exists():
            continue
        s = json.loads(s.read_text())
        if s.get("mode") != "probe":
            continue
        cfg = json.loads((d / "config.resolved.json").read_text())
        tr = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if '"phase": "probe"' in l]
        c = s["counters"]
        rows.append({
            "job": d.name, "variant": cfg.get("variant", ""), "K": s["K"], "bc_update": s["bc_update"], "seed": s["seed"],
            "p0": s["pi0"]["p"], "q0": s["pi0"]["q"], "c0": s["pi0"]["c"],
            "p1": s["probe"]["p"], "q1": s["probe"]["q"], "c1": s["probe"]["c"], "delta_c": s["delta_c"],
            "train_succ": c["successes"], "train_eps": c["episodes"],
            "approx_kl_first": tr[0]["approx_kl"], "approx_kl_mean": float(np.mean([r["approx_kl"] for r in tr])),
            "entropy_last": tr[-1]["entropy"], "anchor_kl_last": tr[-1]["anchor_kl"],
            "critic_test_mse": s["critic_prefit"].get("test_mse"), "critic_const_mse": s["critic_prefit"].get("test_mse_constant"),
            "probe_wall_s": round(s["probe_wall_seconds"]),
        })
    keys = list(rows[0])
    fmt = lambda v: f"{v:.3f}" if isinstance(v, float) else str(v)
    print(" | ".join(keys))
    for r in rows:
        print(" | ".join(fmt(r[k]) for k in keys))
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
