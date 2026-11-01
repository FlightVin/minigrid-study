"""Writes the R1 batch files (PROTOCOL_FREEZE Amendment 3). Deterministic; run from the project root.

  data.batch.json            r1-v1 generation (CPU)
  tests.batch.json           the default test suite as a runner job (CPU; no opt-in RL smoke tests)
  canary-s15.batch.json      engineering canary: r1-bc-s15, r1-probe-K3-u4000-s15, r1-K3-u4000-s15-01-kl0p01
  seed-s15-rest.batch.json   (with --canary-batch B) the other probe and three branches of seed 15
  seed-s<S>.batch.json       for S in 16..22: BC, 2 probes, 4 branches; probe and branch order shuffled with seed 20261031 + S
"""
import argparse
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONF = "experiments/r1/r1-v1.json"
BC = "experiments/m4/bc-v1.json"          # unchanged joint BC dataset (conf-v1 = dev-v2 training roles) and sampler
ARMS = {"00": "00", "01": "01-kl0p01"}
UPDATES = (4000, 16000)


def job(i, cmd, device="mps", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def bc(s):
    return job(f"r1-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)])


def probe(s, u, bc_run):
    return job(f"r1-probe-K3-u{u}-s{s}", ["bc2rl.rl", "probe", "--config", CONF, "--K", "3", "--bc-run", bc_run,
                                         "--bc-update", str(u), "--seed", str(s)])


def branch(s, u, arm, probe_run):
    return job(f"r1-K3-u{u}-s{s}-{ARMS[arm]}", ["bc2rl.rl", "branch", "--config", CONF, "--probe-run", probe_run, "--arm", arm])


def write(name, jobs):
    (HERE / name).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary-batch")
    a = ap.parse_args()
    if a.canary_batch:
        c = a.canary_batch
        write("seed-s15-rest.batch.json", [probe(15, 16000, f"{c}/r1-bc-s15"),
                                           branch(15, 4000, "00", f"{c}/r1-probe-K3-u4000-s15"),
                                           branch(15, 16000, "00", "@/r1-probe-K3-u16000-s15"),
                                           branch(15, 16000, "01", "@/r1-probe-K3-u16000-s15")])
        return
    write("data.batch.json", [job("r1-data-r1-v1", ["bc2rl.data", "--config", "experiments/r1/data-r1-v1.json"], "cpu", 2)])
    write("tests.batch.json", [job("r1-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2)])
    write("canary-s15.batch.json", [bc(15), probe(15, 4000, "@/r1-bc-s15"), branch(15, 4000, "01", "@/r1-probe-K3-u4000-s15")])
    for s in range(16, 23):
        rng = random.Random(20261031 + s)
        us = list(UPDATES)
        rng.shuffle(us)
        branches = [branch(s, u, arm, f"@/r1-probe-K3-u{u}-s{s}") for u in UPDATES for arm in ARMS]
        rng.shuffle(branches)
        write(f"seed-s{s}.batch.json", [bc(s)] + [probe(s, u, f"@/r1-bc-s{s}") for u in us] + branches)


if __name__ == "__main__":
    main()
