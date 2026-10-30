from math import comb

import numpy as np
import torch

from bc2rl import evaluate as E
from bc2rl import model as M
from bc2rl import planner as P
from bc2rl import task as T


def test_pass_estimators_match_definitions():
    assert E.pass_estimators(4, 0, 4) == (0.0, 0.0)
    assert E.pass_estimators(4, 4, 4) == (1.0, 1.0)
    assert E.pass_estimators(16, 8, 4) == (1 - comb(8, 4) / comb(16, 4), comb(8, 4) / comb(16, 4))
    # Unbiasedness of pass@k on the binomial sampling distribution.
    p, n, k = 0.3, 8, 4
    exp_c = sum(comb(n, z) * p ** z * (1 - p) ** (n - z) * E.pass_estimators(n, z, k)[0] for z in range(n + 1))
    exp_r = sum(comb(n, z) * p ** z * (1 - p) ** (n - z) * E.pass_estimators(n, z, k)[1] for z in range(n + 1))
    assert abs(exp_c - (1 - (1 - p) ** k)) < 1e-12 and abs(exp_r - p ** k) < 1e-12


def _starts():
    out = []
    for K, s in ((1, 0), (3, 1)):
        lay, rec = P.plan_and_verify(T.generate_layout(K, s), s, 24, 80)
        out.append(("layout", lay))
    return out


def test_attempts_are_reproducible_and_batch_independent():
    torch.manual_seed(0)
    actor = M.Actor()
    starts = _starts()
    a, n_a = E.run_attempts(actor, starts, 3, 99, torch.device("cpu"), batch=6)
    b, n_b = E.run_attempts(actor, starts, 3, 99, torch.device("cpu"), batch=2)
    key = lambda r: (r["item"], r["attempt"])
    assert sorted(a, key=key) == sorted(b, key=key) and n_a == n_b


def test_inverse_cdf_sampling_matches_probabilities():
    rng = np.random.default_rng(0)
    probs = np.tile([0.1, 0.2, 0.3, 0.4, 0.0, 0.0, 0.0], (200000, 1))
    acts = E._sample(probs, rng.random(200000))
    freq = np.bincount(acts, minlength=7) / len(acts)
    assert np.allclose(freq, probs[0], atol=0.005)
