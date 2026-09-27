"""Step 5c - one quick test, then stop (decision G18): do the Taiwan-listed ODMs that ship to Logitech / GN (identity
grade B-C, config/odm_candidates.csv) lead Logitech's sales? Rolling 3-month ODM revenue YoY ending L months before each
calendar quarter end vs the quarter's YoY of Logitech sales, Nordic consumer revenue and TD Synnex revenue (control for the
common electronics cycle), 2021 onwards."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "odm_monthly_revenue.csv"


def lead_test(p: pd.DataFrame, leads=(0, 1, 2, 3, 6)) -> pd.DataFrame:
    if not RAW.exists():
        return pd.DataFrame()
    o = pd.read_csv(RAW, dtype={"code": str})
    o["m"] = pd.PeriodIndex(o["month"], freq="M")
    w = o.pivot(index="m", columns="code", values="revenue").sort_index()
    w["merry+chicony"] = w["2439"] + w["2385"]
    cand = pd.read_csv(ROOT / "pipelines" / "A_company_financials" / "config" / "odm_candidates.csv", dtype={"code": str})
    names = dict(zip(cand["code"], cand["name"]))
    targets = {"Logitech sales": p["logi_sales_yoy"], "Nordic consumer": p["nordic_consumer_yoy"], "TD Synnex (control)": p["snx_sales_yoy"]}
    rows = []
    for col in [c for c in w.columns]:
        r3 = w[col].rolling(3).sum()
        yoy = (r3 / r3.shift(12) - 1) * 100
        for L in leads:
            for tn, t in targets.items():
                t = t[t.index >= pd.Period("2021Q1", "Q")].dropna()
                x = pd.Series({Q: yoy.get(pd.Period(f"{Q.year}-{3 * Q.quarter:02d}", freq="M") - L, np.nan) for Q in t.index})
                d = pd.concat([x.rename("odm"), t.rename("y")], axis=1).dropna()
                if len(d) >= 8:
                    rows.append({"odm": names.get(col, col), "code": col, "target": tn, "lead_months": L,
                                 "corr": float(d.corr().iloc[0, 1]), "n_quarters": len(d)})
    return pd.DataFrame(rows)
