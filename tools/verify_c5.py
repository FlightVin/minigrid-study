"""Independent verification of the conditional confirmation (owner instruction 2026-11-02, section 8). Shares no code
with tools/analyze_c5.py or tools/analyze_p5.py: own lineage resolution, own metrics from raw attempt rows, own t
interval (tools/audit_r1.py t CDF), own exact sign-flip. No actions.

Usage: .venv/bin/python tools/verify_c5.py  -> reports/c5/verification.json
Checks per seed: one complete BC and probe; both branches complete; identity (arm, fork hash, roles, eval seed);
panel = c5_final K=3 limits; rows 512 normal + 256 bank at both endpoints; step records = summary actions.
With 20 complete seeds: P1, q, r, entry per arm and endpoint; H1 t-test, interval, sign-flip; agreement with
reports/c5/c5_summary.json.
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
SEEDS = range(96, 116)
EPS = (251904, 501760)


def t_crit(df):
    lo, hi = 0.0, 50.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_two_sided_p(mid, df) > 0.05 else (lo, mid)
    return (lo + hi) / 2


def jl(p):
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def complete_dirs(name):
    return [d for d in sorted(RUNS.glob(f"*/{name}")) if (d / "summary.json").exists()]


def chain(base):
    import torch
    cands = complete_dirs(base) + [d for k in range(1, 10) for d in complete_dirs(f"{base}-r{k}")]
    ends = [d for d in cands if json.loads((d / "summary.json").read_text())["continuation_actions"] == EPS[-1]]
    if len(ends) != 1:
        return None
    out, d = [], ends[0]
    while d is not None:
        f = d / "summary.json"
        meta = json.loads(f.read_text()) if f.exists() else json.loads((d / "config.resolved.json").read_text())
        src = meta.get("resumed_from")
        start = torch.load(src, map_location="cpu", weights_only=False)["meta"]["post_probe_actions"] if src else 0
        out.append((d, start))
        d = Path(src).parent if src else None
    return out[::-1]


def file_for(ch, at, tag):
    for k, (d, start) in enumerate(ch):
        end = ch[k + 1][1] if k + 1 < len(ch) else 10 ** 9
        if start < at <= end:
            return d / f"attempts_{tag}.jsonl"


def main():
    arm = json.loads((ROOT / "reports/p5/gate.json").read_text())["selected_arm"]
    lim = [it["layout"]["limit"] for it in json.loads((ROOT / "data/r5-v1/layouts.json").read_text())["c5_final"] if it["layout"]["K"] == 3]
    problems, M, done = [], {}, []
    for s in SEEDS:
        pr, bc = complete_dirs(f"c5-probe-K3-s{s}"), complete_dirs(f"c5-bc-s{s}")
        if len(pr) != 1 or len(bc) != 1:
            if pr or bc:
                problems.append(f"s{s}: incomplete BC/probe")
            continue
        fork = json.loads((pr[0] / "summary.json").read_text())["fork_hash"]
        ok = True
        for a in ("00", arm):
            ch = chain(f"c5-K3-s{s}-{a}")
            if ch is None:
                ok = False
                continue
            for d, _ in ch:
                cf = json.loads((d / "config.resolved.json").read_text())
                if (cf["arm"], cf["fork_hash"], cf["eval_role"], cf["bank_role"], cf["eval_seed"]) != (a, fork, "c5_final", "c5_bank", 999000):
                    problems.append(f"s{s} {a}: identity")
                if (d / "summary.json").exists():
                    sm = json.loads((d / "summary.json").read_text())
                    if sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json")) != sum(sm["actions"].values()):
                        problems.append(f"s{s} {a}: step records")
            for at in EPS:
                rows = jl(file_for(ch, at, f"conf_{at}"))
                n = [r for r in rows if r["kind"] == "normal"]
                b = [r for r in rows if r["kind"] == "bank"]
                if (len(n), len(b)) != (512, 256):
                    problems.append(f"s{s} {a} {at}: rows")
                lims = {r["item"]: r["limit"] for r in n}
                if [lims[i] for i in range(256)] != lim:
                    problems.append(f"s{s} {a} {at}: panel")
                arr = [r for r in n if r["arrival"] is not None]
                M[(s, a, at)] = {"P1": np.mean([r["success"] for r in n]), "q": len(arr) / len(n),
                                 "r": np.mean([r["success"] for r in arr]) if arr else None,
                                 "entry": np.mean([r["success"] for r in b])}
        if ok:
            done.append(s)
    res = {"arm": arm, "complete_seeds": done, "problems": problems}
    if len(done) == 20:
        x = np.array([M[(s, arm, EPS[-1])]["P1"] - M[(s, "00", EPS[-1])]["P1"] for s in SEEDS])
        m, sd = x.mean(), x.std(ddof=1)
        se, c = sd / sqrt(20), t_crit(19)
        cnt = 0
        for st in range(0, 2 ** 20, 2 ** 16):
            idx = np.arange(st, st + 2 ** 16)
            sg = 1 - 2 * ((idx[:, None] >> np.arange(20)) & 1)
            cnt += int((np.abs(sg @ x) >= abs(x.sum()) - 1e-12).sum())
        h1 = {"estimate": float(m), "sd": float(sd), "p": float(t_two_sided_p(m / se, 19)), "lo": float(m - c * se),
              "hi": float(m + c * se), "signflip_p": cnt / 2 ** 20}
        h1["decision"] = "supported" if h1["lo"] > 0 or h1["hi"] < 0 else "not supported"
        ref = json.loads((ROOT / "reports/c5/c5_summary.json").read_text())["H1"]
        agree = {k: bool(abs(h1[a] - ref[b]) < 1e-9) for a, b in (("estimate", "mean"), ("sd", "sd"), ("p", "p"),
                                                                  ("lo", "lo"), ("hi", "hi"), ("signflip_p", "signflip_p_exact"))}
        agree["decision"] = h1["decision"] == ref["decision"]
        res.update(H1=h1, agrees_with_analyze_c5=agree,
                   d_251904=float(np.mean([M[(s, arm, EPS[0])]["P1"] - M[(s, "00", EPS[0])]["P1"] for s in SEEDS])))
        if not all(agree.values()):
            problems.append("disagrees with analyze_c5")
    (ROOT / "reports/c5").mkdir(parents=True, exist_ok=True)
    (ROOT / "reports/c5/verification.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps(res, indent=1, default=float))


if __name__ == "__main__":
    main()
