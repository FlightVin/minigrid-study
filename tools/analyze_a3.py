"""A3 anchor-allocation study analysis (PROTOCOL_FREEZE Amendment 5). Written and tested before any A3 data.

Usage: .venv/bin/python tools/analyze_a3.py [--runs .mae/runs] [--out reports/a3] [--check-states] [--final-incomplete]

Jobs by name: a3-bc-s{S}, a3-probe-K3-u4000-s{S}, a3-K3-u4000-s{S}-{00|01p|01s|01|01w}, seeds 43-66. Only jobs with
summary.json count; a name in two batches is an error. A seed enters only if its probe and all five branches exist,
every branch carries the probe's fork hash and lineage and its frozen arm identity (base and effective
coefficients, component), and (with --check-states) the saved states match their hashes; otherwise it is reported
as excluded, never replaced.

Arms: A = 00 (ordinary PPO), B = 01p (0.0025 E_prefix KL), C = 01s (0.0075 E_suffix KL), D = 01 (original mixed,
0.0025 E_prefix + 0.0075 E_suffix), E = 01w (0.001875 E_prefix + 0.005625 E_suffix; E's total scalar coefficient
equals C's, its gradient strength need not).

Blinding: no contrast, arm mean or per-seed outcome is computed until all 24 seeds are complete (--final-incomplete
only after a recorded, unrepairable execution failure; the report then says the design is incomplete).

Per branch and endpoint, P1, q, C4, R4, r = P(success | actual arrival) and fixed-bank c (with entry, retrieval,
carrying) are recomputed from attempts_<tag>.jsonl and must equal the summary (tools/analyze_r1.endpoint_record);
panel a3_final (128 K=3 items x 4 attempts, the same limits for every branch); bank a3_bank (64 x 4).

Confirmatory (E250 = final_251904; training seed is the unit, n = 24):
  H1: d_i = P1(C_i) - P1(A_i). One two-sided paired t-test at 0.05 and the 95% t-interval.
      "supported" iff the interval lies above 0 (equivalently p < 0.05 with a positive estimate);
      "negative effect supported" iff it lies below 0; otherwise "not supported".
  Gate: only if H1 is supported, H2a C - D and H2b C - E are tested at E250 (two-sided paired t, Holm over the two;
      each supported iff its Holm-adjusted p < 0.05; direction from the estimate). Otherwise both are descriptive and
      reported without a decision. The hierarchy is fixed.
  Sensitivity for H1 (not the decision rule): crossed seed x layout bootstrap (10,000, RNG 20261103), layouts-only
  bootstrap, exact sign-flip over 2^24 patterns.
Secondary (prespecified, descriptive; 95% t-intervals, no multiplicity claim), at E250 and E500:
  B-A, C-A, D-A, E-A, D-C, C-D, C-E, interaction D - B - C + A; the exact access/completion decomposition of each
  arm-minus-A contrast; per arm q, r, C4, R4, c and bins and their change from pi0 and the probe on the same bank
  states; arrival timing and inventory; training anchor KL (all, prefix, suffix), applied penalty, update size
  (actor parameter-change norm; KL between successive policies on fixed prefix and suffix anchor rows), PPO
  approx-KL, entropy, training visitation and reward exposure.
Outputs: a3_branches.csv, a3_seeds.csv, a3_contrasts.csv, a3_decomposition.csv, a3_summary.json.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_r1 as A1   # noqa: E402  (frozen record readers)
import r1_stats as R      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = tuple(range(43, 67))
U = 4000
ARMS = {"A": "00", "B": "01p", "C": "01s", "D": "01", "E": "01w"}
IDENT = {"A": (0.0, "both", (0.0, 0.0)), "B": (0.01, "prefix", (0.0025, 0.0)), "C": (0.01, "suffix", (0.0, 0.0075)),
         "D": (0.01, "both", (0.0025, 0.0075)), "E": (0.0075, "both", (0.001875, 0.005625))}
EP = {"E250": ("final_251904", 251904), "E500": ("final_501760", 501760)}
BINS = A1.BINS
BOOT_R, BOOT_RNG = 10000, 20261103
ROLES = ("a3_select", "a3_final", "a3_bank", "r3-v1")
CONTRASTS = {"B-A": {"B": 1, "A": -1}, "C-A": {"C": 1, "A": -1}, "D-A": {"D": 1, "A": -1}, "E-A": {"E": 1, "A": -1},
             "D-C": {"D": 1, "C": -1}, "C-D": {"C": 1, "D": -1}, "C-E": {"C": 1, "E": -1},
             "interaction D-B-C+A": {"D": 1, "B": -1, "C": -1, "A": 1}}
TRAIN_KEYS = ("anchor_kl", "anchor_kl_prefix", "anchor_kl_suffix", "anchor_penalty", "update_kl_prefix", "update_kl_suffix",
              "actor_update_norm", "approx_kl", "clipfrac", "entropy", "grad_norm_actor", "frac_suffix_steps", "batch_successes")


def signflip_exact(x):
    """Exact two-sided sign-flip p for mean 0 over all 2^n patterns (chunked)."""
    x = np.asarray(x, float)
    n, obs = len(x), abs(x.mean())
    total, hits, bits = 2 ** n, 0, np.arange(n)
    for start in range(0, total, 1 << 16):
        k = np.arange(start, min(total, start + (1 << 16)))
        s = 1 - 2 * ((k[:, None] >> bits) & 1)
        hits += int((np.abs(s @ x) / n >= obs - 1e-15).sum())
    return hits / total


def boot(C, R_=BOOT_R, seed=BOOT_RNG):
    """C: (n_seeds, n_items) per-item contrasts; seeds and items resampled independently (crossed)."""
    n, m = C.shape
    rng = np.random.default_rng(seed)
    sidx = rng.integers(0, n, size=(R_, n))
    lidx = rng.integers(0, m, size=(R_, m))
    M = np.stack([C[:, li].mean(-1) for li in lidx], 1)
    crossed = M[sidx, np.arange(R_)[:, None]].mean(1)
    q = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    return {"crossed95": q(crossed), "layouts_only95": q(M.mean(0)), "replicates": R_, "rng": seed}


def decide_primary(t):
    if t["t95_lo"] > 0:
        return "supported"
    if t["t95_hi"] < 0:
        return "negative effect supported"
    return "not supported"


def gate(primary_decision, t_cd, t_ce):
    """Fixed hierarchy: H2a (C - D) and H2b (C - E) are tested, with Holm over the two, only if H1 is supported."""
    if primary_decision != "supported":
        return {"tested": False, "reason": "H1 not supported; H2a and H2b are descriptive only",
                "H2a_C-D": {**t_cd, "decision": None}, "H2b_C-E": {**t_ce, "decision": None}}
    adj = R.holm([t_cd["p"], t_ce["p"]])
    out = {"tested": True, "reason": "H1 supported; Holm over H2a and H2b"}
    for name, t, pa in (("H2a_C-D", t_cd, adj[0]), ("H2b_C-E", t_ce, adj[1])):
        dec = ("C higher" if t["estimate"] > 0 else "C lower") if pa < 0.05 else "not supported"
        out[name] = {**t, "p_holm": pa, "decision": dec}
    return out


def contrast(X, s, ep, w, get):
    vals = [(get(X[(s, arm, ep)]), c) for arm, c in w.items()]
    return None if any(v is None for v, _ in vals) else float(sum(v * c for v, c in vals))


def decomposition(X, seeds, ep, arm):
    rows = []
    for s in seeds:
        a, o = X[(s, arm, ep)], X[(s, "A", ep)]
        dp, dq = a["P1"] - o["P1"], a["q"] - o["q"]
        base = {"endpoint": ep, "contrast": f"{arm}-A", "seed": s, "q_A": o["q"], "q_arm": a["q"], "r_A": o["r"],
                "r_arm": a["r"], "dp": dp, "dq": dq}
        if a["r"] is None or o["r"] is None:
            rows.append({**base, "dr": None, "access_part": None, "completion_part": None,
                         "note": "r undefined (no arrivals) in an arm; not imputed"})
            continue
        dr = a["r"] - o["r"]
        acc, comp = dq * (a["r"] + o["r"]) / 2, dr * (a["q"] + o["q"]) / 2
        assert abs(acc + comp - dp) < 1e-12
        rows.append({**base, "dr": dr, "access_part": acc, "completion_part": comp, "note": ""})
    ok = [r for r in rows if r["access_part"] is not None]
    summ = {"n_defined": len(ok), "n_undefined": len(rows) - len(ok)}
    if len(ok) >= 3:
        for k in ("dp", "access_part", "completion_part"):
            v = [r[k] for r in ok]
            summ[k] = {**R.t_test(v), "n_positive": int(sum(x > 0 for x in v))}
    return rows, summ


def training_diag(d):
    recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
    tr = [r for r in recs if r.get("phase") == "branch"]
    out = A1.training_diag(d)
    for k in TRAIN_KEYS:
        v = [r[k] for r in tr if r.get(k) is not None]
        out[f"{k}_mean"] = float(np.mean(v)) if v else None
        half = [r[k] for r in tr if r.get(k) is not None and r["actions"] <= 251904]
        out[f"{k}_mean_to_251904"] = float(np.mean(half)) if half else None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--out", default=str(ROOT / "reports/a3"))
    ap.add_argument("--check-states", action="store_true")
    ap.add_argument("--final-incomplete", action="store_true")
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for d in sorted(runs.glob("*/a3-*")):
        if (d / "summary.json").exists():
            assert d.name not in jobs, f"duplicate job {d.name}: {jobs[d.name]} and {d}"
            jobs[d.name] = d
    X, rows, excluded, problems, steps, probes, train = {}, [], [], [], {}, {}, {}
    panel = None
    for s in SEEDS:
        bc = jobs.get(f"a3-bc-s{s}")
        if bc is not None:
            steps[bc.name] = (A1.env_steps(bc), None)
        pj = jobs.get(f"a3-probe-K3-u{U}-s{s}")
        if pj is None:
            excluded.append({"seed": s, "reason": "probe missing"})
            continue
        ps = json.loads((pj / "summary.json").read_text())
        pc = json.loads((pj / "config.resolved.json").read_text())
        if (ps["K"], ps["seed"], ps["bc_update"], pc.get("bc_seed"), pc["diag_role"], pc["eval_role"], pc["bank_role"],
                pc["dataset_id"]) != (3, s, U, s, *ROLES):
            problems.append(f"probe config/lineage {pj.name}")
        if not str(pc["bc_run"]).endswith(f"a3-bc-s{s}"):
            problems.append(f"probe bc_run {pj.name}")
        probes[s] = ps
        steps[pj.name] = (A1.env_steps(pj), sum(ps["actions"].values()))
        bad_seed = False
        for arm, tag in ARMS.items():
            d = jobs.get(f"a3-K3-u{U}-s{s}-{tag}")
            if d is None:
                excluded.append({"seed": s, "reason": f"branch {arm} ({tag}) missing"})
                bad_seed = True
                continue
            sm = json.loads((d / "summary.json").read_text())
            cf = json.loads((d / "config.resolved.json").read_text())
            if sm["fork_hash"] != ps["fork_hash"] or cf["probe_run"] != str(pj):
                excluded.append({"seed": s, "reason": f"branch {arm} fork hash or lineage mismatch"})
                bad_seed = True
                continue
            base, comp, eff = IDENT[arm]
            got_eff = tuple(sm.get("kl_effective_prefix_suffix") or (np.nan, np.nan))
            if (sm["arm"], sm["K"], sm["seed"], sm["bc_update"], sm["alpha"], sm["anchor_component"], cf["dataset_id"],
                    cf["eval_role"], cf["bank_role"], cf["diag_role"]) != (tag, 3, s, U, 0.0, comp, *ROLES[3:], *ROLES[1:3], ROLES[0]) \
                    or abs(sm["kl_coef"] - base) > 1e-15 or not all(abs(x - y) <= 1e-15 for x, y in zip(got_eff, eff)):
                problems.append(f"branch identity {d.name}")
            if a.check_states:
                import torch
                sys.path.insert(0, str(ROOT / "src"))
                from bc2rl import ppo as PP
                for at in (251904, 501760):
                    st = torch.load(d / f"state_{at}.pt", map_location="cpu", weights_only=False)
                    if not (PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(at)]):
                        excluded.append({"seed": s, "reason": f"branch {arm} saved-state hash mismatch at {at}"})
                        bad_seed = True
            steps[d.name] = (A1.env_steps(d), sum(sm.get("actions_this_job", sm["actions"]).values()))
            train[(s, arm)] = training_diag(d)
            for ep, (tag_e, at) in EP.items():
                rec = A1.endpoint_record(d, sm, tag_e)
                if panel is None:
                    panel = rec["limits"]
                if rec["limits"] != panel:
                    problems.append(f"panel differs {d.name} {ep}")
                X[(s, arm, ep)] = rec
                rows.append({"seed": s, "arm": arm, "arm_tag": tag, "endpoint": ep, "post_probe_actions": at,
                             "job": f"{d.parent.name}/{d.name}", "fork_hash": sm["fork_hash"],
                             "state_hash": sm["state_hashes"].get(str(at)),
                             **{m: rec[m] for m in ("P1", "q", "r", "C4", "R4", "c", "n_arrivals",
                                                    "arrival_tau_mean", "arrival_remaining_mean")},
                             **{f"bank_{b}": rec["bins"][b] for b in BINS}})
        if bad_seed:
            continue
    excluded_seeds = {x["seed"] for x in excluded}
    seeds = [s for s in SEEDS if s not in excluded_seeds and all((s, arm, ep) in X for arm in ARMS for ep in EP)]
    complete = len(seeds) == len(SEEDS)
    blinded = not complete and not a.final_incomplete
    res = {"seeds_used": seeds, "n": len(seeds), "complete_design": complete, "excluded": excluded,
           "problems": problems, "primary_computed": not blinded, "state_hashes_checked": a.check_states}
    seed_rows, con_rows, dec_rows = [], [], []
    if not blinded and len(seeds) >= 3:
        P = lambda s, arm, ep: X[(s, arm, ep)]["P1"]
        d = np.array([P(s, "C", "E250") - P(s, "A", "E250") for s in seeds])
        t = R.t_test(d)
        C = np.stack([X[(s, "C", "E250")]["p"] for s in seeds]) - np.stack([X[(s, "A", "E250")]["p"] for s in seeds])
        h1 = {**t, "decision": decide_primary(t), "n_positive": int((d > 0).sum()), "signflip_p_exact": signflip_exact(d),
              **boot(C), "status": "confirmatory primary H1 (C - A at 251,904; single two-sided paired t-test, alpha 0.05)"}
        h1["bootstrap_agrees"] = (h1["crossed95"][0] > 0) == (t["t95_lo"] > 0) and (h1["crossed95"][1] < 0) == (t["t95_hi"] < 0)
        res["H1"] = h1
        cd = R.t_test([P(s, "C", "E250") - P(s, "D", "E250") for s in seeds])
        ce = R.t_test([P(s, "C", "E250") - P(s, "E", "E250") for s in seeds])
        res["gate"] = gate(h1["decision"], cd, ce)
        sec = {}
        for ep in EP:
            for s in seeds:
                seed_rows.append({"endpoint": ep, "seed": s, **{f"P1_{arm}": P(s, arm, ep) for arm in ARMS}})
            blk = {}
            getters = {m: (lambda r, m=m: r[m]) for m in ("P1", "q", "r", "C4", "R4", "c")}
            getters.update({f"bin_{b}": (lambda r, b=b: r["bins"][b]) for b in BINS})
            for name, w in CONTRASTS.items():
                cb = {}
                for m, get in getters.items():
                    v = [contrast(X, s, ep, w, get) for s in seeds]
                    vv = [x for x in v if x is not None]
                    cb[m] = {**(R.t_test(vv) if len(vv) >= 3 else {"n": len(vv)}),
                             "n_positive": int(sum(x > 0 for x in vv)), "n_undefined": len(v) - len(vv)}
                    if m == "P1":
                        for s, x in zip(seeds, v):
                            con_rows.append({"endpoint": ep, "contrast": name, "seed": s, "d_P1": x})
                blk[name] = cb
            for arm in ("B", "C", "D", "E"):
                dr, ds = decomposition(X, seeds, ep, arm)
                dec_rows += dr
                blk[f"decomposition_{arm}-A"] = ds
            sec[ep] = blk
        res["secondary_contrasts"] = sec
        arms = {}
        for ep in EP:
            for arm in ARMS:
                recs = [X[(s, arm, ep)] for s in seeds]
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
                    keys = list(train[(seeds[0], arm)])
                    g["training"] = {k: (float(np.mean([train[(s, arm)][k] for s in seeds if train[(s, arm)][k] is not None]))
                                         if any(train[(s, arm)][k] is not None for s in seeds) else None) for k in keys}
                arms[f"{ep}/{arm}"] = g
        res["arms"] = arms
    res["probes"] = {str(s): {k: probes[s][k] for k in ("pi0", "probe", "fork_hash")} for s in probes}
    res["counter_check"] = {k: {"env_steps": v[0], "summary_actions": v[1],
                                "equal": None if v[0] is None or v[1] is None else v[0] == v[1]} for k, v in steps.items()}
    res["bc_checkpoint_sha256_16"] = {s: hashlib.sha256((jobs[f"a3-bc-s{s}"] / f"actor_u{U}.pt").read_bytes()).hexdigest()[:16]
                                      for s in SEEDS if f"a3-bc-s{s}" in jobs and (jobs[f"a3-bc-s{s}"] / f"actor_u{U}.pt").exists()}
    (out / "a3_summary.json").write_text(json.dumps(res, indent=1, default=float))
    for name, data in (("a3_branches.csv", rows if not blinded else []), ("a3_seeds.csv", seed_rows),
                       ("a3_contrasts.csv", con_rows), ("a3_decomposition.csv", dec_rows)):
        if data:
            keys = list(dict.fromkeys(k for r in data for k in r))
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(data)
    brief = {k: res[k] for k in ("seeds_used", "complete_design", "excluded", "problems", "primary_computed")}
    if "H1" in res:
        brief["H1"] = {k: res["H1"][k] for k in ("estimate", "t95_lo", "t95_hi", "p", "crossed95", "signflip_p_exact", "decision")}
        brief["gate_tested"] = res["gate"]["tested"]
    print(json.dumps(brief, indent=1, default=float))
    return res


if __name__ == "__main__":
    main()
