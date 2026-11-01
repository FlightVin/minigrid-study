"""Anchor-component experiment analysis (PROTOCOL_FREEZE Amendment 4, E2; exploratory, 3 seeds).
Written before any component data.

Usage: .venv/bin/python tools/analyze_comp.py [--runs .mae/runs] [--out reports/comp] [--check-states]

Jobs comp-K3-u4000-s{S}-{00|01p|01s|01}, S in (15, 16, 17), forked from the R1 early-BC probes of those seeds
(fixed rule). Evaluation at 251,904 only: first 32 K=3 r1_select layouts x 4 attempts and r1_bank 64 x 2
(eval seed 979000). Metrics are recomputed from attempts_comp_251904.jsonl and must equal the summary.

Per seed (descriptive; no decision p-values): P1 of each arm; contrasts
  prefix = 01p - 00, suffix = 01s - 00, both = 01 - 00, interaction = (01 - 01p) - (01s - 00);
their 3-seed means, SDs and 95% t-intervals (df 2, wide). The same for q, r = P(success | arrival), C4, R4,
fixed-bank c (mixed) and entry/retrieval/carrying; the exact access/completion decomposition of each contrast;
bank change from pi0 and the probe on the same r1_bank states (probe values: 64 x 4); anchor KL (all, prefix,
suffix) and the applied penalty during training; training access and success rates.
Engineering: every branch carries its probe's fork hash; the 01 and 00 branches' 251,904 state hashes are compared
with the R1 branches of the same fork (equal hashes = the hardware reproduced the R1 trajectory; not required).
A component effect identifies the contribution of that penalty term in this implementation, not a skill or pathway.
Outputs: comp_branches.csv, comp_summary.json.
"""
import argparse
import csv
import json
from math import comb
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_r1 as A1   # noqa: E402
import r1_stats as R      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = (15, 16, 17)
ARMS = ("00", "01p", "01s", "01")
TAG, AT = "comp_251904", 251904
N_ITEMS, N_ATT, N_BANK, N_BANK_ATT = 32, 4, 64, 2
BINS = ("entry", "retrieval", "carrying")
CONTRASTS = {"prefix": (("01p", 1), ("00", -1)), "suffix": (("01s", 1), ("00", -1)), "both": (("01", 1), ("00", -1)),
             "interaction": (("01", 1), ("01p", -1), ("01s", -1), ("00", 1))}


def record(d, sm):
    e = next(x for x in sm["evals"] if x["tag"] == TAG)
    normal, bank = A1.read_attempts(d / f"attempts_{TAG}.jsonl")
    assert sorted(normal) == list(range(N_ITEMS)) and all(len(v) == N_ATT for v in normal.values()), d.name
    assert sorted(bank) == list(range(N_BANK)) and all(len(v) == N_BANK_ATT for v in bank.values()), d.name
    z = np.array([sum(r["success"] for r in normal[i]) for i in range(N_ITEMS)], float)
    a = np.array([sum(r["arrival"] is not None for r in normal[i]) for i in range(N_ITEMS)], float)
    bins = {b: [] for b in BINS}
    for i in sorted(bank):
        bins[bank[i][0]["bin"]].append(np.mean([r["success"] for r in bank[i]]))
    rec = {"P1": float(z.mean() / N_ATT), "q": float(a.sum() / (N_ITEMS * N_ATT)), "r": float(z.sum() / a.sum()) if a.sum() else None,
           "C4": float(np.mean([1 - comb(N_ATT - int(k), 4) / comb(N_ATT, 4) for k in z])),
           "R4": float(np.mean([comb(int(k), 4) / comb(N_ATT, 4) for k in z])),
           "c": float(np.mean([np.mean([r["success"] for r in v]) for v in bank.values()])),
           "bins": {b: float(np.mean(v)) for b, v in bins.items()}}
    for m in ("P1", "q", "C4", "R4", "c"):
        assert abs(rec[m] - e[m]) < 1e-12, (d.name, m)
    return rec


def contrast(X, s, name, get):
    vals = [get(X[(s, arm)]) for arm, _ in CONTRASTS[name]]
    if any(v is None for v in vals):
        return None
    return float(sum(w * v for (_, w), v in zip(CONTRASTS[name], vals)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--out", default=str(ROOT / "reports/comp"))
    ap.add_argument("--check-states", action="store_true")
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for d in sorted(runs.glob("*/comp-*")):
        if (d / "summary.json").exists():
            assert d.name not in jobs, f"duplicate job {d.name}"
            jobs[d.name] = d
    X, rows, train, problems, missing, engineering = {}, [], {}, [], [], {}
    for s in SEEDS:
        for arm in ARMS:
            d = jobs.get(f"comp-K3-u4000-s{s}-{arm}")
            if d is None:
                missing.append(f"s{s} {arm}")
                continue
            sm = json.loads((d / "summary.json").read_text())
            cf = json.loads((d / "config.resolved.json").read_text())
            want = {"00": (0.0, "both"), "01p": (0.01, "prefix"), "01s": (0.01, "suffix"), "01": (0.01, "both")}[arm]
            if (sm["seed"], sm["K"], sm["bc_update"], sm["alpha"], sm["kl_coef"], sm["anchor_component"]) != (s, 3, 4000, 0.0, *want):
                problems.append(f"identity {d.name}")
            probe = Path(sm["probe_run"])
            ps = json.loads((probe / "summary.json").read_text())
            if sm["fork_hash"] != ps["fork_hash"] or probe.name != f"r1-probe-K3-u4000-s{s}":
                problems.append(f"fork lineage {d.name}")
            if (cf["eval_role"], cf["eval_layouts_n"], cf["bank_role"], cf["eval_seed"]) != ("r1_select", 32, "r1_bank", 979000):
                problems.append(f"eval allocation {d.name}")
            if a.check_states:
                import torch
                sys.path.insert(0, str(ROOT / "src"))
                from bc2rl import ppo as PP
                st = torch.load(d / f"state_{AT}.pt", map_location="cpu", weights_only=False)
                if not PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(AT)]:
                    problems.append(f"state hash {d.name}")
            if arm in ("00", "01"):
                r1 = next(iter(runs.glob(f"*/r1-K3-u4000-s{s}-{'00' if arm == '00' else '01-kl0p01'}")), None)
                if r1 is not None:
                    h = json.loads((r1 / "summary.json").read_text())["state_hashes"][str(AT)]
                    engineering[f"s{s}/{arm}"] = {"same_state_hash_as_R1_at_251904": h == sm["state_hashes"][str(AT)]}
            X[(s, arm)] = rec = record(d, sm)
            X[(s, arm)]["probe"] = ps
            tr = A1.training_diag(d)
            recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
            br = [r for r in recs if r.get("phase") == "branch"]
            for k in ("anchor_kl_prefix", "anchor_kl_suffix", "anchor_penalty"):
                v = [r[k] for r in br if r.get(k) is not None]
                tr[f"{k}_mean"] = float(np.mean(v)) if v else None
            train[(s, arm)] = tr
            rows.append({"seed": s, "arm": arm, "job": f"{d.parent.name}/{d.name}", **{m: rec[m] for m in ("P1", "q", "r", "C4", "R4", "c")},
                         **{f"bank_{b}": rec["bins"][b] for b in BINS},
                         "c_change_from_pi0": rec["c"] - ps["pi0"]["c"], "c_change_from_probe": rec["c"] - ps["probe"]["c"],
                         **{f"train_{k}": v for k, v in tr.items()}})
    seeds = [s for s in SEEDS if all((s, arm) in X for arm in ARMS)]
    res = {"seeds_used": seeds, "missing": missing, "problems": problems, "engineering": engineering,
           "status": "exploratory, 3 seeds, 251,904 actions, development-only evaluation", "contrasts": {}}
    getters = {m: (lambda r, m=m: r[m]) for m in ("P1", "q", "r", "C4", "R4", "c")}
    getters.update({f"bin_{b}": (lambda r, b=b: r["bins"][b]) for b in BINS})
    for name in CONTRASTS:
        blk = {}
        for m, get in getters.items():
            v = [contrast(X, s, name, get) for s in seeds]
            vv = [x for x in v if x is not None]
            blk[m] = {"per_seed": dict(zip(map(str, seeds), v)), **(R.t_test(vv) if len(vv) >= 2 else {"n": len(vv)})}
        if name != "interaction":
            arm = CONTRASTS[name][0][0]
            dec = []
            for s in seeds:
                x, y = X[(s, arm)], X[(s, "00")]
                if x["r"] is not None and y["r"] is not None:
                    dec.append({"seed": s, "access_part": (x["q"] - y["q"]) * (x["r"] + y["r"]) / 2,
                                "completion_part": (x["r"] - y["r"]) * (x["q"] + y["q"]) / 2})
            blk["decomposition"] = dec
        res["contrasts"][name] = blk
    res["arms"] = {arm: {m: float(np.mean([X[(s, arm)][m] for s in seeds])) for m in ("P1", "q", "c")} for arm in ARMS if seeds}
    res["training"] = {arm: {k: (float(np.mean([train[(s, arm)][k] for s in seeds if train[(s, arm)].get(k) is not None]))
                                 if any(train[(s, arm)].get(k) is not None for s in seeds) else None)
                             for k in ("anchor_kl_mean", "anchor_kl_prefix_mean", "anchor_kl_suffix_mean", "anchor_penalty_mean",
                                       "train_access_rate", "train_success_rate", "frac_suffix_steps_mean", "entropy_final")}
                       for arm in ARMS if seeds}
    (out / "comp_summary.json").write_text(json.dumps(res, indent=1, default=float))
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with open(out / "comp_branches.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
    print(json.dumps({k: res[k] for k in ("seeds_used", "missing", "problems", "engineering")}, indent=1))
    return res


if __name__ == "__main__":
    main()
