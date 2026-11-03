"""Writes the actor capability audit batches and plan (owner instruction 2026-11-03; PROTOCOL_FREEZE Amendment 10).

experiments/p8/tests.batch.json      p8-tests (tests/test_p8.py, CPU)
experiments/p8/collect.batch.json    p8-collect (train, val, test states; CPU)
experiments/p8/validate.batch.json   p8-validate (zero-action checks, check_label sample, expert panel; CPU)
experiments/p8/tiny.batch.json       p8-tiny-lr3e-4, p8-tiny-lr1e-3 (MPS)
experiments/p8/fits.batch.json       15 fits (MPS): warm original at subset sizes 0, 1, 2 x seeds 0-2; scratch original
                                     and comparison (hidden 1024) at size 2 x seeds 0-2
experiments/p8/test.batch.json       p8-test (selected checkpoints on the final test states and recovery bank; MPS)
experiments/p8/rollout.batch.json    p8-rollout (final panel; CPU)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIT = "experiments/p8/fit-v1.json"


def job(i, cmd, device="cpu", mem=3, threads=1):
    return {"id": i, "cpu_threads": threads, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def write(path, jobs):
    (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
    return path


def fit_jobs():
    out = []
    for k in range(3):
        for s in range(3):
            out.append((f"p8-fit-warm128-n{k}-s{s}", ["--init", "warm", "--hidden", "128", "--size", str(k), "--seed", str(s)]))
    for s in range(3):
        out.append((f"p8-fit-scratch128-n2-s{s}", ["--init", "scratch", "--hidden", "128", "--size", "2", "--seed", str(s)]))
    for s in range(3):
        out.append((f"p8-fit-scratch1024-n2-s{s}", ["--init", "scratch", "--hidden", "1024", "--size", "2", "--seed", str(s)]))
    return out


def main():
    plan = []
    add = lambda p, kind: plan.append({"file": p, "kind": kind, "required": True})
    add(write("experiments/p8/tests.batch.json",
              [job("p8-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests/test_p8.py"])]), "actions")
    # p8-tests ran with every test skipped (data path not resolved from the runner's code snapshot); fixed, new ID
    add(write("experiments/p8/tests2.batch.json",
              [job("p8-tests-fix1", ["pytest", "-q", "-p", "no:cacheprovider", "tests/test_p8.py"])]), "actions")
    add(write("experiments/p8/collect.batch.json",
              [job("p8-collect", ["bc2rl.capability", "collect", "--config", "experiments/p8/collect-v1.json"], mem=4)]), "actions")
    add(write("experiments/p8/validate.batch.json",
              [job("p8-validate", ["bc2rl.capability", "validate", "--config", "experiments/p8/validate-v1.json"], mem=4)]), "actions")
    add(write("experiments/p8/tiny.batch.json",
              [job(f"p8-tiny-lr{lr}", ["bc2rl.capfit", "tiny", "--config", FIT, "--lr", lr], "mps") for lr in ("3e-4", "1e-3")]), "fit")
    add(write("experiments/p8/fits.batch.json",
              [job(i, ["bc2rl.capfit", "fit", "--config", FIT, *a], "mps", 4) for i, a in fit_jobs()]), "fit")
    add(write("experiments/p8/test.batch.json", [job("p8-test", ["bc2rl.capfit", "test", "--config", FIT], "mps", 4)]), "fit")
    add(write("experiments/p8/rollout.batch.json",
              [job("p8-rollout", ["bc2rl.capability", "rollout", "--config", "experiments/p8/rollout-v1.json"])]), "actions")
    (ROOT / "experiments/p8/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")


if __name__ == "__main__":
    main()
