"""Independent audit of the M3 development runs from raw artifacts.

Usage: .venv/bin/python tools/audit_m3.py [--out reports]

Does not import bc2rl.evaluate: metrics are recomputed here from attempts_*.jsonl with separate code.
Outputs:
  m3_manifest.csv    one row per job: role (probe | screen | selected | repeat), fork, arm, alpha, lambda,
                     source commit, probe job, fork hash, SHA-256 of fork.pt / final.pt / BC checkpoint.
  m3_recomputed.csv  one row per branch: recomputed final P1, q, c, C4, R4, P(success | arrival), and the
                     largest absolute difference from summary.json.
  m3_selected_contrasts.csv  paired contrasts from explicitly selected rows (original arm 00 only).
Every selection is by explicit key; a duplicate key is an error.
"""
import argparse
import csv
import hashlib
import json
from math import comb
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".mae/runs"
BATCHES = ["20261030T214937-19577", "20261030T232600-96083"]
ALPHA_STAR, LAMBDA_STAR = 0.25, 0.01


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def commits():
    out = {}
    for line in (ROOT / ".mae/ledger.jsonl").read_text().splitlines():
        r = json.loads(line)
        out[r["batch"]] = r["project_sha"]
    return out


def metrics(path, kind):
    """P1, q, C4, R4 with equal weight per item; P(success | arrival) over attempts with an arrival."""
    recs = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    recs = [r for r in recs if r["kind"] == kind]
    items = sorted({r["item"] for r in recs})
    p1, q, c4, r4 = [], [], [], []
    for i in items:
        rs = [r for r in recs if r["item"] == i]
        n, z = len(rs), sum(bool(r["success"]) for r in rs)
        p1.append(z / n)
        q.append(sum(bool(r["accessed"]) and not r["start_accessed"] for r in rs) / n)
        if n >= 4:
            c4.append(1 - (comb(n - z, 4) if n - z >= 4 else 0) / comb(n, 4))
            r4.append((comb(z, 4) if z >= 4 else 0) / comb(n, 4))
    arr = [r for r in recs if r["arrival"] is not None]
    return {"P1": float(np.mean(p1)), "q": float(np.mean(q)),
            "C4": float(np.mean(c4)) if c4 else None, "R4": float(np.mean(r4)) if r4 else None,
            "P_succ_arrival": float(np.mean([r["success"] for r in arr])) if arr else None,
            "n_items": len(items), "n_attempts": len(recs), "n_arrivals": len(arr)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "reports"))
    a = ap.parse_args()
    out = Path(a.out)
    cm = commits()
    manifest, recomputed = [], []
    for b in BATCHES:
        for d in sorted(p for p in (RUNS / b).iterdir() if p.is_dir() and p.name != "code"):
            s = json.loads((d / "summary.json").read_text())
            cfg = json.loads((d / "config.resolved.json").read_text())
            row = {"batch": b, "job": d.name, "source_commit": cm[b], "K": s["K"], "bc_update": s["bc_update"],
                   "seed": s["seed"], "fork_hash": s["fork_hash"]}
            if s["mode"] == "probe":
                bc = RUNS / cfg["bc_run"] / f"actor_u{cfg['bc_update']}.pt"
                row.update(role="probe", arm="", alpha="", kl_coef="", probe_job=d.name,
                           fork_pt_sha256=sha(d / "fork.pt"), final_pt_sha256="",
                           bc_checkpoint=f"{cfg['bc_run']}/actor_u{cfg['bc_update']}.pt", bc_checkpoint_sha256=sha(bc))
            else:
                arm, alpha, kl = s["arm"], cfg["alpha"], cfg["kl_coef"]
                ok_alpha = alpha == ALPHA_STAR if arm in ("10", "11") else alpha == 0.0
                ok_kl = kl == LAMBDA_STAR if arm in ("01", "11") else kl == 0.0
                role = "repeat" if d.name.endswith("-rep") else "selected" if ok_alpha and ok_kl else "screen"
                row.update(role=role, arm=arm, alpha=alpha, kl_coef=kl, probe_job=Path(cfg["probe_run"]).name,
                           fork_pt_sha256="", final_pt_sha256=sha(d / "final.pt"), bc_checkpoint="", bc_checkpoint_sha256="")
                m = metrics(d / "attempts_final.jsonl", "normal")
                c = metrics(d / "attempts_final.jsonl", "bank")
                f = s["final"]
                ref = {"P1": f["P1"], "q": f["q"], "C4": f["C4"], "R4": f["R4"], "c": f["c"],
                       "P_succ_arrival": f["P_success_given_arrival"]}
                mine = {"P1": m["P1"], "q": m["q"], "C4": m["C4"], "R4": m["R4"], "c": c["P1"],
                        "P_succ_arrival": m["P_succ_arrival"]}
                diff = max(abs(mine[k] - ref[k]) for k in mine if ref[k] is not None)
                recomputed.append({**{k: row[k] for k in ("batch", "job", "role", "K", "bc_update", "seed", "arm",
                                                          "alpha", "kl_coef")},
                                   **mine, "n_items": m["n_items"], "n_attempts": m["n_attempts"],
                                   "bank_items": c["n_items"], "bank_attempts": c["n_attempts"],
                                   "n_arrivals": m["n_arrivals"], "max_abs_diff_vs_summary": diff})
            manifest.append(row)
    # Fork checks: every branch's fork hash equals its probe's.
    probes = {r["probe_job"]: r for r in manifest if r["role"] == "probe"}
    for r in manifest:
        if r["role"] != "probe":
            assert r["fork_hash"] == probes[r["probe_job"]]["fork_hash"], r["job"]
    # Explicit selection with uniqueness.
    sel = {}
    for r in recomputed:
        if r["role"] != "selected":
            continue
        key = (r["K"], r["bc_update"], r["seed"], r["arm"])
        assert key not in sel, f"duplicate selected row {key}"
        sel[key] = r
    reps = {(r["K"], r["bc_update"], r["seed"]): r for r in recomputed if r["role"] == "repeat"}
    forks = sorted({k[:3] for k in sel})
    contr = []
    for f in forks:
        y = {arm: sel[f + (arm,)]["P1"] for arm in ("00", "10", "01", "11")}
        contr.append({"K": f[0], "bc_update": f[1], "seed": f[2], "Y00": y["00"], "Y10": y["10"], "Y01": y["01"],
                      "Y11": y["11"], "Y00_repeat": reps[f]["P1"],
                      "reset": y["10"] - y["00"], "preserve": y["01"] - y["00"], "combined": y["11"] - y["00"],
                      "interaction": (y["11"] - y["01"]) - (y["10"] - y["00"]),
                      "combined_vs_reset": y["11"] - y["10"], "combined_vs_preserve": y["11"] - y["01"],
                      "repeat_minus_original": reps[f]["P1"] - y["00"]})
    for name, rows in (("m3_manifest.csv", manifest), ("m3_recomputed.csv", recomputed),
                       ("m3_selected_contrasts.csv", contr)):
        with open(out / name, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    roles = {}
    for r in manifest:
        roles[r["role"]] = roles.get(r["role"], 0) + 1
    print(json.dumps({"jobs": len(manifest), "roles": roles, "branches_recomputed": len(recomputed),
                      "max_abs_diff": max(r["max_abs_diff_vs_summary"] for r in recomputed),
                      "forks": len(forks)}))
    for c in contr:
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in c.items()})


if __name__ == "__main__":
    main()
