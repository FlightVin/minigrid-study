"""Synthetic checks of tools/analyze_pilot.py (written before any pilot data)."""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_pilot as A    # noqa: E402

GAIN = {(1, "10"): 3, (3, "10"): 10, (1, "01s"): 0, (3, "01s"): 5, (1, "11s"): 2, (3, "11s"): 12}


def write(d, K, extra):
    lines, z = [], []
    for i in range(A.N_ITEMS):
        k = 1 + (1 if i < extra else 0)
        z.append(k)
        for j in range(A.N_ATT):
            arr = {"tau": 40, "remaining": 80, "carrying": ["key", "yellow"]} if j <= k else None
            lines.append({"kind": "normal", "item": i, "attempt": j, "K": K, "limit": 120 + i % 5, "success": j < k,
                          "accessed": arr is not None, "arrival": arr})
    for i in range(A.N_BANK):
        b = "entry" if i < 32 else "retrieval" if i < 48 else "carrying"
        for j in range(A.N_BANK_ATT):
            lines.append({"kind": "bank", "bin": b, "item": i, "attempt": j, "K": K, "success": j < 2, "arrival": None})
    (d / f"attempts_{A.TAG}.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    z = np.array(z, float)
    return {"tag": A.TAG, "P1": float(z.mean() / 4), "q": float(np.minimum(z + 1, 4).sum() / 256), "c": 0.5}


def build(tmp):
    b = tmp / "runs" / "B"
    for K in A.KS:
        for s in A.SEEDS:
            pj = b / f"pl-probe-K{K}-s{s}"
            pj.mkdir(parents=True)
            pr = {"p": 0.1, "q": 0.4, "c": 0.4, "bins": {x: 0.4 for x in A.BINS}}
            (pj / "summary.json").write_text(json.dumps({"K": K, "seed": s, "fork_hash": f"f{K}{s}", "pi0": pr, "probe": pr}))
            (pj / "config.resolved.json").write_text(json.dumps({"diag_role": "pl_select", "eval_role": "pl_final",
                                                                 "bank_role": "pl_bank", "dataset_id": "r3-v1"}))
            for arm in A.ARMS:
                d = b / f"pl-K{K}-s{s}-{arm}"
                d.mkdir()
                e = write(d, K, GAIN.get((K, arm), 0) + (s - 67))
                alpha, coef, comp = A.IDENT[arm]
                (d / "summary.json").write_text(json.dumps({"K": K, "seed": s, "alpha": alpha, "kl_coef": coef, "anchor_component": comp,
                                                            "fork_hash": f"f{K}{s}", "probe_run": str(pj), "evals": [e],
                                                            "state_hashes": {}, "actions": {"train": 251904}, "wall_seconds": 10.0}))
                c = {"normal_episodes": 0, "normal_successes": 0, "normal_accessed": 0, "assisted_episodes": 0, "assisted_successes": 0}
                recs = [{"phase": "branch", "actions": 2048 * (i + 1), "anchor_kl": 0.1, "frac_assisted_steps": 0.2 if alpha else 0.0,
                         "counters": {k: v + 10 * i for k, v in c.items()}} for i in range(2)]
                (d / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    return tmp / "runs"


def test_pilot_contrasts_and_hindsight(tmp_path):
    res = A.main(["--runs", str(build(tmp_path)), "--out", str(tmp_path / "out")])
    assert not res["missing"] and not res["problems"]
    k3 = res["conditions"]["K3"]["contrasts"]
    assert abs(k3["10-00"]["P1"]["estimate"] - 10 / 256) < 1e-12
    assert abs(k3["interaction"]["P1"]["estimate"] - (12 - 10 - 5) / 256) < 1e-12
    assert abs(res["K1_minus_K3"]["10-00"]["estimate"] - (3 - 10) / 256) < 1e-12
    h = res["rq2_hindsight"]
    assert h["best_arm_per_K"] == {1: "10", 3: "11s"} and h["best_fixed_arm"] == "11s"
    assert abs(h["hindsight_headroom"] - (3 - 2) / 256 / 2) < 1e-12
    dec = k3["10-00"]["decomposition"]
    assert all(abs(x["access_part"] + x["completion_part"] - 10 / 256) < 1e-12 for x in dec)
