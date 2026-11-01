"""Behavior cloning on balanced K=1/K=3 planner demonstrations.

python -m bc2rl.bc --config experiments/m1/bc-curve-v1.json --seed 0

Sampler (fixed): every batch has batch_size/2 transitions from each K, uniform over transitions
within K (transition weighting, balanced across K). Calibration option (owner instruction 2026-11-01,
calibration study): with config "prefix_prob" = rho, each K's half-batch draws its prefix count from
Binomial(batch_size/2, rho) and the rest from the suffix; transitions are uniform within each K x stage pool.
Without "prefix_prob" the original sampler and its RNG stream are unchanged. Adam, cross-entropy, no label smoothing, no
entropy term. Checkpoints at fixed update counts save actor, optimizer, sampler RNG, torch RNG.
At each checkpoint: held-out loss/accuracy by stage and K; normal-start p, q on bc_val layouts;
competence c on the development bank. All evaluations sample the policy (common random numbers).
"""
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import torch

from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import task as T
from bc2rl.telemetry import Heartbeat, resource_heartbeat


def load_role(ds, role):
    d = dict(np.load(ds / f"traj_{role}.npz"))
    meta = [it for it in json.loads((ds / "layouts.json").read_text())[role] if "traj_index" in it]
    K_of = np.array([it["layout"]["K"] for it in sorted(meta, key=lambda m: m["traj_index"])])
    d["K"] = K_of[d["traj"]]
    return d, meta


def sample_batch(rng, by_K, by_KS, half, rho=None):
    """One BC batch of row indices: half from each K. rho None: uniform within K (the original sampler, same RNG
    calls). Otherwise prefix count ~ Binomial(half, rho) per K, uniform within each K x stage pool."""
    if rho is None:
        return np.concatenate([rng.choice(by_K[1], half), rng.choice(by_K[3], half)])
    parts = []
    for K in (1, 3):
        n_pre = int(rng.binomial(half, rho))
        parts += [rng.choice(by_KS[(K, "prefix")], n_pre), rng.choice(by_KS[(K, "suffix")], half - n_pre)]
    return np.concatenate(parts)


def to_dev(d, idx, device):
    return (torch.as_tensor(d["grid"][idx], device=device), torch.as_tensor(d["aux"][idx], device=device),
            torch.as_tensor(d["time"][idx][:, None], device=device))


def evaluate_checkpoint(actor, ds, cfg, device, val, val_meta, bank, hb, attempts_path=None):
    out = {}
    actor.eval()
    with torch.no_grad():
        losses, correct = [], []
        for s in range(0, len(val["action"]), 2048):
            idx = np.arange(s, min(s + 2048, len(val["action"])))
            logits = actor(*to_dev(val, idx, device))
            tgt = torch.as_tensor(val["action"][idx].astype(np.int64), device=device)
            losses.append(torch.nn.functional.cross_entropy(logits, tgt, reduction="none").cpu().numpy())
            correct.append((logits.argmax(1) == tgt).cpu().numpy())
        loss, acc = np.concatenate(losses), np.concatenate(correct)
        for K in (1, 3):
            for st, name in ((0, "prefix"), (1, "suffix")):
                m = (val["K"] == K) & ((val["stage"] == 0) if st == 0 else (val["stage"] > 0))
                out[f"val_loss_K{K}_{name}"] = float(loss[m].mean())
                out[f"val_acc_K{K}_{name}"] = float(acc[m].mean())
        out["val_loss"] = float(loss.mean())
    starts = [("layout", T.Layout.from_dict(it["layout"])) for it in val_meta]
    res, n_act = E.run_attempts(actor, starts, cfg["eval_attempts"], cfg["eval_seed"], device, heartbeat=hb)
    raw = [{"kind": "normal", "K": val_meta[r["item"]]["layout"]["K"], **r} for r in res]
    for K in (1, 3):
        items = [i for i, it in enumerate(val_meta) if it["layout"]["K"] == K]
        sub = [dict(r, item=items.index(r["item"])) for r in res if r["item"] in items]
        out[f"normal_K{K}"] = E.summarize(sub, len(items))
    for K in (1, 3):
        snaps = [("snapshot", s["snapshot"]) for s in bank[str(K)]]
        r2, n2 = E.run_attempts(actor, snaps, cfg["bank_attempts"], cfg["eval_seed"] + 1, device, heartbeat=hb)
        n_act += n2
        raw += [{"kind": "bank", "bank_K": K, "bin": bank[str(K)][r["item"]]["bin"], **r} for r in r2]
        out[f"bank_K{K}"] = E.summarize(r2, len(snaps))
        for b in ("entry", "retrieval", "carrying"):
            ids = [i for i, s in enumerate(bank[str(K)]) if s["bin"] == b]
            out[f"bank_K{K}_{b}"] = float(np.mean([r["success"] for r in r2 if r["item"] in ids]))
    out["eval_env_actions"] = n_act
    if attempts_path is not None:
        tmp = Path(str(attempts_path) + ".tmp")
        tmp.write_text("".join(json.dumps(r) + "\n" for r in raw))
        os.replace(tmp, attempts_path)
    actor.train()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, required=True)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    threads = int(os.environ.get("OMP_NUM_THREADS", "1"))
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    device = torch.device(os.environ.get("MAE_DEVICE", cfg.get("device", "cpu")))
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    ds = Path(os.environ.get("MAE_PROJECT", ".")) / "data" / cfg["dataset_id"]
    manifest = json.loads((ds / "manifest.json").read_text())
    (run_dir / "config.resolved.json").write_text(json.dumps(
        {**cfg, "seed": a.seed, "device": str(device), "threads": threads,
         "dataset_files": manifest["files"]}, indent=1))
    torch.manual_seed(a.seed)
    rng = np.random.default_rng([a.seed, 7])
    last = [time.time()]

    def hb():
        if time.time() - last[0] > 5:
            resource_heartbeat()
            last[0] = time.time()

    with Heartbeat(interval=5):
        train, _ = load_role(ds, "bc_train")
        val, val_meta = load_role(ds, "bc_val")
        bank = json.loads((ds / "bank_competence_dev_bank.json").read_text())
        by_K = {K: np.nonzero(train["K"] == K)[0] for K in (1, 3)}
        rho = cfg.get("prefix_prob")
        by_KS = {(K, s): np.nonzero((train["K"] == K) & ((train["stage"] == 0) if s == "prefix" else (train["stage"] > 0)))[0]
                 for K in (1, 3) for s in ("prefix", "suffix")}
        actor = M.Actor().to(device)
        opt = torch.optim.Adam(actor.parameters(), lr=cfg["lr"])
        half = cfg["batch_size"] // 2
        ckpts = sorted(cfg["checkpoints"])
        metrics = (run_dir / "metrics.jsonl").open("w")
        t0 = time.time()
        run_loss = []
        for u in range(1, ckpts[-1] + 1):
            idx = sample_batch(rng, by_K, by_KS, half, rho)
            logits = actor(*to_dev(train, idx, device))
            loss = torch.nn.functional.cross_entropy(
                logits, torch.as_tensor(train["action"][idx].astype(np.int64), device=device))
            opt.zero_grad()
            loss.backward()
            opt.step()
            run_loss.append(loss.item())
            if u in ckpts:
                ev = evaluate_checkpoint(actor, ds, cfg, device, val, val_meta, bank, hb,
                                         attempts_path=run_dir / f"attempts_u{u}.jsonl")
                rec = {"update": u, "train_loss": float(np.mean(run_loss)), "elapsed": time.time() - t0, **ev}
                run_loss = []
                metrics.write(json.dumps(rec) + "\n")
                metrics.flush()
                torch.save({"actor": actor.state_dict(), "optimizer": opt.state_dict(), "update": u,
                            "sampler_rng": rng.bit_generator.state, "torch_rng": torch.get_rng_state(),
                            "seed": a.seed, "config": cfg}, run_dir / f"actor_u{u}.pt.tmp")
                os.replace(run_dir / f"actor_u{u}.pt.tmp", run_dir / f"actor_u{u}.pt")
                print(json.dumps({"update": u, "val_loss": ev["val_loss"],
                                  "p": [ev["normal_K1"]["P1"], ev["normal_K3"]["P1"]],
                                  "q": [ev["normal_K1"]["q"], ev["normal_K3"]["q"]],
                                  "c": [ev["bank_K1"]["P1"], ev["bank_K3"]["P1"]]}), flush=True)
    (run_dir / "summary.json").write_text(json.dumps({"updates": ckpts[-1], "checkpoints": ckpts,
                                                      "wall_seconds": time.time() - t0}))


if __name__ == "__main__":
    main()
