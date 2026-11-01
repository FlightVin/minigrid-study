"""Environment steps outside the runner are recorded and capped (src/bc2rl/accounting.py)."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
PROJECT = Path(os.environ.get("MAE_PROJECT", ROOT))     # data are untracked; a runner job runs from a source snapshot
DS = PROJECT / "data/dev-v2/layouts.json"
SCRIPT = f"""
import json
from bc2rl import task as T
L = T.Layout.from_dict(json.load(open({str(DS)!r}))["dev_eval"][0]["layout"])
env = T.StageTask()
env.reset(options={{"layout": L}})
for i in range(N):
    _, _, term, trunc, _ = env.step(0)
    if term or trunc:
        env.reset(options={{"layout": L}})
"""
pytestmark = pytest.mark.skipif(not DS.exists(), reason="needs dev-v2 data")


def run(tmp_path, n, **env):
    e = {k: v for k, v in os.environ.items() if k != "MAE_RUN_DIR"}
    e.update(MAE_PROJECT=str(tmp_path), PYTHONPATH=str(ROOT / "src"), **env)
    return subprocess.run([sys.executable, "-c", f"N = {n}\n" + SCRIPT], env=e, capture_output=True, text=True)


def test_unmanaged_steps_are_recorded(tmp_path):
    r = run(tmp_path, 300)
    assert r.returncode == 0, r.stderr
    recs = [json.loads(p.read_text()) for p in (tmp_path / ".mae/unmanaged_actions").glob("*.json")]
    assert len(recs) == 1 and recs[0]["actions"] == 300


def test_unmanaged_limit_stops_the_process(tmp_path):
    r = run(tmp_path, 500, BC2RL_UNMANAGED_ACTION_LIMIT="200")
    assert r.returncode != 0 and "BC2RL_UNMANAGED_ACTION_LIMIT" in r.stderr
    rec = json.loads(next((tmp_path / ".mae/unmanaged_actions").glob("*.json")).read_text())
    assert rec["actions"] == 201


def test_runner_jobs_record_in_their_run_dir(tmp_path):
    r = run(tmp_path, 100, MAE_RUN_DIR=str(tmp_path / "job"))
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / ".mae/unmanaged_actions").exists()
    recs = [json.loads(p.read_text()) for p in (tmp_path / "job/env_steps").glob("*.json")]
    assert len(recs) == 1 and recs[0]["actions"] == 100


def test_record_dir_fixed_at_import_not_by_later_env_changes(tmp_path):
    """A test inside a runner job that changes MAE_RUN_DIR (RL smoke tests) must not move the job's step record."""
    code = ("import os; from bc2rl import accounting as A; os.environ['MAE_RUN_DIR'] = %r\n"
            "for _ in range(25): A.count()\n" % str(tmp_path / "elsewhere"))
    e = {**os.environ, "MAE_RUN_DIR": str(tmp_path / "job"), "PYTHONPATH": str(ROOT / "src")}
    subprocess.run([sys.executable, "-c", code], env=e, check=True)
    recs = list((tmp_path / "job/env_steps").glob("*.json"))
    assert len(recs) == 1 and json.loads(recs[0].read_text())["actions"] == 25
    assert not (tmp_path / "elsewhere").exists()
