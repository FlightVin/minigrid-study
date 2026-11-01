"""Targeted R1 audit (owner instruction 2026-11-01, section 2). Independent of tools/analyze_r1.py: reads raw
attempt files, summaries, configs, step records and the layout registry directly. No environment actions.

Checks: exact job and endpoint-record inventory; seed grouping and fork lineage; evaluation roles (panel limit
fingerprint against the r1_final registry); P1 recomputation, paired t-tests and Holm-2 (own t CDF by numerical
integration, not tools/r1_stats.py); action counts (step records vs summaries vs ledger); failure record.
Also the exact descriptive decomposition dp = dq (r1 + r0)/2 + dr (q1 + q0)/2, r = P(success | actual arrival).

Usage: .venv/bin/python tools/audit_r1.py  -> reports/r1/audit.json, reports/r1/decomposition.csv, decomposition.md
"""
import csv
import json
from math import gamma, pi, sqrt
from pathlib import Path
import re

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
OUT = ROOT / "reports/r1"
SEEDS = range(15, 23)
CKPT = {"early": 4000, "extended": 16000}
ARMS = {"00": "00", "01": "01-kl0p01"}
EPS = {"E250": "final_251904", "E500": "final_501760"}
START_R1, END_R1 = 93_199_203, 118_670_302


def t_two_sided_p(t, df):
    """Two-sided p by Simpson integration of the Student t density (independent of r1_stats)."""
    c = gamma((df + 1) / 2) / (sqrt(df * pi) * gamma(df / 2))
    x = np.linspace(0, abs(t), 200001)
    f = c * (1 + x * x / df) ** (-(df + 1) / 2)
    h = x[1] - x[0]
    area = h / 3 * (f[0] + f[-1] + 4 * f[1:-1:2].sum() + 2 * f[2:-1:2].sum())
    return 1 - 2 * area


def ttest(d):
    d = np.asarray(d, float)
    n, m, sd = len(d), d.mean(), d.std(ddof=1)
    t = m / (sd / sqrt(n))
    return {"estimate": float(m), "sd": float(sd), "t": float(t), "p": float(t_two_sided_p(t, n - 1))}


def r1_batches():
    return sorted(p for p in RUNS.iterdir() if p.is_dir() and any(p.glob("r1-*")))


def main():
    problems = []
    inv = {"batches": [], "bc": [], "probe": [], "branch": [], "tests": [], "data": [], "incomplete": []}
    jobs = {}
    for b in r1_batches():
        inv["batches"].append(b.name)
        for d in sorted(b.glob("r1-*")):
            has = (d / "summary.json").exists()
            kind = ("bc" if d.name.startswith("r1-bc") else "probe" if d.name.startswith("r1-probe") else
                    "branch" if re.fullmatch(r"r1-K3-u\d+-s\d+-.*", d.name) else
                    "tests" if d.name == "r1-tests" else "data" if d.name.startswith("r1-data") else "other")
            done = has or (kind == "bc" and (d / "actor_u16000.pt").exists()) or kind in ("tests", "data")
            if not done:
                inv["incomplete"].append(f"{b.name}/{d.name}")
                continue
            inv[kind].append(f"{b.name}/{d.name}")
            if kind in ("bc", "probe", "branch"):
                if d.name in jobs:
                    problems.append(f"duplicate complete job {d.name}")
                jobs[d.name] = d

    # endpoint records
    reg = json.loads((ROOT / "data/r1-v1/layouts.json").read_text())
    k3_limits = [it["layout"]["limit"] for it in reg["r1_final"] if it["layout"]["K"] == 3]
    bank = json.loads((ROOT / "data/r1-v1/bank_competence_r1_bank.json").read_text())
    rec, endpoint_records, panels = {}, 0, set()
    for s in SEEDS:
        for ck, u in CKPT.items():
            probe = jobs.get(f"r1-probe-K3-u{u}-s{s}")
            ps = json.loads((probe / "summary.json").read_text())
            pc = json.loads((probe / "config.resolved.json").read_text())
            if (ps["seed"], ps["bc_update"], ps["K"]) != (s, u, 3):
                problems.append(f"probe {probe.name} identity")
            ref = pc["bc_run"]          # "@/<job>" = same batch; "<batch>/<job>" = earlier batch (seed 15 canary)
            bc = probe.parent / ref[2:] if ref.startswith("@/") else RUNS / ref
            if not bc.exists() or bc.name != f"r1-bc-s{s}":
                problems.append(f"probe {probe.name} bc lineage {pc['bc_run']}")
            for arm, tag in ARMS.items():
                d = jobs[f"r1-K3-u{u}-s{s}-{tag}"]
                sm = json.loads((d / "summary.json").read_text())
                cf = json.loads((d / "config.resolved.json").read_text())
                if (sm["seed"], sm["bc_update"], sm["arm"], sm["alpha"]) != (s, u, arm, 0.0):
                    problems.append(f"{d.name} identity")
                if sm["kl_coef"] != (0.01 if arm == "01" else 0.0):
                    problems.append(f"{d.name} kl_coef {sm['kl_coef']}")
                if sm["fork_hash"] != ps["fork_hash"] or Path(sm["probe_run"]).name != probe.name:
                    problems.append(f"{d.name} fork lineage")
                if (cf["dataset_id"], cf["eval_role"], cf["bank_role"], cf["diag_role"]) != ("r1-v1", "r1_final", "r1_bank", "r1_select"):
                    problems.append(f"{d.name} roles")
                for ep, t in EPS.items():
                    rows = [json.loads(l) for l in (d / f"attempts_{t}.jsonl").read_text().splitlines() if l.strip()]
                    nrm = [r for r in rows if r["kind"] == "normal"]
                    bk = [r for r in rows if r["kind"] == "bank"]
                    endpoint_records += 1
                    if len(nrm) != 512 or len(bk) != 256:
                        problems.append(f"{d.name} {t} counts {len(nrm)}/{len(bk)}")
                    lim = [None] * 128
                    for r in nrm:
                        lim[r["item"]] = r["limit"]
                        if r["success"] and not r["accessed"]:
                            problems.append(f"{d.name} success without arrival")
                    if lim != k3_limits:
                        problems.append(f"{d.name} {t} panel limits differ from r1_final K=3 registry")
                    panels.add(tuple((r["item"], r["attempt"], r["limit"]) for r in sorted(nrm, key=lambda r: (r["item"], r["attempt"]))))
                    q = np.mean([r["accessed"] for r in nrm])
                    succ = sum(r["success"] for r in nrm)
                    arr = sum(r["accessed"] for r in nrm)
                    P1 = succ / 512
                    e = next(x for x in sm["evals"] if x["tag"] == t)
                    if abs(e["P1"] - P1) > 1e-12 or abs(e["q"] - q) > 1e-12:
                        problems.append(f"{d.name} {t} summary P1/q mismatch")
                    rec[(s, ck, arm, ep)] = {"P1": P1, "q": q, "r": succ / arr if arr else None,
                                             "arrivals": arr, "successes": succ,
                                             "bank_c": np.mean([r["success"] for r in bk])}
    if len(panels) != 1:
        problems.append(f"{len(panels)} distinct normal panels across endpoint records")

    # primary statistics, independently
    stats = {}
    for ep in EPS:
        de = np.array([rec[(s, "early", "01", ep)]["P1"] - rec[(s, "early", "00", ep)]["P1"] for s in SEEDS])
        dx = np.array([rec[(s, "extended", "01", ep)]["P1"] - rec[(s, "extended", "00", ep)]["P1"] for s in SEEDS])
        stats[ep] = {"early": ttest(de), "extended": ttest(dx), "interaction": ttest(de - dx)}
    p1, p2 = stats["E500"]["early"]["p"], stats["E500"]["interaction"]["p"]
    lo, hi = sorted([p1, p2])
    holm_lo = min(1, 2 * lo)
    holm_hi = max(holm_lo, hi)
    stats["E500"]["holm"] = {"early": holm_lo if p1 <= p2 else holm_hi, "interaction": holm_lo if p2 < p1 else holm_hi}
    frozen = json.loads((OUT / "r1_summary.json").read_text())
    for k in ("early", "extended", "interaction"):
        if abs(frozen["E500"][k]["estimate"] - stats["E500"][k]["estimate"]) > 1e-12 or abs(frozen["E500"][k]["p"] - stats["E500"][k]["p"]) > 1e-6:
            problems.append(f"frozen E500 {k} differs from independent recomputation")
    for k in ("early", "interaction"):
        if abs(frozen["E500"][k]["p_holm"] - stats["E500"]["holm"][k]) > 1e-6:
            problems.append(f"frozen Holm {k} differs")

    # action counts
    acts = {}
    for b in r1_batches():
        for d in b.glob("r1-*"):
            st = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
            acts[f"{b.name}/{d.name}"] = st
    bc_cmp = {}
    for key in inv["bc"] + [x for x in inv["incomplete"] if "/r1-bc-" in x]:
        d = RUNS / key
        m = [json.loads(l) for l in (d / "metrics.jsonl").read_text().splitlines() if l.strip()]
        bc_cmp[key] = {"metrics_eval_env_actions": sum(r["eval_env_actions"] for r in m), "step_record": acts[key]}
    step_total = sum(acts.values())
    data_job = next(k for k in acts if "r1-data" in k)

    # failure record
    fb = RUNS / "20261101T005849-94851"
    led = [json.loads(l) for l in (ROOT / ".mae/ledger.jsonl").read_text().splitlines() if "94851" in l]

    # decomposition
    dec_rows = []
    for ep in EPS:
        for ck in CKPT:
            for s in SEEDS:
                a, o = rec[(s, ck, "01", ep)], rec[(s, ck, "00", ep)]
                dp = a["P1"] - o["P1"]
                dq = a["q"] - o["q"]
                if a["r"] is None or o["r"] is None:
                    dec_rows.append({"endpoint": ep, "checkpoint": ck, "seed": s, "dp": dp, "dq": dq, "access_part": None,
                                     "completion_part": None, "sum": None, "note": "r undefined (q = 0) in an arm"})
                    continue
                dr = a["r"] - o["r"]
                acc, comp = dq * (a["r"] + o["r"]) / 2, dr * (a["q"] + o["q"]) / 2
                if abs(acc + comp - dp) > 1e-12:
                    problems.append(f"decomposition identity fails s{s} {ck} {ep}")
                dec_rows.append({"endpoint": ep, "checkpoint": ck, "seed": s, "q0": o["q"], "q1": a["q"], "r0": o["r"],
                                 "r1": a["r"], "dp": dp, "dq": dq, "dr": dr, "access_part": acc, "completion_part": comp,
                                 "sum": acc + comp, "note": ""})
    dec_sum = {}
    for ep in EPS:
        for ck in CKPT:
            rows = [r for r in dec_rows if r["endpoint"] == ep and r["checkpoint"] == ck and r["sum"] is not None]
            blk = {"n_defined": len(rows)}
            for k in ("dp", "access_part", "completion_part"):
                v = np.array([r[k] for r in rows])
                blk[k] = {"mean": float(v.mean()), "sd": float(v.std(ddof=1)),
                          "t95": [float(v.mean() - 2.364624 * v.std(ddof=1) / sqrt(len(v))),
                                  float(v.mean() + 2.364624 * v.std(ddof=1) / sqrt(len(v)))],
                          "n_positive": int((v > 0).sum())}
            blk["share_access_of_mean_dp"] = blk["access_part"]["mean"] / blk["dp"]["mean"] if blk["dp"]["mean"] else None
            dec_sum[f"{ep}/{ck}"] = blk

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "decomposition.csv", "w", newline="") as f:
        cols = ["endpoint", "checkpoint", "seed", "q0", "q1", "r0", "r1", "dp", "dq", "dr", "access_part",
                "completion_part", "sum", "note"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in dec_rows:
            w.writerow({k: r.get(k) for k in cols})
    res = {
        "inventory": {"batches": len(inv["batches"]), "bc_complete": len(inv["bc"]), "probes": len(inv["probe"]),
                      "branches": len(inv["branch"]), "endpoint_records": endpoint_records,
                      "summaries_with_actions": len(inv["probe"]) + len(inv["branch"]),
                      "incomplete_jobs": inv["incomplete"], "tests_jobs": inv["tests"], "data_jobs": inv["data"],
                      "batch_ids": inv["batches"]},
        "panel_identical_across_records": len(panels) == 1,
        "independent_stats": stats,
        "bc_action_sources": bc_cmp,
        "step_record_total_r1_batches": step_total,
        "data_job_note": f"{data_job}: step record {acts[data_job]} (planner replay, ledger derives the same from layouts.json)",
        "ledger_r1_delta": END_R1 - START_R1,
        "failure": {"batch": fb.name, "ledger_records": led,
                    "job_files": sorted(p.name for p in (fb / "r1-bc-s17").iterdir())},
        "decomposition": dec_sum,
        "problems": problems,
    }
    (OUT / "audit.json").write_text(json.dumps(res, indent=1))
    return res


if __name__ == "__main__":
    r = main()
    print(json.dumps({k: r[k] for k in ("inventory", "panel_identical_across_records", "step_record_total_r1_batches",
                                        "ledger_r1_delta", "bc_action_sources", "problems")}, indent=1))
    print(json.dumps(r["decomposition"], indent=1))
