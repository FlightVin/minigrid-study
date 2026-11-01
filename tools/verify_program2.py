"""Independent verification of the second 2026-11-01 programme (owner instruction 2026-11-01b, section 14;
PROTOCOL_FREEZE Amendment 5). Independent of tools/analyze_a3.py, analyze_cal.py, analyze_pilot.py, analyze_r1.py and
r1_stats.py: reads raw attempt files, summaries, configs and step records directly; own t interval (via the
tools/audit_r1.py t CDF), own exact sign-flip enumeration, own target and selection code. No environment actions.

A3: inventory (24 seeds x {bc, probe, A..E}, exactly one complete copy each), lineage (branch probe_run and fork hash =
the seed's probe; probe bc_run = the seed's BC), arm identity (base coefficient, component, effective prefix/suffix
coefficients, alpha 0), evaluation roles and seed, panel limits = the a3_final K=3 registry and identical for every
branch and endpoint, 512 normal + 256 bank rows per endpoint, P1/q/c recomputed and equal to the summary, step
records = summary actions. With all 24 seeds complete (and not --engineering): H1 (C-A at 251,904) t-test, 95%
interval, exact sign-flip p; every prespecified contrast at both endpoints; the gate; agreement with
reports/a3/a3_summary.json. Before 24/24 only the engineering checks run (no outcome is computed or printed).
Calibration (when reports/cal/cal_summary.json exists): per job and checkpoint, P1, q and bank bins recomputed from
attempts; three-seed means; targets and selection re-applied; agreement with the analysis.
Pilot (when reports/pilot/pilot_summary.json exists): inventory, lineage, identity, P1 recomputed; per-K contrasts;
agreement with the analysis.
Usage: .venv/bin/python tools/verify_program2.py [--engineering]  -> reports/program2/verification.json
"""
import argparse
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_r1 import t_two_sided_p    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
OUT = ROOT / "reports/program2"
A3_SEEDS = range(43, 67)
A3_ARMS = {"A": ("00", 0.0, "both", (0.0, 0.0)), "B": ("01p", 0.01, "prefix", (0.0025, 0.0)),
           "C": ("01s", 0.01, "suffix", (0.0, 0.0075)), "D": ("01", 0.01, "both", (0.0025, 0.0075)),
           "E": ("01w", 0.0075, "both", (0.001875, 0.005625))}
A3_TAGS = ("final_251904", "final_501760")
A3_W = {"B-A": {"B": 1, "A": -1}, "C-A": {"C": 1, "A": -1}, "D-A": {"D": 1, "A": -1}, "E-A": {"E": 1, "A": -1},
        "D-C": {"D": 1, "C": -1}, "C-D": {"C": 1, "D": -1}, "C-E": {"C": 1, "E": -1},
        "interaction D-B-C+A": {"D": 1, "B": -1, "C": -1, "A": 1}}
PL_ARMS = {"00": (0.0, 0.0, "both"), "10": (0.25, 0.0, "both"), "01s": (0.0, 0.01, "suffix"), "11s": (0.25, 0.01, "suffix")}
PL_W = {"10-00": {"10": 1, "00": -1}, "01s-00": {"01s": 1, "00": -1}, "11s-00": {"11s": 1, "00": -1},
        "interaction": {"11s": 1, "10": -1, "01s": -1, "00": 1}}


def t_crit(df, level=0.95):
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_two_sided_p(mid, df) > 1 - level else (lo, mid)
    return (lo + hi) / 2


def ttest(d):
    d = np.asarray(d, float)
    n, m, sd = len(d), d.mean(), d.std(ddof=1)
    se = sd / sqrt(n)
    c = t_crit(n - 1)
    return {"n": n, "estimate": float(m), "sd": float(sd), "t": float(m / se), "p": float(t_two_sided_p(m / se, n - 1)),
            "lo": float(m - c * se), "hi": float(m + c * se)}


def signflip(d):
    d = np.asarray(d, float)
    n, obs = len(d), abs(d.sum())
    count = 0
    for start in range(0, 2 ** n, 2 ** 16):
        idx = np.arange(start, min(start + 2 ** 16, 2 ** n))
        signs = 1 - 2 * ((idx[:, None] >> np.arange(n)) & 1)
        count += int((np.abs(signs @ d) >= obs - 1e-12).sum())
    return count / 2 ** n


def rows(path):
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def find(name):
    return [d for d in RUNS.glob(f"*/{name}") if (d / "summary.json").exists()]


def one(name, problems, tag):
    h = find(name)
    if len(h) != 1:
        problems.append(f"{tag} {name}: {len(h)} complete copies")
        return None
    return h[0]


def steps(d):
    return sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))


def mean(v):
    return sum(v) / len(v)


def close(a, b, tol=1e-9):
    return a is not None and b is not None and abs(a - b) <= tol


def check_steps(d, sm, problems, tag):
    act = sm.get("actions_this_job", sm.get("actions"))
    if isinstance(act, dict) and steps(d) != sum(act.values()):
        problems.append(f"{tag} {d.name}: step records {steps(d)} != summary {sum(act.values())}")
        return 0
    return 1


def verify_a3(problems, engineering):
    reg = json.loads((ROOT / "data/r3-v1/layouts.json").read_text())
    k3 = [it["layout"]["limit"] for it in reg["a3_final"] if it["layout"]["K"] == 3]
    assert len(k3) == 128
    P, complete, steps_ok, panels = {}, [], 0, set()
    for s in A3_SEEDS:
        bc = one(f"a3-bc-s{s}", problems, "A3") if find(f"a3-bc-s{s}") else None
        probe = one(f"a3-probe-K3-u4000-s{s}", problems, "A3") if find(f"a3-probe-K3-u4000-s{s}") else None
        branches = {a: find(f"a3-K3-u4000-s{s}-{v[0]}") for a, v in A3_ARMS.items()}
        if bc is None or probe is None or not all(branches.values()):
            continue
        ps = json.loads((probe / "summary.json").read_text())
        pc = json.loads((probe / "config.resolved.json").read_text())
        bc_ref = str(pc["bc_run"])
        bc_path = probe.parent / bc_ref[2:] if bc_ref.startswith("@/") else Path(bc_ref)   # "@/" = the probe's own batch
        if bc_path != bc or (ps["K"], ps["seed"], ps["bc_update"]) != (3, s, 4000):
            problems.append(f"A3 s{s}: probe lineage/identity")
        steps_ok += check_steps(probe, ps, problems, "A3")
        ok = True
        for arm, (tag, base, comp, eff) in A3_ARMS.items():
            if len(branches[arm]) != 1:
                problems.append(f"A3 s{s} {arm}: {len(branches[arm])} complete copies")
                ok = False
                continue
            d = branches[arm][0]
            sm = json.loads((d / "summary.json").read_text())
            cf = json.loads((d / "config.resolved.json").read_text())
            if Path(sm["probe_run"]) != probe or sm["fork_hash"] != ps["fork_hash"]:
                problems.append(f"A3 s{s} {arm}: lineage")
                ok = False
            if (sm["seed"], sm["arm"], sm["K"], sm["bc_update"], sm["alpha"], sm["anchor_component"]) != (s, tag, 3, 4000, 0.0, comp) \
                    or not close(sm["kl_coef"], base, 1e-15) or not all(close(x, y, 1e-15) for x, y in zip(sm["kl_effective_prefix_suffix"], eff)):
                problems.append(f"A3 s{s} {arm}: identity")
                ok = False
            if (cf["eval_role"], cf["bank_role"], cf["eval_seed"], cf["dataset_id"]) != ("a3_final", "a3_bank", 959000, "r3-v1"):
                problems.append(f"A3 s{s} {arm}: evaluation roles")
                ok = False
            steps_ok += check_steps(d, sm, problems, "A3")
            for et in A3_TAGS:
                rs = rows(d / f"attempts_{et}.jsonl")
                nrm = [r for r in rs if r["kind"] == "normal"]
                bank = [r for r in rs if r["kind"] == "bank"]
                if len(nrm) != 512 or len(bank) != 256:
                    problems.append(f"A3 s{s} {arm} {et}: {len(nrm)} normal, {len(bank)} bank rows")
                    ok = False
                    continue
                lim = {r["item"]: r["limit"] for r in nrm}
                if [lim[i] for i in range(128)] != k3:
                    problems.append(f"A3 s{s} {arm} {et}: panel limits differ from the a3_final K=3 registry")
                panels.add(tuple(sorted((r["item"], r["attempt"], r["limit"]) for r in nrm)))
                if engineering:
                    continue
                p1 = mean([r["success"] for r in nrm])
                q = mean([r["arrival"] is not None for r in nrm])
                c = mean([r["success"] for r in bank])
                e = next(x for x in sm["evals"] if x["tag"] == et)
                if not (close(p1, e["P1"]) and close(q, e["q"]) and close(c, e["c"])):
                    problems.append(f"A3 s{s} {arm} {et}: summary mismatch")
                P[(s, arm, et)] = p1
        if ok:
            complete.append(s)
    out = {"seeds_complete": complete, "n_complete": len(complete), "distinct_panels": len(panels),
           "step_records_equal_summary_jobs": steps_ok}
    if engineering or len(complete) != len(A3_SEEDS):
        out["outcomes"] = "not computed (engineering mode or fewer than 24 complete seeds)"
        return out
    d = [P[(s, "C", "final_251904")] - P[(s, "A", "final_251904")] for s in complete]
    h1 = {**ttest(d), "signflip_p": signflip(d), "n_positive": int(sum(x > 0 for x in d))}
    h1["decision"] = "supported" if h1["lo"] > 0 else ("negative effect supported" if h1["hi"] < 0 else "not supported")
    con = {}
    for et in A3_TAGS:
        for name, w in A3_W.items():
            con[f"{et}/{name}"] = ttest([sum(c * P[(s, a, et)] for a, c in w.items()) for s in complete])
    gate = None
    if h1["decision"] == "supported":
        ps_ = sorted([("C-D", con["final_251904/C-D"]["p"]), ("C-E", con["final_251904/C-E"]["p"])], key=lambda x: x[1])
        adj, run = {}, 0.0
        for i, (n, p) in enumerate(ps_):
            run = max(run, min(1.0, (2 - i) * p))
            adj[n] = run
        gate = {n: {"holm_p": adj[n], "supported": adj[n] < 0.05} for n in adj}
    ref = json.loads((ROOT / "reports/a3/a3_summary.json").read_text())
    agree = {k: close(h1[a], ref["H1"][k], 1e-6) for a, k in (("estimate", "estimate"), ("sd", "sd"), ("p", "p"),
                                                               ("lo", "t95_lo"), ("hi", "t95_hi"), ("signflip_p", "signflip_p_exact"))}
    agree["decision"] = h1["decision"] == ref["H1"]["decision"]
    ep = {"final_251904": "E250", "final_501760": "E500"}
    agree["contrasts"] = all(close(v["estimate"], ref["secondary_contrasts"][ep[k.split("/")[0]]][k.split("/", 1)[1]]["P1"]["estimate"], 1e-9)
                             for k, v in con.items())
    if not all(agree.values()):
        problems.append(f"A3 disagrees with analyze_a3: {agree}")
    return {**out, "H1": h1, "contrasts": con, "gate": gate, "agrees_with_analyze_a3": agree}


def verify_cal(problems):
    ref_path = ROOT / "reports/cal/cal_summary.json"
    if not ref_path.exists():
        return None
    ref = json.loads(ref_path.read_text())
    T = {"K1_q_min": 0.75, "K3_q_min": 0.05, "K3_q_max": 0.40, "entry_min": 0.55, "P1_max": 0.60}
    per, steps_ok = {}, 0
    for p, rho in ((2, 0.2), (5, 0.5), (8, 0.8)):
        for s in (67, 68, 69):
            d = one(f"cal-bc-p{p}-s{s}", problems, "CAL")
            if d is None:
                continue
            cf = json.loads((d / "config.resolved.json").read_text())
            if (cf["prefix_prob"], cf["seed"], cf["checkpoints"], cf["eval_seed"]) != (rho, s, [4000, 8000], 525000):
                problems.append(f"CAL {d.name}: config")
            for u in (4000, 8000):
                rs = rows(d / f"attempts_u{u}.jsonl")
                for K in (1, 3):
                    nrm = [r for r in rs if r["kind"] == "normal" and r["K"] == K]
                    bank = [r for r in rs if r["kind"] == "bank" and r["bank_K"] == K]
                    if len(nrm) != 200 or len(bank) != 256:
                        problems.append(f"CAL {d.name} u{u} K{K}: {len(nrm)} normal, {len(bank)} bank rows")
                        continue
                    per[(rho, u, s, K)] = {"P1": mean([r["success"] for r in nrm]), "q": mean([r["arrival"] is not None for r in nrm]),
                                           "entry": mean([r["success"] for r in bank if r["bin"] == "entry"])}
    variants, ok_all = {}, True
    for rho in (0.2, 0.5, 0.8):
        for u in (4000, 8000):
            if not all((rho, u, s, K) in per for s in (67, 68, 69) for K in (1, 3)):
                continue
            m = {K: {k: mean([per[(rho, u, s, K)][k] for s in (67, 68, 69)]) for k in ("P1", "q", "entry")} for K in (1, 3)}
            q = (m[1]["q"] >= T["K1_q_min"] and T["K3_q_min"] <= m[3]["q"] <= T["K3_q_max"]
                 and all(m[K]["entry"] >= T["entry_min"] and m[K]["P1"] <= T["P1_max"] for K in (1, 3)))
            variants[(rho, u)] = q
            r = ref["variants"].get(f"rho{rho}/u{u}")
            same = r is not None and r["qualifies"] == q and all(
                close(m[K][k], r["means"][str(K)][k]) for K in (1, 3) for k in ("P1", "q", "entry"))
            ok_all &= same
            if not same:
                problems.append(f"CAL rho{rho}/u{u} disagrees with analyze_cal")
    okv = [k for k, v in variants.items() if v]
    sel = min(okv, key=lambda k: (k[1], abs(k[0] - 0.5), k[0])) if okv else None
    sel = None if sel is None else {"rho": sel[0], "update": sel[1]}
    if sel != ref["selected"]:
        problems.append(f"CAL selection {sel} != analyze_cal {ref['selected']}")
    return {"variants_qualifying": {f"rho{r}/u{u}": v for (r, u), v in variants.items()}, "selected": sel,
            "agrees_with_analyze_cal": ok_all and sel == ref["selected"]}


def verify_pilot(problems):
    ref_path = ROOT / "reports/pilot/pilot_summary.json"
    if not ref_path.exists():
        return None
    ref = json.loads(ref_path.read_text())
    sel = json.loads((ROOT / "reports/cal/cal_summary.json").read_text())["selected"]
    p_of = {0.2: 2, 0.5: 5, 0.8: 8}
    out, P = {}, {}
    for K in (1, 3):
        for s in (67, 68, 69):
            probe = one(f"pl-probe-K{K}-s{s}", problems, "PL")
            if probe is None:
                continue
            ps = json.loads((probe / "summary.json").read_text())
            pc = json.loads((probe / "config.resolved.json").read_text())
            if not str(pc["bc_run"]).endswith(f"cal-bc-p{p_of[sel['rho']]}-s{s}") or ps["bc_update"] != sel["update"] or ps["K"] != K:
                problems.append(f"PL K{K} s{s}: probe lineage (selected variant)")
            for arm, (alpha, base, comp) in PL_ARMS.items():
                d = one(f"pl-K{K}-s{s}-{arm}", problems, "PL")
                if d is None:
                    continue
                sm = json.loads((d / "summary.json").read_text())
                if Path(sm["probe_run"]) != probe or sm["fork_hash"] != ps["fork_hash"]:
                    problems.append(f"PL K{K} s{s} {arm}: lineage")
                if (sm["arm"], sm["K"], sm["seed"], sm["anchor_component"]) != (arm, K, s, comp) or not close(sm["alpha"], alpha) \
                        or not close(sm["kl_coef"], base):
                    problems.append(f"PL K{K} s{s} {arm}: identity")
                rs = rows(d / "attempts_pilot_251904.jsonl")
                nrm = [r for r in rs if r["kind"] == "normal"]
                if len(nrm) != 256 or any(r["K"] != K for r in nrm):
                    problems.append(f"PL K{K} s{s} {arm}: {len(nrm)} normal rows or wrong K")
                    continue
                P[(K, s, arm)] = mean([r["success"] for r in nrm])
                e = next(x for x in sm["evals"] if x["tag"] == "pilot_251904")
                if not close(P[(K, s, arm)], e["P1"]):
                    problems.append(f"PL K{K} s{s} {arm}: summary mismatch")
        for name, w in PL_W.items():
            ss = [s for s in (67, 68, 69) if all((K, s, a) in P for a in w)]
            v = [sum(c * P[(K, s, a)] for a, c in w.items()) for s in ss]
            if not v:
                continue
            r = ref["conditions"].get(f"K{K}", {}).get("contrasts", {}).get(name, {}).get("P1", {})
            ok = close(mean(v), r.get("estimate", np.mean(r.get("per_seed", [np.nan]))), 1e-9)
            if not ok:
                problems.append(f"PL K{K} {name} disagrees with analyze_pilot")
            out[f"K{K}/{name}"] = {"per_seed": v, "mean": mean(v), "agrees": ok}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--engineering", action="store_true", help="inventory, lineage, identity, roles, panels and steps only")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    problems = []
    res = {"a3": verify_a3(problems, a.engineering)}
    if not a.engineering:
        res["cal"], res["pilot"] = verify_cal(problems), verify_pilot(problems)
    res["problems"] = problems
    name = "verification_engineering.json" if a.engineering else "verification.json"
    (OUT / name).write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: (v if k != "a3" else {x: v[x] for x in v if x not in ("contrasts",)}) for k, v in res.items()}, indent=1, default=float))


if __name__ == "__main__":
    main()
