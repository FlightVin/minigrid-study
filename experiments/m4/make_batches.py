"""Writes the M4 batch files (PROTOCOL_FREEZE Amendments 1 and 2). Deterministic; run from the project root.

  data.batch.json         conf-v1 generation (CPU)
  seed-s<S>.batch.json    for S in 10..14: BC, 4 probes (shuffled), 16 branches (shuffled); seed 20261031 + S
"""
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONF = "experiments/m4/conf-v1.json"
ARMS = {"00": "00", "10": "10-a0p25", "01": "01-kl0p01", "11": "11-a0p25-kl0p01"}


def job(i, cmd, device="mps", mem=3):
    return {"id": i, "cpu_threads": 1, "memory_gb": mem, "device": device, "command": ["{python}", "-m", *cmd]}


def write(name, jobs):
    (HERE / name).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")


write("data.batch.json", [job("m4-data-conf-v1", ["bc2rl.data", "--config", "experiments/m4/data-conf-v1.json"], "cpu", 2)])
for s in range(10, 15):
    rng = random.Random(20261031 + s)
    forks = [(K, u) for K in (1, 3) for u in (4000, 16000)]
    rng.shuffle(forks)
    probes = [job(f"m4-probe-K{K}-u{u}-s{s}", ["bc2rl.rl", "probe", "--config", CONF, "--K", str(K), "--bc-run",
                  f"@/m4-bc-s{s}", "--bc-update", str(u), "--seed", str(s)]) for K, u in forks]
    branches = [job(f"m4-K{K}-u{u}-s{s}-{tag}", ["bc2rl.rl", "branch", "--config", CONF, "--probe-run",
                    f"@/m4-probe-K{K}-u{u}-s{s}", "--arm", arm]) for K, u in forks for arm, tag in ARMS.items()]
    rng.shuffle(branches)
    write(f"seed-s{s}.batch.json",
          [job(f"m4-bc-s{s}", ["bc2rl.bc", "--config", "experiments/m4/bc-v1.json", "--seed", str(s)])] + probes + branches)
