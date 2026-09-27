"""Step 5f — nowcast Logitech's unreported quarter from route proxies released before the origin (decision G27).

y(q) = Logitech sell-through YoY (sell-in YoY + disclosed gap; config route_nowcast.target), the demand series step 6 GR
feeds through the graph. At origin(q) (route_nowcast_data.origin) Logitech has reported q-1, not q. Models:
    N0  persistence (the default)       y^(q) = y(q-1)
    N1  Logitech's guide (comparison)   y^(q) = guided sales YoY(q) + gap(q-1)          (walkforward.logitech_guided_demand)
    N2  proxy change                    y^(q) = y(q-1) + b x C(q),  C(s) = mean_j dx_j(s) / sd_j
        dx_j(s) = x_j(s) - x_j(s-1), each x_j as released by origin(s) (route_nowcast_data.x_pit); sd_j over the changes
        known at origin(q); b = OLS without intercept on dy(s) = y(s) - y(s-1), s in [first_train_quarter, q-1]; b = 0
        (persistence) with fewer than min_train_obs pairs. One parameter: nests persistence, never extrapolates a level.
Every input is first cut to the vintage released by origin(q) (vintage()), so a value published later cannot enter.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import route_nowcast_data as rnd

PROXY_TABLES = {"tdsynnex": "tdsynnex", "bestbuy": "bestbuy", "rseas": "rseas"}


def target_series(p: pd.DataFrame, cfg: dict) -> pd.Series:
    cols = cfg["route_nowcast"]["target"]
    return p[cols].sum(axis=1, min_count=len(cols)).rename("y")


def guide_series(p: pd.DataFrame) -> pd.Series:
    """N1's value per quarter: Logitech's guided sales YoY + the previous quarter's gap (as step 6 GRg reads it)."""
    from walkforward import logitech_guided_demand          # steps/step6_backtest/src
    return logitech_guided_demand(p)


def proxy_table(p: pd.DataFrame, cfg: dict, spec: dict) -> pd.DataFrame:
    """One proxy as released (value, period end, release date)."""
    if spec["source"] == "tdsynnex":
        s = p[spec["column"]].dropna()
        return rnd.tdsynnex_table(rnd.asp_adjusted(s, cfg) if spec.get("asp_adjust") else s, cfg)
    if spec["source"] == "bestbuy":
        return rnd.bestbuy_table(spec["column"])
    if spec["source"] == "rseas":
        return rnd.rseas_table(cfg)
    raise ValueError(f"route_nowcast proxy source must be tdsynnex / bestbuy / rseas, got {spec['source']!r}")


def sources(p: pd.DataFrame, cfg: dict) -> dict:
    """Every table the nowcasts read: Logitech's target and guide, and each configured proxy."""
    y = target_series(p, cfg).dropna()
    g = guide_series(p)
    lag = pd.Timedelta(days=int(cfg["route_nowcast"]["release_lag"]["logitech_guide"]["days"]))
    g_rel = pd.Series([(q - 1).end_time.normalize() + lag for q in g.index], index=g.index)
    g_end = pd.Series([q.end_time.normalize() for q in g.index], index=g.index)
    out = {"logitech": rnd.calendar_table(y, cfg, "logitech"), "logitech_guide": rnd.quarter_table(g, g_end, g_rel)}
    out.update({name: proxy_table(p, cfg, spec) for name, spec in cfg["route_nowcast"]["proxies"].items()})
    return out


def vintage(S: dict, at: pd.Timestamp) -> dict:
    """Every table cut to the rows released by `at` (new frames)."""
    return {k: rnd.released(t, at) for k, t in S.items()}


def series(table: pd.DataFrame) -> pd.Series:
    return pd.Series(table["value"].values, index=pd.PeriodIndex(table["label"], freq="Q"), dtype=float)


def x_pit(table: pd.DataFrame, source: str, s: pd.Period, cfg: dict) -> dict:
    """The proxy for quarter s as known at origin(s)."""
    at = rnd.origin(s, cfg)
    if source == "rseas":
        return rnd.monthly_partial_yoy(table, s, at)
    return rnd.latest_overlapping(table, s, at)


def proxy_changes(V: dict, cfg: dict, quarters: list[pd.Period], names: list[str]) -> pd.DataFrame:
    """dx_j(s) = x_j(s) - x_j(s-1) for each proxy j and quarter s (from the vintage V only)."""
    specs = cfg["route_nowcast"]["proxies"]
    cols = {}
    for j in names:
        src = specs[j]["source"]
        cols[j] = [x_pit(V[j], src, s, cfg)["value"] - x_pit(V[j], src, s - 1, cfg)["value"] for s in quarters]
    return pd.DataFrame(cols, index=pd.PeriodIndex(quarters, freq="Q"), dtype=float)


def composite(dx: pd.DataFrame, min_obs: int) -> tuple[pd.Series, dict]:
    """C(s) = mean over proxies of dx_j / sd_j (no demeaning: 0 = no change); proxies with < min_obs changes dropped."""
    sd = {j: float(dx[j].dropna().std(ddof=1)) for j in dx if dx[j].notna().sum() >= min_obs}
    sd = {j: v for j, v in sd.items() if v > 0}
    if not sd:
        return pd.Series(np.nan, index=dx.index), {}
    z = pd.DataFrame({j: dx[j] / v for j, v in sd.items()})
    return z.mean(axis=1), sd


def fit_slope(dy: pd.Series, C: pd.Series, min_obs: int) -> tuple[float, int]:
    """b = sum(C dy) / sum(C^2) (OLS through the origin); 0 with fewer than min_obs pairs."""
    d = pd.concat([dy.rename("dy"), C.rename("C")], axis=1).dropna()
    if len(d) < min_obs or float((d["C"] ** 2).sum()) == 0:
        return 0.0, len(d)
    return float((d["C"] * d["dy"]).sum() / (d["C"] ** 2).sum()), len(d)


def proxy_nowcast(V: dict, q: pd.Period, cfg: dict, names: list[str], y: pd.Series) -> dict:
    """N2 for quarter q from the vintage V."""
    rc = cfg["route_nowcast"]
    first, n_min = pd.Period(rc["first_train_quarter"], "Q"), int(rc["min_train_obs"])
    quarters = list(pd.period_range(first, q, freq="Q"))
    if not quarters:                                            # before the training window: persistence
        return {"value": float(y.get(q - 1, np.nan)), "b": 0.0, "n_train": 0, "C_q": 0.0, "fitted": False, "used": ""}
    dx = proxy_changes(V, cfg, quarters, names)
    C, sd = composite(dx, n_min)
    dy = (y - y.shift(1)).reindex(pd.PeriodIndex(quarters[:-1], freq="Q"))
    b, n = fit_slope(dy, C.iloc[:-1], n_min)
    c_q = float(C.iloc[-1]) if pd.notna(C.iloc[-1]) else 0.0
    fitted = n >= n_min and pd.notna(C.iloc[-1])
    return {"value": float(y.get(q - 1, np.nan)) + b * c_q, "b": b, "n_train": n, "C_q": c_q, "fitted": bool(fitted),
            "used": "|".join(sd), **{f"dx_{j}": float(dx[j].iloc[-1]) for j in names}}


def nowcast(S: dict, q: pd.Period, cfg: dict, model: str) -> dict:
    """One model's nowcast of y(q) at origin(q); every input cut to the vintage released by then."""
    spec = cfg["route_nowcast"]["models"][model]
    V = vintage(S, rnd.origin(q, cfg))
    y = series(V["logitech"])
    if spec["kind"] == "persistence":
        return {"value": float(y.get(q - 1, np.nan)), "fitted": pd.notna(y.get(q - 1, np.nan))}
    if spec["kind"] == "guide":
        v = float(series(V["logitech_guide"]).get(q, np.nan))
        return {"value": v, "fitted": bool(np.isfinite(v))}
    if spec["kind"] == "proxy_change":
        return proxy_nowcast(V, q, cfg, list(spec["proxies"]), y)
    raise ValueError(f"route_nowcast model kind must be persistence / guide / proxy_change, got {spec['kind']!r}")


def walk_forward(S: dict, cfg: dict, quarters: list[pd.Period]) -> pd.DataFrame:
    """quarter x model nowcasts (each at its own origin) with the actual y(q) where reported."""
    actual = series(S["logitech"])
    rows = []
    for q in quarters:
        row = {"quarter": str(q), "origin": rnd.origin(q, cfg).date().isoformat(), "actual": float(actual.get(q, np.nan))}
        for m in cfg["route_nowcast"]["models"]:
            r = nowcast(S, q, cfg, m)
            row.update({m: r["value"], f"{m}_fitted": r["fitted"]})
            row.update({f"{m}_{k}": v for k, v in r.items() if k not in ("value", "fitted")})
        rows.append(row)
    return pd.DataFrame(rows).set_index("quarter")
