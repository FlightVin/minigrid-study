"""Campaign ledger: executed environment actions by role across every run, plus batch wall time.

Usage: .venv/bin/python tools/ledger.py [--csv reports/campaign_ledger.csv]

Sources per job directory under .mae/runs/<batch>/<job>/:
  probe/branch summaries -> actions by role (critic_warmup, train, eval_diagnostic, eval_final);
  BC metrics             -> eval_env_actions per checkpoint (BC updates are counted separately);
  benchmark summaries    -> cycles x 512 rollout actions;
  data generation        -> planner replay actions (verify replay for every planned layout, plus a
                            recording replay for trajectory roles), from layouts.json;
  failed/partial jobs    -> actions recorded in attempts_*.jsonl and metrics.jsonl when no summary;
  any other job          -> env_steps/*.json step records (src/bc2rl/accounting.py), e.g. tests run as jobs.
Running batches are included up to their last written record.
Actions executed outside the runner (software tests, interactive checks) are added from
research/ledger_adjustments.json as their own roles; the conservative value is used.
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def job_actions(d):
    """Actions by role for one job. A job without a summary (failed or partial) never counts fewer actions than its
    managed step records: the excess over the metrics-derived count is added as "partial_unrecorded" (R1 audit
    2026-11-01: the failed r1-bc-s17 ran 128 evaluation actions after its last metrics row)."""
    acts, kind = _job_actions(d)
    if kind in ("bc", "rl_partial", "benchmark_partial") and not (d / "summary.json").exists():
        steps = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
        extra = steps - sum(acts.values())
        if extra > 0:
            acts = {**acts, "partial_unrecorded": extra}
    return acts, kind


def _job_actions(d):
    out = {}
    s = d / "summary.json"
    s = json.loads(s.read_text()) if s.exists() else None
    if s and isinstance(s.get("actions"), dict):
        return dict(s["actions"]), s.get("mode", "rl")
    if s and "cycles" in s and "steps_per_s_mean" in s:
        return {"benchmark": s["cycles"] * 512}, "benchmark"
    m = d / "metrics.jsonl"
    if m.exists():
        recs = [json.loads(l) for l in m.read_text().splitlines() if l.strip()]
        if recs and "eval_env_actions" in recs[0]:
            return {"bc_eval": sum(r["eval_env_actions"] for r in recs)}, "bc"
        if recs and "phase" in recs[0]:     # partial or failed RL job
            train = max([r["actions"] for r in recs if r.get("phase") in ("probe", "branch")] or [0])
            ev = sum(r.get("eval_actions", 0) for r in recs if r.get("phase") == "eval")
            return {"train": train, "eval_diagnostic": ev}, "rl_partial"
        if recs and "cycle" in recs[0]:
            return {"benchmark": len(recs) * 512}, "benchmark_partial"
    man = d / "manifest.json"
    if man.exists():
        mf = json.loads(man.read_text())
        ds = ROOT / "data" / mf["dataset_id"] / "layouts.json"
        if ds.exists():
            lay = json.loads(ds.read_text())
            n = 0
            planned = mf["config"].get("generate_roles") if mf["config"].get("base_dataset") else lay
            for role, items in lay.items():
                if role not in planned:         # copied unchanged from a base dataset; no replay
                    continue
                k = 2 if role in mf["config"]["trajectory_roles"] else 1
                n += k * sum(it["length"] for it in items)
            return {"planner_replay": n}, "data"
    steps = sorted((d / "env_steps").glob("*.json"))
    if steps:
        return {"runner_tests": sum(json.loads(p.read_text())["actions"] for p in steps)}, "steps"
    return out, "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows, totals = [], {}
    for b in sorted((ROOT / ".mae/runs").iterdir()):
        ex = b / "execution.json"
        status = json.loads(ex.read_text())["status"] if ex.exists() else "running"
        for d in sorted(p for p in b.iterdir() if p.is_dir() and p.name != "code"):
            acts, kind = job_actions(d)
            for k, v in acts.items():
                totals[k] = totals.get(k, 0) + v
            rows.append({"batch": b.name, "job": d.name, "batch_status": status, "kind": kind,
                         **{k: acts.get(k, 0) for k in ("planner_replay", "benchmark", "bc_eval", "critic_warmup",
                                                         "train", "eval_diagnostic", "eval_final")}})
    measured = sum(totals.values())
    # measured outside the runner (src/bc2rl/accounting.py, from 2026-10-31 post-M4)
    un = sorted((ROOT / ".mae/unmanaged_actions").glob("*.json")) if (ROOT / ".mae/unmanaged_actions").exists() else []
    unmanaged = sum(json.loads(p.read_text())["actions"] for p in un)
    estimated = {}
    adj = ROOT / "research/ledger_adjustments.json"
    if adj.exists():
        for e in json.loads(adj.read_text())["entries"]:
            estimated[e["role"]] = estimated.get(e["role"], 0) + e["actions"]
            totals[e["role"]] = totals.get(e["role"], 0) + e["actions"]
    if unmanaged:
        totals["outside_runner_measured"] = unmanaged
    wall = sum(json.loads(l)["wall_seconds"] for l in (ROOT / ".mae/ledger.jsonl").read_text().splitlines())
    total = sum(totals.values())
    print(json.dumps({"total_env_actions": total, "runner_measured": measured,
                      "outside_runner_measured": unmanaged, "outside_runner_estimated": sum(estimated.values()),
                      "by_role": totals, "finished_batch_wall_hours": round(wall / 3600, 2),
                      "note": "runner_measured includes data planner replay derived from layouts.json; estimated roles are "
                              "conservative upper estimates (research/ledger_adjustments.json). R1 (Amendment 3): hard incremental "
                              "budget 28.4M from 93,199,203 (tools/run_r1.py); the 109M M4 stop line does not apply to R1."}, indent=1))
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
