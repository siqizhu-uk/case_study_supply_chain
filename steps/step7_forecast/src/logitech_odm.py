"""Step 7f: Logitech supply-side nowcast, a pre-registered challenger to the Logitech revenue forecast (decision F28;
spec in config/model.yaml logitech_odm_challenger, written before estimation).

At the forecast date (the last days of Logitech's quarter) its ODMs (Merry, Chicony; identity from US customs records,
grade C) have published the quarter's first two months. Their same-quarter revenue is news the guide did not have:
    s_t    = ODM revenue YoY over the months known at the forecast date - guide-implied Logitech YoY          (pts)
    beat_t = actual / guide mid - 1                                                                           (%)
    beat_t = a + b s_t, OLS on earlier guided quarters only (walk-forward); benchmark = mean past beat.
Caveats carried into the pitfall register: ODM revenue is in TWD (TWD/USD moves enter s_t); the ODMs have other customers
(a diluted proxy); at most 8 guided quarters.
"""
from __future__ import annotations

import hashlib
from datetime import date

import numpy as np
import pandas as pd

from core.config import ROOT

RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"
OUT = ROOT / "steps" / "step7_forecast" / "outputs"
LOG = OUT / "logitech_odm_prereg_log.csv"


def guides(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Every Logitech quarterly guide with its outcome: explicit (from 2025Q2) plus implied by annual / half-year outlooks."""
    l = pd.read_csv(RAW / "logitech_quarterly.csv").dropna(subset=["guide_low_usdm"])
    g = pd.DataFrame({"quarter": l["quarter"], "guide_mid": (l["guide_low_usdm"] + l["guide_high_usdm"]) / 2, "kind": "explicit"})
    if cfg["logitech_odm_challenger"].get("use_implied_guides", True) and (RAW / "logitech_implied_quarter_guides.csv").exists():
        im = pd.read_csv(RAW / "logitech_implied_quarter_guides.csv")
        g = pd.concat([g, pd.DataFrame({"quarter": im["target_quarter"], "guide_mid": (im["implied_low_usdm"] + im["implied_high_usdm"]) / 2,
                                        "kind": "implied"})], ignore_index=True)
    g.index = pd.PeriodIndex(g.pop("quarter"), freq="Q")
    g = g[~g.index.duplicated(keep="first")].sort_index()
    g["sales"] = p["logi_sales"].reindex(g.index)
    g["sales_t4"] = p["logi_sales"].shift(4).reindex(g.index)
    g["guide_yoy"] = (g["guide_mid"] / g["sales_t4"] - 1) * 100
    g["beat_pct"] = (g["sales"] / g["guide_mid"] - 1) * 100
    return g


def odm_yoy(cfg: dict, q: pd.Period, last_month: pd.Period | None = None) -> tuple[float, int]:
    """YoY of the ODMs' summed revenue over the months of quarter q known by `last_month` (all three if None)."""
    o = pd.read_csv(RAW / "odm_monthly_revenue.csv", dtype={"code": str})
    o = o[o["code"].isin(cfg["logitech_odm_challenger"]["odm_codes"])]
    m = o.assign(month=pd.PeriodIndex(o["month"], freq="M")).groupby("month")["revenue"].sum()
    months = [pd.Period(f"{q.year}-{3 * (q.quarter - 1) + i:02d}", "M") for i in (1, 2, 3)]
    if last_month is not None:
        months = [mm for mm in months if mm <= last_month]
    have = [mm for mm in months if mm in m.index and (mm - 12) in m.index]
    if not have:
        return np.nan, 0
    return float((m[have].sum() / m[[mm - 12 for mm in have]].sum() - 1) * 100), len(have)


def run(p: pd.DataFrame, cfg: dict) -> dict:
    c = cfg["logitech_odm_challenger"]
    g = guides(p, cfg)
    k = int(c.get("months_known", 3))                          # months of the quarter known at the forecast date (end of quarter: 2)
    g["odm_yoy"], g["odm_months"] = zip(*[odm_yoy(cfg, q, pd.Period(f"{q.year}-{3 * (q.quarter - 1) + k:02d}", "M")) for q in g.index])
    g["surprise"] = g["odm_yoy"] - g["guide_yoy"]
    rows = []
    for t in g.index:
        tr = g.loc[:t - 1].dropna(subset=["beat_pct", "surprise"])
        bench = float(tr["beat_pct"].mean()) if len(tr) else 0.0
        pred = np.nan
        if len(tr) >= c["min_train"] and pd.notna(g.loc[t, "surprise"]):
            b = np.polyfit(tr["surprise"], tr["beat_pct"], 1)
            pred = float(np.polyval(b, g.loc[t, "surprise"]))
        rows.append({"quarter": str(t), "kind": g.loc[t, "kind"], "guide_mid": g.loc[t, "guide_mid"], "guide_yoy": g.loc[t, "guide_yoy"],
                     "odm_yoy": g.loc[t, "odm_yoy"], "odm_months": g.loc[t, "odm_months"], "surprise": g.loc[t, "surprise"],
                     "n_train": len(tr), "beat_hat_pct": pred, "benchmark_beat_pct": bench, "actual_beat_pct": g.loc[t, "beat_pct"]})
    wf = pd.DataFrame(rows)
    sc = wf.dropna(subset=["beat_hat_pct", "actual_beat_pct"])
    score = {"n": len(sc),
             "rmse_model_pts": float(np.sqrt(((sc["beat_hat_pct"] - sc["actual_beat_pct"]) ** 2).mean())) if len(sc) else np.nan,
             "rmse_benchmark_pts": float(np.sqrt(((sc["benchmark_beat_pct"] - sc["actual_beat_pct"]) ** 2).mean())) if len(sc) else np.nan}
    full = g.dropna(subset=["beat_pct", "surprise"])
    fit = np.polyfit(full["surprise"], full["beat_pct"], 1) if len(full) >= 3 else [np.nan, np.nan]
    corr = float(np.corrcoef(full["surprise"], full["beat_pct"])[0, 1]) if len(full) >= 3 else np.nan
    live = wf[wf["actual_beat_pct"].isna()].tail(1)
    live_row = live.iloc[0].to_dict() if len(live) else {}
    if live_row:
        tr = g.dropna(subset=["beat_pct", "surprise"])
        b = np.polyfit(tr["surprise"], tr["beat_pct"], 1) if len(tr) >= c["min_train"] else None
        live_row["beat_hat_pct"] = float(np.polyval(b, live_row["surprise"])) if b is not None and pd.notna(live_row["surprise"]) else np.nan
        live_row["revenue_hat_usdm"] = live_row["guide_mid"] * (1 + live_row["beat_hat_pct"] / 100)
        live_row["benchmark_revenue_usdm"] = live_row["guide_mid"] * (1 + live_row["benchmark_beat_pct"] / 100)
    return {"walkforward": wf, "score": score, "full_sample": {"slope": float(fit[0]), "intercept": float(fit[1]), "corr": corr, "n": len(full)},
            "live": live_row}


def _hash(obj) -> str:
    return hashlib.sha1(repr(obj).encode()).hexdigest()[:10]


def write(r: dict, cfg: dict) -> pd.DataFrame:
    """Outputs plus the pre-registration log: a row per (target, spec, data); the last row before the print is of record."""
    OUT.mkdir(parents=True, exist_ok=True)
    r["walkforward"].round(3).to_csv(OUT / "logitech_odm_walkforward.csv", index=False)
    lv = r["live"]
    log = pd.read_csv(LOG, dtype=str) if LOG.exists() else pd.DataFrame()
    if not lv:
        return log
    spec = _hash([cfg["logitech_odm_challenger"], (ROOT / "steps" / "step7_forecast" / "src" / "logitech_odm.py").read_bytes()])
    data = _hash([round(lv["odm_yoy"], 4), lv["odm_months"], lv["guide_mid"], r["walkforward"]["actual_beat_pct"].round(4).tolist()])
    row = {"target": lv["quarter"], "spec_hash": spec, "data_hash": data, "logged_on": date.today().isoformat(),
           "odm_months_known": int(lv["odm_months"]), "odm_yoy_pct": round(lv["odm_yoy"], 2), "guide_mid_usdm": lv["guide_mid"],
           "surprise_pts": round(lv["surprise"], 2), "beat_hat_pct": round(lv["beat_hat_pct"], 2),
           "revenue_hat_usdm": round(lv["revenue_hat_usdm"], 1), "benchmark_revenue_usdm": round(lv["benchmark_revenue_usdm"], 1),
           "actual_usdm": "", "scored_on": ""}
    if log.empty or not ((log["target"] == row["target"]) & (log["spec_hash"] == spec) & (log["data_hash"] == data)).any():
        log = pd.concat([log, pd.DataFrame([row]).astype(str)], ignore_index=True)
        log.to_csv(LOG, index=False)
    return log
