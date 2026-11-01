"""Statistics shared by tools/power_r1.py and tools/analyze_r1.py (PROTOCOL_FREEZE Amendment 3). No scipy.

t_cdf_abs(t, df): P(|T| <= t) for Student t (exact series), so two-sided p = 1 - t_cdf_abs(|t|, df).
"""
from itertools import product
from math import atan, cos, pi, sin, sqrt

import numpy as np

N_SEEDS = 8
DF = N_SEEDS - 1


def t_cdf_abs(t, df=DF):
    """P(|T| <= t), Student t, exact series with theta = atan(t / sqrt(df)).
    Odd df: (2/pi)[theta + sin(theta)(cos + (2/3)cos^3 + (2*4)/(3*5)cos^5 + ...)] (to cos^(df-2)).
    Even df: sin(theta)[1 + (1/2)cos^2 + (1*3)/(2*4)cos^4 + ...] (to cos^(df-2))."""
    assert df >= 1 and t >= 0
    th = atan(t / sqrt(df))
    c = cos(th)
    if df % 2:
        s, term = 0.0, c
        for k in range(1, (df - 1) // 2 + 1):
            s += term
            term *= c * c * (2 * k) / (2 * k + 1)
        return (2 / pi) * (th + sin(th) * s)
    s, term = 0.0, 1.0
    for k in range(1, df // 2 + 1):
        s += term
        term *= c * c * (2 * k - 1) / (2 * k)
    return sin(th) * s


def t_quantile_two_sided(level, df=DF):
    """t such that P(|T| <= t) = level (bisection)."""
    lo, hi = 0.0, 50.0
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if t_cdf_abs(mid, df) < level else (lo, mid)
    return (lo + hi) / 2


T975 = t_quantile_two_sided(0.95)        # 2.3646 for df 7


def t_test(x):
    """Two-sided one-sample t-test of mean 0 and the 95% t-interval (df = n - 1)."""
    x = np.asarray(x, float)
    n = len(x)
    df = n - 1
    q = T975 if df == DF else t_quantile_two_sided(0.95, df)
    m, sd = float(x.mean()), float(x.std(ddof=1))
    se = sd / sqrt(n)
    t = m / se if se > 0 else (np.inf if m else 0.0) * (1 if m >= 0 else -1)
    p = 1 - t_cdf_abs(abs(t), df) if se > 0 else float(m == 0)
    return {"n": n, "estimate": m, "sd": sd, "se": se, "t": float(t), "df": df, "p": float(p),
            "t95_lo": m - q * se, "t95_hi": m + q * se}


def holm(ps):
    order, adj, run = sorted(range(len(ps)), key=lambda i: ps[i]), [0.0] * len(ps), 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i]))
        adj[i] = run
    return adj


def signflip(x):
    """Exact two-sided sign-flip p-value for mean 0 (2^n patterns)."""
    x = np.asarray(x, float)
    obs = abs(x.mean())
    sums = np.array([abs(np.mean(x * np.array(s))) for s in product((1, -1), repeat=len(x))])
    return float(np.mean(sums >= obs - 1e-15))
