"""Writes the A4 batch files and plan (owner instruction 2026-11-01c; PROTOCOL_FREEZE Amendment 6). Deterministic.

experiments/a4/data.batch.json      r4-v1 generation (CPU)
experiments/a4/arrival.batch.json   fixed actual-arrival bank (CPU)
experiments/a4/tests.batch.json     a4-tests (default suite) + a4-smoke (opt-in RL smoke tests: exact resume,
                                    checkpoint-and-pause, arrival capture; CPU)
experiments/a4/seed-s<S>.batch.json S = 70..89: BC (rho 0.2, 8000), probe, branches 00 and 01s. Seed 70 is the
                                    engineering canary. Branch order alternates: 00 first for even S, 01s first for odd S.
experiments/a4/final-tests.batch.json  p4-tests
experiments/a4/resume-*.batch.json  written only after a pause, by tools/make_resume_a4.py, on the owner's instruction.
plan.json: every batch in execution order; all required.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG, BC = "experiments/a4/a4-v1.json", "experiments/a4/bc-a4.json"


def job(i, cmd, device="mps", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def write(path, jobs):
    (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
    return path


def seed_jobs(s):
    arms = ["00", "01s"] if s % 2 == 0 else ["01s", "00"]
    return [job(f"a4-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)]),
            job(f"a4-probe-K3-s{s}", ["bc2rl.rl", "probe", "--config", CFG, "--K", "3", "--bc-run", f"@/a4-bc-s{s}",
                                      "--bc-update", "8000", "--seed", str(s)])] + \
           [job(f"a4-K3-s{s}-{a}", ["bc2rl.rl", "branch", "--config", CFG, "--probe-run", f"@/a4-probe-K3-s{s}", "--arm", a])
            for a in arms]


def main():
    plan = []
    add = lambda p: plan.append({"file": p, "study": "a4", "required": True})
    add(write("experiments/a4/data.batch.json", [job("a4-data-r4-v1", ["bc2rl.data", "--config", "experiments/a4/data-r4-v1.json"], "cpu", 2)]))
    add(write("experiments/a4/arrival.batch.json", [job("a4-arrival-v1", ["bc2rl.arrival_bank", "--config", "experiments/a4/arrival-v1.json"], "cpu", 2)]))
    smoke = {"id": "a4-smoke", "cpu_threads": 1, "memory_gb": 2, "device": "cpu",
             "command": ["env", "BC2RL_SMOKE=1", "{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                         "tests/test_rl_smoke.py", "tests/test_pause_smoke.py"]}
    add(write("experiments/a4/tests.batch.json", [job("a4-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2), smoke]))
    for s in range(70, 90):
        add(write(f"experiments/a4/seed-s{s}.batch.json", seed_jobs(s)))
    add(write("experiments/a4/final-tests.batch.json", [job("p4-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2)]))
    (ROOT / "experiments/a4/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")


if __name__ == "__main__":
    main()
