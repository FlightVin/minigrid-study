"""Resume batches after a battery pause (owner instruction 2026-11-01c, section 9). Run ONLY after the owner's
explicit instruction to resume; it never launches anything itself.

Usage: .venv/bin/python tools/make_resume_a4.py SEED [SEED ...]   -> experiments/a4/resume-s<S>-<k>.batch.json + plan

For each incomplete job of the seed (tools/run_program4.job_complete):
  BC or probe incomplete -> rerun the job from its valid complete input under a new batch (same job id; the
      interrupted record is kept and counted). A rerun probe forks from the complete BC directory.
  branch incomplete     -> resume the lineage from its latest recoverable state with a matching hash (paused.json
      resume point, else the newest state_<n>.pt or recovery.pt in the chain) as job a4-K3-s<S>-<arm>-r<k>; if no
      recoverable state exists, rerun the branch from the probe fork as a4-K3-s<S>-<arm>-r<k>.
The resume batch is appended to experiments/a4/plan.json (required) so the driver admits it with the same rules.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "experiments/a4"))
import run_program4 as D    # noqa: E402
from make_batches import CFG, job, seed_jobs    # noqa: E402


def latest_state(chain):
    import torch
    sys.path.insert(0, str(ROOT / "src"))
    from bc2rl import ppo as PP
    best = None
    for d in chain:
        cands = list(d.glob("state_*.pt")) + ([d / "recovery.pt"] if (d / "recovery.pt").exists() else [])
        for f in cands:
            sv = torch.load(f, map_location="cpu", weights_only=False)
            if PP.state_hash(sv["state"]) != sv["hash"]:
                continue
            at = sv["meta"]["post_probe_actions"]
            if best is None or at > best[0]:
                best = (at, f)
    return best


def plan_for_seed(s):
    jobs, k = [], 1 + len(list((ROOT / "experiments/a4").glob(f"resume-s{s}-*.batch.json")))
    spec = {j["id"]: j for j in seed_jobs(s)}
    bc_done, pr_done = D.job_complete(f"a4-bc-s{s}"), D.job_complete(f"a4-probe-K3-s{s}")
    if not bc_done:
        jobs.append(spec[f"a4-bc-s{s}"])
    if not pr_done:
        pj = dict(spec[f"a4-probe-K3-s{s}"])
        if bc_done:
            bcdir = [d for d in D.job_dirs(f"a4-bc-s{s}") if (d / "summary.json").exists()][-1]
            pj["command"] = [x if x != f"@/a4-bc-s{s}" else f"{bcdir.parent.name}/{bcdir.name}" for x in pj["command"]]
        jobs.append(pj)
    for arm in ("00", "01s"):
        base = f"a4-K3-s{s}-{arm}"
        if D.branch_complete(base):
            continue
        chain = D.job_dirs(base) + [d for r in range(1, 10) for d in D.job_dirs(f"{base}-r{r}")]
        n = 1 + sum(1 for d in chain if re.search(r"-r\d+$", d.name))
        st = latest_state(chain) if pr_done else None
        if st is not None and st[0] < D.TARGET:
            rel = f"{st[1].parent.parent.name}/{st[1].parent.name}/{st[1].name}"
            jobs.append(job(f"{base}-r{n}", ["bc2rl.rl", "resume", "--config", CFG, "--state", rel]))
        else:
            pref = "@/a4-probe-K3-s{s}".format(s=s)
            if pr_done:
                pd = [d for d in D.job_dirs(f"a4-probe-K3-s{s}") if (d / "summary.json").exists()][-1]
                pref = f"{pd.parent.name}/{pd.name}"
            jobs.append(job(f"{base}-r{n}", ["bc2rl.rl", "branch", "--config", CFG, "--probe-run", pref, "--arm", arm]))
    return jobs, k


def main():
    plan_path = ROOT / "experiments/a4/plan.json"
    plan = json.loads(plan_path.read_text())
    for s in map(int, sys.argv[1:]):
        jobs, k = plan_for_seed(s)
        if not jobs:
            print(json.dumps({"seed": s, "note": "nothing to resume"}))
            continue
        path = f"experiments/a4/resume-s{s}-{k}.batch.json"
        (ROOT / path).write_text(json.dumps({"jobs": jobs}, indent=1) + "\n")
        plan["batches"].append({"file": path, "study": "a4", "required": True})
        print(json.dumps({"seed": s, "batch": path, "jobs": [j["id"] for j in jobs]}))
    plan_path.write_text(json.dumps(plan, indent=1) + "\n")


if __name__ == "__main__":
    main()
