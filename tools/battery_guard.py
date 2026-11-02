"""Battery guard (owner instruction 2026-11-01c). Replaces tools/battery_watch.py (20%, 5 min; historical).

Run as a managed background task while the programme is active:
    .venv/bin/python -I tools/battery_guard.py >> .mae/monitor/battery_guard.log 2>&1

Every POLL_S (15 s) it reads `pmset -g batt` and applies bc2rl.battery.decide:
  ok     -> writes .mae/monitor/battery_status.json; clears the admission hold if one exists.
  hold   -> a reading failed: writes the admission hold (no new job or batch starts) and retries next poll.
  pause  -> charge 31% or lower (also on AC), or the recent discharge rate predicts 31% or lower within the next
            safe-checkpoint horizon, or readings unavailable for about 2 minutes:
            1. writes the persistent pause flag (never cleared by code);
            2. if a runner batch is running (supervisor identity verified), writes its STOP file. The runner then sends
               SIGTERM to the job; branch jobs save a recovery state at the next update boundary and exit 75; after the
               runner's bounded grace (stop_grace_seconds, 10 s) any remaining worker is killed;
            3. exits 2, so the agent is notified, records the pause and stops the drivers and review wakeups.
It never shuts down the computer and never changes power settings. It never restarts work.
"""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from bc2rl import battery as B    # noqa: E402

POLL_S = 15
MON = ROOT / ".mae/monitor"
CURRENT = ROOT / ".mae/current.json"


def log(**k):
    print(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), **k}), flush=True)


def stop_running_batch(current=CURRENT):
    """Write STOP into the running batch if its supervisor is alive with the recorded identity. Returns batch id."""
    import psutil
    if not current.exists():
        return None
    s = json.loads(current.read_text())
    if s.get("status") != "running":
        return None
    try:
        alive = abs(psutil.Process(s["supervisor_pid"]).create_time() - s["supervisor_created"]) < 1e-3
    except (psutil.NoSuchProcess, KeyError):
        alive = False
    if not alive:
        return None
    Path(s["out"], "STOP").write_text("battery guard: charge at or below 31% (or predicted / unavailable)\n")
    return s["batch"]


def step(state, reading, now, root=ROOT, stopper=stop_running_batch):
    """One poll. state: {"history": [(t, pct)], "streak": int}. Returns the decision. Side effects on files only."""
    decision, det = B.decide(reading, state["history"], now, state["streak"])
    if reading is None:
        state["streak"] += 1
    else:
        state["streak"] = 0
        state["history"] = [(t, p) for t, p in state["history"] if now - t <= B.RATE_WINDOW_S] + [(now, reading[0])]
    B.write_atomic(Path(root) / ".mae/monitor/battery_status.json", {"unix": now, "decision": decision, **det})
    if decision == "hold":
        B.write_atomic(B.hold_path(root), {"unix": now, **det})
    elif decision == "ok" and B.hold_path(root).exists():
        B.hold_path(root).unlink()
    elif decision == "pause":
        B.set_pause(det, root)
        det["stopped_batch"] = stopper()
    return decision, det


def main():
    MON.mkdir(parents=True, exist_ok=True)
    B.write_atomic(MON / "battery_guard.pid", {"pid": __import__("os").getpid(), "started": time.time()})
    log(event="guard_started", limit=B.LIMIT, inclusive=True, poll_s=POLL_S, horizon_s=B.HORIZON_S)
    if B.flag_path(ROOT).exists():
        log(event="pause_flag_present_at_start", flag=json.loads(B.flag_path(ROOT).read_text()))
        stop_running_batch()
        sys.exit(2)
    state = {"history": [], "streak": 0}
    last_log = 0.0
    while True:
        now = time.time()
        r = B.read()
        decision, det = step(state, r, now)
        if decision != "ok" or now - last_log >= 300:     # log every 5 minutes when nothing happens
            log(event="battery", decision=decision, **det)
            last_log = now
        if decision == "pause":
            log(event="battery_pause", **det)
            sys.exit(2)
        time.sleep(POLL_S)


if __name__ == "__main__":
    main()
