"""Step 6b — walk-forward back-test of the lag models, in the information set of the forecast date.

Why not leave-one-out: LOO trains on quarters AFTER the one it predicts, and the step-6 regression used the distributor
state of the quarter being predicted (known only when Nordic reports it). Neither is possible on 21 October.

Forecast date for target quarter t = the day before Nordic reports t:
    known   Logitech quarterly data through t-1 (Logitech reports ~1 week AFTER Nordic), Nordic actuals through t-1,
            Nordic's revenue guidance for t (given with the t-1 report), Nordic's coded distributor state through t-1
    unknown anything dated t
Every model is re-fit on the quarters before t (expanding window); lags and ridge alpha are the reasoned values from
config (not re-tuned), so no hyper-parameter sees the future and there is nothing to purge or embargo.

Models (target = Nordic consumer revenue YoY at t; total revenue = guidance midpoint + the model's consumer tilt):
    G       guidance-implied        consumer grows like the guided total: consumer_{t-4} x guide_t / revenue_{t-4}
    G+B     guidance + beat          G x (1 + mean beat of the previous 4 quarters)   <- the step-7 method, real time
    N       naive                    consumer YoY_t = consumer YoY_{t-1}
    L6      step-6 lag model         ridge: Logitech radio-category YoY at lags 1-3 + distributor state at t-1
    L6tv    step-6, share-weighted   same, driver re-weighted by step 2's attribution path
    L6leak  step-6 as it was         distributor state at t (the leak) - shown only to measure the leak
    L3      step-3 reduced form      OLS: Logitech sell-through YoY at lag 2
    GR      supply graph (step 5)     OLS on the same sell-out proxy pushed through the graph's lag kernel (path weights x path
                                      lags, graph as known at the origin); one slope, the lag structure is not fitted
    GRg     graph + Logitech guide   h=2 only: GR, but the demand quarter not yet reported (t-1) reads Logitech's own guide for
                                      it (given ~3 months before the origin) instead of persistence, so the edge lags move
                                      the forecast; Logitech guides quarterly only from 2025Q2 (before that GRg = GR)
Horizon h = 2 (the quarter AFTER the guided one, e.g. Q4 2026 on 21 October): origin = the day before Nordic reports
t-1; known = Nordic and Logitech through t-2 and the guide for t-1. There is no guidance for t, so the benchmark
becomes G = guide_{t-1} x last year's seasonal step revenue_{t-4} / revenue_{t-5}. Lag-1 regressors are dropped (Logitech
t-1 is not reported yet) and the distributor state enters at t-2. This is where a lag model could add information
guidance cannot.
Evaluation: RMSE / MAE / bias in YoY points and USD m; direction hit rate of the beat; Diebold-Mariano with the
Harvey-Leybourne-Newbold small-sample correction vs G+B; encompassing regression
    (actual_total - guide_t) = alpha + beta * (model tilt) + e     beta > 0 and significant = the model adds to guidance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def _ridge(X: np.ndarray, y: np.ndarray, alpha: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ridge on standardised regressors (intercept unpenalised), same as step 6's distributed_lag_regression."""
    mu, sd = X.mean(0), X.std(0, ddof=1)
    sd[sd == 0] = 1.0
    Z = np.column_stack([np.ones(len(X)), (X - mu) / sd])
    lam = np.eye(Z.shape[1]) * alpha
    lam[0, 0] = 0.0
    return np.linalg.solve(Z.T @ Z + lam, Z.T @ y), mu, sd


def _predict(beta, mu, sd, x: np.ndarray) -> float:
    return float(beta[0] + ((x - mu) / sd) @ beta[1:])


def logitech_guided_demand(p: pd.DataFrame) -> pd.Series:
    """Sell-out proxy for a quarter Logitech has guided but not reported: guided sales YoY + the latest known
    sell-through gap. Point in time at the origin of the Nordic forecast one quarter later."""
    return ((p["logi_guide_mid"] / p["logi_sales"].shift(4) - 1) * 100 + p["logi_st_gap"].shift(1)).dropna()


def incident_addback(p: pd.DataFrame, cfg: dict) -> pd.Series:
    """Decision F34: Logitech's disclosed supplier-incident loss (USD m) by calendar quarter of its sell-in, 0 elsewhere.
    GRi reads Logitech's sell-in as a proxy for Nordic's whole consumer cycle; a supply loss at Logitech alone is not that
    cycle, so it is added back to what GRi reads and reaches Nordic once, through the event term (chain_forecast.supplier_incident)."""
    add = pd.Series(0.0, index=p.index)
    rule = cfg.get("forecast_next_quarter", {}).get("gri_ex_incident", {})
    loss = cfg.get("structural_breaks", {}).get("logitech_supplier_incident_2026", {})
    if rule.get("apply") and loss.get("apply"):
        for key, quarter in rule["lost_sales"].items():
            q = pd.Period(quarter, "Q")
            if q in add.index:
                add[q] += float(loss[key])
    return add


def logitech_sellin_yoy_ex(p: pd.DataFrame, add: pd.Series) -> pd.Series:
    """Logitech's reported sell-in YoY with `add` (USD m) put back into every quarter it touches, as the level or as the
    year-ago base; all other quarters are the reported series, untouched."""
    a = add.reindex(p.index).fillna(0.0)
    a4 = a.shift(4).fillna(0.0)
    touched = (a != 0) | (a4 != 0)
    if not touched.any():
        return p["logi_sales_yoy"]
    adj = ((p["logi_sales"] + a) / (p["logi_sales"].shift(4) + a4) - 1) * 100
    return p["logi_sales_yoy"].where(~touched, adj)


def logitech_sellin_forecast(p: pd.DataFrame, add: pd.Series | None = None) -> pd.Series:
    """OUR forecast of Logitech's sell-in YoY for a guided quarter not yet reported: guide mid x (1 + Logitech's mean beat
    over the guided quarters reported before it). Point in time at the Nordic origin one quarter later (decision F26).
    No sell-through gap is needed: GRi's driver is sell-in (the gap is unforecastable, ~3 pts on every rule tried).
    `add` (F34): a disclosed one-off loss already inside the guide, put back (after the beat) so the fill is Logitech's
    sell-in without it."""
    a = (add if add is not None else pd.Series(0.0, index=p.index)).reindex(p.index).fillna(0.0)
    beat = (p["logi_sales"] / p["logi_guide_mid"] - 1) * 100
    habit = beat.shift(1).expanding().mean().fillna(0.0)
    level = p["logi_guide_mid"] * (1 + habit / 100) + a                       # + 0.0 outside the incident: bit-identical to F26
    base = p["logi_sales"].shift(4) + a.shift(4).fillna(0.0)
    return ((level / base - 1) * 100).dropna()


def gri_fill_check(p: pd.DataFrame, add: pd.Series | None = None) -> pd.DataFrame:
    """F26 evidence: our sell-in forecast vs persistence for each guided Logitech quarter, and the live (unreported) quarter
    (the live fill as GRi reads it, with any F34 add-back)."""
    si = p["logi_sales_yoy"]
    fc = logitech_sellin_forecast(p, add)
    d = pd.DataFrame({"actual_yoy": si, "our_forecast_yoy": fc, "persistence_yoy": si.shift(1)}).loc[fc.index]
    d["err_our_forecast"] = d["our_forecast_yoy"] - d["actual_yoy"]
    d["err_persistence"] = d["persistence_yoy"] - d["actual_yoy"]
    d.index = d.index.astype(str)
    return d.reset_index().rename(columns={"index": "quarter"})


def design(p: pd.DataFrame, model: str, cfg: dict, tv: pd.Series | None, h: int = 1, scenario: str = "mid") -> pd.DataFrame:
    """Regressors for each model, aligned so that row t only contains information dated t-h or earlier."""
    lags = [k for k in cfg["regression"]["lags_used"] if k >= h]
    if model in ("L6", "L6tv", "L6leak"):
        drv = tv if model == "L6tv" else p[cfg["regression"]["driver"]]
        X = pd.DataFrame({f"x_L{k}": drv.shift(k) for k in lags}, index=p.index)
        X["dist_state"] = p["nordic_dist_state"] if model == "L6leak" else p["nordic_dist_state"].shift(h)
        return X
    if model == "L3":
        g = p["logi_sales_yoy"] + p["logi_st_gap"]
        return pd.DataFrame({"st_L2": g.shift(2)}, index=p.index)
    if model == "GRi":                              # Logitech SELL-IN drives Nordic through the Nordic -> ODM -> Logitech segment only
        from supply_graph import propagate
        origin = lambda t: (t - h + 1).start_time + pd.Timedelta(days=20)   # noqa: E731
        fill = cfg.get("forecast_next_quarter", {}).get("gri_fill", "our_forecast")
        add = incident_addback(p, cfg)                    # F34: Logitech's own incident loss is not the common cycle; it enters once, as the event term
        ahead = logitech_sellin_forecast(p, add) if fill == "our_forecast" else None     # None -> persistence of sell-in (F24's rule)
        x = propagate(logitech_sellin_yoy_ex(p, add), cfg, h, origin, scenario=scenario, ahead=ahead, stop_at="logitech")
        return pd.DataFrame({"graph_sellin": x}, index=p.index)
    if model in ("GR", "GRg"):
        from supply_graph import propagate          # steps/step5_supply_graph/src
        g = p["logi_sales_yoy"] + p["logi_st_gap"]
        origin = lambda t: (t - h + 1).start_time + pd.Timedelta(days=20)   # noqa: E731  the day before Nordic reports t-h+1
        ahead = logitech_guided_demand(p) if model == "GRg" else None
        return pd.DataFrame({"graph_demand": propagate(g, cfg, h, origin, scenario=scenario, ahead=ahead)}, index=p.index)
    raise ValueError(model)


def _guidance_rows(p: pd.DataFrame, t: pd.Period, bw: int, h: int) -> dict:
    t4 = t - 4
    if h == 1:
        g_total = p.loc[t, "nordic_guide_mid"]
    else:                                         # no guide for t yet: last guide carried by last year's seasonal step
        g_total = p.loc[t - 1, "nordic_guide_mid"] * p.loc[t4, "nordic_rev"] / p.loc[t4 - 1, "nordic_rev"]
    g_cons = p.loc[t4, "nordic_consumer"] * g_total / p.loc[t4, "nordic_rev"]
    past = p["nordic_beat_vs_guide_pct"].loc[:t - h].dropna().tail(bw)
    beat = float(past.mean()) / 100 if len(past) else 0.0
    return {"guide_total": g_total, "guide_cons": g_cons, "beat_rt": beat}


def _models(h: int, tv: pd.Series | None) -> list[str]:
    return ["L6", "L3", "GR"] + (["L6leak"] if h == 1 else ["GRg", "GRi"]) + (["L6tv"] if tv is not None else [])


def forecast_row(p: pd.DataFrame, cfg: dict, designs: dict, t: pd.Period, h: int, exclude_sc: bool) -> dict:
    """Every model's forecast of Nordic consumer YoY for quarter t from the information of origin t-h (no actual needed)."""
    bt = cfg["backtest"]
    y_all = p["nordic_consumer_yoy"]
    gr = _guidance_rows(p, t, bt["beat_window_quarters"], h)
    cons4 = p.loc[t - 4, "nordic_consumer"]
    row = {"quarter": str(t), "horizon": h, "regime": p.loc[t, "regime"], "cons_t4": cons4, **gr,
           "G_yoy": (gr["guide_cons"] / cons4 - 1) * 100, "N_yoy": y_all.get(t - h, np.nan),
           "GB_yoy": (gr["guide_cons"] * (1 + gr["beat_rt"]) / cons4 - 1) * 100}
    for m, X in designs.items():
        train = pd.concat([y_all.rename("y"), X], axis=1).loc[:t - h].dropna()
        if exclude_sc:
            train = train[p.loc[train.index, "regime"] != "supply_constrained"]
        x_t = X.loc[t]
        if len(train) < bt["min_train_obs"] or x_t.isna().any():
            row[f"{m}_yoy"], row[f"{m}_ntrain"] = np.nan, len(train)
            continue
        Xm = train.drop(columns="y").values
        if m in ("L3", "GR", "GRg", "GRi"):
            b = np.linalg.lstsq(np.column_stack([np.ones(len(Xm)), Xm]), train["y"].values, rcond=None)[0]
            pred = float(b[0] + b[1:] @ x_t.values)
        else:
            beta, mu, sd = _ridge(Xm, train["y"].values, cfg["regression"]["ridge_alpha"])
            pred = _predict(beta, mu, sd, x_t.values)
        row[f"{m}_yoy"], row[f"{m}_ntrain"] = pred, len(train)
    return row


def _levels(out: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    """Consumer USD m and total = guidance + the model's consumer tilt (G itself -> the guide)."""
    out = out.copy()
    for m in ["G", "GB", "N"] + models:
        out[f"{m}_cons"] = out["cons_t4"] * (1 + out[f"{m}_yoy"] / 100)
        out[f"{m}_tilt"] = out[f"{m}_cons"] - out["guide_cons"]
        out[f"{m}_total"] = out["guide_total"] + out[f"{m}_tilt"]
    return out


def walk_forward(p: pd.DataFrame, cfg: dict, tv: pd.Series | None = None, exclude_sc: bool | None = None, h: int = 1) -> pd.DataFrame:
    bt = cfg["backtest"]
    ex = bt["exclude_supply_constrained_from_training"] if exclude_sc is None else exclude_sc
    y_all = p["nordic_consumer_yoy"]
    models = _models(h, tv)
    designs = {m: design(p, m, cfg, tv, h) for m in models}
    targets = [q for q in p.index if q >= pd.Period(bt["first_target"], "Q") and pd.notna(y_all.get(q))
               and pd.notna(p["nordic_guide_mid"].get(q if h == 1 else q - 1, np.nan))]
    rows = []
    for t in targets:
        r = forecast_row(p, cfg, designs, t, h, ex)
        r.update({"actual_cons": p.loc[t, "nordic_consumer"], "actual_total": p.loc[t, "nordic_rev"], "actual_yoy": y_all[t]})
        rows.append(r)
    return _levels(pd.DataFrame(rows).set_index("quarter"), models)


def live_forecasts(p: pd.DataFrame, cfg: dict, tv: pd.Series | None, targets: dict[int, str], scenario: str = "mid") -> pd.DataFrame:
    """The same models for quarters not yet reported, e.g. {1: '2026Q3', 2: '2026Q4'} from the 21 October origin.
    `scenario` (low / mid / high) sets the supply graph's shares and edge lags for GR / GRg."""
    ex = cfg["backtest"]["exclude_supply_constrained_from_training"]
    rows = []
    for h, q in targets.items():
        t = pd.Period(q, "Q")
        if t not in p.index:
            p = p.reindex(p.index.append(pd.PeriodIndex([t])))
        models = _models(h, tv)
        designs = {m: design(p, m, cfg, tv.reindex(p.index) if tv is not None else None, h, scenario) for m in models}
        rows.append(_levels(pd.DataFrame([forecast_row(p, cfg, designs, t, h, ex)]).set_index("quarter"), models))
    return pd.concat(rows)


def _dm_hln(e1: np.ndarray, e2: np.ndarray, h: int = 1) -> tuple[float, float]:
    """Diebold-Mariano on squared errors with autocovariances to lag h-1 and the Harvey-Leybourne-Newbold (1997)
    small-sample correction; returns (statistic, two-sided p from t_{n-1})."""
    d = e1 ** 2 - e2 ** 2
    n = len(d)
    if n < 4 or np.var(d, ddof=1) == 0:
        return np.nan, np.nan
    dc = d - d.mean()
    var = (dc @ dc + 2 * sum(dc[k:] @ dc[:-k] for k in range(1, h))) / n
    if var <= 0:
        return np.nan, np.nan
    dm = d.mean() / np.sqrt(var / n)
    hln = dm * np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    return float(hln), float(2 * stats.t.sf(abs(hln), df=n - 1))


def metrics(wf: pd.DataFrame, models: list[str], bench: str = "GB") -> pd.DataFrame:
    """Errors per model; the benchmark (G+B) is re-scored on exactly the model's quarters so the ratio is like for like."""
    h = int(wf["horizon"].iloc[0]) if "horizon" in wf and len(wf) else 1
    rows = []
    for m in models:
        cols = list(dict.fromkeys([f"{m}_yoy", f"{m}_total", "actual_yoy", "actual_total", "guide_total", f"{m}_tilt", f"{bench}_total"]))
        d = wf[cols].dropna()
        if d.empty:
            continue
        e_yoy = d[f"{m}_yoy"] - d["actual_yoy"]
        e_tot = d[f"{m}_total"] - d["actual_total"]
        e_b = d[f"{bench}_total"] - d["actual_total"]
        beat = d["actual_total"] - d["guide_total"]
        hit = float(np.mean(np.sign(d[f"{m}_tilt"]) == np.sign(beat))) if m != "G" else np.nan
        dm, pv = _dm_hln(e_tot.values, e_b.values, h) if m != bench else (np.nan, np.nan)
        rmse, rmse_b = float(np.sqrt(np.mean(e_tot ** 2))), float(np.sqrt(np.mean(e_b ** 2)))
        rows.append({"model": m, "n": len(d), "first": d.index[0], "last": d.index[-1],
                     "rmse_yoy_pts": np.sqrt(np.mean(e_yoy ** 2)), "bias_yoy_pts": e_yoy.mean(),
                     "rmse_total_usdm": rmse, "mae_total_usdm": e_tot.abs().mean(), "bias_total_usdm": e_tot.mean(),
                     f"{bench}_rmse_same_quarters": rmse_b, f"rmse_ratio_vs_{bench}": rmse / rmse_b if rmse_b else np.nan,
                     "beat_direction_hit": hit, f"dm_vs_{bench}": dm, f"dm_p_vs_{bench}": pv})
    return pd.DataFrame(rows).round(2)


def metrics_by_regime(wf: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    out = []
    for r, g in wf.groupby("regime"):
        m = metrics(g, models)
        m.insert(0, "regime", r)
        out.append(m)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def encompassing(wf: pd.DataFrame, models: list[str], hac_lags: int) -> pd.DataFrame:
    """(actual - guide) = a + b * tilt: does the model's disagreement with guidance predict the beat?"""
    rows = []
    for m in models:
        d = wf[[f"{m}_tilt", "actual_total", "guide_total"]].dropna()
        if len(d) < 5:
            continue
        y = (d["actual_total"] - d["guide_total"]).values
        X = np.column_stack([np.ones(len(d)), d[f"{m}_tilt"].values])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        e = y - X @ b
        xtx = np.linalg.inv(X.T @ X)
        u = X * e[:, None]
        s = u.T @ u
        for L in range(1, hac_lags + 1):
            g = u[L:].T @ u[:-L]
            s += (1 - L / (hac_lags + 1)) * (g + g.T)
        se = np.sqrt(np.diag(xtx @ s @ xtx * len(y) / (len(y) - 2)))
        rows.append({"model": m, "n": len(d), "alpha_usdm": b[0], "beta_on_tilt": b[1], "beta_se_hac": se[1], "t": b[1] / se[1],
                     "p": 2 * stats.t.sf(abs(b[1] / se[1]), df=len(y) - 2),
                     "reading": "adds to guidance" if b[1] > 0 and abs(b[1] / se[1]) > 2 else ("perverse sign" if b[1] < 0 and abs(b[1] / se[1]) > 2 else "no incremental information")})
    return pd.DataFrame(rows).round(3)
