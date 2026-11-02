"""Writes the conditional-confirmation batches after the frozen pilot gate (owner instruction 2026-11-02, section 8;
PROTOCOL_FREEZE Amendment 7 E). Deterministic. Refuses unless reports/p5/gate.json selects a method.

experiments/p5/conf-s<S>.batch.json  S = 96..115: BC (rho 0.2, 8000), probe (c5-v1), branches 00 and the selected arm;
                                     00 first for even S.
The batches are appended to experiments/p5/plan.json before the final tests (study "conf", required).
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments/p5"))
from make_batches import job, write, BC    # noqa: E402

CFG = "experiments/p5/c5-v1.json"


def main():
    g = json.loads((ROOT / "reports/p5/gate.json").read_text())
    arm = g["selected_arm"]
    assert arm in ("B5", "C5", "D5"), "the gate selected no method; no confirmation"
    plan = json.loads((ROOT / "experiments/p5/plan.json").read_text())["batches"]
    assert not any(p["study"] == "conf" for p in plan), "confirmation batches already planned"
    new = []
    for s in range(96, 116):
        arms = ["00", arm] if s % 2 == 0 else [arm, "00"]
        jobs = [job(f"c5-bc-s{s}", ["bc2rl.bc", "--config", BC, "--seed", str(s)]),
                job(f"c5-probe-K3-s{s}", ["bc2rl.rl", "probe", "--config", CFG, "--K", "3", "--bc-run", f"@/c5-bc-s{s}",
                                          "--bc-update", "8000", "--seed", str(s)])] + \
               [job(f"c5-K3-s{s}-{a}", ["bc2rl.rl", "branch", "--config", CFG, "--probe-run", f"@/c5-probe-K3-s{s}",
                                        "--arm", a]) for a in arms]
        new.append({"file": write(f"experiments/p5/conf-s{s}.batch.json", jobs), "study": "conf", "required": True})
    k = next(i for i, p in enumerate(plan) if p["study"] == "final")
    plan = plan[:k] + new + plan[k:]
    (ROOT / "experiments/p5/plan.json").write_text(json.dumps({"batches": plan}, indent=1) + "\n")
    print(json.dumps({"selected_arm": arm, "batches": len(new)}))


if __name__ == "__main__":
    main()
