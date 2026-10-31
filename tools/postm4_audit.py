"""Post-M4 audit and interpretation analyses (owner instruction 2026-10-31, after M4). No environment actions.

Usage: .venv/bin/python tools/postm4_audit.py [--out reports/postm4] [--skip-state-hashes]

Reads only raw M4 artifacts (attempt files, summaries, configs, saved states) by explicit job name in the five
M4 seed batches, plus dev-campaign diagnostics for the bank comparison. It does not reuse tools/analyze_m4.py:
the primary contrasts are recomputed independently. The frozen primary analysis is not modified.

Outputs (reports/postm4/):
  primary.csv            six primary contrasts: estimate, t-interval, TOST statistics/p, Holm-6, three bootstraps
  strata.csv             every arm-vs-00 contrast per stratum and endpoint (paired seed differences), t, exact
                         sign-flip p, Holm over 24 and over the 48 contrasts examined in F10, BH over 48
  strata_seeds.csv       the per-seed paired differences behind strata.csv (plot input)
  k3early_subgroup.json  preservation K=3/4k audit (per seed, crossed bootstrap, per-layout, leave-one-out)
  checkpoint_interaction.csv  post hoc (effect at 4k) - (effect at 16k) within K, and E500 - E250 per stratum
  decomposition.csv      p = q r per branch; within seed x stratum delta-p = dq * rbar + dr * qbar
  bank_m4.csv            planner entry/retrieval/carrying/mixed c and own-arrival r per branch and endpoint
  bank_dev.csv           development E3b: planner bins vs policy-generated arrival banks (M3 K=3/16k, seeds 0-1)
  secondary.csv          C4, R4, q, c, P(success|arrival) contrasts (pooled over strata), pointwise
  selection.csv          hindsight per-condition best arm vs best fixed arm; leave-one-seed-out (same conditions)
  training.csv           learning rate, clipping activity, policy change (anchor KL), learning per branch
  execution.json         lineage, hashes, split separation, bank composition, recomputation, accounting
"""
import argparse
import csv
import hashlib
import json
from itertools import product
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
BATCHES = {10: "20261031T144443-65814", 11: "20261031T154838-81881", 12: "20261031T165349-92672",
           13: "20261031T175829-2090", 14: "20261031T190210-20242"}
SEEDS = tuple(BATCHES)
STRATA = [(1, 4000), (1, 16000), (3, 4000), (3, 16000)]
ARMTAG = {"00": "00", "10": "10-a0p25", "01": "01-kl0p01", "11": "11-a0p25-kl0p01"}
EP = {"E250": ("final_251904", 251904), "E500": ("final_501760", 501760)}
CON = {"reset": "10", "preservation": "01", "combined": "11"}
DELTA = 0.05
T975, T95 = 2.7764451, 2.1318468


def tcdf(t):
    """Student t CDF with df 4 (closed form)."""
    return 0.5 + t * (t * t + 6) / (2 * (t * t + 4) ** 1.5)


def tstats(x):
    x = np.asarray(x, float)
    m, se = float(x.mean()), float(x.std(ddof=1) / np.sqrt(len(x)))
    assert len(x) == 5
    t = m / se if se > 0 else np.inf * np.sign(m)
    p = float(2 * (1 - tcdf(abs(t)))) if se > 0 else float(m == 0)
    return {"estimate": m, "se": se, "t": t, "p": p, "t95_lo": m - T975 * se, "t95_hi": m + T975 * se}


def tost(m, se):
    tl, tu = (m + DELTA) / se, (m - DELTA) / se
    pl, pu = 1 - tcdf(tl), tcdf(tu)
    return {"tost_t_lower": tl, "tost_p_lower": pl, "tost_t_upper": tu, "tost_p_upper": pu,
            "tost_p": max(pl, pu), "t90_lo": m - T95 * se, "t90_hi": m + T95 * se}


def signflip(x):
    x = np.asarray(x, float)
    obs = abs(x.mean())
    sums = [abs(np.mean(x * np.array(s))) for s in product((1, -1), repeat=len(x))]
    return float(np.mean([v >= obs - 1e-15 for v in sums]))


def holm(ps):
    order, adj, run = sorted(range(len(ps)), key=lambda i: ps[i]), [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


def bh(ps):
    n = len(ps)
    order = sorted(range(n), key=lambda i: ps[i])
    adj, run = [0.0] * n, 1.0
    for r in range(n - 1, -1, -1):
        i = order[r]
        run = min(run, ps[i] * n / (r + 1))
        adj[i] = run
    return adj


def jdir(s, K, u, arm):
    return RUNS / BATCHES[s] / f"m4-K{K}-u{u}-s{s}-{ARMTAG[arm]}"


def read_attempts(path):
    normal, bank = {}, {}
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        (normal if r["kind"] == "normal" else bank).setdefault(r["item"], []).append(r)
    return normal, bank


def load():
    """D[(s,K,u,arm,ep)] = per-layout arrays from raw attempts."""
    D, S = {}, {}
    for s in SEEDS:
        for K, u in STRATA:
            for arm in ARMTAG:
                d = jdir(s, K, u, arm)
                sm = json.loads((d / "summary.json").read_text())
                S[(s, K, u, arm)] = sm
                for ep, (tag, _) in EP.items():
                    normal, bank = read_attempts(d / f"attempts_{tag}.jsonl")
                    items = sorted(normal)
                    assert items == list(range(64)) and sorted(bank) == list(range(64))
                    z = np.array([sum(r["success"] for r in normal[i]) for i in items], float)
                    n = np.array([len(normal[i]) for i in items], float)
                    a = np.array([sum(r["arrival"] is not None for r in normal[i]) for i in items], float)
                    assert (n == 8).all() and all(len(bank[i]) == 4 for i in bank)
                    # success implies arrival; accessed == arrival recorded
                    for i in items:
                        for r in normal[i]:
                            assert (not r["success"]) or r["arrival"] is not None
                            assert bool(r["accessed"]) == (r["arrival"] is not None)
                    D[(s, K, u, arm, ep)] = {
                        "z": z, "n": n, "a": a, "p": z / n,
                        "limit": [normal[i][0]["limit"] for i in items],
                        "rem": [r["arrival"]["remaining"] for i in items for r in normal[i] if r["arrival"]],
                        "tau": [r["arrival"]["tau"] for i in items for r in normal[i] if r["arrival"]],
                        "carry": [tuple(map(str, r["arrival"]["carrying"])) if r["arrival"]["carrying"] else ()
                                  for i in items for r in normal[i] if r["arrival"]],
                        "bank": {i: [r["success"] for r in bank[i]] for i in bank},
                        "bank_bin": {i: bank[i][0]["bin"] for i in bank},
                    }
    return D, S


def seed_contrast(D, arm, ep, strata=STRATA):
    return np.array([np.mean([(D[(s, K, u, arm, ep)]["p"] - D[(s, K, u, "00", ep)]["p"]).mean() for K, u in strata])
                     for s in SEEDS])


def primary(D, out):
    rows = []
    R = 10000
    for ep in EP:
        for name, arm in CON.items():
            x = seed_contrast(D, arm, ep)
            r = {"endpoint": ep, "contrast": name, "seed_values": json.dumps([round(v, 7) for v in x]), **tstats(x)}
            r.update(tost(r["estimate"], r["se"]))
            # per seed x stratum x layout contrast, (5, 4, 64)
            C = np.stack([np.stack([D[(s, K, u, arm, ep)]["p"] - D[(s, K, u, "00", ep)]["p"] for K, u in STRATA])
                          for s in SEEDS])
            # (a) frozen scheme (independent K=1 / K=3 layout indices; same RNG order as tools/analyze_m4.py)
            rng = np.random.default_rng(20261031)
            sidx = rng.integers(0, 5, size=(R, 5))
            lidx = {K: rng.integers(0, 64, size=(R, 64)) for K in (1, 3)}
            est = boot(C, sidx, [lidx[K] for K, u in STRATA])
            r["boot_frozen_lo"], r["boot_frozen_hi"] = np.quantile(est, [.025, .975])
            # (b) matched across K: one layout index set for both K (conf_final item i shares gen_seed across K)
            rng = np.random.default_rng(20261101)
            sidx = rng.integers(0, 5, size=(R, 5))
            li = rng.integers(0, 64, size=(R, 64))
            est = boot(C, sidx, [li] * 4)
            r["boot_matched_lo"], r["boot_matched_hi"] = np.quantile(est, [.025, .975])
            # (c) layouts only (seeds fixed): the layout-sampling component alone
            est = boot(C, np.tile(np.arange(5), (R, 1)), [li] * 4)
            r["boot_layouts_only_lo"], r["boot_layouts_only_hi"] = np.quantile(est, [.025, .975])
            rows.append(r)
    for r, adj in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm6"] = adj
    w = csv.DictWriter(open(out / "primary.csv", "w", newline=""), fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return rows


def boot(C, sidx, lidx_per_stratum):
    """C (5 seeds, 4 strata, 64 layouts) -> R bootstrap estimates of the equal-weight seed mean."""
    strat = np.stack([C[:, j, :][:, li].mean(-1) for j, li in enumerate(lidx_per_stratum)], -1)  # (5, R, 4)
    seed_c = strat.mean(-1)                                                                        # (5, R)
    return seed_c[sidx, np.arange(sidx.shape[0])[:, None]].mean(1)


def strata(D, out):
    rows, seeds_rows = [], []
    for ep in EP:
        for K, u in STRATA:
            for name, arm in CON.items():
                x = np.array([(D[(s, K, u, arm, ep)]["p"] - D[(s, K, u, "00", ep)]["p"]).mean() for s in SEEDS])
                base = np.array([D[(s, K, u, "00", ep)]["p"].mean() for s in SEEDS])
                r = {"endpoint": ep, "K": K, "bc_update": u, "contrast": name, "baseline_mean": base.mean(),
                     **tstats(x), "signflip_p": signflip(x), "n_positive": int((x > 0).sum()),
                     "relative_to_baseline": x.mean() / base.mean() if base.mean() > 0 else None}
                rows.append(r)
                for s, v, b0 in zip(SEEDS, x, base):
                    seeds_rows.append({"endpoint": ep, "K": K, "bc_update": u, "contrast": name, "seed": s,
                                       "baseline": b0, "diff": v})
    for r, a in zip(rows, holm([r["p"] for r in rows])):
        r["p_holm24"] = a
    # family examined in F10 / m4_strata.csv: 6 contrasts x 4 strata x 2 endpoints = 48
    extra = []
    W = {"interaction": {"11": 1, "01": -1, "10": -1, "00": 1}, "combined_vs_reset": {"11": 1, "10": -1},
         "combined_vs_preservation": {"11": 1, "01": -1}}
    for ep in EP:
        for K, u in STRATA:
            for name, w in W.items():
                x = np.array([sum(c * D[(s, K, u, a, ep)]["p"].mean() for a, c in w.items()) for s in SEEDS])
                extra.append(tstats(x)["p"])
    allp = [r["p"] for r in rows] + extra
    h48, b48 = holm(allp), bh(allp)
    for r, a, b in zip(rows, h48, b48):
        r["p_holm48"], r["q_bh48"] = a, b
    for name, rs in (("strata.csv", rows), ("strata_seeds.csv", seeds_rows)):
        w = csv.DictWriter(open(out / name, "w", newline=""), fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
    return rows


def subgroup(D, S, out, K=3, u=4000, arm="01", ep="E500"):
    res = {"stratum": f"K={K}, BC {u}", "contrast": "preservation 01-00", "endpoint": ep, "per_seed": []}
    for s in SEEDS:
        b, t = D[(s, K, u, "00", ep)], D[(s, K, u, arm, ep)]
        res["per_seed"].append({
            "seed": s, "job_00": str(jdir(s, K, u, "00").relative_to(RUNS)), "job_01": str(jdir(s, K, u, arm).relative_to(RUNS)),
            "fork_hash_match": S[(s, K, u, "00")]["fork_hash"] == S[(s, K, u, arm)]["fork_hash"],
            "attempts_00": int(b["n"].sum()), "attempts_01": int(t["n"].sum()),
            "P1_00": b["p"].mean(), "P1_01": t["p"].mean(), "diff": t["p"].mean() - b["p"].mean(),
            "q_00": b["a"].sum() / b["n"].sum(), "q_01": t["a"].sum() / t["n"].sum(),
            "arrivals_00": int(b["a"].sum()), "arrivals_01": int(t["a"].sum()),
            "zero_arrival_layouts_00": int((b["a"] == 0).sum()), "zero_arrival_layouts_01": int((t["a"] == 0).sum()),
            "successes_00": int(b["z"].sum()), "successes_01": int(t["z"].sum())})
    x = np.array([r["diff"] for r in res["per_seed"]])
    base = np.mean([r["P1_00"] for r in res["per_seed"]])
    res["t"] = tstats(x)
    res["signflip_p"] = signflip(x)
    res["baseline_P1"], res["relative_change"] = base, x.mean() / base
    C = np.stack([D[(s, K, u, arm, ep)]["p"] - D[(s, K, u, "00", ep)]["p"] for s in SEEDS])   # (5, 64)
    rng = np.random.default_rng(20261102)
    R = 10000
    si, li = rng.integers(0, 5, (R, 5)), rng.integers(0, 64, (R, 64))
    est = C[:, li].mean(-1)[si, np.arange(R)[:, None]].mean(1)
    res["boot_crossed_95"] = list(np.quantile(est, [.025, .975]))
    est_l = C[:, li].mean(-1).mean(0)
    res["boot_layouts_only_95"] = list(np.quantile(est_l, [.025, .975]))
    est_s = C.mean(1)[si].mean(1)
    res["boot_seeds_only_95"] = list(np.quantile(est_s, [.025, .975]))
    per_layout = C.mean(0)
    order = np.argsort(-per_layout)
    total = per_layout.sum()
    res["per_layout"] = {
        "positive": int((per_layout > 0).sum()), "negative": int((per_layout < 0).sum()), "zero": int((per_layout == 0).sum()),
        "layouts_any_success_00": int((np.stack([D[(s, K, u, "00", ep)]["z"] for s in SEEDS]).sum(0) > 0).sum()),
        "layouts_any_success_01": int((np.stack([D[(s, K, u, arm, ep)]["z"] for s in SEEDS]).sum(0) > 0).sum()),
        "share_of_net_gain_top5": float(per_layout[order[:5]].sum() / total) if total else None,
        "share_of_net_gain_top10": float(per_layout[order[:10]].sum() / total) if total else None,
        "top10": [{"item": int(i), "mean_diff": float(per_layout[i]),
                   "seeds_positive": int((C[:, i] > 0).sum()), "seeds_negative": int((C[:, i] < 0).sum())} for i in order[:10]],
        "bottom5": [{"item": int(i), "mean_diff": float(per_layout[i])} for i in order[-5:]],
        "values": [float(v) for v in per_layout]}
    res["leave_one_seed_out"] = [{"dropped": s, "mean": float(np.delete(x, k).mean())} for k, s in enumerate(SEEDS)]
    groups = []
    for g in range(8):
        keep = np.array([i // 8 != g for i in range(64)])
        xs = C[:, keep].mean(1)
        groups.append({"dropped_items": f"{8 * g}-{8 * g + 7}", **{k: v for k, v in tstats(xs).items() if k in ("estimate", "t95_lo", "t95_hi")}})
    res["leave_one_layout_group_out"] = groups
    # mechanism: arrival timing / states, fixed-entry-bank completion, longitudinal fixed states
    def q(v, p):
        return float(np.quantile(v, p)) if len(v) else None
    mech = {}
    for a in ("00", arm):
        rem = sum((D[(s, K, u, a, ep)]["rem"] for s in SEEDS), [])
        tau = sum((D[(s, K, u, a, ep)]["tau"] for s in SEEDS), [])
        mech[a] = {"arrivals": len(rem), "remaining_q10_50_90": [q(rem, .1), q(rem, .5), q(rem, .9)],
                   "tau_q10_50_90": [q(tau, .1), q(tau, .5), q(tau, .9)],
                   "r_pooled": sum(D[(s, K, u, a, ep)]["z"].sum() for s in SEEDS) / max(1, len(rem))}
    res["arrival"] = mech
    res["fixed_bank_longitudinal"] = longitudinal(S, K, u)
    (out / "k3early_subgroup.json").write_text(json.dumps(res, indent=1, default=float))
    return res


def longitudinal(S, K, u):
    """Fixed conf_bank bins (same states throughout) and conf_select normal starts (same layouts throughout)."""
    rows = []
    for s in SEEDS:
        ps = json.loads((RUNS / BATCHES[s] / f"m4-probe-K{K}-u{u}-s{s}" / "summary.json").read_text())
        for pt in ("pi0", "probe"):
            rows.append({"seed": s, "arm": "all", "point": pt, "select_P1": ps[pt]["p"], **{f"bank_{b}": ps[pt]["bins"][b] for b in ("entry", "retrieval", "carrying")},
                         "bank_attempts_per_state": 4})
        for arm in ("00", "01"):
            for e in S[(s, K, u, arm)]["evals"]:
                rows.append({"seed": s, "arm": arm, "point": e["tag"],
                             "select_P1": e["P1"] if e.get("layouts") == "diag" else None,
                             **{f"bank_{b}": e["bins"][b] for b in ("entry", "retrieval", "carrying")},
                             "bank_attempts_per_state": e["bank_attempts"]})
    agg = {}
    for r in rows:
        k = (r["arm"], r["point"])
        agg.setdefault(k, []).append(r)
    return [{"arm": a, "point": p, "n": len(v),
             "select_P1_mean": float(np.mean([x["select_P1"] for x in v])) if v[0]["select_P1"] is not None else None,
             **{f"bank_{b}_mean": float(np.mean([x[f"bank_{b}"] for x in v])) for b in ("entry", "retrieval", "carrying")},
             "bank_attempts_per_state": v[0]["bank_attempts_per_state"]} for (a, p), v in agg.items()]


def checkpoint_interaction(D, out):
    rows = []
    for ep in EP:
        for K in (1, 3):
            for name, arm in CON.items():
                e4 = np.array([(D[(s, K, 4000, arm, ep)]["p"] - D[(s, K, 4000, "00", ep)]["p"]).mean() for s in SEEDS])
                e16 = np.array([(D[(s, K, 16000, arm, ep)]["p"] - D[(s, K, 16000, "00", ep)]["p"]).mean() for s in SEEDS])
                rows.append({"analysis": "checkpoint x intervention (post hoc)", "endpoint": ep, "K": K, "contrast": name,
                             "effect_4k": e4.mean(), "effect_16k": e16.mean(), **tstats(e4 - e16)})
    for K, u in STRATA:
        for name, arm in CON.items():
            d = np.array([(D[(s, K, u, arm, "E500")]["p"] - D[(s, K, u, "00", "E500")]["p"]).mean()
                          - (D[(s, K, u, arm, "E250")]["p"] - D[(s, K, u, "00", "E250")]["p"]).mean() for s in SEEDS])
            rows.append({"analysis": "E500 - E250 of the stratum contrast (descriptive)", "endpoint": "E500-E250", "K": K,
                         "bc_update": u, "contrast": name, **tstats(d)})
    fields = list(dict.fromkeys(k for r in rows for k in r))
    w = csv.DictWriter(open(out / "checkpoint_interaction.csv", "w", newline=""), fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return rows


def decomposition(D, out):
    rows, comp = [], []
    for ep in EP:
        for s in SEEDS:
            for K, u in STRATA:
                for arm in ARMTAG:
                    d = D[(s, K, u, arm, ep)]
                    p, qv = d["z"].sum() / d["n"].sum(), d["a"].sum() / d["n"].sum()
                    r = d["z"].sum() / d["a"].sum() if d["a"].sum() else None
                    assert abs(p - d["p"].mean()) < 1e-12 and (r is None and p == 0 or abs(p - qv * r) < 1e-12)
                    rows.append({"endpoint": ep, "seed": s, "K": K, "bc_update": u, "arm": arm, "p": p, "q": qv, "r": r})
    idx = {(x["endpoint"], x["seed"], x["K"], x["bc_update"], x["arm"]): x for x in rows}
    for ep in EP:
        for name, arm in CON.items():
            for s in SEEDS:
                for K, u in STRATA:
                    a0, a1 = idx[(ep, s, K, u, "00")], idx[(ep, s, K, u, arm)]
                    dp = a1["p"] - a0["p"]
                    if a0["r"] is None or a1["r"] is None:
                        comp.append({"endpoint": ep, "contrast": name, "seed": s, "K": K, "bc_update": u, "dp": dp,
                                     "access_part": None, "completion_part": None, "unsupported": dp})
                    else:
                        ap = (a1["q"] - a0["q"]) * (a1["r"] + a0["r"]) / 2
                        cp = (a1["r"] - a0["r"]) * (a1["q"] + a0["q"]) / 2
                        assert abs(ap + cp - dp) < 1e-12
                        comp.append({"endpoint": ep, "contrast": name, "seed": s, "K": K, "bc_update": u, "dp": dp,
                                     "access_part": ap, "completion_part": cp, "unsupported": 0.0})
    for name, rs in (("decomposition_branches.csv", rows), ("decomposition.csv", comp)):
        w = csv.DictWriter(open(out / name, "w", newline=""), fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
    return rows, comp


def bank_m4(D, out):
    rows = []
    for (s, K, u, arm, ep), d in D.items():
        bins = {b: [np.mean(d["bank"][i]) for i in d["bank"] if d["bank_bin"][i] == b] for b in ("entry", "retrieval", "carrying")}
        mixed = np.mean([np.mean(v) for v in d["bank"].values()])
        rows.append({"endpoint": ep, "seed": s, "K": K, "bc_update": u, "arm": arm,
                     "c_entry": np.mean(bins["entry"]), "c_retrieval": np.mean(bins["retrieval"]),
                     "c_carrying": np.mean(bins["carrying"]), "c_mixed": mixed,
                     "n_entry": len(bins["entry"]), "n_retrieval": len(bins["retrieval"]), "n_carrying": len(bins["carrying"]),
                     "r_own_arrival": d["z"].sum() / d["a"].sum() if d["a"].sum() else None, "arrivals": int(d["a"].sum()),
                     "arrival_remaining_q50": float(np.median(d["rem"])) if d["rem"] else None,
                     "arrival_remaining_q10": float(np.quantile(d["rem"], .1)) if d["rem"] else None})
    w = csv.DictWriter(open(out / "bank_m4.csv", "w", newline=""), fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return rows


def bank_dev(out):
    """E3b (dev): M3 K=3/16k seeds 0-1; planner dev_bank bins vs arrival banks from pi0 / 00 / 11 on dev_eval."""
    M3, M3B, E3 = "20261030T214937-19577", "20261030T232600-96083", "20261031T050016-80407"
    orig = {"00": f"{M3}/m3-K3-u16000-s{{s}}-00", "01": f"{M3}/m3-K3-u16000-s{{s}}-01-kl0p01",
            "10": f"{M3}/m3-K3-u16000-s{{s}}-10-a0p25", "11": f"{M3B}/m3-K3-u16000-s{{s}}-11-a0p25-kl0p01"}
    bank = json.loads((ROOT / "data/dev-v2/bank_competence_dev_bank.json").read_text())["3"]
    lay = json.loads((ROOT / "data/dev-v2/layouts.json").read_text())
    rows, banks_meta = [], []
    for s in (0, 1):
        ad = RUNS / E3 / f"e3-arrival-K3-u16000-s{s}"
        ar = json.loads((ad / "summary.json").read_text())
        ps = json.loads((RUNS / M3 / f"m3-probe-K3-u16000-s{s}" / "summary.json").read_text())
        planner = {"pi0": ps["pi0"], "probe": ps["probe"]}
        for arm, rel in orig.items():
            sm = json.loads((RUNS / rel.format(s=s) / "summary.json").read_text())
            planner[arm] = {"c": sm["final"]["c"], "bins": sm["final"]["bins"]}
        states = [json.loads(l) for l in (ad / "arrival_banks.jsonl").read_text().splitlines()]
        for src in ("pi0", "00", "11"):
            st = [x for x in states if x["source"] == src]
            rem = [x["remaining"] for x in st]
            banks_meta.append({"seed": s, "source_bank": src, "states": len(st), "layouts": len({x["item"] for x in st}),
                               "remaining_q10_50_90": [float(np.quantile(rem, p)) for p in (.1, .5, .9)],
                               "max_states_one_layout": max(np.bincount([x["item"] for x in st]))})
        for pol in ("pi0", "probe", "00", "01", "10", "11"):
            pl = planner[pol]
            row = {"seed": s, "policy": pol, "c_mixed": pl["c"], "c_entry": pl["bins"]["entry"],
                   "c_retrieval": pl["bins"]["retrieval"], "c_carrying": pl["bins"]["carrying"]}
            for src in ("pi0", "00", "11"):
                e = ar["eval"].get(f"{src}|{pol}")
                row[f"arrival_{src}"] = e["P1"] if e else None
                row[f"arrival_{src}_rem_ge80"] = e["P1_rem_ge80"] if e else None
                row[f"arrival_{src}_rem_lt80"] = e["P1_rem_lt80"] if e else None
            own = {"00": "00", "11": "11", "pi0": "pi0"}.get(pol)
            row["arrival_own"] = row[f"arrival_{own}"] if own else None
            row["gap_mixed_minus_own"] = pl["c"] - row["arrival_own"] if own else None
            row["gap_entry_minus_own"] = pl["bins"]["entry"] - row["arrival_own"] if own else None
            rows.append(row)
    planner_rem = sorted({b["remaining"] for b in bank if b["bin"] == "entry"})
    meta = {"planner_bank": {"layout_role": "dev_bank (64 layouts per K)", "states": len(bank),
                             "bins": {b: sum(x["bin"] == b for x in bank) for b in ("entry", "retrieval", "carrying")},
                             "entry_remaining_values": planner_rem,
                             "remaining_q10_50_90_all": [float(np.quantile([x["remaining"] for x in bank], p)) for p in (.1, .5, .9)]},
            "arrival_banks": banks_meta, "arrival_layout_role": "dev_eval (32 layouts per K)",
            "note": "planner bank weights: equal per state, 32 entry / 16 retrieval / 16 carrying"}
    w = csv.DictWriter(open(out / "bank_dev.csv", "w", newline=""), fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    (out / "bank_dev_meta.json").write_text(json.dumps(meta, indent=1, default=int))
    return rows, meta


def secondary(D, S, out):
    rows = []
    for ep, (tag, at) in EP.items():
        ev = {k: next(e for e in sm["evals"] if e["tag"] == tag) for k, sm in S.items()}
        for name, arm in CON.items():
            for m in ("C4", "R4", "q", "c", "P_success_given_arrival", "P1"):
                xs = []
                for s in SEEDS:
                    v = [(ev[(s, K, u, arm)][m], ev[(s, K, u, "00")][m]) for K, u in STRATA]
                    xs.append(None if any(a is None or b is None for a, b in v) else np.mean([a - b for a, b in v]))
                if None in xs:
                    rows.append({"endpoint": ep, "contrast": name, "metric": m, "note": "undefined in some stratum (no arrivals)"})
                    continue
                rows.append({"endpoint": ep, "contrast": name, "metric": m, **tstats(xs)})
    # independent C4/R4 recomputation check
    for (s, K, u, arm, ep), d in D.items():
        n, z = 8, d["z"].astype(int)
        c4 = np.mean([1 - comb(n - k, 4) / comb(n, 4) for k in z])
        r4 = np.mean([comb(k, 4) / comb(n, 4) for k in z])
        e = next(x for x in S[(s, K, u, arm)]["evals"] if x["tag"] == EP[ep][0])
        assert abs(c4 - e["C4"]) < 1e-12 and abs(r4 - e["R4"]) < 1e-12
    fields = list(dict.fromkeys(k for r in rows for k in r))
    w = csv.DictWriter(open(out / "secondary.csv", "w", newline=""), fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return rows


def selection(D, out):
    rows = []
    for ep in EP:
        M = {(K, u, a): np.mean([D[(s, K, u, a, ep)]["p"].mean() for s in SEEDS]) for K, u in STRATA for a in ARMTAG}
        fixed = {a: np.mean([M[(K, u, a)] for K, u in STRATA]) for a in ARMTAG}
        best = {(K, u): max(ARMTAG, key=lambda a: M[(K, u, a)]) for K, u in STRATA}
        oracle = np.mean([M[(K, u, best[(K, u)])] for K, u in STRATA])
        bf = max(fixed, key=fixed.get)
        rows.append({"endpoint": ep, "analysis": "hindsight in-sample reference", "per_condition_best": oracle,
                     "best_fixed_arm": bf, "best_fixed": fixed[bf], "gap": oracle - fixed[bf],
                     "chosen": json.dumps({f"K{K}/{u}": best[(K, u)] for K, u in STRATA}),
                     "fixed_arm_means": json.dumps({a: round(v, 6) for a, v in fixed.items()})})
        # leave-one-seed-out (new training replicates of the SAME conditions; not RQ2)
        g_cond, g_fix, g_00 = [], [], []
        for k, s in enumerate(SEEDS):
            tr = [x for x in SEEDS if x != s]
            Mt = {(K, u, a): np.mean([D[(t, K, u, a, ep)]["p"].mean() for t in tr]) for K, u in STRATA for a in ARMTAG}
            ch = {(K, u): max(ARMTAG, key=lambda a: Mt[(K, u, a)]) for K, u in STRATA}
            fx = max(ARMTAG, key=lambda a: np.mean([Mt[(K, u, a)] for K, u in STRATA]))
            g_cond.append(np.mean([D[(s, K, u, ch[(K, u)], ep)]["p"].mean() for K, u in STRATA]))
            g_fix.append(np.mean([D[(s, K, u, fx, ep)]["p"].mean() for K, u in STRATA]))
            g_00.append(np.mean([D[(s, K, u, "00", ep)]["p"].mean() for K, u in STRATA]))
        d1 = np.array(g_cond) - np.array(g_00)
        d2 = np.array(g_cond) - np.array(g_fix)
        rows.append({"endpoint": ep, "analysis": "leave-one-seed-out condition-identity rule (same conditions)",
                     "per_condition_best": float(np.mean(g_cond)), "best_fixed": float(np.mean(g_fix)),
                     "gap": float(d2.mean()), "chosen": "", "fixed_arm_means": "",
                     "vs_ordinary_mean": float(d1.mean()), "vs_ordinary_t95": json.dumps([tstats(d1)["t95_lo"], tstats(d1)["t95_hi"]])})
    fields = list(dict.fromkeys(k for r in rows for k in r))
    w = csv.DictWriter(open(out / "selection.csv", "w", newline=""), fieldnames=fields)
    w.writeheader()
    w.writerows(rows)
    return rows


def training(S, out):
    rows = []
    for (s, K, u, arm), sm in S.items():
        d = jdir(s, K, u, arm)
        cfg = json.loads((d / "config.resolved.json").read_text())
        upd = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if '"phase": "branch"' in l]
        g = np.array([x["grad_norm_actor"] for x in upd])
        ev = {e["tag"]: e for e in sm["evals"]}
        rows.append({"seed": s, "K": K, "bc_update": u, "arm": arm, "actor_lr": cfg["actor_lr"], "max_grad_norm": cfg["max_grad_norm"],
                     "updates": len(upd), "frac_updates_grad_above_clip": float((g > cfg["max_grad_norm"]).mean()),
                     "grad_norm_median": float(np.median(g)), "clipfrac_mean": float(np.mean([x["clipfrac"] for x in upd])),
                     "approx_kl_mean": float(np.mean([x["approx_kl"] for x in upd])),
                     "anchor_kl_first": upd[0]["anchor_kl"], "anchor_kl_last": upd[-1]["anchor_kl"],
                     "entropy_first": upd[0]["entropy"], "entropy_last": upd[-1]["entropy"],
                     "P1_E250": ev["final_251904"]["P1"], "P1_E500": ev["final_501760"]["P1"],
                     "select_P1_126976": ev["curve_126976"]["P1"], "select_P1_376832": ev["curve_376832"]["P1"]})
    w = csv.DictWriter(open(out / "training.csv", "w", newline=""), fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return rows


def execution(D, S, out, check_states):
    import torch
    import sys
    sys.path.insert(0, str(ROOT / "src"))
    from bc2rl import ppo as PP
    ex = {"forks": 0, "branch_endpoint_records": 0, "problems": []}
    lay = json.loads((ROOT / "data/conf-v1/layouts.json").read_text())
    limits = {role: {K: [it["layout"]["limit"] for it in lay[role] if it["layout"]["K"] == K] for K in (1, 3)}
              for role in ("conf_select", "conf_final")}
    bc_hash = {}
    for s in SEEDS:
        bdir = RUNS / BATCHES[s] / f"m4-bc-s{s}"
        bc_hash[s] = {u: hashlib.sha256((bdir / f"actor_u{u}.pt").read_bytes()).hexdigest()[:16] for u in (4000, 16000)}
        for K, u in STRATA:
            pdir = RUNS / BATCHES[s] / f"m4-probe-K{K}-u{u}-s{s}"
            pc = json.loads((pdir / "config.resolved.json").read_text())
            ps = json.loads((pdir / "summary.json").read_text())
            if (pc["bc_run"], pc["bc_update"], pc.get("bc_seed"), pc["diag_role"], pc["eval_role"]) != (f"@/m4-bc-s{s}", u, s, "conf_select", "conf_final"):
                ex["problems"].append(f"probe lineage {pdir.name}")
            fork = torch.load(pdir / "fork.pt", map_location="cpu", weights_only=False)
            if PP.state_hash(fork) != ps["fork_hash"]:
                ex["problems"].append(f"fork hash {pdir.name}")
            # pi0 / probe normal starts were on conf_select: limits per item must match conf_select, not conf_final
            for tag in ("pi0", "probe"):
                n, _ = read_attempts(pdir / f"attempts_{tag}.jsonl")
                lim = [n[i][0]["limit"] for i in sorted(n)]
                if lim != limits["conf_select"][K]:
                    ex["problems"].append(f"{pdir.name} {tag} not on conf_select")
            ex["forks"] += 1
            for arm in ARMTAG:
                d = jdir(s, K, u, arm)
                sm, cfg = S[(s, K, u, arm)], json.loads((d / "config.resolved.json").read_text())
                if sm["fork_hash"] != ps["fork_hash"] or cfg["probe_run"] != str(pdir):
                    ex["problems"].append(f"branch lineage {d.name}")
                for e in sm["evals"]:
                    n, _ = read_attempts(d / f"attempts_{e['tag']}.jsonl")
                    lim = [n[i][0]["limit"] for i in sorted(n)]
                    want = limits["conf_select" if e["layouts"] == "diag" else "conf_final"][K]
                    if lim != want or (e["layouts"] == "diag") == e["endpoint"]:
                        ex["problems"].append(f"{d.name} {e['tag']} layout role")
                for ep, (tag, at) in EP.items():
                    ex["branch_endpoint_records"] += 1
                    if check_states:
                        saved = torch.load(d / f"state_{at}.pt", map_location="cpu", weights_only=False)
                        if not (PP.state_hash(saved["state"]) == saved["hash"] == sm["state_hashes"][str(at)]):
                            ex["problems"].append(f"state hash {d.name} {at}")
                    dd = D[(s, K, u, arm, ep)]
                    e = next(x for x in sm["evals"] if x["tag"] == tag)
                    pa = dd["z"].sum() / dd["a"].sum() if dd["a"].sum() else None
                    if abs(dd["p"].mean() - e["P1"]) > 1e-12 or abs(dd["a"].sum() / 512 - e["q"]) > 1e-12 \
                            or (pa is None) != (e["P_success_given_arrival"] is None) or (pa is not None and abs(pa - e["P_success_given_arrival"]) > 1e-12) \
                            or abs(np.mean([np.mean(v) for v in dd["bank"].values()]) - e["c"]) > 1e-12:
                        ex["problems"].append(f"metric mismatch {d.name} {ep}")
    ex["bc_checkpoint_sha256_16"] = bc_hash
    ex["state_hashes_checked"] = check_states
    # split separation among confirmation roles (independent of tools/data_gate.py)
    sig = lambda it: (it["layout"]["K"], it["layout"]["gen_seed"])
    suf = lambda it: (tuple(it["layout"]["delivery_pos"]), tuple(it["layout"]["target_pos"]), tuple(it["layout"]["distractor_pos"]), it["layout"]["gap_row"])
    roles = ("conf_select", "conf_bank", "conf_final")
    other = [r for r in lay if r not in roles]
    ov = {}
    for i, a in enumerate(roles):
        for b in roles[i + 1:] + tuple(other):
            A_, B_ = lay[a], lay[b]
            ov[f"{a}|{b}"] = {"structure_hash": len({x["structure_hash"] for x in A_} & {x["structure_hash"] for x in B_}),
                              "gen_seed": len({x["layout"]["gen_seed"] for x in A_} & {x["layout"]["gen_seed"] for x in B_}),
                              "suffix_signature": len({suf(x) for x in A_} & {suf(x) for x in B_})}
    ex["role_overlap"] = ov
    bank = json.loads((ROOT / "data/conf-v1/bank_competence_conf_bank.json").read_text())
    ex["conf_bank"] = {K: {"bins": {b: sum(x["bin"] == b for x in v) for b in ("entry", "retrieval", "carrying")},
                           "layouts": len({x["snapshot"]["layout"]["gen_seed"] for x in v})} for K, v in bank.items()}
    ex["conf_bank_matched_across_K"] = [x["snapshot"]["layout"]["gen_seed"] for x in bank["1"]] == [x["snapshot"]["layout"]["gen_seed"] for x in bank["3"]] \
        and [x["bin"] for x in bank["1"]] == [x["bin"] for x in bank["3"]]
    cf = lay["conf_final"]
    ex["conf_final_matched_across_K"] = [x["layout"]["gen_seed"] for x in cf if x["layout"]["K"] == 1] == [x["layout"]["gen_seed"] for x in cf if x["layout"]["K"] == 3]
    ex["zero_arrival_branch_endpoints"] = sum(1 for d in D.values() if d["a"].sum() == 0)
    ex["zero_arrival_layout_cells"] = int(sum((d["a"] == 0).sum() for d in D.values()))
    (out / "execution.json").write_text(json.dumps(ex, indent=1, default=int))
    return ex


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports/postm4"))
    ap.add_argument("--skip-state-hashes", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    D, S = load()
    pr = primary(D, out)
    st = strata(D, out)
    sg = subgroup(D, S, out)
    checkpoint_interaction(D, out)
    decomposition(D, out)
    bank_m4(D, out)
    bank_dev(out)
    secondary(D, S, out)
    selection(D, out)
    training(S, out)
    ex = execution(D, S, out, not a.skip_state_hashes)
    print(json.dumps({"primary": [(r["endpoint"], r["contrast"], round(r["estimate"], 5), round(r["tost_p"], 5)) for r in pr],
                      "subgroup": sg["t"], "problems": ex["problems"]}, indent=1, default=float))


if __name__ == "__main__":
    main()
