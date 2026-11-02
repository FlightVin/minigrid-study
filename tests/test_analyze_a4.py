"""Synthetic end-to-end test of tools/analyze_a4.py (no environment actions): lineage with a battery-paused and
resumed branch, endpoint attribution, blinding, the gated H2, decomposition identity and the planted effect."""
import json
from pathlib import Path
import sys

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_a4 as A    # noqa: E402

N_ARR = 6


def make_data(tmp):
    data = tmp / "data/r4-v1"
    data.mkdir(parents=True)
    lay = {"a4_final": [{"layout": {"K": 3, "limit": 140 + i % 10}} for i in range(256)]}
    (data / "layouts.json").write_text(json.dumps(lay))
    arr = tmp / "arr.json"
    arr.write_text(json.dumps({"states": [{} for _ in range(N_ARR)]}))
    return data, arr, [140 + i % 10 for i in range(256)]


def attempts(path, rng, p, q_extra, limits):
    out = []
    for i in range(256):
        for j in range(2):
            arrived = rng.random() < min(1.0, p + q_extra)
            succ = arrived and rng.random() < p / min(1.0, p + q_extra)
            out.append({"kind": "normal", "item": i, "attempt": j, "limit": limits[i], "success": bool(succ),
                        "arrival": {"tau": 50, "remaining": 90, "carrying": None} if arrived else None})
    out += [{"kind": "bank", "bin": "entry", "item": i, "attempt": j, "success": bool(rng.random() < p + 0.3)}
            for i in range(128) for j in range(2)]
    out += [{"kind": "bank_extra", "bank": "arrival", "item": i, "attempt": j, "success": bool(rng.random() < 0.5)}
            for i in range(N_ARR) for j in range(2)]
    path.write_text("".join(json.dumps(r) + "\n" for r in out))


def probe_attempts(path, rng):
    out = [{"kind": "normal", "item": i, "attempt": j, "success": False, "arrival": None} for i in range(64) for j in range(2)]
    out += [{"kind": "bank", "bin": "entry", "item": i, "attempt": j, "success": bool(rng.random() < .6)} for i in range(128) for j in range(2)]
    out += [{"kind": "bank_extra", "bank": "arrival", "item": i, "attempt": j, "success": True} for i in range(N_ARR) for j in range(2)]
    path.write_text("".join(json.dumps(r) + "\n" for r in out))


def build(tmp, seeds, effect=0.05, resume_seed=71):
    runs = tmp / ".mae/runs"
    rng = np.random.default_rng(0)
    data, arr, limits = make_data(tmp)
    for s in seeds:
        b = runs / f"b{s}"
        bc, pr = b / f"a4-bc-s{s}", b / f"a4-probe-K3-s{s}"
        for d in (bc, pr):
            d.mkdir(parents=True)
            (d / "summary.json").write_text("{}")
        (bc / "actor_u8000.pt").write_text("x")
        (pr / "fork.pt").write_text("x")
        (bc / "config.resolved.json").write_text(json.dumps({"prefix_prob": 0.2, "seed": s, "checkpoints": [8000], "dataset_id": "conf-v1"}))
        (bc / "metrics.jsonl").write_text(json.dumps({"update": 8000, "normal_K1": {"P1": .55, "q": .95}, "normal_K3": {"P1": .1, "q": .2},
                                                      "bank_K1_entry": .6, "bank_K3_entry": .6}) + "\n")
        (pr / "summary.json").write_text(json.dumps({"K": 3, "seed": s, "bc_update": 8000, "fork_hash": f"f{s}"}))
        (pr / "config.resolved.json").write_text(json.dumps({"bc_run": f"@/a4-bc-s{s}", "diag_role": "a4_select", "dataset_id": "r4-v1"}))
        probe_attempts(pr / "attempts_pi0.jsonl", rng)
        probe_attempts(pr / "attempts_probe.jsonl", rng)
        for arm, tag in A.ARMS.items():
            base, comp, eff = A.IDENT[arm]
            meta = {"arm": tag, "K": 3, "seed": s, "alpha": 0.0, "anchor_component": comp, "fork_hash": f"f{s}",
                    "kl_coef": base, "kl_effective_prefix_suffix": list(eff), "base_actions": 68000}
            cfg = {**meta, "dataset_id": "r4-v1", "eval_role": "a4_final", "bank_role": "a4_bank", "eval_seed": 969000}
            p_by_ep = {"E250": .10, "E500": .15, "E1M": .20}
            eff_by_ep = {"E250": effect / 2, "E500": effect * .75, "E1M": effect} if arm == "C" else {e: 0 for e in p_by_ep}
            d = b / f"a4-K3-s{s}-{tag}"
            d.mkdir()
            met = [{"phase": "branch", "counters": {"env_actions": 68000 + x}, "anchor_kl": .1, "batch_successes": 3}
                   for x in range(2048, 1001473, 2048)]
            if s == resume_seed and arm == "C":
                # paused at 300,032 after the E250 evaluation; resumed from recovery.pt
                (d / "config.resolved.json").write_text(json.dumps(cfg))
                attempts(d / "attempts_final_251904.jsonl", rng, p_by_ep["E250"] + eff_by_ep["E250"], .1, limits)
                (d / "paused.json").write_text("{}")
                torch.save({"hash": "hrec", "meta": {**meta, "post_probe_actions": 300032}, "state": {}}, d / "recovery.pt")
                (d / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in met if r["counters"]["env_actions"] - 68000 <= 300032))
                rb = runs / "resume1" / f"a4-K3-s{s}-{tag}-r1"
                rb.mkdir(parents=True)
                rmeta = {**meta, "resumed_from": str(d / "recovery.pt"), "resumed_hash": "hrec"}
                (rb / "config.resolved.json").write_text(json.dumps({**cfg, **rmeta}))
                (rb / "summary.json").write_text(json.dumps({**rmeta, "continuation_actions": A.TARGET, "state_hashes": {}}))
                (rb / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in met if r["counters"]["env_actions"] - 68000 > 300032))
                for ep, at in A.EP.items():
                    if at > 300032:
                        attempts(rb / f"attempts_final_{at}.jsonl", rng, p_by_ep[ep] + eff_by_ep[ep], .1, limits)
                continue
            (d / "config.resolved.json").write_text(json.dumps(cfg))
            (d / "summary.json").write_text(json.dumps({**meta, "resumed_from": None, "continuation_actions": A.TARGET, "state_hashes": {}}))
            (d / "metrics.jsonl").write_text("".join(json.dumps(r) + "\n" for r in met))
            for ep, at in A.EP.items():
                attempts(d / f"attempts_final_{at}.jsonl", rng, p_by_ep[ep] + eff_by_ep[ep], .1, limits)
    return runs, data, arr


def test_analysis_end_to_end(tmp_path):
    runs, data, arr = build(tmp_path, A.SEEDS)
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out"), "--data", str(data), "--arrival", str(arr)])
    assert res["complete_design"] and res["primary_computed"] and not res["problems"], res["problems"]
    assert res["H1"]["decision"] == "supported" and abs(res["H1"]["estimate"] - 0.05) < 0.02
    assert res["H2"]["tested"] and res["H2"]["estimate"] > 0
    assert any("resumed" in x for x in res["interrupted_records"])
    for ep in A.EP:
        dc = res["secondary"][ep]["decomposition"]
        assert abs(dc["dp"]["estimate"] - dc["access_part"]["estimate"] - dc["completion_part"]["estimate"]) < 1e-12
    assert res["cohort"]["bc_meets_all_targets"] == 20
    rows = (tmp_path / "out/a4_branches.csv").read_text()
    assert "resume1/a4-K3-s71-01s-r1" in rows and "b71/a4-K3-s71-01s," in rows   # E250 from the paused job


def test_blinded_until_complete_and_h2_gated(tmp_path):
    runs, data, arr = build(tmp_path, A.SEEDS[:-1])
    res = A.main(["--runs", str(runs), "--out", str(tmp_path / "out"), "--data", str(data), "--arrival", str(arr)])
    assert not res["primary_computed"] and "H1" not in res and not (tmp_path / "out/a4_branches.csv").exists()
    runs2, data2, arr2 = build(tmp_path / "null", A.SEEDS, effect=0.0)
    res2 = A.main(["--runs", str(runs2), "--out", str(tmp_path / "out2"), "--data", str(data2), "--arrival", str(arr2)])
    if res2["H1"]["decision"] != "supported":
        assert res2["H2"]["tested"] is False and res2["H2"]["increasing_benefit_supported"] is False
