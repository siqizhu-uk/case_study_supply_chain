"""Step 7b: the forecast one quarter past the guide (Nordic Q4 2026 from the 21 October origin, h = 2).

This is where the supply graph enters a forecast: GR / GRg push the sell-out proxy through the step-5 lag kernel, so an
edited edge lag or share (config/supply_graph.csv, config/model.yaml supply_graph) re-populates this table. The step-6
walk-forward supplies the error of each model at h = 2; the graph's low / high scenario (grade-based lag and share
ranges) supplies the structural uncertainty. Band = point +/- sqrt((z x RMSE)^2 + (half the scenario spread)^2).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from walkforward import live_forecasts, metrics, walk_forward   # steps/step6_backtest/src


def _band(point: float, rmse: float, lo_pt: float, hi_pt: float, z: float) -> tuple[float, float]:
    spread = abs(hi_pt - lo_pt) / 2 if np.isfinite(lo_pt) and np.isfinite(hi_pt) else 0.0
    hw = float(np.hypot(z * rmse, spread)) if np.isfinite(rmse) else spread
    lo = min(point - hw, lo_pt) if np.isfinite(lo_pt) else point - hw
    hi = max(point + hw, hi_pt) if np.isfinite(hi_pt) else point + hw
    return lo, hi


def forecast_next_quarter(p: pd.DataFrame, cfg: dict, tv: pd.Series | None, met_h2: pd.DataFrame | None = None,
                          event_usdm: float = 0.0) -> pd.DataFrame:
    """`event_usdm`: a dated event pushed forward through the graph (F21: Logitech's incident, step 5d), added to every model's
    point and band. GR's unreported quarter is filled by persistence, so it does not carry the incident; GRi's fill is Logitech's
    guide, which does, so GRi reads Logitech's sell-in with the disclosed loss added back (F34) and the incident enters once.
    GRg (sensitivity: the raw guide by definition) and the guide-carried benchmarks G / GB keep part of it in their inputs."""
    c = cfg["forecast_next_quarter"]
    t, h = c["target"], int(c["horizon"])
    if met_h2 is None:
        met_h2 = metrics(walk_forward(p, cfg, tv, h=h), [m for m in c["models"]])
    met = met_h2.set_index("model")
    live = {s: live_forecasts(p, cfg, tv, {h: t}, scenario=s).iloc[0] for s in ("mid", "low", "high")}
    prev = p["nordic_rev"].get(pd.Period(t, "Q") - 4, np.nan)
    rows = []
    for m in c["models"]:
        point = float(live["mid"][f"{m}_total"]) + event_usdm
        graph = m.startswith("GR")
        lo_pt = float(live["low"][f"{m}_total"]) + event_usdm if graph else np.nan
        hi_pt = float(live["high"][f"{m}_total"]) + event_usdm if graph else np.nan
        rmse = float(met.loc[m, "rmse_total_usdm"]) if m in met.index else np.nan
        lo, hi = _band(point, rmse, lo_pt, hi_pt, float(c["band_z"]))
        rows.append({"quarter": t, "horizon": h, "model": m, "role": c["role"].get(m, ""), "is_point": m == c["point_model"],
                     "point": point, "low": lo, "high": hi, "yoy_pct": (point / prev - 1) * 100 if prev else np.nan,
                     "lag_low_point": lo_pt, "lag_high_point": hi_pt, "wf_rmse_usdm": rmse,
                     "wf_n": met.loc[m, "n"] if m in met.index else np.nan,
                     "rmse_ratio_vs_GB": met.loc[m, "rmse_ratio_vs_GB"] if m in met.index else np.nan,
                     "guide_prev_q_mid": float(p["nordic_guide_mid"].get(pd.Period(t, "Q") - 1, np.nan)), "event_usdm": event_usdm})
    return pd.DataFrame(rows)


def next_quarter_md(df: pd.DataFrame) -> str:
    """Section for model_report.md."""
    pt = df[df["is_point"]].iloc[0]
    tab = df[["model", "role", "point", "low", "high", "yoy_pct", "lag_low_point", "lag_high_point", "wf_rmse_usdm", "wf_n", "rmse_ratio_vs_GB"]]
    return "\n".join([
        f"## Next quarter: Nordic {pt['quarter']} revenue (h = {int(pt['horizon'])}, graph-driven)\n",
        f"Point **USD {pt['point']:.0f}m** ({pt['low']:.0f}–{pt['high']:.0f}, {pt['yoy_pct']:+.0f}% y/y) from {pt['model']}. "
        "No guide exists for this quarter; the benchmark carries the Q3 guide by last year's seasonal step. The graph models "
        "read the step-5 lag kernel, so an edited edge lag moves them: GR only when a path's lag crosses two quarters "
        "(the unreported quarter is filled by persistence, P74), GRg whenever weight shifts between lags 1 and 2 "
        "(it reads Logitech's own Q3 guide). `lag_low_point` / `lag_high_point` = the graph's low / high scenario. "
        "Caveat: GR / GRg regress all Nordic consumer revenue on Logitech's sell-out proxy, so they carry the common consumer cycle, "
        "not the Logitech / GN slice; they fail when Logitech diverges from the rest of consumer electronics (e.g. the 2026 supplier "
        "incident; step 6 section 5, P86).\n",
        tab.round(2).to_markdown(index=False), ""])
