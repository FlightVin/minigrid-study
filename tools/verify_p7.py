"""Independent recomputation for the corrective prefix imitation study (owner instruction 2026-11-02c, section 10;
Amendment 9). Shares no code with tools/analyze_p7.py. No actions.

Usage: .venv/bin/python tools/verify_p7.py gate   -> reports/p7/gate_verification.json
       .venv/bin/python tools/verify_p7.py final  -> reports/p7/verification.json

Shared upstream data: the raw attempts_*.jsonl rows, branch summaries, aux_schedule.json files and env_steps records
(the same files the analysis reads). Independent here: run-directory discovery, success aggregation (plain counts per
layout), seed means, contrasts, the gate and selection rules (restated from PROTOCOL_FREEZE Amendment 9), the
fixed-sequence confirmation decision with its own t-quantile (series integration), the per-update matching of R to
C, and executed-action totals per job against the step records. The eval replay job (bc2rl.eval_replay) re-executes a
sample of evaluation episodes in fresh environments and is the independent check of recorded outcomes.
"""
import json
from math import gamma, pi, sqrt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/p7"


def runs(job):
    found = []
    for pat in (job, job + "-r*"):
        for d in (ROOT / ".mae/runs").glob(f"*/{pat}"):
            if (d / "summary.json").exists():
                found.append(d)
    found.sort()
    return found


def seed_p1(path):
    succ, cnt = {}, {}
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["kind"] != "normal":
                continue
            succ[r["item"]] = succ.get(r["item"], 0) + (1 if r["success"] else 0)
            cnt[r["item"]] = cnt.get(r["item"], 0) + 1
    return sum(succ[i] / cnt[i] for i in cnt) / len(cnt), len(cnt), sum(cnt.values())


def student_cdf_two_sided(t, df, steps=400_000):
    c = gamma((df + 1) / 2) / (sqrt(df * pi) * gamma(df / 2))
    h = abs(t) / steps
    s = 0.0
    for k in range(steps + 1):
        x = k * h
        w = 1 if k in (0, steps) else (4 if k % 2 else 2)
        s += w * c * (1 + x * x / df) ** (-(df + 1) / 2)
    return 1 - 2 * s * h / 3


def mean(v):
    return sum(v) / len(v)


def actions_check(d):
    s = json.loads((d / "summary.json").read_text())
    rec = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
    return rec, sum(s["actions"].values()) if isinstance(s.get("actions"), dict) else None


def collect(prefix, seeds, arms, tag):
    P, probs, acts = {}, [], {}
    for s in seeds:
        for a in arms:
            ds = runs(f"{prefix}-K3-s{s}-{a}")
            if len(ds) != 1:
                probs.append(f"{prefix} s{s} {a}: {len(ds)} complete runs")
                continue
            d = ds[0]
            for at in (251904, 501760):
                P[(s, a, at)], n_lay, n_rows = seed_p1(d / f"attempts_{tag}_{at}.jsonl")
            rec, summ = actions_check(d)
            acts[f"{s}-{a}"] = rec
            if rec != summ:
                probs.append(f"s{s} {a}: step records {rec} vs summary {summ}")
        if "C7" in arms and "R7" in arms and not probs:
            c = json.loads((runs(f"{prefix}-K3-s{s}-C7")[0] / "aux_schedule.json").read_text())["labelled_per_update"]
            r = json.loads((runs(f"{prefix}-K3-s{s}-R7")[0] / "aux_schedule.json").read_text())["labelled_per_update"]
            if c != r:
                probs.append(f"s{s}: R7 schedule differs from C7")
            q = json.loads((runs(f"{prefix}-K3-s{s}-C7")[0] / "summary.json").read_text())["aux"]["queried_states"]
            if q > 75_000:
                probs.append(f"s{s}: C7 queried {q}")
    return P, probs, acts


def gate():
    seeds, arms = list(range(116, 122)), ("00", "C7", "R7")
    P, probs, acts = collect("p7", seeds, arms, "dev")
    d = {k: [P[(s, x, 501760)] - P[(s, y, 501760)] for s in seeds] for k, (x, y) in
         {"C-A": ("C7", "00"), "R-A": ("R7", "00"), "C-R": ("C7", "R7")}.items()}
    ana = json.loads((OUT / "gate.json").read_text())
    fits = ana["fits"]          # budget fit uses the ledger at gate time (recorded by the analysis; checked below)
    q = {"C7": mean(d["C-A"]) >= 0.05 and sum(x > 0 for x in d["C-A"]) >= 4 and not probs and fits["C7"],
         "R7": mean(d["R-A"]) >= 0.05 and sum(x > 0 for x in d["R-A"]) >= 4 and not probs and fits["R7"]}
    sel = "C7" if q["C7"] and mean(d["C-R"]) >= 0.02 else ("R7" if q["R7"] else None)
    agree = (sel == ana["selected"] and all(abs(mean(d[k]) - ana[k]["mean"]) < 1e-12 for k in d)
             and ana["integrity_ok"] == (not probs))
    out = {"selected": sel, "agrees": agree, "means": {k: mean(v) for k, v in d.items()},
           "n_pos": {k: sum(x > 0 for x in v) for k, v in d.items()}, "qualifies": q, "problems": probs,
           "actions_by_branch": acts,
           "budget_fit_inputs": {"spent_at_gate": ana["spent_at_gate"], "confirmation_bound": ana["confirmation_bound"],
                                 "recomputed_fit": {a: ana["spent_at_gate"]["scientific"] + ana["confirmation_bound"][a]
                                                    + 400_000 <= 72_000_000 for a in ("C7", "R7")}}}
    out["agrees"] = agree and out["budget_fit_inputs"]["recomputed_fit"] == fits
    (OUT / "gate_verification.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("selected", "agrees", "means", "n_pos", "qualifies", "problems")}, indent=1))


def final():
    g = json.loads((OUT / "gate_verification.json").read_text())
    out = {"gate": g}
    problems = []
    sel = g["selected"]
    if sel:
        arms = ("00", "C7", "R7") if sel == "C7" else ("00", "R7")
        seeds = list(range(122, 142))
        P, probs, acts = collect("c7", seeds, arms, "conf")
        problems += probs
        ana = json.loads((OUT / "conf.json").read_text())
        pairs = {"C-A": ("C7", "00"), "C-R": ("C7", "R7"), "R-A": ("R7", "00")}
        res = {}
        for k, (x, y) in pairs.items():
            if x not in arms or y not in arms:
                continue
            d = [P[(s, x, 501760)] - P[(s, y, 501760)] for s in seeds]
            m = mean(d)
            sd = sqrt(sum((v - m) ** 2 for v in d) / (len(d) - 1))
            t = m / (sd / sqrt(len(d)))
            p = student_cdf_two_sided(t, len(d) - 1)
            res[k] = {"mean": m, "sd": sd, "t": t, "p": p}
            a = ana["contrasts"]["501760"][k]
            if abs(a["mean"] - m) > 1e-12 or abs(a["p_t"] - p) > 1e-4:
                problems.append(f"{k}: analysis {a['mean']}, {a['p_t']} vs {m}, {p}")
        if sel == "C7":
            dec = {"C-A_rejected": res["C-A"]["p"] < 0.05}
            dec["C-R_rejected"] = bool(dec["C-A_rejected"] and res["C-R"]["p"] < 0.05)
        else:
            dec = {"R-A_rejected": res["R-A"]["p"] < 0.05}
        for k, v in dec.items():
            if ana["primary"].get(k) != v:
                problems.append(f"decision {k} differs")
        out.update(confirmation=res, decision=dec, actions_by_branch=acts)
    rep = runs("p7-verify-replay")
    if rep:
        out["eval_replay"] = json.loads((rep[-1] / "summary.json").read_text())
        if out["eval_replay"]["mismatches"]:
            problems.append(f"eval replay mismatches {out['eval_replay']['mismatches']}")
    out["problems"] = problems
    out["agrees_with_analysis"] = not problems
    (OUT / "verification.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in out if k not in ("gate", "actions_by_branch")}, indent=1))


if __name__ == "__main__":
    {"gate": gate, "final": final}[sys.argv[1]]()
