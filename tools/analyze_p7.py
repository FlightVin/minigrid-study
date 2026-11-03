"""Frozen analysis of the corrective prefix imitation study (owner instruction 2026-11-02c, sections 6-8;
PROTOCOL_FREEZE Amendment 9). No actions.

Usage:
  .venv/bin/python tools/analyze_p7.py dev         -> reports/p7/dev.{json,md}, reports/p7/gate.json
  .venv/bin/python tools/analyze_p7.py conf-check  -> completeness and integrity of the confirmation only (no outcomes)
  .venv/bin/python tools/analyze_p7.py conf        -> reports/p7/conf.{json,md} (refuses unless conf-check passes)

Unit of analysis: the training seed. Seed-level success P1 = mean over layouts of the per-layout attempt mean of
unassisted normal-start success (development: r7_dev 64 x 4; confirmation: r7_conf 256 x 2), at 501,760 continuation
actions (primary) and 251,904 (descriptive). Paired difference d_X(s) = P1_X(s) - P1_A(s).

Development gate (frozen; prospective spending rule, not a test):
  arm X in {C7, R7} qualifies if mean d_X >= 0.05, at least 4 of 6 d_X(s) > 0, the integrity checks pass, and the
  conservative cost of its confirmation fits the scientific cap (run_program7: scientific spent + confirmation
  bound + AUDIT <= 72,000,000).
  Select C7 if C7 qualifies and mean (P1_C - P1_R) >= 0.02; otherwise R7 if R7 qualifies; otherwise none.
Confirmation (frozen):
  C7 selected: test 1 = two-sided paired t over 20 seeds of P1_C - P1_A at 0.05; only if p < 0.05, test 2 = P1_C - P1_R
  at 0.05 (fixed sequence). R7 selected: one test of P1_R - P1_A. Estimates and 95% t intervals are reported for
  every contrast regardless of significance, with a crossed seed-and-layout bootstrap interval (10,000 resamples of
  seeds and layouts independently; panel-generalization scope) and an exact paired sign-flip p (2^20 sign vectors).
Secondary measures (descriptive, explicit counts): boundary reach q = A/n, completion after arrival r = S_A/A,
planner finishability F/A of actual arrivals, arrival time tau and remaining time at arrival, key pickups,
wrong-key pickups, key drops by door state, locked-door toggles, no-op actions; supervision cost and coverage;
update diagnostics; recovery-bank agreement.
"""
import argparse
import json
from math import sqrt
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))
from analyze_p6 import t_crit    # noqa: E402
from audit_r1 import t_two_sided_p    # noqa: E402

OUT = ROOT / "reports/p7"
DEV_SEEDS = list(range(116, 122))
CONF_SEEDS = list(range(122, 142))
ARMS = ("00", "C7", "R7")
NAME = {"00": "A", "C7": "C", "R7": "R"}
TARGET, MID = 501_760, 251_904
NB = 10_000
GAIN, POS, CR_MARGIN = 0.05, 4, 0.02


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def job_dir(name):
    """The single complete run directory of a job (documented retries carry -r<k> and are preferred if complete)."""
    good = []
    for d in sorted((ROOT / ".mae/runs").glob(f"*/{name}")) + sorted((ROOT / ".mae/runs").glob(f"*/{name}-r*")):
        s = d / "summary.json"
        if s.exists():
            good.append(d)
    return good[-1] if good else None


def per_layout(rows):
    s, k = {}, {}
    for r in rows:
        s[r["item"]] = s.get(r["item"], 0) + int(r["success"])
        k[r["item"]] = k.get(r["item"], 0) + 1
    items = sorted(s)
    assert len(set(k.values())) == 1, "unequal attempts per layout"
    return np.array([s[i] / k[i] for i in items]), items


def tsum(d):
    d = np.asarray(d, float)
    n, m = len(d), float(np.mean(d))
    sd = float(np.std(d, ddof=1)) if n > 1 else float("nan")
    se = sd / sqrt(n)
    c = t_crit(n - 1)
    return {"n": n, "mean": m, "sd": sd, "lo": m - c * se, "hi": m + c * se, "n_pos": int((d > 0).sum()),
            "p_t": float(t_two_sided_p(m / se, n - 1)) if se > 0 else None, "values": [float(x) for x in d]}


def sign_flip(d):
    """Exact two-sided paired sign-flip p over all 2^n sign vectors (chunks of 2^16)."""
    d = np.asarray(d, float)
    n, obs, hits = len(d), abs(d.sum()) - 1e-12, 0
    for start in range(0, 2 ** n, 2 ** 16):
        k = np.arange(start, min(2 ** n, start + 2 ** 16))
        signs = ((k[:, None] >> np.arange(n)) & 1) * 2 - 1
        hits += int((np.abs(signs @ d) >= obs).sum())
    return hits / 2 ** n


def crossed(D, rng):
    S, L = D.shape
    bs, bl = rng.integers(0, S, (NB, S)), rng.integers(0, L, (NB, L))
    m = np.array([D[bs[b]][:, bl[b]].mean() for b in range(NB)])
    return float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))


def secondary(rows):
    n = len(rows)
    arr = [r for r in rows if r["arrival"] is not None]
    A = len(arr)
    SA = sum(1 for r in arr if r["success"])
    F = sum(1 for r in arr if r["arrival"]["cert"]["status"] == "feasible")
    tr = [r["trace"] for r in rows]
    per = lambda f: float(np.mean([f(t) for t in tr]))
    kd = lambda k: per(lambda t: t["key_drops"][k])
    return {"n": n, "S": sum(int(r["success"]) for r in rows), "A": A, "S_A": SA, "F": F, "q": A / n,
            "r": SA / A if A else None, "F_over_A": F / A if A else None,
            "tau_mean": float(np.mean([r["arrival"]["tau"] for r in arr])) if arr else None,
            "remaining_mean": float(np.mean([r["arrival"]["remaining"] for r in arr])) if arr else None,
            "key_pickups": per(lambda t: len(t["key_pickups"])), "wrong_key_pickups": per(lambda t: t["wrong_key_pickups"]),
            "key_drops_premature": kd("premature"), "key_drops_unlocked_unpassed": kd("unlocked_unpassed"),
            "key_drops_obsolete": kd("obsolete"), "locked_toggles": per(lambda t: t["locked_toggles"]),
            "noop_actions": per(lambda t: t["noop_actions"])}


def update_diag(d):
    recs = [r for r in jl(d / "metrics.jsonl") if r.get("phase") == "branch"]
    keys = ("approx_kl", "clipfrac", "entropy", "grad_norm_actor", "pg_loss", "aux_ce", "aux_grad_norm", "pg_grad_norm",
            "aux_label_argmax", "update_kl_prefix", "update_kl_suffix", "actor_update_norm", "aux_n")
    out = {"updates": len(recs)}
    for k in keys:
        v = [r[k] for r in recs if k in r and r[k] is not None]
        if v:
            out[k] = {"mean": float(np.mean(v)), "max": float(np.max(v)), "first": float(v[0]), "last": float(v[-1])}
    return out


def load_seed(s, prefix, tag, arms=ARMS):
    """All records for one seed. Returns (record, problems)."""
    probs = []
    bc, probe = job_dir(f"{prefix}-bc-s{s}"), job_dir(f"{prefix}-probe-K3-s{s}")
    if bc is None or json.loads((bc / "summary.json").read_text()).get("updates") != 8000:
        probs.append("BC incomplete")
    psum = json.loads((probe / "summary.json").read_text()) if probe else None
    if psum is None:
        probs.append("probe incomplete")
    rec = {"seed": s, "arms": {}}
    for a in arms:
        d = job_dir(f"{prefix}-K3-s{s}-{a}")
        if d is None:
            probs.append(f"{a} missing")
            continue
        sm = json.loads((d / "summary.json").read_text())
        if sm.get("continuation_actions") != TARGET:
            probs.append(f"{a} continuation {sm.get('continuation_actions')}")
        if psum and sm["fork_hash"] != psum["fork_hash"]:
            probs.append(f"{a} fork hash differs from probe")
        steps = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json"))
        if steps != sum(sm["actions"].values()):
            probs.append(f"{a} actions {sum(sm['actions'].values())} vs step records {steps}")
        ev = {}
        for at in (MID, TARGET):
            rows = [r for r in jl(d / f"attempts_{tag}_{at}.jsonl") if r["kind"] == "normal"]
            pl, items = per_layout(rows)
            ev[at] = {"P1": float(pl.mean()), "per_layout": pl, "items": items, "rows": rows}
        rec["arms"][a] = {"dir": str(d.relative_to(ROOT)), "summary": sm, "eval": ev}
        if a == "C7":
            ax = sm["aux"]
            if ax["queried_states"] > 75_000:
                probs.append("C7 queried more than 75,000 states")
        if a == "R7":
            if not sm["aux"]["matched_to_C"]:
                probs.append("R7 not matched")
            if "C7" in arms and "C7" in rec["arms"]:
                sc = json.loads((ROOT / rec["arms"]["C7"]["dir"] / "aux_schedule.json").read_text())["labelled_per_update"]
                sr = json.loads((d / "aux_schedule.json").read_text())["labelled_per_update"]
                if sc != sr:
                    probs.append("R7 schedule differs from C7")
    if len(rec["arms"]) == len(arms):
        it = [rec["arms"][a]["eval"][TARGET]["items"] for a in arms]
        if any(x != it[0] for x in it):
            probs.append("evaluation panels differ")
        cfgs = {a: json.loads((ROOT / rec["arms"][a]["dir"] / "config.resolved.json").read_text()) for a in arms}
        skip = {"arm", "match_run", "kl_effective_prefix_suffix", "resumed_from", "resumed_hash", "anchors"}
        keys = set().union(*cfgs.values()) - skip
        diff = sorted(k for k in keys if len({json.dumps(cfgs[a].get(k), sort_keys=True) for a in arms}) > 1)
        if diff:
            probs.append(f"configs differ beyond the arm: {diff}")
    rec["probe"] = psum
    return rec, probs


def supervision(recs):
    out = {}
    for a in ("C7", "R7"):
        rows = [r["arms"][a]["summary"]["aux"] for r in recs]
        out[a] = rows
    return out


def arm_secondary(recs, at):
    out = {}
    for a in ARMS:
        pooled = [x for r in recs for x in r["arms"][a]["eval"][at]["rows"]]
        out[a] = {"pooled": secondary(pooled),
                  "per_seed": {r["seed"]: secondary(r["arms"][a]["eval"][at]["rows"]) for r in recs}}
    return out


def agreement(recs):
    out = {}
    for a in ARMS:
        out[a] = {r["seed"]: r["arms"][a]["summary"].get("recovery_agreement") for r in recs}
    return out


def fmt(x, nd=3, sign=False):
    return "—" if x is None else (f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}")


def dev():
    from run_program7 import AUDIT, SCI_CAP, confirmation_bound, spent
    recs, problems = [], {}
    for s in DEV_SEEDS:
        r, p = load_seed(s, "p7", "dev")
        recs.append(r)
        problems[s] = p
    ok = not any(problems.values())
    P = {at: {a: np.array([r["arms"][a]["eval"][at]["P1"] for r in recs]) for a in ARMS} for at in (MID, TARGET)}
    contr = {at: {"C-A": tsum(P[at]["C7"] - P[at]["00"]), "R-A": tsum(P[at]["R7"] - P[at]["00"]),
                  "C-R": tsum(P[at]["C7"] - P[at]["R7"])} for at in (MID, TARGET)}
    plan = json.loads((ROOT / "experiments/p7/plan.json").read_text())["batches"]
    sp = spent(plan)
    fits = {a: sp["scientific"] + confirmation_bound(a) + AUDIT <= SCI_CAP for a in ("C7", "R7")}
    c = contr[TARGET]
    qual = {"C7": c["C-A"]["mean"] >= GAIN and c["C-A"]["n_pos"] >= POS and ok and fits["C7"],
            "R7": c["R-A"]["mean"] >= GAIN and c["R-A"]["n_pos"] >= POS and ok and fits["R7"]}
    if qual["C7"] and c["C-R"]["mean"] >= CR_MARGIN:
        sel = "C7"
    elif qual["R7"]:
        sel = "R7"
    else:
        sel = None
    gate = {"rule": "qualify: mean gain over A >= 0.05, >= 4/6 positive, integrity, confirmation fits; C7 if it qualifies "
                    "and mean(C-R) >= 0.02, else R7 if it qualifies, else none",
            "C-A": {k: c["C-A"][k] for k in ("mean", "n_pos")}, "R-A": {k: c["R-A"][k] for k in ("mean", "n_pos")},
            "C-R": {k: c["C-R"][k] for k in ("mean", "n_pos")}, "integrity_ok": ok, "problems": problems,
            "spent_at_gate": sp, "confirmation_bound": {a: confirmation_bound(a) for a in ("C7", "R7")},
            "fits": fits, "qualifies": qual, "selected": sel}
    out = {"seeds": DEV_SEEDS, "P1": {str(at): {a: P[at][a].tolist() for a in ARMS} for at in P},
           "contrasts": {str(at): v for at, v in contr.items()}, "gate": gate,
           "secondary": {str(at): arm_secondary(recs, at) for at in (MID, TARGET)},
           "supervision": supervision(recs), "agreement": agreement(recs),
           "update_diagnostics": {a: {r["seed"]: update_diag(ROOT / r["arms"][a]["dir"]) for r in recs} for a in ARMS},
           "probe": {r["seed"]: {k: r["probe"][k] for k in ("pi0", "probe", "fork_hash")} for r in recs},
           "wall_seconds": {a: {r["seed"]: r["arms"][a]["summary"]["wall_seconds"] for r in recs} for a in ARMS}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "dev.json").write_text(json.dumps(out, indent=1, default=float))
    (OUT / "gate.json").write_text(json.dumps(gate, indent=1, default=float))
    md = ["# Development results (seeds 116-121; r7_dev 64 x 4; unassisted)", "",
          "| Seed | A @251,904 | R | C | A @501,760 | R | C | R−A | C−A | C−R |", "|---|---|---|---|---|---|---|---|---|---|"]
    for i, s in enumerate(DEV_SEEDS):
        md.append(f"| {s} | " + " | ".join(fmt(P[MID][a][i]) for a in ("00", "R7", "C7")) + " | "
                  + " | ".join(fmt(P[TARGET][a][i]) for a in ("00", "R7", "C7")) + " | "
                  + " | ".join(fmt(contr[TARGET][k]["values"][i], sign=True) for k in ("R-A", "C-A", "C-R")) + " |")
    for at in (MID, TARGET):
        md.append(f"| mean @{at:,} | " + " | ".join(fmt(P[at][a].mean()) for a in ("00", "R7", "C7")) + " | | | | "
                  + " | ".join(f"{fmt(contr[at][k]['mean'], sign=True)} [{fmt(contr[at][k]['lo'], sign=True)}, "
                               f"{fmt(contr[at][k]['hi'], sign=True)}] ({contr[at][k]['n_pos']}/6)"
                               for k in ("R-A", "C-A", "C-R")) + " |")
    md += ["", f"**Gate:** qualifies {qual}; fits {fits}; integrity {'ok' if ok else problems}; selected **{sel}**.",
           "Intervals are 95% t over 6 seeds (descriptive; the gate is a spending rule, not a test).", ""]
    sec = out["secondary"][str(TARGET)]
    md += ["## Secondary measures at 501,760 (pooled over seeds; explicit counts)", "",
           "| Arm | S/n | A/n (q) | S_A/A (r) | F/A | tau | remaining | key pickups | wrong-key pickups | drops premature "
           "| drops unlocked-unpassed | drops obsolete | locked toggles | no-ops |", "|---" * 15 + "|"]
    for a in ("00", "R7", "C7"):
        x = sec[a]["pooled"]
        md.append(f"| {NAME[a]} | {x['S']}/{x['n']} | {x['A']}/{x['n']} ({fmt(x['q'])}) | {x['S_A']}/{x['A']} "
                  f"({fmt(x['r'])}) | {x['F']}/{x['A']} | {fmt(x['tau_mean'], 1)} | {fmt(x['remaining_mean'], 1)} | "
                  f"{fmt(x['key_pickups'], 2)} | {fmt(x['wrong_key_pickups'], 2)} | {fmt(x['key_drops_premature'], 2)} | "
                  f"{fmt(x['key_drops_unlocked_unpassed'], 2)} | {fmt(x['key_drops_obsolete'], 2)} | "
                  f"{fmt(x['locked_toggles'], 2)} | {fmt(x['noop_actions'], 2)} |")
    md += ["", "## Supervision (per seed)", "",
           "| Seed | C queried | C labelled | C failed | exec in label | policy mass on label | conflicts | planner s | R examples |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in recs:
        cx, rx = r["arms"]["C7"]["summary"]["aux"], r["arms"]["R7"]["summary"]["aux"]
        md.append(f"| {r['seed']} | {cx['queried_states']} | {cx['labelled_examples']} | {cx['failed_queries']} | "
                  f"{fmt(cx['executed_action_in_label_set'])} | {fmt(cx['policy_mass_on_label_set'])} | "
                  f"{cx['observation_conflicts']} | {cx['planner']['planner_seconds']:.1f} | {rx['labelled_examples']} |")
    md += ["", "## Recovery-bank agreement (mass on label set; mean over seeds)", "",
           "| Arm | at fork | @251,904 | @501,760 |", "|---|---|---|---|"]
    for a in ("00", "R7", "C7"):
        g = [r["arms"][a]["summary"]["recovery_agreement"] for r in recs]
        md.append(f"| {NAME[a]} | " + " | ".join(fmt(np.mean([x[k]["mass"] for x in g])) for k in ("0", str(MID), str(TARGET)))
                  + " |")
    (OUT / "dev.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def conf_check():
    sel = json.loads((OUT / "gate.json").read_text())["selected"]
    assert sel in ("C7", "R7"), "no arm selected: no confirmation"
    arms = ("00", "C7", "R7") if sel == "C7" else ("00", "R7")
    problems = {}
    for s in CONF_SEEDS:
        p = []
        for a in arms:
            d = job_dir(f"c7-K3-s{s}-{a}")
            if d is None:
                p.append(f"{a} missing")
                continue
            sm = json.loads((d / "summary.json").read_text())
            if sm.get("continuation_actions") != TARGET:
                p.append(f"{a} incomplete")
            steps = sum(json.loads(x.read_text())["actions"] for x in (d / "env_steps").glob("*.json"))
            if steps != sum(sm["actions"].values()):
                p.append(f"{a} action records differ")
            if a == "R7" and not sm["aux"]["matched_to_C"]:
                p.append("R7 not matched")
            if a == "C7" and sm["aux"]["queried_states"] > 75_000:
                p.append("C7 cap exceeded")
        problems[s] = p
    ok = not any(problems.values())
    print(json.dumps({"selected": sel, "complete_and_integrity_ok": ok, "problems": problems}, indent=1))
    return ok, sel


def conf():
    ok, sel = conf_check()
    assert ok, "confirmation incomplete or integrity failed: outcomes stay blinded"
    rng = np.random.default_rng(20261102)
    recs = []
    for s in CONF_SEEDS:
        r, p = load_seed(s, "c7", "conf", ("00", "C7", "R7") if sel == "C7" else ("00", "R7"))
        assert not p, p
        recs.append(r)
    arms = ("00", "C7", "R7") if sel == "C7" else ("00", "R7")
    P = {at: {a: np.array([r["arms"][a]["eval"][at]["P1"] for r in recs]) for a in arms} for at in (MID, TARGET)}
    pairs = [("C7", "00"), ("C7", "R7"), ("R7", "00")] if sel == "C7" else [("R7", "00")]
    res = {}
    for at in (MID, TARGET):
        res[at] = {}
        for x, y in pairs:
            d = P[at][x] - P[at][y]
            D = np.stack([r["arms"][x]["eval"][at]["per_layout"] - r["arms"][y]["eval"][at]["per_layout"] for r in recs])
            t = tsum(d)
            t["crossed_lo"], t["crossed_hi"] = crossed(D, rng)
            t["sign_flip_p"] = sign_flip(d)
            res[at][f"{NAME[x]}-{NAME[y]}"] = t
    prim = res[TARGET]
    if sel == "C7":
        t1 = prim["C-A"]["p_t"] < 0.05
        t2 = bool(t1 and prim["C-R"]["p_t"] < 0.05)
        primary = {"family": "fixed sequence: C-A then C-R, each two-sided 0.05", "C-A_rejected": t1,
                   "C-R_tested": t1, "C-R_rejected": t2}
    else:
        primary = {"family": "single test R-A, two-sided 0.05", "R-A_rejected": prim["R-A"]["p_t"] < 0.05}
    out = {"selected": sel, "seeds": CONF_SEEDS, "primary": primary,
           "P1": {str(at): {a: P[at][a].tolist() for a in arms} for at in P},
           "contrasts": {str(at): v for at, v in res.items()},
           "secondary": {str(at): {a: {"pooled": secondary([x for r in recs for x in r["arms"][a]["eval"][at]["rows"]])}
                                   for a in arms} for at in (MID, TARGET)},
           "supervision": {a: [r["arms"][a]["summary"]["aux"] for r in recs] for a in arms if a != "00"},
           "agreement": {a: {r["seed"]: r["arms"][a]["summary"].get("recovery_agreement") for r in recs} for a in arms}}
    (OUT / "conf.json").write_text(json.dumps(out, indent=1, default=float))
    md = [f"# Confirmation (seeds 122-141; r7_conf 256 x 2; selected {sel})", "",
          "| Contrast @501,760 | mean | 95% t | p (t) | crossed seed-and-layout 95% | sign-flip p | seeds > 0 |",
          "|---|---|---|---|---|---|---|"]
    for k, t in prim.items():
        md.append(f"| {k} | {fmt(t['mean'], sign=True)} | [{fmt(t['lo'], sign=True)}, {fmt(t['hi'], sign=True)}] | "
                  f"{t['p_t']:.4f} | [{fmt(t['crossed_lo'], sign=True)}, {fmt(t['crossed_hi'], sign=True)}] | "
                  f"{t['sign_flip_p']:.4f} | {t['n_pos']}/20 |")
    md += ["", f"Primary: {primary}", ""]
    (OUT / "conf.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["dev", "conf-check", "conf"])
    a = ap.parse_args()
    {"dev": dev, "conf-check": conf_check, "conf": conf}[a.mode]()


if __name__ == "__main__":
    main()
