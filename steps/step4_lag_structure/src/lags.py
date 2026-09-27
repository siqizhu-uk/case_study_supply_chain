"""Lag structure: reasoning first (config/model.yaml lag_weeks), then three
empirical checks on the panel:

1. Cross-correlation of Nordic consumer YoY against Logitech BLE YoY at 0..K lags,
   overall and by regime.
2. Turning-point alignment: when did each tier's YoY growth peak / trough / change sign?
3. Amplitude ratio: peak-to-trough swing at Nordic vs Logitech (bullwhip).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import edge_lags


def reasoned_lag_quarters(cfg: dict) -> dict:
    lw = cfg["lag_weeks"]
    out = {}
    for k in ("low", "mid", "high"):
        weeks = sum(lw[s][k] for s in lw)
        out[k] = {"weeks": weeks, "quarters": round(weeks / 13.0, 2)}
    return out


def cross_correlation(p: pd.DataFrame, target: str, driver: str, max_lag: int, regime: str | None = None) -> pd.DataFrame:
    df = p[[target, driver, "regime"]].copy()
    rows = []
    for k in range(0, max_lag + 1):
        d = df[driver].shift(k)
        sub = pd.DataFrame({"y": df[target], "x": d, "regime": df["regime"]}).dropna()
        if regime:
            sub = sub[sub["regime"] == regime]
        if len(sub) < 6:
            rows.append({"lag_q": k, "corr": np.nan, "n": len(sub)})
            continue
        rows.append({"lag_q": k, "corr": float(np.corrcoef(sub["x"], sub["y"])[0, 1]), "n": len(sub)})
    out = pd.DataFrame(rows)
    out["regime"] = regime or "all"
    return out


def turning_points(s: pd.Series) -> dict:
    s = s.dropna()
    if s.empty:
        return {}
    res = {"peak": str(s.idxmax()), "peak_val": round(float(s.max()), 1),
           "trough": str(s.idxmin()), "trough_val": round(float(s.min()), 1)}
    sign = np.sign(s)
    flips = s.index[(sign != sign.shift(1)) & sign.shift(1).notna()]
    res["sign_changes"] = [str(q) for q in flips]
    return res


def amplitude_ratio(p: pd.DataFrame, a: str, b: str, lo: str, hi: str) -> float:
    w = p.loc[pd.Period(lo, "Q"):pd.Period(hi, "Q")]
    swing_a = w[a].max() - w[a].min()
    swing_b = w[b].max() - w[b].min()
    return float(swing_a / swing_b) if swing_b else np.nan


def level_check(p: pd.DataFrame, implied: pd.Series, max_lag: int) -> dict:
    """Step 2b's implied Logitech→Nordic dollars (quarterly, at the path's time-varying content ratio) against Nordic
    consumer revenue: YoY cross-correlation at lags, and the implied dollars as a share of consumer revenue per regime."""
    df = p[["nordic_consumer", "regime"]].join(implied)
    yoy_n = df["nordic_consumer"].pct_change(4) * 100
    yoy_i = df["logi_implied_nordic_usdm"].pct_change(4) * 100
    rows = []
    for k in range(0, max_lag + 1):
        sub = pd.DataFrame({"y": yoy_n, "x": yoy_i.shift(k)}).dropna()
        rows.append({"lag_q": k, "corr": float(np.corrcoef(sub["x"], sub["y"])[0, 1]) if len(sub) >= 6 else np.nan, "n": len(sub)})
    share = (df["logi_implied_nordic_usdm"] / df["nordic_consumer"] * 100)
    return {"xcorr": pd.DataFrame(rows), "implied_share_of_consumer_by_regime": share.groupby(df["regime"]).median().round(1).to_dict(),
            "note": "level series from steps/step2_attribution/outputs/attribution_path.csv (nordic_content_pct_of_logi_sales_p50); the ratio is an estimate, the timing is the test"}


def lag_analysis(p: pd.DataFrame, cfg: dict, implied: pd.Series | None = None, attr: dict | None = None) -> dict:
    """Timing checks (L1-L3) and the edge-by-edge lag of the chain (edge_lags, L4-L9; attr = step 2's result, else its json)."""
    rc = cfg["regression"]
    target, driver, K = rc["target"], rc["driver"], rc["max_lag_quarters"]
    xc_all = cross_correlation(p, target, driver, K)
    xc_by_regime = pd.concat([cross_correlation(p, target, driver, K, r) for r in cfg["regimes"]], ignore_index=True)
    best_all = int(xc_all.loc[xc_all["corr"].idxmax(), "lag_q"]) if xc_all["corr"].notna().any() else None
    tp = {
        "sellout_proxy": turning_points(p["sellout_proxy_yoy"]),
        "logitech_ble": turning_points(p["logi_ble_yoy"]),
        "gn_periph": turning_points(p["gn_periph_yoy"]),
        "nordic_consumer": turning_points(p["nordic_consumer_yoy"]),
        "nordic_total": turning_points(p["nordic_rev_yoy"]),
    }
    amp = {
        "destock_2022_2024": amplitude_ratio(p, "nordic_consumer_yoy", "logi_ble_yoy", "2022Q1", "2024Q2"),
        "recovery_2024_2026": amplitude_ratio(p, "nordic_consumer_yoy", "logi_ble_yoy", "2024Q2", "2026Q2"),
    }
    return {"reasoned": reasoned_lag_quarters(cfg), "xcorr_all": xc_all, "xcorr_by_regime": xc_by_regime,
            "best_lag_all": best_all, "turning_points": tp, "amplitude": amp,
            "level_check": level_check(p, implied, K) if implied is not None else None, "edge_lags": edge_lags.run(p, cfg, attr)}
