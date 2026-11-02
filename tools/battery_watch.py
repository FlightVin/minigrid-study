"""HISTORICAL; superseded on 2026-11-01c by tools/battery_guard.py (stop at 31% or lower, 15 s polling). Do not run.
Battery watch (owner instructions 2026-10-31 and 2026-11-01): check every 5 minutes; below 20%, stop any running
mae batch (STOP file), write .mae/monitor/battery_low.flag and exit 2 so the agent ends execution.
Run as a managed background task: .venv/bin/python -I tools/battery_watch.py >> .mae/monitor/battery_watch.log"""
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".mae/current.json"
MON = ROOT / ".mae/monitor"
LIMIT = 20


def log(**k):
    print(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M:%S"), **k}), flush=True)


MON.mkdir(parents=True, exist_ok=True)
(MON / "battery_watch.pid").write_text(json.dumps({"pid": __import__("os").getpid(), "started": time.time()}))
log(event="watch_started", limit=LIMIT, interval_s=300)
while True:
    out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
    pct = int(re.search(r"(\d+)%", out).group(1))
    log(event="battery", percent=pct, source="AC" if "AC Power" in out else "battery")
    if pct < LIMIT:
        s = json.loads(STATE.read_text()) if STATE.exists() else {}
        if s.get("status") == "running":
            Path(s["out"], "STOP").write_text("battery watch: below 20%\n")
            log(event="stop_written", batch=s["batch"])
        (MON / "battery_low.flag").write_text(str(pct))
        log(event="battery_low_exit", percent=pct)
        sys.exit(2)
    time.sleep(300)
