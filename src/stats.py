"""Calibration statistics shared by the Manifold and Polymarket analyses."""
import numpy as np
import pandas as pd

RESAMPLES = 500
logit = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))


def wshifts(x, y, w, c, counts):
    """Best logit shift a in [-4, 4] per resample, by Newton steps. counts[b, j]: how often resample b draws cluster j; c: each row's cluster."""
    ex, out = np.exp(-x), []
    for K in np.array_split(counts, min(len(counts), max(1, len(counts) * len(x) // 2**20))):  # cache-sized chunks
        W = K[:, c] * w
        target, a = W @ y, np.zeros(len(W))
        for _ in range(100):
            s = 1 / (1 + np.exp(-a)[:, None] * ex)  # = sigmoid(a + x)
            Ws = W * s
            new = np.clip(a + (target - Ws.sum(1)) / np.einsum("bn,bn->b", Ws, 1 - s), -4, 4)
            done, a = np.abs(new - a).max() < 1e-9, new
            if done:
                break
        assert done, "Newton did not converge"
        out.append(a)
    return np.concatenate(out)


def wshift(x, y, w):
    return wshifts(x, y, w, np.zeros(len(x), int), np.ones((1, 1)))[0]


def resample_counts(k, seed):
    """counts[b, j]: how many times resample b draws cluster j, for RESAMPLES resamples of k clusters."""
    draws = np.random.default_rng(seed).integers(0, k, (RESAMPLES, k)) + k * np.arange(RESAMPLES)[:, None]
    return np.bincount(draws.ravel(), minlength=RESAMPLES * k).reshape(RESAMPLES, k)


def summary(g, by="creator", seed=0):
    x, y = logit(g.prob.to_numpy()), g.y.to_numpy()
    w = g.w.to_numpy() if "w" in g else np.ones(len(g))  # optional per-market weights
    c = pd.factorize(g[by])[0]
    low, high = np.percentile(wshifts(x, y, w, c, resample_counts(c.max() + 1, seed)), [2.5, 97.5])
    price, yes = np.average(g.prob, weights=w), np.average(y, weights=w)
    return dict(n=len(g), price=price, yes=yes, gap=price - yes, shift=wshift(x, y, w), low=low, high=high)


def boot_rate(g, seed=0):
    c, y = pd.factorize(g.creator)[0], g.y.to_numpy()
    w = g.w.to_numpy() if "w" in g else np.ones(len(g))
    counts = resample_counts(c.max() + 1, seed)
    return np.percentile(counts @ np.bincount(c, w * y) / (counts @ np.bincount(c, w)), [2.5, 97.5])
