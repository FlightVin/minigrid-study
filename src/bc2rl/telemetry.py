"""Atomic resource heartbeats for the mae runner (adapted from the harness template).

A background thread writes `MAE_TELEMETRY` every `interval` seconds, so long BC, evaluation,
data-generation and checkpoint phases keep telemetry fresh. The thread only reads the
process-wide MPS driver counter; it never runs model operations. Outside the runner
(no `MAE_TELEMETRY`), every function is a no-op.
"""
import json
import os
from pathlib import Path
import threading
import time


def _mps_bytes():
    if os.environ.get("MAE_DEVICE") != "mps":
        return 0
    import torch
    return int(torch.mps.driver_allocated_memory())


def resource_heartbeat(extra=None):
    target = os.environ.get("MAE_TELEMETRY")
    if not target:
        return
    path = Path(target)
    data = {"timestamp": time.time(), "mps_driver_bytes": _mps_bytes()}
    if extra:
        data.update(extra)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.replace(path)


class Heartbeat:
    """Context manager that keeps telemetry fresh from a daemon thread."""

    def __init__(self, interval=5.0):
        self.interval = interval
        self._stop = threading.Event()
        self._thread = None

    def _loop(self):
        while not self._stop.wait(self.interval):
            resource_heartbeat()

    def __enter__(self):
        resource_heartbeat()
        if os.environ.get("MAE_TELEMETRY"):
            self._thread = threading.Thread(target=self._loop, name="mae-heartbeat", daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval + 1)
        resource_heartbeat()
        return False
