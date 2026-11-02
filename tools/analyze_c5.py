"""Conditional confirmation analysis (owner instruction 2026-11-02, section 8; PROTOCOL_FREEZE Amendment 7 E).
Frozen before any confirmation run. No actions.

Usage: .venv/bin/python tools/analyze_c5.py [--engineering S]  -> reports/c5/{c5_summary.json, c5_branches.csv, c5.md}
  --engineering S: execution checks for seed S only (canary); no outcome.

Seeds 96-115 (n = 20, all kept). Arms A = 00 and M = the method selected by reports/p5/gate.json, forked from the same
post-probe state. Primary: d_i = P1(M_i) - P1(A_i) at 501,760 on c5_final (256 K=3 layouts x 2, common random
numbers); one two-sided paired t-test, alpha 0.05, 95% t-interval; "supported" iff the interval excludes 0.
Sensitivity (not decision rules): crossed seed x layout bootstrap (seeds and the 256 layouts resampled with
replacement, layouts common to arms and seeds, 10,000 replicates, RNG 20261105); layouts-only bootstrap (conditional
on the 20 seeds); exact sign-flip over 2^20 patterns (exchangeable signs under H0). Uncertainty relative to 0, 0.03
and 0.05. Descriptive: d at 251,904 (same panel); per endpoint q, r, entry-bank competence (c5_bank 128 x 2);
verified finishable access at 501,760 (certified feasible; unresolved and impossible separate); arrival timing and
inventory; per-module progress; training allocation (normal versus assisted episodes and successes, assisted-step
fraction, region visitation); cohort (pi0 and post-probe on c5_select). Exact decomposition dp = dq (r1 + r0)/2 +
dr (q1 + q0)/2 per seed (descriptive, not mediation). The pilot is never pooled. Blinded until 20/20 complete.
A benefit is learning efficiency at a fixed budget, not converged performance.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import analyze_p5 as P5    # noqa: E402  (lineage, owner_of, measure, training, tsum: shared helpers)

RUNS = ROOT / ".mae/runs"
OUT = ROOT / "reports/c5"
SEEDS = range(96, 116)
EPS = (251904, 501760)
TAG = {251904: "conf_251904", 501760: "conf_501760"}
PRIMARY = 501760
BOOT_R, BOOT_RNG = 10_000, 20261105
FROZEN = ROOT / "experiments/p5/c5-v1.json"


def check_seed(s, arm, frozen):
    problems, data = [], {}
    pr = [d for d in P5.dirs(f"c5-probe-K3-s{s}") if (d / "summary.json").exists() and (d / "fork.pt").exists()]
    bc = [d for d in P5.dirs(f"c5-bc-s{s}") if (d / "summary.json").exists() and (d / "actor_u8000.pt").exists()]
    if len(pr) != 1 or len(bc) != 1:
        return [f"s{s}: {len(bc)} complete BC, {len(pr)} complete probes"], None
    psum = json.loads((pr[0] / "summary.json").read_text())
    import torch
    fork = torch.load(pr[0] / "fork.pt", map_location="cpu", weights_only=False)
    data["probe"] = {"pi0": psum["pi0"], "probe": psum["probe"]}
    lim = [it["layout"]["limit"] for it in json.loads((ROOT / "data/r5-v1/layouts.json").read_text())["c5_final"] if it["layout"]["K"] == 3]
    for lab, a in (("A", "00"), ("M", arm)):
        base = f"c5-K3-s{s}-{a}"
        P5.TARGET = PRIMARY
        ch = P5.lineage(base)
        if ch is None:
            problems.append(f"s{s} {lab}: branch not complete")
            continue
        for d, _, _ in ch:
            cf = json.loads((d / "config.resolved.json").read_text())
            want = (a, psum["fork_hash"], "c5_final", "c5_bank", 999000, "r5-v1",
                    frozen["assist_schedule"].get(a) if a != "00" else None, 0.25 if a != "00" else 0.0)
            got = (cf.get("arm"), cf.get("fork_hash"), cf["eval_role"], cf["bank_role"], cf["eval_seed"], cf["dataset_id"],
                   cf.get("assist_schedule", {}).get(a) if a != "00" else None, cf.get("alpha"))
            if got != want:
                problems.append(f"s{s} {lab} identity {d.name}")
            if (d / "summary.json").exists():
                sm = json.loads((d / "summary.json").read_text())
                stp = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
                if stp != sum(sm["actions"].values()):
                    problems.append(f"s{s} {lab} {d.name}: step records != summary")
        data[lab] = {"chain": [str(d.relative_to(RUNS)) for d, _, _ in ch]}
        for at in EPS:
            rows = P5.jl(P5.owner_of(ch, at) / f"attempts_{TAG[at]}.jsonl")
            n = [r for r in rows if r["kind"] == "normal"]
            b = [r for r in rows if r["kind"] == "bank"]
            if (len(n), len(b)) != (512, 256):
                problems.append(f"s{s} {lab} {at}: rows {(len(n), len(b))}")
            li = {r["item"]: r["limit"] for r in n}
            if [li[i] for i in range(256)] != lim:
                problems.append(f"s{s} {lab} {at}: panel")
            cert = at == PRIMARY
            if cert and any(r["arrival"] is not None and "cert" not in r["arrival"] for r in n):
                problems.append(f"s{s} {lab} {at}: uncertified arrival")
            arr = [r for r in n if r["arrival"] is not None]
            st = lambda x: sum(1 for r in arr if r["arrival"]["cert"]["status"] == x) / len(n) if cert else None
            per_item = np.zeros(256)
            for r in n:
                per_item[r["item"]] += r["success"] / 2
            tr = [r["trace"] for r in n]
            data[lab][at] = {"P1": sum(r["success"] for r in n) / len(n), "q": len(arr) / len(n),
                             "r": sum(r["success"] for r in arr) / len(arr) if arr else None,
                             "entry": sum(r["success"] for r in b) / len(b),
                             "q_feasible": st("feasible"), "q_unresolved": st("unresolved"), "q_impossible": st("impossible"),
                             "tau_mean": float(np.mean([r["arrival"]["tau"] for r in arr])) if arr else None,
                             "remaining_mean": float(np.mean([r["arrival"]["remaining"] for r in arr])) if arr else None,
                             "reach_module": [float(np.mean([t["mod_entry"][j] is not None for t in tr])) for j in range(3)],
                             "open_door": [float(np.mean([t["door_open"][j] is not None for t in tr])) for j in range(3)],
                             "per_item": per_item}
        data[lab]["training"] = P5.training(ch, fork["counters"])
    return problems, data


def signflip_exact(x):
    x = np.asarray(x, float)
    n, obs, cnt = len(x), abs(x.sum()), 0
    for st in range(0, 2 ** n, 2 ** 16):
        idx = np.arange(st, min(st + 2 ** 16, 2 ** n))
        sg = 1 - 2 * ((idx[:, None] >> np.arange(n)) & 1)
        cnt += int((np.abs(sg @ x) >= obs - 1e-12).sum())
    return cnt / 2 ** n


def boot(Dm, reps=BOOT_R, seed=BOOT_RNG):
    """Dm: (seeds, layouts) per-item paired differences. Returns crossed and layouts-only 95% percentile intervals."""
    rng = np.random.default_rng(seed)
    S, L = Dm.shape
    cr, lo = np.empty(reps), np.empty(reps)
    for b in range(reps):
        si, li = rng.integers(S, size=S), rng.integers(L, size=L)
        cr[b] = Dm[np.ix_(si, li)].mean()
        lo[b] = Dm[:, li].mean()
    q = lambda v: [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]
    return q(cr), q(lo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engineering", type=int)
    a = ap.parse_args()
    frozen = json.loads(FROZEN.read_text())
    arm = json.loads((ROOT / "reports/p5/gate.json").read_text())["selected_arm"]
    assert arm, "no method selected; no confirmation"
    OUT.mkdir(parents=True, exist_ok=True)
    if a.engineering is not None:
        p, d = check_seed(a.engineering, arm, frozen)
        out = {"seed": a.engineering, "arm": arm, "problems": p, "pass": not p}
        if d:
            out["allocation"] = {lab: {k: d[lab]["training"][k] for k in ("train_actions", "assisted_step_fraction", "episodes")}
                                 for lab in ("A", "M") if lab in d}
        (OUT / "canary_check.json").write_text(json.dumps(out, indent=1))
        print(json.dumps({k: out[k] for k in ("seed", "arm", "problems", "pass")}, indent=1))
        return
    allp, D = [], {}
    for s in SEEDS:
        p, d = check_seed(s, arm, frozen)
        allp += p
        D[s] = d
    complete = [s for s in SEEDS if D[s] is not None and "A" in D[s] and "M" in D[s]]
    res = {"arm": arm, "complete_seeds": complete, "problems": allp}
    if len(complete) != 20 or allp:
        res["outcomes"] = "blinded: fewer than 20 complete seeds or problems present"
        (OUT / "c5_summary.json").write_text(json.dumps(res, indent=1))
        print(json.dumps(res, indent=1))
        sys.exit(1)
    d = {at: np.array([D[s]["M"][at]["P1"] - D[s]["A"][at]["P1"] for s in SEEDS]) for at in EPS}
    h1 = P5.tsum(d[PRIMARY])
    h1["signflip_p_exact"] = signflip_exact(d[PRIMARY])
    Dm = np.stack([D[s]["M"][PRIMARY]["per_item"] - D[s]["A"][PRIMARY]["per_item"] for s in SEEDS])
    assert np.allclose(Dm.mean(1), d[PRIMARY])
    h1["crossed95"], h1["layouts_only95"] = boot(Dm)
    h1["decision"] = "supported" if h1["lo"] > 0 or h1["hi"] < 0 else "not supported"
    for v in (0.0, 0.03, 0.05):
        h1[f"excludes_{v}"] = not (h1["lo"] <= v <= h1["hi"])
        h1[f"excludes_-{v}"] = not (h1["lo"] <= -v <= h1["hi"])
    res["H1"] = h1
    res["d_251904"] = P5.tsum(d[251904])
    sec = {}
    for at in EPS:
        sec[at] = {}
        for k in ("q", "r", "entry", "q_feasible", "q_unresolved", "q_impossible", "tau_mean", "remaining_mean"):
            if all(D[s][x][at][k] is not None for s in SEEDS for x in ("A", "M")):
                sec[at][k] = {"A": P5.tsum([D[s]["A"][at][k] for s in SEEDS]), "M": P5.tsum([D[s]["M"][at][k] for s in SEEDS]),
                              "M-A": P5.tsum([D[s]["M"][at][k] - D[s]["A"][at][k] for s in SEEDS])}
        sec[at]["P1"] = {x: P5.tsum([D[s][x][at]["P1"] for s in SEEDS]) for x in ("A", "M")}
        acc, comp = [], []
        for s in SEEDS:
            A0, M1 = D[s]["A"][at], D[s]["M"][at]
            acc.append((M1["q"] - A0["q"]) * (M1["r"] + A0["r"]) / 2)
            comp.append((M1["r"] - A0["r"]) * (M1["q"] + A0["q"]) / 2)
        sec[at]["decomposition"] = {"access_term": P5.tsum(acc), "completion_term": P5.tsum(comp)}
        sec[at]["progress"] = {x: {"reach_module": np.mean([D[s][x][at]["reach_module"] for s in SEEDS], 0).tolist(),
                                   "open_door": np.mean([D[s][x][at]["open_door"] for s in SEEDS], 0).tolist()} for x in ("A", "M")}
    res["secondary"] = sec
    res["allocation"] = {x: {"assisted_step_fraction": P5.tsum([D[s][x]["training"]["assisted_step_fraction"] or 0.0 for s in SEEDS]),
                             "normal_training_success": P5.tsum([D[s][x]["training"]["normal_successes"] / D[s][x]["training"]["normal_episodes"] for s in SEEDS])}
                         for x in ("A", "M")}
    res["cohort"] = {s: D[s]["probe"] for s in SEEDS}
    (OUT / "c5_summary.json").write_text(json.dumps(res, indent=1, default=float))
    with (OUT / "c5_branches.csv").open("w", newline="") as f:
        w = csv.writer(f)
        keys = ("P1", "q", "r", "entry", "q_feasible", "q_unresolved", "q_impossible", "tau_mean", "remaining_mean")
        w.writerow(["seed", "arm", "endpoint", *keys, "assisted_step_fraction"])
        for s in SEEDS:
            for x in ("A", "M"):
                for at in EPS:
                    w.writerow([s, x, at, *[D[s][x][at][k] for k in keys], D[s][x]["training"]["assisted_step_fraction"]])
    md = [f"# Confirmation (seeds 96-115; A = 00 vs M = {arm})", "",
          f"H1 d(501,760) = {h1['mean']:+.4f} [{h1['lo']:+.4f}, {h1['hi']:+.4f}], p {h1['p']:.3g}, {h1['n_positive']}/20 positive; "
          f"sign-flip p {h1['signflip_p_exact']:.3g}; crossed {h1['crossed95']}; layouts-only {h1['layouts_only95']}: **{h1['decision']}**",
          f"d(251,904) = {res['d_251904']['mean']:+.4f} [{res['d_251904']['lo']:+.4f}, {res['d_251904']['hi']:+.4f}] (descriptive)"]
    (OUT / "c5.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
