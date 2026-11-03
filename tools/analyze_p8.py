"""Analysis of the actor capability audit (owner instruction 2026-11-03; PROTOCOL_FREEZE Amendment 10). No actions.

Usage: .venv/bin/python tools/analyze_p8.py prep    -> reports/p8/prep.{json,md}   (validation, dataset, tiny, fits;
                                                        never reads the final test)
       .venv/bin/python tools/analyze_p8.py final   -> reports/p8/audit.{json,md}  (adds the final test and rollouts)

Uncertainty (Amendment 10 I, J): per-layout means over unique states (or the layout's rollout outcome), seed means per
layout, then the mean over layouts with a 95% percentile bootstrap over layouts (10,000 resamples, seed 20261108).
Fit-seed variation: per-seed values and their range. Paired comparisons use per-layout differences of seed means.
"""
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/p8"
STRATA = ("on_track", "wrong_key", "key_lost", "backtracked", "all_unlocked")
TYPES = ("turn", "forward", "pickup", "drop", "toggle")
CONDS = {"warm128-n0": "p8-fit-warm128-n0-s{}", "warm128-n1": "p8-fit-warm128-n1-s{}",
         "warm128-n2": "p8-fit-warm128-n2-s{}", "scratch128-n2": "p8-fit-scratch128-n2-s{}",
         "scratch1024-n2": "p8-fit-scratch1024-n2-s{}"}
SEEDS = (0, 1, 2)
COMPARE = (("scratch1024-n2", "scratch128-n2"), ("warm128-n2", "scratch128-n2"), ("warm128-n2", "warm128-n0"))


def latest(job):
    ds = sorted(d for d in (ROOT / ".mae/runs").glob(f"*/{job}") if (d / "summary.json").exists())
    return ds[-1] if ds else None


def js(job):
    d = latest(job)
    return json.loads((d / "summary.json").read_text()) if d else None


def boot(per_layout, seed=20261108, n=10_000):
    v = np.asarray(per_layout, float)
    rng = np.random.default_rng(seed)
    m = v[rng.integers(0, len(v), (n, len(v)))].mean(1)
    return [float(v.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def type_masks(mask):
    m = np.asarray(mask).astype(np.int64)
    return {"turn": ((m & 1) | ((m >> 1) & 1)).astype(bool), "forward": ((m >> 2) & 1).astype(bool),
            "pickup": ((m >> 3) & 1).astype(bool), "drop": ((m >> 4) & 1).astype(bool),
            "toggle": ((m >> 5) & 1).astype(bool)}


def prep():
    out = {}
    v = js("p8-validate")
    out["validation"] = {g: v[g] for g in ("train", "val", "test")}
    out["check_label"] = v["check_label"]["by"]
    out["check_label_violations"] = v["check_label"]["violation_examples"]
    ex = v["expert"]
    out["expert_validation_panel"] = {"episodes": ex["episodes"], "crossed": ex["crossed"],
                                      "tau_mean": float(np.mean([e["tau"] for e in ex["results"] if e["crossed"]])),
                                      "stops": [e["stop"] for e in ex["results"] if not e["crossed"]]}
    out["collect"] = js("p8-collect")
    for g in out["collect"]["groups"].values():
        g.pop("layout_indices_used", None)
    out["dataset"] = json.loads((OUT / "dataset_manifest.json").read_text())
    out["tiny"] = {}
    for lr in ("3e-4", "1e-3"):
        s = js(f"p8-tiny-lr{lr}")
        if s:
            out["tiny"][lr] = {k: s[k] for k in ("final", "checks", "passes", "compute_seconds", "n")}
            out["tiny"][lr]["curve"] = s["curve"]
    out["fits"] = {}
    for c, pat in CONDS.items():
        for s in SEEDS:
            f = js(pat.format(s))
            if f:
                d = latest(pat.format(s))
                curve = json.loads((d / "curve.json").read_text())
                out["fits"][pat.format(s)] = {
                    "condition": c, "seed": s, "n_train": f["n_train"], "params": f["params"],
                    "selected_update": f["selected_update"], "selected_val": f["selected"]["val"],
                    "selected_train_probe": f["selected"]["train_probe"], "final_val": f["final"]["val"],
                    "final_train_probe": f["final"]["train_probe"], "train_seconds": f["train_seconds"],
                    "compute_seconds": f["compute_seconds"],
                    "curve_val_agree": {str(p["update"]): p["val"]["argmax_in_set"] for p in curve
                                        if p["update"] in (0, 1000, 2500, 5000, 10000, 20000, 30000)},
                    "curve_probe_agree": {str(p["update"]): p["train_probe"]["argmax_in_set"] for p in curve
                                          if p["update"] in (0, 1000, 2500, 5000, 10000, 20000, 30000)}}
    out["fit_conditions"] = {}
    for c, pat in CONDS.items():
        rows = [out["fits"][pat.format(s)] for s in SEEDS if pat.format(s) in out["fits"]]
        if rows:
            out["fit_conditions"][c] = {k: {"per_seed": [r[k]["argmax_in_set"] for r in rows],
                                            "mean": float(np.mean([r[k]["argmax_in_set"] for r in rows]))}
                                        for k in ("selected_train_probe", "selected_val", "final_train_probe", "final_val")}
            out["fit_conditions"][c]["selected_val_mass_mean"] = float(np.mean([r["selected_val"]["mass"] for r in rows]))
            out["fit_conditions"][c]["selected_val_loss_mean"] = float(np.mean([r["selected_val"]["set_loss"] for r in rows]))
            out["fit_conditions"][c]["selected_probe_loss_mean"] = float(np.mean([r["selected_train_probe"]["set_loss"] for r in rows]))
    return out


def by_groups(z, prefix, agree):
    """Pooled per-state means by stratum and label action type (unique states)."""
    st = z[prefix + "_stratum"]
    tm = type_masks(z[prefix + "_mask"])
    r = {"stratum": {s: [float(agree[st == i].mean()) if (st == i).any() else None, int((st == i).sum())]
                     for i, s in enumerate(STRATA)},
         "type": {t: [float(agree[tm[t]].mean()) if tm[t].any() else None, int(tm[t].sum())] for t in TYPES}}
    return r


def final():
    out = prep()
    z = np.load(ROOT / "data/cap-v1/dataset.npz")
    td = latest("p8-test")
    pred = np.load(td / "test_predictions.npz")
    lay = z["test_layout"]
    layouts = np.unique(lay)
    res = {}
    per_layout = {}
    for c, pat in CONDS.items():
        seeds = {}
        for s in SEEDS:
            j = pat.format(s)
            a, m, l = (pred[f"{j}|test|{k}"].astype(float) for k in ("agree", "mass", "loss"))
            ra, rm = pred[f"{j}|recov|agree"].astype(float), pred[f"{j}|recov|mass"].astype(float)
            seeds[s] = {"test": {"argmax_in_set": a.mean(), "mass": m.mean(), "set_loss": l.mean()},
                        "test_groups": by_groups(z, "test", a),
                        "recov": {"argmax_in_set": ra.mean(), "mass": rm.mean()},
                        "recov_groups": by_groups(z, "recov", ra),
                        "layout_agree": np.array([a[lay == L].mean() for L in layouts]),
                        "layout_mass": np.array([m[lay == L].mean() for L in layouts])}
        pl = np.mean([seeds[s]["layout_agree"] for s in SEEDS], 0)
        pm = np.mean([seeds[s]["layout_mass"] for s in SEEDS], 0)
        per_layout[c] = pl
        res[c] = {"test_agree_layout_boot": boot(pl), "test_mass_layout_boot": boot(pm),
                  "test_agree_per_seed": [float(seeds[s]["test"]["argmax_in_set"]) for s in SEEDS],
                  "test_mass_per_seed": [float(seeds[s]["test"]["mass"]) for s in SEEDS],
                  "test_set_loss_per_seed": [float(seeds[s]["test"]["set_loss"]) for s in SEEDS],
                  "recov_agree_per_seed": [float(seeds[s]["recov"]["argmax_in_set"]) for s in SEEDS],
                  "recov_mass_per_seed": [float(seeds[s]["recov"]["mass"]) for s in SEEDS],
                  "test_by_stratum": {k: [float(np.mean([seeds[s]["test_groups"]["stratum"][k][0] for s in SEEDS]))
                                          if seeds[0]["test_groups"]["stratum"][k][0] is not None else None,
                                          seeds[0]["test_groups"]["stratum"][k][1]] for k in STRATA},
                  "test_by_type": {k: [float(np.mean([seeds[s]["test_groups"]["type"][k][0] for s in SEEDS]))
                                       if seeds[0]["test_groups"]["type"][k][0] is not None else None,
                                       seeds[0]["test_groups"]["type"][k][1]] for k in TYPES},
                  "recov_by_stratum": {k: float(np.mean([seeds[s]["recov_groups"]["stratum"][k][0] for s in SEEDS]))
                                       for k in STRATA}}
    out["test"] = res
    out["test_compare"] = {f"{a} - {b}": {"layout_boot": boot(per_layout[a] - per_layout[b]),
                                          "per_seed": [float(x - y) for x, y in zip(res[a]["test_agree_per_seed"],
                                                                                     res[b]["test_agree_per_seed"])]}
                           for a, b in COMPARE}
    # rollouts
    rd = latest("p8-rollout")
    rows = [json.loads(l) for l in (rd / "rollouts.jsonl").read_text().splitlines() if l.strip()]
    first = [r for r in rows if r["attempt"] == 0]
    det = {}
    for r in rows:
        if r["attempt"] == 1:
            o = next(x for x in first if x["controller"] == r["controller"] and x["item"] == r["item"])
            det.setdefault(r["controller"], []).append(o["steps"] == r["steps"] and o["crossed"] == r["crossed"]
                                                       and o["trace"] == r["trace"])
    ctrl = sorted({r["controller"] for r in first})
    roll = {}
    reach = {}
    for c in ctrl:
        rr = sorted((r for r in first if r["controller"] == c), key=lambda r: r["item"])
        x = np.array([r["crossed"] for r in rr], float)
        reach[c] = x
        fails = [r for r in rr if not r["crossed"]]
        cats = {}
        for r in fails:
            k = (r["end_category"] or "none")
            st = ("all_unlocked" if k.startswith("all_unlocked") else "backtracked" if k.startswith("behind")
                  else "key_lost" if k.endswith("_key_displaced") else
                  "wrong_key" if k in ("in_module_obsolete_key", "in_module_other_object") else "on_track")
            cats[st] = cats.get(st, 0) + 1
        roll[c] = {"reached": int(x.sum()), "n": len(rr), "tau_mean": float(np.mean([r["tau"] for r in rr if r["crossed"]]))
                   if x.any() else None,
                   "fail_stratum": cats,
                   "fail_stage_end": {k: sum(1 for r in fails if r["trace"]["stage_end"] == k)
                                      for k in sorted({r["trace"]["stage_end"] for r in fails})},
                   "per_episode_means": {k: float(np.mean([r["trace"][k] for r in rr])) for k in
                                         ("locked_toggles", "wrong_key_pickups", "noop_actions", "pose_repeat_frac")},
                   "premature_key_drops": float(np.mean([r["trace"]["key_drops"]["premature"] for r in rr]))}
    out["rollouts"] = roll
    out["determinism_check"] = {c: [sum(v), len(v)] for c, v in det.items()}
    cond_reach = {}
    for c, pat in CONDS.items():
        names = [f"{c}-s{s}" for s in SEEDS]
        if all(n in reach for n in names):
            cond_reach[c] = {"per_seed": [float(reach[n].mean()) for n in names],
                             "layout_boot": boot(np.mean([reach[n] for n in names], 0))}
    bc = [f"bc-s{116 + s}" for s in SEEDS]
    if all(n in reach for n in bc):
        cond_reach["bc_warm_start"] = {"per_seed": [float(reach[n].mean()) for n in bc],
                                       "layout_boot": boot(np.mean([reach[n] for n in bc], 0))}
    if "expert" in reach:
        cond_reach["expert"] = {"per_seed": [float(reach["expert"].mean())], "layout_boot": boot(reach["expert"])}
    out["rollout_conditions"] = cond_reach
    lay_r = {c: np.mean([reach[f"{c}-s{s}"] for s in SEEDS], 0) for c in CONDS if f"{c}-s0" in reach}
    if all(n in reach for n in bc):
        lay_r["bc_warm_start"] = np.mean([reach[n] for n in bc], 0)
    out["rollout_compare"] = {f"{a} - {b}": boot(lay_r[a] - lay_r[b]) for a, b in
                              COMPARE + (("warm128-n2", "bc_warm_start"),) if a in lay_r and b in lay_r}
    return out


def fmt(x, d=3):
    return "—" if x is None else f"{x:.{d}f}"


def md_prep(o):
    L = ["# Capability audit — preparation (validation, dataset, tiny check, fits; final test not read)", ""]
    L += ["## Validation", "", "| Group | Rows | Unique obs | Unique labelled configs | Rebuilt mismatches | Obs conflicts | Config conflicts across time | Door reads not visible |",
          "|---|---|---|---|---|---|---|---|"]
    for g, v in o["validation"].items():
        L.append(f"| {g} | {v['rows']} | {v['unique_observations']} | {v['unique_labelled_configurations']} | "
                 f"{v['rebuilt_query_mismatches']} | {v['observation_conflicts']} | "
                 f"{v['configuration_label_conflicts_across_time']} | {v['door_rows_or_colours_not_visible']} |")
    L += ["", "check_label (real environment):", ""]
    L += [f"- {k}: {v['with_violations']}/{v['checked']} with violations" for k, v in sorted(o["check_label"].items())]
    e = o["expert_validation_panel"]
    L += ["", f"Expert prefix controller (validation panel): crossed {e['crossed']}/{e['episodes']}, mean time to "
          f"boundary {e['tau_mean']:.1f}; non-crossing stops: {e['stops']}", ""]
    L += ["## Dataset", "", "```", json.dumps({g: {k: v for k, v in d.items() if k not in ("label_type_share",)}
                                               for g, d in o["dataset"]["groups"].items()}, indent=1), "```", ""]
    L += [f"Subsets: {o['dataset']['subsets']}", f"Tiny: {o['dataset']['tiny']}",
          f"Cross-group shared configurations: {o['dataset']['cross_group_shared_observations']}",
          f"Layout provenance: {o['dataset']['layout_provenance']}", ""]
    L += ["## Tiny-set check", "", "| lr | argmax-in-set | mass | set loss | grad norm | checks | passes |", "|---|---|---|---|---|---|---|"]
    for lr, t in o["tiny"].items():
        f = t["final"]
        L.append(f"| {lr} | {f['argmax_in_set']:.4f} | {f['mass']:.4f} | {f['set_loss']:.4f} | {f['grad_norm']:.3g} | "
                 f"{t['checks']} | {t['passes']} |")
    L += ["", "## Fits (selected checkpoint by validation; final test not read)", "",
          "| Condition | n train | train probe (selected) | validation (selected) | train probe (final) | validation (final) | val mass | val set loss | probe set loss |",
          "|---|---|---|---|---|---|---|---|---|"]
    for c, v in o["fit_conditions"].items():
        n = next(f["n_train"] for f in o["fits"].values() if f["condition"] == c)
        L.append(f"| {c} | {n} | {fmt(v['selected_train_probe']['mean'])} {[round(x, 3) for x in v['selected_train_probe']['per_seed']]} | "
                 f"{fmt(v['selected_val']['mean'])} {[round(x, 3) for x in v['selected_val']['per_seed']]} | "
                 f"{fmt(v['final_train_probe']['mean'])} | {fmt(v['final_val']['mean'])} | {fmt(v['selected_val_mass_mean'])} | "
                 f"{fmt(v['selected_val_loss_mean'])} | {fmt(v['selected_probe_loss_mean'])} |")
    L += ["", "Selected updates and compute: " + ", ".join(f"{j.replace('p8-fit-', '')} u{f['selected_update']} "
                                                          f"{f['compute_seconds']:.0f}s" for j, f in o["fits"].items())]
    return L


def md_final(o):
    L = md_prep(o)
    L[0] = "# Actor capability audit — results (Amendment 10)"
    L += ["", "## Final test states (fresh r7_conf layouts; unique configurations)", "",
          "| Condition | argmax-in-set [95% layout bootstrap] | per seed | mass [95%] | set loss per seed | recovery bank argmax per seed | recovery mass per seed |",
          "|---|---|---|---|---|---|---|"]
    for c, r in o["test"].items():
        b, m = r["test_agree_layout_boot"], r["test_mass_layout_boot"]
        L.append(f"| {c} | {b[0]:.3f} [{b[1]:.3f}, {b[2]:.3f}] | {[round(x, 3) for x in r['test_agree_per_seed']]} | "
                 f"{m[0]:.3f} [{m[1]:.3f}, {m[2]:.3f}] | {[round(x, 3) for x in r['test_set_loss_per_seed']]} | "
                 f"{[round(x, 3) for x in r['recov_agree_per_seed']]} | {[round(x, 3) for x in r['recov_mass_per_seed']]} |")
    L += ["", "By stratum (test argmax-in-set, seed mean; n unique states):", "",
          "| Condition | " + " | ".join(STRATA) + " |", "|---|" + "---|" * len(STRATA)]
    for c, r in o["test"].items():
        L.append(f"| {c} | " + " | ".join(f"{fmt(r['test_by_stratum'][k][0])} ({r['test_by_stratum'][k][1]})" for k in STRATA) + " |")
    L += ["", "By label action type (a state counts in every type in its label set):", "",
          "| Condition | " + " | ".join(TYPES) + " |", "|---|" + "---|" * len(TYPES)]
    for c, r in o["test"].items():
        L.append(f"| {c} | " + " | ".join(f"{fmt(r['test_by_type'][k][0])} ({r['test_by_type'][k][1]})" for k in TYPES) + " |")
    L += ["", "Recovery bank by stratum (argmax-in-set, seed mean):", ""]
    for c, r in o["test"].items():
        L.append(f"- {c}: " + ", ".join(f"{k} {fmt(v)}" for k, v in r["recov_by_stratum"].items()))
    L += ["", "Paired comparisons (test argmax-in-set; per-layout differences of seed means):", ""]
    for k, v in o["test_compare"].items():
        b = v["layout_boot"]
        L.append(f"- {k}: {b[0]:+.3f} [{b[1]:+.3f}, {b[2]:+.3f}]; per seed {[round(x, 3) for x in v['per_seed']]}")
    L += ["", "## Rollouts (final panel, 64 layouts, deterministic argmax, prefix only)", "",
          "| Controller | Reached | tau mean | failures by stratum | failures by stage | locked toggles | wrong-key pickups | premature drops | no-ops | pose repeat |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for c, r in o["rollouts"].items():
        pe = r["per_episode_means"]
        L.append(f"| {c} | {r['reached']}/{r['n']} | {fmt(r['tau_mean'], 1)} | {r['fail_stratum']} | {r['fail_stage_end']} | "
                 f"{pe['locked_toggles']:.1f} | {pe['wrong_key_pickups']:.2f} | {r['premature_key_drops']:.2f} | "
                 f"{pe['noop_actions']:.1f} | {pe['pose_repeat_frac']:.2f} |")
    L += ["", "Conditions (boundary reach; seed means per layout; 95% layout bootstrap):", ""]
    for c, v in o["rollout_conditions"].items():
        b = v["layout_boot"]
        L.append(f"- {c}: {b[0]:.3f} [{b[1]:.3f}, {b[2]:.3f}]; per seed {[round(x, 3) for x in v['per_seed']]}")
    L += ["", "Paired rollout comparisons:", ""]
    L += [f"- {k}: {b[0]:+.3f} [{b[1]:+.3f}, {b[2]:+.3f}]" for k, b in o["rollout_compare"].items()]
    L += ["", f"Determinism check (second attempt identical): {o['determinism_check']}"]
    return L


def main():
    mode = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    if mode == "prep":
        o = prep()
        (OUT / "prep.json").write_text(json.dumps(o, indent=1, default=float))
        (OUT / "prep.md").write_text("\n".join(md_prep(o)) + "\n")
    else:
        o = final()
        (OUT / "audit.json").write_text(json.dumps(o, indent=1, default=float))
        (OUT / "audit.md").write_text("\n".join(md_final(o)) + "\n")
    print(f"wrote reports/p8/{'prep' if mode == 'prep' else 'audit'}.md")


if __name__ == "__main__":
    main()
