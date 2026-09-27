"""Step 4, edge 2 (brand sell-in -> Nordic revenue): attribution-constrained lag with a common-cycle control (decision L7).

    y_t = alpha + s m x(t - tau) + beta w(t - kappa) [+ delta destock_t] + e_t

y = Nordic consumer revenue YoY; x = the brand's sell-in YoY; s = the brand's share of Nordic consumer revenue (step 2,
fixed); m = the slice amplitude multiplier (step 3, fixed); w = the common semiconductor cycle (WSTS) at its own lag
kappa, set at w's correlation peak on the same sample (step 5's continuous-lag criterion). The size of the brand's slice
is therefore NOT fitted: only tau, alpha, beta (and kappa) are free, and the data can only say WHEN the fixed-size slice
fits best. x_tau is interpolated between integer quarters (continuous_lag.lagged); every tau is searched on one fixed
sample (continuous_lag.common_axis).

Reading: the profile-likelihood set {tau: n ln(SSR(tau) / SSR_min) <= chi2_1(90%)} and a moving-block bootstrap of the
argmin (kappa re-estimated in every draw). The unconstrained fit (slope b on x free) is shown next to it: b far above
s m says the fitted slope carries the common cycle, not the slice (P77).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from continuous_lag import aligned, block_indices, common_axis, estimate as corr_peak, tau_grid


def residual_maker(Z: np.ndarray) -> np.ndarray:
    """M = I - Z Z^+ for a design (n, k) or a batch (draws, n, k): SSR of r on Z = r' M r."""
    n = Z.shape[-2]
    return np.eye(n) - Z @ np.linalg.pinv(Z)


def ssr(R: np.ndarray, M: np.ndarray) -> np.ndarray:
    """Row-wise residual sum of squares of R (..., T, n) after projecting out the design behind M (..., n, n)."""
    return np.einsum("...tn,...nm,...tm->...t", R, M, R)


def controls(w_row: np.ndarray, dummy: np.ndarray | None) -> np.ndarray:
    """Design [1, w (, destock)] on the last axis."""
    cols = [np.ones_like(w_row), w_row] + ([np.broadcast_to(dummy, w_row.shape)] if dummy is not None else [])
    return np.stack(cols, axis=-1)


def profile_set(curve: np.ndarray, taus: np.ndarray, n: int, chi2: float) -> dict:
    """Taus inside the 90% profile-likelihood set and the share of the grid they cover."""
    inside = n * np.log(curve / np.nanmin(curve)) <= chi2
    return {"set_lo_q": float(taus[inside].min()), "set_hi_q": float(taus[inside].max()), "set_share": float(inside.mean())}


def _boot(ya, X, W, kap, taus, sm, dummy, lc) -> np.ndarray:
    """Bootstrap argmin tau: resampled quarters, kappa per draw, fixed-size slice sm x_tau."""
    idx = block_indices(len(ya), lc["block_len"], lc["boot_draws"], lc["seed"])
    k_i = np.abs(taus[None, :] - kap[:, None]).argmin(1)
    w_b = W[k_i[:, None], idx]                                               # (draws, n): control at each draw's kappa
    d_b = dummy[idx] if dummy is not None else None
    M = residual_maker(controls(w_b, d_b))                                   # (draws, n, n)
    R = ya[idx][:, None, :] - sm * X[:, idx].transpose(1, 0, 2)             # (draws, T, n)
    return taus[np.argmin(ssr(R, M), axis=1)]


def constrained(y: pd.Series, x: pd.Series, w: pd.Series, keep: pd.Index, sm: float, lc: dict, chi2: float,
                dummy: pd.Series | None = None) -> dict:
    """Fixed-size slice sm x(t - tau) + control w(t - kappa): tau by SSR on one sample, profile set, bootstrap interval."""
    taus = tau_grid(lc)
    axis = common_axis(y, [x, w], keep, taus)
    if len(axis) < lc["min_pairs"]:
        return {"n": len(axis)}
    idx = block_indices(len(axis), lc["block_len"], lc["boot_draws"], lc["seed"])
    kap = corr_peak(y, w, axis, lc, idx)
    ya, X = aligned(y, x, axis, taus)
    _, W = aligned(y, w, axis, taus)
    dm = dummy.reindex(axis).to_numpy(dtype=float) if dummy is not None else None
    w0 = W[int(np.abs(taus - kap["tau_q"]).argmin())]
    curve = ssr(ya[None, :] - sm * X, residual_maker(controls(w0, dm)))
    boot = _boot(ya, X, W, kap["boot"], taus, sm, dm, lc)
    lo, hi = np.quantile(boot, lc["ci"])
    return {"n": len(axis), "first_quarter": str(axis[0]), "kappa_q": kap["tau_q"], "tau_q": float(taus[np.argmin(curve)]),
            "ci_lo_q": float(lo), "ci_hi_q": float(hi), "ci_share": float((hi - lo) / taus[-1]),
            **profile_set(curve, taus, len(axis), chi2), "curve": pd.Series(curve, index=taus)}


def unconstrained(y: pd.Series, x: pd.Series, w: pd.Series, keep: pd.Index, lc: dict, chi2: float) -> dict:
    """Slope b on x_tau free (with the same control at its own peak): tau, b and the profile set."""
    taus = tau_grid(lc)
    axis = common_axis(y, [x, w], keep, taus)
    kap = corr_peak(y, w, axis, lc)["tau_q"]
    ya, X = aligned(y, x, axis, taus)
    _, W = aligned(y, w, axis, taus)
    w0 = W[int(np.abs(taus - kap).argmin())]
    Z = np.stack([np.stack([np.ones_like(w0), w0, xt], axis=-1) for xt in X])          # (T, n, 3)
    coef = np.linalg.pinv(Z) @ ya[:, None]                                              # (T, 3, 1)
    curve = ((ya[None, :] - (Z @ coef)[..., 0]) ** 2).sum(1)
    i = int(np.argmin(curve))
    return {"n": len(axis), "first_quarter": str(axis[0]), "kappa_q": kap, "tau_q": float(taus[i]), "slope": float(coef[i, 2, 0]),
            **profile_set(curve, taus, len(axis), chi2)}
