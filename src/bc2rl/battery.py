"""Battery rule (owner instruction 2026-11-01c): stop scientific execution when the reported charge is 31% or lower,
also on AC power. Shared by the guard (tools/battery_guard.py), the driver (tools/run_program4.py) and every heavy
job at start (bc2rl.bc, bc2rl.rl, bc2rl.arrival_bank).

Persistent pause flag: <project>/.mae/monitor/BATTERY_PAUSE.json. Only the owner's explicit instruction clears it
(the agent deletes it then). No code path removes it, so recovery above 31% never restarts work.
Admission hold: <project>/.mae/monitor/BATTERY_HOLD.json while readings are unavailable (cleared by the guard once a
reading works again); no new job or batch starts while it exists.
Jobs that refuse admission, or that checkpoint and stop after SIGTERM, exit with PAUSED_EXIT (75).
"""
import json
import os
from pathlib import Path
import re
import subprocess
import time

LIMIT = 31                 # inclusive: 31% or lower stops execution
PAUSED_EXIT = 75
HORIZON_S = 300            # time to the next safe checkpoint, conservatively (recovery interval + one evaluation)
RATE_WINDOW_S = 900        # discharge rate from readings in the last 15 minutes ...
RATE_MIN_SPAN_S = 300      # ... spanning at least 5 minutes
UNAVAILABLE_ESCALATE = 8   # consecutive failed readings (about 2 minutes at 15 s) -> full pause


def project_root():
    return Path(os.environ.get("MAE_PROJECT", Path(__file__).resolve().parents[2]))


def flag_path(root=None):
    return Path(root or project_root()) / ".mae/monitor/BATTERY_PAUSE.json"


def hold_path(root=None):
    return Path(root or project_root()) / ".mae/monitor/BATTERY_HOLD.json"


def parse_pmset(text):
    """(percent, source) from `pmset -g batt` output, or None when no internal battery reading is present."""
    m = re.search(r"InternalBattery[^\n]*?\t(\d+)%", text) or re.search(r"(\d+)%;", text)
    if not m:
        return None
    src = "AC" if "AC Power" in text else ("battery" if "Battery Power" in text else "unknown")
    return int(m.group(1)), src


def read(runner=None):
    """One lightweight reading. Never raises; None means unavailable (treated as insufficient charge)."""
    try:
        out = (runner or (lambda: subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True,
                                                 timeout=10).stdout))()
        return parse_pmset(out)
    except Exception:
        return None


def discharge_rate(history, now):
    """Percent per second from (t, percent) readings in the window; None if the span is too short. Negative when
    discharging. Least-squares slope."""
    pts = [(t, p) for t, p in history if now - t <= RATE_WINDOW_S]
    if len(pts) < 3 or pts[-1][0] - pts[0][0] < RATE_MIN_SPAN_S:
        return None
    ts = [t for t, _ in pts]
    ps = [p for _, p in pts]
    mt, mp = sum(ts) / len(ts), sum(ps) / len(ps)
    var = sum((t - mt) ** 2 for t in ts)
    return sum((t - mt) * (p - mp) for t, p in pts) / var if var > 0 else None


def decide(reading, history, now, unavailable_streak=0):
    """Pure decision for one poll. reading: (percent, source) or None. history: earlier (t, percent).
    Returns (decision, detail): "ok", "pause" (persistent), or "hold" (admission hold; readings unavailable)."""
    if reading is None:
        if unavailable_streak + 1 >= UNAVAILABLE_ESCALATE:
            return "pause", {"reason": "battery readings unavailable", "streak": unavailable_streak + 1}
        return "hold", {"reason": "battery reading unavailable", "streak": unavailable_streak + 1}
    pct, src = reading
    if pct <= LIMIT:
        return "pause", {"reason": f"charge {pct}% <= {LIMIT}%", "percent": pct, "source": src}
    rate = discharge_rate(history + [(now, pct)], now)
    if rate is not None and rate < 0:
        predicted = pct + rate * HORIZON_S
        if predicted <= LIMIT:
            return "pause", {"reason": f"predicted {predicted:.2f}% <= {LIMIT}% within {HORIZON_S} s",
                             "percent": pct, "source": src, "rate_pct_per_hour": rate * 3600}
        return "ok", {"percent": pct, "source": src, "rate_pct_per_hour": rate * 3600, "predicted": predicted}
    return "ok", {"percent": pct, "source": src, "rate_pct_per_hour": None if rate is None else rate * 3600}


def write_atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1))
    os.replace(tmp, path)


def set_pause(detail, root=None):
    """Write the persistent pause flag once (the first trigger is kept)."""
    p = flag_path(root)
    if not p.exists():
        write_atomic(p, {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "unix": time.time(), **detail,
                         "rule": f"stop at {LIMIT}% or lower (owner instruction 2026-11-01c)",
                         "clear": "only on the owner's explicit instruction to resume"})
    return p


def admission(root=None, reader=None, retries=3, wait_s=10.0, sleep=time.sleep):
    """(ok, detail) for starting a heavy job or batch now. Refuses while the pause flag or the admission hold exists,
    when the charge is 31% or lower, and when readings stay unavailable after `retries` attempts."""
    if flag_path(root).exists():
        return False, {"reason": "battery pause flag present", "flag": str(flag_path(root))}
    if hold_path(root).exists():
        return False, {"reason": "battery admission hold present (readings unavailable)"}
    for i in range(retries):
        r = read(reader)
        if r is not None:
            pct, src = r
            return pct > LIMIT, {"percent": pct, "source": src,
                                 **({} if pct > LIMIT else {"reason": f"charge {pct}% <= {LIMIT}%"})}
        if i + 1 < retries:
            sleep(wait_s)
    return False, {"reason": "battery reading unavailable"}


def require_admission(what):
    """Called at the start of a heavy job. Exits with PAUSED_EXIT (no work done) when admission is refused."""
    ok, det = admission()
    print(json.dumps({"event": "battery_admission", "job": what, "admit": ok, **det}), flush=True)
    if not ok:
        raise SystemExit(PAUSED_EXIT)
