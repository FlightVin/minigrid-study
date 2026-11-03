"""After the frozen development gate (owner instruction 2026-11-02c, sections 6-7; Amendment 9): writes the
confirmation batches only if reports/p7/gate.json selects an arm and the independent recomputation
(reports/p7/gate_verification.json) agrees. Also writes the reserve batches (verification replay, final tests).

C7 selected: experiments/p7/conf-s<S>.batch.json, S = 122..141: BC, probe, branches 00, C7, R7 (R7 matched to the
same seed's C7) with experiments/p7/c7-v1.json.
R7 selected: BC, probe, branches 00, R7. R7's per-update example counts come from the frozen development-derived
schedule experiments/p7/r7_schedule.json: n_t = round(mean over the 6 development seeds of C7's labelled examples in
update t), written here before any confirmation run.
No arm selected: writes nothing but the reserve batches.
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/p7"))
from make_batches import job, seed_jobs, write    # noqa: E402

CONF_SEEDS = list(range(122, 142))
CFG = "experiments/p7/c7-v1.json"


def main():
    gate = json.loads((ROOT / "reports/p7/gate.json").read_text())
    ver = json.loads((ROOT / "reports/p7/gate_verification.json").read_text())
    assert ver["agrees"] and ver["selected"] == gate["selected"], "independent gate recomputation disagrees"
    plan = json.loads((ROOT / "experiments/p7/plan.json").read_text())
    have = {p["file"] for p in plan["batches"]}
    add = lambda p, study, cat: plan["batches"].append({"file": p, "study": study, "category": cat, "required": True}) \
        if p not in have else None
    sel = gate["selected"]
    if sel == "C7":
        for s in CONF_SEEDS:
            add(write(f"experiments/p7/conf-s{s}.batch.json", seed_jobs(s, CFG, "c7")), "conf", "scientific")
    elif sel == "R7":
        import numpy as np
        rows = []
        for s in range(116, 122):
            d = sorted((ROOT / ".mae/runs").glob(f"*/p7-K3-s{s}-C7"))[-1]
            rows.append(json.loads((d / "aux_schedule.json").read_text())["labelled_per_update"])
        sched = [int(round(x)) for x in np.mean(np.array(rows, float), 0)]
        (ROOT / "experiments/p7/r7_schedule.json").write_text(json.dumps(
            {"complete": True, "rule": "round(mean over development seeds 116-121 of C7 labelled examples per update)",
             "labelled_per_update": sched}, indent=1) + "\n")
        for s in CONF_SEEDS:
            jobs = seed_jobs(s, CFG, "c7", ["00"])
            jobs.append(job(f"c7-K3-s{s}-R7", ["bc2rl.rl", "branch", "--config", CFG, "--probe-run",
                                               f"@/c7-probe-K3-s{s}", "--arm", "R7", "--match-run",
                                               "experiments/p7/r7_schedule.json"]))
            add(write(f"experiments/p7/conf-s{s}.batch.json", jobs), "conf", "scientific")
    add(write("experiments/p7/verify.batch.json",
              [job("p7-verify-replay", ["bc2rl.eval_replay", "--config", "experiments/p7/verify-v1.json"], "cpu", 2)]),
        "verify", "reserve")
    add(write("experiments/p7/final-tests.batch.json",
              [job("p7-final-tests", ["pytest", "-q", "-p", "no:cacheprovider", "tests"], "cpu", 2)]), "final", "reserve")
    (ROOT / "experiments/p7/plan.json").write_text(json.dumps(plan, indent=1) + "\n")
    print(json.dumps({"selected": sel, "batches": len(plan["batches"])}))


if __name__ == "__main__":
    main()
