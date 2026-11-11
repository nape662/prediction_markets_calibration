"""Calibration statistics shared by the Manifold and Polymarket analyses."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

RESAMPLES, TOLERANCE = 500, 1e-3
logit = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))


def wshift(x, y, w):
    return minimize_scalar(lambda a: -np.sum(w * (y * (a + x) - np.log1p(np.exp(a + x)))), bounds=(-4, 4), method="bounded", options=dict(xatol=TOLERANCE)).x


def summary(g, by="creator", seed=0):
    x, y = logit(g.prob.to_numpy()), g.y.to_numpy()
    w = g.w.to_numpy() if "w" in g else np.ones(len(g))  # optional per-market weights
    c = pd.factorize(g[by])[0]
    rng = np.random.default_rng(seed)
    draws = [wshift(x, y, w * np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c]) for _ in range(RESAMPLES)]
    low, high = np.percentile(draws, [2.5, 97.5])
    price, yes = np.average(g.prob, weights=w), np.average(y, weights=w)
    return dict(n=len(g), price=price, yes=yes, gap=price - yes, shift=wshift(x, y, w), low=low, high=high)


def boot_rate(g, seed=0):
    c, y = pd.factorize(g.creator)[0], g.y.to_numpy()
    w = g.w.to_numpy() if "w" in g else np.ones(len(g))
    rng = np.random.default_rng(seed)
    counts = np.array([np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c] for _ in range(RESAMPLES)])
    return np.percentile(counts @ (w * y) / (counts @ w), [2.5, 97.5])
