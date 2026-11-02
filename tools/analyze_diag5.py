"""Failure taxonomy, assisted references and the opportunity rule (owner instruction 2026-11-02, section 3;
PROTOCOL_FREEZE Amendment 7 B). Written before the diagnostics ran. No actions.

Usage: .venv/bin/python tools/analyze_diag5.py  -> reports/p5/diag/{diag_summary.json, diag.md, attempts.csv}

Inputs: the complete p5-diag-v1 job (8 policies: A4 seeds 70-73, arm 00, post-probe and 1,001,472) and the A4 raw
attempt files (arrival timing for all 20 seeds, both arms, three endpoints).
Per policy (d5_trace, 64 K=3 layouts x 2, attempt-weighted; every layout has 2 attempts, so item weighting is equal):
  P1, q (manuscript access), verified finishable access (arrival certified feasible), unresolved and impossible shares,
  r = P(success | arrival), r_feasible = P(success | feasible arrival), reference 1 (planner prefix, learned suffix),
  reference 2 (learned prefix, planner suffix: success iff the arrival is certified feasible; the planner replay is
  the executed suffix).
Failure taxonomy (exclusive): success; arrival then failure (by certification status); failure before the boundary
(by the module of the first still-locked door). Every failure in this task ends at the deadline (an episode ends only
on success or at the time limit), so "deadline failure" = every failure; the taxonomy says where the clock ran out.
Progress: share reaching each module and opening each door; median steps per module (door opened - module entered).
Errors: wrong-key pickups, toggles on locked doors without the key, door closes, no-op share, pose-repeat share and
maximum cell visits, for successful and failed attempts.
Opportunity rule (fixed): over the 4 final checkpoints, mean(1 - q) >= 0.25 and mean(reference 1 - P1) >= 0.05.
Correctness checks: an arrival with fewer than 3 open doors; "impossible" with a plan within the remaining time; any
feasible arrival whose replay failed (the job asserts this); any missing trace.
Failure accounting is not causal attribution: pre-boundary failures do not show that an access intervention would
recover them; reference 1 changes arrival state and timing and is not an upper bound.
"""
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
OUT = ROOT / "reports/p5/diag"
SEEDS = (70, 71, 72, 73)


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def q_(x, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    x = np.asarray([v for v in x if v is not None], float)
    return {f"p{int(q * 100)}": float(np.quantile(x, q)) for q in qs} | {"mean": float(x.mean()), "n": int(len(x))} if len(x) else {"n": 0}


def mean(x):
    x = [v for v in x if v is not None]
    return float(np.mean(x)) if x else None


def policy_stats(rows, ref1):
    n = len(rows)
    arr = [r for r in rows if r["arrival"] is not None]
    st = lambda s: [r for r in arr if r["arrival"]["cert"]["status"] == s]
    feas, unres, imp = st("feasible"), st("unresolved"), st("impossible")
    succ = [r for r in rows if r["success"]]
    out = {"attempts": n, "P1": len(succ) / n, "q": len(arr) / n, "q_feasible": len(feas) / n,
           "q_unresolved": len(unres) / n, "q_impossible": len(imp) / n,
           "r": len([r for r in arr if r["success"]]) / len(arr) if arr else None,
           "r_feasible": len([r for r in feas if r["success"]]) / len(feas) if feas else None,
           "ref1_P1": float(np.mean([r["success"] for r in ref1])), "ref2_P1": len(feas) / n,
           "ref2_planner_suffix_actions": q_([r["arrival"]["cert"]["replay_actions"] for r in feas])}
    tax = {"success": len(succ)}
    for s in ("feasible", "unresolved", "impossible"):
        tax[f"arrived_failed_{s}"] = len([r for r in st(s) if not r["success"]])
    for r in rows:
        if r["arrival"] is None:
            k = "before_boundary_" + r["trace"]["stage_end"].replace("prefix_", "")
            tax[k] = tax.get(k, 0) + 1
    out["taxonomy"] = tax
    out["taxonomy_share"] = {k: v / n for k, v in tax.items()}
    fails = n - len(succ)
    out["share_of_failures_before_boundary"] = (n - len(arr)) / fails if fails else None
    out["arrival_tau"] = q_([r["arrival"]["tau"] for r in arr])
    out["arrival_remaining"] = q_([r["arrival"]["remaining"] for r in arr])
    out["arrival_remaining_by_cert"] = {s: q_([r["arrival"]["remaining"] for r in st(s)]) for s in ("feasible", "unresolved", "impossible")}
    out["inventory_at_arrival"] = {}
    for r in arr:
        c = r["arrival"]["carrying"]
        k = "none" if c is None else ":".join(c)
        out["inventory_at_arrival"][k] = out["inventory_at_arrival"].get(k, 0) + 1
    tr = [r["trace"] for r in rows]
    K = len(tr[0]["mod_entry"])
    out["progress"] = {"reach_module": [mean([t["mod_entry"][j] is not None for t in tr]) for j in range(K)],
                       "open_door": [mean([t["door_open"][j] is not None for t in tr]) for j in range(K)],
                       "steps_in_module_median": [float(np.median([t["door_open"][j] - t["mod_entry"][j] for t in tr
                                                                   if t["door_open"][j] is not None and t["mod_entry"][j] is not None]))
                                                  if any(t["door_open"][j] is not None for t in tr) else None for j in range(K)]}
    out["errors"] = {}
    for lab, sel in (("success", [r["trace"] for r in rows if r["success"]]), ("failure", [r["trace"] for r in rows if not r["success"]])):
        if not sel:
            continue
        out["errors"][lab] = {"n": len(sel), "wrong_key_pickups_per_attempt": mean([t["wrong_key_pickups"] for t in sel]),
                              "share_with_wrong_key": mean([t["wrong_key_pickups"] > 0 for t in sel]),
                              "locked_toggles_per_attempt": mean([t["locked_toggles"] for t in sel]),
                              "door_closes_per_attempt": mean([t["door_closes"] for t in sel]),
                              "noop_actions_per_attempt": mean([t["noop_actions"] for t in sel]),
                              "pose_repeat_frac": mean([t["pose_repeat_frac"] for t in sel]),
                              "max_cell_visits_median": float(np.median([t["max_cell_visits"] for t in sel]))}
    noop_share = [r["trace"]["noop_actions"] / max(1, r["actions"]) for r in rows]
    out["errors"]["noop_share_of_actions"] = mean(noop_share)
    checks = {"arrival_with_locked_door": sum(1 for r in arr if r["trace"]["doors_open_end"] < 3),
              "impossible_but_plan_fits": sum(1 for r in imp if r["arrival"]["cert"]["plan_length"] is not None
                                              and r["arrival"]["cert"]["plan_length"] <= r["arrival"]["cert"]["remaining"]),
              "feasible_replay_failed": sum(1 for r in feas if not r["arrival"]["cert"]["replay_success"]),
              "missing_trace": sum(1 for r in rows + ref1 if "trace" not in r)}
    out["checks"] = checks
    return out


def a4_timing():
    """Arrival timing on a4_final for all 20 seeds, both arms, three endpoints (existing raw records)."""
    res = {}
    for arm in ("00", "01s"):
        for at in (251904, 501760, 1001472):
            tau, rem, dead, n = [], [], 0, 0
            for f in RUNS.glob(f"*/a4-K3-s*-{arm}/attempts_final_{at}.jsonl"):
                for r in jl(f):
                    if r["kind"] != "normal":
                        continue
                    n += 1
                    dead += bool(r.get("timeout"))
                    if r["arrival"] is not None:
                        tau.append(r["arrival"]["tau"])
                        rem.append(r["arrival"]["remaining"])
            res[f"{arm}@{at}"] = {"attempts": n, "deadline_failures": dead / n, "tau": q_(tau), "remaining": q_(rem)}
    return res


def main():
    jobs = [d for d in RUNS.glob("*/p5-diag-v1") if (d / "summary.json").exists()]
    assert len(jobs) == 1, f"need exactly one complete p5-diag-v1 job, found {len(jobs)}"
    d = jobs[0]
    sm = json.loads((d / "summary.json").read_text())
    pols = {}
    rows_csv = []
    for name in sm["config"]["policies"]:
        rows, ref1 = jl(d / f"attempts_{name}_normal.jsonl"), jl(d / f"attempts_{name}_ref1.jsonl")
        assert len(rows) == len(ref1) == 128
        pols[name] = policy_stats(rows, ref1)
        for r in rows:
            c = r["arrival"]["cert"] if r["arrival"] else None
            rows_csv.append({"policy": name, "item": r["item"], "attempt": r["attempt"], "success": r["success"],
                             "accessed": r["accessed"], "tau": r["tau"], "remaining_at_arrival": r["arrival"]["remaining"] if c else None,
                             "cert": c["status"] if c else None, "lower_bound": c["lower_bound"] if c else None,
                             "plan_length": c["plan_length"] if c else None, "stage_end": r["trace"]["stage_end"],
                             "doors_open_end": r["trace"]["doors_open_end"], "wrong_key": r["trace"]["wrong_key_pickups"],
                             "noop": r["trace"]["noop_actions"], "actions": r["actions"]})
    finals = [pols[f"s{s}_final"] for s in SEEDS]
    opp = {"mean_pre_boundary_failure": float(np.mean([1 - p["q"] for p in finals])),
           "mean_ref1_minus_P1": float(np.mean([p["ref1_P1"] - p["P1"] for p in finals])),
           "per_seed": {s: {"1-q": 1 - pols[f"s{s}_final"]["q"], "ref1-P1": pols[f"s{s}_final"]["ref1_P1"] - pols[f"s{s}_final"]["P1"]} for s in SEEDS}}
    opp["met"] = opp["mean_pre_boundary_failure"] >= 0.25 and opp["mean_ref1_minus_P1"] >= 0.05
    checks = {k: sum(p["checks"][k] for p in pols.values()) for k in finals[0]["checks"]}
    res = {"job": str(d.relative_to(RUNS)), "actions": sm["actions"], "policies": pols, "opportunity_rule": opp,
           "correctness_checks": checks, "a4_arrival_timing": a4_timing()}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diag_summary.json").write_text(json.dumps(res, indent=1))
    with (OUT / "attempts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_csv[0]))
        w.writeheader()
        w.writerows(rows_csv)
    md = ["# Failure diagnostics (d5_trace 64 K=3 layouts x 2; A4 arm 00 seeds 70-73)", "",
          "| policy | P1 | q | finishable q | unresolved | impossible | r | r given feasible | ref 1 | ref 2 | pre-boundary share of failures |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    fm = lambda v: "-" if v is None else f"{v:.3f}"
    for n, p in pols.items():
        md.append(f"| {n} | {fm(p['P1'])} | {fm(p['q'])} | {fm(p['q_feasible'])} | {fm(p['q_unresolved'])} | {fm(p['q_impossible'])} | "
                  f"{fm(p['r'])} | {fm(p['r_feasible'])} | {fm(p['ref1_P1'])} | {fm(p['ref2_P1'])} | {fm(p['share_of_failures_before_boundary'])} |")
    md += ["", "Taxonomy (shares of attempts):", ""]
    keys = sorted({k for p in pols.values() for k in p["taxonomy"]})
    md += ["| policy | " + " | ".join(keys) + " |", "|---" * (len(keys) + 1) + "|"]
    for n, p in pols.items():
        md.append(f"| {n} | " + " | ".join(fm(p["taxonomy_share"].get(k, 0)) for k in keys) + " |")
    md += ["", "Progress (reach module / open door; median steps in module):", ""]
    for n, p in pols.items():
        g = p["progress"]
        md.append(f"- {n}: reach {[round(x, 3) for x in g['reach_module']]}, open {[round(x, 3) for x in g['open_door']]}, "
                  f"steps {g['steps_in_module_median']}; arrival tau median {p['arrival_tau'].get('p50')}, remaining median "
                  f"{p['arrival_remaining'].get('p50')}; errors(fail) {p['errors'].get('failure')}")
    md += ["", f"Opportunity rule: mean(1 - q) = {opp['mean_pre_boundary_failure']:.3f} (>= 0.25), "
           f"mean(ref1 - P1) = {opp['mean_ref1_minus_P1']:+.3f} (>= 0.05): **{'met' if opp['met'] else 'not met'}**.",
           f"Correctness checks: {checks}", f"Actions: {sm['actions']}"]
    (OUT / "diag.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
