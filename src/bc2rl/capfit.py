"""Actor capability audit: supervised fitting (owner instruction 2026-11-03; PROTOCOL_FREEZE Amendment 10).
No environment actions. Device MPS where available.

python -m bc2rl.capfit tiny --config experiments/p8/fit-v1.json --lr LR
python -m bc2rl.capfit fit  --config experiments/p8/fit-v1.json --init warm|scratch --hidden H --size K --seed S
python -m bc2rl.capfit test --config experiments/p8/fit-v1.json

Loss: set loss = -log(sum of policy probabilities over the valid label set) (floor 0). It differs from the 2026-11-02c
auxiliary loss (cross-entropy to a uniform target over the set, floor = log of the set size); it does not revise that
study. Metrics per state: argmax-in-set (1 if the most probable action is in the set), mass on the set, set loss.

tiny  original actor from scratch, the frozen 512-state audited set, full batch, fixed update limit; logs loss,
      agreement, mass and gradient norm; checks loss reduction (batch mean equals the mean of per-row losses),
      preprocessing (dataset tensors give the same logits as the rollout path bc2rl.model.obs_to_torch) and labels
      (non-empty, done never labelled).
fit   Adam, batch 512, per-epoch permutation from torch.Generator(seed) (identical for equal subset sizes and seeds),
      fixed update limit. Every eval_every updates: full validation set and a fixed 10,000-row training probe. The
      selected checkpoint has the highest validation argmax-in-set (ties: the earlier one). The final test set is not
      read.
test  Loads every selected checkpoint listed in the config and scores the final test set and the recovery bank once.
"""
import argparse
import json
import os
from pathlib import Path
import time

import numpy as np
import torch
from torch import nn

from bc2rl import battery as BAT
from bc2rl import model as M
from bc2rl.telemetry import Heartbeat

DONE = 6


class CapActor(nn.Module):
    """bc2rl.model.Actor with a configurable dense width. hidden=128 has the same parameters and keys as Actor."""

    def __init__(self, hidden=128):
        super().__init__()
        self.enc = M.Encoder(hidden)
        self.head = nn.Linear(hidden, 7)

    def forward(self, grid, aux, time):
        return self.head(self.enc(grid, aux, time))


def device():
    return torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")


def mask_bits(mask):
    return ((torch.as_tensor(mask, dtype=torch.long)[:, None] >> torch.arange(7)) & 1).bool()


def set_loss(logits, valid):
    return -(logits.masked_fill(~valid, float("-inf")).logsumexp(-1) - logits.logsumexp(-1))


def load_split(z, prefix, dev):
    return {"grid": torch.as_tensor(z[prefix + "_grid"], device=dev),
            "aux": torch.as_tensor(z[prefix + "_aux"].astype(np.int64), device=dev),
            "time": torch.as_tensor(z[prefix + "_time"][:, None], device=dev),
            "valid": mask_bits(z[prefix + "_mask"]).to(dev)}


def take(split, idx):
    return {k: v[idx] for k, v in split.items()}


@torch.no_grad()
def score(model, split, batch=4096):
    model.eval()
    n = len(split["valid"])
    agree, mass, loss = [], [], []
    for i in range(0, n, batch):
        s = {k: v[i:i + batch] for k, v in split.items()}
        lg = model(s["grid"], s["aux"], s["time"]).float()
        p = torch.softmax(lg, -1)
        agree.append(s["valid"].gather(1, lg.argmax(-1, keepdim=True))[:, 0].float())
        mass.append((p * s["valid"]).sum(-1))
        loss.append(set_loss(lg, s["valid"]))
    model.train()
    return {k: torch.cat(v).cpu().numpy() for k, v in (("agree", agree), ("mass", mass), ("loss", loss))}


def summ(r):
    return {"argmax_in_set": float(r["agree"].mean()), "mass": float(r["mass"].mean()), "set_loss": float(r["loss"].mean())}


def grad_norm(model):
    return float(torch.sqrt(sum((p.grad.float() ** 2).sum() for p in model.parameters() if p.grad is not None)))


def project_dir():
    return Path(os.environ.get("MAE_PROJECT", "."))


def run_dir():
    return Path(os.environ.get("MAE_RUN_DIR", "."))


def dataset(project, cfg):
    return np.load(project / cfg["dataset"])


def tiny(cfg, lr):
    project, dev = project_dir(), device()
    z = dataset(project, cfg)
    tr = load_split(z, "tiny", dev)
    torch.manual_seed(cfg["tiny"]["init_seed"])
    model = CapActor(128).to(dev)
    # label and preprocessing checks
    v = tr["valid"].cpu()
    assert bool(v.any(-1).all()) and not bool(v[:, DONE].any()), "empty label or done labelled"
    o = {"grid": z["tiny_grid"][:16], "aux": z["tiny_aux"][:16].astype(np.int64), "time": z["tiny_time"][:16, None]}
    with torch.no_grad():
        same = torch.allclose(model(*M.obs_to_torch(o, dev)), model(tr["grid"][:16], tr["aux"][:16], tr["time"][:16]))
    opt = torch.optim.Adam(model.parameters(), lr)
    curve, t0 = [], time.time()
    for u in range(1, cfg["tiny"]["updates"] + 1):
        lg = model(tr["grid"], tr["aux"], tr["time"])
        per = set_loss(lg, tr["valid"])
        loss = per.mean()
        opt.zero_grad()
        loss.backward()
        if u == 1:
            red_ok = abs(float(loss.detach()) - float(per.detach().sum() / len(per))) < 1e-5
        gn = grad_norm(model)
        opt.step()
        if u % cfg["tiny"]["log_every"] == 0 or u == 1:
            r = summ(score(model, tr))
            curve.append({"update": u, **r, "grad_norm": gn})
    final = curve[-1]
    BAT.write_atomic(run_dir() / "summary.json", {
        "complete": True, "mode": "tiny", "lr": lr, "n": int(len(tr["valid"])), "updates": cfg["tiny"]["updates"],
        "final": final, "curve": curve, "checks": {"loss_reduction_mean": red_ok, "preprocessing_same_logits": bool(same),
                                                   "labels_nonempty_no_done": True},
        "passes": final["argmax_in_set"] >= cfg["tiny"]["pass_agree"] and final["set_loss"] <= cfg["tiny"]["pass_loss"],
        "compute_seconds": time.time() - t0, "device": str(dev)})


def fit(cfg, init, hidden, size, seed):
    project, dev = project_dir(), device()
    z = dataset(project, cfg)
    train_all = load_split(z, "train", dev)
    sub = torch.as_tensor(z[f"subset_{size}"], device=dev)
    train = take(train_all, sub)
    val = load_split(z, "val", dev)
    n = len(sub)
    probe_idx = torch.as_tensor(np.sort(np.random.default_rng(cfg["probe_seed"]).choice(n, min(n, 10_000), replace=False)),
                                device=dev)
    probe = take(train, probe_idx)
    torch.manual_seed(cfg["init_seed_base"] + seed)
    model = CapActor(hidden)
    if init == "warm":
        assert hidden == 128
        bc = cfg["warm"][str(seed)]
        d = sorted(d for d in (project / ".mae/runs").glob(f"*/{bc['job']}") if (d / "summary.json").exists())[-1]
        model.load_state_dict(torch.load(d / f"actor_u{bc['update']}.pt", map_location="cpu", weights_only=False)["actor"])
    model.to(dev)
    opt = torch.optim.Adam(model.parameters(), cfg["lr"])
    gen = torch.Generator().manual_seed(cfg["batch_seed_base"] + seed)
    B, U, E = cfg["batch"], cfg["updates"], cfg["eval_every"]
    perm, pos = torch.randperm(n, generator=gen), 0
    curve, best, best_state = [], None, None
    t_train = 0.0
    t_all = time.time()
    r0v, r0p = summ(score(model, val)), summ(score(model, probe))
    curve.append({"update": 0, "val": r0v, "train_probe": r0p})
    for u in range(1, U + 1):
        if pos + B > n:
            perm, pos = torch.randperm(n, generator=gen), 0
        idx = perm[pos:pos + B].to(dev)
        pos += B
        t0 = time.time()
        s = take(train, idx)
        loss = set_loss(model(s["grid"], s["aux"], s["time"]), s["valid"]).mean()
        opt.zero_grad()
        loss.backward()
        gn = grad_norm(model) if u % E == 0 else None
        opt.step()
        t_train += time.time() - t0
        if u % E == 0:
            if BAT.flag_path(project).exists():
                raise SystemExit(BAT.PAUSED_EXIT)
            rv, rp = summ(score(model, val)), summ(score(model, probe))
            curve.append({"update": u, "val": rv, "train_probe": rp, "grad_norm": gn, "batch_loss": float(loss.detach())})
            if best is None or rv["argmax_in_set"] > best["val"]["argmax_in_set"]:
                best = curve[-1]
                best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    if dev.type == "mps":
        torch.mps.synchronize()
    torch.save({"state": best_state, "hidden": hidden, "update": best["update"]}, run_dir() / "selected.pt")
    torch.save({"state": {k: v.detach().cpu() for k, v in model.state_dict().items()}, "hidden": hidden, "update": U},
               run_dir() / "final.pt")
    (run_dir() / "curve.json").write_text(json.dumps(curve))
    BAT.write_atomic(run_dir() / "summary.json", {
        "complete": True, "mode": "fit", "init": init, "hidden": hidden, "size": size, "n_train": n, "seed": seed,
        "params": M.n_params(model), "updates": U, "selected_update": best["update"], "selected": best,
        "final": curve[-1], "train_seconds": t_train, "compute_seconds": time.time() - t_all, "device": str(dev)})


def load_selected(project, job, map_location="cpu"):
    d = sorted(d for d in (project / ".mae/runs").glob(f"*/{job}") if (d / "summary.json").exists())[-1]
    st = torch.load(d / "selected.pt", map_location=map_location, weights_only=False)
    m = CapActor(st["hidden"])
    m.load_state_dict(st["state"])
    m.eval()
    return m


def test(cfg):
    project, dev = project_dir(), device()
    z = dataset(project, cfg)
    sets = {"test": load_split(z, "test", dev), "recov": load_split(z, "recov", dev)}
    out, preds = {}, {}
    t0 = time.time()
    for job in cfg["test_jobs"]:
        m = load_selected(project, job).to(dev)
        out[job] = {}
        for name, s in sets.items():
            r = score(m, s)
            out[job][name] = summ(r)
            preds[f"{job}|{name}|agree"] = r["agree"].astype(np.int8)
            preds[f"{job}|{name}|mass"] = r["mass"].astype(np.float32)
            preds[f"{job}|{name}|loss"] = r["loss"].astype(np.float32)
    np.savez_compressed(run_dir() / "test_predictions.npz", **preds)
    BAT.write_atomic(run_dir() / "summary.json", {"complete": True, "mode": "test", "results": out,
                                                  "compute_seconds": time.time() - t0, "device": str(dev)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("tiny", "fit", "test"))
    ap.add_argument("--config", required=True)
    ap.add_argument("--lr", type=float)
    ap.add_argument("--init", choices=("warm", "scratch"))
    ap.add_argument("--hidden", type=int, default=128)
    ap.add_argument("--size", type=int)
    ap.add_argument("--seed", type=int)
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission("capfit_" + a.mode)
    with Heartbeat(interval=5):      # the runner stops MPS jobs without fresh telemetry (first tiny batch, 2026-11-03)
        if a.mode == "tiny":
            tiny(cfg, a.lr)
        elif a.mode == "fit":
            fit(cfg, a.init, a.hidden, a.size, a.seed)
        else:
            test(cfg)


if __name__ == "__main__":
    main()
