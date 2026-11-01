"""R1 replication analysis (PROTOCOL_FREEZE Amendment 3). Written and committed before any R1 data exist.

Usage: .venv/bin/python tools/analyze_r1.py [--batches B ...] [--runs .mae/runs] [--out reports/r1] [--check-states]

Jobs are found by name in the given batches (default: every batch): r1-bc-s{S}, r1-probe-K3-u{U}-s{S},
r1-K3-u{U}-s{S}-{00|01-kl0p01}; only jobs with summary.json count, and a name in two batches is an error.
A seed enters the primary analysis only if its two probes and four branches exist and every branch carries its
probe's fork hash; otherwise it is reported as excluded (never replaced).

Per branch and endpoint, P1, q, C4, R4, P(success | arrival) and c are recomputed from attempts_<tag>.jsonl and must
equal the summary. Every normal-start record must be K=3, and the per-item limits must be the same frozen panel
(r1_final, 128 items x 4 attempts) for every branch; the bank must be r1_bank (64 x 4).

Primary (E500 = final_501760), training seed is the unit (n = 8):
  d_early_i = P1(01, early) - P1(00, early); d_ext_i = P1(01, extended) - P1(00, extended);
  inter_i = d_early_i - d_ext_i.
  H1: mean d_early = 0; H2: mean inter = 0. Two-sided paired t-tests (df n-1), Holm over {H1, H2} at 0.05.
  "Supported" = Holm-adjusted p < 0.05. The t-interval and t-test are conditional on the frozen panel.
  Layout sampling: crossed bootstrap, 10,000 replicates (RNG 20261101) resampling seeds (n) and r1_final items
  (128) independently; the same item indices for every seed, arm and checkpoint (pairing kept); percentile 95%.
  Also a layouts-only bootstrap (seeds fixed) and the exact sign-flip test, as sensitivity checks only.
  Magnitude (for d_early): t-interval lower bound > 0.05 -> "exceeds the 0.05 practical threshold"; upper bound
  < 0.05 -> "below the threshold"; otherwise "not distinguishable from the threshold".
  If H1 is not supported: upper bound < 0.0227 (half the M4 post hoc estimate) -> "informative failure to
  replicate (excludes half the original estimate)"; upper bound < 0.0453 -> "excludes the original estimate,
  not half of it"; otherwise "inconclusive".
  Interpretation cell: section 6 of the owner instruction (four cases).
Descriptive (no claims): the same statistics at E250 (unadjusted p); by checkpoint and arm: P1, q, P(success |
arrival) (undefined when a branch has no arrivals; never imputed), C4/R4 (4 attempts per layout), fixed-bank entry,
retrieval and carrying and their change from pi0 and the probe on the same bank, arrival timing and inventory,
anchor KL, training visitation and optimization diagnostics; curves kept separate by layout role (r1_select:
pi0, probe, 126,976, 376,832; r1_final: 251,904, 501,760). M4 post hoc reference values are reported in a separate
block and never pooled.
Execution: lineage, fork hashes, branch configs, optional saved-state hashes, env_steps counter cross-check.
Outputs: r1_branches.csv, r1_seeds.csv, r1_curves.csv, r1_summary.json.
"""
import argparse
import csv
import hashlib
import json
from math import comb
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import r1_stats as R      # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SEEDS = tuple(range(15, 23))
CKPT = {"early": 4000, "extended": 16000}
ARMS = {"00": "00", "01": "01-kl0p01"}
EP = {"E500": ("final_501760", 501760), "E250": ("final_251904", 251904)}
CURVE = {"curve_126976": 126976, "curve_376832": 376832}
N_ITEMS, N_ATT, N_BANK, N_BANK_ATT = 128, 4, 64, 4
BINS = ("entry", "retrieval", "carrying")
PRACTICAL, M4_EST = 0.05, 0.0453
M4_REFERENCE = {"source": "F11 post hoc subgroup, M4 seeds 10-14, conf_final 64 x 8 (not pooled with R1)",
                "estimate": 0.0453, "t95": [0.0353, 0.0554], "crossed_bootstrap95": [0.022, 0.074],
                "within_K3_interaction_E500": 0.073, "interaction_t95": [0.038, 0.108]}
BOOT_R, BOOT_RNG = 10000, 20261101


def read_attempts(path):
    normal, bank = {}, {}
    for line in Path(path).read_text().splitlines():
        r = json.loads(line)
        (normal if r["kind"] == "normal" else bank).setdefault(r["item"], []).append(r)
    return normal, bank


def find_jobs(runs, batches):
    found = {}
    for b in batches:
        for d in sorted((runs / b).glob("r1-*")):
            if (d / "summary.json").exists():
                assert d.name not in found, f"duplicate job {d.name}: {found[d.name]} and {d}"
                found[d.name] = d
    return found


def endpoint_record(d, sm, tag):
    """Raw per-item arrays for one branch endpoint, with recomputation checks against the summary."""
    e = next(x for x in sm["evals"] if x["tag"] == tag)
    normal, bank = read_attempts(d / f"attempts_{tag}.jsonl")
    items = sorted(normal)
    assert items == list(range(N_ITEMS)) and all(len(normal[i]) == N_ATT for i in items), f"{d.name} {tag} panel shape"
    assert sorted(bank) == list(range(N_BANK)) and all(len(bank[i]) == N_BANK_ATT for i in bank), f"{d.name} {tag} bank shape"
    for i in items:
        for r in normal[i]:
            assert r["K"] == 3, f"{d.name} non-K3 record"
            assert (not r["success"]) or r["arrival"] is not None
            assert bool(r["accessed"]) == (r["arrival"] is not None)
    z = np.array([sum(bool(r["success"]) for r in normal[i]) for i in items], float)
    a = np.array([sum(r["arrival"] is not None for r in normal[i]) for i in items], float)
    arr = [r["arrival"] for i in items for r in normal[i] if r["arrival"]]
    bins = {b: [] for b in BINS}
    for i in sorted(bank):
        bins[bank[i][0]["bin"]].append(np.mean([bool(r["success"]) for r in bank[i]]))
    rec = {"z": z, "a": a, "p": z / N_ATT, "limits": [normal[i][0]["limit"] for i in items],
           "P1": float(z.mean() / N_ATT), "q": float(a.sum() / (N_ITEMS * N_ATT)),
           "r": float(z.sum() / a.sum()) if a.sum() else None,
           "C4": float(np.mean([1 - comb(N_ATT - int(k), 4) / comb(N_ATT, 4) for k in z])),
           "R4": float(np.mean([comb(int(k), 4) / comb(N_ATT, 4) for k in z])),
           "c": float(np.mean([np.mean([bool(r["success"]) for r in v]) for v in bank.values()])),
           "bins": {b: float(np.mean(v)) for b, v in bins.items()}, "bin_counts": {b: len(v) for b, v in bins.items()},
           "n_arrivals": int(a.sum()),
           "arrival_tau_mean": float(np.mean([x["tau"] for x in arr])) if arr else None,
           "arrival_remaining_mean": float(np.mean([x["remaining"] for x in arr])) if arr else None,
           "inventory": {}}
    for x in arr:
        k = "+".join(map(str, x["carrying"])) if x["carrying"] else "nothing"
        rec["inventory"][k] = rec["inventory"].get(k, 0) + 1
    for m in ("P1", "q", "C4", "R4", "c"):
        assert abs(rec[m] - e[m]) < 1e-12, f"{d.name} {tag} {m} {rec[m]} != {e[m]}"
    pe = e["P_success_given_arrival"]
    assert (pe is None) == (rec["r"] is None) and (pe is None or abs(pe - rec["r"]) < 1e-12)
    assert e["actions"] == dict(EP.values())[tag] and e.get("endpoint") and e["layouts"] == "eval"
    return rec


def training_diag(d):
    recs = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
    tr = [r for r in recs if r.get("phase") == "branch"]
    mean = lambda k: float(np.mean([r[k] for r in tr if r.get(k) is not None])) if tr else None
    c0, c1 = tr[0]["counters"], tr[-1]["counters"]
    ep = c1["normal_episodes"] - c0["normal_episodes"]
    return {"updates": len(tr), "anchor_kl_mean": mean("anchor_kl"), "anchor_kl_final": tr[-1].get("anchor_kl"),
            "approx_kl_mean": mean("approx_kl"), "clipfrac_mean": mean("clipfrac"), "entropy_final": tr[-1]["entropy"],
            "explained_var_mean": mean("explained_var"), "grad_norm_actor_mean": mean("grad_norm_actor"),
            "frac_suffix_steps_mean": mean("frac_suffix_steps"),
            "train_access_rate": (c1["normal_accessed"] - c0["normal_accessed"]) / ep if ep else None,
            "train_success_rate": (c1["normal_successes"] - c0["normal_successes"]) / ep if ep else None}


def env_steps(d):
    p = sorted((d / "env_steps").glob("*.json"))
    return sum(json.loads(x.read_text())["actions"] for x in p) if p else None


def boot(C, n_seeds, R_=BOOT_R, seed=BOOT_RNG):
    """C: (n_seeds, 128) per-item contrasts. Crossed and layouts-only percentile intervals (same item indices for
    every seed; callers build C so that arms and checkpoints share them)."""
    rng = np.random.default_rng(seed)
    sidx = rng.integers(0, n_seeds, size=(R_, n_seeds))
    lidx = rng.integers(0, N_ITEMS, size=(R_, N_ITEMS))
    M = np.stack([C[:, li].mean(-1) for li in lidx], 1)          # (n_seeds, R): per seed, resampled layouts
    crossed = M[sidx, np.arange(R_)[:, None]].mean(1)
    lay_only = M.mean(0)
    q = lambda x: [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))]
    return {"crossed95": q(crossed), "layouts_only95": q(lay_only), "replicates": R_, "rng": seed}


def magnitude(t):
    if t["t95_lo"] > PRACTICAL:
        return "exceeds the 0.05 practical threshold"
    if t["t95_hi"] < PRACTICAL:
        return "below the 0.05 practical threshold"
    return "not distinguishable from the 0.05 practical threshold"


def interpret(h1, h2, t1):
    if h1 and h2:
        return "H1 and H2 supported: replication of the early-BC benefit and evidence of checkpoint dependence."
    if h1:
        return "H1 supported, H2 not: replication of the early-BC benefit; checkpoint dependence remains unresolved."
    if h2:
        return "H2 supported, H1 not: relative checkpoint dependence alone does not establish benefit in early BC."
    if t1["t95_hi"] < M4_EST / 2:
        return "Neither supported: informative failure to replicate (the interval excludes half the original estimate)."
    if t1["t95_hi"] < M4_EST:
        return "Neither supported: the interval excludes the original estimate but not half of it; partly informative."
    return "Neither supported: inconclusive (the interval does not exclude the original estimate)."


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=str(ROOT / ".mae/runs"))
    ap.add_argument("--batches", nargs="*")
    ap.add_argument("--out", default=str(ROOT / "reports/r1"))
    ap.add_argument("--check-states", action="store_true")
    a = ap.parse_args(argv)
    runs, out = Path(a.runs), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    batches = a.batches or sorted(p.name for p in runs.iterdir() if p.is_dir())
    jobs = find_jobs(runs, batches)
    X, rows, curves, excluded, problems, steps = {}, [], [], [], [], {}
    probes, train = {}, {}
    panel = None
    for s in SEEDS:
        bc = jobs.get(f"r1-bc-s{s}")
        for ck, u in CKPT.items():
            pj = jobs.get(f"r1-probe-K3-u{u}-s{s}")
            if pj is None:
                excluded.append({"seed": s, "reason": f"probe {ck} missing"})
                continue
            ps = json.loads((pj / "summary.json").read_text())
            pc = json.loads((pj / "config.resolved.json").read_text())
            if (ps["K"], ps["seed"], ps["bc_update"], pc.get("bc_seed"), pc["diag_role"], pc["eval_role"], pc["bank_role"],
                    pc["dataset_id"]) != (3, s, u, s, "r1_select", "r1_final", "r1_bank", "r1-v1"):
                problems.append(f"probe config/lineage {pj.name}")
            if bc is not None and not str(pc["bc_run"]).endswith(f"r1-bc-s{s}"):
                problems.append(f"probe bc_run {pj.name}")
            probes[(s, ck)] = ps
            steps[pj.name] = (env_steps(pj), sum(ps["actions"].values()))
            for tag in ("pi0", "probe"):
                curves.append({"seed": s, "checkpoint": ck, "arm": "shared", "role": "r1_select", "point": tag,
                               "post_probe_actions": -51200 if tag == "pi0" else 0, "P1": ps[tag]["p"], "q": ps[tag]["q"],
                               "c": ps[tag]["c"], **{f"bank_{b}": ps[tag]["bins"][b] for b in BINS}})
            for arm, tag in ARMS.items():
                d = jobs.get(f"r1-K3-u{u}-s{s}-{tag}")
                if d is None:
                    excluded.append({"seed": s, "reason": f"branch {ck}/{arm} missing"})
                    continue
                sm = json.loads((d / "summary.json").read_text())
                cf = json.loads((d / "config.resolved.json").read_text())
                if sm["fork_hash"] != ps["fork_hash"] or cf["probe_run"] != str(pj):
                    excluded.append({"seed": s, "reason": f"branch {ck}/{arm} fork hash or lineage mismatch"})
                    continue
                want_kl = 0.01 if arm == "01" else 0.0
                if (sm["arm"], sm["K"], sm["seed"], sm["bc_update"], sm["alpha"], sm["kl_coef"], cf["dataset_id"],
                        cf["eval_role"], cf["bank_role"], cf["diag_role"]) != (arm, 3, s, u, 0.0, want_kl, "r1-v1",
                                                                               "r1_final", "r1_bank", "r1_select"):
                    problems.append(f"branch config {d.name}")
                steps[d.name] = (env_steps(d), sum(sm.get("actions_this_job", sm["actions"]).values()))
                train[(s, ck, arm)] = training_diag(d)
                if a.check_states:
                    import torch
                    sys.path.insert(0, str(ROOT / "src"))
                    from bc2rl import ppo as PP
                    for at in (251904, 501760):
                        st = torch.load(d / f"state_{at}.pt", map_location="cpu", weights_only=False)
                        if not (PP.state_hash(st["state"]) == st["hash"] == sm["state_hashes"][str(at)]):
                            problems.append(f"state hash {d.name} {at}")
                for e in sm["evals"]:
                    if e["tag"] in CURVE:
                        assert e["layouts"] == "diag" and not e.get("endpoint")
                        curves.append({"seed": s, "checkpoint": ck, "arm": arm, "role": "r1_select", "point": e["tag"],
                                       "post_probe_actions": e["actions"], "P1": e["P1"], "q": e["q"], "c": e["c"],
                                       **{f"bank_{b}": e["bins"][b] for b in BINS}})
                for ep, (tag_e, at) in EP.items():
                    rec = endpoint_record(d, sm, tag_e)
                    if panel is None:
                        panel = rec["limits"]
                    if rec["limits"] != panel:
                        problems.append(f"panel differs {d.name} {ep}")
                    X[(s, ck, arm, ep)] = rec
                    rows.append({"seed": s, "checkpoint": ck, "bc_update": u, "arm": arm, "endpoint": ep,
                                 "post_probe_actions": at, "job": f"{d.parent.name}/{d.name}", "fork_hash": sm["fork_hash"],
                                 "state_hash": sm["state_hashes"].get(str(at)),
                                 **{m: rec[m] for m in ("P1", "q", "r", "C4", "R4", "c", "n_arrivals",
                                                        "arrival_tau_mean", "arrival_remaining_mean")},
                                 **{f"bank_{b}": rec["bins"][b] for b in BINS}})
                    curves.append({"seed": s, "checkpoint": ck, "arm": arm, "role": "r1_final", "point": tag_e,
                                   "post_probe_actions": at, "P1": rec["P1"], "q": rec["q"], "c": rec["c"],
                                   **{f"bank_{b}": rec["bins"][b] for b in BINS}})
        if bc is not None:
            steps[bc.name] = (env_steps(bc), None)
    seeds = [s for s in SEEDS if all((s, ck, arm, "E500") in X for ck in CKPT for arm in ARMS)]
    res = {"seeds_used": seeds, "n": len(seeds), "excluded": excluded, "problems": problems,
           "m4_post_hoc_reference": M4_REFERENCE}
    seed_rows = []
    for ep in EP:
        P = lambda s, ck, arm: X[(s, ck, arm, ep)]["P1"]
        de = np.array([P(s, "early", "01") - P(s, "early", "00") for s in seeds])
        dx = np.array([P(s, "extended", "01") - P(s, "extended", "00") for s in seeds])
        it = de - dx
        for i, s in enumerate(seeds):
            seed_rows.append({"endpoint": ep, "seed": s, "P1_00_early": P(s, "early", "00"), "P1_01_early": P(s, "early", "01"),
                              "P1_00_extended": P(s, "extended", "00"), "P1_01_extended": P(s, "extended", "01"),
                              "d_early": de[i], "d_extended": dx[i], "interaction": it[i]})
        if len(seeds) < 3:
            continue
        item = lambda ck, arm: np.stack([X[(s, ck, arm, ep)]["p"] for s in seeds])         # (n, 128)
        Ce = item("early", "01") - item("early", "00")
        Cx = item("extended", "01") - item("extended", "00")
        blk = {}
        for name, x, C in (("early", de, Ce), ("extended", dx, Cx), ("interaction", it, Ce - Cx)):
            blk[name] = {**R.t_test(x), "signflip_p": R.signflip(x), **boot(C, len(seeds))}
        p_holm = R.holm([blk["early"]["p"], blk["interaction"]["p"]])
        blk["early"]["p_holm"], blk["interaction"]["p_holm"] = p_holm
        base = float(np.mean([P(s, "early", "00") for s in seeds]))
        blk["early"]["relative_to_ordinary_early"] = blk["early"]["estimate"] / base if base else None
        blk["early"]["magnitude"] = magnitude(blk["early"])
        if ep == "E500":
            h1, h2 = p_holm[0] < 0.05, p_holm[1] < 0.05
            blk["H1_supported"], blk["H2_supported"] = h1, h2
            blk["interpretation"] = interpret(h1, h2, blk["early"])
            blk["status"] = "primary (Holm over H1, H2)"
            blk["bootstrap_agrees"] = {k: (blk[k]["crossed95"][0] > 0) == (blk[k]["estimate"] > 0) and
                                       (blk[k]["crossed95"][0] > 0 or blk[k]["crossed95"][1] < 0)
                                       for k in ("early", "interaction")}
            blk["complete_design"] = len(seeds) == len(SEEDS)
        else:
            blk["status"] = "descriptive checkpoint (p-values unadjusted, no claims)"
        res[ep] = blk
    # secondary, by checkpoint and arm (descriptive)
    sec = {}
    for ep in EP:
        for ck in CKPT:
            for arm in ARMS:
                recs = [X[(s, ck, arm, ep)] for s in seeds]
                g = {m: float(np.mean([r[m] for r in recs])) for m in ("P1", "q", "C4", "R4", "c")}
                rs = [r["r"] for r in recs if r["r"] is not None]
                g["r_mean_defined"], g["r_defined_n"] = (float(np.mean(rs)) if rs else None), len(rs)
                g["bins"] = {b: float(np.mean([r["bins"][b] for r in recs])) for b in BINS}
                g["arrival_tau_mean"] = float(np.mean([r["arrival_tau_mean"] for r in recs if r["arrival_tau_mean"] is not None])) \
                    if any(r["arrival_tau_mean"] is not None for r in recs) else None
                g["arrival_remaining_mean"] = float(np.mean([r["arrival_remaining_mean"] for r in recs if r["arrival_remaining_mean"] is not None])) \
                    if any(r["arrival_remaining_mean"] is not None for r in recs) else None
                inv = {}
                for r in recs:
                    for k, v in r["inventory"].items():
                        inv[k] = inv.get(k, 0) + v
                g["inventory"], g["zero_arrival_branches"] = inv, sum(r["n_arrivals"] == 0 for r in recs)
                for ref in ("pi0", "probe"):
                    g[f"bins_change_from_{ref}"] = {b: float(np.mean([X[(s, ck, arm, ep)]["bins"][b] - probes[(s, ck)][ref]["bins"][b]
                                                                       for s in seeds])) for b in BINS}
                if ep == "E500":
                    g["training"] = {k: (float(np.mean([train[(s, ck, arm)][k] for s in seeds if train[(s, ck, arm)][k] is not None]))
                                         if any(train[(s, ck, arm)][k] is not None for s in seeds) else None)
                                     for k in train[(seeds[0], ck, arm)]} if seeds else {}
                sec[f"{ep}/{ck}/{arm}"] = g
            # paired arm differences (01 - 00) for the secondary metrics
            diffs = {}
            for m in ("P1", "q", "C4", "R4", "c") + tuple(f"bin_{b}" for b in BINS):
                get = (lambda r, m=m: r["bins"][m[4:]]) if m.startswith("bin_") else (lambda r, m=m: r[m])
                x = [get(X[(s, ck, "01", ep)]) - get(X[(s, ck, "00", ep)]) for s in seeds]
                diffs[m] = R.t_test(x) if len(x) >= 3 else None
            rx = [X[(s, ck, "01", ep)]["r"] - X[(s, ck, "00", ep)]["r"] for s in seeds
                  if X[(s, ck, "01", ep)]["r"] is not None and X[(s, ck, "00", ep)]["r"] is not None]
            diffs["r_defined_pairs"] = {"n": len(rx), **(R.t_test(rx) if len(rx) >= 3 else {})}
            sec[f"{ep}/{ck}/diff_01_minus_00"] = diffs
    res["secondary"] = sec
    res["probes"] = {f"{s}/{ck}": {k: probes[(s, ck)][k] for k in ("pi0", "probe", "fork_hash")} for s, ck in probes}
    res["counter_check"] = {k: {"env_steps": v[0], "summary_actions": v[1],
                                "equal": None if v[0] is None or v[1] is None else v[0] == v[1]} for k, v in steps.items()}
    res["bc_checkpoint_sha256_16"] = {}
    for s in SEEDS:
        bc = jobs.get(f"r1-bc-s{s}")
        if bc is not None:
            res["bc_checkpoint_sha256_16"][s] = {u: hashlib.sha256((bc / f"actor_u{u}.pt").read_bytes()).hexdigest()[:16]
                                                 for u in CKPT.values() if (bc / f"actor_u{u}.pt").exists()}
    res["state_hashes_checked"] = a.check_states
    (out / "r1_summary.json").write_text(json.dumps(res, indent=1, default=float))
    for name, data in (("r1_branches.csv", rows), ("r1_seeds.csv", seed_rows), ("r1_curves.csv", curves)):
        if data:
            keys = list(dict.fromkeys(k for r in data for k in r))
            with open(out / name, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                w.writerows(data)
    brief = {k: res[k] for k in ("seeds_used", "excluded", "problems")}
    if "E500" in res:
        brief["E500"] = {k: res["E500"][k] for k in ("H1_supported", "H2_supported", "interpretation")}
        for k in ("early", "extended", "interaction"):
            brief["E500"][k] = {m: res["E500"][k][m] for m in ("estimate", "t95_lo", "t95_hi", "p", "crossed95")}
            brief["E500"][k]["p_holm"] = res["E500"][k].get("p_holm")
    print(json.dumps(brief, indent=1, default=float))
    return res


if __name__ == "__main__":
    main()
