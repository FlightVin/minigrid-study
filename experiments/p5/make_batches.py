"""Writes the 2026-11-02 programme batch files and plan (owner instruction 2026-11-02; PROTOCOL_FREEZE Amendment 7).

experiments/p5/data.batch.json        r5-v1 generation (CPU)
experiments/p5/tests.batch.json       p5-tests (default suite) + p5-smoke (opt-in RL smoke tests, CPU)
experiments/p5/diag.batch.json        failure diagnostics and assisted references on frozen A4 checkpoints (diag-v1)
experiments/p5/pilot-s<S>.batch.json  S = 90..95: BC (rho 0.2, 8000), probe, branches 00, B5, C5, D5 in an order
                                      rotated by seed (S - 90) mod 4. Seed 90 is the engineering canary.
experiments/p5/final-tests.batch.json p5-final-tests
Confirmation batches (seeds 96-115) are written only after the frozen gate selects a method, by
tools/make_confirm_p5.py. plan.json lists the batches in execution order.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG, BC = "experiments/p5/p5-v1.json", "experiments/a4/bc-a4.json"
ARMS = ["00", "B5", "C5", "D5"]


def job(i, cmd, device="mps", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def write(path, jobs):
    (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
    return path


def seed_jobs(s, cfg=CFG, prefix="p5", arms=ARMS):
    k = (s - 90) % len(arms)
    order = arms[k:] + arms[:k]
    return [job(f"{prefix}-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)]),
            job(f"{prefix}-probe-K3-s{s}", ["bc2rl.rl", "probe", "--config", cfg, "--K", "3", "--bc-run",
                                           f"@/{prefix}-bc-s{s}", "--bc-update", "8000", "--seed", str(s)])] + \
           [job(f"{prefix}-K3-s{s}-{a}", ["bc2rl.rl", "branch", "--config", cfg, "--probe-run",
                                          f"@/{prefix}-probe-K3-s{s}", "--arm", a]) for a in order]


def main():
    plan = []
    add = lambda p, study: plan.append({"file": p, "study": study, "required": True})
    add(write("experiments/p5/data.batch.json", [job("p5-data-r5-v1", ["bc2rl.data", "--config", "experiments/p5/data-r5-v1.json"], "cpu", 2)]), "prep")
    smoke = {"id": "p5-smoke", "cpu_threads": 1, "memory_gb": 2, "device": "cpu",
             "command": ["env", "BC2RL_SMOKE=1", "{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                         "tests/test_rl_smoke.py", "tests/test_pause_smoke.py", "tests/test_p5_smoke.py"]}
    add(write("experiments/p5/tests.batch.json", [job("p5-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2), smoke]), "prep")
    add(write("experiments/p5/diag.batch.json", [job("p5-diag-v1", ["bc2rl.diag5", "--config", "experiments/p5/diag-v1.json"], "mps", 3)]), "diag")
    for s in range(90, 96):
        add(write(f"experiments/p5/pilot-s{s}.batch.json", seed_jobs(s)), "pilot")
    add(write("experiments/p5/final-tests.batch.json", [job("p5-final-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2)]), "final")
    (ROOT / "experiments/p5/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")


if __name__ == "__main__":
    main()
