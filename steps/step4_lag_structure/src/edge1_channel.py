"""Step 4, edge 1 (customers' sell-out -> brand sell-in): channel-inventory partial adjustment (decision L6).

Mechanism (stock adjustment, Lovell / Blinder): the channel holds S_t against a target S*_t = k x sell-out; each period it
closes part of the gap, so the deviation d_t = S_t - S*_t (step 3's Logitech channel index, weeks vs target) follows

    d_t = a + c t + rho d_{t-1} + e_t          (trend c absorbs the anchor drift of step 3's D21)

and sell-in = sell-out + change in channel stock, so a sell-out change reaches the brand's sell-in with the adjustment's
mean lag. Weeks from rho:
    continuous (primary):  rho = exp(-13 / T)  ->  T = -13 / ln(rho)   (weekly replenishment sampled at quarter ends)
    Koyck (shown):         rho / (1 - rho) quarters                     (books a same-quarter response as zero lag)
rho <= 0: the deviation is gone within the quarter (lag 0 at this resolution); rho >= 1: no reversion (lag unbounded).

OLS rho on ~13 quarters is biased towards zero (Hurwicz bias, larger with a trend), so the estimate used is Andrews'
(1993) exact median-unbiased rho with its 90% interval, by simulation of the same regression under Gaussian AR(1)
errors (the OLS rho is invariant to the intercept, trend and scale, so rho is the only parameter). A moving-block
bootstrap of the OLS rho is shown as asked; it does not remove the bias.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from continuous_lag import block_indices


def design(d: np.ndarray, trend: bool) -> tuple[np.ndarray, np.ndarray]:
    """(X, y) of the AR(1) regression on the last axis: y = d_t, X = [1, d_{t-1}, (t)]."""
    y, x = d[..., 1:], d[..., :-1]
    cols = [np.ones_like(x), x] + ([np.broadcast_to(np.arange(x.shape[-1], dtype=float), x.shape)] if trend else [])
    return np.stack(cols, axis=-1), y


def ols_rho(d: np.ndarray, trend: bool) -> np.ndarray:
    """OLS rho for one series (n,) or a batch (reps, n)."""
    X, y = design(np.asarray(d, dtype=float), trend)
    xtx = np.einsum("...ij,...ik->...jk", X, X)
    xty = np.einsum("...ij,...i->...j", X, y)
    return np.linalg.solve(xtx, xty[..., None])[..., 1, 0]


def ols_rho_pairs(x: np.ndarray, y: np.ndarray, t: np.ndarray, trend: bool) -> np.ndarray:
    """OLS rho from resampled (d_{t-1}, d_t, t) triples, batch (draws, n); pseudo-inverse so a degenerate draw cannot fail."""
    X = np.stack([np.ones_like(x), x] + ([t] if trend else []), axis=-1)
    return (np.linalg.pinv(X) @ y[..., None])[..., 1, 0]


def simulated_quantiles(n: int, trend: bool, mu: dict) -> tuple[np.ndarray, np.ndarray]:
    """(rho grid, quantiles 5 / 50 / 95 of the OLS rho per grid value) for AR(1) series of length n (common random numbers)."""
    grid = np.round(np.arange(mu["grid"]["lo"], mu["grid"]["hi"] + 1e-9, mu["grid"]["step"]), 4)
    e = np.random.default_rng(mu["seed"]).standard_normal((mu["reps"], n + mu["burn_in"]))
    q = []
    for r in grid:
        d = np.zeros_like(e)
        for i in range(1, e.shape[1]):
            d[:, i] = r * d[:, i - 1] + e[:, i]
        q.append(np.quantile(ols_rho(d[:, mu["burn_in"]:], trend), [0.05, 0.5, 0.95]))
    return grid, np.maximum.accumulate(np.array(q), axis=0)          # quantiles rise with rho; enforce it against noise


def invert(grid: np.ndarray, curve: np.ndarray, value: float) -> float:
    """The rho whose simulated quantile equals `value`; clipped to the grid ends (hi end = unit root not rejected)."""
    if value <= curve[0]:
        return float(grid[0])
    if value >= curve[-1]:
        return float(grid[-1])
    return float(np.interp(value, curve, grid))


def median_unbiased(rho_hat: float, n: int, trend: bool, mu: dict) -> dict:
    """Andrews (1993): point = rho with median OLS rho equal to the estimate; 90% interval by inverting the 95% / 5% quantiles."""
    grid, q = simulated_quantiles(n, trend, mu)
    return {"rho": invert(grid, q[:, 1], rho_hat), "rho_lo": invert(grid, q[:, 2], rho_hat),
            "rho_hi": invert(grid, q[:, 0], rho_hat), "rho_max": float(grid[-1])}


def weeks(rho, wpq: float, how: str = "continuous"):
    """Mean lag in weeks from quarterly rho: 0 at rho <= 0, inf at rho >= 1."""
    r = np.asarray(rho, dtype=float)
    inside = np.clip(r, 1e-12, 1 - 1e-12)
    lag = -wpq / np.log(inside) if how == "continuous" else wpq * inside / (1 - inside)
    return np.where(r <= 0, 0.0, np.where(r >= 1, np.inf, lag))


def bootstrap_rho(d: np.ndarray, trend: bool, lc: dict) -> np.ndarray:
    """Moving-block bootstrap of the OLS rho over the (d_{t-1}, d_t, t) triples (blocks and draws of supply_graph.lag_check)."""
    x, y, t = d[:-1], d[1:], np.arange(len(d) - 1, dtype=float)
    idx = block_indices(len(y), lc["block_len"], lc["boot_draws"], lc["seed"])
    return ols_rho_pairs(x[idx], y[idx], t[idx], trend)


def _row(spec: str, rho: float, lo: float, hi: float, n: int, wpq: float, method: str) -> dict:
    lag = weeks([rho, lo, hi], wpq)
    return {"spec": spec, "n": n, "rho": rho, "rho_lo": lo, "rho_hi": hi, "lag_weeks": float(lag[0]),
            "lag_lo_weeks": float(lag[1]), "lag_hi_weeks": float(lag[2]), "koyck_weeks": float(weeks(rho, wpq, "koyck")),
            "interval": method}


def estimate(index: pd.Series, e1: dict, lc: dict) -> pd.DataFrame:
    """Edge 1 rows (Logitech): OLS with trend + block bootstrap; median-unbiased with trend (primary); OLS without trend.
    Empty frame when the index is shorter than e1.min_obs (prior only)."""
    d = index.dropna().to_numpy(dtype=float)
    if len(d) < e1["min_obs"]:
        return pd.DataFrame()
    wpq, trend, n = e1["weeks_per_quarter"], e1["trend"], len(d) - 1
    rho = float(ols_rho(d, trend))
    boot = bootstrap_rho(d, trend, lc)
    b_lo, b_hi = (float(v) for v in np.nanquantile(boot, lc["ci"]))
    mu = median_unbiased(rho, len(d), trend, e1["median_unbiased"])
    hi = np.inf if mu["rho_hi"] >= mu["rho_max"] else mu["rho_hi"]           # grid end = unit root not rejected
    flat = float(ols_rho(d, False))
    return pd.DataFrame([
        {**_row("AR(1) + trend, median-unbiased (primary)", mu["rho"], mu["rho_lo"], min(hi, 1.0), n, wpq,
                "Andrews (1993) exact 90% (Gaussian AR(1))"), "primary": True},
        {**_row("AR(1) + trend, OLS", rho, b_lo, b_hi, n, wpq, "moving-block bootstrap 90% (bias not removed)"), "primary": False},
        {**_row("AR(1), no trend, OLS (drift left in)", flat, np.nan, np.nan, n, wpq, "none: the drift reads as persistence"),
         "primary": False}])
