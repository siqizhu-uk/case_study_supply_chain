"""Step 5 vs step 4 (decision G21): the correlation peak on a continuous lag, with a block-bootstrap interval.
A check only - nothing here changes an edge lag or step 4's lag_weeks.

Step 4 reads the lag off integer quarters (0-4) of YoY growth rates: a 2-quarter peak means 'somewhere near 26 weeks' and
cannot separate 19 from 26. Here the driver is shifted by a continuous tau (quarters) with linear interpolation,

    x_tau(t) = (1 - f) x(t - k) + f x(t - k - 1),   tau = k + f,  0 <= f < 1,

tau is the one that maximises corr(y_t, x_tau(t)) (step 4's criterion), and a moving-block bootstrap over quarters
(blocks of consecutive quarters of the (y_t, x history) pairs; the same draws for every driver, so drivers can be
differenced) gives its interval. Settings: config/model.yaml supply_graph.lag_check.

Two reading rules (P86). (1) Near-optimal set: every tau whose correlation is within `near_optimal_corr_gap` of the maximum.
With one down-up cycle and 13-18 quarters the correlation surface is flat, so this set - not the argmax - is what the data
say. (2) Interpolation smoothing bias: x_tau between two integer lags is a 2-tap moving average of x, so a smoother
regressor against a smooth target (YoY growth) is favoured at fractional taus; the argmax leans away from integers and
must not be quoted as a lag.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def lagged(x: pd.Series, tau: float) -> pd.Series:
    """x shifted by tau quarters, linearly interpolated between the two neighbouring integer lags."""
    k = int(np.floor(tau + 1e-9))
    f = tau - k
    if f < 1e-9:
        return x.shift(k)
    return (1 - f) * x.shift(k) + f * x.shift(k + 1)


def tau_grid(lc: dict) -> np.ndarray:
    return np.round(np.arange(0.0, lc["tau_max_q"] + 1e-9, lc["tau_step_q"]), 4)


def common_axis(y: pd.Series, xs: list[pd.Series], keep: pd.Index, taus: np.ndarray) -> pd.Index:
    """Quarters in `keep` where y and every x_tau (every driver, every tau) exist: one sample for the whole search, so the
    peak cannot come from quarters entering or leaving the sample as tau changes."""
    ok = y.reindex(keep).notna()
    for x in xs:
        for t in taus:
            ok &= lagged(x, t).reindex(keep).notna()
    return keep[ok.to_numpy()]


def aligned(y: pd.Series, x: pd.Series, axis: pd.Index, taus: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """y on the sample axis (n,) and x_tau on the same quarters for every tau (T, n)."""
    xs = np.vstack([lagged(x, t).reindex(axis).to_numpy(dtype=float) for t in taus])
    return y.reindex(axis).to_numpy(dtype=float), xs


def nan_corr(y: np.ndarray, x: np.ndarray, min_n: int) -> np.ndarray:
    """Correlation over the last axis using only pairs where both are present; NaN below min_n pairs or zero variance."""
    y, x = np.broadcast_arrays(y, x)
    m = ~(np.isnan(y) | np.isnan(x))
    n = m.sum(-1)
    with np.errstate(invalid="ignore", divide="ignore"):
        my = np.where(m, y, 0.0).sum(-1) / n
        mx = np.where(m, x, 0.0).sum(-1) / n
        dy = np.where(m, y - my[..., None], 0.0)
        dx = np.where(m, x - mx[..., None], 0.0)
        c = (dy * dx).sum(-1) / np.sqrt((dy ** 2).sum(-1) * (dx ** 2).sum(-1))
    return np.where(n >= min_n, c, np.nan)


def block_indices(n: int, block: int, draws: int, seed: int) -> np.ndarray:
    """Moving-block bootstrap: (draws, n) positions, each row made of blocks of `block` consecutive quarters."""
    rng = np.random.default_rng(seed)
    block = min(block, n)
    starts = rng.integers(0, n - block + 1, size=(draws, -(-n // block)))
    return (starts[..., None] + np.arange(block)).reshape(draws, -1)[:, :n]


def argmax_tau(corr: np.ndarray, taus: np.ndarray) -> np.ndarray:
    """tau with the highest correlation along axis 0 (first on ties); NaN where every tau is NaN."""
    filled = np.where(np.isnan(corr), -np.inf, corr)
    best = taus[np.argmax(filled, axis=0)]
    return np.where(np.isfinite(filled.max(axis=0)), best, np.nan)


def estimate(y: pd.Series, x: pd.Series, axis: pd.Index, lc: dict, idx: np.ndarray | None = None) -> dict:
    """Point tau (quarters), its correlation and pairs, and the bootstrap taus for the given draws (idx)."""
    taus = tau_grid(lc)
    ya, xa = aligned(y, x, axis, taus)
    curve = nan_corr(ya[None, :], xa, lc["min_pairs"])
    tau = float(argmax_tau(curve[:, None], taus)[0])
    i = int(np.argmin(np.abs(taus - tau)))
    pairs = int((~(np.isnan(ya) | np.isnan(xa[i]))).sum())
    boot = np.array([])
    if idx is not None:
        boot = argmax_tau(nan_corr(ya[idx][None, ...], xa[:, idx], lc["min_pairs"]), taus)
    near = near_optimal(pd.Series(curve, index=taus), lc["near_optimal_corr_gap"])
    return {"tau_q": tau, "corr": float(curve[i]), "n": pairs, "boot": boot, "curve": pd.Series(curve, index=taus), **near}


def near_optimal(curve: pd.Series, gap: float) -> dict:
    """Taus (quarters) whose correlation is within `gap` of the maximum: lowest, highest, and whether the set is one
    unbroken run on the grid. NaN when the curve has no finite value."""
    ok = curve.dropna()
    if ok.empty:
        return {"near_lo_q": np.nan, "near_hi_q": np.nan, "near_contiguous": None}
    inside = curve >= ok.max() - gap
    taus = curve.index[inside.to_numpy()]
    pos = np.flatnonzero(inside.to_numpy())
    return {"near_lo_q": float(taus.min()), "near_hi_q": float(taus.max()), "near_contiguous": bool((np.diff(pos) == 1).all())}
