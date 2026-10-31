"""tools/analyze_m4.py on a synthetic M4 tree (no environment actions)."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("analyze_m4", ROOT / "tools/analyze_m4.py")
A = importlib.util.module_from_spec(spec)
spec.loader.exec_module(A)


def test_t_cdf4_and_holm():
    assert abs(A.t_cdf4(2.7764451) - 0.975) < 1e-6 and abs(A.t_cdf4(0) - 0.5) < 1e-12
    assert abs(A.t_cdf4(-2.1318468) - 0.05) < 1e-6
    assert A.holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]


def write_tree(runs, effect):
    """Arm 11 succeeds on extra layouts (effect x 64 per stratum); the other arms are identical."""
    rng = np.random.default_rng(0)
    b = runs / "B"
    for s in A.SEEDS:
        for K, u in A.STRATA:
            fh = f"h{s}{K}{u}"
            d = b / f"m4-probe-K{K}-u{u}-s{s}"
            d.mkdir(parents=True)
            (d / "summary.json").write_text(json.dumps({"fork_hash": fh, "pi0": {"p": .2, "q": .5, "c": .6},
                                                        "probe": {"p": .2, "q": .5, "c": .6}}))
            base = rng.random(64) < 0.4
            base[:16] = False                     # so the arm-11 effect is exactly (10 + s % 2) / 64
            for arm, tag in A.TAGS.items():
                d = b / f"m4-K{K}-u{u}-s{s}-{tag}"
                d.mkdir()
                evals = []
                for ep, (etag, at) in A.ENDPOINTS.items():
                    succ = base.copy()
                    if arm == "11" and effect > 0:
                        succ[:int(round(effect * 64)) + s % 2] = True
                    lines = [{"kind": "normal", "item": i, "attempt": j, "success": bool(succ[i]), "arrival": None}
                             for i in range(64) for j in range(8)]
                    lines += [{"kind": "bank", "item": i, "attempt": j, "success": j < 2} for i in range(64) for j in range(4)]
                    (d / f"attempts_{etag}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
                    p1 = float(succ.mean())
                    evals.append({"tag": etag, "actions": at, "endpoint": True, "layouts": "eval", "P1": p1, "q": 0.5,
                                  "c": 0.5, "C4": p1, "R4": p1, "P_success_given_arrival": None})
                evals.insert(0, {"tag": "curve_126976", "actions": 126976, "endpoint": False, "layouts": "diag",
                                 "P1": .2, "q": .5, "c": .5})
                (d / "summary.json").write_text(json.dumps({"arm": arm, "K": K, "seed": s, "bc_update": u, "fork_hash": fh,
                                                            "evals": evals, "state_hashes": {"251904": "x", "501760": "y"}}))


def test_synthetic_effect_is_recovered(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    write_tree(runs, 0.15)
    monkeypatch.setattr(A, "RUNS", runs)
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out)])
    A.main()
    sm = json.loads((out / "m4_summary.json").read_text())
    assert sm["complete_forks"] == 20 and not sm["excluded"] and sm["audit_max_abs_diff"] < 1e-12
    by = {(r["endpoint"], r["contrast"]): r for r in sm["primary"]}
    comb = by[("E250", "combined")]
    assert abs(comb["estimate"] - 10.4 / 64) < 1e-12 and comb["p_holm6"] < 0.05 and comb["verdict"] == "useful benefit"
    reset = by[("E500", "reset")]
    assert reset["estimate"] == 0 and "practically equivalent" in reset["verdict"]


def test_fork_hash_mismatch_excludes_fork(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    write_tree(runs, 0.0)
    f = runs / "B/m4-K1-u4000-s10-10-a0p25/summary.json"
    s = json.loads(f.read_text())
    s["fork_hash"] = "other"
    f.write_text(json.dumps(s))
    monkeypatch.setattr(A, "RUNS", runs)
    out = tmp_path / "out"
    out.mkdir()
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out)])
    A.main()
    sm = json.loads((out / "m4_summary.json").read_text())
    assert sm["complete_forks"] == 19 and sm["excluded"][0]["reason"] == "arm 10 fork hash mismatch"
    assert sm["primary"] == []      # incomplete seed: not estimated, never imputed
