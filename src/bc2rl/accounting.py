"""Environment-step accounting at the common boundary (StageTask.step).

Inside a runner job (MAE_RUN_DIR set) each process records its count in $MAE_RUN_DIR/env_steps/<pid>-<start>.json.
The job's own summaries stay the ledger source; tools/ledger.py uses these records only for jobs without one
(software tests run through the runner), and they cross-check the summaries' action counters.
Outside the runner (tests, interactive checks) every process records its cumulative step count in
<project>/.mae/unmanaged_actions/<pid>-<start>.json (rewritten every FLUSH steps and at exit), which
tools/ledger.py adds as measured outside-runner actions. Outside the runner a process also stops with an error
after BC2RL_UNMANAGED_ACTION_LIMIT steps (default 1,000,000), so an unmanaged check cannot grow unnoticed.
"""
import atexit
import json
import os
from pathlib import Path
import sys
import time

FLUSH = 10_000
_n = 0
_managed = bool(os.environ.get("MAE_RUN_DIR"))
_limit = int(os.environ.get("BC2RL_UNMANAGED_ACTION_LIMIT", "1000000"))
_start = time.time()
_path = None
# The record directory is fixed at import, before any in-process test can change MAE_RUN_DIR (the RL smoke tests
# point it at temporary job directories; fixed 2026-11-01 after r2-smoke's records were lost with them).
_steps_dir = Path(os.environ["MAE_RUN_DIR"]) / "env_steps" if _managed else None


def _record():
    global _path
    if _n == 0:
        return
    if _path is None:
        if _managed:
            d = _steps_dir
        else:
            root = Path(os.environ.get("MAE_PROJECT", Path(__file__).resolve().parents[2]))
            d = root / ".mae" / "unmanaged_actions"
        d.mkdir(parents=True, exist_ok=True)
        _path = d / f"{os.getpid()}-{int(_start)}.json"
    tmp = _path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"pid": os.getpid(), "argv": sys.argv, "started": _start, "updated": time.time(),
                               "actions": _n}))
    tmp.replace(_path)


def count():
    """Called once per environment step."""
    global _n
    _n += 1
    if _n % FLUSH == 0:
        _record()
    if not _managed:
        if _n > _limit:
            _record()
            raise RuntimeError(f"unmanaged environment steps exceed BC2RL_UNMANAGED_ACTION_LIMIT={_limit}; "
                               "run heavy work through the runner")


def total():
    return _n


atexit.register(_record)
