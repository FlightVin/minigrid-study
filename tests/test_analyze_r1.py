"""Synthetic checks of tools/analyze_r1.py and tools/r1_stats.py (written before R1 data)."""
import json
from math import comb
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_r1 as A    # noqa: E402
import r1_stats as R      # noqa: E402

M_EARLY = [8, 10, 12, 6, 9, 11, 7, 13]    # extra successes for arm 01, early BC, per seed
M_EXT = [3, 0, 5, 2, 4, 1, 0, 2]          # fewer successes for arm 01, extended BC, per seed


def write_attempts(path, z_items, bank_ok):
    lines = []
    for i, z in enumerate(z_items):
        for j in range(A.N_ATT):
            succ = j < z
            arr = {"tau": 50 + j, "remaining": 90, "pos": [1, 1], "dir": 0, "carrying": ["key", "yellow"]} if j <= z else None
            lines.append({"kind": "normal", "item": i, "attempt": j, "K": 3, "limit": 140 + i % 7, "success": succ,
                          "accessed": arr is not None, "arrival": arr})
    for i in range(A.N_BANK):
        b = "entry" if i < 32 else "retrieval" if i < 48 else "carrying"
        for j in range(A.N_BANK_ATT):
            lines.append({"kind": "bank", "bin": b, "item": i, "attempt": j, "K": 3, "limit": 140, "success": j < bank_ok,
                          "accessed": True, "arrival": None})
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    z = np.array(z_items, float)
    a = np.minimum(z + 1, A.N_ATT)
    return {"P1": float(z.mean() / 4), "q": float(a.sum() / 512), "C4": float(np.mean([1 - comb(4 - int(k), 4) for k in z])),
            "R4": float(np.mean([comb(int(k), 4) for k in z])), "c": bank_ok / 4,
            "P_success_given_arrival": float(z.sum() / a.sum()), "bins": {b: bank_ok / 4 for b in A.BINS}}


def build(tmp, drop=None, bad_panel=False):
    runs = tmp / "runs"
    b = runs / "B1"
    for s in A.SEEDS:
        (b / f"r1-bc-s{s}").mkdir(parents=True)
        for ck, u in A.CKPT.items():
            pj = b / f"r1-probe-K3-u{u}-s{s}"
            pj.mkdir()
            fh = f"fork{s}{u}"
            pr = {"p": 0.4, "q": 0.6, "c": 0.4, "bins": {x: 0.4 for x in A.BINS}}
            (pj / "summary.json").write_text(json.dumps({"K": 3, "seed": s, "bc_update": u, "fork_hash": fh, "pi0": pr,
                                                         "probe": pr, "actions": {"train": 51200}}))
            (pj / "config.resolved.json").write_text(json.dumps({"bc_run": f"@/r1-bc-s{s}", "bc_seed": s, "diag_role": "r1_select",
                                                                 "eval_role": "r1_final", "bank_role": "r1_bank", "dataset_id": "r1-v1"}))
            for arm, tag in A.ARMS.items():
                if drop == (s, ck, arm):
                    continue
                d = b / f"r1-K3-u{u}-s{s}-{tag}"
                d.mkdir()
                evals = []
                for ep, (t, at) in A.EP.items():
                    z = [2] * A.N_ITEMS
                    k = s - 15
                    if arm == "01" and ck == "early":
                        for i in range(M_EARLY[k]):
                            z[i] += 1
                    if arm == "01" and ck == "extended":
                        for i in range(M_EXT[k]):
                            z[i] -= 1
                    if bad_panel and (s, ck, arm) == (16, "early", "00"):
                        pass
                    m = write_attempts(d / f"attempts_{t}.jsonl", z, 2 if arm == "00" else 3)
                    evals.append({"tag": t, "actions": at, "endpoint": True, "layouts": "eval", **m})
                if bad_panel and (s, ck, arm) == (16, "early", "00"):
                    p = d / "attempts_final_501760.jsonl"
                    p.write_text(p.read_text().replace('"limit": 140,', '"limit": 141,', 1).replace('"item": 0, "attempt": 0, "K": 3, "limit": 140', '"item": 0, "attempt": 0, "K": 3, "limit": 139'))
                (d / "summary.json").write_text(json.dumps({"arm": arm, "K": 3, "seed": s, "bc_update": u, "alpha": 0.0,
                                                            "kl_coef": 0.01 if arm == "01" else 0.0, "fork_hash": fh,
                                                            "evals": evals, "state_hashes": {}, "actions": {"train": 501760},
                                                            "actions_this_job": {"train": 501760}}))
                (d / "config.resolved.json").write_text(json.dumps({"probe_run": str(pj), "dataset_id": "r1-v1",
                                                                    "eval_role": "r1_final", "bank_role": "r1_bank",
                                                                    "diag_role": "r1_select"}))
                cnt = {"normal_episodes": 0, "normal_accessed": 0, "normal_successes": 0}
                recs = [{"phase": "branch", "actions": 2048 * (i + 1), "anchor_kl": 0.1, "approx_kl": 0.01, "clipfrac": 0.05,
                         "entropy": 0.4, "explained_var": 0.5, "grad_norm_actor": 1.0, "frac_suffix_steps": 0.3,
                         "counters": {k: v + 10 * i for k, v in cnt.items()}} for i in range(3)]
                (d / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return runs


def test_t_distribution_df7():
    assert abs(R.T975 - 2.364624) < 1e-5
    assert abs(R.t_cdf_abs(2.364624252) - 0.95) < 1e-8
    assert abs(R.t_quantile_two_sided(0.95, 5) - 2.570582) < 1e-5


def test_holm_and_signflip():
    assert R.holm([0.01, 0.04]) == [0.02, 0.04]
    assert R.holm([0.04, 0.03]) == [0.06, 0.06]
    assert abs(R.signflip([1.0] * 8) - 2 / 256) < 1e-12


def test_primary_estimates_exact(tmp_path):
    runs = build(tmp_path)
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out")])
    assert res["seeds_used"] == list(A.SEEDS) and not res["problems"] and not res["excluded"]
    de = np.array(M_EARLY) / 512
    dx = -np.array(M_EXT) / 512
    e = res["E500"]
    assert abs(e["early"]["estimate"] - de.mean()) < 1e-12
    assert abs(e["extended"]["estimate"] - dx.mean()) < 1e-12
    assert abs(e["interaction"]["estimate"] - (de - dx).mean()) < 1e-12
    t1, t2 = R.t_test(de), R.t_test(de - dx)
    assert abs(e["early"]["p"] - t1["p"]) < 1e-12 and e["early"]["df"] == 7
    assert [e["early"]["p_holm"], e["interaction"]["p_holm"]] == R.holm([t1["p"], t2["p"]])
    assert e["H1_supported"] and e["H2_supported"] and e["interpretation"].startswith("H1 and H2 supported")
    assert e["early"]["magnitude"] == "below the 0.05 practical threshold"
    lo, hi = e["early"]["crossed95"]
    assert lo <= de.mean() <= hi
    # all extra successes sit on items < 13, so layout resampling moves the estimate
    assert e["early"]["layouts_only95"][1] > e["early"]["layouts_only95"][0]
    sec = res["secondary"]["E500/early/diff_01_minus_00"]
    assert abs(sec["c"]["estimate"] - 0.25) < 1e-12


def test_missing_branch_excludes_seed_not_replaced(tmp_path):
    runs = build(tmp_path, drop=(18, "extended", "01"))
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out")])
    assert 18 not in res["seeds_used"] and len(res["seeds_used"]) == 7
    assert res["excluded"] == [{"seed": 18, "reason": "branch extended/01 missing"}]
    assert res["E500"]["complete_design"] is False


def test_panel_mismatch_is_flagged(tmp_path):
    runs = build(tmp_path, bad_panel=True)
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out")])
    assert any("panel differs" in p for p in res["problems"])


def test_summary_mismatch_raises(tmp_path):
    runs = build(tmp_path)
    p = runs / "B1/r1-K3-u4000-s15-00/summary.json"
    sm = json.loads(p.read_text())
    sm["evals"][0]["P1"] += 0.01
    p.write_text(json.dumps(sm))
    with pytest.raises(AssertionError):
        A.main(["--runs", str(runs), "--out", str(tmp_path / "out")])


def test_interpretation_cells():
    t = {"t95_hi": 0.01}
    assert A.interpret(False, False, t).startswith("Neither supported: informative")
    assert "partly informative" in A.interpret(False, False, {"t95_hi": 0.03})
    assert "inconclusive" in A.interpret(False, False, {"t95_hi": 0.06})
    assert A.interpret(False, True, t).startswith("H2 supported, H1 not")
    assert A.interpret(True, False, t).startswith("H1 supported, H2 not")
