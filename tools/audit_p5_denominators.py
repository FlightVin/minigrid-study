"""Denominator audit of the 2026-11-02 diagnostics and pilot (owner instruction 2026-11-02b, section 1). No actions.

Reads raw attempt rows only. For each policy: counts with explicit denominators
  n attempts; S successes; A arrivals (first boundary crossings); S_A successes among arrivals; F, U, I arrivals
  certified feasible / unresolved / impossible; S_F successes among feasible arrivals; failures before the boundary
  and their last module.
Rates: P1 = S/n, q = A/n, r = S_A/A (learned completion given actual arrival), finishable share of arrivals F/A,
finishable share of attempts F/n, learned completion given a finishable arrival S_F/F. Pooled rates use summed counts.
Outputs reports/p6/audit_p5.{json,md}.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / ".mae/runs/20261102T102039-57342/diag5"


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def counts(rows):
    arr = [r for r in rows if r["arrival"] is not None]
    st = lambda s: [r for r in arr if r["arrival"].get("cert", {}).get("status") == s]
    pre = [r for r in rows if r["arrival"] is None]
    c = {"n": len(rows), "S": sum(r["success"] for r in rows), "A": len(arr), "S_A": sum(r["success"] for r in arr),
         "F": len(st("feasible")), "U": len(st("unresolved")), "I": len(st("impossible")),
         "S_F": sum(r["success"] for r in st("feasible")), "pre_fail": len(pre)}
    if rows and "trace" in rows[0]:
        for k in ("prefix_m0", "prefix_m1", "prefix_m2"):
            c["pre_end_" + k[-2:]] = sum(1 for r in pre if r["trace"]["stage_end"] == k)
    return c


def rates(c):
    d = lambda a, b: None if b == 0 else a / b
    return {"P1=S/n": d(c["S"], c["n"]), "q=A/n": d(c["A"], c["n"]), "r=S_A/A": d(c["S_A"], c["A"]),
            "finishable_of_arrivals=F/A": d(c["F"], c["A"]), "finishable_of_attempts=F/n": d(c["F"], c["n"]),
            "impossible_of_arrivals=I/A": d(c["I"], c["A"]), "completion_given_finishable=S_F/F": d(c["S_F"], c["F"]),
            "pre_boundary_of_failures": d(c["pre_fail"], c["n"] - c["S"])}


def add(cs):
    out = {}
    for c in cs:
        for k, v in c.items():
            out[k] = out.get(k, 0) + v
    return out


def main():
    rep = {"diagnostics": {}, "pilot": {}}
    for ck in ("probe", "final"):
        cs = []
        for s in (70, 71, 72, 73):
            c = counts(jl(next(DIAG.parent.glob(f"*/attempts_s{s}_{ck}_normal.jsonl"))))
            rep["diagnostics"][f"s{s}_{ck}"] = {"counts": c, "rates": rates(c)}
            cs.append(c)
        p = add(cs)
        rep["diagnostics"][f"pooled_{ck}"] = {"counts": p, "rates": rates(p)}
    for arm in ("00", "B5", "C5", "D5"):
        cs = []
        for s in range(90, 96):
            f = next((ROOT / ".mae/runs").glob(f"*/p5-K3-s{s}-{arm}/attempts_dev_501760.jsonl"))
            c = counts([r for r in jl(f) if r["start_kind"] == "layout"])
            cs.append(c)
        p = add(cs)
        per_seed_r = [c["S_A"] / c["A"] for c in cs]
        rep["pilot"][arm] = {"pooled_counts": p, "pooled_rates": rates(p),
                             "mean_of_per_seed_r": sum(per_seed_r) / len(per_seed_r)}
    (ROOT / "reports/p6/audit_p5.json").write_text(json.dumps(rep, indent=1))
    f3 = lambda v: "—" if v is None else f"{v:.3f}"
    md = ["# Denominator audit (diagnostics batch 20261102T102039-57342; pilot 501,760)", "",
          "| policy | n | S | A | S_A | F | I | P1 = S/n | q = A/n | r = S_A/A | F/A | F/n | S_F/F | pre-boundary / failures |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in rep["diagnostics"].items():
        c, r = v["counts"], v["rates"]
        md.append(f"| {k} | {c['n']} | {c['S']} | {c['A']} | {c['S_A']} | {c['F']} | {c['I']} | " + " | ".join(
            f3(r[x]) for x in ("P1=S/n", "q=A/n", "r=S_A/A", "finishable_of_arrivals=F/A", "finishable_of_attempts=F/n",
                               "completion_given_finishable=S_F/F", "pre_boundary_of_failures")) + " |")
    md += ["", "| pilot arm (6 seeds pooled, 501,760) | n | S | A | S_A | F | P1 | q | pooled r = S_A/A | mean of per-seed r | F/A | S_F/F |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, v in rep["pilot"].items():
        c, r = v["pooled_counts"], v["pooled_rates"]
        md.append(f"| {k} | {c['n']} | {c['S']} | {c['A']} | {c['S_A']} | {c['F']} | {f3(r['P1=S/n'])} | {f3(r['q=A/n'])} | "
                  f"{f3(r['r=S_A/A'])} | {f3(v['mean_of_per_seed_r'])} | {f3(r['finishable_of_arrivals=F/A'])} | "
                  f"{f3(r['completion_given_finishable=S_F/F'])} |")
    (ROOT / "reports/p6/audit_p5.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
