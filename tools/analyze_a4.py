"""A4 analysis (owner instruction 2026-11-01c, sections 4-8; PROTOCOL_FREEZE Amendment 6). Frozen before any A4 run.

Usage: .venv/bin/python tools/analyze_a4.py [--runs .mae/runs] [--out reports/a4] [--check-states] [--final-incomplete]

Design: K=3, BC rho 0.2 / 8,000 updates, seeds 70-89 (n = 20, all kept), arms A = 00 (ordinary PPO) and
C = 01s (suffix-only preservation, effective 0.0075), forked from the same post-probe state per seed. Endpoints
E250 = 251,904, E500 = 501,760 and E1M = 1,001,472 post-probe actions (primary). Normal starts: a4_final, 256 K=3
layouts x 2 attempts; entry bank: a4_bank, 128 planner entry states x 2; arrival bank: the fixed actual-arrival bank x 2.
Treatment outcomes stay blinded until all 20 seeds are complete (unless --final-incomplete, never used for decisions).

Lineage: a branch is the job a4-K3-s<S>-<arm> plus any resume jobs -r1, -r2, ... (after a battery pause). Each
resume job must start from a state file of an earlier job in the chain with the recorded hash. The evaluation at an
endpoint is taken from the job whose training covered it: start_j < at <= start_{j+1}. Interrupted records are kept
and reported, never used for outcomes.

Confirmatory (training seed = unit, n = 20, two-sided, alpha 0.05):
  H1: d_i = P1(C_i, E1M) - P1(A_i, E1M); paired t-test and 95% t-interval. "supported" iff the interval excludes 0
      (direction from the estimate).
  H2 (gated): only if H1 is supported, g_i = d_i(E1M) - d_i(E250); paired t-test, two-sided, alpha 0.05. An increasing
      benefit is "supported" only if H1 is supported with a positive estimate and H2 is supported with a positive
      estimate. Otherwise the change across time is descriptive.
Sensitivity for H1 (not decision rules): crossed seed x layout bootstrap (seeds and the 256 layouts resampled with
replacement, layouts common to all seeds and both arms, 10,000 replicates, RNG 20261104); layouts-only bootstrap
(conditional on the 20 seeds); exact sign-flip over 2^20 patterns (exchangeable signs of d_i under H0).
Uncertainty is reported relative to 0, 0.03 and 0.05 (whether the 95% interval excludes each value).
Secondary (descriptive, 95% t over seeds): d at E250 and E500; arm means at each endpoint; per endpoint p, q,
r = P(success | actual arrival) (missing when no arrival), planner-entry competence, actual-arrival-bank competence,
their changes from pi0 and the post-probe policy on the same states, arrival timing (tau, remaining time) and
inventory at arrival; per-seed decomposition dp = dq (r1 + r0)/2 + dr (q1 + q0)/2 (missing when r is undefined; not
mediation; bank competence is never substituted for r); training anchor KL (all, prefix, suffix), applied penalty,
update size, PPO approx-KL, entropy, suffix visitation and successful-return exposure by interval (to E250,
E250-E500, E500-E1M). Outcome patterns are classified descriptively (section 8 list), never as a unique explanation.
Cohort (not a treatment outcome; reported from the start): per seed BC-evaluation q, entry competence and P1 at
8,000 (bc_val / dev_bank, as in calibration) against the calibration targets; pi0 and post-probe q (a4_select), entry
competence (a4_bank) and arrival-bank competence.
Outputs: a4_summary.json, a4_branches.csv, a4_seeds.csv, a4_cohort.csv, a4_decomposition.csv.
"""
import argparse
import csv
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = tuple(range(70, 90))
ARMS = {"A": "00", "C": "01s"}
IDENT = {"A": (0.0, "both", (0.0, 0.0)), "C": (0.01, "suffix", (0.0, 0.0075))}
EP = {"E250": 251904, "E500": 501760, "E1M": 1001472}
TARGET = 1001472
N_ITEMS, N_ATT, N_ENTRY = 256, 2, 128
BOOT_R, BOOT_RNG = 10000, 20261104
CAL_TARGET = {"K1_q_min": 0.75, "K3_q_min": 0.05, "K3_q_max": 0.40, "entry_min": 0.55, "P1_max": 0.60}
TRAIN_KEYS = ("anchor_kl", "anchor_kl_prefix", "anchor_kl_suffix", "anchor_penalty", "update_kl_prefix",
              "update_kl_suffix", "actor_update_norm", "approx_kl", "entropy", "clipfrac", "frac_suffix_steps",
              "batch_successes")
INTERVALS = {"to_E250": (0, 251904), "E250_E500": (251904, 501760), "E500_E1M": (501760, 1001472)}


def rows(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def jdirs(runs, name):
    return sorted(d for d in runs.glob(f"*/{name}") if d.is_dir())


def complete_dir(runs, name, need):
    ds = [d for d in jdirs(runs, name) if (d / "summary.json").exists() and all((d / f).exists() for f in need)]
    return ds[-1] if ds else None


def lineage(runs, base):
    """Ordered chain [(dir, start)] ending in the job that reached TARGET; None if incomplete or inconsistent."""
    import torch
    jobs = jdirs(runs, base) + [d for k in range(1, 10) for d in jdirs(runs, f"{base}-r{k}")]
    final = [d for d in jobs if (d / "summary.json").exists()
             and json.loads((d / "summary.json").read_text()).get("continuation_actions") == TARGET]
    if len(final) != 1:
        return None, jobs
    chain, d = [], final[0]
    while True:
        sm = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else None
        cf = json.loads((d / "config.resolved.json").read_text())
        src = (sm or {}).get("resumed_from") or cf.get("resumed_from")
        if not src:
            chain.append((d, 0))
            break
        src = Path(src)
        saved = torch.load(src, map_location="cpu", weights_only=False)
        if saved["hash"] != (sm or cf).get("resumed_hash"):
            return None, jobs
        chain.append((d, saved["meta"]["post_probe_actions"]))
        d = src.parent
        if d not in jobs:
            return None, jobs
    return chain[::-1], jobs


def endpoint_file(chain, at):
    for k, (d, start) in enumerate(chain):
        nxt = chain[k + 1][1] if k + 1 < len(chain) else float("inf")
        if start < at <= nxt:
            return d / f"attempts_final_{at}.jsonl"
    return None


def measure(path, entry_n, arrival_n, limits=None):
    """Per-endpoint metrics recomputed from attempt rows."""
    rs = rows(path)
    nrm = [r for r in rs if r["kind"] == "normal"]
    ent = [r for r in rs if r["kind"] == "bank"]
    arr = [r for r in rs if r["kind"] == "bank_extra" and r["bank"] == "arrival"]
    assert len(nrm) == N_ITEMS * N_ATT and len(ent) == entry_n * N_ATT and len(arr) == arrival_n * N_ATT, path
    assert all(r["bin"] == "entry" for r in ent)
    assert all((not r["success"]) or r["arrival"] is not None for r in nrm), "success without an actual arrival"
    if limits is not None:
        lim = {r["item"]: r["limit"] for r in nrm}
        assert [lim[i] for i in range(N_ITEMS)] == limits, f"panel differs {path}"
    p_item = np.zeros(N_ITEMS)
    q_item = np.zeros(N_ITEMS)
    for r in nrm:
        p_item[r["item"]] += r["success"] / N_ATT
        q_item[r["item"]] += (r["arrival"] is not None) / N_ATT
    arrived = [r for r in nrm if r["arrival"] is not None]
    inv = {}
    for r in arrived:
        c = r["arrival"]["carrying"]
        k = "none" if c is None else f"{c[0]}:{c[1]}"
        inv[k] = inv.get(k, 0) + 1
    return {"P1": float(p_item.mean()), "q": float(q_item.mean()), "p_item": p_item,
            "r": float(np.mean([r["success"] for r in arrived])) if arrived else None, "n_arrivals": len(arrived),
            "entry": float(np.mean([r["success"] for r in ent])), "arrival_bank": float(np.mean([r["success"] for r in arr])),
            "tau_mean": float(np.mean([r["arrival"]["tau"] for r in arrived])) if arrived else None,
            "remaining_mean": float(np.mean([r["arrival"]["remaining"] for r in arrived])) if arrived else None,
            "inventory": inv}


def probe_measure(d, tag, entry_n, arrival_n):
    rs = rows(d / f"attempts_{tag}.jsonl")
    nrm = [r for r in rs if r["kind"] == "normal"]
    ent = [r for r in rs if r["kind"] == "bank"]
    arr = [r for r in rs if r["kind"] == "bank_extra" and r["bank"] == "arrival"]
    assert len(ent) == entry_n * N_ATT and len(arr) == arrival_n * N_ATT, d
    return {"P1": float(np.mean([r["success"] for r in nrm])), "q": float(np.mean([r["arrival"] is not None for r in nrm])),
            "entry": float(np.mean([r["success"] for r in ent])), "arrival_bank": float(np.mean([r["success"] for r in arr]))}


def bc_cohort(d):
    rec = [r for r in rows(d / "metrics.jsonl") if r["update"] == 8000][0]
    v = {f"K{K}_{m}": rec[f"normal_K{K}"][m] for K in (1, 3) for m in ("P1", "q")}
    v.update({f"K{K}_entry": rec[f"bank_K{K}_entry"] for K in (1, 3)})
    meets = {"K1_access": v["K1_q"] >= CAL_TARGET["K1_q_min"],
             "K3_access": CAL_TARGET["K3_q_min"] <= v["K3_q"] <= CAL_TARGET["K3_q_max"],
             "K1_entry": v["K1_entry"] >= CAL_TARGET["entry_min"], "K3_entry": v["K3_entry"] >= CAL_TARGET["entry_min"],
             "K1_room": v["K1_P1"] <= CAL_TARGET["P1_max"], "K3_room": v["K3_P1"] <= CAL_TARGET["P1_max"]}
    return {**v, "meets": meets, "meets_all": all(meets.values())}


def signflip_exact(x):
    x = np.asarray(x, float)
    n, obs = len(x), abs(x.sum())
    count = 0
    for start in range(0, 2 ** n, 2 ** 16):
        idx = np.arange(start, min(start + 2 ** 16, 2 ** n))
        signs = 1 - 2 * ((idx[:, None] >> np.arange(n)) & 1)
        count += int((np.abs(signs @ x) >= obs - 1e-12).sum())
    return count / 2 ** n


def boot(D, reps=BOOT_R, seed=BOOT_RNG):
    """D: seeds x layouts per-item contrasts. Crossed (seeds and layouts) and layouts-only percentile intervals."""
    rng = np.random.default_rng(seed)
    n, m = D.shape
    crossed, lay = np.empty(reps), np.empty(reps)
    for b in range(reps):
        s = rng.integers(0, n, n)
        i = rng.integers(0, m, m)
        crossed[b] = D[s][:, i].mean()
        lay[b] = D[:, i].mean()
    q = lambda v: [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]
    return {"crossed95": q(crossed), "layouts_only95": q(lay), "replicates": reps, "rng": seed,
            "assumptions": "crossed: seeds and the 256 layouts are both random samples; layouts resampled jointly for "
                           "all seeds and arms (pairing kept). layouts-only: conditional on the 20 trained seeds."}


def decide(t):
    return "supported" if t["t95_lo"] > 0 or t["t95_hi"] < 0 else "not supported"


def margins(t):
    return {f"excludes_{v}": bool(t["t95_lo"] > v or t["t95_hi"] < v) for v in (0.0, 0.03, -0.03, 0.05, -0.05)}


def training(chain, base_by_job):
    out = {}
    for name, (lo, hi) in INTERVALS.items():
        recs = []
        for d, _ in chain:
            base = base_by_job[d]
            for r in rows(d / "metrics.jsonl"):
                if r.get("phase") == "branch":
                    x = r["counters"]["env_actions"] - base
                    if lo < x <= hi:
                        recs.append(r)
        out[name] = {k: (float(np.mean([r[k] for r in recs if r.get(k) is not None]))
                         if any(r.get(k) is not None for r in recs) else None) for k in TRAIN_KEYS}
        out[name]["updates"] = len(recs)
    return out


def classify(res):
    """Descriptive pattern labels (owner instruction section 8); several may apply; none is an explanation."""
    E = res["secondary"]["E1M"]
    lab = []
    ent, arr, p = E["entry"], E["arrival_bank"], res["H1"]
    ent_up = ent["t95_lo"] > 0
    arr_up = arr["t95_lo"] > 0
    if (ent_up or arr_up) and res["H1"]["decision"] == "supported" and p["estimate"] > 0:
        lab.append("bank competence improves and normal-start success improves")
    if (ent_up or arr_up) and res["H1"]["decision"] != "supported":
        lab.append("bank competence improves but normal-start success remains unresolved")
    if ent_up and not arr_up:
        lab.append("only planner-bank competence improves")
    d250, d1m = res["secondary"]["E250"]["P1"]["estimate"], p["estimate"]
    if d250 > 0 and d1m < d250 and res["secondary"]["arms"]["E1M/A"]["P1"] > res["secondary"]["arms"]["E250/A"]["P1"]:
        lab.append("ordinary PPO gains on preservation after 251,904 (catch-up pattern, descriptive)")
    if res["secondary"]["arms"]["E1M/C"]["P1"] - res["secondary"]["arms"]["E250/C"]["P1"] < \
            res["secondary"]["arms"]["E1M/A"]["P1"] - res["secondary"]["arms"]["E250/A"]["P1"]:
        lab.append("preservation arm gains less after 251,904 than ordinary PPO (possible constraint, descriptive)")
    return lab


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--out", default=str(ROOT / "reports/a4"))
    ap.add_argument("--check-states", action="store_true")
    ap.add_argument("--final-incomplete", action="store_true")
    ap.add_argument("--data", default=str(ROOT / "data/r4-v1"))
    ap.add_argument("--arrival", default=str(ROOT / "data/a4-arrival-v1/arrival_bank.json"))
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    lay = json.loads((Path(a.data) / "layouts.json").read_text())
    limits = [it["layout"]["limit"] for it in lay["a4_final"] if it["layout"]["K"] == 3]
    n_arr = len(json.loads(Path(a.arrival).read_text())["states"])
    problems, excluded, cohort, X, interrupted, train = [], [], {}, {}, [], {}
    for s in SEEDS:
        bc = complete_dir(runs, f"a4-bc-s{s}", ["actor_u8000.pt"])
        pr = complete_dir(runs, f"a4-probe-K3-s{s}", ["fork.pt"])
        if bc is None or pr is None:
            excluded.append({"seed": s, "reason": "BC or probe incomplete"})
            continue
        bcf = json.loads((bc / "config.resolved.json").read_text())
        if (bcf.get("prefix_prob"), bcf["seed"], bcf["checkpoints"], bcf["dataset_id"]) != (0.2, s, [8000], "conf-v1"):
            problems.append(f"BC config {bc}")
        ps = json.loads((pr / "summary.json").read_text())
        pc = json.loads((pr / "config.resolved.json").read_text())
        ref = str(pc["bc_run"])
        bc_path = pr.parent / ref[2:] if ref.startswith("@/") else runs / ref
        if bc_path != bc or (ps["K"], ps["seed"], ps["bc_update"], pc["diag_role"], pc["dataset_id"]) != (3, s, 8000, "a4_select", "r4-v1"):
            problems.append(f"probe lineage/identity s{s}")
        cohort[s] = {"bc": bc_cohort(bc), "pi0": probe_measure(pr, "pi0", N_ENTRY, n_arr),
                     "probe": probe_measure(pr, "probe", N_ENTRY, n_arr)}
        ok = True
        for arm, tag in ARMS.items():
            chain, jobs = lineage(runs, f"a4-K3-s{s}-{tag}")
            interrupted += [str(d) for d in jobs if (d / "paused.json").exists() or not (d / "summary.json").exists()]
            if chain is None:
                excluded.append({"seed": s, "reason": f"branch {arm} incomplete or inconsistent lineage"})
                ok = False
                continue
            base_by_job = {}
            for d, _ in chain:
                sm = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else None
                cf = json.loads((d / "config.resolved.json").read_text())
                base, comp, eff = IDENT[arm]
                meta = sm or cf
                if (meta["arm"], meta["K"], meta["seed"], meta["alpha"], meta["anchor_component"], meta["fork_hash"],
                        cf["dataset_id"], cf["eval_role"], cf["bank_role"], cf["eval_seed"]) != \
                        (tag, 3, s, 0.0, comp, ps["fork_hash"], "r4-v1", "a4_final", "a4_bank", 969000) \
                        or abs(meta["kl_coef"] - base) > 1e-15 or \
                        any(abs(x - y) > 1e-15 for x, y in zip(meta["kl_effective_prefix_suffix"], eff)):
                    problems.append(f"branch identity {d}")
                base_by_job[d] = meta["base_actions"]
            last = json.loads((chain[-1][0] / "summary.json").read_text())
            if a.check_states:
                import torch
                sys.path.insert(0, str(ROOT / "src"))
                from bc2rl import ppo as PP
                for at in EP.values():
                    owner = [d for d, st in chain if (d / f"state_{at}.pt").exists() and st < at]
                    stf = owner[-1] / f"state_{at}.pt"
                    sv = torch.load(stf, map_location="cpu", weights_only=False)
                    if PP.state_hash(sv["state"]) != sv["hash"]:
                        excluded.append({"seed": s, "reason": f"branch {arm} state hash mismatch at {at}"})
                        ok = False
                if last["state_hashes"][str(TARGET)] != torch.load(chain[-1][0] / f"state_{TARGET}.pt", map_location="cpu",
                                                                   weights_only=False)["hash"]:
                    excluded.append({"seed": s, "reason": f"branch {arm} final state hash differs from summary"})
                    ok = False
            for ep, at in EP.items():
                f = endpoint_file(chain, at)
                X[(s, arm, ep)] = measure(f, N_ENTRY, n_arr, limits)
                X[(s, arm, ep)]["job"] = f"{f.parent.parent.name}/{f.parent.name}"
            train[(s, arm)] = training(chain, base_by_job)
            if len(chain) > 1:
                interrupted.append(f"s{s} {arm}: completed through {len(chain)} jobs (resumed)")
    exc = {x["seed"] for x in excluded}
    seeds = [s for s in SEEDS if s not in exc and all((s, arm, ep) in X for arm in ARMS for ep in EP)]
    complete = len(seeds) == len(SEEDS)
    blinded = not complete and not a.final_incomplete
    co = list(cohort.values())
    res = {"seeds_used": seeds, "n": len(seeds), "complete_design": complete, "excluded": excluded, "problems": problems,
           "interrupted_records": interrupted, "primary_computed": not blinded, "state_hashes_checked": a.check_states,
           "arrival_bank_states": n_arr,
           "cohort": {"per_seed": {str(s): v for s, v in cohort.items()},
                      "bc_meets_all_targets": sum(v["bc"]["meets_all"] for v in co),
                      "bc_meets_each": {k: sum(v["bc"]["meets"][k] for v in co) for k in (co[0]["bc"]["meets"] if co else {})},
                      "summary": {f"{src}_{m}": {"min": float(np.min(x)), "median": float(np.median(x)), "max": float(np.max(x))}
                                  for src in ("pi0", "probe") for m in ("q", "entry", "arrival_bank", "P1")
                                  for x in [[v[src][m] for v in co]] if x}
                      if co else {}}}
    seed_rows, dec_rows = [], []
    if not blinded and len(seeds) >= 3:
        P = lambda s, arm, ep: X[(s, arm, ep)]["P1"]
        d = {ep: np.array([P(s, "C", ep) - P(s, "A", ep) for s in seeds]) for ep in EP}
        t1 = R.t_test(d["E1M"])
        D = np.stack([X[(s, "C", "E1M")]["p_item"] - X[(s, "A", "E1M")]["p_item"] for s in seeds])
        h1 = {**t1, "decision": decide(t1), "n_positive": int((d["E1M"] > 0).sum()), "signflip_p_exact": signflip_exact(d["E1M"]),
              **boot(D), **margins(t1), "status": "confirmatory H1 (C - A at 1,001,472; two-sided paired t, alpha 0.05)"}
        res["H1"] = h1
        g = d["E1M"] - d["E250"]
        tg = R.t_test(g)
        if h1["decision"] == "supported":
            res["H2"] = {**tg, "tested": True, "decision": decide(tg), "n_positive": int((g > 0).sum()),
                         "increasing_benefit_supported": bool(h1["estimate"] > 0 and decide(tg) == "supported" and tg["estimate"] > 0)}
        else:
            res["H2"] = {**tg, "tested": False, "decision": None, "increasing_benefit_supported": False,
                         "note": "H1 not supported: the change d(E1M) - d(E250) is descriptive only"}
        sec = {}
        for ep in EP:
            blk = {}
            for m in ("P1", "q", "entry", "arrival_bank"):
                v = [X[(s, "C", ep)][m] - X[(s, "A", ep)][m] for s in seeds]
                blk[m] = {**R.t_test(v), "n_positive": int(sum(x > 0 for x in v)), **margins(R.t_test(v))}
            rv = [X[(s, "C", ep)]["r"] - X[(s, "A", ep)]["r"] for s in seeds
                  if X[(s, "C", ep)]["r"] is not None and X[(s, "A", ep)]["r"] is not None]
            blk["r"] = {**(R.t_test(rv) if len(rv) >= 3 else {"n": len(rv)}), "n_defined": len(rv)}
            dec = []
            for s in seeds:
                c, o = X[(s, "C", ep)], X[(s, "A", ep)]
                row = {"endpoint": ep, "seed": s, "q_A": o["q"], "q_C": c["q"], "r_A": o["r"], "r_C": c["r"], "dp": c["P1"] - o["P1"]}
                if c["r"] is None or o["r"] is None:
                    row.update(access_part=None, completion_part=None, note="r undefined (no arrivals); not imputed")
                else:
                    row.update(access_part=(c["q"] - o["q"]) * (c["r"] + o["r"]) / 2,
                               completion_part=(c["r"] - o["r"]) * (c["q"] + o["q"]) / 2, note="")
                    assert abs(row["access_part"] + row["completion_part"] - row["dp"]) < 1e-12
                dec.append(row)
            dec_rows += dec
            okd = [r for r in dec if r["access_part"] is not None]
            blk["decomposition"] = {"n_defined": len(okd), **({k: R.t_test([r[k] for r in okd]) for k in ("dp", "access_part", "completion_part")}
                                                               if len(okd) >= 3 else {})}
            sec[ep] = blk
        sec["change_E1M_minus_E250"] = R.t_test(g)
        sec["change_E500_minus_E250"] = R.t_test(d["E500"] - d["E250"])
        arms = {}
        for ep in EP:
            for arm in ARMS:
                recs = [X[(s, arm, ep)] for s in seeds]
                gm = {m: float(np.mean([r[m] for r in recs])) for m in ("P1", "q", "entry", "arrival_bank")}
                rs = [r["r"] for r in recs if r["r"] is not None]
                gm["r_mean_defined"], gm["r_defined_n"] = (float(np.mean(rs)) if rs else None), len(rs)
                for k in ("tau_mean", "remaining_mean"):
                    v = [r[k] for r in recs if r[k] is not None]
                    gm[k] = float(np.mean(v)) if v else None
                inv = {}
                for r in recs:
                    for k, v in r["inventory"].items():
                        inv[k] = inv.get(k, 0) + v
                gm["inventory_at_arrival"] = inv
                for ref in ("pi0", "probe"):
                    for m in ("entry", "arrival_bank"):
                        gm[f"{m}_change_from_{ref}"] = float(np.mean([X[(s, arm, ep)][m] - cohort[s][ref][m] for s in seeds]))
                arms[f"{ep}/{arm}"] = gm
            for s in seeds:
                seed_rows.append({"endpoint": ep, "seed": s, **{f"{m}_{arm}": X[(s, arm, ep)][m] for arm in ARMS
                                                               for m in ("P1", "q", "r", "entry", "arrival_bank")}})
        sec["arms"] = arms
        sec["training"] = {arm: {iv: {k: (float(np.mean([train[(s, arm)][iv][k] for s in seeds if train[(s, arm)][iv][k] is not None]))
                                          if any(train[(s, arm)][iv][k] is not None for s in seeds) else None)
                                      for k in list(TRAIN_KEYS) + ["updates"]} for iv in INTERVALS} for arm in ARMS}
        res["secondary"] = sec
        res["patterns_descriptive"] = classify(res)
    (out / "a4_summary.json").write_text(json.dumps(res, indent=1, default=float))
    branch_rows = [] if blinded else [{"seed": s, "arm": arm, "endpoint": ep, "job": X[(s, arm, ep)]["job"],
                                       **{m: X[(s, arm, ep)][m] for m in ("P1", "q", "r", "n_arrivals", "entry", "arrival_bank",
                                                                         "tau_mean", "remaining_mean")}}
                                      for (s, arm, ep) in sorted(X)]
    cohort_rows = [{"seed": s, **{f"bc_{k}": v for k, v in c["bc"].items() if k != "meets"},
                    **{f"{src}_{m}": c[src][m] for src in ("pi0", "probe") for m in c[src]}} for s, c in cohort.items()]
    for name, data in (("a4_branches.csv", branch_rows), ("a4_seeds.csv", seed_rows), ("a4_cohort.csv", cohort_rows),
                       ("a4_decomposition.csv", dec_rows)):
        if data:
            keys = list(dict.fromkeys(k for r in data for k in r))
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(data)
    brief = {k: res[k] for k in ("seeds_used", "complete_design", "excluded", "problems", "primary_computed")}
    if "H1" in res:
        brief["H1"] = {k: res["H1"][k] for k in ("estimate", "t95_lo", "t95_hi", "p", "crossed95", "signflip_p_exact", "decision")}
        brief["H2"] = {k: res["H2"].get(k) for k in ("tested", "estimate", "p", "decision", "increasing_benefit_supported")}
    print(json.dumps(brief, indent=1, default=float))
    return res


if __name__ == "__main__":
    main()
