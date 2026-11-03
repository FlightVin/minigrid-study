"""Record audit of the controller diagnostics (owner instruction 2026-11-02c, section 1). Added after the 2026-11-02b
outcomes; it corrects interpretation only and changes no historical verdict.

Usage: .venv/bin/python tools/audit_p6b.py -> reports/p6/audit_p6b.json and reports/p6/audit_p6b.md

1. Direct paired contrasts between assistance and masking, from the per-layout attempt means of the raw ctrl rows:
   key_mid - mask_prefix, key_all - mask_prefix, both_all - mask_prefix (cohort mean over the 4 policies of each
   cohort). Two scopes: layout-conditional (95% t over the 64 layouts of the policy-averaged difference, fixed
   policies) and crossed (policy-and-layout bootstrap, 10,000 resamples, policies and layouts resampled
   independently). The key-only contrasts against base are restated with both scopes.
2. Key drops reclassified by the state of the associated door. Every episode of base, key_mid and key_all with at
   least one learner key drop is replayed from its recorded action string in a fresh StageTask (no policy, no
   random numbers; executed actions are counted through bc2rl.accounting). For each learner drop of module j's key:
     door_locked      door j still locked (premature loss: the key is still required)
     door_open_unpassed  door j unlocked, the agent has never stood beyond it
     door_passed      the agent has stood beyond door j (the key is obsolete)
   Drops of a key that matches no module (none exist in K=3) are counted separately. The replay checks that the
   recorded end step and success are reproduced.
"""
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
import analyze_p6 as A          # noqa: E402  (frozen helpers: job_dir, jl, per_layout, t_crit)
from bc2rl import task as T     # noqa: E402

PAIRS = [("key_mid", "mask_prefix"), ("key_all", "mask_prefix"), ("both_all", "mask_prefix"),
         ("key_mid", "base"), ("key_all", "base")]
DROP_CONDS = ("base", "key_mid", "key_all")
NB = 10_000


def scopes(D, rng):
    """D: policies x layouts paired differences."""
    P, L = D.shape
    d = D.mean(0)
    m, se = float(d.mean()), float(d.std(ddof=1) / sqrt(L))
    c = A.t_crit(L - 1)
    bi, bj = rng.integers(0, P, (NB, P)), rng.integers(0, L, (NB, L))
    cr = np.array([D[bi[b]][:, bj[b]].mean() for b in range(NB)])
    return {"mean": m, "layout_conditional_lo": m - c * se, "layout_conditional_hi": m + c * se,
            "crossed_lo": float(np.quantile(cr, 0.025)), "crossed_hi": float(np.quantile(cr, 0.975)),
            "per_policy_means": [float(x) for x in D.mean(1)], "n_policies_positive": int((D.mean(1) > 0).sum())}


def panel():
    lay = json.loads((ROOT / "data/r6-v1/layouts.json").read_text())["d6_ctrl"]
    return [T.Layout.from_dict(it["layout"]) for it in lay if it["layout"]["K"] == 3][:A.CFG["n_layouts"]]


def classify_drops(row, layout):
    env = T.StageTask()
    env.reset(options={"layout": layout})
    colors = layout.colors()
    slots = layout.active_slots()
    passed = [False] * layout.K
    out, info = [], {}
    for a, who in zip(row["actions"], row["who"]):
        a = int(a)
        c, f = env.carrying, env.grid.get(*env.front_pos)
        if who == "p" and a == 4 and c is not None and c.type == "key" and f is None:
            j = colors.index(c.color) if c.color in colors else None
            if j is None:
                kind = "non_module_key"
            else:
                door = env.grid.get(T.DOOR_X[slots[j]], layout.door_rows[j])
                kind = "door_passed" if passed[j] else ("door_locked" if door.is_locked else "door_open_unpassed")
            ka = any(x["type"] == "ka" and x["m"] == j and x["status"] == "assisted" and x["step"] <= env.step_count
                     for x in row["assists"])
            out.append({"module": j, "kind": kind, "after_ka_in_module": ka, "step": int(env.step_count)})
        _, _, term, _, info = env.step(a)
        for k, s in enumerate(slots):
            if env.agent_pos[0] > T.DOOR_X[s]:
                passed[k] = True
    ok = info.get("success") == row["success"] and env.step_count == row["end_step"]
    return out, ok


def main():
    rng = np.random.default_rng(20261102)
    lays = panel()
    out = {"note": "Record audit (2026-11-02c, section 1); added after outcomes; interpretation only.",
           "contrasts": {}, "drops": {}, "replay": {"episodes": 0, "mismatches": 0}}
    md = ["# Controller record audit (2026-11-02c, section 1)", "",
          "Added after the 2026-11-02b outcomes. Interpretation only; no historical verdict changes.", "",
          "## Direct paired contrasts (cohort mean over 4 policies; n = 64 layouts x 2 attempts per policy)", "",
          "| Cohort | Contrast | Mean | Layout-conditional 95% t | Crossed policy-and-layout 95% | Policies > 0 |",
          "|---|---|---|---|---|---|"]
    rows = {}
    for coh, pols in A.CFG["cohorts"].items():
        PL = {}
        for p in pols:
            d = A.job_dir(f"p6-ctrl-{p}")
            for c in A.CONDS:
                rows[(p, c)] = A.jl(d / f"ctrl_{p}_{c}.jsonl")
                PL[(p, c)] = A.per_layout(rows[(p, c)], A.CFG["n_layouts"])
        for a, b in PAIRS:
            D = np.stack([PL[(p, a)] - PL[(p, b)] for p in pols])
            r = scopes(D, rng)
            out["contrasts"][f"{coh}|{a}-{b}"] = r
            md.append(f"| {coh} | {a} − {b} | {r['mean']:+.3f} | [{r['layout_conditional_lo']:+.3f}, "
                      f"{r['layout_conditional_hi']:+.3f}] | [{r['crossed_lo']:+.3f}, {r['crossed_hi']:+.3f}] | "
                      f"{r['n_policies_positive']}/4 |")
    md += ["", "## Learner key drops by the state of the associated door", "",
           "| Cohort | Condition | Episodes with a drop | Drops | Door locked (premature) | Door unlocked, not passed "
           "| Door passed (obsolete) | Middle-module key after KA: locked / unlocked-unpassed / passed |",
           "|---|---|---|---|---|---|---|---|"]
    for coh, pols in A.CFG["cohorts"].items():
        for c in DROP_CONDS:
            cnt = {"door_locked": 0, "door_open_unpassed": 0, "door_passed": 0, "non_module_key": 0}
            mid_ka = {"door_locked": 0, "door_open_unpassed": 0, "door_passed": 0}
            mid_ka_episodes = {"door_locked": 0, "any": 0}
            eps = 0
            for p in pols:
                for r in rows[(p, c)]:
                    if r["counts"]["learner_key_drops"] == 0:
                        continue
                    drops, ok = classify_drops(r, lays[r["item"]])
                    out["replay"]["episodes"] += 1
                    out["replay"]["mismatches"] += int(not ok)
                    if drops:
                        eps += 1
                    kinds_mid = set()
                    for x in drops:
                        cnt[x["kind"]] += 1
                        if x["module"] == 1 and x["after_ka_in_module"]:
                            mid_ka[x["kind"]] += 1
                            kinds_mid.add(x["kind"])
                    if kinds_mid:
                        mid_ka_episodes["any"] += 1
                        mid_ka_episodes["door_locked"] += int("door_locked" in kinds_mid)
            n_ka_mid = sum(1 for p in pols for r in rows[(p, c)]
                           if any(x["type"] == "ka" and x["m"] == 1 and x["status"] == "assisted" for x in r["assists"]))
            out["drops"][f"{coh}|{c}"] = {"episodes_with_drop": eps, "drops": cnt, "middle_key_drops_after_ka": mid_ka,
                                          "episodes_middle_ka_assisted": n_ka_mid,
                                          "episodes_middle_key_dropped_after_ka": mid_ka_episodes}
            md.append(f"| {coh} | {c} | {eps} | {sum(cnt.values())} | {cnt['door_locked']} | "
                      f"{cnt['door_open_unpassed']} | {cnt['door_passed']} | "
                      f"{mid_ka['door_locked']} / {mid_ka['door_open_unpassed']} / {mid_ka['door_passed']} "
                      f"(episodes {mid_ka_episodes['any']} of {n_ka_mid} assisted; with a premature drop "
                      f"{mid_ka_episodes['door_locked']}) |")
    md += ["", f"Replayed episodes: {out['replay']['episodes']}; outcome mismatches: {out['replay']['mismatches']}.", ""]
    (ROOT / "reports/p6/audit_p6b.json").write_text(json.dumps(out, indent=1))
    (ROOT / "reports/p6/audit_p6b.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
