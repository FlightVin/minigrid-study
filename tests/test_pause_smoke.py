"""Battery checkpoint-and-pause, exact resume from the recovery state, partial accounting, and arrival capture
(owner instruction 2026-11-01c, section 9). Real branch jobs as subprocesses on development data, tiny budgets (CPU).
Opt-in (BC2RL_SMOKE=1): they execute environment actions, counted by the runner when run as a job."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("BC2RL_SMOKE") != "1", reason="set BC2RL_SMOKE=1")

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("MAE_PROJECT", ROOT))
DS = PROJECT / "data/dev-v2"
BC = PROJECT / ".mae/runs/20261030T204407-76602/m1-bc-curve-v1-s0/actor_u4000.pt"
need = pytest.mark.skipif(not (DS.exists() and BC.exists()), reason="needs dev-v2 data and a BC checkpoint")


def setup(tmp_path):
    cfg = json.loads((ROOT / "experiments/m2/ppo-canary-v1.json").read_text())
    cfg.update(critic_warmup_actions=300, critic_prefit_steps=5, probe_actions=256, n_steps=64, n_envs=4,
               diag_attempts=1, diag_bank_attempts=1, continuation_actions=2048, kl_coef=0.01, diag_role="dev_bank",
               eval_schedule=[{"at": 1024, "attempts": 1, "bank_attempts": 1, "tag": "e1024", "endpoint": True},
                              {"at": 2048, "attempts": 1, "bank_attempts": 1, "tag": "e2048", "endpoint": True}],
               save_state_at=[1024, 2048], recovery_every=512)
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    proj = tmp_path / "project"
    (proj / ".mae/runs/bc").mkdir(parents=True)
    os.symlink(BC, proj / ".mae/runs/bc/actor_u4000.pt")
    (proj / "data").mkdir()
    os.symlink(DS, proj / "data/dev-v2")
    return cfg_path, proj


def job(proj, name, args, cfg_path, extra_env=None):
    d = proj / ".mae/runs/batch" / name
    d.mkdir(parents=True)
    env = {**os.environ, "MAE_PROJECT": str(proj), "MAE_RUN_DIR": str(d), "MAE_DEVICE": "cpu", "OMP_NUM_THREADS": "1",
           "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]), **(extra_env or {}),
           # the subprocess's step record is mirrored to the parent's ledger location (never lost with tmp_path)
           "BC2RL_STEPS_MIRROR": (str(Path(os.environ["MAE_RUN_DIR"]) / "env_steps") if os.environ.get("MAE_RUN_DIR")
                                  else str(PROJECT / ".mae/unmanaged_actions"))}
    env.pop("BC2RL_TEST_SIGTERM_AT", None) if not extra_env else None
    r = subprocess.run([sys.executable, "-m", "bc2rl.rl", *args, "--config", str(cfg_path)], env=env,
                       capture_output=True, text=True)
    return d, r


@need
def test_sigterm_checkpoint_pause_and_exact_resume(tmp_path):
    cfg_path, proj = setup(tmp_path)
    _, r = job(proj, "probe", ["probe", "--K", "3", "--bc-run", "bc", "--bc-update", "4000", "--seed", "0"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    straight, r = job(proj, "straight", ["branch", "--probe-run", "@/probe", "--arm", "01s"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    s0 = json.loads((straight / "summary.json").read_text())
    assert not (straight / "recovery.pt").exists()                 # removed at completion; endpoint states kept
    assert sorted(s0["state_hashes"]) == ["1024", "2048"]
    # SIGTERM after 1,280 actions (past the 1,024 endpoint and its saved state; not a recovery point)
    paused, r = job(proj, "paused", ["branch", "--probe-run", "@/probe", "--arm", "01s"], cfg_path,
                    {"BC2RL_TEST_SIGTERM_AT": "1280"})
    assert r.returncode == 75, r.stdout + r.stderr
    assert not (paused / "summary.json").exists()                  # never complete
    pz = json.loads((paused / "paused.json").read_text())
    assert pz["resume_point"]["at"] == 1280 and pz["resume_point"]["file"] == "recovery.pt"
    assert pz["evals_done"] == [1024] and pz["states_saved"] == [1024] and pz["train_actions_this_job"] == 1280
    import torch
    from bc2rl import ppo as PP
    rec = torch.load(paused / "recovery.pt", map_location="cpu", weights_only=False)
    assert PP.state_hash(rec["state"]) == rec["hash"] == pz["resume_point"]["hash"]
    assert rec["meta"]["post_probe_actions"] == 1280
    # partial accounting: the ledger counts the paused job's training and evaluation actions
    sys.path.insert(0, str(ROOT / "tools"))
    import ledger
    acts, kind = ledger.job_actions(paused)
    steps = sum(json.loads(p.read_text())["actions"] for p in (paused / "env_steps").glob("*.json"))
    assert acts["train"] == 1280 and sum(acts.values()) >= steps - 0 and sum(acts.values()) == steps
    # resume from the recovery state: identical endpoint state and evaluation to the uninterrupted branch
    resumed, r = job(proj, "resumed", ["resume", "--state", "@/paused/recovery.pt"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    s2 = json.loads((resumed / "summary.json").read_text())
    assert s2["state_hashes"]["2048"] == s0["state_hashes"]["2048"]
    assert s2["final"] == s0["final"] and [e["actions"] for e in s2["evals"]] == [2048]
    assert s2["actions"]["train"] == 2048 - 1280
    a = (straight / "attempts_e2048.jsonl").read_text()
    assert (resumed / "attempts_e2048.jsonl").read_text() == a


@need
def test_job_refuses_admission_with_pause_flag(tmp_path):
    cfg_path, proj = setup(tmp_path)
    (proj / ".mae/monitor").mkdir(parents=True)
    (proj / ".mae/monitor/BATTERY_PAUSE.json").write_text("{}")
    d, r = job(proj, "probe", ["probe", "--K", "3", "--bc-run", "bc", "--bc-update", "4000", "--seed", "0"], cfg_path)
    assert r.returncode == 75 and not (d / "summary.json").exists() and not (d / "env_steps").exists()


@need
def test_arrival_capture_rule(tmp_path):
    """Captured first-crossing states restore exactly, keep the original clock, and follow donor order."""
    import torch
    from bc2rl import arrival_bank as AB
    from bc2rl import model as M
    from bc2rl import task as T
    lay = json.loads((DS / "layouts.json").read_text())
    donors = [T.Layout.from_dict(it["layout"]) for it in lay["dev_eval"] if it["layout"]["K"] == 3][:9]
    ck = torch.load(BC, map_location="cpu", weights_only=False)
    actors = []
    for _ in range(3):
        a = M.Actor()
        a.load_state_dict(ck["actor"])
        actors.append(a)
    kept, records, n = AB.collect(actors, donors, 1234, 3, 1, torch.device("cpu"))
    assert len(records) == 9 and all(r["source"] == r["donor_index"] % 3 for r in records)
    arrived = [r["donor_index"] for r in records if r["arrival"] is not None and r["arrival"]["remaining"] >= 1]
    assert [k["donor_index"] for k in kept] == arrived[:3]
    for k in kept:
        env = T.StageTask()
        obs, info = env.reset(options={"snapshot": k["snapshot"]})
        assert info["accessed"] and info["step_count"] == k["tau"] and env.layout.limit - env.step_count == k["remaining"]
