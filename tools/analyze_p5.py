"""Reset-placement development pilot analysis and the frozen confirmation gate (owner instruction 2026-11-02,
sections 4-7; PROTOCOL_FREEZE Amendment 7 C-D). Written before any pilot outcome. No actions.

Usage: .venv/bin/python tools/analyze_p5.py [--engineering S]   -> reports/p5/{pilot_summary.json, pilot.md,
       pilot_branches.csv, gate.json}
  --engineering S: checks only for seed S (canary): lineage, identity, schedule, counters, row counts, step records;
                   prints no outcome and writes reports/p5/canary_check.json.

Seeds 90-95, arms A = 00, B = B5, C = C5, D = D5, all forked from one post-probe state per seed. Endpoints 251,904
and 501,760 (fixed final pilot endpoint). Per seed, arm and endpoint (p5_eval 64 K=3 layouts x 4, attempt-pooled =
item-weighted): P1, q, verified finishable access (certified feasible) with unresolved and impossible shares,
r = P(success | arrival), entry-bank competence (p5_bank 128 x 2), arrival timing (tau, remaining) and inventory,
per-module progress (share reaching each module, opening each door). Training (from the branch's final counters,
continuation only = final minus fork): normal and assisted episodes and successes by start type, assisted-step
fraction, steps by region (module 1-3, suffix) for normal and assisted episodes; interaction and compute costs.
Assisted-start results are never pooled with normal-start evaluation.
Paired contrasts m - A per seed (all six shown), mean and 95% t-interval (df 5), number positive. Development only;
no per-arm checkpoint selection.
Gate (Amendment 7 D): m in {B, C, D} qualifies iff at 501,760 mean(P1_m - P1_A) >= 0.05, P1_m - P1_A > 0 in >= 4/6
seeds, all execution/evaluation checks pass for m and A, and the complete confirmation (conservative) fits the
remaining budget. Select the qualifying method with the highest mean final P1; a qualifying method within 0.02 of it
that is simpler (order B, C, D) is preferred. Writes gate.json with the exact inputs and decision.
"""
import argparse
import csv
import json
from pathlib import Path
import re
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_r1 import t_two_sided_p    # noqa: E402

RUNS = ROOT / ".mae/runs"
OUT = ROOT / "reports/p5"
SEEDS = range(90, 96)
ARMS = {"A": "00", "B": "B5", "C": "C5", "D": "D5"}
SIMPLER = ["B", "C", "D"]
EPS = (251904, 501760)
TAG = {251904: "dev_251904", 501760: "dev_501760"}
TARGET = 501760
FROZEN_CFG = ROOT / "experiments/p5/p5-v1.json"


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def dirs(name):
    return sorted(d for d in RUNS.glob(f"*/{name}") if d.is_dir())


def t_crit(df):
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_two_sided_p(mid, df) > 0.05 else (lo, mid)
    return (lo + hi) / 2


def tsum(x):
    x = np.asarray(x, float)
    m = float(x.mean())
    sd = float(x.std(ddof=1)) if len(x) > 1 else float("nan")
    se = sd / np.sqrt(len(x))
    c = t_crit(len(x) - 1)
    p = float(t_two_sided_p(m / se, len(x) - 1)) if se > 0 else float("nan")
    return {"mean": m, "sd": sd, "lo": m - c * se, "hi": m + c * se, "p": p, "n": len(x),
            "n_positive": int((x > 0).sum()), "values": [float(v) for v in x]}


def lineage(base):
    """Branch job plus resume jobs -r1..; returns [(dir, start_actions, meta)] or None if not complete."""
    import torch
    allj = dirs(base) + [d for k in range(1, 10) for d in dirs(f"{base}-r{k}")]
    ends = [d for d in allj if (d / "summary.json").exists()
            and json.loads((d / "summary.json").read_text()).get("continuation_actions") == TARGET]
    if len(ends) != 1:
        return None
    out, d = [], ends[0]
    while d is not None:
        sm = (d / "summary.json")
        meta = json.loads(sm.read_text()) if sm.exists() else json.loads((d / "config.resolved.json").read_text())
        src = meta.get("resumed_from")
        if src:
            sv = torch.load(src, map_location="cpu", weights_only=False)
            out.append((d, sv["meta"]["post_probe_actions"], meta))
            d = Path(src).parent
        else:
            out.append((d, 0, meta))
            d = None
    return out[::-1]


def owner_of(chain, at):
    for k, (d, start, _) in enumerate(chain):
        end = chain[k + 1][1] if k + 1 < len(chain) else 10 ** 9
        if start < at <= end:
            return d
    return None


def measure(rows, bank_n):
    n = [r for r in rows if r["kind"] == "normal"]
    b = [r for r in rows if r["kind"] == "bank"]
    arr = [r for r in n if r["arrival"] is not None]
    st = lambda s: sum(1 for r in arr if r["arrival"]["cert"]["status"] == s)
    inv = {}
    for r in arr:
        c = r["arrival"]["carrying"]
        k = "none" if c is None else ":".join(c)
        inv[k] = inv.get(k, 0) + 1
    tr = [r["trace"] for r in n]
    return {"P1": sum(r["success"] for r in n) / len(n), "q": len(arr) / len(n),
            "q_feasible": st("feasible") / len(n), "q_unresolved": st("unresolved") / len(n),
            "q_impossible": st("impossible") / len(n),
            "r": sum(r["success"] for r in arr) / len(arr) if arr else None,
            "entry": sum(r["success"] for r in b) / len(b),
            "tau_mean": float(np.mean([r["arrival"]["tau"] for r in arr])) if arr else None,
            "remaining_mean": float(np.mean([r["arrival"]["remaining"] for r in arr])) if arr else None,
            "inventory": inv,
            "reach_module": [float(np.mean([t["mod_entry"][j] is not None for t in tr])) for j in range(3)],
            "open_door": [float(np.mean([t["door_open"][j] is not None for t in tr])) for j in range(3)],
            "counts": (len(n), len(b)), "bank_n": bank_n}


def training(chain, fork_counters):
    c = json.loads((chain[-1][0] / "summary.json").read_text())["counters"]
    d = {k: c.get(k, 0) - fork_counters.get(k, 0) for k in c}
    steps = {k[6:]: v for k, v in d.items() if k.startswith("steps_")}
    tot = sum(steps.values())
    ass = sum(v for k, v in steps.items() if k.startswith("assisted"))
    eps = {k: v for k, v in d.items() if re.match(r"(episodes|successes|accessed|end_doors\d)_", k)}
    return {"train_actions": d["env_actions"], "steps_by_type_region": steps, "assisted_step_fraction": ass / tot if tot else None,
            "episodes": eps, "normal_episodes": d.get("normal_episodes"), "normal_successes": d.get("normal_successes"),
            "assisted_episodes": d.get("assisted_episodes"), "assisted_successes": d.get("assisted_successes"),
            "updates": d.get("updates"), "actor_minibatches": d.get("actor_minibatches")}


def check_seed(s, frozen):
    """Execution and evaluation checks for one seed. Returns (problems, data)."""
    problems, data = [], {}
    pr = [d for d in dirs(f"p5-probe-K3-s{s}") if (d / "summary.json").exists() and (d / "fork.pt").exists()]
    bc = [d for d in dirs(f"p5-bc-s{s}") if (d / "summary.json").exists() and (d / "actor_u8000.pt").exists()]
    if len(pr) != 1 or len(bc) != 1:
        return [f"s{s}: {len(bc)} complete BC, {len(pr)} complete probes"], None
    psum = json.loads((pr[0] / "summary.json").read_text())
    import torch
    fork = torch.load(pr[0] / "fork.pt", map_location="cpu", weights_only=False)
    data["probe"] = {"pi0": psum["pi0"], "probe": psum["probe"], "dir": str(pr[0].relative_to(RUNS))}
    lim = [it["layout"]["limit"] for it in json.loads((ROOT / "data/r5-v1/layouts.json").read_text())["p5_eval"] if it["layout"]["K"] == 3]
    for lab, arm in ARMS.items():
        ch = lineage(f"p5-K3-s{s}-{arm}")
        if ch is None:
            problems.append(f"s{s} {lab}: branch not complete")
            continue
        for d, _, meta in ch:
            cf = json.loads((d / "config.resolved.json").read_text())
            want = (arm, psum["fork_hash"], "p5_eval", "p5_bank", 989000, "r5-v1", frozen["assist_schedule"].get(arm),
                    0.25 if arm != "00" else 0.0, [0.0, 0.0])
            got = (cf.get("arm"), cf.get("fork_hash"), cf["eval_role"], cf["bank_role"], cf["eval_seed"], cf["dataset_id"],
                   cf.get("assist_schedule", {}).get(arm) if arm != "00" else None, cf.get("alpha"),
                   list(cf.get("kl_effective_prefix_suffix", [0.0, 0.0])))
            if got != want:
                problems.append(f"s{s} {lab} identity {d.name}: {got} != {want}")
            if (d / "summary.json").exists():
                sm = json.loads((d / "summary.json").read_text())
                stp = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
                if stp != sum(sm["actions"].values()):
                    problems.append(f"s{s} {lab} {d.name}: step records {stp} != summary {sum(sm['actions'].values())}")
                if sm["counters"].get("assisted_episodes", 0) - fork["counters"].get("assisted_episodes", 0) and arm == "00":
                    problems.append(f"s{s} A has assisted episodes")
        data[lab] = {"chain": [str(d.relative_to(RUNS)) for d, _, _ in ch]}
        for at in EPS:
            d = owner_of(ch, at)
            rows = jl(d / f"attempts_{TAG[at]}.jsonl")
            m = measure(rows, 128)
            if m["counts"] != (256, 256):
                problems.append(f"s{s} {lab} {at}: rows {m['counts']}")
            li = {r["item"]: r["limit"] for r in rows if r["kind"] == "normal"}
            if [li[i] for i in range(64)] != lim:
                problems.append(f"s{s} {lab} {at}: panel")
            if any(r["kind"] == "normal" and "trace" not in r for r in rows):
                problems.append(f"s{s} {lab} {at}: missing trace")
            if any(r["kind"] == "normal" and r["arrival"] is not None and "cert" not in r["arrival"] for r in rows):
                problems.append(f"s{s} {lab} {at}: uncertified arrival")
            data[lab][at] = m
        data[lab]["training"] = training(ch, fork["counters"])
        if arm != "00":
            tr = data[lab]["training"]
            regions = {k.split("_", 1)[1] for k in tr["episodes"] if k.startswith("episodes_assisted_")}
            exp = {f"assisted_{b}" for ph in frozen["assist_schedule"][arm] for b, _ in ph["mixture"]}
            if not regions or not regions <= exp:
                problems.append(f"s{s} {lab}: assisted start types {sorted(regions)} not within {sorted(exp)}")
    return problems, data


def gate(contr, means, problems_by_arm, fits):
    res = {}
    for m in SIMPLER:
        c = contr[m][TARGET]
        res[m] = {"mean_diff": c["mean"], "n_positive": c["n_positive"], "checks_pass": not problems_by_arm[m] and not problems_by_arm["A"],
                  "fits_budget": fits["fits"], "mean_final_P1": means[m]}
        res[m]["qualifies"] = (c["mean"] >= 0.05 and c["n_positive"] >= 4 and res[m]["checks_pass"] and fits["fits"])
    q = [m for m in SIMPLER if res[m]["qualifies"]]
    sel = None
    if q:
        best = max(q, key=lambda m: means[m])
        near = [m for m in q if means[best] - means[m] <= 0.02]
        sel = min(near, key=SIMPLER.index)
    return {"methods": res, "qualifying": q, "selected": sel, "selected_arm": ARMS[sel] if sel else None,
            "rule": "Amendment 7 D: mean(P1_m - P1_A) >= 0.05 at 501,760; > 0 in >= 4/6; checks pass; confirmation fits; "
                    "highest mean final P1, simpler (B, C, D) within 0.02", "budget": fits}


def budget_fit():
    import run_program5 as R
    spent = R.ledger_total() - R.START_TOTAL
    need = spent + R.confirmation_reserve() + R.cost("p5-final-tests")[0] + R.AUDIT
    return {"spent": spent, "confirmation_conservative": R.confirmation_reserve(), "final_tests": R.cost("p5-final-tests")[0],
            "audit": R.AUDIT, "need": need, "budget": R.BUDGET, "fits": need <= R.BUDGET, "protection_left": R.BUDGET - need}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engineering", type=int)
    a = ap.parse_args()
    frozen = json.loads(FROZEN_CFG.read_text())
    if a.engineering is not None:
        probs, data = check_seed(a.engineering, frozen)
        out = {"seed": a.engineering, "problems": probs, "pass": not probs}
        if data:
            out["training_allocation"] = {lab: {k: data[lab]["training"][k] for k in ("train_actions", "assisted_step_fraction",
                                                                                     "steps_by_type_region", "episodes")}
                                          for lab in ARMS if lab in data}
            out["chains"] = {lab: data[lab]["chain"] for lab in ARMS if lab in data}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "canary_check.json").write_text(json.dumps(out, indent=1))
        print(json.dumps({"seed": a.engineering, "problems": probs, "pass": not probs}, indent=1))
        return
    allp, D = {}, {}
    for s in SEEDS:
        p, d = check_seed(s, frozen)
        allp[s], D[s] = p, d
    problems = [x for s in SEEDS for x in allp[s]]
    if any(D[s] is None for s in SEEDS):
        print(json.dumps({"problems": problems, "note": "pilot incomplete; no outcomes computed"}, indent=1))
        sys.exit(1)
    by_arm = {lab: [x for x in problems if f" {lab}" in x or f" {lab}:" in x] for lab in ARMS}
    contr, means, levels = {}, {}, {}
    metrics = ("P1", "q", "q_feasible", "q_unresolved", "q_impossible", "r", "entry", "tau_mean", "remaining_mean")
    for lab in ARMS:
        levels[lab] = {at: {m: tsum([D[s][lab][at][m] for s in SEEDS]) if all(D[s][lab][at][m] is not None for s in SEEDS) else None
                            for m in metrics} for at in EPS}
        means[lab] = levels[lab][TARGET]["P1"]["mean"]
    for m in SIMPLER:
        contr[m] = {at: tsum([D[s][m][at]["P1"] - D[s]["A"][at]["P1"] for s in SEEDS]) for at in EPS}
        contr[m]["secondary"] = {at: {k: tsum([D[s][m][at][k] - D[s]["A"][at][k] for s in SEEDS])
                                      for k in ("q", "q_feasible", "r", "entry") if all(D[s][x][at][k] is not None for s in SEEDS for x in (m, "A"))}
                                 for at in EPS}
    fits = budget_fit()
    g = gate(contr, means, by_arm, fits)
    alloc = {lab: {"assisted_step_fraction": tsum([D[s][lab]["training"]["assisted_step_fraction"] or 0.0 for s in SEEDS]),
                   "normal_success_rate_training": tsum([D[s][lab]["training"]["normal_successes"] / D[s][lab]["training"]["normal_episodes"] for s in SEEDS]),
                   "assisted_success_rate_training": (tsum([D[s][lab]["training"]["assisted_successes"] / D[s][lab]["training"]["assisted_episodes"] for s in SEEDS])
                                                      if lab != "A" else None)} for lab in ARMS}
    progress = {lab: {at: {"reach_module": np.mean([D[s][lab][at]["reach_module"] for s in SEEDS], 0).tolist(),
                           "open_door": np.mean([D[s][lab][at]["open_door"] for s in SEEDS], 0).tolist()} for at in EPS} for lab in ARMS}
    cohort = {s: D[s]["probe"] for s in SEEDS}
    res = {"seeds": list(SEEDS), "problems": problems, "levels": levels, "contrasts": contr, "allocation": alloc,
           "progress": progress, "cohort": cohort, "gate": g,
           "per_seed": {s: {lab: {at: {k: D[s][lab][at][k] for k in metrics + ("inventory", "reach_module", "open_door")} for at in EPS}
                            | {"training": D[s][lab]["training"], "chain": D[s][lab]["chain"]} for lab in ARMS} for s in SEEDS}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pilot_summary.json").write_text(json.dumps(res, indent=1, default=str))
    (OUT / "gate.json").write_text(json.dumps(g, indent=1))
    with (OUT / "pilot_branches.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seed", "arm", "endpoint", *metrics, "assisted_step_fraction"])
        for s in SEEDS:
            for lab in ARMS:
                for at in EPS:
                    w.writerow([s, lab, at, *[D[s][lab][at][k] for k in metrics], D[s][lab]["training"]["assisted_step_fraction"]])
    f3 = lambda v: "-" if v is None else f"{v:+.3f}"
    md = ["# Reset-placement pilot (seeds 90-95; development only)", "",
          "| arm | P1 @251,904 | P1 @501,760 | q @501,760 | finishable q | r | entry bank | assisted-step fraction |",
          "|---|---|---|---|---|---|---|---|"]
    for lab in ARMS:
        L = levels[lab]
        md.append(f"| {lab} ({ARMS[lab]}) | {L[251904]['P1']['mean']:.3f} | {L[TARGET]['P1']['mean']:.3f} | {L[TARGET]['q']['mean']:.3f} | "
                  f"{L[TARGET]['q_feasible']['mean']:.3f} | {L[TARGET]['r']['mean']:.3f} | {L[TARGET]['entry']['mean']:.3f} | "
                  f"{alloc[lab]['assisted_step_fraction']['mean']:.3f} |")
    md += ["", "Paired P1 contrasts m - A (per seed 90..95; mean [95% t, df 5]; positive):", ""]
    for m in SIMPLER:
        for at in EPS:
            c = contr[m][at]
            md.append(f"- {m} - A @{at}: {[round(v, 3) for v in c['values']]}; {c['mean']:+.3f} [{c['lo']:+.3f}, {c['hi']:+.3f}]; {c['n_positive']}/6")
    md += ["", f"Gate: qualifying {g['qualifying']}; selected **{g['selected']}**; budget {g['budget']}", f"Problems: {problems}"]
    (OUT / "pilot.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
