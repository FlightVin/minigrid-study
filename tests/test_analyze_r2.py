"""Synthetic checks of tools/analyze_r2.py (written before R2 data)."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import analyze_r2 as A    # noqa: E402
import r1_stats as R      # noqa: E402
from test_analyze_r1 import write_attempts    # noqa: E402

EXTRA = [8, 10, 12, 6, 9, 11, 7, 13, 0, 5, 4, 3, 14, 2, 6, 9, 1, 10, 7, 5]   # extra successes for arm 01, per seed


def build(tmp, drop=None, upto=None):
    runs = tmp / "runs"
    b = runs / "B1"
    for k, s in enumerate(A.SEEDS):
        if upto is not None and k >= upto:
            break
        (b / f"r2-bc-s{s}").mkdir(parents=True)
        pj = b / f"r2-probe-K3-u4000-s{s}"
        pj.mkdir()
        pr = {"p": 0.1, "q": 0.4, "c": 0.4, "bins": {x: 0.4 for x in A.BINS}}
        (pj / "summary.json").write_text(json.dumps({"K": 3, "seed": s, "bc_update": 4000, "fork_hash": f"f{s}", "pi0": pr,
                                                     "probe": pr, "actions": {"train": 51200}}))
        (pj / "config.resolved.json").write_text(json.dumps({"bc_run": f"@/r2-bc-s{s}", "bc_seed": s, "diag_role": "r2_select",
                                                             "eval_role": "r2_final", "bank_role": "r2_bank", "dataset_id": "r2-v1"}))
        for arm, tag in A.ARMS.items():
            if drop == (s, arm):
                continue
            d = b / f"r2-K3-u4000-s{s}-{tag}"
            d.mkdir()
            evals = []
            for ep, (t, at) in A.EP.items():
                z = [2] * 128
                if arm == "01":
                    for i in range(EXTRA[k]):
                        z[i] += 1
                m = write_attempts(d / f"attempts_{t}.jsonl", z, 2 if arm == "00" else 3)
                evals.append({"tag": t, "actions": at, "endpoint": True, "layouts": "eval", **m})
            (d / "summary.json").write_text(json.dumps({"arm": arm, "K": 3, "seed": s, "bc_update": 4000, "alpha": 0.0,
                                                        "kl_coef": 0.01 if arm == "01" else 0.0, "anchor_component": "both",
                                                        "fork_hash": f"f{s}", "evals": evals, "state_hashes": {},
                                                        "actions": {"train": 501760}, "actions_this_job": {"train": 501760}}))
            (d / "config.resolved.json").write_text(json.dumps({"probe_run": str(pj), "dataset_id": "r2-v1", "eval_role": "r2_final",
                                                                "bank_role": "r2_bank", "diag_role": "r2_select"}))
            cnt = {"normal_episodes": 0, "normal_accessed": 0, "normal_successes": 0}
            recs = [{"phase": "branch", "actions": 2048 * (i + 1), "anchor_kl": 0.1, "anchor_kl_prefix": 0.05,
                     "anchor_kl_suffix": 0.12, "approx_kl": 0.01, "clipfrac": 0.05, "entropy": 0.4, "explained_var": 0.5,
                     "grad_norm_actor": 1.0, "frac_suffix_steps": 0.3, "batch_successes": 3.0,
                     "counters": {k: v + 10 * i for k, v in cnt.items()}} for i in range(3)]
            (d / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return runs


def test_primary_exact_and_decision(tmp_path):
    res = A.main(["--runs", str(build(tmp_path)), "--out", str(tmp_path / "out")])
    assert res["complete_design"] and res["primary_computed"] and not res["problems"] and not res["excluded"]
    d = np.array(EXTRA) / 512
    t = R.t_test(d)
    e = res["E500"]
    assert abs(e["estimate"] - d.mean()) < 1e-12 and abs(e["p"] - t["p"]) < 1e-12 and e["df"] == 19
    assert e["decision"] == "positive effect supported" and e["magnitude"] == "positive; not shown to exceed 0.03"
    assert e["n_positive"] == 19
    lo, hi = e["crossed95"]
    assert lo <= d.mean() <= hi
    dec = res["E500_decomposition"]
    assert dec["n_defined"] == 20 and abs(dec["dp"]["estimate"] - d.mean()) < 1e-12
    assert abs(dec["access_part"]["estimate"] + dec["completion_part"]["estimate"] - d.mean()) < 1e-12
    assert "synthesis_descriptive" in res and res["secondary"]["E500/diff_01_minus_00"]["c"]["estimate"] == 0.25


def test_blinded_until_all_twenty_complete(tmp_path):
    res = A.main(["--runs", str(build(tmp_path, upto=12)), "--out", str(tmp_path / "out")])
    assert not res["primary_computed"] and "E500" not in res and not res["secondary"]
    assert not (tmp_path / "out/r2_seeds.csv").exists() and not (tmp_path / "out/r2_branches.csv").exists()


def test_missing_branch_excluded_not_replaced(tmp_path):
    runs = build(tmp_path, drop=(30, "01"))
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out")])
    assert not res["primary_computed"] and {"seed": 30, "reason": "branch 01 missing"} in res["excluded"]
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out2"), "--final-incomplete"])
    assert res["primary_computed"] and res["n"] == 19 and 30 not in res["seeds_used"] and not res["complete_design"]


def test_signflip_exact_matches_enumeration():
    x = np.random.default_rng(3).normal(0.02, 0.04, 10)
    assert abs(A.signflip_exact(x) - R.signflip(x)) < 1e-12
    assert A.signflip_exact(np.full(20, 0.01)) == 2 / 2 ** 20


def test_decision_cells():
    t = lambda lo, hi: {"t95_lo": lo, "t95_hi": hi}
    assert A.decide(t(0.06, 0.1)) == ("positive effect supported", "exceeds 0.05")
    assert A.decide(t(0.031, 0.1)) == ("positive effect supported", "exceeds 0.03")
    assert A.decide(t(0.001, 0.1)) == ("positive effect supported", "positive; not shown to exceed 0.03")
    assert A.decide(t(-0.05, -0.001))[0] == "negative effect supported"
    assert A.decide(t(-0.01, 0.029))[1].startswith("informative")
    assert A.decide(t(-0.01, 0.04))[1].startswith("the interval excludes the M4")
    assert A.decide(t(-0.01, 0.05))[1].startswith("inconclusive")
