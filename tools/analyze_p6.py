"""Frozen analysis of the controller diagnostics (owner instruction 2026-11-02b, section 6; PROTOCOL_FREEZE Amendment 8).
Written and committed before any d6_ctrl outcome. No actions.

Usage: .venv/bin/python tools/analyze_p6.py [--canary]
  --canary  engineering checks of the canary run only (d5_trace; no d6_ctrl outcomes).

Inputs: ctrl_<policy>_<condition>.jsonl of the p6-ctrl-<policy> jobs (exactly one completed job each).
Per policy and condition (n = 64 layouts x 2 attempts = 128 episodes; pooled counts, denominators explicit):
  P1 = S/n; q = A/n (first boundary crossings); r = S_A/A (learned completion given actual arrival; the suffix is
  always the learned policy); F/A certified-finishable share of arrivals (planner, original clock); S_F/F;
  assistance: per type and module, counts of not eligible / assisted (ok) / unresolved / certified impossible /
  not needed; exposure = share of episodes with >= 1 executed helper action; helper-action fraction = helper steps /
  all steps; arrival time and remaining time quantiles; learner locked-door toggles, learner ineffective actions
  (prefix), mean policy mass on ineffective actions in the prefix, learner key pickups and nominally wrong pickups
  (a key other than the first still-locked door's), mask removed mass (mask_prefix).
Paired contrasts (per policy): per-layout difference of attempt-means, condition minus base; mean over 64 layouts with
95% t interval (df 63) and a percentile bootstrap over layouts (10,000; rng 20261103). Interactions per scope:
both - key - door + base, per layout, same intervals. Cohort (A4: s70-73; P5: s90-93; never pooled across cohorts):
mean over the 4 policies of the per-layout differences; t interval over layouts (conditional on the 4 fixed
policies); sensitivity: crossed bootstrap resampling policies (within cohort) and layouts. Multiplicity: 7 contrasts
against base and 2 interactions per cohort are exploratory; Bonferroni 95% intervals (alpha 0.05/9) are reported as
a simultaneous sensitivity. No contrast is confirmatory.
Mechanism summaries (descriptive): module durations (entry of module j to entry of j+1 or episode end) among episodes
that entered module j; share of episodes that end in each module; for KA-assisted episodes, the share whose module
key is later dropped; for DA, backtracks; for paired base-failure episodes, the share rescued per condition.
Trajectory sample (predetermined): per cohort, the first 2 episodes (policy order, item, attempt) in each category
  a base failure before the boundary -> both_all success      b base failure before the boundary -> both_all failure
  c base failure before the boundary -> key_mid success        d base failure before the boundary -> mask_prefix success
  e base success -> failure under any modified condition (counterexample)
  f base failure after a certified-finishable arrival
rendered as event timelines in reports/p6/trajectories.md.
Outputs: reports/p6/summary.json, reports/p6/table.md, reports/p6/cells.csv, reports/p6/trajectories.md
(--canary: reports/p6/canary_check.json).
"""
import argparse
import csv
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from audit_r1 import t_two_sided_p    # noqa: E402

CFG = json.loads((ROOT / "experiments/p6/ctrl-v1.json").read_text())
CONDS = CFG["conditions"]
SCOPES = {"mid": ("key_mid", "door_mid", "both_mid"), "all": ("key_all", "door_all", "both_all")}
OUT = ROOT / "reports/p6"
NB = 10_000


def t_crit(df, alpha=0.05):
    lo, hi = 0.0, 60.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_two_sided_p(mid, df) > alpha else (lo, mid)
    return (lo + hi) / 2


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def job_dir(name):
    ds = [d for d in sorted((ROOT / ".mae/runs").glob(f"*/{name}")) if (d / "summary.json").exists()
          and json.loads((d / "summary.json").read_text()).get("complete")]
    assert len(ds) == 1, (name, ds)
    return ds[0]


def q_(x, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    return {str(q): float(np.quantile(x, q)) for q in qs} if len(x) else None


def ratio(a, b):
    return None if b == 0 else a / b


def cell_stats(rows):
    n = len(rows)
    arr = [r for r in rows if r["arrival"] is not None]
    st = lambda s: [r for r in arr if r["arrival"]["cert"]["status"] == s]
    F = st("feasible")
    c = {"n": n, "S": sum(r["success"] for r in rows), "A": len(arr), "S_A": sum(r["success"] for r in arr),
         "F": len(F), "U": len(st("unresolved")), "I": len(st("impossible")), "S_F": sum(r["success"] for r in F)}
    steps = sum(r["end_step"] for r in rows)
    helper = sum(r["counts"]["helper_steps"] for r in rows)
    assist = {}
    for kind in ("ka", "da"):
        for j in range(3):
            xs = [x for r in rows for x in r["assists"] if x["type"] == kind and x["m"] == j]
            assist[f"{kind}{j}"] = {s: sum(x["status"] == s for x in xs) for s in
                                    ("assisted", "unresolved", "certified_impossible", "not_needed")}
            assist[f"{kind}{j}"]["ok"] = sum(x.get("ok") is True for x in xs)
            assist[f"{kind}{j}"]["evaluated"] = len(xs)
            assist[f"{kind}{j}"]["helper_actions"] = sum(x.get("n_exec", 0) for x in xs)
    cnt = lambda k: float(np.mean([r["counts"][k] for r in rows]))
    pre_steps = [r["tau"] if r["tau"] is not None else r["end_step"] for r in rows]
    lps = sum(p - sum(1 for w in r["who"][:p] if w != "p") for r, p in zip(rows, pre_steps))   # learner prefix steps
    out = {"counts": c, "P1": c["S"] / n, "q": c["A"] / n, "r": ratio(c["S_A"], c["A"]),
           "finishable_of_arrivals": ratio(c["F"], c["A"]), "finishable_of_attempts": c["F"] / n,
           "impossible_of_arrivals": ratio(c["I"], c["A"]), "unresolved_of_arrivals": ratio(c["U"], c["A"]),
           "completion_given_finishable": ratio(c["S_F"], c["F"]),
           "exposure": float(np.mean([r["counts"]["helper_steps"] > 0 for r in rows])),
           "helper_action_fraction": helper / steps, "steps": steps, "helper_steps": helper, "assist": assist,
           "arrival_tau": q_([r["arrival"]["tau"] for r in arr]),
           "arrival_remaining": q_([r["arrival"]["remaining"] for r in arr]),
           "helper_cross_share_of_arrivals": ratio(sum(r["arrival"]["helper_cross"] for r in arr), len(arr)),
           "learner_locked_toggles_per_ep": cnt("learner_locked_toggles"),
           "learner_ineffective_prefix_per_ep": cnt("learner_ineffective_prefix"),
           "learner_prefix_steps": lps,
           "ineffective_mass_prefix_mean": ratio(sum(r["counts"]["ineffective_mass_prefix"] for r in rows), lps),
           "ineffective_prefix_share_of_learner_prefix_steps": ratio(
               sum(r["counts"]["learner_ineffective_prefix"] for r in rows), lps),
           "learner_key_pickups_per_ep": cnt("learner_key_pickups"),
           "learner_wrong_key_pickups_per_ep": cnt("learner_wrong_key_pickups"),
           "key_lost_after_ka_eps": sum(r["counts"]["key_lost_after_ka"] > 0 for r in rows),
           "backtrack_after_da_eps": sum(r["counts"]["backtrack_after_da"] > 0 for r in rows),
           "mask_removed_mean_per_masked_step": ratio(sum(r["counts"]["mask_removed_sum"] for r in rows),
                                                      sum(r["counts"]["mask_steps"] for r in rows)),
           "mask_changed_action_share": ratio(sum(r["counts"]["mask_changed_action"] for r in rows),
                                              sum(r["counts"]["mask_steps"] for r in rows)),
           "pose_repeat_frac_mean": float(np.mean([r["trace"]["pose_repeat_frac"] for r in rows])),
           "end_stage": {k: sum(r["trace"]["stage_end"] == k for r in rows) for k in
                         ("prefix_m0", "prefix_m1", "prefix_m2", "suffix_no_target", "carrying")},
           "success": None}
    dur = {}
    for j in range(3):
        d = []
        for r in rows:
            e = r["mod_entry"]
            if e[j] is None:
                continue
            nxt = e[j + 1] if j + 1 < 3 else r["tau"]
            d.append((nxt if nxt is not None else r["end_step"]) - e[j])
        dur[f"m{j}"] = {"entered": len(d), "median": float(np.median(d)) if d else None,
                        "mean": float(np.mean(d)) if d else None}
    out["module_duration"] = dur
    out.pop("success")
    return out


def per_layout(rows, n_layouts):
    s = np.zeros(n_layouts)
    k = np.zeros(n_layouts)
    for r in rows:
        s[r["item"]] += r["success"]
        k[r["item"]] += 1
    assert (k == CFG["attempts"]).all()
    return s / k


def interval(d, rng, alpha=0.05):
    n = len(d)
    m, sd = float(d.mean()), float(d.std(ddof=1))
    se = sd / sqrt(n)
    c = t_crit(n - 1, alpha)
    boots = d[rng.integers(0, n, (NB, n))].mean(1)
    return {"mean": m, "sd_layouts": sd, "lo": m - c * se, "hi": m + c * se,
            "p": float(t_two_sided_p(m / se, n - 1)) if se > 0 else None,
            "boot_lo": float(np.quantile(boots, alpha / 2)), "boot_hi": float(np.quantile(boots, 1 - alpha / 2))}


def contrasts(PL, pols, rng):
    """PL[(policy, cond)] = per-layout success means. Returns per-policy and cohort contrasts and interactions."""
    names = [c for c in CONDS if c != "base"] + [f"interaction_{s}" for s in SCOPES]

    def diff(p, name):
        if name.startswith("interaction_"):
            k, d, b = SCOPES[name.split("_")[1]]
            return PL[(p, b)] - PL[(p, k)] - PL[(p, d)] + PL[(p, "base")]
        return PL[(p, name)] - PL[(p, "base")]

    out = {"per_policy": {p: {n: interval(diff(p, n), rng) for n in names} for p in pols}, "cohort": {}}
    alpha_b = 0.05 / len(names)
    for n in names:
        D = np.stack([diff(p, n) for p in pols])          # policies x layouts
        res = interval(D.mean(0), rng)
        res["bonferroni"] = {k: v for k, v in interval(D.mean(0), rng, alpha_b).items() if k in ("lo", "hi")}
        P, L = D.shape
        bi = rng.integers(0, P, (NB, P))
        bj = rng.integers(0, L, (NB, L))
        crossed = np.array([D[bi[b]][:, bj[b]].mean() for b in range(NB)])
        res["crossed_lo"], res["crossed_hi"] = float(np.quantile(crossed, 0.025)), float(np.quantile(crossed, 0.975))
        res["per_policy_means"] = [float(x) for x in D.mean(1)]
        res["n_policies_positive"] = int((D.mean(1) > 0).sum())
        out["cohort"][n] = res
    return out


def rescue(R, pols):
    """Among base failures (per episode), the share that succeed under each condition; split by base failure stage."""
    out = {}
    for c in CONDS[1:]:
        tot = {"pre": [0, 0], "post": [0, 0]}
        for p in pols:
            base = {(r["item"], r["attempt"]): r for r in R[(p, "base")]}
            for r in R[(p, c)]:
                b = base[(r["item"], r["attempt"])]
                if b["success"]:
                    continue
                k = "pre" if b["arrival"] is None else "post"
                tot[k][0] += 1
                tot[k][1] += r["success"]
        out[c] = {k: {"base_failures": v[0], "rescued": v[1], "share": ratio(v[1], v[0])} for k, v in tot.items()}
    harmed = {}
    for c in CONDS[1:]:
        n = h = 0
        for p in pols:
            base = {(r["item"], r["attempt"]): r for r in R[(p, "base")]}
            for r in R[(p, c)]:
                if base[(r["item"], r["attempt"])]["success"]:
                    n += 1
                    h += not r["success"]
        harmed[c] = {"base_successes": n, "lost": h, "share": ratio(h, n)}
    return {"rescued": out, "lost": harmed}


def timeline(r):
    t = r["trace"]
    ev = [f"limit {r['limit']}", f"module entries {r['mod_entry']}", f"doors unlocked at {t['door_open']}",
          f"key pickups {t['key_pickups']}"]
    for x in r["assists"]:
        ev.append(f"{x['type'].upper()} m{x['m']} at {x['step']} (remaining {x.get('remaining')}): {x['status']}"
                  + (f", {x.get('n_exec')} helper actions, ok {x.get('ok')}" if x["status"] == "assisted" else "")
                  + (f", plan {x.get('plan_len')}, bound {x.get('lb')}, {x.get('reason')}" if x["status"] != "assisted" and "lb" in x else ""))
    a = r["arrival"]
    ev.append("no arrival" if a is None else f"arrival at {a['tau']} (remaining {a['remaining']}, carrying "
              f"{a['carrying']}, cert {a['cert']['status']}{', by helper' if a['helper_cross'] else ''})")
    c = r["counts"]
    ev.append(f"end {r['end_step']} {'success' if r['success'] else 'failure'}; stage_end {t['stage_end']}; learner "
              f"locked toggles {c['learner_locked_toggles']}, ineffective prefix {c['learner_ineffective_prefix']}, "
              f"wrong-key pickups {c['learner_wrong_key_pickups']}, pose repeat {t['pose_repeat_frac']:.2f}")
    seg = [(w, ch) for w, ch in zip(r["who"], r["actions"])]
    hist = {}
    for w, ch in seg:
        if w == "p":
            hist[ch] = hist.get(ch, 0) + 1
    ev.append("learner action counts " + ", ".join(f"{'LRFPDTN'[int(k)]}:{v}" for k, v in sorted(hist.items())))
    return ev


def trajectories(R, cohorts):
    md = ["# Predetermined trajectory sample (rule in tools/analyze_p6.py)", ""]
    cats = {
        "a": ("base failure before the boundary -> both_all success", "both_all", lambda b, x: b["arrival"] is None and not b["success"] and x["success"]),
        "b": ("base failure before the boundary -> both_all failure", "both_all", lambda b, x: b["arrival"] is None and not x["success"]),
        "c": ("base failure before the boundary -> key_mid success", "key_mid", lambda b, x: b["arrival"] is None and x["success"]),
        "d": ("base failure before the boundary -> mask_prefix success", "mask_prefix", lambda b, x: b["arrival"] is None and x["success"]),
        "e": ("base success -> failure under a modified condition (counterexample)", None, None),
        "f": ("base failure after a certified-finishable arrival", None, None),
    }
    for coh, pols in cohorts.items():
        md.append(f"## Cohort {coh}")
        for key, (title, cond, pred) in cats.items():
            md += ["", f"### {key}. {title}"]
            found = 0
            for p in pols:
                base = sorted(R[(p, "base")], key=lambda r: (r["item"], r["attempt"]))
                for b in base:
                    if found >= 2:
                        break
                    if key == "e":
                        if not b["success"]:
                            continue
                        alt = next((x for c in CONDS[1:] for x in R[(p, c)] if (x["item"], x["attempt"]) ==
                                    (b["item"], b["attempt"]) and not x["success"]), None)
                        if alt is None:
                            continue
                        pair = [("base", b), (alt["condition"], alt)]
                    elif key == "f":
                        if b["success"] or b["arrival"] is None or b["arrival"]["cert"]["status"] != "feasible":
                            continue
                        pair = [("base", b)]
                    else:
                        x = next(x for x in R[(p, cond)] if (x["item"], x["attempt"]) == (b["item"], b["attempt"]))
                        if b["success"] or not pred(b, x):
                            continue
                        pair = [("base", b), (cond, x)]
                    found += 1
                    md.append(f"- **{p} item {b['item']} attempt {b['attempt']}**")
                    for c, r in pair:
                        md.append(f"  - {c}: " + "; ".join(timeline(r)))
            if found == 0:
                md.append("- none in this cohort")
    (OUT / "trajectories.md").write_text("\n".join(md) + "\n")


def canary():
    d = job_dir("p6-canary")
    cfg = json.loads((ROOT / "experiments/p6/canary-v1.json").read_text())
    s = json.loads((d / "summary.json").read_text())
    probs = []
    steps_rec = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
    if steps_rec != s["actions_total"]:
        probs.append(f"step records {steps_rec} != summary {s['actions_total']}")
    for c in cfg["conditions"]:
        rows = jl(d / f"ctrl_a4_s70_{c}.jsonl")
        if len(rows) != cfg["n_layouts"] * cfg["attempts"]:
            probs.append(f"{c}: rows")
        for r in rows:
            if len(r["actions"]) != r["end_step"] or len(r["who"]) != r["end_step"]:
                probs.append(f"{c}: clock")
            kinds = {x["type"] for x in r["assists"]}
            allowed = {"base": set(), "mask_prefix": set()}.get(c)
            if allowed is not None and kinds:
                probs.append(f"{c}: helpers present")
            for x in r["assists"]:
                if x["status"] == "assisted" and not x.get("ok"):
                    probs.append(f"{c}: helper goal not reached")
                if c.endswith("_mid") and x["m"] != 1:
                    probs.append(f"{c}: helper outside the middle module")
            if c == "mask_prefix" and r["counts"]["learner_ineffective_prefix"]:
                probs.append("mask: ineffective prefix action executed")
            if c != "mask_prefix" and r["counts"]["mask_steps"]:
                probs.append(f"{c}: mask active")
            if r["arrival"] is not None and "cert" not in r["arrival"]:
                probs.append(f"{c}: arrival not certified")
    out = {"dir": str(d.relative_to(ROOT)), "problems": probs, "actions": s["actions"], "actions_total": s["actions_total"],
           "wall_seconds": s["wall_seconds"],
           "throughput_actions_per_s": s["actions_total"] / max(1e-9, s["wall_seconds"])}
    (OUT / "canary_check.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--canary", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if a.canary:
        return canary()
    pols = list(CFG["policies"])
    R, PL, cells, problems, dirs = {}, {}, {}, [], {}
    for p in pols:
        d = job_dir(f"p6-ctrl-{p}")
        s = json.loads((d / "summary.json").read_text())
        dirs[p] = str(d.relative_to(ROOT))
        if s["panel_sha256"] != CFG["panel_sha256"]:
            problems.append(f"{p}: panel hash")
        rec = sum(json.loads(f.read_text())["actions"] for f in (d / "env_steps").glob("*.json"))
        if rec != s["actions_total"]:
            problems.append(f"{p}: step records {rec} != summary {s['actions_total']}")
        for c in CONDS:
            rows = jl(d / f"ctrl_{p}_{c}.jsonl")
            if len(rows) != CFG["n_layouts"] * CFG["attempts"]:
                problems.append(f"{p} {c}: rows")
            R[(p, c)] = rows
            PL[(p, c)] = per_layout(rows, CFG["n_layouts"])
            cells[(p, c)] = cell_stats(rows)
    rng = np.random.default_rng(20261103)
    out = {"dirs": dirs, "problems": problems, "cells": {f"{p}|{c}": v for (p, c), v in cells.items()}, "cohorts": {}}
    for coh, cp in CFG["cohorts"].items():
        pooled = {c: cell_stats([r for p in cp for r in R[(p, c)]]) for c in CONDS}
        out["cohorts"][coh] = {"pooled": pooled, "contrasts": contrasts(PL, cp, rng), "rescue": rescue(R, cp)}
    (OUT / "summary.json").write_text(json.dumps(out, indent=1, default=float))
    f3 = lambda v: "—" if v is None else f"{v:.3f}"
    f3s = lambda v: "—" if v is None else f"{v:+.3f}"
    md = ["# Controller diagnostics on frozen policies (d6_ctrl 64 K=3 layouts x 2 attempts; exploratory)", "",
          f"Problems: {problems or 'none'}", ""]
    for coh, cp in CFG["cohorts"].items():
        co = out["cohorts"][coh]
        md += [f"## Cohort {coh} ({', '.join(cp)})", "",
               "| condition | P1 = S/n | Δ vs base [95% t over layouts] | Bonferroni | crossed bootstrap | policies > 0 | q = A/n | r = S_A/A | F/A | exposure | helper fraction | ineffective prefix / ep | locked toggles / ep |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in CONDS:
            pc = co["pooled"][c]
            k = pc["counts"]
            if c == "base":
                dtxt = bon = crs = npos = "—"
            else:
                x = co["contrasts"]["cohort"][c]
                dtxt = f"{x['mean']:+.3f} [{x['lo']:+.3f}, {x['hi']:+.3f}]"
                bon = f"[{x['bonferroni']['lo']:+.3f}, {x['bonferroni']['hi']:+.3f}]"
                crs = f"[{x['crossed_lo']:+.3f}, {x['crossed_hi']:+.3f}]"
                npos = f"{x['n_policies_positive']}/4"
            md.append(f"| {c} | {f3(pc['P1'])} ({k['S']}/{k['n']}) | {dtxt} | {bon} | {crs} | {npos} | {f3(pc['q'])} ({k['A']}/{k['n']}) | "
                      f"{f3(pc['r'])} ({k['S_A']}/{k['A']}) | {f3(pc['finishable_of_arrivals'])} ({k['F']}/{k['A']}) | "
                      f"{f3(pc['exposure'])} | {f3(pc['helper_action_fraction'])} | {pc['learner_ineffective_prefix_per_ep']:.1f} | "
                      f"{pc['learner_locked_toggles_per_ep']:.1f} |")
        md += ["", "Interactions (both − key − door + base), cohort mean [95% t; crossed bootstrap]:"]
        for s in SCOPES:
            x = co["contrasts"]["cohort"][f"interaction_{s}"]
            md.append(f"- {s}: {x['mean']:+.3f} [{x['lo']:+.3f}, {x['hi']:+.3f}; {x['crossed_lo']:+.3f}, {x['crossed_hi']:+.3f}]")
        md += ["", "Per-policy Δ P1 vs base (mean over layouts [95% t]):", "",
               "| policy | base P1 | " + " | ".join(CONDS[1:]) + " | int. mid | int. all |",
               "|---|---|" + "---|" * (len(CONDS) + 1)]
        for p in cp:
            pp = co["contrasts"]["per_policy"][p]
            md.append(f"| {p} | {f3(cells[(p, 'base')]['P1'])} | " + " | ".join(
                f"{pp[c]['mean']:+.3f} [{pp[c]['lo']:+.3f}, {pp[c]['hi']:+.3f}]" for c in CONDS[1:]) + " | " + " | ".join(
                f"{pp[f'interaction_{s}']['mean']:+.3f}" for s in SCOPES) + " |")
        md += ["", "Assistance (pooled over the cohort; evaluated / assisted ok / unresolved / certified impossible / not needed; helper actions):", ""]
        for c in CONDS[1:7]:
            pc = co["pooled"][c]
            parts = []
            for key, v in pc["assist"].items():
                if v["evaluated"]:
                    parts.append(f"{key}: {v['evaluated']}/{v['ok']}/{v['unresolved']}/{v['certified_impossible']}/{v['not_needed']} ({v['helper_actions']})")
            md.append(f"- {c}: " + "; ".join(parts) + f"; key lost after KA in {pc['key_lost_after_ka_eps']} eps; backtrack after DA in {pc['backtrack_after_da_eps']} eps")
        pm = co["pooled"]["mask_prefix"]
        md += ["", f"Mask: mean removed mass per masked step {f3(pm['mask_removed_mean_per_masked_step'])}; share of masked steps whose action changed {f3(pm['mask_changed_action_share'])}; base ineffective share of learner prefix steps {f3(co['pooled']['base']['ineffective_prefix_share_of_learner_prefix_steps'])}.", "",
               "Rescue of base failures (pre-boundary / post-arrival) and loss of base successes:", ""]
        for c in CONDS[1:]:
            x = co["rescue"]["rescued"][c]
            l = co["rescue"]["lost"][c]
            md.append(f"- {c}: pre {x['pre']['rescued']}/{x['pre']['base_failures']}, post {x['post']['rescued']}/{x['post']['base_failures']}; lost {l['lost']}/{l['base_successes']}")
        md += ["", "Timing (pooled): arrival time median / remaining median; module durations (median, entered):", ""]
        for c in CONDS:
            pc = co["pooled"][c]
            at, rm = pc["arrival_tau"], pc["arrival_remaining"]
            md.append(f"- {c}: tau {f3(at and at['0.5'])} / remaining {f3(rm and rm['0.5'])}; " + "; ".join(
                f"{m} {f3(v['median'])} ({v['entered']})" for m, v in pc["module_duration"].items()) +
                f"; end stages {pc['end_stage']}")
        md.append("")
    (OUT / "table.md").write_text("\n".join(md) + "\n")
    with open(OUT / "cells.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["policy", "condition", "n", "S", "A", "S_A", "F", "U", "I", "S_F", "P1", "q", "r", "F_over_A",
                    "exposure", "helper_fraction", "ineffective_prefix_per_ep", "locked_toggles_per_ep"])
        for (p, c), v in cells.items():
            k = v["counts"]
            w.writerow([p, c, k["n"], k["S"], k["A"], k["S_A"], k["F"], k["U"], k["I"], k["S_F"], v["P1"], v["q"],
                        v["r"], v["finishable_of_arrivals"], v["exposure"], v["helper_action_fraction"],
                        v["learner_ineffective_prefix_per_ep"], v["learner_locked_toggles_per_ep"]])
    trajectories(R, CFG["cohorts"])
    print("\n".join(md))


if __name__ == "__main__":
    main()
