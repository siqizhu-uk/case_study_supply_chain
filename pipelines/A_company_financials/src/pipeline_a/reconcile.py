"""Cross-check the hand-collected CSVs against the SEC XBRL table (US filers only).

Writes data/processed/sec_reconciliation.csv: one row per company × quarter × metric with the CSV value,
the XBRL value and the % difference. Anything beyond `tol_pct` is flagged — either a typing error in the CSV
(fix it) or a definitional difference (document it: e.g. Logitech non-GAAP vs GAAP, SNX revenue vs gross billings).
"""
from __future__ import annotations

import pandas as pd

from .paths import DATA_RAW, DATA_PROC
from .manifest import COMPANIES

# raw-CSV column -> XBRL column, per company
MAP = {
    "logitech": {"net_sales_usdm": "revenue_usdm", "inventory_usdm": "inventory_usdm", "gm_gaap_pct": "gm_pct"},
    "ingram":   {"net_sales_usdm": "revenue_usdm", "inventory_usdm": "inventory_usdm", "gross_profit_usdm": "gross_profit_usdm"},
    "tdsynnex": {"revenue_usdm": "revenue_usdm", "inventory_usdm": "inventory_usdm", "gross_profit_usdm": "gross_profit_usdm"},
}


def reconcile(sec: pd.DataFrame | None = None, tol_pct: float = 0.5) -> pd.DataFrame:
    if sec is None:
        sec = pd.read_csv(DATA_PROC / "sec_quarterly.csv")
    sec["quarter"] = pd.PeriodIndex(sec["quarter"], freq="Q")
    rows = []
    for company, cols in MAP.items():
        raw = pd.read_csv(DATA_RAW / COMPANIES[company]["raw_csv"])
        raw["quarter"] = pd.PeriodIndex(raw["quarter"], freq="Q")
        s = sec[sec["company"] == company].set_index("quarter")
        for _, r in raw.iterrows():
            if r["quarter"] not in s.index:
                continue
            for rc, xc in cols.items():
                a, b = r.get(rc), s.loc[r["quarter"], xc]
                if pd.isna(a) or pd.isna(b):
                    continue
                diff = (a / b - 1) * 100 if b else float("nan")
                rows.append({"company": company, "quarter": str(r["quarter"]), "metric": rc, "csv_value": round(a, 3),
                             "xbrl_value": round(b, 3), "diff_pct": round(diff, 3), "flag": abs(diff) > tol_pct})
    out = pd.DataFrame(rows)
    out.to_csv(DATA_PROC / "sec_reconciliation.csv", index=False)
    return out
