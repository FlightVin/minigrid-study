"""Planner demonstrations, state banks and their manifest.

Usage (through the runner): python -m bc2rl.data --config experiments/m1/data-dev-v1.json

Outputs under $MAE_PROJECT/data/<dataset_id>/:
  layouts.json            planned layouts (with H_x) and plan statistics for every generated role
  traj_<role>.npz         planner trajectories for roles that need states
  bank_competence_<role>.json   fixed competence-bank snapshots per K (from *_bank roles)
  banks_index.npz         reset/anchor sampling indices
  manifest.json           config, registry hash, counts, SHA-256 of every file
A copy of manifest.json goes to $MAE_RUN_DIR.

Optional "bank_spec" (owner instruction 2026-11-01c): {role: {"bins": "entry", "size": n, "Ks": [3]}} builds that
role's competence bank from boundary-entry states only (the first state after the planner's crossing, original
remaining time), for the listed Ks, from the first n donors in role order. No progress mixing; no cross-K matching.

Optional "base_dataset": every file and layout role of data/<base_dataset> is copied unchanged, and only
generate_roles are planned. The registry is still built from all registry_counts, so new roles (later in
splits.ROLE_ORDER) are checked against every earlier role; the base roles' registry entries must be identical.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np

from bc2rl import planner as P
from bc2rl import splits as S
from bc2rl import task as T
from bc2rl.telemetry import Heartbeat

SCHEMA = 1
EVENT_NONE, EVENT_CROSS, EVENT_PICKUP, EVENT_SUCCESS = 0, 1, 2, 3
BINS = ("entry", "retrieval", "carrying")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_trajectory(env, layout, actions):
    """Replay a verified plan and return per-transition arrays (state before each action)."""
    obs, _ = env.reset(options={"layout": layout})
    rows = {k: [] for k in ("grid", "aux", "time", "action", "reward", "done", "step_count", "stage", "event")}
    pickup_t = None
    for a in actions:
        rows["grid"].append(obs["grid"])
        rows["aux"].append(obs["aux"])
        rows["time"].append(obs["time"][0])
        rows["step_count"].append(env.step_count)
        rows["stage"].append(env.stage())
        obs, r, term, _, info = env.step(a)
        ev = EVENT_NONE
        if info["crossed"]:
            ev = EVENT_CROSS
        if pickup_t is None and env.stage() == 2:
            pickup_t, ev = env.step_count, EVENT_PICKUP
        if info["success"]:
            ev = EVENT_SUCCESS
        rows["action"].append(a)
        rows["reward"].append(r)
        rows["done"].append(term)
        rows["event"].append(ev)
    assert info["success"] and pickup_t is not None
    return rows, pickup_t


def snapshot_from_record(layout, grid, aux, step_count, tau):
    """Rebuild an env snapshot from a stored observation (dynamics never use the env RNG)."""
    xs, ys = np.nonzero(grid[:, :, 3])
    assert len(xs) == 1
    carrying = None if aux[1] == 0 else [int(aux[1]), int(aux[2]) - 1]
    return {"version": T.SNAPSHOT_VERSION, "layout": json.loads(layout.to_json()),
            "grid": grid[:, :, :3].tolist(), "carrying": carrying, "agent_pos": [int(xs[0]), int(ys[0])],
            "agent_dir": int(aux[0]), "step_count": int(step_count), "accessed": bool(step_count >= tau),
            "tau": int(tau) if step_count >= tau else None, "np_random": None}


def competence_choice(tau, pickup_t, length, bin_name, seed):
    """Step index (state before that action) for one bank snapshot. Frozen rule, documented in DECISIONS."""
    u = np.random.default_rng([seed, 2]).random()
    if bin_name == "entry":
        return tau                                   # first state after the crossing
    if bin_name == "retrieval":                      # strictly after entry, strictly before pickup
        return tau + 1 + int(u * (pickup_t - tau - 1))
    # carrying the target: first half of the delivery leg, never the final action
    return pickup_t + int(u * max(1, (length - pickup_t) // 2))


def bin_of_index(i):
    return ("entry", "entry", "retrieval", "carrying")[i % 4]   # 50/25/25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    out = Path(os.environ.get("MAE_PROJECT", ".")) / "data" / cfg["dataset_id"]
    out.mkdir(parents=True, exist_ok=False)
    run_dir = Path(os.environ.get("MAE_RUN_DIR", out))
    t0 = time.time()
    with Heartbeat():
        reg = S.build_registry(cfg["registry_counts"], tuple(cfg["Ks"]))
        stats = S.check_registry(reg)
        (out / "registry.json").write_text(json.dumps(reg, indent=1))
        env = T.StageTask()
        layouts, failures = {}, []
        base = cfg.get("base_dataset")
        if base:
            bdir = out.parent / base
            breg = json.loads((bdir / "registry.json").read_text())["roles"]
            for role, entries in breg.items():
                assert reg["roles"][role] == entries, f"registry entries for base role {role} changed"
            layouts.update(json.loads((bdir / "layouts.json").read_text()))
            assert not set(layouts) & set(cfg["generate_roles"]), "a generated role already exists in the base"
            for f in sorted(bdir.iterdir()):
                if f.name.startswith(("traj_", "bank_competence_")) or f.name == "banks_index.npz":
                    shutil.copy2(f, out / f.name)
        for role in cfg["generate_roles"]:
            layouts[role] = []
            trajs = {k: [] for k in ("grid", "aux", "time", "action", "reward", "done", "step_count", "stage", "event", "traj")}
            meta = []
            for e in reg["roles"][role]:
                for K in cfg["Ks"]:
                    try:
                        lay, rec = P.plan_and_verify(T.generate_layout(K, e["seed"]), e["seed"],
                                                     cfg["prefix_slack"], cfg["suffix_allowance"], env)
                    except Exception as exc:      # recorded, never silently dropped
                        failures.append({"role": role, "seed": e["seed"], "K": K, "error": repr(exc)})
                        continue
                    item = {"layout": json.loads(lay.to_json()), "tau": rec["tau"], "length": rec["length"],
                            "planner_seed": rec["planner_seed"], "structure_hash": lay.structure_hash()}
                    if role in cfg["trajectory_roles"]:
                        rows, pickup_t = record_trajectory(env, lay, rec["actions"])
                        item["pickup_t"] = pickup_t
                        item["traj_index"] = len(meta)
                        for k, v in rows.items():
                            trajs[k].extend(v)
                        trajs["traj"].extend([len(meta)] * len(rec["actions"]))
                        meta.append(item)
                    layouts[role].append(item)
            if role in cfg["trajectory_roles"]:
                np.savez_compressed(out / f"traj_{role}.npz",
                                    grid=np.array(trajs["grid"], np.uint8), aux=np.array(trajs["aux"], np.int8),
                                    time=np.array(trajs["time"], np.float32), action=np.array(trajs["action"], np.int8),
                                    reward=np.array(trajs["reward"], np.float32), done=np.array(trajs["done"], bool),
                                    step_count=np.array(trajs["step_count"], np.int16),
                                    stage=np.array(trajs["stage"], np.int8), event=np.array(trajs["event"], np.int8),
                                    traj=np.array(trajs["traj"], np.int32))
            print(json.dumps({"role": role, "layouts": len(layouts[role]), "elapsed": round(time.time() - t0, 1)}), flush=True)
        (out / "layouts.json").write_text(json.dumps(layouts))

        # Fixed competence banks (one per bank role and K), matched across K by donor seed.
        bank_counts = {}
        for role in cfg["bank_roles"]:
            bank = {}
            spec = cfg.get("bank_spec", {}).get(role)
            for K in (spec["Ks"] if spec else cfg["Ks"]):
                donors = [it for it in layouts[role] if it["layout"]["K"] == K]
                d = np.load(out / f"traj_{role}.npz")
                snaps = []
                size = spec["size"] if spec else cfg["bank_size"]
                assert len(donors) >= size, f"{role} K={K}: {len(donors)} planned donors < bank size {size}"
                for i, it in enumerate(donors[:size]):
                    b = "entry" if spec else bin_of_index(i)
                    t = competence_choice(it["tau"], it["pickup_t"], it["length"], b, it["planner_seed"])
                    rows = np.nonzero(d["traj"] == it["traj_index"])[0]
                    r = rows[t]
                    assert d["step_count"][r] == t
                    lay = T.Layout.from_dict(it["layout"])
                    snap = snapshot_from_record(lay, d["grid"][r], d["aux"][r], t, it["tau"])
                    snaps.append({"bin": b, "donor_seed": it["layout"]["gen_seed"], "remaining": lay.limit - t,
                                  "suffix_offset": t - it["tau"], "snapshot": snap})
                bank[str(K)] = snaps
                bank_counts[f"{role}/K{K}"] = {b: sum(s["bin"] == b for s in snaps) for b in BINS}
            # Matched across K by construction: same donor, bin, suffix offset and remaining time.
            keys = lambda s: (s["bin"], s["donor_seed"], s["suffix_offset"], s["remaining"])
            for K in ([] if spec else cfg["Ks"][1:]):
                assert [keys(s) for s in bank[str(K)]] == [keys(s) for s in bank[str(cfg["Ks"][0])]], "bank not matched"
            (out / f"bank_competence_{role}.json").write_text(json.dumps(bank))

        # Reset and anchor sampling indices over donor trajectories (per K, per bin/stage).
        idx = {}
        for role, kind in (("reset_donor", "reset"), ("anchor_donor", "anchor")):
            if role not in cfg["trajectory_roles"]:
                continue
            d = np.load(out / f"traj_{role}.npz")
            for K in cfg["Ks"]:
                donors = {it["traj_index"]: it for it in layouts[role] if it["layout"]["K"] == K}
                sel = {"entry": [], "retrieval": [], "carrying": [], "prefix": [], "suffix": []}
                for r in range(len(d["traj"])):
                    it = donors.get(int(d["traj"][r]))
                    if it is None:
                        continue
                    t = int(d["step_count"][r])
                    if t < it["tau"]:
                        sel["prefix"].append(r)
                        continue
                    sel["suffix"].append(r)
                    sel["entry" if t == it["tau"] else "retrieval" if t < it["pickup_t"] else "carrying"].append(r)
                for name, rows in sel.items():
                    idx[f"{kind}_K{K}_{name}"] = np.array(rows, np.int64)
        if idx or not base:
            np.savez(out / "banks_index.npz", **idx)

    manifest = {"schema": SCHEMA, "dataset_id": cfg["dataset_id"], "config": cfg,
                "registry_sha256": S.registry_hash(reg), "split_check": stats,
                "rejected_layouts": reg["rejected"], "planner_failures": failures,
                "counts": {r: len(v) for r, v in layouts.items()},
                "transitions": {r: int(np.load(out / f"traj_{r}.npz")["action"].shape[0]) for r in cfg["trajectory_roles"]},
                "bank_bin_counts": bank_counts, "index_sizes": {k: int(len(v)) for k, v in idx.items()},
                "wall_seconds": time.time() - t0,
                "files": {p.name: sha256(p) for p in sorted(out.iterdir()) if p.name != "manifest.json"}}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
    (run_dir / "summary.json").write_text(json.dumps({"dataset": str(out), "failures": len(failures),
                                                      "wall_seconds": manifest["wall_seconds"]}))
    print(json.dumps({"event": "done", "dataset": str(out), "failures": len(failures)}), flush=True)


if __name__ == "__main__":
    main()
