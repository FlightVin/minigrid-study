"""Programme 2026-11-02 smoke: a scheduled assistance branch (D5) with arrival certification, traced evaluation and
allocation counters, and exact checkpoint-and-pause/resume across schedule phases. Real jobs on dev-v2 (CPU).
Opt-in (BC2RL_SMOKE=1): they execute environment actions, counted by the runner when run as a job."""
import json
import os

import pytest

from test_pause_smoke import BC, DS, ROOT, job

pytestmark = pytest.mark.skipif(os.environ.get("BC2RL_SMOKE") != "1", reason="set BC2RL_SMOKE=1")
need = pytest.mark.skipif(not (DS.exists() and BC.exists()), reason="needs dev-v2 data and a BC checkpoint")


def setup(tmp_path):
    cfg = json.loads((ROOT / "experiments/m2/ppo-canary-v1.json").read_text())
    cfg.update(critic_warmup_actions=300, critic_prefit_steps=5, probe_actions=256, n_steps=64, n_envs=4,
               diag_attempts=1, diag_bank_attempts=1, continuation_actions=2048, kl_coef=0.01, diag_role="dev_bank",
               alpha=0.25, certify_arrivals=True, trace_eval=True, track_allocation=True,
               assist_schedule={"D5": [{"until": 512, "alpha": 0.5, "mixture": [["mod2", 1.0]]},
                                       {"until": 1024, "alpha": 0.5, "mixture": [["mod1", 1.0]]},
                                       {"until": 1536, "alpha": 0.5, "mixture": [["mod0", 1.0]]}],
                                "B5": [{"until": 1536, "alpha": 0.5,
                                        "mixture": [["entry", 0.5], ["retrieval", 0.25], ["carrying", 0.25]]}]},
               eval_schedule=[{"at": 1024, "attempts": 1, "bank_attempts": 1, "tag": "e1024"},
                              {"at": 2048, "attempts": 2, "bank_attempts": 1, "tag": "e2048"}],
               save_state_at=[1024, 2048], recovery_every=512)
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    proj = tmp_path / "project"
    (proj / ".mae/runs/bc").mkdir(parents=True)
    os.symlink(BC, proj / ".mae/runs/bc/actor_u4000.pt")
    (proj / "data").mkdir()
    os.symlink(DS, proj / "data/dev-v2")
    return cfg_path, proj


@need
def test_scheduled_branch_certification_and_exact_resume(tmp_path):
    cfg_path, proj = setup(tmp_path)
    _, r = job(proj, "probe", ["probe", "--K", "3", "--bc-run", "bc", "--bc-update", "4000", "--seed", "0"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    straight, r = job(proj, "straight", ["branch", "--probe-run", "@/probe", "--arm", "D5"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    s0 = json.loads((straight / "summary.json").read_text())
    c = s0["counters"]
    tags = {k.split("_", 1)[1] for k in c if k.startswith("episodes_assisted_")}
    assert tags <= {"assisted_mod2", "assisted_mod1", "assisted_mod0"} and "assisted_mod2" in tags
    steps = sum(json.loads(p.read_text())["actions"] for p in (straight / "env_steps").glob("*.json"))
    assert steps == sum(s0["actions"].values())                       # includes certification replays
    rows = [json.loads(l) for l in (straight / "attempts_e2048.jsonl").read_text().splitlines()]
    normal = [x for x in rows if x["kind"] == "normal"]
    assert all("trace" in x for x in normal)
    for x in normal:
        if x["arrival"] is not None:
            assert "snapshot" not in x["arrival"] and x["arrival"]["cert"]["status"] in ("feasible", "unresolved", "impossible")
    ev = s0["final"]
    # pause inside the second phase, resume: identical endpoint state and evaluation rows
    paused, r = job(proj, "paused", ["branch", "--probe-run", "@/probe", "--arm", "D5"], cfg_path,
                    {"BC2RL_TEST_SIGTERM_AT": "768"})
    assert r.returncode == 75, r.stdout + r.stderr
    resumed, r = job(proj, "resumed", ["resume", "--state", "@/paused/recovery.pt"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    s2 = json.loads((resumed / "summary.json").read_text())
    assert s2["state_hashes"]["2048"] == s0["state_hashes"]["2048"] and s2["final"] == ev
    assert (resumed / "attempts_e2048.jsonl").read_text() == (straight / "attempts_e2048.jsonl").read_text()
