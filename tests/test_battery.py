"""Battery rule 31% or lower (owner instruction 2026-11-01c): simulated readings only; the real battery is never
drained. Covers the guard decision, persistence of the pause flag, the admission hold, STOP of a running batch,
job and driver admission, and paused-versus-complete status in the driver."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from bc2rl import battery as B    # noqa: E402

AC = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=23134307)\t{p}%; charging; 1:53 remaining present: true\n"
BAT = "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=23134307)\t{p}%; discharging; 3:10 remaining present: true\n"


def test_parse_pmset():
    assert B.parse_pmset(AC.format(p=85)) == (85, "AC")
    assert B.parse_pmset(BAT.format(p=32)) == (32, "battery")
    assert B.parse_pmset("Now drawing from 'AC Power'\n") is None
    assert B.parse_pmset("") is None
    assert B.read(lambda: (_ for _ in ()).throw(OSError("pmset failed"))) is None


@pytest.mark.parametrize("pct,src,expect", [(32, "battery", "ok"), (31, "battery", "pause"), (30, "battery", "pause"),
                                            (32, "AC", "ok"), (31, "AC", "pause"), (30, "AC", "pause"), (85, "AC", "ok")])
def test_threshold_inclusive_also_on_ac(pct, src, expect):
    assert B.decide((pct, src), [], 1000.0)[0] == expect


def test_unavailable_reading_holds_then_pauses():
    assert B.decide(None, [], 0.0, 0)[0] == "hold"
    assert B.decide(None, [], 0.0, B.UNAVAILABLE_ESCALATE - 2)[0] == "hold"
    assert B.decide(None, [], 0.0, B.UNAVAILABLE_ESCALATE - 1)[0] == "pause"


def test_discharge_rate_pauses_early():
    now = 10_000.0
    fast = [(now - 600, 38), (now - 300, 35)]            # -36 %/h: 32 now -> ~29 within 300 s
    assert B.decide((32, "battery"), fast, now)[0] == "pause"
    slow = [(now - 600, 33), (now - 300, 33)]            # -6 %/h: 32 -> 31.5
    assert B.decide((32, "battery"), slow, now)[0] == "ok"
    charging = [(now - 600, 30), (now - 300, 31)]
    assert B.decide((32, "AC"), charging, now)[0] == "ok"
    short = [(now - 60, 40)]                              # span too short for a rate
    assert B.decide((32, "battery"), short, now)[0] == "ok"


def test_guard_step_flag_persists_and_stops_batch(tmp_path):
    import battery_guard as G
    stopped = []
    st = {"history": [], "streak": 0}
    assert G.step(st, (40, "AC"), 0.0, tmp_path, lambda: stopped.append(1))[0] == "ok"
    assert not B.flag_path(tmp_path).exists()
    assert G.step(st, None, 15.0, tmp_path, lambda: stopped.append(1))[0] == "hold"
    assert B.hold_path(tmp_path).exists() and not B.flag_path(tmp_path).exists()
    assert G.step(st, (40, "AC"), 30.0, tmp_path, lambda: stopped.append(1))[0] == "ok"
    assert not B.hold_path(tmp_path).exists()
    d, det = G.step(st, (31, "AC"), 45.0, tmp_path, lambda: stopped.append(1) or "batchX")
    assert d == "pause" and det["stopped_batch"] == "batchX" and stopped == [1]
    flag = json.loads(B.flag_path(tmp_path).read_text())
    assert flag["percent"] == 31
    # charging back above 31% never clears the flag
    assert G.step(st, (90, "AC"), 60.0, tmp_path, lambda: None)[0] == "ok"
    assert B.flag_path(tmp_path).exists() and json.loads(B.flag_path(tmp_path).read_text())["percent"] == 31


def test_stop_running_batch_requires_supervisor_identity(tmp_path):
    import os
    import psutil
    import battery_guard as G
    out = tmp_path / "batch"
    out.mkdir()
    cur = tmp_path / "current.json"
    cur.write_text(json.dumps({"status": "running", "batch": "b1", "out": str(out), "supervisor_pid": os.getpid(),
                               "supervisor_created": psutil.Process().create_time()}))
    assert G.stop_running_batch(cur) == "b1" and (out / "STOP").exists()
    (out / "STOP").unlink()
    cur.write_text(json.dumps({"status": "running", "batch": "b1", "out": str(out), "supervisor_pid": os.getpid(),
                               "supervisor_created": 1.0}))                 # stale identity: not ours
    assert G.stop_running_batch(cur) is None and not (out / "STOP").exists()
    cur.write_text(json.dumps({"status": "exited", "batch": "b1", "out": str(out)}))
    assert G.stop_running_batch(cur) is None


def test_admission(tmp_path):
    sleeps = []
    ok = lambda p: (lambda: AC.format(p=p))
    assert B.admission(tmp_path, ok(32), sleep=sleeps.append)[0] is True
    assert B.admission(tmp_path, ok(31), sleep=sleeps.append)[0] is False
    assert B.admission(tmp_path, ok(30), sleep=sleeps.append)[0] is False
    assert B.admission(tmp_path, lambda: "", retries=3, wait_s=10, sleep=sleeps.append)[0] is False
    assert sleeps == [10, 10]                              # retried lightweight readings, then refused
    B.write_atomic(B.hold_path(tmp_path), {})
    assert B.admission(tmp_path, ok(90))[0] is False
    B.hold_path(tmp_path).unlink()
    B.set_pause({"percent": 31}, tmp_path)
    assert B.admission(tmp_path, ok(95))[0] is False       # the flag wins over any later reading


def test_require_admission_exits_75(tmp_path, monkeypatch):
    monkeypatch.setenv("MAE_PROJECT", str(tmp_path))
    B.set_pause({"percent": 30}, tmp_path)
    with pytest.raises(SystemExit) as e:
        B.require_admission("test")
    assert e.value.code == B.PAUSED_EXIT == 75


def test_driver_paused_status_and_guard(tmp_path, monkeypatch):
    import run_program4 as D
    monkeypatch.setattr(D, "ROOT", tmp_path)
    out = tmp_path / "batch"
    out.mkdir()
    (out / "execution.json").write_text(json.dumps({"jobs": {"a": {"returncode": 0}, "b": {"returncode": 75}}}))
    assert D.paused_after(str(out)) is True
    (out / "execution.json").write_text(json.dumps({"jobs": {"a": {"returncode": 1}}}))
    assert D.paused_after(str(out)) is False
    B.set_pause({"percent": 31}, tmp_path)
    assert D.paused_after(str(out)) is True
    assert D.guard_ok()[0] is False                        # no guard running in this sandbox -> refuse
