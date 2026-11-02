"""Fixed actual-arrival bank (owner instruction 2026-11-01c, section 6; PROTOCOL_FREEZE Amendment 6).

python -m bc2rl.arrival_bank --config experiments/a4/arrival-v1.json

Bank-generating policies: the existing calibration development BC policies (rho 0.2, 8,000 updates, seeds 67-69),
not policies selected by any A4 outcome. Frozen rule, fixed before collection:
  donors   = the a4_donor K=3 layouts in role order (512);
  source   = donor index mod 3 -> sources[0..2];
  attempts = one sampled normal-start episode per donor, attempt stream rng([collect_seed + source, local index, 0]);
  capture  = the complete simulator snapshot at the first boundary crossing (original clock and env RNG state kept);
  keep     = every captured state with remaining time >= min_remaining, in donor order, up to cap (the first cap);
  no state is selected by its eventual success (the episode outcome is recorded but never used).
Every donor runs, whatever the arrival count (cost fixed in advance). If fewer than cap arrivals occur, the bank is
smaller and the shortfall is reported; nothing is collected again.
Outputs under $MAE_PROJECT/<out>/: arrival_bank.json ({"states": [...], "rule": ..., "sources": ...}) and
manifest.json (SHA-256 of the bank and of each source checkpoint, counts). summary.json in the run directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

import torch

from bc2rl import battery as BAT
from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import task as T
from bc2rl.telemetry import Heartbeat, resource_heartbeat


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def collect(actors, donors, collect_seed, cap, min_remaining, device, heartbeat=None):
    """actors: list of 3 policies; donors: list of Layouts. Returns (kept, records, actions)."""
    records, actions = [None] * len(donors), 0
    for s, actor in enumerate(actors):
        idx = [i for i in range(len(donors)) if i % len(actors) == s]
        res, n = E.run_attempts(actor, [("layout", donors[i]) for i in idx], 1, collect_seed + s, device,
                                heartbeat=heartbeat, capture=True)
        actions += n
        for r in res:
            records[idx[r["item"]]] = {**r, "donor_index": idx[r["item"]], "source": s}
    kept = []
    for r in records:
        a = r["arrival"]
        if a is None or a["remaining"] < min_remaining:
            continue
        snap = a["snapshot"]
        assert snap["accessed"] and snap["tau"] == snap["step_count"] == a["tau"]
        if len(kept) < cap:
            kept.append({"snapshot": snap, "donor_index": r["donor_index"], "donor_seed": donors[r["donor_index"]].gen_seed,
                         "source": r["source"], "tau": a["tau"], "remaining": a["remaining"], "carrying": a["carrying"]})
    return kept, records, actions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("arrival_bank")
    project = Path(os.environ.get("MAE_PROJECT", "."))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    device = torch.device(os.environ.get("MAE_DEVICE", "cpu"))
    torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))
    out = project / cfg["out"]
    out.mkdir(parents=True, exist_ok=False)
    lay = json.loads((project / "data" / cfg["dataset_id"] / "layouts.json").read_text())
    donors = [T.Layout.from_dict(it["layout"]) for it in lay[cfg["donor_role"]] if it["layout"]["K"] == cfg["K"]]
    assert len(donors) == cfg["n_donors"], (len(donors), cfg["n_donors"])
    actors, src = [], []
    for s in cfg["sources"]:
        p = project / ".mae/runs" / s["run"] / f"actor_u{s['update']}.pt"
        ck = torch.load(p, map_location="cpu", weights_only=False)
        actor = M.Actor().to(device)
        actor.load_state_dict(ck["actor"])
        actors.append(actor)
        src.append({**s, "sha256": sha256(p), "bc_seed": ck["seed"], "prefix_prob": ck["config"].get("prefix_prob")})
    last = [time.time()]

    def hb():
        if time.time() - last[0] > 5:
            resource_heartbeat()
            last[0] = time.time()

    t0 = time.time()
    with Heartbeat(interval=5):
        kept, records, actions = collect(actors, donors, cfg["collect_seed"], cfg["cap"], cfg["min_remaining"], device, hb)
    rule = {k: cfg[k] for k in ("donor_role", "K", "n_donors", "collect_seed", "cap", "min_remaining")}
    rule["assignment"] = "donor index mod 3 -> source; one sampled attempt per donor; first crossing captured; first cap kept in donor order"
    bank = {"states": kept, "rule": rule, "sources": src, "dataset_id": cfg["dataset_id"]}
    (out / "arrival_bank.json").write_text(json.dumps(bank))
    n_arr = sum(r["arrival"] is not None for r in records)
    counts = {"donors_run": len(records), "arrivals": n_arr,
              "arrivals_with_remaining": sum(r["arrival"] is not None and r["arrival"]["remaining"] >= cfg["min_remaining"] for r in records),
              "kept": len(kept), "cap": cfg["cap"], "shortfall": max(0, cfg["cap"] - len(kept)),
              "arrivals_by_source": [sum(r["arrival"] is not None for r in records if r["source"] == s) for s in range(len(actors))],
              "kept_by_source": [sum(k["source"] == s for k in kept) for s in range(len(actors))],
              "last_kept_donor_index": kept[-1]["donor_index"] if kept else None}
    man = {"config": cfg, "rule": rule, "sources": src, "counts": counts, "actions": actions,
           "files": {"arrival_bank.json": sha256(out / "arrival_bank.json")}, "wall_seconds": time.time() - t0}
    (out / "manifest.json").write_text(json.dumps(man, indent=1))
    (run_dir / "donor_records.jsonl").write_text("".join(json.dumps({k: v for k, v in r.items() if k != "arrival"} |
        {"arrival": None if r["arrival"] is None else {k: v for k, v in r["arrival"].items() if k != "snapshot"}}) + "\n"
        for r in records))
    BAT.write_atomic(run_dir / "summary.json", {"mode": "arrival_bank", "actions": {"bank_collection": actions},
                                                "counts": counts, "bank_sha256": man["files"]["arrival_bank.json"]})
    print(json.dumps({"event": "done", **counts, "actions": actions}), flush=True)


if __name__ == "__main__":
    main()
