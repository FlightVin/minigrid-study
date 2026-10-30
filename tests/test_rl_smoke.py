"""End-to-end probe -> branch smoke test on real development data with tiny budgets (CPU).
Skipped when the dev dataset or a BC checkpoint is not present locally."""
import json
import os
from pathlib import Path
import sys

import pytest

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
