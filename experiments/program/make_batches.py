"""Writes the batch files and the plan of the 2026-11-01 programme (PROTOCOL_FREEZE Amendment 4). Deterministic;
run from the project root.

R2 (experiments/r2/):
  data.batch.json          r2-v1 generation (CPU)
  tests.batch.json         r2-tests (default suite) + r2-smoke (opt-in RL smoke tests incl. exact resume; CPU)
  drill.batch.json         r2-drill: runner interruption drill (canary sleep with children; stopped by the agent)
  canary-s23.batch.json    engineering canary from the planned sample: r2-bc-s23, r2-probe-K3-u4000-s23,
                           r2-K3-u4000-s23-01-kl0p01
  seed-s23-rest.batch.json (with --canary-batch B) branch 00 of seed 23 from the canary's probe
  seed-s<S>.batch.json     S = 24..42: BC, probe, both branches; branch order shuffled with seed 20261101 + S
E1 cross-panel (experiments/crosspanel/): xp-m4.batch.json (10 jobs), xp-r1.batch.json (16 jobs)
E2 components (experiments/comp/): comp-s<S>.batch.json, S = 15, 16, 17; arm order shuffled with seed 20261102 + S
Final audit: experiments/program/final-tests.batch.json (prog-tests)
plan.json: every batch file in execution order with its study.
"""
import argparse
import json
from pathlib import Path
import random

ROOT = Path(__file__).resolve().parents[2]
R2C = "experiments/r2/r2-v1.json"
BC = "experiments/r2/bc-r2.json"
XPC = "experiments/crosspanel/crosspanel-v1.json"
COMPC = "experiments/comp/comp-v1.json"
ARMS = {"00": "00", "01": "01-kl0p01"}
M4 = {10: "20261031T144443-65814", 11: "20261031T154838-81881", 12: "20261031T165349-92672",
      13: "20261031T175829-2090", 14: "20261031T190210-20242"}
R1 = {15: ("20261101T002041-87256", "20261101T002815-88091"), 16: ("20261101T003945-89279",) * 2,
      17: ("20261101T010311-99104",) * 2, 18: ("20261101T012123-1751",) * 2, 19: ("20261101T013935-7336",) * 2,
      20: ("20261101T015804-10217",) * 2, 21: ("20261101T021657-15496",) * 2, 22: ("20261101T023515-17380",) * 2}
# R1: (batch of branch 01, batch of branch 00); seed 15's 01 branch ran in the canary batch.


def job(i, cmd, device="mps", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def bc(s):
    return job(f"r2-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)])


def probe(s, bc_run):
    return job(f"r2-probe-K3-u4000-s{s}", ["bc2rl.rl", "probe", "--config", R2C, "--K", "3", "--bc-run", bc_run,
                                          "--bc-update", "4000", "--seed", str(s)])


def branch(s, arm, probe_run):
    return job(f"r2-K3-u4000-s{s}-{ARMS[arm]}", ["bc2rl.rl", "branch", "--config", R2C, "--probe-run", probe_run, "--arm", arm])


def write(path, jobs):
    (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary-batch")
    a = ap.parse_args()
    if a.canary_batch:
        write("experiments/r2/seed-s23-rest.batch.json", [branch(23, "00", f"{a.canary_batch}/r2-probe-K3-u4000-s23")])
        return
    plan = []
    add = lambda path, study: plan.append({"file": path, "study": study})
    add(write("experiments/r2/data.batch.json", [job("r2-data-r2-v1", ["bc2rl.data", "--config", "experiments/r2/data-r2-v1.json"], "cpu", 2)]), "r2")
    smoke = {"id": "r2-smoke", "cpu_threads": 1, "memory_gb": 2, "device": "cpu",
             "command": ["env", "BC2RL_SMOKE=1", "{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_rl_smoke.py"]}
    add(write("experiments/r2/tests.batch.json", [job("r2-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2), smoke]), "r2")
    add(write("experiments/r2/drill.batch.json", [job("r2-drill", ["bc2rl.canary", "sleep", "--children", "2", "--seconds", "600"], "cpu", 1)]), "r2")
    plan[-1]["required"] = False      # stopped on purpose (reports/r2/drill.json); never "complete"
    add(write("experiments/r2/canary-s23.batch.json", [bc(23), probe(23, "@/r2-bc-s23"), branch(23, "01", "@/r2-probe-K3-u4000-s23")]), "r2")
    # placeholder until the canary batch id is known; rewritten with --canary-batch B before it runs
    add(write("experiments/r2/seed-s23-rest.batch.json", [branch(23, "00", "CANARY_BATCH/r2-probe-K3-u4000-s23")]), "r2")
    for s in range(24, 43):
        rng = random.Random(20261101 + s)
        br = [branch(s, arm, f"@/r2-probe-K3-u4000-s{s}") for arm in ARMS]
        rng.shuffle(br)
        add(write(f"experiments/r2/seed-s{s}.batch.json", [bc(s), probe(s, f"@/r2-bc-s{s}")] + br), "r2")
    xp = lambda co, s, arm, b, name: job(f"xp-{co}-s{s}-{arm}", ["bc2rl.diag", "crosspanel", "--config", XPC, "--branch", f"{b}/{name}"])
    add(write("experiments/crosspanel/xp-m4.batch.json",
              [xp("m4", s, arm, M4[s], f"m4-K3-u4000-s{s}-{ARMS[arm]}") for s in M4 for arm in ARMS]), "xp")
    add(write("experiments/crosspanel/xp-r1.batch.json",
              [xp("r1", s, arm, R1[s][0 if arm == "01" else 1], f"r1-K3-u4000-s{s}-{ARMS[arm]}") for s in R1 for arm in ARMS]), "xp")
    probes = {15: "20261101T002041-87256", 16: "20261101T003945-89279", 17: "20261101T010311-99104"}
    for s, b in probes.items():
        rng = random.Random(20261102 + s)
        arms = ["00", "01p", "01s", "01"]
        rng.shuffle(arms)
        add(write(f"experiments/comp/comp-s{s}.batch.json",
                  [job(f"comp-K3-u4000-s{s}-{arm}", ["bc2rl.rl", "branch", "--config", COMPC, "--probe-run",
                                                     f"{b}/r1-probe-K3-u4000-s{s}", "--arm", arm]) for arm in arms]), "comp")
    add(write("experiments/program/final-tests.batch.json", [job("prog-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2)]), "prog")
    (ROOT / "experiments/program/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")


if __name__ == "__main__":
    main()
