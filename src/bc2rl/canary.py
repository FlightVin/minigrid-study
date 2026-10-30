"""Non-scientific resource canaries for the mae runner (M0).

Modes:
  cpu      spawn N busy CPU children for a fixed time (tests CPU duty cycling and child cleanup)
  memory   allocate memory in small steps up to a ceiling, then hold (tests the memory stop)
  sleep    hold idle with live children (tests wall limit, owner stop and child cleanup)
  mps      run small MPS work with or without telemetry (tests missing/stale telemetry stops)

Each mode writes child PIDs and create times to MAE_RUN_DIR/children.json so cleanup can be
verified after the batch, and a summary.json if it finishes normally.
"""
import argparse
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import time

import psutil

RUN_DIR = Path(os.environ.get("MAE_RUN_DIR", "."))


def busy(seconds):
    end = time.monotonic() + seconds
    x = 0
    while time.monotonic() < end:
        x += 1


def idle(seconds):
    time.sleep(seconds)


def start_children(n, target, seconds):
    ctx = mp.get_context("spawn")
    procs = [ctx.Process(target=target, args=(seconds,)) for _ in range(n)]
    for p in procs:
        p.start()
    record = [{"pid": p.pid, "created": psutil.Process(p.pid).create_time()} for p in procs]
    (RUN_DIR / "children.json").write_text(json.dumps(record))
    return procs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["cpu", "memory", "sleep", "mps"])
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--memory-mb", type=int, default=0)
    ap.add_argument("--telemetry", choices=["on", "off", "stale"], default="on")
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, lambda *_: os._exit(143))
    from bc2rl.telemetry import resource_heartbeat
    t0 = time.time()
    procs = []
    if a.mode == "cpu":
        procs = start_children(a.children, busy, a.seconds)
        for p in procs:
            p.join()
    elif a.mode == "sleep":
        procs = start_children(a.children, idle, a.seconds)
        for p in procs:
            p.join()
    elif a.mode == "memory":
        chunks = []
        while len(chunks) * 64 < a.memory_mb:
            chunks.append(bytearray(64 * 2 ** 20))  # 64 MiB, touched by allocation
            time.sleep(0.25)
        time.sleep(a.seconds)
    elif a.mode == "mps":
        import torch
        x = torch.randn(512, 512, device="mps")
        end = time.monotonic() + a.seconds
        beats = 0
        while time.monotonic() < end:
            x = torch.tanh(x @ x / 512)
            torch.mps.synchronize()
            if a.telemetry == "on" or (a.telemetry == "stale" and beats == 0):
                resource_heartbeat()
                beats += 1
            time.sleep(1)
    (RUN_DIR / "summary.json").write_text(json.dumps(
        {"mode": a.mode, "wall_seconds": time.time() - t0, "completed": True}))


if __name__ == "__main__":
    main()
