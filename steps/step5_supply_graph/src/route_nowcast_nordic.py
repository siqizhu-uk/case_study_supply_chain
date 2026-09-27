"""Step 5f — the nowcast of Logitech's unreported quarter pushed through the graph into Nordic's h=2 forecast (decision G27).

At the h=2 origin of Nordic t (the day before Nordic reports t-1) the kernel's lags 0-1 need Logitech t-1, not yet reported.
Step 6 GR reads D(t-2) there (persistence); GRg reads Logitech's guide. Here each nowcast model fills t-1 with ITS nowcast
made at origin(t-1) - the same day - and nothing else: the `ahead` map holds only t-1, so a lag-0 weight can never read a
forecast of t made later (P107). graph_demand_at() is supply_graph.propagate's _known rule for that one-entry map (test:
equal to propagate on every quarter). Then step 6's own forecast_row (OLS of Nordic consumer YoY on the graph demand,
expanding window) and step 7c's CH formula (nothing fitted) turn it into Nordic totals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from route_propagation import ch_total, extend, targets
from supply_graph import kernel_asof

from core.config import ROOT

SHARE_PATH = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"


def graph_date(t: pd.Period, h: int) -> pd.Timestamp:
    """The graph (10-K weights) as step 6's walk-forward dates it for target t at horizon h."""
    return (t - h + 1).start_time + pd.Timedelta(days=20)


class KernelCache:
    """kernel_asof per date (the graph changes only at 10-K filing dates; the file reads are the cost)."""

    def __init__(self, cfg: dict):
        self.cfg, self.store = cfg, {}

    def __call__(self, date: pd.Timestamp) -> pd.Series:
        key = pd.Timestamp(date)
        if key not in self.store:
            k = kernel_asof(key, self.cfg, self.cfg["route_nowcast"]["scenario"])
            self.store[key] = k[k > 0]
        return self.store[key]


def _value(D: pd.Series, ahead: dict, t: pd.Period, j: int, h: int) -> float:
    """D(t-j) as known at the origin: reported (j >= h), else the nowcast held in `ahead`, else persistence."""
    for jj in range(j, j + 8):
        if jj >= h:
            return float(D.get(t - jj, np.nan))
        if t - jj in ahead and np.isfinite(ahead[t - jj]):
            return float(ahead[t - jj])
    return np.nan


def graph_demand_at(D: pd.Series, t: pd.Period, h: int, k: pd.Series, ahead: dict) -> float:
    vals = [_value(D, ahead, t, int(j), h) for j in k.index]
    return float(np.dot(k.values, vals)) if not np.isnan(vals).any() else np.nan


def graph_demand(D: pd.Series, nowcasts: pd.Series | None, h: int, kc: KernelCache) -> pd.Series:
    """Graph demand for every quarter of D; t-1 read from `nowcasts` (made at origin(t-1)) where given, else persistence."""
    out = {}
    for t in D.index:
        ahead = {} if nowcasts is None else {t - 1: float(nowcasts.get(t - 1, np.nan))}
        out[t] = graph_demand_at(D, t, h, kc(graph_date(t, h)), ahead)
    return pd.Series(out, name="graph_demand")


def nordic_row(p: pd.DataFrame, cfg: dict, X: pd.DataFrame, t: pd.Period, h: int, ctx: dict) -> dict:
    """GR total (step 6's forecast_row, OLS, expanding window) and CH total (step 7c formula) for one target."""
    from walkforward import forecast_row                 # steps/step6_backtest/src
    r = forecast_row(p, cfg, {"GR": X}, t, h, cfg["backtest"]["exclude_supply_constrained_from_training"])
    cons = r["cons_t4"] * (1 + r["GR_yoy"] / 100)
    gb = r["cons_t4"] * (1 + r["GB_yoy"] / 100)
    g = float(X["graph_demand"].get(t, np.nan))
    ch = ch_total(float(r["guide_total"]), float(ctx["share"][t]), float(p.loc[t - 4, "nordic_rev"]), ctx["m"], g)
    return {"guide_total": float(r["guide_total"]), "GB_total": float(r["guide_total"] + gb - r["guide_cons"]),
            "GR_total": float(r["guide_total"] + cons - r["guide_cons"]), "CH_total": ch, "graph_demand": g,
            "GR_ntrain": r["GR_ntrain"]}


def context(pe: pd.DataFrame, cfg: dict) -> dict:
    """Share path (step 2) and slice multiplier (step 3) for CH; the kernel cache."""
    from attribution_path import share_series          # steps/step2_attribution/src
    from chain_forecast import slice_multiplier          # steps/step7_forecast/src (read only)
    m, _ = slice_multiplier(cfg)
    return {"share": share_series(pd.read_csv(SHARE_PATH), pe) / 100, "m": m, "kc": KernelCache(cfg)}


def variants(pe: pd.DataFrame, cfg: dict, nowcasts: pd.DataFrame, kc: KernelCache) -> dict:
    """model -> design frame: the graph demand with that model's nowcast for t-1 (N0 = step 6 GR: no nowcast)."""
    rc = cfg["route_nowcast"]
    h, D = int(rc["nordic_horizon"]), pe[rc["target"]].sum(axis=1, min_count=len(rc["target"]))
    nc = nowcasts.copy()
    nc.index = pd.PeriodIndex(nc.index, freq="Q")
    out = {}
    for m, spec in rc["models"].items():
        series = None if spec["kind"] == "persistence" else nc[m].where(nc[f"{m}_fitted"].astype(bool))
        out[m] = pd.DataFrame({"graph_demand": graph_demand(D, series, h, kc)})
    return out


def walk_forward(p: pd.DataFrame, cfg: dict, nowcasts: pd.DataFrame) -> dict:
    """Step 6's h=2 targets and the live target, for every nowcast model: {'wf': long frame, 'live': long frame}."""
    rc = cfg["route_nowcast"]
    h, live_t = int(rc["nordic_horizon"]), pd.Period(rc["live_quarter"], "Q") + int(rc["nordic_horizon"]) - 1
    pe = extend(p, live_t)
    ctx = context(pe, cfg)
    X = variants(pe, cfg, nowcasts, ctx["kc"])
    rows = []
    for m, Xm in X.items():
        for t in targets(p, cfg, h) + [live_t]:
            r = nordic_row(pe, cfg, Xm, t, h, ctx)
            rows.append({"quarter": str(t), "model": m, "kind": "live" if t == live_t else "walkforward",
                         "actual_total": float(pe["nordic_rev"].get(t, np.nan)), **r})
    long = pd.DataFrame(rows)
    return {"wf": long[long["kind"] == "walkforward"].reset_index(drop=True), "live": long[long["kind"] == "live"].reset_index(drop=True)}
