"""Independent recomputation of the pilot gate (owner instruction 2026-11-02, sections 7 and 10). Shares no code with
tools/analyze_p5.py: own run discovery, own P1 from raw attempt rows, own gate rule. No actions.

Usage: .venv/bin/python tools/verify_p5.py -> reports/p5/gate_verification.json
Gate (Amendment 7 D): m in {B, C, D} qualifies iff at 501,760 mean(P1_m - P1_A) >= 0.05 over seeds 90-95 and the
difference is > 0 in >= 4/6 (checks and budget are taken from gate.json and re-read, not recomputed); select the
highest mean final P1, preferring a simpler qualifying method (B, C, D) within 0.02.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
ARMS = {"A": "00", "B": "B5", "C": "C5", "D": "D5"}


def p1(seed, arm, tag="dev_501760"):
    files = [f for f in sorted((ROOT / ".mae/runs").glob(f"*/p5-K3-s{seed}-{arm}*/attempts_{tag}.jsonl"))]
    vals = set()
    for f in files:
        n = [json.loads(l) for l in f.read_text().splitlines() if l.strip() and '"kind": "normal"' in l]
        if len(n) == 256:
            vals.add(sum(r["success"] for r in n) / 256)
    assert len(vals) == 1, (seed, arm, vals)
    return vals.pop()


def main():
    P = {(s, lab): p1(s, a) for s in range(90, 96) for lab, a in ARMS.items()}
    g = json.loads((ROOT / "reports/p5/gate.json").read_text())
    res, q = {}, []
    for m in "BCD":
        d = np.array([P[(s, m)] - P[(s, "A")] for s in range(90, 96)])
        res[m] = {"mean_diff": float(d.mean()), "n_positive": int((d > 0).sum()),
                  "mean_final_P1": float(np.mean([P[(s, m)] for s in range(90, 96)]))}
        ok = d.mean() >= 0.05 and (d > 0).sum() >= 4 and g["methods"][m]["checks_pass"] and g["budget"]["fits"]
        res[m]["qualifies"] = bool(ok)
        if ok:
            q.append(m)
    sel = None
    if q:
        best = max(q, key=lambda m: res[m]["mean_final_P1"])
        sel = min([m for m in q if res[best]["mean_final_P1"] - res[m]["mean_final_P1"] <= 0.02], key="BCD".index)
    agree = sel == g["selected"] and all(abs(res[m]["mean_diff"] - g["methods"][m]["mean_diff"]) < 1e-12 and
                                         res[m]["n_positive"] == g["methods"][m]["n_positive"] for m in "BCD")
    out = {"methods": res, "qualifying": q, "selected": sel, "agrees_with_gate_json": bool(agree)}
    (ROOT / "reports/p5/gate_verification.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
