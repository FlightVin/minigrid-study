"""Independent verification of the A4 results (owner instruction 2026-11-01c, section 10). Shares no code with
tools/analyze_a4.py or r1_stats.py: own lineage resolution (summary/config resumed_from links), own metric
recomputation from raw attempt rows, own t interval (tools/audit_r1.py t CDF), own exact sign-flip. No actions.

Usage: .venv/bin/python tools/verify_a4.py [--engineering]  -> reports/a4/verification.json
Checks per seed: one complete BC and probe, both branches complete through their lineage, identity (arm, alpha,
effective coefficients, fork hash, roles, eval seed), panel limits = a4_final K=3 registry, row counts (512 normal,
256 entry, 2n arrival), step records = summary actions for every completed job. Unless --engineering, and only with
all 20 seeds: P1, q, r, entry and arrival-bank competence for both arms at the three endpoints; d at each endpoint;
H1 t-test, interval and exact sign-flip; H2 (if gated in); decomposition sums; agreement with reports/a4/a4_summary.json.
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
SEEDS = range(70, 90)
EPS = (251904, 501760, 1001472)
EFF = {"00": [0.0, 0.0], "01s": [0.0, 0.0075]}


def t_crit(df):
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_two_sided_p(mid, df) > 0.05 else (lo, mid)
    return (lo + hi) / 2


def ttest(x):
    x = np.asarray(x, float)
    n, m, sd = len(x), x.mean(), x.std(ddof=1)
    se = sd / sqrt(n)
    c = t_crit(n - 1)
    return {"n": n, "estimate": float(m), "sd": float(sd), "p": float(t_two_sided_p(m / se, n - 1)),
            "lo": float(m - c * se), "hi": float(m + c * se)}


def signflip(x):
    x = np.asarray(x, float)
    n, obs, cnt = len(x), abs(x.sum()), 0
    for st in range(0, 2 ** n, 2 ** 16):
        idx = np.arange(st, min(st + 2 ** 16, 2 ** n))
        sg = 1 - 2 * ((idx[:, None] >> np.arange(n)) & 1)
        cnt += int((np.abs(sg @ x) >= obs - 1e-12).sum())
    return cnt / 2 ** n


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def dirs(name):
    return sorted(d for d in RUNS.glob(f"*/{name}") if d.is_dir())


def chain_of(s, arm):
    base = f"a4-K3-s{s}-{arm}"
    all_ = dirs(base) + [d for k in range(1, 10) for d in dirs(f"{base}-r{k}")]
    ends = [d for d in all_ if (d / "summary.json").exists() and json.loads((d / "summary.json").read_text())["continuation_actions"] == EPS[-1]]
    if len(ends) != 1:
        return None
    out, d = [], ends[0]
    while d is not None:
        meta = json.loads((d / "summary.json").read_text()) if (d / "summary.json").exists() else json.loads((d / "config.resolved.json").read_text())
        src = meta.get("resumed_from")
        if src:
            import torch
            sv = torch.load(src, map_location="cpu", weights_only=False)
            out.append((d, sv["meta"]["post_probe_actions"], meta))
            d = Path(src).parent
        else:
            out.append((d, 0, meta))
            d = None
    return out[::-1]


def owner_of(chain, at):
    for k, (d, start, _) in enumerate(chain):
        end = chain[k + 1][1] if k + 1 < len(chain) else 10 ** 9
        if start < at <= end:
            return d
    return None


def stage(rows):
    n = [r for r in rows if r["kind"] == "normal"]
    e = [r for r in rows if r["kind"] == "bank"]
    a = [r for r in rows if r["kind"] == "bank_extra"]
    arr = [r for r in n if r["arrival"] is not None]
    return {"P1": sum(r["success"] for r in n) / len(n), "q": len(arr) / len(n),
            "r": (sum(r["success"] for r in arr) / len(arr)) if arr else None,
            "entry": sum(r["success"] for r in e) / len(e), "arrival_bank": sum(r["success"] for r in a) / len(a),
            "counts": (len(n), len(e), len(a))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engineering", action="store_true")
    a = ap.parse_args()
    problems, M, complete = [], {}, []
    n_arr = len(json.loads((ROOT / "data/a4-arrival-v1/arrival_bank.json").read_text())["states"])
    lim = [it["layout"]["limit"] for it in json.loads((ROOT / "data/r4-v1/layouts.json").read_text())["a4_final"] if it["layout"]["K"] == 3]
    step_eq = 0
    for s in SEEDS:
        pr = [d for d in dirs(f"a4-probe-K3-s{s}") if (d / "summary.json").exists()]
        bc = [d for d in dirs(f"a4-bc-s{s}") if (d / "summary.json").exists()]
        if len(pr) != 1 or len(bc) != 1:
            if pr or bc:
                problems.append(f"s{s}: {len(bc)} complete BC, {len(pr)} complete probes")
            continue
        fork = json.loads((pr[0] / "summary.json").read_text())["fork_hash"]
        ok = True
        for arm in ("00", "01s"):
            ch = chain_of(s, arm)
            if ch is None:
                ok = False
                continue
            for d, _, meta in ch:
                cf = json.loads((d / "config.resolved.json").read_text())
                if (meta["arm"], meta["alpha"], list(meta["kl_effective_prefix_suffix"]), meta["fork_hash"], cf["eval_role"],
                        cf["bank_role"], cf["eval_seed"], cf["dataset_id"]) != (arm, 0.0, EFF[arm], fork, "a4_final", "a4_bank", 969000, "r4-v1"):
                    problems.append(f"s{s} {arm} identity {d.name}")
                if (d / "summary.json").exists():
                    sm = json.loads((d / "summary.json").read_text())
                    st = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
                    step_eq += st == sum(sm["actions"].values())
                    if st != sum(sm["actions"].values()):
                        problems.append(f"s{s} {arm} {d.name}: step records != summary")
            for at in EPS:
                d = owner_of(ch, at)
                rs = jl(d / f"attempts_final_{at}.jsonl")
                m = stage(rs)
                if m["counts"] != (512, 256, 2 * n_arr):
                    problems.append(f"s{s} {arm} {at}: rows {m['counts']}")
                li = {r["item"]: r["limit"] for r in rs if r["kind"] == "normal"}
                if [li[i] for i in range(256)] != lim:
                    problems.append(f"s{s} {arm} {at}: panel")
                M[(s, arm, at)] = m
        if ok:
            complete.append(s)
    res = {"complete_seeds": complete, "n_complete": len(complete), "step_records_equal_summary_jobs": step_eq}
    if a.engineering or len(complete) != 20:
        res["outcomes"] = "not computed (engineering mode or fewer than 20 complete seeds)"
    else:
        d = {at: [M[(s, "01s", at)]["P1"] - M[(s, "00", at)]["P1"] for s in complete] for at in EPS}
        h1 = {**ttest(d[EPS[-1]]), "signflip_p": signflip(d[EPS[-1]])}
        h1["decision"] = "supported" if h1["lo"] > 0 or h1["hi"] < 0 else "not supported"
        h2 = ttest(np.array(d[EPS[-1]]) - np.array(d[EPS[0]]))
        ref = json.loads((ROOT / "reports/a4/a4_summary.json").read_text())
        agree = {k: bool(abs(h1[x] - ref["H1"][k]) < 1e-6) for x, k in (("estimate", "estimate"), ("sd", "sd"), ("p", "p"),
                                                                   ("lo", "t95_lo"), ("hi", "t95_hi"), ("signflip_p", "signflip_p_exact"))}
        agree["decision"] = h1["decision"] == ref["H1"]["decision"]
        agree["H2_estimate"] = bool(abs(h2["estimate"] - ref["H2"]["estimate"]) < 1e-9)
        names = {251904: "E250", 501760: "E500", 1001472: "E1M"}
        for at in EPS:
            for m in ("P1", "q", "entry", "arrival_bank"):
                v = np.mean([M[(s, "01s", at)][m] - M[(s, "00", at)][m] for s in complete])
                agree[f"{names[at]}_{m}"] = bool(abs(v - ref["secondary"][names[at]][m]["estimate"]) < 1e-9)
        if not all(agree.values()):
            problems.append(f"disagrees with analyze_a4: {[k for k, v in agree.items() if not v]}")
        res.update(H1=h1, H2_descriptive_or_gated=h2, d_means={str(at): float(np.mean(d[at])) for at in EPS},
                   agrees_with_analyze_a4=agree)
    res["problems"] = problems
    (ROOT / "reports/a4").mkdir(parents=True, exist_ok=True)
    name = "verification_engineering.json" if a.engineering else "verification.json"
    (ROOT / "reports/a4" / name).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
