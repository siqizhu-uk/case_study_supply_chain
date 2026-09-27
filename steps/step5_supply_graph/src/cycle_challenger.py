"""Step 5g — industry-cycle regression as a pre-registered challenger for Nordic one quarter past the guide (decision G29).

GR (step 6) regresses Nordic consumer YoY on Logitech sell-through pushed through the graph kernel; its slope is ~3x the
attribution slice (P77) because Nordic's other consumer customers ride the same cycle. CYC regresses the same target on an
industry-cycle series directly, not constrained to Logitech's total:
    Nordic consumer YoY_t = a + b x cycle YoY_(t-2)        (one slope, OLS, expanding window)
Total = the guide-anchored benchmark + the model's consumer tilt, exactly as GR (step 6 forecast_row is reused, so targets,
training rows, the supply-constrained rule and the guide rows are GR's). Spec and adoption bar: config cycle_challenger.

Point in time: origin(t) = the day before Nordic reports t-1 (route_nowcast.origin_days_after_quarter_end after t-1's end).
A cycle quarter is published when its third month is (quarter end + the series' release lag). The regressor for t is the
cycle YoY of t-2 if published by origin(t), else the latest published quarter (persistence, F24); nothing later is read.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import route_nowcast_data as rnd


def release_days(cfg: dict, series: str) -> int:
    """First-publication lag (days after the quarter's last month end) of a cycle series."""
    s = cfg["cycle_challenger"]["series"][series]
    if s.get("release") == "route_nowcast":
        return int(cfg["route_nowcast"]["release_lag"][series]["days"])
    return int(s["release_days"])


def origin(t: pd.Period, cfg: dict) -> pd.Timestamp:
    """The h-step origin of target t: the day before Nordic reports t-h+1."""
    return rnd.origin(t - int(cfg["cycle_challenger"]["horizon"]) + 1, cfg)


def released_value(values: pd.Series, t: pd.Period, cfg: dict, series: str) -> float:
    """Cycle YoY as known at origin(t): quarter t-lag if published, else the latest published quarter before it."""
    at, lag = origin(t, cfg), pd.Timedelta(days=release_days(cfg, series))
    want = t - int(cfg["cycle_challenger"]["lag_quarters"])
    known = [q for q in values.dropna().index if q <= want and q.end_time.normalize() + lag <= at]
    return float(values[max(known)]) if known else np.nan


def cycle_regressor(p: pd.DataFrame, cfg: dict, series: str) -> pd.Series:
    """The point-in-time regressor for every quarter of the panel (each row at its own origin)."""
    col = cfg["cycle_challenger"]["series"][series]["column"]
    v = p[col] if col in p else pd.Series(np.nan, index=p.index)
    return pd.Series([released_value(v, t, cfg, series) for t in p.index], index=p.index, name=series)


def designs(p: pd.DataFrame, cfg: dict) -> dict:
    """model -> design frame (regressor columns), every column point in time at each row's origin."""
    from walkforward import design                   # steps/step6_backtest/src: GR's graph demand at the same horizon
    cc = cfg["cycle_challenger"]
    h = int(cc["horizon"])
    cols = {s: cycle_regressor(p, cfg, s) for s in cc["series"]}
    cols["graph_demand"] = design(p, "GR", cfg, None, h)["graph_demand"]
    return {m: pd.DataFrame({r: cols[r] for r in spec["regressors"]}, index=p.index) for m, spec in cc["models"].items()}


def model_row(p: pd.DataFrame, cfg: dict, X: pd.DataFrame, t: pd.Period, exclude_sc: bool) -> dict:
    """One model's forecast for target t through step 6's forecast_row (OLS for the 'GR' slot, same window and rules)."""
    from walkforward import forecast_row             # steps/step6_backtest/src
    h = int(cfg["cycle_challenger"]["horizon"])
    r = forecast_row(p, cfg, {"GR": X}, t, h, exclude_sc)
    cons = r["cons_t4"] * (1 + r["GR_yoy"] / 100)
    gb_cons = r["cons_t4"] * (1 + r["GB_yoy"] / 100)
    return {"yoy": r["GR_yoy"], "total": r["guide_total"] + cons - r["guide_cons"], "ntrain": r["GR_ntrain"],
            "guide_total": r["guide_total"], "GB_total": r["guide_total"] + gb_cons - r["guide_cons"]}


def slope(p: pd.DataFrame, cfg: dict, X: pd.DataFrame, t: pd.Period, exclude_sc: bool) -> list[float]:
    """The OLS coefficients [a, b...] behind target t's forecast (training rows as forecast_row picks them)."""
    h = int(cfg["cycle_challenger"]["horizon"])
    train = pd.concat([p["nordic_consumer_yoy"].rename("y"), X], axis=1).loc[:t - h].dropna()
    if exclude_sc:
        train = train[p.loc[train.index, "regime"] != "supply_constrained"]
    A = np.column_stack([np.ones(len(train)), train.drop(columns="y").values])
    return [float(b) for b in np.linalg.lstsq(A, train["y"].values, rcond=None)[0]]


def gr_ch(p: pd.DataFrame, cfg: dict, exclude_sc: bool) -> pd.DataFrame:
    """GR and GB (step 6 walk_forward, h) and CH (step 7c formula, read only) per target quarter."""
    from attribution_path import share_series        # steps/step2_attribution/src
    from chain_forecast import nordic_ch_walkforward, slice_multiplier   # steps/step7_forecast/src (read only)
    from route_nowcast_nordic import SHARE_PATH
    from walkforward import walk_forward
    h = int(cfg["cycle_challenger"]["horizon"])
    wf = walk_forward(p, cfg, None, exclude_sc, h=h)
    m, _ = slice_multiplier(cfg)
    ch = nordic_ch_walkforward(p, cfg, wf, h, share_series(pd.read_csv(SHARE_PATH), p) / 100, m)
    return wf[["guide_total", "GB_total", "GR_total", "actual_total"]].join(ch[["CH_total"]])


def walk_forward(p: pd.DataFrame, cfg: dict, exclude_sc: bool | None = None) -> pd.DataFrame:
    """Step 6's h-step targets: GB, GR, CH and every CYC model's total (USD m), the regressors and the actual."""
    ex = cfg["backtest"]["exclude_supply_constrained_from_training"] if exclude_sc is None else exclude_sc
    base = gr_ch(p, cfg, ex)
    X = designs(p, cfg)
    rows = []
    for q in base.index:
        t = pd.Period(q, "Q")
        row = {"quarter": q, "regime": p.loc[t, "regime"]}
        for m, Xm in X.items():
            r = model_row(p, cfg, Xm, t, ex)
            row.update({f"{m}_total": r["total"], f"{m}_yoy": r["yoy"], f"{m}_ntrain": r["ntrain"]})
            row.update({f"x_{c}": float(Xm.loc[t, c]) for c in Xm.columns})
        rows.append(row)
    return base.join(pd.DataFrame(rows).set_index("quarter"))


def live(p: pd.DataFrame, cfg: dict) -> dict:
    """Every CYC model plus GR / GB / CH for the live target (h-step, from the same origin), before the event term."""
    from attribution_path import share_series
    from chain_forecast import nordic_live, slice_multiplier
    from route_nowcast_nordic import SHARE_PATH
    from walkforward import live_forecasts
    cc = cfg["cycle_challenger"]
    h, t = int(cc["horizon"]), pd.Period(cc["live_target"], "Q")
    pe = p.reindex(p.index.union(pd.period_range(p.index.min(), t, freq="Q")))
    ex = cfg["backtest"]["exclude_supply_constrained_from_training"]
    lv = live_forecasts(p, cfg, None, {h: str(t)}).reset_index()
    m, _ = slice_multiplier(cfg)
    ch = nordic_live(p, cfg, lv, share_series(pd.read_csv(SHARE_PATH), p) / 100, m)[h]
    out = {"quarter": str(t), "origin": origin(t, cfg).date().isoformat(), "GR_total": float(lv["GR_total"].iloc[0]),
           "GB_total": float(lv["GB_total"].iloc[0]), "CH_total": float(ch["CH_total"]), "guide_total": float(lv["guide_total"].iloc[0])}
    for mod, Xm in designs(pe, cfg).items():
        r = model_row(pe, cfg, Xm, t, ex)
        out.update({f"{mod}_total": r["total"], f"{mod}_yoy": r["yoy"], f"{mod}_ntrain": r["ntrain"],
                    f"{mod}_coef": slope(pe, cfg, Xm, t, ex), **{f"{mod}_x_{c}": float(Xm.loc[t, c]) for c in Xm.columns}})
    return out


def availability(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """For the live target: each cycle series' recent quarters, their publication date against the origin and which one is used."""
    cc = cfg["cycle_challenger"]
    t = pd.Period(cc["live_target"], "Q")
    at, want = origin(t, cfg), t - int(cc["lag_quarters"])
    rows = []
    for s, spec in cc["series"].items():
        v = p[spec["column"]] if spec["column"] in p else pd.Series(dtype=float)
        lag = release_days(cfg, s)
        used = released_value(v, t, cfg, s)
        for q in pd.period_range(want - 1, t - 1, freq="Q"):
            rel = q.end_time.normalize() + pd.Timedelta(days=lag)
            val = float(v.get(q, np.nan))
            rows.append({"series": s, "quarter": str(q), "value_yoy": val, "period_end": q.end_time.date().isoformat(),
                         "release_date": rel.date().isoformat(), "release_rule": f"month 3 end + {lag} d", "origin": at.date().isoformat(),
                         "available_at_origin": bool(rel <= at and np.isfinite(val)),
                         "used": bool(q == want and np.isfinite(val) and np.isclose(val, used))})
    return pd.DataFrame(rows)
