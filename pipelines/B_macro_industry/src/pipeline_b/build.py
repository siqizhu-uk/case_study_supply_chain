"""Assemble the monthly and quarterly context tables and date the industry cycle."""
from __future__ import annotations

import pandas as pd

from .paths import DATA_PROC
from .retail import build_retail
from .wsts import build_wsts
from .fx import build_fx


def build_all(refresh: bool = False) -> dict:
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    retail, rcheck = build_retail(refresh)
    wsts, wcheck = build_wsts(refresh)
    m = wsts.merge(retail, on="date", how="outer").sort_values("date")
    m = m[m["date"] >= "2018-01-01"]
    m.to_csv(DATA_PROC / "macro_monthly.csv", index=False)

    q = m.set_index("date")[["wsts_ww_usdm", "rseas_usdm"]].resample("QE").sum(min_count=3)
    q.index = q.index.to_period("Q")
    q["wsts_yoy_pct"] = (q["wsts_ww_usdm"] / q["wsts_ww_usdm"].shift(4) - 1) * 100
    q["rseas_yoy_pct"] = (q["rseas_usdm"] / q["rseas_usdm"].shift(4) - 1) * 100
    q = q.dropna(subset=["wsts_ww_usdm"]).rename_axis("quarter").reset_index()
    q.to_csv(DATA_PROC / "macro_quarterly.csv", index=False)

    # industry destock = the longest run of quarters with WSTS YoY < 0 since 2020
    neg = q[(q["quarter"] >= pd.Period("2020Q1", "Q")) & (q["wsts_yoy_pct"] < 0)]["quarter"].tolist()
    runs, cur = [], []
    for p in neg:
        if cur and p != cur[-1] + 1:
            runs.append(cur); cur = []
        cur.append(p)
    if cur:
        runs.append(cur)
    longest = max(runs, key=len) if runs else []
    cycle = {"wsts_negative_yoy_quarters": [str(p) for p in neg],
             "industry_destock_window": f"{longest[0]}–{longest[-1]}" if longest else "none"}
    fxq, fxcheck = build_fx(refresh)                          # ECB reference rates for the post-guide FX update (F27)
    return {"retail_check": rcheck, "wsts_check": wcheck, "fx_check": fxcheck, "cycle": cycle, "quarterly": q}
