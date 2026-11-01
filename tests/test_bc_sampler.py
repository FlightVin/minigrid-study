import numpy as np

from bc2rl import bc as B


def _pools():
    K = np.array([1] * 60 + [3] * 40)
    stage = np.array([0] * 20 + [1] * 40 + [0] * 30 + [2] * 10)
    by_K = {k: np.nonzero(K == k)[0] for k in (1, 3)}
    by_KS = {(k, s): np.nonzero((K == k) & ((stage == 0) if s == "prefix" else (stage > 0)))[0]
             for k in (1, 3) for s in ("prefix", "suffix")}
    return K, stage, by_K, by_KS


def test_original_sampler_unchanged():
    _, _, by_K, by_KS = _pools()
    r1, r2 = np.random.default_rng(3), np.random.default_rng(3)
    a = B.sample_batch(r1, by_K, by_KS, 128)
    b = np.concatenate([r2.choice(by_K[1], 128), r2.choice(by_K[3], 128)])
    assert np.array_equal(a, b)


def test_prefix_probability_sampler_is_k_balanced_with_target_stage_fraction():
    K, stage, by_K, by_KS = _pools()
    for rho in (0.2, 0.5, 0.8):
        rng = np.random.default_rng(4)
        fr, kk = [], []
        for _ in range(400):
            idx = B.sample_batch(rng, by_K, by_KS, 128, rho)
            assert len(idx) == 256
            kk.append((K[idx] == 1).mean())
            for k in (1, 3):
                fr.append((stage[idx][K[idx] == k] == 0).mean())
        assert all(x == 0.5 for x in kk)
        assert abs(np.mean(fr) - rho) < 0.01, rho
