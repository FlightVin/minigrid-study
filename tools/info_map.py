"""Condition-level information map for the selected M3 arms (development data).

Usage: .venv/bin/python tools/info_map.py [--out reports/m3_info_map.csv]

Reads reports/m3_manifest.csv (from tools/audit_m3.py) to pick rows by explicit role; never by order.
One row per (fork, arm) for the selected arms and the arm-00 repeat, with:
  pi0 / post-probe p, q, c, delta-c (probe summary; dev_eval 32 x 4, dev_bank 64 x 2);
  final p, q, c (dev_eval 32 x 8, dev_bank 64 x 2);
  arrival time tau and remaining time at first crossing (normal attempts), P(success | arrival);
  training counters (successes, normal / assisted episodes, realized assisted-episode fraction);
  update statistics averaged over the continuation (suffix-step and assisted-step fractions, anchor KL,
  PPO approx KL, clip fraction, actor grad norm before clipping, explained variance);
  critic pre-fit calibration (held-out MSE vs constant) from the probe.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"


def q(v, p):
    return float(np.quantile(v, p)) if len(v) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports/m3_info_map.csv"))
    a = ap.parse_args()
    man = list(csv.DictReader(open(ROOT / "reports/m3_manifest.csv")))
    probes = {r["probe_job"]: r for r in man if r["role"] == "probe"}
    rows = []
    for r in man:
        if r["role"] not in ("selected", "repeat"):
            continue
        d = RUNS / r["batch"] / r["job"]
        s = json.loads((d / "summary.json").read_text())
        pr = probes[r["probe_job"]]
        ps = json.loads((RUNS / pr["batch"] / pr["job"] / "summary.json").read_text())
        att = [json.loads(l) for l in (d / "attempts_final.jsonl").read_text().splitlines()]
        normal = [x for x in att if x["kind"] == "normal"]
        arr = [x for x in normal if x["arrival"]]
        tau = [x["arrival"]["tau"] for x in arr]
        rem = [x["arrival"]["remaining"] for x in arr]
        upd = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if '"phase": "branch"' in l]
        m = lambda k: float(np.mean([u[k] for u in upd if u.get(k) is not None]))
        c = s["counters"]
        pc = ps["counters"]
        cp = ps["critic_prefit"]
        rows.append({
            "K": r["K"], "bc_update": r["bc_update"], "seed": r["seed"], "arm": r["arm"], "role": r["role"],
            "pi0_p": ps["pi0"]["p"], "pi0_q": ps["pi0"]["q"], "pi0_c": ps["pi0"]["c"],
            "probe_p": ps["probe"]["p"], "probe_q": ps["probe"]["q"], "probe_c": ps["probe"]["c"],
            "delta_c": ps["delta_c"],
            "final_p": s["final"]["P1"], "final_q": s["final"]["q"], "final_c": s["final"]["c"],
            "final_c_entry": s["final"]["bins"]["entry"], "final_c_retrieval": s["final"]["bins"]["retrieval"],
            "final_c_carrying": s["final"]["bins"]["carrying"],
            "n_attempts": len(normal), "n_arrivals": len(arr),
            "p_succ_given_arrival": float(np.mean([x["success"] for x in arr])) if arr else None,
            "tau_q10": q(tau, .1), "tau_q50": q(tau, .5), "tau_q90": q(tau, .9),
            "rem_q10": q(rem, .1), "rem_q50": q(rem, .5), "rem_q90": q(rem, .9),
            "train_successes": c["successes"] - pc["successes"],
            "train_episodes": c["episodes"] - pc["episodes"],
            "normal_episodes": c["normal_episodes"] - pc["normal_episodes"],
            "normal_successes": c["normal_successes"] - pc["normal_successes"],
            "assisted_episodes": c["assisted_episodes"] - pc["assisted_episodes"],
            "assisted_successes": c["assisted_successes"] - pc["assisted_successes"],
            "assisted_episode_frac": (c["assisted_episodes"] - pc["assisted_episodes"]) / max(1, c["episodes"] - pc["episodes"]),
            "frac_assisted_steps": m("frac_assisted_steps"), "frac_suffix_steps": m("frac_suffix_steps"),
            "anchor_kl_mean": m("anchor_kl"), "anchor_kl_last": upd[-1]["anchor_kl"],
            "approx_kl_mean": m("approx_kl"), "clipfrac_mean": m("clipfrac"),
            "grad_norm_actor_mean": m("grad_norm_actor"), "explained_var_mean": m("explained_var"),
            "critic_test_mse": cp.get("test_mse"), "critic_const_mse": cp.get("test_mse_constant"),
            "continuation_actions": s["continuation_actions"],
        })
    rows.sort(key=lambda x: (x["K"], x["bc_update"], x["seed"], x["role"], x["arm"]))
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {a.out}")


if __name__ == "__main__":
    main()
