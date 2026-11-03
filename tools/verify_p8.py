"""Independent recomputation for the actor capability audit (owner instruction 2026-11-03, section 8; Amendment 10).
Shares no code with tools/analyze_p8.py or bc2rl.capfit. No actions.

Usage: .venv/bin/python tools/verify_p8.py   -> reports/p8/verification.json

- Test metrics: the actor's forward pass is re-implemented here with torch.nn.functional from the saved state
  dictionaries (embeddings, three convolutions, channel-first flatten, scalar one-hots, dense layers), on CPU in
  float64. Argmax-in-set and mass on the set are recomputed for every selected checkpoint on the test states and the
  recovery bank and compared with reports/p8/audit.json (tolerances: mass 1e-3; argmax-in-set 2e-3, because MPS
  float32 can flip near-ties).
- Rollouts: boundary reach and mean time to boundary per controller from the raw rollout rows.
- Actions: ledger total minus the start, against the sum of the audit's job step records, its local unmanaged
  records after the start, and its ledger adjustments.
- Hashes: dataset, collection files, selected checkpoints, layout index lists, code files.
Shared upstream data: dataset.npz, selected.pt, rollouts.jsonl, step records (the files the analysis reads).
"""
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
START = 342_196_148
N_TYPES, N_COLORS = 11, 6


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run_of(job):
    ds = sorted(d for d in (ROOT / ".mae/runs").glob(f"*/{job}") if (d / "summary.json").exists())
    return ds[-1]


def forward(sd, grid, aux, tim):
    g = torch.as_tensor(grid.astype(np.int64))
    x = torch.cat([F.embedding(g[..., i], sd[f"enc.emb.{i}.weight"]) for i in range(4)], -1).permute(0, 3, 1, 2)
    for k in (0, 2, 4):
        x = F.relu(F.conv2d(x, sd[f"enc.conv.{k}.weight"], sd[f"enc.conv.{k}.bias"], padding=1))
    x = x.reshape(x.shape[0], -1)
    a = torch.as_tensor(aux.astype(np.int64))
    s = torch.cat([F.one_hot(a[:, 0], 4), F.one_hot(a[:, 1], N_TYPES), F.one_hot(a[:, 2], N_COLORS + 1)], 1).double()
    h = F.relu(F.linear(torch.cat([x, s, torch.as_tensor(tim, dtype=torch.float64)[:, None]], 1),
                        sd["enc.fc.0.weight"], sd["enc.fc.0.bias"]))
    return F.linear(h, sd["head.weight"], sd["head.bias"])


def metrics(sd, z, p):
    sd = {k: v.double() for k, v in sd.items()}
    agree, mass = [], []
    n = len(z[p + "_mask"])
    with torch.no_grad():
        for i in range(0, n, 2048):
            lg = forward(sd, z[p + "_grid"][i:i + 2048], z[p + "_aux"][i:i + 2048], z[p + "_time"][i:i + 2048]).numpy()
            m = z[p + "_mask"][i:i + 2048].astype(np.int64)
            valid = ((m[:, None] >> np.arange(7)) & 1).astype(bool)
            pr = np.exp(lg - lg.max(1, keepdims=True))
            pr /= pr.sum(1, keepdims=True)
            agree.append(valid[np.arange(len(lg)), lg.argmax(1)])
            mass.append((pr * valid).sum(1))
    return float(np.concatenate(agree).mean()), float(np.concatenate(mass).mean())


def main():
    audit = json.loads((ROOT / "reports/p8/audit.json").read_text())
    z = np.load(ROOT / "data/cap-v1/dataset.npz")
    problems, test, hashes = [], {}, {"selected": {}}
    conds = {"warm128-n0": "p8-fit-warm128-n0-s{}", "warm128-n1": "p8-fit-warm128-n1-s{}",
             "warm128-n2": "p8-fit-warm128-n2-s{}", "scratch128-n2": "p8-fit-scratch128-n2-s{}",
             "scratch1024-n2": "p8-fit-scratch1024-n2-s{}"}
    for c, pat in conds.items():
        for s in range(3):
            j = pat.format(s)
            f = run_of(j) / "selected.pt"
            hashes["selected"][j] = sha(f)
            sd = torch.load(f, map_location="cpu", weights_only=False)["state"]
            ta, tm = metrics(sd, z, "test")
            ra, rm = metrics(sd, z, "recov")
            test[j] = {"test_agree": ta, "test_mass": tm, "recov_agree": ra, "recov_mass": rm}
            A = audit["test"][c]
            for k, mine, tol in (("test_agree_per_seed", ta, 2e-3), ("test_mass_per_seed", tm, 1e-3),
                                 ("recov_agree_per_seed", ra, 2e-3), ("recov_mass_per_seed", rm, 1e-3)):
                if abs(A[k][s] - mine) > tol:
                    problems.append(f"{j} {k}: analysis {A[k][s]:.5f} vs {mine:.5f}")
    rows = [json.loads(l) for l in (run_of("p8-rollout") / "rollouts.jsonl").read_text().splitlines() if l.strip()]
    roll = {}
    for r in rows:
        if r["attempt"] != 0:
            continue
        d = roll.setdefault(r["controller"], {"reached": 0, "n": 0, "taus": []})
        d["n"] += 1
        if r["crossed"]:
            d["reached"] += 1
            d["taus"].append(r["tau"])
    for c, d in roll.items():
        a = audit["rollouts"][c]
        tau = sum(d["taus"]) / len(d["taus"]) if d["taus"] else None
        if a["reached"] != d["reached"] or a["n"] != d["n"] or (tau is not None and abs(a["tau_mean"] - tau) > 1e-9):
            problems.append(f"rollout {c} differs")
        d["tau_mean"] = tau
        del d["taus"]
    # actions
    out =subprocess.run([str(ROOT / ".venv/bin/python"), "tools/ledger.py"], cwd=ROOT, capture_output=True, text=True).stdout
    total = json.loads(out[out.index("{"):])["total_env_actions"]
    jobs = {}
    for d in (ROOT / ".mae/runs").glob("*/p8-*"):
        n = sum(json.loads(p.read_text())["actions"] for p in (d / "env_steps").glob("*.json")) if (d / "env_steps").exists() else 0
        if n:
            jobs[f"{d.parent.name}/{d.name}"] = n
    unmanaged = 0
    for p in (ROOT / ".mae/unmanaged_actions").glob("*.json"):
        r = json.loads(p.read_text())
        if r["started"] >= 1793710000:            # after the 2026-11-02d write-up (2026-11-03 local time)
            unmanaged += r["actions"]
    adj = sum(e["actions"] for e in json.loads((ROOT / "research/ledger_adjustments.json").read_text())["entries"]
              if e.get("role", "").startswith("p8_"))
    acts = {"ledger_spent": total - START, "job_step_records": sum(jobs.values()), "by_job": jobs,
            "local_unmanaged": unmanaged, "adjustments": adj}
    acts["reconciled"] = acts["ledger_spent"] == acts["job_step_records"] + unmanaged + adj
    if not acts["reconciled"]:
        problems.append("action totals do not reconcile")
    hashes["dataset"] = sha(ROOT / "data/cap-v1/dataset.npz")
    hashes["collect"] = {g: sha(ROOT / f"data/cap-v1/collect_{g}.npz") for g in ("train", "val", "test")}
    coll = json.loads((run_of("p8-collect") / "summary.json").read_text())
    hashes["layouts_used"] = {g: hashlib.sha256(json.dumps(v["layout_indices_used"]).encode()).hexdigest()
                              for g, v in coll["groups"].items()}
    hashes["code"] = {p: sha(ROOT / p) for p in ("src/bc2rl/capability.py", "src/bc2rl/capfit.py", "src/bc2rl/corrective.py",
                                                 "src/bc2rl/model.py", "src/bc2rl/task.py", "tools/build_p8_dataset.py",
                                                 "tools/analyze_p8.py", "tools/verify_p8.py", "tools/run_program8.py")}
    res = {"test_recomputed": test, "rollouts_recomputed": roll, "actions": acts, "hashes": hashes,
           "problems": problems, "agrees": not problems}
    (ROOT / "reports/p8/verification.json").write_text(json.dumps(res, indent=1) + "\n")
    print(json.dumps({k: res[k] for k in ("problems", "agrees")} | {"actions": {k: v for k, v in acts.items() if k != "by_job"}}, indent=1))


if __name__ == "__main__":
    main()
