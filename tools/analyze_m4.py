"""M4 confirmatory analysis (PROTOCOL_FREEZE sections 6-8, 10, 12; Amendments 1 and 2). Written before outcomes.

Usage: .venv/bin/python tools/analyze_m4.py [--batches B ...] [--out reports]

Branches are found by explicit job name m4-K{K}-u{U}-s{S}-{arm tag} in the given batches (default: every batch
under .mae/runs); a job name with a summary in two batches is an error. Endpoints: E250 (tag final_251904) and
E500 (tag final_501760).
Per branch and endpoint, P1, q, C4, R4 and c are recomputed from attempts_<tag>.jsonl and must equal the
summary. A fork is used only if its four arms share the probe's fork hash (section 10); otherwise it is
excluded and reported.

Estimand: per seed, the equal-weight mean over the 4 strata (K x BC checkpoint) of the paired arm contrast;
estimate = mean over seeds.
  - t-interval over seeds (df 4): 95% pointwise, 90% for TOST at +-0.05.
  - crossed bootstrap: 10,000 replicates resampling seeds (5) and conf_final layouts (64 per K) independently,
    each seed's arms and checkpoints kept together; the same indices for both endpoints; percentile; RNG 20261031.
  - Confirmatory family: reset, preservation, combined x {E250, E500} = 6 two-sided t-tests, Holm at 0.05.
    A directional claim needs Holm rejection and the bootstrap 95% interval excluding 0, in the same direction.
  - Verdicts (section 8 with B3): useful benefit (claim > 0, estimate >= 0.05), benefit below the useful
    threshold (claim > 0, estimate < 0.05), harm (claim < 0), practically equivalent (TOST), inconclusive.
    Equivalence can co-occur with a below-threshold benefit; both are listed.
Descriptive (no claims): secondary contrasts, the same contrasts in q, c, C4, R4 and P(success | arrival),
per-stratum contrasts, E500 - E250 changes, D moderation (K=3 minus K=1, mean over checkpoints).
Audit (section 12): fork hashes; independent recomputation of P1/C4/R4/c for 8 branches sampled with
RNG 20261031 (math.comb, written separately from bc2rl.evaluate).
Outputs: m4_branches.csv, m4_contrasts.csv, m4_strata.csv, m4_curves.csv, m4_summary.json.
"""
import argparse
import csv
import json
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
SEEDS = (10, 11, 12, 13, 14)
STRATA = [(K, u) for K in (1, 3) for u in (4000, 16000)]
TAGS = {"00": "00", "10": "10-a0p25", "01": "01-kl0p01", "11": "11-a0p25-kl0p01"}
ENDPOINTS = {"E250": ("final_251904", 251904), "E500": ("final_501760", 501760)}
PRIMARY = ("reset", "preservation", "combined")
CONTRASTS = {"reset": {"10": 1, "00": -1}, "preservation": {"01": 1, "00": -1}, "combined": {"11": 1, "00": -1},
             "interaction": {"11": 1, "01": -1, "10": -1, "00": 1}, "combined_vs_reset": {"11": 1, "10": -1},
             "combined_vs_preservation": {"11": 1, "01": -1}}
METRICS = ("P1", "q", "c", "C4", "R4", "P_success_given_arrival")
T975, T95, DELTA = 2.7764451, 2.1318468, 0.05


def t_cdf4(t):
    """Student t CDF, df 4 (closed form)."""
    return 0.5 + t * (t * t + 6) / (2 * (t * t + 4) ** 1.5)


def t_summary(x):
    x = np.asarray(x, float)
    n, m = len(x), float(np.mean(x))
    assert n == 5, "the t-interval is defined for 5 seeds (df 4)"
    se = float(np.std(x, ddof=1) / np.sqrt(n))
    p = 2 * (1 - t_cdf4(abs(m) / se)) if se > 0 else (0.0 if m != 0 else 1.0)
    return {"estimate": m, "se": se, "t95_lo": m - T975 * se, "t95_hi": m + T975 * se,
            "t90_lo": m - T95 * se, "t90_hi": m + T95 * se, "p": p}


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


def read_attempts(path):
    normal, bank = {}, {}
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        (normal if r["kind"] == "normal" else bank).setdefault(r["item"], []).append(r)
    return normal, bank


def per_item(by):
    items = sorted(by)
    assert items == list(range(len(items)))
    return np.array([np.mean([r["success"] for r in by[i]]) for i in items])


def find_jobs(batches):
    found = {}
    for b in batches:
        for d in sorted((RUNS / b).glob("m4-*")):
            if (d / "summary.json").exists():
                assert d.name not in found, f"duplicate job {d.name}: {found.get(d.name)} and {d}"
                found[d.name] = d
    return found


def audit_metrics(normal, bank):
    """Independent recomputation (section 12)."""
    p1, c4, r4 = [], [], []
    for i in sorted(normal):
        n, z = len(normal[i]), sum(bool(r["success"]) for r in normal[i])
        p1.append(z / n)
        c4.append(1 - comb(n - z, 4) / comb(n, 4))
        r4.append(comb(z, 4) / comb(n, 4))
    c = np.mean([np.mean([bool(r["success"]) for r in v]) for v in bank.values()])
    return {"P1": float(np.mean(p1)), "C4": float(np.mean(c4)), "R4": float(np.mean(r4)), "c": float(c)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batches", nargs="*")
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()
    batches = a.batches or sorted(p.name for p in RUNS.iterdir() if p.is_dir())
    jobs = find_jobs(batches)
    rows, layouts, probes, excluded, curves = [], {}, {}, [], []
    for s in SEEDS:
        for K, u in STRATA:
            pj = jobs.get(f"m4-probe-K{K}-u{u}-s{s}")
            if pj is None:
                excluded.append({"seed": s, "K": K, "bc_update": u, "reason": "probe missing"})
                continue
            ps = json.loads((pj / "summary.json").read_text())
            probes[(s, K, u)] = ps
            for tag, key in (("pi0", "pi0"), ("probe", "probe")):
                curves.append({"seed": s, "K": K, "bc_update": u, "arm": "all", "post_probe_actions": -51200 if key == "pi0" else 0,
                               "point": key, "P1": ps[key]["p"], "q": ps[key]["q"], "c": ps[key]["c"]})
            fork, ok = {}, True
            for arm, t in TAGS.items():
                d = jobs.get(f"m4-K{K}-u{u}-s{s}-{t}")
                if d is None:
                    ok = False
                    excluded.append({"seed": s, "K": K, "bc_update": u, "reason": f"arm {arm} missing"})
                    break
                sm = json.loads((d / "summary.json").read_text())
                assert (sm["arm"], sm["K"], sm["seed"], sm["bc_update"]) == (arm, K, s, u)
                if sm["fork_hash"] != ps["fork_hash"]:
                    ok = False
                    excluded.append({"seed": s, "K": K, "bc_update": u, "reason": f"arm {arm} fork hash mismatch"})
                    break
                fork[arm] = (d, sm)
            if not ok:
                continue
            for arm, (d, sm) in fork.items():
                ev = {e["tag"]: e for e in sm["evals"]}
                for e in sm["evals"]:
                    if not e.get("endpoint"):
                        curves.append({"seed": s, "K": K, "bc_update": u, "arm": arm, "post_probe_actions": e["actions"],
                                       "point": e["tag"], "P1": e["P1"], "q": e["q"], "c": e["c"]})
                for ep, (tag, at) in ENDPOINTS.items():
                    e = ev[tag]
                    assert e["actions"] == at and e.get("endpoint") and e["layouts"] == "eval"
                    normal, bank = read_attempts(d / f"attempts_{tag}.jsonl")
                    p = per_item(normal)
                    assert len(p) == 64 and all(len(v) == 8 for v in normal.values())
                    assert len(bank) == 64 and all(len(v) == 4 for v in bank.values())
                    assert abs(p.mean() - e["P1"]) < 1e-12 and abs(per_item(bank).mean() - e["c"]) < 1e-12
                    layouts[(s, K, u, arm, ep)] = p
                    rows.append({"seed": s, "K": K, "bc_update": u, "arm": arm, "endpoint": ep, "post_probe_actions": at,
                                 "job": f"{d.parent.name}/{d.name}", "fork_hash": sm["fork_hash"],
                                 "state_hash": sm["state_hashes"][str(at)],
                                 **{m: e[m] for m in METRICS},
                                 "n_arrivals": sum(r["arrival"] is not None for v in normal.values() for r in v)})
                    curves.append({"seed": s, "K": K, "bc_update": u, "arm": arm, "post_probe_actions": at, "point": tag,
                                   "P1": e["P1"], "q": e["q"], "c": e["c"]})
    complete = {(s, K, u) for s in SEEDS for K, u in STRATA if (s, K, u, "00", "E250") in layouts}
    val = {(r["seed"], r["K"], r["bc_update"], r["arm"], r["endpoint"], m): r[m] for r in rows for m in METRICS}

    def stratum(s, K, u, ep, name, m="P1"):
        vals = [val.get((s, K, u, arm, ep, m)) for arm in CONTRASTS[name]]
        if any(v is None for v in vals):
            return None
        return sum(w * v for w, v in zip(CONTRASTS[name].values(), vals))

    def seed_level(ep, name, m="P1", strata=STRATA):
        out = []
        for s in SEEDS:
            x = [stratum(s, K, u, ep, name, m) for K, u in strata if (s, K, u) in complete]
            x = [v for v in x if v is not None]
            out.append(float(np.mean(x)) if len(x) == len(strata) else None)
        return out

    full = len(complete) == len(SEEDS) * len(STRATA)
    contr = []
    # bootstrap (P1 only), same indices for both endpoints
    boot = {}
    if full:
        rng = np.random.default_rng(20261031)
        R = 10000
        sidx = rng.integers(0, 5, size=(R, 5))
        lidx = {K: rng.integers(0, 64, size=(R, 64)) for K in (1, 3)}
        for ep in ENDPOINTS:
            for name, w in CONTRASTS.items():
                # per seed x stratum: per-layout contrast vector (64)
                D = np.stack([np.stack([sum(c * layouts[(s, K, u, arm, ep)] for arm, c in w.items()) for K, u in STRATA])
                              for s in SEEDS])                                   # (5, 4, 64)
                strat_means = np.stack([D[:, j, :][:, lidx[K]].mean(-1) for j, (K, u) in enumerate(STRATA)], -1)  # (5, R, 4)
                seed_c = strat_means.mean(-1)                                    # (5, R)
                est = seed_c[sidx, np.arange(R)[:, None]].mean(1)                # (R,)
                boot[(ep, name)] = (float(np.quantile(est, .025)), float(np.quantile(est, .975)))
    for ep in ENDPOINTS:
        for name in CONTRASTS:
            for m in METRICS:
                x = seed_level(ep, name, m)
                if any(v is None for v in x):
                    contr.append({"endpoint": ep, "contrast": name, "metric": m, "n_seeds": sum(v is not None for v in x),
                                  "note": "missing values; not estimated"})
                    continue
                r = {"endpoint": ep, "contrast": name, "metric": m, "n_seeds": 5, **t_summary(x),
                     "seed_values": json.dumps([round(v, 6) for v in x])}
                if m == "P1" and (ep, name) in boot:
                    r["boot95_lo"], r["boot95_hi"] = boot[(ep, name)]
                contr.append(r)
    prim = [r for r in contr if r["metric"] == "P1" and r["contrast"] in PRIMARY and "p" in r]
    if len(prim) == 6:
        for r, adj in zip(prim, holm([r["p"] for r in prim])):
            r["p_holm6"] = adj
            pos = adj < 0.05 and r["boot95_lo"] > 0 and r["estimate"] > 0
            neg = adj < 0.05 and r["boot95_hi"] < 0 and r["estimate"] < 0
            eq = r["t90_lo"] > -DELTA and r["t90_hi"] < DELTA
            v = []
            if pos:
                v.append("useful benefit" if r["estimate"] >= DELTA else "benefit below the useful threshold")
            if neg:
                v.append("harm")
            if eq:
                v.append("practically equivalent")
            r["verdict"] = "; ".join(v) if v else "inconclusive"
            r["pointwise_both_exclude_0"] = (r["t95_lo"] > 0 and r["boot95_lo"] > 0) or (r["t95_hi"] < 0 and r["boot95_hi"] < 0)
    # E500 - E250 changes and D moderation (descriptive)
    extra = []
    for name in CONTRASTS:
        a250, a500 = seed_level("E250", name), seed_level("E500", name)
        if None not in a250 + a500:
            extra.append({"endpoint": "E500-E250", "contrast": name, "metric": "P1", "n_seeds": 5,
                          **t_summary(np.array(a500) - np.array(a250))})
        for ep in ENDPOINTS:
            k3, k1 = seed_level(ep, name, strata=[(3, 4000), (3, 16000)]), seed_level(ep, name, strata=[(1, 4000), (1, 16000)])
            if None not in k3 + k1:
                extra.append({"endpoint": ep, "contrast": f"D_moderation_{name}", "metric": "P1", "n_seeds": 5,
                              **t_summary(np.array(k3) - np.array(k1))})
    strata_rows = []
    for ep in ENDPOINTS:
        for K, u in STRATA:
            for arm in TAGS:
                x = [val.get((s, K, u, arm, ep, "P1")) for s in SEEDS]
                if None not in x:
                    strata_rows.append({"endpoint": ep, "K": K, "bc_update": u, "row": f"arm {arm}", **t_summary(x)})
            for name in CONTRASTS:
                x = [stratum(s, K, u, ep, name) for s in SEEDS]
                if None not in x:
                    strata_rows.append({"endpoint": ep, "K": K, "bc_update": u, "row": name, **t_summary(x)})
    # audit sample
    rng = np.random.default_rng(20261031)
    keys = sorted({(r["seed"], r["K"], r["bc_update"], r["arm"]) for r in rows})
    audit = []
    for i in rng.choice(len(keys), size=min(8, len(keys)), replace=False):
        s, K, u, arm = keys[i]
        d = jobs[f"m4-K{K}-u{u}-s{s}-{TAGS[arm]}"]
        for ep, (tag, _) in ENDPOINTS.items():
            got = audit_metrics(*read_attempts(d / f"attempts_{tag}.jsonl"))
            diff = max(abs(got[m] - val[(s, K, u, arm, ep, m)]) for m in ("P1", "C4", "R4", "c"))
            audit.append({"job": d.name, "endpoint": ep, "max_abs_diff": diff})
    out = Path(a.out)
    for name, rs in (("m4_branches.csv", rows), ("m4_contrasts.csv", contr + extra), ("m4_strata.csv", strata_rows),
                     ("m4_curves.csv", curves)):
        if rs:
            fields = list(dict.fromkeys(k for r in rs for k in r))
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=fields)
                w.writeheader()
                w.writerows(rs)
    summary = {"complete_forks": len(complete), "excluded": excluded, "branches_endpoints": len(rows),
               "audit": audit, "audit_max_abs_diff": max([x["max_abs_diff"] for x in audit] or [None]),
               "primary": [{k: r.get(k) for k in ("endpoint", "contrast", "estimate", "t95_lo", "t95_hi", "boot95_lo",
                                                  "boot95_hi", "t90_lo", "t90_hi", "p", "p_holm6", "verdict")} for r in prim]}
    (out / "m4_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
