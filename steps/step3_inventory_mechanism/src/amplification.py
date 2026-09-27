"""Step 3d — WHY the chain amplifies, and what the data can and cannot identify.

Structural model: the anchoring-and-adjustment ordering rule (Sterman 1989; Forrester 1961; the stock-adjustment
model of Metzler 1941 / Blinder & Maccini 1991). A tier orders

    O_t = E[D_t]  +  (I*_t - I*_{t-1})  +  alpha * (I*_t - I_t)
          demand     accelerator:          stock-gap correction:
                     target-cover change   close part of the gap between target and actual stock

with target stock I*_t = c * D^TTM_t (c = cover in YEARS of trailing demand; a target on TTM demand is what makes the
seasonal build cancel year on year). In YoY growth rates (g = demand YoY, g^O = order YoY), to first order:

    g^O_t  ~=  g_t  +  c * (g_t - g_{t-4})  -  alpha' * gap_t                                              (1)

  term 1  pass-through                          coefficient 1 if nothing else happens
  term 2  accelerator  c * (g_t - g_{t-4})       predicts orders LEAD demand; c x 52 = cover in weeks  -> prior from the
                                                 balance sheets (prior_cover_weeks), stated before any fit
  term 3  stock gap    -alpha' * gap_t            predicts orders LAG demand (stock piles up involuntarily when demand
                                                 falls, then is cut) -> observable proxy: distributor days vs normal

Regression per tier (OLS, Newey-West HAC s.e., moving-block bootstrap, leave-one-out RMSE):
    y_t = a + b * g_{t-L} [+ c * (g_{t-L} - g_{t-L-4})] [+ gamma * gap_{t-K}]
The reduced form keeps b only if the extra terms do not lower the leave-one-out error (decision D11).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from bullwhip import block_bootstrap_ci


def _ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(X, y, rcond=None)[0]


def newey_west_se(X: np.ndarray, resid: np.ndarray, lags: int) -> np.ndarray:
    n = len(resid)
    xtx_inv = np.linalg.inv(X.T @ X)
    u = X * resid[:, None]
    s = u.T @ u
    for L in range(1, lags + 1):
        g = u[L:].T @ u[:-L]
        s += (1 - L / (lags + 1)) * (g + g.T)
    return np.sqrt(np.diag(xtx_inv @ s @ xtx_inv * n / (n - X.shape[1])))


def fit_link(y: pd.Series, g: pd.Series, lag: int, sample: tuple[str, str], accel: bool = False,
             gap: pd.Series | None = None, gap_lag: int = 0, hac_lags: int = 2, boot: dict | None = None) -> dict:
    cols = {"y": y, "g": g.shift(lag)}
    if accel:
        cols["d4g"] = (g - g.shift(4)).shift(lag)
    if gap is not None:
        cols["gap"] = gap.shift(gap_lag)
    lo, hi = (pd.Period(q, "Q") for q in sample)
    d = pd.DataFrame(cols).loc[lo:hi].dropna()
    names = [c for c in d.columns if c != "y"]
    X = np.column_stack([np.ones(len(d))] + [d[c].values for c in names])
    yv = d["y"].values
    b = _ols(X, yv)
    resid = yv - X @ b
    se = newey_west_se(X, resid, hac_lags)
    loo = [yv[i] - X[i] @ _ols(np.delete(X, i, 0), np.delete(yv, i)) for i in range(len(yv))]
    out = {"n": int(len(d)), "lag": lag, "sample": list(sample), "a": float(b[0]),
           "coef": {k: float(v) for k, v in zip(names, b[1:])}, "se": {k: float(v) for k, v in zip(names, se[1:])},
           "r2": float(1 - resid.var() / yv.var()), "rmse_loo": float(np.sqrt(np.mean(np.square(loo)))),
           "fitted": pd.Series(X @ b, index=d.index), "actual": pd.Series(yv, index=d.index)}
    if boot:
        arrays = [X[:, j] for j in range(X.shape[1])] + [yv]
        for j, k in enumerate(names, start=1):
            out.setdefault("ci90", {})[k] = block_bootstrap_ci(lambda *c, j=j: _ols(np.column_stack(c[:-1]), c[-1])[j],
                                                              arrays, boot["reps"], boot["block"], boot["seed"])
    if accel:
        out["implied_cover_weeks"] = out["coef"]["d4g"] * 52
    return out


def prior_cover_weeks(f: pd.DataFrame, cfg: dict, sample: tuple[str, str]) -> pd.DataFrame:
    """Cover at each stocking point, stated BEFORE the regression; measured from filings where possible."""
    im = cfg["inventory_mechanism"]
    lo, hi = (pd.Period(q, "Q") for q in sample)
    w = f.loc[lo:hi]
    fg, own = w["logi_fg_weeks"].dropna(), (w["logi_dio"] / 7).dropna()
    md = w["mchp_disti_days"].dropna() / 7
    sh = im["nordic_distribution_share"]
    ch, odm = im["cover_prior_weeks"]["retail_and_distribution_channel"], im["cover_prior_weeks"]["odm_ems_component_stock"]
    rows = [
        {"point": "retail + distribution channel (Logitech products)", "tier_test": "logitech_channel", "source": "assumption: 'weeks on hand' never disclosed numerically", "low": ch["low"], "mid": ch["mid"], "high": ch["high"]},
        {"point": "Logitech own stock (RM + FG)", "tier_test": "logitech_own", "source": "measured: DIO / 7 (range over sample)", "low": own.min(), "mid": own.median(), "high": own.max()},
        {"point": "  of which finished goods", "tier_test": "", "source": "measured: XBRL FG / COGS x 13", "low": fg.min(), "mid": fg.median(), "high": fg.max()},
        {"point": "ODM / EMS component stock", "tier_test": "", "source": "assumption (unobservable)", "low": odm["low"], "mid": odm["mid"], "high": odm["high"]},
        {"point": "component distributors (Nordic parts)", "tier_test": "", "source": "measured proxy: Microchip distributor days / 7 x Nordic distribution share", "low": md.min() * sh["low"], "mid": md.median() * sh["mid"], "high": md.max() * sh["high"]},
    ]
    t = pd.DataFrame(rows)
    body = t[~t["point"].str.startswith("  ")]
    total = {"point": "TOTAL end demand -> Nordic (prior for the Nordic-tier c x 52)", "tier_test": "nordic", "source": "sum",
             "low": body["low"].sum(), "mid": body["mid"].sum(), "high": body["high"].sum()}
    return pd.concat([t, pd.DataFrame([total])], ignore_index=True).round(1)


TIERS = [  # (tier, y column, demand column, lag, sample, prior row)
    ("logitech_channel", "logi_sales_yoy", "logi_sellthrough_yoy", 0, ("2022Q2", "2026Q2")),
    ("logitech_own", "logi_purchases_yoy", "logi_sales_yoy", 0, ("2021Q3", "2026Q2")),
    ("nordic", "nordic_consumer_yoy", "logi_sellthrough_yoy", 2, ("2022Q3", "2026Q2")),
]


def mechanism_tests(s: pd.DataFrame, gap_proxy: pd.Series, prior: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Every tier: (A) demand only, (B) + accelerator, (C) + stock gap. Plus the Nordic lag sweep for term 2."""
    boot = cfg["inventory_mechanism"]["bootstrap"]
    rows, fits = [], {}
    pr = prior.set_index("tier_test")
    for tier, yc, gc, L, smp in TIERS:
        specs = [("A demand", {}), ("B + accelerator", {"accel": True})]
        if tier == "nordic":
            specs.append(("C + stock gap (component distributor days vs normal, 1q earlier)", {"gap": gap_proxy, "gap_lag": 1}))
            specs += [(f"B + accelerator, lag {k}", {"accel": True, "_lag": k}) for k in (1, 3)]
        for name, kw in specs:
            lag = kw.pop("_lag", L)
            r = fit_link(s[yc], s[gc], lag, smp, boot=boot, **kw)
            fits[(tier, name)] = r
            prior_row = pr.loc[tier] if tier in pr.index else None
            rows.append({"tier": tier, "spec": name, "lag": lag, "n": r["n"], "a": r["a"], "b_demand": r["coef"]["g"],
                         "b_se": r["se"]["g"], "b_ci90": r.get("ci90", {}).get("g"),
                         "c_accel": r["coef"].get("d4g"), "c_se": r["se"].get("d4g"),
                         "implied_cover_wk": r.get("implied_cover_weeks"),
                         "prior_cover_wk": None if prior_row is None else f"{prior_row['low']:.0f}-{prior_row['high']:.0f} (mid {prior_row['mid']:.0f})",
                         "gamma_gap": r["coef"].get("gap"), "gamma_se": r["se"].get("gap"),
                         "r2": r["r2"], "rmse_loo": r["rmse_loo"]})
    t = pd.DataFrame(rows)
    num = ["a", "b_demand", "b_se", "c_accel", "c_se", "implied_cover_wk", "gamma_gap", "gamma_se", "r2", "rmse_loo"]
    t[num] = t[num].astype(float).round(2)
    return t, fits


def chain_consistency(s: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Product of the link elasticities vs the direct end-to-end elasticity (a check that the links add up)."""
    boot = cfg["inventory_mechanism"]["bootstrap"]
    a = fit_link(s["logi_sales_yoy"], s["logi_sellthrough_yoy"], 0, ("2022Q2", "2026Q2"))["coef"]["g"]
    b = fit_link(s["logi_purchases_yoy"], s["logi_sales_yoy"], 0, ("2022Q2", "2026Q2"))["coef"]["g"]
    c = fit_link(s["nordic_consumer_yoy"], s["logi_purchases_yoy"], 1, ("2022Q3", "2026Q2"))["coef"]["g"]
    d = fit_link(s["nordic_consumer_yoy"], s["logi_sellthrough_yoy"], 2, ("2022Q3", "2026Q2"), boot=boot)
    return pd.DataFrame([
        {"link": "channel: Logitech sell-in on sell-through (lag 0)", "elasticity": a},
        {"link": "Logitech own: purchases on sell-in (lag 0)", "elasticity": b},
        {"link": "Nordic consumer on Logitech purchases (lag 1)", "elasticity": c},
        {"link": "PRODUCT of the three links", "elasticity": a * b * c},
        {"link": "DIRECT: Nordic consumer on Logitech sell-through (lag 2)", "elasticity": d["coef"]["g"],
         "ci90": d["ci90"]["g"]},
    ]).round(2)


def predict_reduced(fit: dict, g: pd.Series, q: str) -> dict:
    """Reduced form (spec A): Nordic consumer YoY for quarter q from Logitech end demand `lag` quarters earlier."""
    t = pd.Period(q, "Q") - fit["lag"]
    gv = float(g.get(t, np.nan))
    return {"quarter": q, "driver_quarter": str(t), "driver_yoy": gv, "trend_a": fit["a"], "demand_b_x_g": fit["coef"]["g"] * gv,
            "yoy": fit["a"] + fit["coef"]["g"] * gv, "rmse_loo": fit["rmse_loo"]}
