"""Synthetic checks of tools/analyze_a3.py (written before any A3 data)."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import analyze_a3 as A    # noqa: E402
import r1_stats as R      # noqa: E402
from test_analyze_r1 import write_attempts    # noqa: E402

EXTRA = [8, 10, 12, 6, 9, 11, 7, 13, 0, 5, 4, 3, 14, 2, 6, 9, 1, 10, 7, 5, 8, 6, 4, 9]   # extra successes, arm C


def build(tmp, effect=True, drop=None, upto=None, bad_coef=None):
    runs = tmp / "runs"
    b = runs / "B1"
    for k, s in enumerate(A.SEEDS):
        if upto is not None and k >= upto:
            break
        (b / f"a3-bc-s{s}").mkdir(parents=True)
        pj = b / f"a3-probe-K3-u4000-s{s}"
        pj.mkdir()
        pr = {"p": 0.1, "q": 0.4, "c": 0.4, "bins": {x: 0.4 for x in A.BINS}}
        (pj / "summary.json").write_text(json.dumps({"K": 3, "seed": s, "bc_update": 4000, "fork_hash": f"f{s}", "pi0": pr,
                                                     "probe": pr, "actions": {"train": 51200}}))
        (pj / "config.resolved.json").write_text(json.dumps({"bc_run": f"@/a3-bc-s{s}", "bc_seed": s, "diag_role": "a3_select",
                                                             "eval_role": "a3_final", "bank_role": "a3_bank", "dataset_id": "r3-v1"}))
        for arm, tag in A.ARMS.items():
            if drop == (s, arm):
                continue
            d = b / f"a3-K3-u4000-s{s}-{tag}"
            d.mkdir()
            evals = []
            for ep, (t, at) in A.EP.items():
                z = [2] * 128
                if arm == "C" and effect:
                    for i in range(EXTRA[k]):
                        z[i] += 1
                m = write_attempts(d / f"attempts_{t}.jsonl", z, 2)
                evals.append({"tag": t, "actions": at, "endpoint": True, "layouts": "eval", **m})
            base, comp, eff = A.IDENT[arm]
            if bad_coef == (s, arm):
                base = base * 0.75
            (d / "summary.json").write_text(json.dumps({"arm": tag, "K": 3, "seed": s, "bc_update": 4000, "alpha": 0.0,
                                                        "kl_coef": base, "anchor_component": comp, "kl_effective_prefix_suffix": eff,
                                                        "fork_hash": f"f{s}", "evals": evals, "state_hashes": {},
                                                        "actions": {"train": 501760}, "actions_this_job": {"train": 501760}}))
            (d / "config.resolved.json").write_text(json.dumps({"probe_run": str(pj), "dataset_id": "r3-v1", "eval_role": "a3_final",
                                                                "bank_role": "a3_bank", "diag_role": "a3_select"}))
            cnt = {"normal_episodes": 0, "normal_accessed": 0, "normal_successes": 0}
            recs = [{"phase": "branch", "actions": 2048 * (i + 1), "anchor_kl": 0.1, "anchor_kl_prefix": 0.05,
                     "anchor_kl_suffix": 0.12, "approx_kl": 0.01, "clipfrac": 0.05, "entropy": 0.4, "explained_var": 0.5,
                     "grad_norm_actor": 1.0, "frac_suffix_steps": 0.3, "batch_successes": 3.0, "update_kl_prefix": 0.001,
                     "update_kl_suffix": 0.002, "actor_update_norm": 0.05,
                     "counters": {kk: v + 10 * i for kk, v in cnt.items()}} for i in range(3)]
            (d / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return runs


def test_primary_exact_and_gate_opens_when_supported(tmp_path):
    res = A.main(["--runs", str(build(tmp_path)), "--out", str(tmp_path / "out")])
    assert res["complete_design"] and res["primary_computed"] and not res["problems"] and not res["excluded"]
    d = np.array(EXTRA) / 512
    t = R.t_test(d)
    h = res["H1"]
    assert abs(h["estimate"] - d.mean()) < 1e-12 and abs(h["p"] - t["p"]) < 1e-12 and h["df"] == 23
    assert h["decision"] == "supported" and h["n_positive"] == 23 and h["bootstrap_agrees"]
    g = res["gate"]
    assert g["tested"]
    # D and E equal A here, so C-D = C-E = C-A; Holm over two equal p-values gives 2p for both
    assert abs(g["H2a_C-D"]["p_holm"] - min(1, 2 * t["p"])) < 1e-12 and g["H2b_C-E"]["decision"] == "C higher"
    sec = res["secondary_contrasts"]["E250"]
    assert abs(sec["C-A"]["P1"]["estimate"] - d.mean()) < 1e-12 and sec["B-A"]["P1"]["estimate"] == 0
    assert abs(sec["interaction D-B-C+A"]["P1"]["estimate"] + d.mean()) < 1e-12
    dec = sec["decomposition_C-A"]
    assert dec["n_defined"] == 24
    assert abs(dec["access_part"]["estimate"] + dec["completion_part"]["estimate"] - d.mean()) < 1e-12
    assert abs(res["arms"]["E500/E"]["training"]["actor_update_norm_mean"] - 0.05) < 1e-12


def test_gate_closed_when_primary_not_supported(tmp_path):
    res = A.main(["--runs", str(build(tmp_path, effect=False)), "--out", str(tmp_path / "out")])
    assert res["H1"]["decision"] == "not supported"
    g = res["gate"]
    assert not g["tested"] and g["H2a_C-D"]["decision"] is None and g["H2b_C-E"]["decision"] is None
    assert "p_holm" not in g["H2a_C-D"]


def test_gate_rule_direct():
    t = {"estimate": 0.02, "p": 0.01}
    assert A.gate("supported", t, {"estimate": -0.01, "p": 0.06})["H2b_C-E"]["decision"] == "not supported"   # Holm 0.06
    assert A.gate("supported", t, {"estimate": -0.01, "p": 0.02})["H2b_C-E"]["decision"] == "C lower"
    assert not A.gate("negative effect supported", t, t)["tested"]


def test_blinded_until_all_24_complete(tmp_path):
    res = A.main(["--runs", str(build(tmp_path, upto=23)), "--out", str(tmp_path / "out")])
    assert not res["primary_computed"] and "H1" not in res and "arms" not in res
    assert not (tmp_path / "out/a3_seeds.csv").exists() and not (tmp_path / "out/a3_branches.csv").exists()


def test_missing_branch_excluded_and_identity_checked(tmp_path):
    runs = build(tmp_path, drop=(50, "E"), bad_coef=(51, "E"))
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out")])
    assert not res["primary_computed"] and {"seed": 50, "reason": "branch E (01w) missing"} in res["excluded"]
    assert any("a3-K3-u4000-s51-01w" in p for p in res["problems"])


def test_signflip_exact_matches_enumeration():
    x = np.random.default_rng(3).normal(0.02, 0.04, 10)
    assert abs(A.signflip_exact(x) - R.signflip(x)) < 1e-12
