"""CPU vs MPS throughput benchmark with the real model and environment (non-scientific).

One cycle = collect 4 envs x 128 transitions (sampled actions from the actor, critic values),
then 4 epochs x 4 minibatches of 128 actor+critic updates with an extra 128-state actor forward
for a KL-style anchor term. Separately times BC steps (batch 256). Writes metrics.jsonl per cycle
and summary.json to MAE_RUN_DIR.

python -m bc2rl.bench --device cpu --threads 4 --seconds 150
"""
import argparse
import json
import os
from pathlib import Path
import resource
import time

import numpy as np
import torch

from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import task as T
from bc2rl.telemetry import Heartbeat

BENCH_SEED0 = 4_000_000_000   # outside every role namespace draw (checked against the registry later)


def sync(device):
    if device.type == "mps":
        torch.mps.synchronize()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--threads", type=int, default=1)
    ap.add_argument("--seconds", type=float, default=150)
    ap.add_argument("--layouts", type=int, default=64)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    device = torch.device(a.device)
    run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
    rng = np.random.default_rng(0)
    with Heartbeat(interval=5):
        layouts = [P.plan_and_verify(T.generate_layout(1 + 2 * (i % 2), BENCH_SEED0 + i), i, 24, 80)[0]
                   for i in range(a.layouts)]
        actor, critic = M.Actor().to(device), M.Critic().to(device)
        opt_a = torch.optim.Adam(actor.parameters(), lr=3e-4)
        opt_c = torch.optim.Adam(critic.parameters(), lr=3e-4)
        envs = [T.StageTask() for _ in range(4)]
        obs = [e.reset(options={"layout": layouts[rng.integers(len(layouts))]})[0] for e in envs]
        start = time.time()
        cycles, metrics = 0, []
        f = (run_dir / "metrics.jsonl").open("w")
        while time.time() - start < a.seconds:
            t0 = time.perf_counter()
            buf = {k: [] for k in ("grid", "aux", "time")}
            env_time = 0.0
            for _ in range(128):
                batch = {k: np.stack([o[k] for o in obs]) for k in ("grid", "aux", "time")}
                with torch.no_grad():
                    g, x, tm = M.obs_to_torch(batch, device)
                    logits = actor(g, x, tm)
                    critic(g, x, tm)
                    act = torch.distributions.Categorical(logits=logits).sample().cpu().numpy()
                for k in buf:
                    buf[k].append(batch[k])
                te = time.perf_counter()
                for i, e in enumerate(envs):
                    o, r, term, _, _ = e.step(int(act[i]))
                    if term:
                        o, _ = e.reset(options={"layout": layouts[rng.integers(len(layouts))]})
                    obs[i] = o
                env_time += time.perf_counter() - te
            sync(device)
            t1 = time.perf_counter()
            data = {k: torch.as_tensor(np.concatenate(v), device=device) for k, v in buf.items()}
            acts = torch.as_tensor(rng.integers(7, size=512), device=device)
            adv = torch.randn(512, device=device)
            ret = torch.rand(512, device=device)
            for _ in range(4):
                perm = torch.randperm(512, device=device)
                for mb in perm.split(128):
                    logits = actor(data["grid"][mb], data["aux"][mb], data["time"][mb])
                    logp = torch.log_softmax(logits, -1).gather(1, acts[mb, None]).squeeze(1)
                    anchor = torch.log_softmax(actor(data["grid"][mb], data["aux"][mb], data["time"][mb]), -1)
                    loss_a = -(logp * adv[mb]).mean() + 0.1 * anchor.exp().mean()
                    opt_a.zero_grad()
                    loss_a.backward()
                    torch.nn.utils.clip_grad_norm_(actor.parameters(), 0.5)
                    opt_a.step()
                    v = critic(data["grid"][mb], data["aux"][mb], data["time"][mb])
                    loss_c = ((v - ret[mb]) ** 2).mean()
                    opt_c.zero_grad()
                    loss_c.backward()
                    torch.nn.utils.clip_grad_norm_(critic.parameters(), 0.5)
                    opt_c.step()
            sync(device)
            t2 = time.perf_counter()
            cycles += 1
            m = {"cycle": cycles, "rollout_s": t1 - t0, "env_s": env_time, "update_s": t2 - t1,
                 "steps_per_s": 512 / (t2 - t0), "elapsed": time.time() - start}
            metrics.append(m)
            f.write(json.dumps(m) + "\n")
            f.flush()
        # BC throughput: batch 256 cross-entropy steps.
        sel = torch.randint(0, 512, (256,), device=device)
        t3 = time.perf_counter()
        for _ in range(50):
            loss = torch.nn.functional.cross_entropy(actor(data["grid"][sel], data["aux"][sel], data["time"][sel]), acts[sel])
            opt_a.zero_grad()
            loss.backward()
            opt_a.step()
        sync(device)
        bc_rate = 50 / (time.perf_counter() - t3)
        # Checkpoint latency.
        t4 = time.perf_counter()
        torch.save({"actor": actor.state_dict(), "critic": critic.state_dict(), "opt_a": opt_a.state_dict(),
                    "opt_c": opt_c.state_dict()}, run_dir / "ckpt.pt")
        ckpt_s = time.perf_counter() - t4
    warm = metrics[2:] if len(metrics) > 4 else metrics
    half = len(warm) // 2
    summary = {"device": a.device, "threads": a.threads, "cycles": cycles,
               "steps_per_s_mean": float(np.mean([m["steps_per_s"] for m in warm])),
               "steps_per_s_first_half": float(np.mean([m["steps_per_s"] for m in warm[:half]])) if half else None,
               "steps_per_s_second_half": float(np.mean([m["steps_per_s"] for m in warm[half:]])) if half else None,
               "rollout_s_mean": float(np.mean([m["rollout_s"] for m in warm])),
               "env_s_mean": float(np.mean([m["env_s"] for m in warm])),
               "update_s_mean": float(np.mean([m["update_s"] for m in warm])),
               "bc_steps_per_s": bc_rate, "checkpoint_s": ckpt_s,
               "max_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 30,
               "mps_driver_gb": (torch.mps.driver_allocated_memory() / 2 ** 30) if a.device == "mps" else 0.0,
               "actor_params": M.n_params(actor), "critic_params": M.n_params(critic)}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
