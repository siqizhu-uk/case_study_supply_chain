"""Step 6 — back-test with structural breaks: ridge distributed-lag regression (leave-one-out) and the regime-conditioned guidance-bias model."""
from __future__ import annotations

import numpy as np
import pandas as pd


def distributed_lag_regression(p: pd.DataFrame, cfg: dict, driver: pd.Series | None = None) -> dict:
    """`driver` overrides the config driver column — step 2b passes the attribution-path-weighted Logitech YoY, so the
    back-test uses the share that was true in each quarter rather than today's."""
    rc = cfg["regression"]
    y_col, x_col, alpha = rc["target"], rc["driver"], rc["ridge_alpha"]
    lags = list(rc.get("lags_used", range(0, rc["max_lag_quarters"] + 1)))
    xs = driver if driver is not None else p[x_col]
    X = pd.DataFrame(index=p.index)
    for k in lags:
        X[f"{x_col}_L{k}"] = xs.shift(k)
    for c in rc["controls"]:
        X[c] = p[c]
    df = pd.concat([p[y_col].rename("y"), X], axis=1).dropna()
    if len(df) < rc["min_obs"]:
        return {"ok": False, "n": len(df), "reason": f"only {len(df)} complete observations"}
    y = df["y"].values
    Xm = df.drop(columns="y")
    mu, sd = Xm.mean(), Xm.std().replace(0, 1)
    Z = ((Xm - mu) / sd).values
    Z1 = np.column_stack([np.ones(len(Z)), Z])
    lam = np.eye(Z1.shape[1]) * alpha
    lam[0, 0] = 0.0
    beta = np.linalg.solve(Z1.T @ Z1 + lam, Z1.T @ y)
    yhat = Z1 @ beta
    resid = y - yhat
    r2 = 1 - resid.var() / y.var()
    coefs = pd.Series(beta[1:], index=Xm.columns, name="beta_std")
    # Unstandardised effect of 1pt Logitech YoY at each lag:
    unstd = coefs / sd
    lag_profile = {k: float(unstd[f"{x_col}_L{k}"]) for k in lags}
    best_lag = max(lag_profile, key=lambda k: lag_profile[k])
    # leave-one-out RMSE for honesty
    loo = []
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        b = np.linalg.solve(Z1[m].T @ Z1[m] + lam, Z1[m].T @ y[m])
        loo.append(y[i] - Z1[i] @ b)
    return {"ok": True, "driver": (driver.name if driver is not None else x_col), "driver_series": xs, "n": int(len(df)), "r2_in_sample": float(r2), "rmse_in_sample": float(np.sqrt((resid**2).mean())),
            "rmse_loo": float(np.sqrt(np.mean(np.square(loo)))), "coef_std": coefs, "lag_profile_pts": lag_profile,
            "best_lag": int(best_lag), "fitted": pd.Series(yhat, index=df.index), "actual": pd.Series(y, index=df.index),
            "sum_lag_effect": float(sum(lag_profile.values()))}


# ----------------------------------------------------------------------------- B
def guidance_bias(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    gb = cfg["guidance_bias"]
    rows = []

    def window(col, lo, hi, label, company):
        w = p.loc[pd.Period(lo, "Q"):pd.Period(hi, "Q"), col].dropna()
        rows.append({"company": company, "window": label, "n": len(w), "mean_beat_pct": w.mean(),
                     "median_beat_pct": w.median(), "std_pct": w.std(ddof=1) if len(w) > 1 else np.nan,
                     "min_pct": w.min(), "max_pct": w.max()})

    window("nordic_beat_vs_guide_pct", *gb["nordic_window_normal"], "normal channel (2024Q2-2026Q2)", "Nordic")
    window("nordic_beat_vs_guide_pct", *gb["nordic_window_destock"], "destock (2022Q4-2024Q1)", "Nordic")
    window("nordic_beat_vs_guide_pct", str(p.index.min()), "2026Q2", "all quarters", "Nordic")     # panel-wide (2020Q1+ once F32 rows exist)
    window("logi_beat_vs_guide_pct", *gb["logitech_window"], "quarterly guides (2025Q2-2026Q2)", "Logitech")
    return pd.DataFrame(rows).round(2)


# ----------------------------------------------------------------------------- C
