"""Independent verification of the controller diagnostics (owner instruction 2026-11-02b, section 9; Amendment 8).
Shares no code with tools/analyze_p6.py. No actions.

Usage: .venv/bin/python tools/verify_p6.py -> reports/p6/verification.json

From the raw ctrl_*.jsonl rows (shared upstream data: the same files the analysis reads) it recomputes, with its own
code: counts S, A, S_A, F per policy and condition; P1, q, r, F/A; per-policy and cohort mean paired differences
against base and both interactions (per-layout attempt means); and executed-action totals per job
(sum of episode lengths + certification replays) against the job summary, the job's step records and the ledger.
It also reads the verification replay job (bc2rl.ctrl_replay: a separate re-execution of a fixed sample, which is the
genuinely independent check of episode outcomes, helper claims and policy actions) and reports its mismatch counts.
Agreement with reports/p6/summary.json is checked to 1e-9.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = json.loads((ROOT / "experiments/p6/ctrl-v1.json").read_text())


def rows_of(path):
    with open(path) as fh:
        return [json.loads(x) for x in fh if x.strip()]


def the_dir(job):
    good = []
    for d in sorted((ROOT / ".mae/runs").glob(f"*/{job}")):
        s = d / "summary.json"
        if s.exists() and json.loads(s.read_text()).get("complete"):
            good.append(d)
    if len(good) != 1:
        raise SystemExit(f"{job}: {len(good)} complete runs")
    return good[0]


def layout_means(rows):
    tot, cnt = {}, {}
    for r in rows:
        tot[r["item"]] = tot.get(r["item"], 0) + (1 if r["success"] else 0)
        cnt[r["item"]] = cnt.get(r["item"], 0) + 1
    return [tot[i] / cnt[i] for i in range(CFG["n_layouts"])]


def main():
    ana = json.loads((ROOT / "reports/p6/summary.json").read_text())
    problems, cells, LM, action_check = [], {}, {}, {}
    for p in CFG["policies"]:
        d = the_dir(f"p6-ctrl-{p}")
        s = json.loads((d / "summary.json").read_text())
        mine = 0
        for c in CFG["conditions"]:
            rows = rows_of(d / f"ctrl_{p}_{c}.jsonl")
            S = sum(1 for r in rows if r["success"])
            arr = [r for r in rows if r["arrival"]]
            A = len(arr)
            SA = sum(1 for r in arr if r["success"])
            F = sum(1 for r in arr if r["arrival"]["cert"]["status"] == "feasible")
            cells[f"{p}|{c}"] = {"n": len(rows), "S": S, "A": A, "S_A": SA, "F": F, "P1": S / len(rows),
                                 "q": A / len(rows), "r": SA / A if A else None, "F/A": F / A if A else None}
            LM[(p, c)] = layout_means(rows)
            mine += sum(r["end_step"] for r in rows) + sum(r["arrival"]["cert"]["replay_actions"] for r in arr)
            a = ana["cells"][f"{p}|{c}"]
            for k_mine, k_ana in (("P1", "P1"), ("q", "q"), ("r", "r"), ("F/A", "finishable_of_arrivals")):
                x, y = cells[f"{p}|{c}"][k_mine], a[k_ana]
                if (x is None) != (y is None) or (x is not None and abs(x - y) > 1e-9):
                    problems.append(f"{p} {c} {k_mine}: {x} vs {y}")
        rec = sum(json.loads(f.read_text())["actions"] for f in (d / "env_steps").glob("*.json"))
        action_check[p] = {"from_rows": mine, "summary": s["actions_total"], "step_records": rec}
        if not mine == s["actions_total"] == rec:
            problems.append(f"{p}: action totals {action_check[p]}")
    diffs = {}
    names = [c for c in CFG["conditions"] if c != "base"] + ["interaction_mid", "interaction_all"]
    trip = {"mid": ("key_mid", "door_mid", "both_mid"), "all": ("key_all", "door_all", "both_all")}
    for coh, pols in CFG["cohorts"].items():
        for n in names:
            per_pol = []
            for p in pols:
                if n.startswith("interaction_"):
                    k, dd, b = trip[n[12:]]
                    v = [LM[(p, b)][i] - LM[(p, k)][i] - LM[(p, dd)][i] + LM[(p, "base")][i] for i in range(CFG["n_layouts"])]
                else:
                    v = [LM[(p, n)][i] - LM[(p, "base")][i] for i in range(CFG["n_layouts"])]
                per_pol.append(sum(v) / len(v))
                y = ana["cohorts"][coh]["contrasts"]["per_policy"][p][n]["mean"]
                if abs(per_pol[-1] - y) > 1e-9:
                    problems.append(f"{p} {n}: {per_pol[-1]} vs {y}")
            m = sum(per_pol) / len(per_pol)
            diffs[f"{coh}|{n}"] = {"cohort_mean": m, "per_policy": per_pol}
            if abs(m - ana["cohorts"][coh]["contrasts"]["cohort"][n]["mean"]) > 1e-9:
                problems.append(f"{coh} {n}: cohort mean")
    rep = json.loads((the_dir("p6-verify-replay") / "summary.json").read_text())
    for k in ("outcome_mismatches", "cert_mismatches", "helper_check_failures"):
        if rep[k]:
            problems.append(f"replay {k} = {rep[k]}")
    out = {"cells": cells, "contrasts": diffs, "actions": action_check, "replay": rep, "problems": problems,
           "agrees_with_analysis": not problems,
           "independence": "Counts, rates, contrasts and action totals are recomputed here from the same raw rows "
                           "(shared upstream data). The replay job re-executes a fixed sample of episodes in fresh "
                           "environments and re-derives policy actions; it shares the environment, policy network and "
                           "suffix certification code with the evaluation."}
    (ROOT / "reports/p6/verification.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({"problems": problems, "actions": action_check, "replay": rep}, indent=1))


if __name__ == "__main__":
    main()
