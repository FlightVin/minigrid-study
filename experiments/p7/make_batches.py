"""Writes the 2026-11-02c programme batch files and plan (owner instruction 2026-11-02c; PROTOCOL_FREEZE Amendment 9).

experiments/p7/data.batch.json         r7-v1 generation (CPU)
experiments/p7/recov.batch.json        held-out recovery-state bank (frozen A4 finals on r7_recov; CPU)
experiments/p7/tests.batch.json        p7-tests (default suite) + p7-smoke (opt-in smoke tests incl. test_p7_smoke, CPU)
experiments/p7/dev-s<S>.batch.json     S = 116..121: BC (rho 0.2, 8000), probe, branches 00, C7, R7 in this order
                                       (R7 reads C7's per-update example counts). Seed 116 is the engineering canary.
Confirmation batches (seeds 122-141) are written only after the frozen gate selects an arm, by
experiments/p7/make_confirm.py. Reserve batches (verification replay, final tests) are written by make_reserve.py.
plan.json lists the batches in execution order with their budget category.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG, BC = "experiments/p7/p7-v1.json", "experiments/a4/bc-a4.json"
DEV_SEEDS = list(range(116, 122))
ARMS = ["00", "C7", "R7"]


def job(i, cmd, device="mps", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def write(path, jobs):
    (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
    return path


def seed_jobs(s, cfg=CFG, prefix="p7", arms=ARMS):
    out = [job(f"{prefix}-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)]),
           job(f"{prefix}-probe-K3-s{s}", ["bc2rl.rl", "probe", "--config", cfg, "--K", "3", "--bc-run",
                                          f"@/{prefix}-bc-s{s}", "--bc-update", "8000", "--seed", str(s)])]
    for a in arms:
        extra = ["--match-run", f"@/{prefix}-K3-s{s}-C7"] if a == "R7" else []
        out.append(job(f"{prefix}-K3-s{s}-{a}", ["bc2rl.rl", "branch", "--config", cfg, "--probe-run",
                                                 f"@/{prefix}-probe-K3-s{s}", "--arm", a, *extra]))
    return out


def main():
    plan = []
    add = lambda p, study, cat="scientific": plan.append({"file": p, "study": study, "category": cat, "required": True})
    add(write("experiments/p7/data.batch.json",
              [job("p7-data-r7-v1", ["bc2rl.data", "--config", "experiments/p7/data-r7-v1.json"], "cpu", 2)]), "prep")
    add(write("experiments/p7/recov.batch.json",
              [job("p7-recov-v1", ["bc2rl.recovery_bank", "--config", "experiments/p7/recov-v1.json"], "cpu", 2)]), "prep")
    smoke = {"id": "p7-smoke", "cpu_threads": 1, "memory_gb": 2, "device": "cpu",
             "command": ["env", "BC2RL_SMOKE=1", "{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                         "tests/test_pause_smoke.py", "tests/test_p7_smoke.py"]}
    add(write("experiments/p7/tests.batch.json",
              [job("p7-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2), smoke]), "prep")
    for s in DEV_SEEDS:
        add(write(f"experiments/p7/dev-s{s}.batch.json", seed_jobs(s)), "dev")
    (ROOT / "experiments/p7/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")


if __name__ == "__main__":
    main()
