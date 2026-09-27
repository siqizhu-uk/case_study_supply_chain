"""Extend the hand-collected CSVs backwards with headline lines from SEC XBRL, so the 2020–21 supply-constrained
regime is covered by every US filer that existed as a public company then.

Only quarters the CSV does not already have are added, only headline columns are filled (segments stay blank),
and each added row is stamped source='SEC XBRL companyfacts (headline only)'. Idempotent.

Known level breaks in the extended history (flagged in config/model.yaml structural_breaks):
  * TD Synnex: SYNNEX merged with Tech Data on 1 Sep 2021 -> revenue triples from 2021Q4 (FQ4 FY21); no YoY across it.
  * Logitech: FY2021 quarters are the pandemic demand spike (2020Q3 +75% YoY); kept, labelled supply_constrained.
Ingram Micro was private until Oct 2024 and has no quarterly public data before 2022 (S-1 gives FY2022-23 only).
"""
from __future__ import annotations

import pandas as pd

from .paths import DATA_RAW, DATA_PROC
from .manifest import COMPANIES

EXTEND = {
    "tdsynnex": {"start": "2020Q1", "map": {"revenue_usdm": "revenue_usdm", "gross_profit_usdm": "gross_profit_usdm",
                                             "gm_pct": "gm_pct", "inventory_usdm": "inventory_usdm"}, "fiscal": "FQ{q}-{yy}"},
    "logitech": {"start": "2020Q1", "map": {"net_sales_usdm": "revenue_usdm", "gm_gaap_pct": "gm_pct",
                                             "inventory_usdm": "inventory_usdm"}, "fiscal": None},
}


def _logi_fiscal(q: pd.Period) -> str:
    fy = q.year + (1 if q.quarter >= 2 else 0)
    fq = (q.quarter - 2) % 4 + 1
    return f"FY{fy % 100:02d}Q{fq}"


def extend_from_xbrl(sec: pd.DataFrame | None = None) -> pd.DataFrame:
    if sec is None:
        sec = pd.read_csv(DATA_PROC / "sec_quarterly.csv")
    sec["quarter"] = pd.PeriodIndex(sec["quarter"], freq="Q")
    log = []
    for c, spec in EXTEND.items():
        path = DATA_RAW / COMPANIES[c]["raw_csv"]
        raw = pd.read_csv(path)
        have = set(raw["quarter"])
        s = sec[(sec["company"] == c) & (sec["quarter"] >= pd.Period(spec["start"], "Q"))].set_index("quarter")
        new = []
        for q, r in s.iterrows():
            if str(q) in have or pd.isna(r["revenue_usdm"]):
                continue
            row = {k: None for k in raw.columns}
            row["quarter"] = str(q)
            for rc, xc in spec["map"].items():
                row[rc] = round(float(r[xc]), 1) if pd.notna(r[xc]) else None
            if "fiscal_label" in raw.columns:
                row["fiscal_label"] = _logi_fiscal(q) if c == "logitech" else f"FQ{q.quarter}-{q.year % 100:02d}"
            if "is_estimate" in raw.columns:
                row["is_estimate"] = 0
            row["source"] = "SEC XBRL companyfacts (headline only; segments not available)"
            new.append(row)
        if new:
            raw = pd.concat([pd.DataFrame(new), raw], ignore_index=True)
            raw["_q"] = pd.PeriodIndex(raw["quarter"], freq="Q")
            raw = raw.sort_values("_q").drop(columns="_q")
            raw.to_csv(path, index=False)
        log.append({"company": c, "rows_added": len(new), "first_quarter_now": raw["quarter"].min()})
    return pd.DataFrame(log)
