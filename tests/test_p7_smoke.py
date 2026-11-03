"""Programme 2026-11-02c smoke (Amendment 9, section 5 checks): real probe and branch jobs for arms 00, C7 and R7 from
one fork on dev-v2 (CPU, tiny budgets); identical fork state; C7 executes learner actions only; R7 reproduces C7's
per-update example counts; recovery-bank agreement is recorded; exact checkpoint-and-pause/resume for C7 and R7;
executed actions match the step records. Opt-in (BC2RL_SMOKE=1): executes environment actions, counted by the
runner when run as a job."""
import json
import os

import numpy as np
import pytest

from test_pause_smoke import BC, DS, ROOT, job

pytestmark = pytest.mark.skipif(os.environ.get("BC2RL_SMOKE") != "1", reason="set BC2RL_SMOKE=1")
need = pytest.mark.skipif(not (DS.exists() and BC.exists()), reason="needs dev-v2 data and a BC checkpoint")


def recovery_bank(proj):
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bc2rl import corrective as CR
    from bc2rl import task as T
    lay = json.loads((DS / "layouts.json").read_text())["dev_bank"]
    states = []
    for it in [x for x in lay if x["layout"]["K"] == 3][:4]:
        env = T.StageTask()
        obs, _ = env.reset(options={"layout": T.Layout.from_dict(it["layout"])})
        q = CR.query(env)
        states.append({"obs": {"grid": obs["grid"].tolist(), "aux": obs["aux"].tolist(), "time": obs["time"].tolist()},
                       "mask": q["mask"], "stratum": "on_track"})
    (proj / "data/rbank.json").write_text(json.dumps({"sha256": "smoke", "states": states}))


def setup(tmp_path):
    cfg = json.loads((ROOT / "experiments/m2/ppo-canary-v1.json").read_text())
    cfg.update(critic_warmup_actions=300, critic_prefit_steps=5, probe_actions=256, n_steps=64, n_envs=4,
               diag_attempts=1, diag_bank_attempts=1, continuation_actions=2048, kl_coef=0.01, diag_role="dev_bank",
               alpha=0.0, certify_arrivals=True, trace_eval=True, track_allocation=True, aux_coef=0.1,
               aux_cap=200, aux_quota=40, recovery_bank="data/rbank.json", update_diagnostics=True,
               eval_schedule=[{"at": 1024, "attempts": 1, "bank_attempts": 0, "tag": "e1024"},
                              {"at": 2048, "attempts": 2, "bank_attempts": 0, "tag": "e2048"}],
               save_state_at=[1024, 2048], recovery_every=512)
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg))
    proj = tmp_path / "project"
    (proj / ".mae/runs/bc").mkdir(parents=True)
    os.symlink(BC, proj / ".mae/runs/bc/actor_u4000.pt")
    (proj / "data").mkdir()
    os.symlink(DS, proj / "data/dev-v2")
    recovery_bank(proj)
    return cfg_path, proj


def steps(d):
    return sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))


@need
def test_aux_arms_fork_schedule_accounting_and_exact_resume(tmp_path):
    cfg_path, proj = setup(tmp_path)
    _, r = job(proj, "probe", ["probe", "--K", "3", "--bc-run", "bc", "--bc-update", "4000", "--seed", "0"], cfg_path)
    assert r.returncode == 0, r.stdout + r.stderr
    out = {}
    for name, args in (("A", ["--arm", "00"]), ("C", ["--arm", "C7"]), ("R", ["--arm", "R7", "--match-run", "@/C"])):
        out[name], r = job(proj, name, ["branch", "--probe-run", "@/probe", *args], cfg_path)
        assert r.returncode == 0, r.stdout + r.stderr
    S = {k: json.loads((d / "summary.json").read_text()) for k, d in out.items()}
    assert len({s["fork_hash"] for s in S.values()}) == 1                 # identical starting state
    for k, s in S.items():
        assert steps(out[k]) == sum(s["actions"].values())               # every executed action is recorded
        assert s["counters"]["env_actions"] - s["base_actions"] == 2048   # the learner executed every training action
        assert set(s["recovery_agreement"]) == {"0", "1024", "2048"}
        assert s["recovery_agreement"]["0"] == S["A"]["recovery_agreement"]["0"]
    assert S["A"]["aux"] is None
    c, rr = S["C"]["aux"], S["R"]["aux"]
    assert 0 < c["queried_states"] <= 200 and c["labelled_examples"] > 0 and c["observation_conflicts"] == 0
    assert rr["matched_to_C"] and rr["labelled_examples"] == c["labelled_examples"]
    sc = json.loads((out["C"] / "aux_schedule.json").read_text())
    sr = json.loads((out["R"] / "aux_schedule.json").read_text())
    assert sc["labelled_per_update"] == sr["labelled_per_update"] and all(h["stride"] >= 4 for h in sc["history"])
    recs = [json.loads(l) for l in (out["C"] / "metrics.jsonl").read_text().splitlines()]
    upd = [x for x in recs if x.get("phase") == "branch"]
    assert len(upd) == 8 and all(np.isfinite(x["approx_kl"]) and "clipfrac" in x and "entropy" in x for x in upd)
    assert any(x.get("aux_n", 0) > 0 and x["aux_grad_norm"] > 0 and np.isfinite(x["aux_ce"]) for x in upd)
    assert all("aux_ce" not in x for x in [json.loads(l) for l in (out["A"] / "metrics.jsonl").read_text().splitlines()]
               if x.get("phase") == "branch")
    # checkpoint-and-pause / resume reproduces the uninterrupted C7 and R7 branches exactly
    for name, args in (("C", ["--arm", "C7"]), ("R", ["--arm", "R7", "--match-run", "@/C"])):
        paused, r = job(proj, f"{name}p", ["branch", "--probe-run", "@/probe", *args], cfg_path,
                        {"BC2RL_TEST_SIGTERM_AT": "768"})
        assert r.returncode == 75, r.stdout + r.stderr
        resumed, r = job(proj, f"{name}r", ["resume", "--state", f"@/{name}p/recovery.pt"], cfg_path)
        assert r.returncode == 0, r.stdout + r.stderr
        s2 = json.loads((resumed / "summary.json").read_text())
        assert s2["state_hashes"]["2048"] == S[name]["state_hashes"]["2048"] and s2["final"] == S[name]["final"]
        strip = lambda x: {**x, "planner": {k: v for k, v in x["planner"].items() if k != "planner_seconds"}} \
            if "planner" in x else x
        assert strip(s2["aux"]) == strip(S[name]["aux"])
        assert (resumed / "attempts_e2048.jsonl").read_text() == (out[name] / "attempts_e2048.jsonl").read_text()
        assert steps(paused) + steps(resumed) == steps(out[name])
