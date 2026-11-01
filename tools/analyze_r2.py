"""R2 replication analysis (PROTOCOL_FREEZE Amendment 4). Written and committed before any R2 data exist.

Usage: .venv/bin/python tools/analyze_r2.py [--batches B ...] [--runs .mae/runs] [--out reports/r2] [--check-states]
                                            [--final-incomplete]

Jobs by name: r2-bc-s{S}, r2-probe-K3-u4000-s{S}, r2-K3-u4000-s{S}-{00|01-kl0p01}, seeds 23-42; only jobs with
summary.json count; a name in two batches is an error. A seed enters only if its probe and both branches exist,
both branches carry the probe's fork hash and lineage, and (with --check-states) their saved states match their
hashes; otherwise it is reported as excluded, never replaced.

Blinding rule (owner instruction section 5): the primary statistics are computed only when all 20 seeds are
complete. --final-incomplete computes them on the complete seeds only after the campaign has ended with a
recorded execution failure that the failure policy could not repair; the report then says the design is incomplete.

Per branch and endpoint, P1, q, C4, R4, r = P(success | actual arrival) and the fixed-bank c are recomputed from
attempts_<tag>.jsonl and must equal the summary (tools/analyze_r1.endpoint_record, frozen in Amendment 3); the panel
is r2_final (128 K=3 items x 4 attempts), the same limits for every branch; the bank is r2_bank (64 x 4).

Primary (E500 = final_501760), training seed is the unit (n = 20): d_i = P1(01_i) - P1(00_i).
  One two-sided paired t-test (df n - 1) at 0.05 and the 95% t-interval. Conditional on the frozen panel.
  Decision cells (frozen):
    lower > 0  -> "positive effect supported"; magnitude: lower > 0.05 "exceeds 0.05"; lower > 0.03 "exceeds 0.03";
                  otherwise "positive; not shown to exceed 0.03".
    upper < 0  -> "negative effect supported".
    otherwise  -> not supported; upper < 0.03 "informative: excludes the 0.03 planning effect"; upper < 0.0453
                  "excludes the M4 estimate, not 0.03"; otherwise "inconclusive".
  Uncertainty is also reported relative to 0, 0.03 and 0.05 (one-sided t p-values against each value, labelled
  descriptive; the decision uses the interval only).
  Sensitivity (not the decision rule): crossed seed x layout bootstrap (10,000 replicates, RNG 20261102, seeds and
  r2_final items resampled independently, the same item indices for both arms; percentile 95%), layouts-only
  bootstrap, exact sign-flip test (2^20 patterns).
Descriptive (no claims): E250 with the same statistics; per seed the exact decomposition
  dp = dq (r1 + r0)/2 + dr (q1 + q0)/2 (undefined when an arm has no arrivals; never imputed); by arm q, r, C4, R4,
  mixed-bank c and entry/retrieval/carrying and their change from pi0 and the probe on the same bank states,
  arrival timing and inventory, anchor KL (all, prefix, suffix), training visitation (fraction of suffix steps),
  reward exposure (training access and success rates); curves by role (r2_select: pi0, probe, 126,976, 376,832;
  r2_final: 251,904, 501,760). M4 and R1 values are shown in a separate block; a descriptive R1+R2
  precision-weighted mean (no p-value; adaptive study selection disclosed) is reported separately.
Outputs: r2_branches.csv, r2_seeds.csv, r2_curves.csv, r2_decomposition.csv, r2_summary.json.
"""
import argparse
import csv
import hashlib
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_r1 as A1   # noqa: E402  (frozen record readers: endpoint_record, read_attempts, env_steps)
import r1_stats as R      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = tuple(range(23, 43))
U = 4000
ARMS = {"00": "00", "01": "01-kl0p01"}
EP = A1.EP
CURVE = A1.CURVE
BINS = A1.BINS
PLAN, PRACTICAL, M4_EST = 0.03, 0.05, 0.0453
BOOT_R, BOOT_RNG = 10000, 20261102
ROLES = ("r2_select", "r2_final", "r2_bank", "r2-v1")
REFERENCE = {
    "M4": {"source": "F11 post hoc subgroup, M4 seeds 10-14, conf_final 64 x 8", "estimate": 0.0453,
           "t95": [0.0353, 0.0554], "n": 5, "sd": 0.0081},
    "R1": {"source": "F12 prespecified (Holm-2 not met), R1 seeds 15-22, r1_final 128 x 4", "estimate": 0.040283203125,
           "t95": [0.004181288458096566, 0.07638511779190343], "n": 8, "sd": 0.043183027760271324},
}


def signflip_exact(x):
    """Exact two-sided sign-flip p for mean 0, all 2^n patterns (vectorized in chunks)."""
    x = np.asarray(x, float)
    n, obs = len(x), abs(x.mean())
    total, hits = 2 ** n, 0
    bits = np.arange(n)
    for start in range(0, total, 1 << 16):
        k = np.arange(start, min(total, start + (1 << 16)))
        s = 1 - 2 * ((k[:, None] >> bits) & 1)
        hits += int((np.abs(s @ x) / n >= obs - 1e-15).sum())
    return hits / total


def one_sided_above(t, value):
    """Descriptive one-sided t p-value for H0: mean <= value (df from t)."""
    tt = (t["estimate"] - value) / t["se"] if t["se"] > 0 else np.inf
    two = 1 - R.t_cdf_abs(abs(tt), t["df"])
    return float(two / 2 if tt > 0 else 1 - two / 2)


def decide(t):
    lo, hi = t["t95_lo"], t["t95_hi"]
    if lo > 0:
        mag = ("exceeds 0.05" if lo > PRACTICAL else "exceeds 0.03" if lo > PLAN else "positive; not shown to exceed 0.03")
        return "positive effect supported", mag
    if hi < 0:
        return "negative effect supported", None
    if hi < PLAN:
        return "not supported", "informative: the interval excludes the 0.03 planning effect"
    if hi < M4_EST:
        return "not supported", "the interval excludes the M4 estimate (0.0453) but not 0.03"
    return "not supported", "inconclusive (the interval includes 0 and 0.03)"


def training_diag(d):
    recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
    tr = [r for r in recs if r.get("phase") == "branch"]
    out = A1.training_diag(d)
    mean = lambda k: float(np.mean([r[k] for r in tr if r.get(k) is not None])) if any(r.get(k) is not None for r in tr) else None
    out.update(anchor_kl_prefix_mean=mean("anchor_kl_prefix"), anchor_kl_suffix_mean=mean("anchor_kl_suffix"),
               anchor_penalty_mean=mean("anchor_penalty"), batch_successes_mean=mean("batch_successes"))
    return out


def boot(C, R_=BOOT_R, seed=BOOT_RNG):
    n, m = C.shape
    rng = np.random.default_rng(seed)
    sidx = rng.integers(0, n, size=(R_, n))
    lidx = rng.integers(0, m, size=(R_, m))
    M = np.stack([C[:, li].mean(-1) for li in lidx], 1)
    crossed = M[sidx, np.arange(R_)[:, None]].mean(1)
    q = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    return {"crossed95": q(crossed), "layouts_only95": q(M.mean(0)), "replicates": R_, "rng": seed}


def decomposition(X, seeds, ep):
    rows = []
    for s in seeds:
        a, o = X[(s, "01", ep)], X[(s, "00", ep)]
        dp, dq = a["P1"] - o["P1"], a["q"] - o["q"]
        if a["r"] is None or o["r"] is None:
            rows.append({"endpoint": ep, "seed": s, "q0": o["q"], "q1": a["q"], "r0": o["r"], "r1": a["r"], "dp": dp, "dq": dq,
                         "dr": None, "access_part": None, "completion_part": None, "sum": None,
                         "note": "r undefined (no arrivals) in an arm; not imputed"})
            continue
        dr = a["r"] - o["r"]
        acc, comp = dq * (a["r"] + o["r"]) / 2, dr * (a["q"] + o["q"]) / 2
        assert abs(acc + comp - dp) < 1e-12
        rows.append({"endpoint": ep, "seed": s, "q0": o["q"], "q1": a["q"], "r0": o["r"], "r1": a["r"], "dp": dp, "dq": dq,
                     "dr": dr, "access_part": acc, "completion_part": comp, "sum": acc + comp, "note": ""})
    ok = [r for r in rows if r["sum"] is not None]
    summ = {"n_defined": len(ok), "n_undefined": len(rows) - len(ok)}
    if len(ok) >= 3:
        for k in ("dp", "access_part", "completion_part"):
            v = [r[k] for r in ok]
            summ[k] = {**R.t_test(v), "n_positive": int(sum(x > 0 for x in v))}
    return rows, summ


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--batches", nargs="*")
    ap.add_argument("--out", default=str(ROOT / "reports/r2"))
    ap.add_argument("--check-states", action="store_true")
    ap.add_argument("--final-incomplete", action="store_true")
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    batches = a.batches or sorted(p.name for p in runs.iterdir() if p.is_dir())
    jobs = {}
    for b in batches:
        for d in sorted((runs / b).glob("r2-*")):
            if (d / "summary.json").exists():
                assert d.name not in jobs, f"duplicate job {d.name}: {jobs[d.name]} and {d}"
                jobs[d.name] = d
    X, rows, curves, excluded, problems, steps, probes, train = {}, [], [], [], [], {}, {}, {}
    panel = None
    for s in SEEDS:
        bc = jobs.get(f"r2-bc-s{s}")
        if bc is not None:
            steps[bc.name] = (A1.env_steps(bc), None)
        pj = jobs.get(f"r2-probe-K3-u{U}-s{s}")
        if pj is None:
            excluded.append({"seed": s, "reason": "probe missing"})
            continue
        ps = json.loads((pj / "summary.json").read_text())
        pc = json.loads((pj / "config.resolved.json").read_text())
        if (ps["K"], ps["seed"], ps["bc_update"], pc.get("bc_seed"), pc["diag_role"], pc["eval_role"], pc["bank_role"],
                pc["dataset_id"]) != (3, s, U, s, *ROLES):
            problems.append(f"probe config/lineage {pj.name}")
        if not str(pc["bc_run"]).endswith(f"r2-bc-s{s}"):
            problems.append(f"probe bc_run {pj.name}")
        probes[s] = ps
        steps[pj.name] = (A1.env_steps(pj), sum(ps["actions"].values()))
        for tag in ("pi0", "probe"):
            curves.append({"seed": s, "arm": "shared", "role": "r2_select", "point": tag,
                           "post_probe_actions": -51200 if tag == "pi0" else 0, "P1": ps[tag]["p"], "q": ps[tag]["q"],
                           "c": ps[tag]["c"], **{f"bank_{b}": ps[tag]["bins"][b] for b in BINS}})
        for arm, tag in ARMS.items():
            d = jobs.get(f"r2-K3-u{U}-s{s}-{tag}")
            if d is None:
                excluded.append({"seed": s, "reason": f"branch {arm} missing"})
                continue
            sm = json.loads((d / "summary.json").read_text())
            cf = json.loads((d / "config.resolved.json").read_text())
            if sm["fork_hash"] != ps["fork_hash"] or cf["probe_run"] != str(pj):
                excluded.append({"seed": s, "reason": f"branch {arm} fork hash or lineage mismatch"})
                continue
            want_kl = 0.01 if arm == "01" else 0.0
            if (sm["arm"], sm["K"], sm["seed"], sm["bc_update"], sm["alpha"], sm["kl_coef"], sm.get("anchor_component", "both"),
                    cf["dataset_id"], cf["eval_role"], cf["bank_role"], cf["diag_role"]) != \
                    (arm, 3, s, U, 0.0, want_kl, "both", "r2-v1", "r2_final", "r2_bank", "r2_select"):
                problems.append(f"branch config {d.name}")
            if a.check_states:
                import torch
                sys.path.insert(0, str(ROOT / "src"))
                from bc2rl import ppo as PP
                bad = False
                for at in (251904, 501760):
                    st = torch.load(d / f"state_{at}.pt", map_location="cpu", weights_only=False)
                    if not (PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(at)]):
                        bad = True
                if bad:
                    excluded.append({"seed": s, "reason": f"branch {arm} saved-state hash mismatch"})
                    continue
            steps[d.name] = (A1.env_steps(d), sum(sm.get("actions_this_job", sm["actions"]).values()))
            train[(s, arm)] = training_diag(d)
            for e in sm["evals"]:
                if e["tag"] in CURVE:
                    assert e["layouts"] == "diag" and not e.get("endpoint")
                    curves.append({"seed": s, "arm": arm, "role": "r2_select", "point": e["tag"],
                                   "post_probe_actions": e["actions"], "P1": e["P1"], "q": e["q"], "c": e["c"],
                                   **{f"bank_{b}": e["bins"][b] for b in BINS}})
            for ep, (tag_e, at) in EP.items():
                rec = A1.endpoint_record(d, sm, tag_e)
                if panel is None:
                    panel = rec["limits"]
                if rec["limits"] != panel:
                    problems.append(f"panel differs {d.name} {ep}")
                X[(s, arm, ep)] = rec
                rows.append({"seed": s, "arm": arm, "endpoint": ep, "post_probe_actions": at,
                             "job": f"{d.parent.name}/{d.name}", "fork_hash": sm["fork_hash"],
                             "state_hash": sm["state_hashes"].get(str(at)),
                             **{m: rec[m] for m in ("P1", "q", "r", "C4", "R4", "c", "n_arrivals",
                                                    "arrival_tau_mean", "arrival_remaining_mean")},
                             **{f"bank_{b}": rec["bins"][b] for b in BINS}})
                curves.append({"seed": s, "arm": arm, "role": "r2_final", "point": tag_e, "post_probe_actions": at,
                               "P1": rec["P1"], "q": rec["q"], "c": rec["c"], **{f"bank_{b}": rec["bins"][b] for b in BINS}})
    seeds = [s for s in SEEDS if all((s, arm, "E500") in X for arm in ARMS) and not any(x["seed"] == s for x in excluded)]
    complete = len(seeds) == len(SEEDS)
    res = {"seeds_used": seeds, "n": len(seeds), "complete_design": complete, "excluded": excluded,
           "problems": problems, "references_not_pooled": REFERENCE}
    blinded = not complete and not a.final_incomplete
    res["primary_computed"] = not blinded
    seed_rows, dec_rows = [], []
    for ep in EP:
        P = lambda s, arm: X[(s, arm, ep)]["P1"]
        d = np.array([P(s, "01") - P(s, "00") for s in seeds])
        if not blinded:
            for i, s in enumerate(seeds):
                seed_rows.append({"endpoint": ep, "seed": s, "P1_00": P(s, "00"), "P1_01": P(s, "01"), "d": d[i]})
        if blinded or len(seeds) < 3:
            continue
        C = np.stack([X[(s, "01", ep)]["p"] for s in seeds]) - np.stack([X[(s, "00", ep)]["p"] for s in seeds])
        t = R.t_test(d)
        blk = {**t, "signflip_p_exact": signflip_exact(d), **boot(C), "n_positive": int((d > 0).sum()),
               "baseline_00_mean": float(np.mean([P(s, "00") for s in seeds])),
               "one_sided_p_above": {str(v): one_sided_above(t, v) for v in (0.0, PLAN, PRACTICAL)}}
        blk["relative_to_baseline"] = blk["estimate"] / blk["baseline_00_mean"] if blk["baseline_00_mean"] else None
        blk["decision"], blk["magnitude"] = decide(t)
        blk["status"] = "primary (single two-sided paired t-test, alpha 0.05)" if ep == "E500" else \
            "descriptive checkpoint (no claims)"
        blk["bootstrap_agrees_on_sign"] = (blk["crossed95"][0] > 0) == (t["t95_lo"] > 0) and (blk["crossed95"][1] < 0) == (t["t95_hi"] < 0)
        res[ep] = blk
        dr, ds = decomposition(X, seeds, ep)
        dec_rows += dr
        res[f"{ep}_decomposition"] = ds
    if not blinded and "E500" in res and len(seeds) >= 3:
        # descriptive synthesis of the two prespecified studies (R1, R2); M4 excluded (it selected the condition)
        r1 = REFERENCE["R1"]
        se1 = r1["sd"] / sqrt(r1["n"])
        se2 = res["E500"]["se"]
        w1, w2 = 1 / se1 ** 2, 1 / se2 ** 2
        m = (w1 * r1["estimate"] + w2 * res["E500"]["estimate"]) / (w1 + w2)
        se = sqrt(1 / (w1 + w2))
        res["synthesis_descriptive"] = {
            "studies": ["R1", "R2"], "precision_weighted_mean": m, "approx95": [m - 1.96 * se, m + 1.96 * se],
            "note": "Descriptive only. Not a confirmatory test and no p-value. R1 and R2 were run because M4's post hoc "
                    "subgroup looked positive (adaptive study selection); M4 is excluded. Normal approximation."}
    # secondary (descriptive)
    sec = {}
    for ep in (EP if not blinded else ()):        # arm means would reveal the effect: none while blinded
        for arm in ARMS:
            recs = [X[(s, arm, ep)] for s in seeds]
            if not recs:
                continue
            g = {m: float(np.mean([r[m] for r in recs])) for m in ("P1", "q", "C4", "R4", "c")}
            rs = [r["r"] for r in recs if r["r"] is not None]
            g["r_mean_defined"], g["r_defined_n"] = (float(np.mean(rs)) if rs else None), len(rs)
            g["bins"] = {b: float(np.mean([r["bins"][b] for r in recs])) for b in BINS}
            for k in ("arrival_tau_mean", "arrival_remaining_mean"):
                v = [r[k] for r in recs if r[k] is not None]
                g[k] = float(np.mean(v)) if v else None
            inv = {}
            for r in recs:
                for k, v in r["inventory"].items():
                    inv[k] = inv.get(k, 0) + v
            g["inventory"], g["zero_arrival_branches"] = inv, sum(r["n_arrivals"] == 0 for r in recs)
            for ref in ("pi0", "probe"):
                g[f"c_change_from_{ref}"] = float(np.mean([X[(s, arm, ep)]["c"] - probes[s][ref]["c"] for s in seeds]))
                g[f"bins_change_from_{ref}"] = {b: float(np.mean([X[(s, arm, ep)]["bins"][b] - probes[s][ref]["bins"][b]
                                                                   for s in seeds])) for b in BINS}
            if ep == "E500":
                keys = train[(seeds[0], arm)]
                g["training"] = {k: (float(np.mean([train[(s, arm)][k] for s in seeds if train[(s, arm)][k] is not None]))
                                     if any(train[(s, arm)][k] is not None for s in seeds) else None) for k in keys}
            sec[f"{ep}/{arm}"] = g
        if not blinded and len(seeds) >= 3:
            diffs = {}
            for m in ("P1", "q", "C4", "R4", "c") + tuple(f"bin_{b}" for b in BINS):
                get = (lambda r, m=m: r["bins"][m[4:]]) if m.startswith("bin_") else (lambda r, m=m: r[m])
                diffs[m] = R.t_test([get(X[(s, "01", ep)]) - get(X[(s, "00", ep)]) for s in seeds])
            rx = [X[(s, "01", ep)]["r"] - X[(s, "00", ep)]["r"] for s in seeds
                  if X[(s, "01", ep)]["r"] is not None and X[(s, "00", ep)]["r"] is not None]
            diffs["r_defined_pairs"] = {"n": len(rx), **(R.t_test(rx) if len(rx) >= 3 else {})}
            sec[f"{ep}/diff_01_minus_00"] = diffs
    res["secondary"] = sec
    res["probes"] = {str(s): {k: probes[s][k] for k in ("pi0", "probe", "fork_hash")} for s in probes}
    res["counter_check"] = {k: {"env_steps": v[0], "summary_actions": v[1],
                                "equal": None if v[0] is None or v[1] is None else v[0] == v[1]} for k, v in steps.items()}
    res["bc_checkpoint_sha256_16"] = {s: hashlib.sha256((jobs[f"r2-bc-s{s}"] / f"actor_u{U}.pt").read_bytes()).hexdigest()[:16]
                                      for s in SEEDS if f"r2-bc-s{s}" in jobs and (jobs[f"r2-bc-s{s}"] / f"actor_u{U}.pt").exists()}
    res["state_hashes_checked"] = a.check_states
    (out / "r2_summary.json").write_text(json.dumps(res, indent=1, default=float))
    for name, data in (("r2_branches.csv", rows if not blinded else []), ("r2_seeds.csv", seed_rows),
                       ("r2_curves.csv", curves if not blinded else []), ("r2_decomposition.csv", dec_rows)):
        if data:
            keys = list(dict.fromkeys(k for r in data for k in r))
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(data)
    brief = {k: res[k] for k in ("seeds_used", "complete_design", "excluded", "problems", "primary_computed")}
    if "E500" in res:
        brief["E500"] = {k: res["E500"][k] for k in ("estimate", "t95_lo", "t95_hi", "p", "crossed95", "signflip_p_exact",
                                                      "decision", "magnitude")}
    print(json.dumps(brief, indent=1, default=float))
    return res


if __name__ == "__main__":
    main()
