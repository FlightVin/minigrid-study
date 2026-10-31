"""Environment-step accounting at the common boundary (StageTask.step).

Inside a runner job (MAE_RUN_DIR set) the job's own summaries are the ledger source, so this module only counts.
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


def _record():
    global _path
    if _managed or _n == 0:
        return
    if _path is None:
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
    if not _managed:
        if _n % FLUSH == 0:
            _record()
        if _n > _limit:
            _record()
            raise RuntimeError(f"unmanaged environment steps exceed BC2RL_UNMANAGED_ACTION_LIMIT={_limit}; "
                               "run heavy work through the runner")


def total():
    return _n


atexit.register(_record)
