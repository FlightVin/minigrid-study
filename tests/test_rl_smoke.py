"""End-to-end probe -> branch smoke test on real development data with tiny budgets (CPU).
Skipped when the dev dataset or a BC checkpoint is not present locally.

These tests execute ~220k environment actions per run, which count against the campaign cap
(research/ledger_adjustments.json). They run only with BC2RL_SMOKE=1, before launching changed RL code."""
import json
import os
from pathlib import Path
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("BC2RL_SMOKE") != "1", reason="set BC2RL_SMOKE=1 (costs ~220k env actions)")

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data/dev-v2"
BC = ROOT / ".mae/runs/20261030T204407-76602/m1-bc-curve-v1-s0/actor_u4000.pt"


@pytest.mark.skipif(not (DS.exists() and BC.exists()), reason="needs dev-v2 data and a BC checkpoint")
def test_probe_then_all_arms(tmp_path, monkeypatch):
    from bc2rl import rl
    cfg = json.loads((ROOT / "experiments/m2/ppo-canary-v1.json").read_text())
    cfg.update(critic_warmup_actions=300, critic_prefit_steps=5, probe_actions=512, n_steps=64, n_envs=4,
               diag_attempts=1, diag_bank_attempts=1, continuation_actions=512, curve_every=256,
               curve_attempts=1, curve_bank_attempts=1, final_attempts=2, final_bank_attempts=1)
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    runs = tmp_path / "project/.mae/runs"
    (runs / "bc").mkdir(parents=True)
    os.symlink(BC, runs / "bc/actor_u4000.pt")
    (tmp_path / "project/data").mkdir()
    os.symlink(DS, tmp_path / "project/data/dev-v2")
    monkeypatch.setenv("MAE_PROJECT", str(tmp_path / "project"))
    monkeypatch.setenv("MAE_DEVICE", "cpu")
    probe_dir = runs / "probe"
    probe_dir.mkdir()
    monkeypatch.setenv("MAE_RUN_DIR", str(probe_dir))
    monkeypatch.setattr(sys, "argv", ["rl", "probe", "--config", str(cfg_path), "--K", "3", "--bc-run", "bc",
                                      "--bc-update", "4000", "--seed", "0"])
    rl.main()
    s = json.loads((probe_dir / "summary.json").read_text())
    assert s["actions"]["train"] >= 512 and s["actions"]["critic_warmup"] >= 300
    finals = {}
    for arm in ("00", "10", "01", "11"):
        d = runs / f"b{arm}"
        d.mkdir()
        monkeypatch.setenv("MAE_RUN_DIR", str(d))
        monkeypatch.setattr(sys, "argv", ["rl", "branch", "--config", str(cfg_path), "--probe-run", "probe", "--arm", arm])
        rl.main()
        b = json.loads((d / "summary.json").read_text())
        assert b["fork_hash"] == s["fork_hash"] and b["continuation_actions"] >= 512
        finals[arm] = b
        recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines()]
        tr = [r for r in recs if r.get("phase") == "branch"]
        assert tr and all(r["frac_assisted_steps"] == 0 for r in tr) == (arm[0] == "0")


@pytest.mark.skipif(not (DS.exists() and BC.exists()), reason="needs dev-v2 data and a BC checkpoint")
def test_scheduled_branch_resumes_exactly(tmp_path, monkeypatch):
    """A branch saved at 512 actions and resumed to 1,024 equals the uninterrupted branch (CPU)."""
    from bc2rl import rl
    cfg = json.loads((ROOT / "experiments/m2/ppo-canary-v1.json").read_text())
    cfg.update(critic_warmup_actions=300, critic_prefit_steps=5, probe_actions=256, n_steps=64, n_envs=4,
               diag_attempts=1, diag_bank_attempts=1, continuation_actions=1000, alpha=0.5, kl_coef=0.1,
               diag_role="dev_bank",
               eval_schedule=[{"at": 512, "attempts": 1, "bank_attempts": 0, "tag": "mid", "layouts": "diag",
                               "endpoint": True},
                              {"at": 1024, "attempts": 1, "bank_attempts": 1, "tag": "end"}],
               save_state_at=[512])
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    runs = tmp_path / "project/.mae/runs"
    (runs / "bc").mkdir(parents=True)
    os.symlink(BC, runs / "bc/actor_u4000.pt")
    (tmp_path / "project/data").mkdir()
    os.symlink(DS, tmp_path / "project/data/dev-v2")
    monkeypatch.setenv("MAE_PROJECT", str(tmp_path / "project"))
    monkeypatch.setenv("MAE_DEVICE", "cpu")

    def run(job, *args):
        d = runs / "batch" / job
        d.mkdir(parents=True)
        monkeypatch.setenv("MAE_RUN_DIR", str(d))
        monkeypatch.setattr(sys, "argv", ["rl", *args, "--config", str(cfg_path)])
        rl.main()
        return d, json.loads((d / "summary.json").read_text())

    run("probe", "probe", "--K", "3", "--bc-run", "bc", "--bc-update", "4000", "--seed", "0")
    d1, s1 = run("straight", "branch", "--probe-run", "@/probe", "--arm", "11")
    assert s1["continuation_actions"] == 1024 and [e["actions"] for e in s1["evals"]] == [512, 1024]
    assert set(s1["state_hashes"]) == {"512", "1024"}          # JSON keys
    assert s1["evals"][0]["c"] is None and s1["evals"][1]["c"] is not None
    # the mid point uses the diag_role layouts (64 per K) and counts as a second endpoint
    mid = [json.loads(l) for l in (d1 / "attempts_mid.jsonl").read_text().splitlines()]
    end = [r for r in map(json.loads, (d1 / "attempts_end.jsonl").read_text().splitlines()) if r["kind"] == "normal"]
    assert len({r["item"] for r in mid}) == 64 and len({r["item"] for r in end}) == 32
    assert s1["evals"][0]["layouts"] == "diag" and s1["evals"][0]["endpoint"] and s1["evals"][1]["endpoint"]
    assert s1["actions"]["eval_diagnostic"] == 0 and s1["actions"]["eval_final"] > 0
    d2, s2 = run("resumed", "resume", "--state", "@/straight/state_512.pt")
    assert [e["actions"] for e in s2["evals"]] == [1024]
    assert s1["state_hashes"]["1024"] == s2["state_hashes"]["1024"]
    assert s2["final"] == s1["final"]
    assert s2["actions"]["train"] == 512 and s2["resumed_from"].endswith("state_512.pt")


M3 = ROOT / ".mae/runs/20261030T214937-19577"


@pytest.mark.skipif(not (DS.exists() and M3.exists()), reason="needs dev-v2 data and M3 runs")
def test_diagnostics_on_saved_m3_policies(tmp_path, monkeypatch):
    from bc2rl import diag
    cfg = json.loads((ROOT / "experiments/dev2/diag-v1.json").read_text())
    cfg.update(arrival_layouts=3, final_attempts=1, final_bank_attempts=1)
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    (tmp_path / "project/.mae").mkdir(parents=True)
    os.symlink(ROOT / ".mae/runs", tmp_path / "project/.mae/runs")
    (tmp_path / "project/data").mkdir()
    os.symlink(DS, tmp_path / "project/data/dev-v2")
    monkeypatch.setenv("MAE_PROJECT", str(tmp_path / "project"))
    monkeypatch.setenv("MAE_DEVICE", "cpu")
    b = "20261030T214937-19577/m3-K3-u16000-s0"
    br = [f"00={b}-00", f"01={b}-01-kl0p01", f"10={b}-10-a0p25", "11=20261030T232600-96083/m3-K3-u16000-s0-11-a0p25-kl0p01"]
    for mode, extra in (("arrival", ["--probe", "20261030T214937-19577/m3-probe-K3-u16000-s0", "--branches", *br]),
                        ("gradcheck", ["--probe", "20261030T214937-19577/m3-probe-K3-u16000-s0", "--branches", *br[:2]])):
        d = tmp_path / mode
        d.mkdir()
        monkeypatch.setenv("MAE_RUN_DIR", str(d))
        monkeypatch.setattr(sys, "argv", ["diag", mode, "--config", str(cfg_path), *extra])
        diag.main()
        s = json.loads((d / "summary.json").read_text())
        if mode == "arrival":
            assert set(s["sources"]) == {"pi0", "00", "11"}
            for src, v in s["sources"].items():
                assert v["attempts"] == 6 and v["crossings"] <= 6
            banks = [json.loads(l) for l in (d / "arrival_banks.jsonl").read_text().splitlines()]
            assert all(x["snapshot"]["step_count"] == x["tau"] and x["remaining"] > 0 for x in banks)
            assert s["total_actions"] == sum(s["actions"].values()) > 0
        else:
            p = s["policies"]
            assert p["01"]["anchor_kl"] > 0 and p["00"]["lambda_kl_grad_norm"] > 0
