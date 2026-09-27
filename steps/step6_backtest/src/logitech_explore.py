"""Step 6i - EXPLORATION (analyst request 2026-09-26, decision B45): which public series forecast Logitech's quarterly
sales growth? Looked at before any specification is fixed, so every result here is in-sample in the sense that matters
(the factor choice sees the data). Every specification tried is logged in outputs/logitech_factor_exploration.csv; the
count is the multiple-testing denominator. A fixed specification can only be tested on prints after it is written down.

Target  y_t = Logitech net sales YoY (%) for calendar quarter t.
Forecast date = the day before Logitech reports t (~4 weeks after quarter end). Known then (lag 0): IDC / Gartner
        preliminary PC shipments for t (~2 weeks after quarter end), Census retail sales for t, TD Synnex's fiscal
        quarter ending in the last month of t (reported ~4 weeks after its end). Not known (lag >= 1): Logitech's own t,
        Ingram's t (reports after Logitech), Best Buy's quarter mapped to t (ends a month later).
Model   y_t = a + b x_t, OLS re-fit each quarter on the quarters before t (walk-forward, min 8 training quarters).
Scores  RMSE vs (1) naive y_{t-1}, (2) training mean, on the same quarters; on the guided quarters also vs the guide
        (guide midpoint / sales_{t-4} - 1).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

PC = ROOT / "pipelines" / "B_macro_industry" / "data" / "raw" / "pc_shipments_quarterly.csv"
BBY = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "bestbuy_category_comps.csv"

# (name, column, lag in quarters that respects the forecast date, economic sign, why)
CANDIDATES = [
    ("pc_shipments_idc_yoy", "pc_idc_yoy", 0, 1, "mice / keyboards / webcams are bought with PCs"),
    ("pc_shipments_gartner_yoy", "pc_gartner_yoy", 0, 1, "same, second source"),
    ("bestbuy_computing_comp", "bby_computing_comp", 1, 1, "US retail sell-out of the category Logitech sits in"),
    ("bestbuy_ce_comp", "bby_ce_comp", 1, 1, "headsets / speakers sell-out"),
    ("census_electronics_retail_yoy", "rseas_yoy", 0, 1, "US electronics store sales (broad)"),
    ("tdsynnex_endpoint_billings_yoy", "snx_endpoint_yoy", 0, 1, "enterprise endpoint demand at the IT distributor"),
    ("tdsynnex_inventory_days_change", "snx_inv_days_chg", 0, -1, "distributor already full -> fewer orders"),
    ("ingram_inventory_days_change", "ingm_inv_days_chg", 1, -1, "same, Ingram (reports after Logitech)"),
    ("logitech_sellthrough_minus_sellin", "logi_st_gap", 1, 1, "channel draining -> sell-in catches up"),
    ("logitech_sales_yoy_last_quarter", "logi_sales_yoy", 1, 1, "persistence (this is also the naive benchmark)"),
]


def _q(s: pd.Series) -> pd.PeriodIndex:
    return pd.PeriodIndex(s.astype(str), freq="Q")


def frame(p: pd.DataFrame) -> pd.DataFrame:
    """Target, guide and every candidate, one row per calendar quarter."""
    f = pd.DataFrame(index=p.index)
    f["y"] = p["logi_sales_yoy"]
    f["logi_sales_yoy"] = p["logi_sales_yoy"]
    f["guide_yoy"] = (p["logi_guide_mid"] / p["logi_sales"].shift(4) - 1) * 100 if "logi_guide_mid" in p else np.nan
    for c in ("rseas_yoy", "snx_endpoint_yoy", "logi_st_gap"):
        f[c] = p[c] if c in p else np.nan
    f["snx_inv_days_chg"] = p["snx_inv_days"].diff() if "snx_inv_days" in p else np.nan
    f["ingm_inv_days_chg"] = p["ingm_inv_days"].diff() if "ingm_inv_days" in p else np.nan
    if BBY.exists():
        b = pd.read_csv(BBY)
        b.index = _q(b["quarter"])
        f["bby_computing_comp"] = b["computing_mobile_comp_pct"].reindex(f.index)
        f["bby_ce_comp"] = b["consumer_electronics_comp_pct"].reindex(f.index)
    if PC.exists():
        pc = pd.read_csv(PC)
        for src in ("IDC", "Gartner"):
            s = pc[pc["source"] == src]
            f[f"pc_{src.lower()}_yoy"] = pd.Series(s["yoy_pct"].values, index=_q(s["quarter"])).groupby(level=0).last().reindex(f.index)
    return f


def walk_forward(y: pd.Series, x: pd.Series, min_train: int = 8, train_from: str | None = None) -> pd.Series:
    """`train_from` drops earlier quarters from every training window (structural break), not from the scored quarters."""
    out = {}
    d = pd.concat([y.rename("y"), x.rename("x")], axis=1)
    start = pd.Period(train_from, "Q") if train_from else d.index.min()
    for t in d.index:
        tr = d.loc[start:t - 1].dropna()
        if len(tr) < min_train or pd.isna(d.loc[t, "x"]) or pd.isna(d.loc[t, "y"]):
            continue
        b = np.polyfit(tr["x"], tr["y"], 1)
        out[t] = float(np.polyval(b, d.loc[t, "x"]))
    return pd.Series(out, dtype=float)


TRAIN_WINDOWS = {"all (2021Q1-)": None, "post-COVID (2022Q3-)": "2022Q3"}   # 2021-22: pandemic surge and bust (regimes in config)


def explore(p: pd.DataFrame, first: str = "2021Q1") -> pd.DataFrame:
    return pd.concat([_explore(p, first, w, tf) for w, tf in TRAIN_WINDOWS.items()], ignore_index=True)


def _explore(p: pd.DataFrame, first: str, window: str, train_from: str | None) -> pd.DataFrame:
    f = frame(p).loc[pd.Period(first, "Q"):]
    y = f["y"]
    rows = []
    for name, col, lag, sign, why in CANDIDATES:
        if col not in f or f[col].notna().sum() < 10:
            rows.append({"train_window": window, "factor": name, "lag": lag, "prior_sign": sign, "why": why, "n": int(f[col].notna().sum()) if col in f else 0})
            continue
        x = f[col].shift(lag)
        both = pd.concat([y, x], axis=1).dropna()
        pred = walk_forward(y, x, train_from=train_from).loc[pd.Period("2024Q1", "Q"):]   # same scored quarters in both windows
        idx = pred.index
        naive = y.shift(1).reindex(idx)
        tstart = pd.Period(train_from, "Q") if train_from else y.index.min()
        mean = pd.Series({t: y.loc[tstart:t - 1].dropna().mean() for t in idx}, dtype=float)
        e, en, em = pred - y.reindex(idx), naive - y.reindex(idx), mean - y.reindex(idx)
        g = f["guide_yoy"].reindex(idx)
        gi = g.dropna().index
        slope = np.polyfit(both.iloc[:, 1], both.iloc[:, 0], 1)[0] if len(both) > 2 else np.nan
        rows.append({"train_window": window, "factor": name, "lag": lag, "prior_sign": sign, "why": why, "n": len(both),
                     "corr_full_sample": both.corr().iloc[0, 1], "slope_full_sample": slope,
                     "sign_matches_prior": bool(np.sign(slope) == sign) if pd.notna(slope) else None,
                     "wf_n": len(idx), "wf_first": str(idx.min()) if len(idx) else "",
                     "wf_rmse": float(np.sqrt((e ** 2).mean())) if len(idx) else np.nan,
                     "naive_rmse": float(np.sqrt((en ** 2).mean())) if len(idx) else np.nan,
                     "mean_rmse": float(np.sqrt((em ** 2).mean())) if len(idx) else np.nan,
                     "oos_r2_vs_naive": float(1 - (e ** 2).sum() / (en ** 2).sum()) if len(idx) else np.nan,
                     "guided_n": len(gi),
                     "guided_rmse_model": float(np.sqrt((e.loc[gi] ** 2).mean())) if len(gi) else np.nan,
                     "guided_rmse_guide": float(np.sqrt(((g.loc[gi] - y.reindex(gi)) ** 2).mean())) if len(gi) else np.nan})
    return pd.DataFrame(rows)
