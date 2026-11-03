"""Probe and branch jobs.

probe:  python -m bc2rl.rl probe  --config C --K 1 --bc-run DIR --bc-update U --seed S
        pi0 evaluation -> critic pre-fit on pi0 normal-start returns (held-out calibration) ->
        fixed ordinary-PPO probe -> post-probe evaluation -> hashed fork state.
branch: python -m bc2rl.rl branch --config C --probe-run DIR --arm 10
        load fork (verify hash) -> continuation with the arm's interventions -> evaluations.
resume: python -m bc2rl.rl resume --config C --state DIR/state_<n>.pt
        load a complete saved branch state (verify hash) -> continue the same trajectory to the
        config's cumulative continuation_actions; scheduled evaluations and states beyond n only.

Optional config keys (absent in M3 configs, so earlier runs are unchanged):
  diag_role: layout role for the pi0 and post-probe normal-start diagnostics (default: eval_role).
  eval_schedule: [{"at": actions, "attempts": n, "bank_attempts": m, "tag": t}, ...]
      evaluations at exact cumulative post-probe action counts (multiples of the rollout size);
      the entry at the endpoint is the final evaluation. Replaces curve_every/final_attempts.
      Optional per entry: "layouts": "diag" evaluates normal starts on the diag_role layouts
      (default: eval_role); "endpoint": true counts an earlier point as eval_final (a second endpoint).
  save_state_at: [actions, ...]  complete learner state (actor, critic, both optimizers, all RNGs,
      sampler streams, in-flight environments, counters) + pi0, hashed, as state_<actions>.pt.
  recovery_every: n  (owner instruction 2026-11-01c) also save the same complete state as recovery.pt (atomic
      replace; only the latest is kept) every n post-probe actions; removed when the job completes.
  extra_banks: [{"name": n, "path": p}]  further fixed snapshot banks (list of {"snapshot": ...}; path relative to
      the project), evaluated with the same bank_attempts on eval_seed + 2 + index; attempt rows kind "bank_extra".

Auxiliary supervision (owner instruction 2026-11-02c): arms C7 / R7 attach a bc2rl.aux_sup source with coefficient
  cfg["aux_coef"]. R7 needs --match-run (the same seed's completed C7 branch, whose aux_schedule.json fixes R7's
  per-update example counts). Optional cfg["recovery_bank"] (path relative to the project): a fixed held-out bank of
  labelled prefix states; at the fork and at every scheduled evaluation the actor's probability mass on the label set
  and the share of states whose argmax is in the label set are recorded (forward passes only; no environment actions).

Battery (owner instruction 2026-11-01c; bc2rl.battery): every job checks admission at start and exits 75 without work
when refused. In scheduled branch/resume jobs SIGTERM (sent by the runner after a STOP) requests checkpoint-and-pause:
at the next update boundary the job saves recovery.pt, writes paused.json (resume point, hash, actions of this job)
and exits 75. It never writes summary.json then, so a paused job is never counted as complete.

Paths: --bc-run / --probe-run / --state are relative to $MAE_PROJECT/.mae/runs, or "@/job" for a job
earlier in the same batch. All evaluation uses the
same eval seeds for every policy (common random numbers). Every environment action is counted by
role: critic_warmup, probe/continuation training, and evaluation (diagnostic or final).
"""
import argparse
import copy
import json
import os
from pathlib import Path
import signal
import time

import numpy as np
import torch

from bc2rl import battery as BAT
from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import ppo as PP
from bc2rl import suffix_cert as SC
from bc2rl import task as T
from bc2rl.telemetry import Heartbeat, resource_heartbeat

RESET_MIXTURE = [("entry", 0.5), ("retrieval", 0.25), ("carrying", 0.25)]


def cert_summary(res, n_items):
    """Item-weighted shares of normal-start attempts whose actual arrival was certified feasible / unresolved /
    impossible (verified finishable access = feasible; unresolved is never counted as finishable)."""
    out = {}
    for st in ("feasible", "unresolved", "impossible"):
        per = {}
        for r in res:
            per.setdefault(r["item"], []).append(r["arrival"] is not None and r["arrival"]["cert"]["status"] == st)
        out[f"q_{st}"] = float(np.mean([np.mean(per[i]) for i in range(n_items)]))
    return out


class Ctx:
    def __init__(self, cfg, K, seed):
        self.cfg, self.K, self.seed = cfg, K, seed
        self.project = Path(os.environ.get("MAE_PROJECT", "."))
        self.ds = self.project / "data" / cfg["dataset_id"]
        self.run_dir = Path(os.environ.get("MAE_RUN_DIR", "."))
        threads = int(os.environ.get("OMP_NUM_THREADS", "1"))
        torch.set_num_threads(threads)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:              # already set in this process (in-process tests only)
            assert torch.get_num_interop_threads() == 1
        self.device = torch.device(os.environ.get("MAE_DEVICE", "cpu"))
        lay = json.loads((self.ds / "layouts.json").read_text())
        pick = lambda role: [T.Layout.from_dict(it["layout"]) for it in lay[role] if it["layout"]["K"] == K]
        self.train_layouts = pick("rl_train")
        self.eval_layouts = pick(cfg["eval_role"])
        if cfg.get("eval_layouts_n"):        # component experiment: the first n layouts of the role (fixed rule)
            self.eval_layouts = self.eval_layouts[:cfg["eval_layouts_n"]]
        # pi0 / post-probe diagnostics may use their own layouts (diag_role); default: the eval role.
        self.diag_layouts = pick(cfg.get("diag_role", cfg["eval_role"]))
        self.bank = json.loads((self.ds / f"bank_competence_{cfg['bank_role']}.json").read_text())[str(K)]
        self.extra_banks = [(b["name"], json.loads((self.project / b["path"]).read_text())["states"])
                            for b in cfg.get("extra_banks", [])]
        self.metrics = (self.run_dir / "metrics.jsonl").open("a")
        self.actions = {"critic_warmup": 0, "train": 0, "eval_diagnostic": 0, "eval_final": 0}
        self.compute = {"actor_minibatches": 0, "critic_fit_steps": 0}
        self._last = time.time()

    def hb(self):
        if time.time() - self._last > 5:
            resource_heartbeat()
            self._last = time.time()

    def log(self, rec):
        self.metrics.write(json.dumps(rec) + "\n")
        self.metrics.flush()

    def anchors(self, pi0):
        bank = PP.ResetBank(self.ds, "anchor_donor", self.K, "anchor")
        pre, suf = bank.rows("prefix"), bank.rows("suffix")
        rows = np.concatenate([pre, suf])
        w = np.concatenate([np.full(len(pre), self.cfg["anchor_prefix_weight"] / len(pre)),
                            np.full(len(suf), (1 - self.cfg["anchor_prefix_weight"]) / len(suf))])
        dev = self.device
        A = {"grid": torch.as_tensor(bank.grid[rows], device=dev), "aux": torch.as_tensor(bank.aux[rows], device=dev),
             "time": torch.as_tensor(bank.d["time"][rows][:, None], device=dev), "weights": w / w.sum(),
             "is_prefix": torch.as_tensor(np.arange(len(rows)) < len(pre), device=dev)}
        with torch.inference_mode():
            pi0.eval()
            A["ref_logp"] = torch.cat([torch.log_softmax(pi0(A["grid"][s:s + 1024], A["aux"][s:s + 1024],
                                                                A["time"][s:s + 1024]).float(), -1)
                                       for s in range(0, len(rows), 1024)]).clone()
        return A, {"prefix_states": int(len(pre)), "suffix_states": int(len(suf)),
                   "prefix_weight": self.cfg["anchor_prefix_weight"]}

    def sampler(self, alpha, arm=None):
        sched = self.cfg.get("assist_schedule", {}).get(arm) if alpha > 0 else None
        if sched is not None:      # 2026-11-02 pilot arms: phases by executed continuation actions (clock set later)
            names = sorted({b for ph in sched for b, _ in ph["mixture"]})
            bins = PP.ResetBank(self.ds, "reset_donor", self.K, "reset").bins(names)
            return PP.StartSampler(self.train_layouts, bins, alpha, None, [self.seed, 31], schedule=sched)
        bins = PP.ResetBank(self.ds, "reset_donor", self.K, "reset").bins([b for b, _ in RESET_MIXTURE]) if alpha > 0 else {}
        return PP.StartSampler(self.train_layouts, bins, alpha, RESET_MIXTURE, [self.seed, 31])

    def evaluate(self, actor, attempts, bank_attempts, role, tag, layouts=None, certify=None):
        starts = [("layout", L) for L in (self.eval_layouts if layouts is None else layouts)]
        cert = bool(self.cfg.get("certify_arrivals") if certify is None else certify)
        res, n1 = E.run_attempts(actor, starts, attempts, self.cfg["eval_seed"], self.device, heartbeat=self.hb,
                                 capture=cert, trace=bool(self.cfg.get("trace_eval")))
        if cert:                   # 2026-11-02: planner certification of each actual arrival (replay actions counted)
            nc = 0
            for r in res:
                if r["arrival"] is not None:
                    c = SC.certify(r["arrival"].pop("snapshot"))
                    nc += c["replay_actions"]
                    r["arrival"]["cert"] = c
            self.actions["certification"] = self.actions.get("certification", 0) + nc
        snaps = [("snapshot", s["snapshot"]) for s in self.bank]
        bres, n2 = (E.run_attempts(actor, snaps, bank_attempts, self.cfg["eval_seed"] + 1, self.device, heartbeat=self.hb)
                    if bank_attempts else ([], 0))
        extra, n3 = {}, 0
        for k, (name, states) in enumerate(self.extra_banks):
            if bank_attempts:
                xs = [("snapshot", s["snapshot"]) for s in states]
                xres, nx = E.run_attempts(actor, xs, bank_attempts, self.cfg["eval_seed"] + 2 + k, self.device, heartbeat=self.hb)
                extra[name] = (xres, len(xs))
                n3 += nx
        self.actions[role] += n1 + n2 + n3
        present = [b for b in ("entry", "retrieval", "carrying") if any(s["bin"] == b for s in self.bank)]
        out = {"tag": tag, "normal": {**E.summarize(res, len(starts)), **(cert_summary(res, len(starts)) if cert else {})},
               "bank": E.summarize(bres, len(snaps)) if bres else None,
               "bank_bins": {b: float(np.mean([r["success"] for r in bres if self.bank[r["item"]]["bin"] == b]))
                             for b in present} if bres else None,
               "extra_banks": {n: E.summarize(x, m) for n, (x, m) in extra.items()},
               "eval_actions": n1 + n2 + n3}
        tmp = self.run_dir / f"attempts_{tag}.jsonl.tmp"
        with tmp.open("w") as f:
            for r in res:
                f.write(json.dumps({"kind": "normal", **r}) + "\n")
            for r in bres:
                f.write(json.dumps({"kind": "bank", "bin": self.bank[r["item"]]["bin"], **r}) + "\n")
            for name, (xres, _) in extra.items():
                for r in xres:
                    f.write(json.dumps({"kind": "bank_extra", "bank": name, **r}) + "\n")
        os.replace(tmp, self.run_dir / f"attempts_{tag}.jsonl")
        return out


def attach_aux(ctx, cfg, learner, arm, seed, match_run):
    """Set learner.aux for arms C7 / R7 (before learner.load, so a saved source state is restored)."""
    from bc2rl import aux_sup as AS
    step = learner.n_envs * learner.n_steps
    updates = -(-cfg["continuation_actions"] // step)
    if arm == "C7":
        learner.aux = AS.Corrections(seed, cfg["aux_coef"], cfg.get("aux_cap", AS.CAP), cfg.get("aux_quota", AS.QUOTA))
    elif arm == "R7" and str(match_run).endswith(".json"):
        # confirmation with R7 selected (no C7 branch): the frozen development-derived schedule file
        path = ctx.project / match_run
        learner.aux = AS.DemoReplay(seed, cfg["aux_coef"], ctx.ds, AS.load_c_schedule(path, updates))
        return str(match_run)
    elif arm == "R7":
        assert match_run, "arm R7 needs --match-run (the same seed's completed C7 branch, or a schedule file)"
        mdir = run_path(match_run) if not str(match_run).startswith("/") else Path(match_run)
        msum = json.loads((mdir / "summary.json").read_text())
        assert msum["arm"] == "C7" and msum["seed"] == seed, "match run must be this seed's C7 branch"
        learner.aux = AS.DemoReplay(seed, cfg["aux_coef"], ctx.ds, AS.load_c_schedule(mdir / "aux_schedule.json", updates))
        return str(mdir)
    return None


def recovery_agreement(ctx, actor):
    """Label agreement of the actor on the fixed recovery bank (no environment actions)."""
    path = ctx.cfg.get("recovery_bank")
    if not path:
        return None
    if not hasattr(ctx, "_rbank"):
        b = json.loads((ctx.project / path).read_text())
        st = b["states"]
        ctx._rbank = {"grid": torch.as_tensor(np.array([s["obs"]["grid"] for s in st], np.uint8), device=ctx.device),
                      "aux": torch.as_tensor(np.array([s["obs"]["aux"] for s in st], np.int64), device=ctx.device),
                      "time": torch.as_tensor(np.array([s["obs"]["time"] for s in st], np.float32), device=ctx.device),
                      "mask": np.array([s["mask"] for s in st]), "cat": [s["stratum"] for s in st], "sha": b["sha256"]}
    R = ctx._rbank
    with torch.inference_mode():
        actor.eval()
        p = torch.cat([torch.softmax(actor(R["grid"][i:i + 512], R["aux"][i:i + 512], R["time"][i:i + 512]).float(), -1)
                       for i in range(0, len(R["mask"]), 512)]).cpu().numpy()
        actor.train()
    inset = np.array([[(m >> a) & 1 for a in range(7)] for m in R["mask"]], bool)
    mass = (p * inset).sum(1)
    top = inset[np.arange(len(p)), p.argmax(1)]
    out = {"n": int(len(p)), "mass": float(mass.mean()), "argmax_in_label": float(top.mean()), "bank_sha256": R["sha"],
           "by_stratum": {}}
    for c in sorted(set(R["cat"])):
        m = np.array([x == c for x in R["cat"]])
        out["by_stratum"][c] = {"n": int(m.sum()), "mass": float(mass[m].mean()), "argmax_in_label": float(top[m].mean())}
    return out


def critic_prefit(ctx, pi0, critic):
    """Fit the critic to pi0's actual normal-start returns (gamma = 1: 1 if the episode later succeeds).
    Episodes are split 80/20 for held-out calibration. Returns diagnostics."""
    cfg = ctx.cfg
    sampler = ctx.sampler(0.0)
    rng = np.random.default_rng([ctx.seed, 41])
    obs_all, ret_all, ep_all, stage_all, rem_all = [], [], [], [], []
    envs = [T.StageTask() for _ in range(cfg["n_envs"])]
    cur = [[] for _ in envs]
    obs = []
    for e in envs:
        kind, x, _ = sampler.draw()
        obs.append(e.reset(options={kind: x})[0])
    n_ep, actions, active = 0, 0, [True] * len(envs)
    pi0.eval()
    while any(active):
        b = {k: np.stack([o[k] for o in obs]) for k in ("grid", "aux", "time")}
        with torch.inference_mode():
            probs = torch.softmax(pi0(*M.obs_to_torch(b, ctx.device)).float(), -1).cpu().numpy().astype(np.float64)
        acts = E._sample(probs, rng.random(len(envs)))
        for i, e in enumerate(envs):
            if not active[i]:
                continue
            cur[i].append(({k: obs[i][k] for k in obs[i]}, e.stage(), e.remaining()))
            o, r, term, _, info = e.step(int(acts[i]))
            actions += 1
            obs[i] = o
            if term:
                for ob, st, rem in cur[i]:
                    obs_all.append(ob); ret_all.append(r); ep_all.append(n_ep); stage_all.append(st); rem_all.append(rem)
                n_ep += 1
                cur[i] = []
                if actions >= cfg["critic_warmup_actions"]:
                    active[i] = False      # finish in-flight episodes, then stop
                else:
                    kind, x, _ = sampler.draw()
                    obs[i] = e.reset(options={kind: x})[0]
        ctx.hb()
    ctx.actions["critic_warmup"] += actions
    ep = np.array(ep_all)
    # Episode-level split: 60% fit, 20% early-stopping validation, 20% held-out calibration.
    u_ep = rng.random(n_ep)
    is_test, is_val = (u_ep < 0.2)[ep], ((u_ep >= 0.2) & (u_ep < 0.4))[ep]
    G = {k: torch.as_tensor(np.stack([o[k] for o in obs_all]), device=ctx.device) for k in ("grid", "aux", "time")}
    y = torch.as_tensor(np.array(ret_all, np.float32), device=ctx.device)
    tr, va, te = np.nonzero(~is_test & ~is_val)[0], np.nonzero(is_val)[0], np.nonzero(is_test)[0]

    def predict():
        with torch.inference_mode():
            return torch.cat([critic(G["grid"][s:s + 2048], G["aux"][s:s + 2048], G["time"][s:s + 2048])
                              for s in range(0, len(y), 2048)]).float().cpu().numpy()

    yy = y.cpu().numpy()
    opt = torch.optim.Adam(critic.parameters(), lr=cfg["critic_prefit_lr"])
    best = (float(np.mean((predict()[va] - yy[va]) ** 2)), 0, copy.deepcopy(critic.state_dict()))
    for step in range(1, cfg["critic_prefit_steps"] + 1):
        idx = torch.as_tensor(rng.choice(tr, 256), device=ctx.device)
        loss = ((critic(G["grid"][idx], G["aux"][idx], G["time"][idx]) - y[idx]) ** 2).mean()
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(critic.parameters(), cfg["max_grad_norm"])
        opt.step()
        if step % 25 == 0:
            ctx.hb()
            v = float(np.mean((predict()[va] - yy[va]) ** 2))
            if v < best[0]:
                best = (v, step, copy.deepcopy(critic.state_dict()))
    critic.load_state_dict(best[2])
    ctx.compute["critic_fit_steps"] += cfg["critic_prefit_steps"]
    pred = predict()
    stage, rem = np.array(stage_all), np.array(rem_all)
    ep_return = {}
    for r, e in zip(ret_all, ep_all):
        ep_return[e] = r
    diag = {"episodes": n_ep, "actions": actions,
            "episode_success_rate": float(np.mean(list(ep_return.values()))) if ep_return else None,
            "state_mean_return": float(np.mean(ret_all)) if ret_all else None, "train_states": int(len(tr)), "val_states": int(len(va)),
            "test_states": int(len(te)), "best_step": best[1], "best_val_mse": best[0]}
    if len(te):
        base = float(yy[tr].mean())
        diag.update(test_mse=float(np.mean((pred[te] - yy[te]) ** 2)), test_mse_constant=float(np.mean((base - yy[te]) ** 2)))
        cal = {}
        for name, m in (("prefix", stage == 0), ("suffix_pre_pickup", stage == 1), ("carrying", stage == 2)):
            mm = m & is_test
            cal[name] = {"n": int(mm.sum()), "mean_pred": float(pred[mm].mean()) if mm.any() else None,
                         "mean_return": float(yy[mm].mean()) if mm.any() else None}
        for lo, hi in ((0, 40), (40, 80), (80, 200)):
            mm = (rem >= lo) & (rem < hi) & is_test
            cal[f"remaining_{lo}_{hi}"] = {"n": int(mm.sum()), "mean_pred": float(pred[mm].mean()) if mm.any() else None,
                                           "mean_return": float(yy[mm].mean()) if mm.any() else None}
        diag["calibration"] = cal
    return diag


def train_loop(ctx, learner, budget, tag, eval_every=None, eval_fn=None, on_update=None):
    start = learner.counters["env_actions"]
    t0 = time.time()
    while learner.counters["env_actions"] - start < budget:
        data = learner.collect()
        stats = learner.update(data)
        done = learner.counters["env_actions"] - start
        rec = {"phase": tag, "actions": done, "wall": time.time() - t0, **stats,
               "counters": dict(learner.counters)}
        ctx.log(rec)
        ctx.hb()
        if not all(np.isfinite(v) for v in stats.values() if isinstance(v, float)):
            raise FloatingPointError(f"non-finite PPO statistics: {stats}")
        if eval_every and eval_fn and done // eval_every != (done - learner.n_envs * learner.n_steps) // eval_every:
            eval_fn(done)
        if on_update:
            on_update(done)
    ctx.actions["train"] += learner.counters["env_actions"] - start
    return time.time() - t0


def run_path(rel):
    if rel.startswith("@/"):                  # a job earlier in the same batch
        return Path(os.environ["MAE_RUN_DIR"]).parent / rel[2:]
    return Path(os.environ.get("MAE_PROJECT", ".")) / ".mae/runs" / rel


def probe(a, cfg):
    ctx = Ctx(cfg, a.K, a.seed)
    bc_path = run_path(a.bc_run) / f"actor_u{a.bc_update}.pt"
    bc = torch.load(bc_path, map_location="cpu", weights_only=False)
    torch.manual_seed(a.seed * 1000 + 17)
    pi0 = M.Actor().to(ctx.device)
    pi0.load_state_dict(bc["actor"])
    for p in pi0.parameters():
        p.requires_grad_(False)
    actor = M.Actor().to(ctx.device)
    actor.load_state_dict(bc["actor"])
    critic = M.Critic().to(ctx.device)
    (ctx.run_dir / "config.resolved.json").write_text(json.dumps({**cfg, "mode": "probe", "K": a.K, "seed": a.seed,
        "bc_run": a.bc_run, "bc_update": a.bc_update, "bc_seed": bc["seed"], "device": str(ctx.device),
        "threads": torch.get_num_threads(), "actor_params": M.n_params(actor), "critic_params": M.n_params(critic)}, indent=1))
    t0 = time.time()
    with Heartbeat(interval=5):
        ev0 = ctx.evaluate(pi0, cfg["diag_attempts"], cfg["diag_bank_attempts"], "eval_diagnostic", "pi0", ctx.diag_layouts)
        ctx.log({"phase": "eval", **ev0})
        cdiag = critic_prefit(ctx, pi0, critic)
        ctx.log({"phase": "critic_prefit", **cdiag})
        anchors, anchor_info = ctx.anchors(pi0)
        learner = PP.PPO(actor, critic, cfg, ctx.device, ctx.sampler(0.0), anchors, use_kl=False, seed=a.seed)
        probe_wall = train_loop(ctx, learner, cfg["probe_actions"], "probe")
        ev1 = ctx.evaluate(actor, cfg["diag_attempts"], cfg["diag_bank_attempts"], "eval_diagnostic", "probe", ctx.diag_layouts)
        ctx.log({"phase": "eval", **ev1})
        st = learner.state()
        st["pi0"] = pi0.state_dict()
        fork_hash = PP.state_hash(st)
        tmp = ctx.run_dir / "fork.pt.tmp"
        torch.save(st, tmp)
        os.replace(tmp, ctx.run_dir / "fork.pt")
    ctx.compute["actor_minibatches"] += learner.counters["actor_minibatches"]
    summary = {"mode": "probe", "K": a.K, "seed": a.seed, "bc_update": a.bc_update, "fork_hash": fork_hash,
               "pi0": {"p": ev0["normal"]["P1"], "q": ev0["normal"]["q"], "c": ev0["bank"]["P1"], "bins": ev0["bank_bins"],
                       **({"extra_c": {n: v["P1"] for n, v in ev0["extra_banks"].items()}} if ev0["extra_banks"] else {})},
               "probe": {"p": ev1["normal"]["P1"], "q": ev1["normal"]["q"], "c": ev1["bank"]["P1"], "bins": ev1["bank_bins"],
                         **({"extra_c": {n: v["P1"] for n, v in ev1["extra_banks"].items()}} if ev1["extra_banks"] else {})},
               "delta_c": ev1["bank"]["P1"] - ev0["bank"]["P1"], "critic_prefit": cdiag, "anchors": anchor_info,
               "actions": ctx.actions, "compute": ctx.compute, "probe_wall_seconds": probe_wall,
               "wall_seconds": time.time() - t0, "counters": learner.counters}
    (ctx.run_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({k: summary[k] for k in ("pi0", "probe", "delta_c", "fork_hash")}), flush=True)


def branch(a, cfg):
    probe_dir = run_path(a.probe_run)
    psum = json.loads((probe_dir / "summary.json").read_text())
    pcfg = json.loads((probe_dir / "config.resolved.json").read_text())
    K, seed = psum["K"], psum["seed"]
    ctx = Ctx(cfg, K, seed)
    st = torch.load(probe_dir / "fork.pt", map_location="cpu", weights_only=False)
    assert PP.state_hash(st) == psum["fork_hash"], "fork state does not match recorded hash"
    use_reset, use_kl = PP.ARMS[a.arm]
    pi0 = M.Actor().to(ctx.device)
    pi0.load_state_dict(st["pi0"])
    for p in pi0.parameters():
        p.requires_grad_(False)
    actor, critic = M.Actor().to(ctx.device), M.Critic().to(ctx.device)
    anchors, anchor_info = ctx.anchors(pi0)
    alpha = cfg["alpha"] if use_reset else 0.0
    component = PP.COMPONENT.get(a.arm, "both")
    learner = PP.PPO(actor, critic, {**cfg, "kl_coef": PP.arm_kl_coef(a.arm, cfg)}, ctx.device,
                     ctx.sampler(alpha, a.arm), anchors, use_kl=use_kl, seed=seed, component=component)
    match = attach_aux(ctx, cfg, learner, a.arm, seed, getattr(a, "match_run", None))
    learner.load(st)
    fork_actions = learner.counters["env_actions"]
    learner.sampler.clock = lambda: learner.counters["env_actions"] - fork_actions
    loaded_hash = PP.state_hash({**learner.state(), "pi0": st["pi0"]})
    assert loaded_hash == psum["fork_hash"], "loaded learner state differs from fork"
    base_actions = learner.counters["env_actions"]
    (ctx.run_dir / "config.resolved.json").write_text(json.dumps({**cfg, "mode": "branch", "arm": a.arm,
        "alpha": alpha, "kl_coef": PP.arm_kl_coef(a.arm, cfg), "anchor_component": component,
        "kl_effective_prefix_suffix": PP.effective_coefficients(a.arm, cfg), "probe_run": str(probe_dir),
        "fork_hash": psum["fork_hash"], "K": K, "seed": seed, "bc_update": pcfg["bc_update"],
        "device": str(ctx.device)}, indent=1))
    if "eval_schedule" in cfg:
        return scheduled(ctx, cfg, learner, st["pi0"], {"mode": "branch", "arm": a.arm, "alpha": alpha,
                         "kl_coef": PP.arm_kl_coef(a.arm, cfg), "anchor_component": component,
                         "kl_effective_prefix_suffix": PP.effective_coefficients(a.arm, cfg),
                         "K": K, "seed": seed,
                         "bc_update": pcfg["bc_update"], "fork_hash": psum["fork_hash"],
                         "probe_run": str(probe_dir), "base_actions": base_actions, "resumed_from": None,
                         "anchors": anchor_info, "match_run": match})
    curve = []
    t0 = time.time()
    with Heartbeat(interval=5):
        def eval_fn(done):
            ev = ctx.evaluate(learner.actor, cfg["curve_attempts"], cfg["curve_bank_attempts"], "eval_diagnostic", f"curve_{done}")
            curve.append({"actions": done, "p": ev["normal"]["P1"], "q": ev["normal"]["q"], "c": ev["bank"]["P1"]})
            ctx.log({"phase": "eval", **ev})
        wall = train_loop(ctx, learner, cfg["continuation_actions"], "branch", cfg.get("curve_every"), eval_fn)
        evf = ctx.evaluate(learner.actor, cfg["final_attempts"], cfg["final_bank_attempts"], "eval_final", "final")
        ctx.log({"phase": "eval", **evf})
        tmp = ctx.run_dir / "final.pt.tmp"
        torch.save({"actor": learner.actor.state_dict(), "critic": learner.critic.state_dict(),
                    "counters": learner.counters}, tmp)
        os.replace(tmp, ctx.run_dir / "final.pt")
    c = learner.counters
    summary = {"mode": "branch", "arm": a.arm, "K": K, "seed": seed, "bc_update": pcfg["bc_update"],
               "fork_hash": psum["fork_hash"], "final": {"P1": evf["normal"]["P1"], "q": evf["normal"]["q"],
               "C4": evf["normal"].get("C4"), "R4": evf["normal"].get("R4"), "c": evf["bank"]["P1"],
               "bins": evf["bank_bins"], "P_success_given_arrival": evf["normal"]["P_success_given_arrival"]},
               "curve": curve, "continuation_actions": c["env_actions"] - base_actions,
               "actions": ctx.actions, "counters": c, "anchors": anchor_info,
               "train_wall_seconds": wall, "wall_seconds": time.time() - t0}
    (ctx.run_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"arm": a.arm, "final": summary["final"]}), flush=True)


def save_state(ctx, learner, pi0_state, meta, done, name=None):
    st = learner.state()
    st["pi0"] = pi0_state
    h = PP.state_hash(st)
    name = name or f"state_{done}.pt"
    tmp = ctx.run_dir / (name + ".tmp")
    torch.save({"state": st, "hash": h, "meta": {**meta, "post_probe_actions": done}}, tmp)
    os.replace(tmp, ctx.run_dir / name)
    return h


_SIGTERM = []


def _request_pause(sig, frame):
    _SIGTERM.append(sig)


def scheduled(ctx, cfg, learner, pi0_state, meta):
    """Continuation with evaluations and saved states at exact cumulative post-probe action counts.
    meta["base_actions"] = learner env_actions at the fork; done = actions since the fork."""
    step = learner.n_envs * learner.n_steps
    target = -(-cfg["continuation_actions"] // step) * step       # executed: whole rollouts
    sched = {e["at"]: e for e in cfg["eval_schedule"]}
    saves = set(cfg.get("save_state_at", [])) | {target}
    for x in list(sched) + list(saves):
        assert x % step == 0 and 0 < x <= target, f"schedule point {x} is not a rollout multiple <= {target}"
    assert target in sched, "the endpoint must have a scheduled (final) evaluation"
    since_fork = lambda: learner.counters["env_actions"] - meta["base_actions"]
    start = since_fork()
    evals, states = [], {}
    agreement = {}
    if start == 0:
        ra = recovery_agreement(ctx, learner.actor)
        if ra is not None:
            agreement[0] = ra
            ctx.log({"phase": "recovery_agreement", "post_probe_actions": 0, **ra})
    rec_every = cfg.get("recovery_every")
    assert rec_every is None or rec_every % step == 0, "recovery_every must be a rollout multiple"
    recovery = {}
    signal.signal(signal.SIGTERM, _request_pause)
    (ctx.run_dir / "config.resolved.json").write_text(json.dumps({**cfg, **{k: v for k, v in meta.items()
        if k != "anchors"}, "device": str(ctx.device), "executed_target": target}, indent=1))
    t0 = time.time()
    with Heartbeat(interval=5):
        def on_update(_):
            done = since_fork()
            if done in sched:
                e = sched[done]
                role = "eval_final" if done == target or e.get("endpoint") else "eval_diagnostic"
                lay = ctx.diag_layouts if e.get("layouts") == "diag" else None
                ev = ctx.evaluate(learner.actor, e["attempts"], e["bank_attempts"], role, e.get("tag", f"at_{done}"), lay,
                                  e.get("certify"))
                ctx.log({"phase": "eval", "post_probe_actions": done, **ev})
                ra = recovery_agreement(ctx, learner.actor)
                if ra is not None:
                    agreement[done] = ra
                    ctx.log({"phase": "recovery_agreement", "post_probe_actions": done, **ra})
                evals.append({"actions": done, "tag": ev["tag"], "P1": ev["normal"]["P1"], "q": ev["normal"]["q"],
                              "C4": ev["normal"].get("C4"), "R4": ev["normal"].get("R4"),
                              "P_success_given_arrival": ev["normal"]["P_success_given_arrival"],
                              "c": ev["bank"]["P1"] if ev["bank"] else None, "bins": ev["bank_bins"],
                              "extra_c": {n: v["P1"] for n, v in ev["extra_banks"].items()},
                              "attempts": e["attempts"], "bank_attempts": e["bank_attempts"],
                              "layouts": e.get("layouts", "eval"), "endpoint": done == target or bool(e.get("endpoint"))})
            if done in saves:
                states[done] = save_state(ctx, learner, pi0_state, meta, done)
            elif rec_every and done % rec_every == 0 and done < target:
                recovery.update(at=done, hash=save_state(ctx, learner, pi0_state, meta, done, "recovery.pt"))
            if os.environ.get("BC2RL_TEST_SIGTERM_AT") == str(done):    # test hook: the real signal path, deterministic
                os.kill(os.getpid(), signal.SIGTERM)
            if _SIGTERM and done < target:       # checkpoint-and-pause (battery or owner stop); never complete
                if done in states:
                    point = {"at": done, "file": f"state_{done}.pt", "hash": states[done]}
                else:
                    if recovery.get("at") != done:
                        recovery.update(at=done, hash=save_state(ctx, learner, pi0_state, meta, done, "recovery.pt"))
                    point = {"at": done, "file": "recovery.pt", "hash": recovery["hash"]}
                BAT.write_atomic(ctx.run_dir / "paused.json", {
                    "status": "paused", "signal": int(_SIGTERM[0]), "resume_point": point, "target": target,
                    "evals_done": [e["actions"] for e in evals], "states_saved": sorted(states),
                    "train_actions_this_job": done - start,
                    "eval_actions_this_job": {k: v for k, v in ctx.actions.items() if k.startswith("eval")},
                    "resumed_from": meta.get("resumed_from"), "unix": time.time()})
                ctx.log({"phase": "paused", "post_probe_actions": done})
                print(json.dumps({"event": "paused", "resume_point": point}), flush=True)
                raise SystemExit(BAT.PAUSED_EXIT)
        wall = train_loop(ctx, learner, target - start, "branch", on_update=on_update)
    assert since_fork() == target, (since_fork(), target)
    c = learner.counters
    aux = None
    if learner.aux is not None:
        aux = learner.aux.summary()
        BAT.write_atomic(ctx.run_dir / "aux_schedule.json", {"arm": meta["arm"], "seed": meta["seed"], "complete": True,
                                                             "labelled_per_update": learner.aux.schedule(),
                                                             "history": learner.aux.history})
        if meta["arm"] == "C7":
            BAT.write_atomic(ctx.run_dir / "aux_failures.json", learner.aux.failures)
    summary = {**meta, "final": next(e for e in evals if e["actions"] == target), "evals": evals,
               "recovery_agreement": {str(k): v for k, v in agreement.items()}, "aux": aux,
               "state_hashes": states, "continuation_actions": target, "actions_this_job": ctx.actions,
               "actions": ctx.actions, "counters": c, "train_wall_seconds": wall, "wall_seconds": time.time() - t0}
    BAT.write_atomic(ctx.run_dir / "summary.json", summary)
    if (ctx.run_dir / "recovery.pt").exists():       # the endpoint states supersede it; keep no extra copies
        (ctx.run_dir / "recovery.pt").unlink()
    print(json.dumps({"arm": meta["arm"], "evals": [(e["actions"], e["P1"], e["c"]) for e in evals]}), flush=True)


def resume(a, cfg):
    path = run_path(a.state)
    saved = torch.load(path, map_location="cpu", weights_only=False)
    st, meta = saved["state"], dict(saved["meta"])
    assert PP.state_hash(st) == saved["hash"], "saved state does not match its hash"
    src_cfg = json.loads((path.parent / "config.resolved.json").read_text())
    may_change = {"continuation_actions", "eval_schedule", "save_state_at", "purpose"} | set(meta)
    fixed = [k for k in cfg if k not in may_change and k in src_cfg and src_cfg[k] != cfg[k]]
    assert not fixed, f"resume config changes frozen settings: {fixed}"
    K, seed, arm = meta["K"], meta["seed"], meta["arm"]
    use_reset, use_kl = PP.ARMS[arm]
    assert meta["alpha"] == (cfg["alpha"] if use_reset else 0.0) and meta["kl_coef"] == PP.arm_kl_coef(arm, cfg)
    ctx = Ctx(cfg, K, seed)
    pi0 = M.Actor().to(ctx.device)
    pi0.load_state_dict(st["pi0"])
    for p in pi0.parameters():
        p.requires_grad_(False)
    anchors, anchor_info = ctx.anchors(pi0)
    learner = PP.PPO(M.Actor().to(ctx.device), M.Critic().to(ctx.device),
                     {**cfg, "alpha": meta["alpha"], "kl_coef": meta["kl_coef"]}, ctx.device,
                     ctx.sampler(meta["alpha"], arm), anchors, use_kl=use_kl, seed=seed,
                     component=meta.get("anchor_component", "both"))
    attach_aux(ctx, cfg, learner, arm, seed, meta.get("match_run"))
    if learner.aux is not None:
        assert "aux" in st, "saved state has no auxiliary-source state"
    learner.load(st)
    learner.sampler.clock = lambda: learner.counters["env_actions"] - meta["base_actions"]
    assert PP.state_hash({**learner.state(), "pi0": st["pi0"]}) == saved["hash"], "loaded learner differs from saved state"
    assert learner.counters["env_actions"] - meta["base_actions"] == meta["post_probe_actions"]
    meta.update(resumed_from=str(path), resumed_hash=saved["hash"], anchors=anchor_info)
    meta.pop("post_probe_actions")
    scheduled(ctx, cfg, learner, st["pi0"], meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["probe", "branch", "resume"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--K", type=int)
    ap.add_argument("--bc-run")
    ap.add_argument("--bc-update", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--probe-run")
    ap.add_argument("--arm", choices=list(PP.ARMS))
    ap.add_argument("--alpha", type=float, help="override the config's reset probability")
    ap.add_argument("--kl-coef", type=float, help="override the config's preservation strength")
    ap.add_argument("--match-run", help="arm R7: the same seed's completed C7 branch (relative to .mae/runs or @/job)")
    ap.add_argument("--state", help="resume: saved branch state, relative to .mae/runs or @/job/state_<n>.pt")
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text())
    BAT.require_admission(f"rl {a.mode}")
    if a.alpha is not None:
        cfg["alpha"] = a.alpha
    if a.kl_coef is not None:
        cfg["kl_coef"] = a.kl_coef
    {"probe": probe, "branch": branch, "resume": resume}[a.mode](a, cfg)


if __name__ == "__main__":
    main()
