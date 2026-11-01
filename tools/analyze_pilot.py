"""Calibrated-regime pilot analysis (PROTOCOL_FREEZE Amendment 5, E; exploratory). Committed before any pilot run.

Usage: .venv/bin/python tools/analyze_pilot.py [--runs .mae/runs] [--out reports/pilot] [--check-states]

Jobs pl-probe-K{1|3}-s{S} and pl-K{K}-s{S}-{00|10|01s|11s}, seeds 67-69, forked from the calibration BC variant
selected by tools/analyze_cal.py. Evaluation at 251,904 only: pl_final (64 layouts of the condition's K x 4
attempts) and pl_bank (64 states x 4: 32 entry, 16 retrieval, 16 carrying), eval seed 989000. Metrics are
recomputed from attempts_pilot_251904.jsonl and must equal the summary.

Per K, seed and arm (no p-values used for decisions; 3 seeds; 95% t-intervals with df 2 are wide):
- normal-start P1, access q, r = P(success | actual arrival), mixed bank c and entry/retrieval/carrying, their change
  from pi0 and the post-probe policy on the same bank states (probe diagnostics on pl_select / pl_bank);
- arrival timing (tau, remaining time) and inventory at arrival;
- training: normal and assisted episodes and success rates kept separate (assisted access is never pooled with
  normal-start access), fraction of assisted steps, fraction of suffix steps, anchor KL by stage, applied penalty,
  update size (actor parameter-change norm; successive-policy KL on fixed prefix / suffix anchor rows);
- compute: environment actions by role and wall time.
Contrasts per K: 10-00 (resets), 01s-00 (suffix preservation), 11s-00 (both), interaction 11s-10-01s+00; the exact
access/completion decomposition of each arm vs 00. Across K: difference of each contrast (K1 minus K3), per seed.
RQ2 descriptors (hindsight, descriptive): the best arm per K by mean P1, the best single fixed arm over both K, the
hindsight headroom (mean over K of best-per-K P1 minus the best fixed arm's mean P1), and whether a condition-identity
rule (choose by K) differs from the best fixed arm. These describe 3 seeds x 2 conditions; they are not a rule.
Outputs: pilot_branches.csv, pilot_summary.json.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (67, 68, 69)
KS = (1, 3)
ARMS = ("00", "10", "01s", "11s")
IDENT = {"00": (0.0, 0.0, "both"), "10": (0.25, 0.0, "both"), "01s": (0.0, 0.01, "suffix"), "11s": (0.25, 0.01, "suffix")}
TAG, AT = "pilot_251904", 251904
N_ITEMS, N_ATT, N_BANK, N_BANK_ATT = 64, 4, 64, 4
BINS = ("entry", "retrieval", "carrying")
CONTRASTS = {"10-00": {"10": 1, "00": -1}, "01s-00": {"01s": 1, "00": -1}, "11s-00": {"11s": 1, "00": -1},
             "interaction": {"11s": 1, "10": -1, "01s": -1, "00": 1}}
TRAIN = ("anchor_kl", "anchor_kl_prefix", "anchor_kl_suffix", "anchor_penalty", "update_kl_prefix", "update_kl_suffix",
         "actor_update_norm", "approx_kl", "entropy", "frac_suffix_steps", "frac_assisted_steps")


def record(d, sm, K):
    e = next(x for x in sm["evals"] if x["tag"] == TAG)
    rows = [json.loads(l) for l in (d / f"attempts_{TAG}.jsonl").read_text().splitlines() if l.strip()]
    normal, bank = {}, {}
    for r in rows:
        (normal if r["kind"] == "normal" else bank).setdefault(r["item"], []).append(r)
    assert sorted(normal) == list(range(N_ITEMS)) and all(len(v) == N_ATT for v in normal.values()), d.name
    assert sorted(bank) == list(range(N_BANK)) and all(len(v) == N_BANK_ATT for v in bank.values()), d.name
    assert all(r["K"] == K and ((not r["success"]) or r["arrival"] is not None) for v in normal.values() for r in v), d.name
    z = np.array([sum(r["success"] for r in normal[i]) for i in range(N_ITEMS)], float)
    a = np.array([sum(r["arrival"] is not None for r in normal[i]) for i in range(N_ITEMS)], float)
    arr = [r["arrival"] for v in normal.values() for r in v if r["arrival"]]
    bins = {b: [] for b in BINS}
    for i in sorted(bank):
        bins[bank[i][0]["bin"]].append(np.mean([r["success"] for r in bank[i]]))
    inv = {}
    for x in arr:
        k = "+".join(map(str, x["carrying"])) if x["carrying"] else "nothing"
        inv[k] = inv.get(k, 0) + 1
    rec = {"P1": float(z.mean() / N_ATT), "q": float(a.sum() / (N_ITEMS * N_ATT)),
           "r": float(z.sum() / a.sum()) if a.sum() else None,
           "c": float(np.mean([np.mean([r["success"] for r in v]) for v in bank.values()])),
           "bins": {b: float(np.mean(v)) for b, v in bins.items()}, "limits": [normal[i][0]["limit"] for i in range(N_ITEMS)],
           "arrival_tau_mean": float(np.mean([x["tau"] for x in arr])) if arr else None,
           "arrival_remaining_mean": float(np.mean([x["remaining"] for x in arr])) if arr else None, "inventory": inv}
    for m in ("P1", "q", "c"):
        assert abs(rec[m] - e[m]) < 1e-12, (d.name, m)
    return rec


def training(d):
    recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
    tr = [r for r in recs if r.get("phase") == "branch"]
    out = {}
    for k in TRAIN:
        v = [r[k] for r in tr if r.get(k) is not None]
        out[f"{k}_mean"] = float(np.mean(v)) if v else None
    c0, c1 = tr[0]["counters"], tr[-1]["counters"]
    dif = lambda k: c1[k] - c0[k]
    out["normal_episodes"], out["assisted_episodes"] = dif("normal_episodes"), dif("assisted_episodes")
    out["normal_success_rate"] = dif("normal_successes") / out["normal_episodes"] if out["normal_episodes"] else None
    out["normal_access_rate"] = dif("normal_accessed") / out["normal_episodes"] if out["normal_episodes"] else None
    out["assisted_success_rate"] = dif("assisted_successes") / out["assisted_episodes"] if out["assisted_episodes"] else None
    return out


def tstats(v):
    v = [x for x in v if x is not None]
    return {**(R.t_test(v) if len(v) >= 2 else {"n": len(v)}), "per_seed": v}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--out", default=str(ROOT / "reports/pilot"))
    ap.add_argument("--check-states", action="store_true")
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for d in sorted(runs.glob("*/pl-*")):
        if (d / "summary.json").exists():
            assert d.name not in jobs, f"duplicate job {d.name}"
            jobs[d.name] = d
    X, T, probes, rows, problems, missing, panels = {}, {}, {}, [], [], [], {}
    for K in KS:
        for s in SEEDS:
            pj = jobs.get(f"pl-probe-K{K}-s{s}")
            if pj is None:
                missing.append(f"probe K{K} s{s}")
                continue
            ps = json.loads((pj / "summary.json").read_text())
            pc = json.loads((pj / "config.resolved.json").read_text())
            if (ps["K"], ps["seed"], pc["diag_role"], pc["eval_role"], pc["bank_role"], pc["dataset_id"]) != \
                    (K, s, "pl_select", "pl_final", "pl_bank", "r3-v1"):
                problems.append(f"probe identity {pj.name}")
            probes[(K, s)] = ps
            for arm in ARMS:
                d = jobs.get(f"pl-K{K}-s{s}-{arm}")
                if d is None:
                    missing.append(f"K{K} s{s} {arm}")
                    continue
                sm = json.loads((d / "summary.json").read_text())
                alpha, coef, comp = IDENT[arm]
                if (sm["K"], sm["seed"], sm["alpha"], sm["kl_coef"], sm["anchor_component"], sm["fork_hash"], sm["probe_run"]) != \
                        (K, s, alpha, coef, comp, ps["fork_hash"], str(pj)):
                    problems.append(f"branch identity/lineage {d.name}")
                if a.check_states:
                    import torch
                    sys.path.insert(0, str(ROOT / "src"))
                    from bc2rl import ppo as PP
                    st = torch.load(d / f"state_{AT}.pt", map_location="cpu", weights_only=False)
                    if not PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(AT)]:
                        problems.append(f"state hash {d.name}")
                rec = record(d, sm, K)
                panels.setdefault(K, rec["limits"])
                if rec["limits"] != panels[K]:
                    problems.append(f"panel differs {d.name}")
                X[(K, s, arm)] = rec
                T[(K, s, arm)] = {**training(d), "env_actions": sum(sm["actions"].values()), "wall_seconds": sm["wall_seconds"]}
                rows.append({"K": K, "seed": s, "arm": arm, "job": f"{d.parent.name}/{d.name}",
                             **{m: rec[m] for m in ("P1", "q", "r", "c", "arrival_tau_mean", "arrival_remaining_mean")},
                             **{f"bank_{b}": rec["bins"][b] for b in BINS},
                             "c_change_from_pi0": rec["c"] - ps["pi0"]["c"], "c_change_from_probe": rec["c"] - ps["probe"]["c"],
                             "entry_change_from_pi0": rec["bins"]["entry"] - ps["pi0"]["bins"]["entry"],
                             "entry_change_from_probe": rec["bins"]["entry"] - ps["probe"]["bins"]["entry"],
                             **{f"train_{k}": v for k, v in T[(K, s, arm)].items()}})
    res = {"status": "exploratory pilot; 3 seeds x 2 conditions; no rule is established", "missing": missing,
           "problems": problems, "conditions": {}}
    for K in KS:
        ss = [s for s in SEEDS if all((K, s, arm) in X for arm in ARMS)]
        if not ss:
            continue
        blk = {"seeds": ss, "probe": {s: {k: probes[(K, s)][k] for k in ("pi0", "probe")} for s in ss}, "arms": {}, "contrasts": {}}
        for arm in ARMS:
            g = lambda f: float(np.mean([f(X[(K, s, arm)]) for s in ss]))
            blk["arms"][arm] = {"P1": g(lambda r: r["P1"]), "q": g(lambda r: r["q"]), "c": g(lambda r: r["c"]),
                                "bins": {b: g(lambda r, b=b: r["bins"][b]) for b in BINS},
                                "training": {k: (float(np.mean([T[(K, s, arm)][k] for s in ss if T[(K, s, arm)][k] is not None]))
                                                 if any(T[(K, s, arm)][k] is not None for s in ss) else None)
                                             for k in T[(K, ss[0], arm)]}}
        for name, w in CONTRASTS.items():
            cb = {}
            for m, get in (("P1", lambda r: r["P1"]), ("q", lambda r: r["q"]), ("r", lambda r: r["r"]), ("c", lambda r: r["c"]),
                           ("entry", lambda r: r["bins"]["entry"])):
                vals = []
                for s in ss:
                    v = [get(X[(K, s, arm)]) for arm in w]
                    vals.append(None if any(x is None for x in v) else float(sum(c * x for c, x in zip(w.values(), v))))
                cb[m] = tstats(vals)
            if name != "interaction":
                arm = next(k for k, c in w.items() if c == 1)
                dec = []
                for s in ss:
                    x, y = X[(K, s, arm)], X[(K, s, "00")]
                    dec.append(None if x["r"] is None or y["r"] is None else
                               {"seed": s, "access_part": (x["q"] - y["q"]) * (x["r"] + y["r"]) / 2,
                                "completion_part": (x["r"] - y["r"]) * (x["q"] + y["q"]) / 2})
                cb["decomposition"] = dec
            blk["contrasts"][name] = cb
        res["conditions"][f"K{K}"] = blk
    if all(f"K{K}" in res["conditions"] for K in KS):
        C = res["conditions"]
        common = sorted(set(C["K1"]["seeds"]) & set(C["K3"]["seeds"]))
        res["K1_minus_K3"] = {name: tstats([sum(c * (X[(1, s, a_)]["P1"] - X[(3, s, a_)]["P1"]) for a_, c in w.items()) for s in common])
                              for name, w in CONTRASTS.items()}
        best_per_K = {K: max(ARMS, key=lambda a_: C[f"K{K}"]["arms"][a_]["P1"]) for K in KS}
        fixed = {a_: float(np.mean([C[f"K{K}"]["arms"][a_]["P1"] for K in KS])) for a_ in ARMS}
        best_fixed = max(fixed, key=fixed.get)
        oracle = float(np.mean([C[f"K{K}"]["arms"][best_per_K[K]]["P1"] for K in KS]))
        res["rq2_hindsight"] = {"best_arm_per_K": best_per_K, "fixed_arm_mean_P1": fixed, "best_fixed_arm": best_fixed,
                                "condition_identity_rule_mean_P1": oracle, "hindsight_headroom": oracle - fixed[best_fixed],
                                "note": "in-sample hindsight over 3 seeds; the condition-identity rule is chosen on the same data"}
    (out / "pilot_summary.json").write_text(json.dumps(res, indent=1, default=float))
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(out / "pilot_branches.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    print(json.dumps({"missing": missing, "problems": problems, "conditions": list(res["conditions"])}, indent=1))
    return res


if __name__ == "__main__":
    main()
