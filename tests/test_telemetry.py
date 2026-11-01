"""Concurrent heartbeat writers must not fail (src/bc2rl/telemetry.py)."""
import json
import threading

from bc2rl import telemetry


def test_concurrent_heartbeats(tmp_path, monkeypatch):
    target = tmp_path / "telemetry.json"
    monkeypatch.setenv("MAE_TELEMETRY", str(target))
    monkeypatch.delenv("MAE_DEVICE", raising=False)
    errors = []

    def write():
        try:
            for _ in range(300):
                telemetry.resource_heartbeat()
        except Exception as e:      # noqa: BLE001 - any failure is the defect
            errors.append(repr(e))

    threads = [threading.Thread(target=write) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert "timestamp" in json.loads(target.read_text())
    assert not list(tmp_path.glob("*.tmp"))
