"""Independent verification of the 2026-11-01 programme results (owner instruction section 5).
Independent of tools/analyze_r2.py, analyze_r1.py and r1_stats.py: reads raw attempt files, summaries, configs and
step records directly; own t CDF and interval (tools/audit_r1.py integration), own exact sign-flip enumeration.
No environment actions.

R2: inventory (20 seeds x {bc, probe, 00, 01}, no duplicates), lineage (branch probe_run and fork hash = the seed's
probe), arm identity, evaluation roles and seed, panel limits = r2_final K=3 registry and identical for every
branch, 512 normal + 256 bank rows per endpoint, P1/q recomputed and equal to the summary, paired d, t-test, 95%
interval, exact sign-flip p, exact decomposition, step records = summary actions, and the comparison with
reports/r2/r2_summary.json.
E1 / E2 (when present): attempt-level recomputation of every policy/branch P1 and q, the cell / contrast means,
and comparison with reports/crosspanel and reports/comp.
Usage: .venv/bin/python tools/verify_program.py  -> reports/program/verification.json
"""
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_r1 import t_two_sided_p    # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
OUT = ROOT / "reports/program"
ARMS = {"00": "00", "01": "01-kl0p01"}


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
    hits = [d for d in RUNS.glob(f"*/{name}") if (d / "summary.json").exists()]
    return hits


def pq(normal):
    n = len(normal)
    return sum(r["success"] for r in normal) / n, sum(r["arrival"] is not None for r in normal) / n, \
        (sum(r["success"] for r in normal) / sum(r["arrival"] is not None for r in normal)
         if any(r["arrival"] is not None for r in normal) else None)


def close(a, b, tol=1e-9):
    return abs(a - b) <= tol


def verify_r2(problems):
    reg = json.loads((ROOT / "data/r2-v1/layouts.json").read_text())
    k3 = [it["layout"]["limit"] for it in reg["r2_final"] if it["layout"]["K"] == 3]
    assert len(k3) == 128
    d500, dec, steps_eq, panels = [], [], 0, set()
    for s in range(23, 43):
        found = {}
        for j in [f"r2-bc-s{s}", f"r2-probe-K3-u4000-s{s}"] + [f"r2-K3-u4000-s{s}-{a}" for a in ARMS.values()]:
            h = find(j)
            if len(h) != 1:
                problems.append(f"R2 {j}: {len(h)} complete copies")
                continue
            found[j] = h[0]
            sm = json.loads((h[0] / "summary.json").read_text())
            st = sum(json.loads(p.read_text())["actions"] for p in (h[0] / "env_steps").glob("*.json"))
            if isinstance(sm.get("actions"), dict):
                steps_eq += st == sum(sm["actions"].values())
                if st != sum(sm["actions"].values()):
                    problems.append(f"R2 {j}: step records {st} != summary {sum(sm['actions'].values())}")
        probe = found.get(f"r2-probe-K3-u4000-s{s}")
        ps = json.loads((probe / "summary.json").read_text())
        P = {}
        for arm, name in ARMS.items():
            d = found[f"r2-K3-u4000-s{s}-{name}"]
            sm = json.loads((d / "summary.json").read_text())
            cf = json.loads((d / "config.resolved.json").read_text())
            if Path(sm["probe_run"]) != probe or sm["fork_hash"] != ps["fork_hash"]:
                problems.append(f"R2 s{s} {arm}: lineage")
            if (sm["seed"], sm["arm"], sm["K"], sm["bc_update"], sm["kl_coef"], sm["alpha"]) != \
                    (s, arm, 3, 4000, 0.01 if arm == "01" else 0.0, 0.0):
                problems.append(f"R2 s{s} {arm}: identity")
            if (cf["eval_role"], cf["bank_role"], cf["eval_seed"]) != ("r2_final", "r2_bank", 949000):
                problems.append(f"R2 s{s} {arm}: evaluation roles")
            for tag in ("final_251904", "final_501760"):
                rs = rows(d / f"attempts_{tag}.jsonl")
                nrm = [r for r in rs if r["kind"] == "normal"]
                bank = [r for r in rs if r["kind"] == "bank"]
                if len(nrm) != 512 or len(bank) != 256:
                    problems.append(f"R2 s{s} {arm} {tag}: {len(nrm)} normal, {len(bank)} bank rows")
                lim = {}
                for r in nrm:
                    lim[r["item"]] = r["limit"]
                if [lim[i] for i in range(128)] != k3:
                    problems.append(f"R2 s{s} {arm} {tag}: panel limits differ from the r2_final K=3 registry")
                panels.add(tuple(sorted((r["item"], r["attempt"], r["limit"]) for r in nrm)))
                p, q, r = pq(nrm)
                e = next(x for x in sm["evals"] if x["tag"] == tag)
                if not (close(p, e["P1"]) and close(q, e["q"])):
                    problems.append(f"R2 s{s} {arm} {tag}: summary mismatch")
                if tag == "final_501760":
                    P[arm] = (p, q, r)
        d500.append(P["01"][0] - P["00"][0])
        (p1, q1, r1), (p0, q0, r0) = P["01"], P["00"]
        if r1 is not None and r0 is not None:
            dec.append(((q1 - q0) * (r1 + r0) / 2, (r1 - r0) * (q1 + q0) / 2))
    t = ttest(d500)
    t["signflip_p"] = signflip(d500)
    ref = json.loads((ROOT / "reports/r2/r2_summary.json").read_text())["E500"]
    agree = {k: close(t[a], ref[k], 1e-6) for a, k in (("estimate", "estimate"), ("sd", "sd"), ("p", "p"),
                                                         ("lo", "t95_lo"), ("hi", "t95_hi"), ("signflip_p", "signflip_p_exact"))}
    if not all(agree.values()):
        problems.append(f"R2 primary disagrees with analyze_r2: {agree}")
    acc, com = np.array(dec).T
    return {"primary_E500": t, "agrees_with_analyze_r2": agree, "panels_distinct": len(panels),
            "n_seeds": len(d500), "n_positive": int((np.array(d500) > 0).sum()),
            "decomposition": {"n_defined": len(dec), "access_mean": float(acc.mean()), "completion_mean": float(com.mean()),
                              "sum_equals_d": bool(close(acc.mean() + com.mean(), float(np.mean(d500)), 1e-12))},
            "step_records_equal_summary_jobs": steps_eq}


def verify_xp(problems):
    ref_path = ROOT / "reports/crosspanel/crosspanel_summary.json"
    if not ref_path.exists():
        return None
    ref = json.loads(ref_path.read_text())["cells"]
    cohorts = {"m4": range(10, 15), "r1": range(15, 23)}
    out = {}
    for co, seeds in cohorts.items():
        for pn, n in (("conf_final", 64), ("r1_final", 128)):
            d = []
            for s in seeds:
                P = {}
                for arm in ARMS:
                    h = find(f"xp-{co}-s{s}-{arm}")
                    if len(h) != 1:
                        problems.append(f"E1 xp-{co}-s{s}-{arm}: {len(h)} copies")
                        continue
                    nrm = rows(h[0] / f"attempts_crosspanel_{pn}.jsonl")
                    if len(nrm) != 4 * n:
                        problems.append(f"E1 xp-{co}-s{s}-{arm} {pn}: {len(nrm)} rows")
                    P[arm] = sum(r["success"] for r in nrm) / len(nrm)
                if len(P) == 2:
                    d.append(P["01"] - P["00"])
            t = ttest(d)
            c = ref.get(f"{co}/{pn}")
            ok = c is not None and close(t["estimate"], c["d"]["estimate"], 1e-9) and close(t["p"], c["d"]["p"], 1e-6)
            if not ok:
                problems.append(f"E1 {co}/{pn} disagrees with analyze_crosspanel")
            out[f"{co}/{pn}"] = {**t, "agrees": ok}
    return out


def verify_comp(problems):
    ref_path = ROOT / "reports/comp/comp_summary.json"
    if not ref_path.exists():
        return None
    ref = json.loads(ref_path.read_text())["contrasts"]
    P = {}
    for s in (15, 16, 17):
        for arm in ("00", "01p", "01s", "01"):
            h = find(f"comp-K3-u4000-s{s}-{arm}")
            if len(h) != 1:
                problems.append(f"E2 comp s{s} {arm}: {len(h)} copies")
                continue
            nrm = [r for r in rows(h[0] / "attempts_comp_251904.jsonl") if r["kind"] == "normal"]
            if len(nrm) != 128:
                problems.append(f"E2 comp s{s} {arm}: {len(nrm)} normal rows")
            P[(s, arm)] = sum(r["success"] for r in nrm) / len(nrm)
    W = {"prefix": {"01p": 1, "00": -1}, "suffix": {"01s": 1, "00": -1}, "both": {"01": 1, "00": -1},
         "interaction": {"01": 1, "01p": -1, "01s": -1, "00": 1}}
    out = {}
    for name, w in W.items():
        v = [sum(c * P[(s, a)] for a, c in w.items()) for s in (15, 16, 17)]
        ok = close(float(np.mean(v)), ref[name]["P1"]["estimate"], 1e-9)
        if not ok:
            problems.append(f"E2 {name} disagrees with analyze_comp")
        out[name] = {"per_seed": v, "mean": float(np.mean(v)), "agrees": ok}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    problems = []
    res = {"r2": verify_r2(problems), "crosspanel": verify_xp(problems), "comp": verify_comp(problems)}
    res["problems"] = problems
    (OUT / "verification.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
