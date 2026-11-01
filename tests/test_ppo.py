import json
import numpy as np
import torch

from bc2rl import data as D
from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import ppo as PP
from bc2rl import task as T

CFG = {"actor_lr": 3e-4, "critic_lr": 3e-4, "n_envs": 2, "n_steps": 16, "gamma": 1.0, "gae_lambda": 0.95,
       "epochs": 2, "minibatch": 16, "clip": 0.2, "ent_coef": 0.01, "max_grad_norm": 0.5,
       "anchor_batch": 8, "kl_coef": 0.1}


def test_gae_cuts_at_terminals_and_bootstraps_at_batch_end():
    r = torch.tensor([[0.0], [1.0], [0.0], [0.0]])
    v = torch.tensor([[0.5], [0.6], [0.2], [0.3]])
    d = torch.tensor([[False], [True], [False], [False]])
    last = torch.tensor([0.9])
    g, lam = 1.0, 0.95
    adv = PP.gae(r, v, d, last, g, lam)
    # step 3: bootstrap from last value; step 2 flows from step 3
    d3 = 0 + 0.9 - 0.3
    d2 = 0 + 0.3 - 0.2
    # step 1 is terminal (success): no bootstrap, no flow from step 2 (next episode)
    d1 = 1.0 - 0.6
    d0 = 0 + 0.6 - 0.5
    expect = [d0 + lam * d1, d1, d2 + lam * d3, d3]
    assert torch.allclose(adv[:, 0], torch.tensor(expect))


def test_categorical_kl_matches_torch():
    a, b = torch.randn(5, 7), torch.randn(5, 7)
    la, lb = torch.log_softmax(a, -1), torch.log_softmax(b, -1)
    ref = torch.distributions.kl_divergence(torch.distributions.Categorical(logits=a),
                                            torch.distributions.Categorical(logits=b))
    assert torch.allclose(PP.categorical_kl(la, lb), ref, atol=1e-6)


def _setup(alpha, seed=0):
    layouts, bins = [], {"entry": [], "retrieval": [], "carrying": []}
    rows_all = []
    env = T.StageTask()
    for s in range(6):
        lay, rec = P.plan_and_verify(T.generate_layout(1, 900 + s), s, 24, 80)
        layouts.append(lay)
        rows, pickup = D.record_trajectory(env, lay, rec["actions"])
        for t in range(rec["tau"], rec["length"]):
            snap = D.snapshot_from_record(lay, rows["grid"][t], rows["aux"][t], rows["step_count"][t], rec["tau"])
            b = "entry" if t == rec["tau"] else "retrieval" if t < pickup else "carrying"
            bins[b].append(lambda snap=snap: snap)
            rows_all.append(rows["grid"][t])
    torch.manual_seed(seed)
    actor, critic = M.Actor(), M.Critic()
    sampler = PP.StartSampler(layouts, bins, alpha, [("entry", .5), ("retrieval", .25), ("carrying", .25)], seed)
    g = torch.as_tensor(np.stack(rows_all[:32]))
    anchors = {"grid": g, "aux": torch.zeros(32, 3, dtype=torch.int8), "time": torch.full((32, 1), 0.5),
               "ref_logp": torch.log_softmax(torch.randn(32, 7), -1), "weights": np.full(32, 1 / 32)}
    return actor, critic, sampler, anchors


def test_fork_reproduces_training_exactly_on_cpu():
    actor, critic, sampler, anchors = _setup(0.5)
    learner = PP.PPO(actor, critic, CFG, torch.device("cpu"), sampler, anchors, use_kl=True, seed=3)
    learner.update(learner.collect())
    st = learner.state()
    h = PP.state_hash(st)
    outs = []
    for _ in range(2):
        a2, c2, s2, _ = _setup(0.5, seed=99)     # different init, overwritten by the fork
        # Anchors are not fork state; production rebuilds them deterministically from pi0.
        l2 = PP.PPO(a2, c2, CFG, torch.device("cpu"), s2, anchors, use_kl=True, seed=3)
        l2.load(st)
        assert PP.state_hash(l2.state()) == h
        stats = l2.update(l2.collect())
        outs.append((stats, PP.state_hash(l2.state())))
    stats0 = learner.update(learner.collect())
    assert outs[0] == outs[1] == (stats0, PP.state_hash(learner.state()))


def test_assisted_starts_keep_original_time_and_count_actions():
    actor, critic, sampler, anchors = _setup(1.0)
    learner = PP.PPO(actor, critic, CFG, torch.device("cpu"), sampler, anchors, seed=1)
    for i, e in enumerate(learner.envs):
        assert learner.assisted[i] and e.accessed and e.step_count > 0
        assert e.remaining() == e.layout.limit - e.step_count < e.layout.limit
    data = learner.collect()
    assert learner.counters["env_actions"] == CFG["n_envs"] * CFG["n_steps"]
    assert data["assisted"].all()


def test_normal_layout_stream_is_shared_across_alpha():
    _, _, s0, _ = _setup(0.0, seed=5)
    _, _, s1, _ = _setup(0.5, seed=5)
    a = [s0.draw()[1] for _ in range(20)]
    b = [x[1] for x in (s1.draw() for _ in range(60)) if x[0] == "layout"][:20]
    assert a == b


def _original_penalty(ref, actor, ag, aa, at, coef):
    """The pre-2026-11-01 anchor term, verbatim: coef * categorical_kl(ref, log_softmax(actor)).mean()."""
    return coef * PP.categorical_kl(ref, torch.log_softmax(actor(ag, aa, at), -1)).mean()


def test_anchor_components_match_original_loss_and_gradients():
    """Component experiment (owner instruction 2026-11-01, section 7): "both" equals the original loss and its
    gradients exactly; prefix + suffix = both (same denominator, no renormalization)."""
    actor, _, _, A = _setup(0.0)
    pre = torch.arange(32) < 8
    idx = torch.as_tensor(np.random.default_rng(0).integers(0, 32, 16))
    ag, aa, at, ref, p = A["grid"][idx], A["aux"][idx], A["time"][idx], A["ref_logp"][idx], pre[idx]

    def grads(fn):
        actor.zero_grad()
        v = fn()
        v.backward()
        return v.detach().clone(), [q.grad.clone() for q in actor.parameters()]

    kl_rows = lambda: PP.categorical_kl(ref, torch.log_softmax(actor(ag, aa, at), -1))
    v0, g0 = grads(lambda: _original_penalty(ref, actor, ag, aa, at, 0.01))
    vb, gb = grads(lambda: PP.anchor_penalty(kl_rows(), p, "both", 0.01))
    assert torch.equal(v0, vb) and all(torch.equal(x, y) for x, y in zip(g0, gb))
    vp, gp = grads(lambda: PP.anchor_penalty(kl_rows(), p, "prefix", 0.01))
    vs, gs = grads(lambda: PP.anchor_penalty(kl_rows(), p, "suffix", 0.01))
    assert torch.allclose(vp + vs, vb, atol=1e-9) and all(torch.allclose(x + y, z, atol=1e-8) for x, y, z in zip(gp, gs, gb))
    with torch.no_grad():
        r = kl_rows()
    assert torch.allclose(vp, 0.01 * r[p].sum() / 16) and torch.allclose(vs, 0.01 * r[~p].sum() / 16)


def test_components_share_rng_streams_and_both_equals_unlabelled():
    """After one rollout + update: every component arm leaves the action, permutation, anchor and start-sampler
    streams in the same state; "both" with stage labels equals the unlabelled original path bitwise."""
    states, params = {}, {}
    for comp in ("none", "both", "prefix", "suffix", "unlabelled"):
        actor, critic, sampler, A = _setup(0.0)
        if comp != "unlabelled":
            A = {**A, "is_prefix": torch.arange(32) < 8}
        L = PP.PPO(actor, critic, CFG, torch.device("cpu"), sampler, A, use_kl=comp != "none", seed=5,
                   component="both" if comp in ("none", "unlabelled") else comp)
        L.update(L.collect())
        states[comp] = (L.torch_gen.get_state().clone(), json.dumps(L.np_rng.bit_generator.state, default=str),
                        json.dumps(L.sampler.get_state(), default=str))
        params[comp] = [q.detach().clone() for q in actor.parameters()]
    ref = states["none"]
    for comp, s in states.items():
        assert torch.equal(s[0], ref[0]) and s[1:] == ref[1:], comp
    assert all(torch.equal(x, y) for x, y in zip(params["both"], params["unlabelled"]))
    assert not all(torch.equal(x, y) for x, y in zip(params["prefix"], params["suffix"]))
