"""US electronics & appliance store sales (NAICS 443), seasonally adjusted, USD millions.

Primary: FRED series RSEAS (fredgraph.csv, keyless).  Cross-check: the Census Bureau's own MARTS text table
adv44300.txt, which FRED mirrors — every month present in both must agree to 0.5%.
Grade A (Census). Used only as retail-context; peripherals are a rounding error inside this category.
"""
from __future__ import annotations

import re

import pandas as pd

from .fetch import fetch

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=RSEAS"
CENSUS_URL = "https://www.census.gov/retail/marts/www/adv44300.txt"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def fred_rseas(refresh: bool = False) -> pd.DataFrame:
    f = fetch(FRED_URL, "fred_RSEAS.csv", refresh)
    d = pd.read_csv(f)
    d.columns = ["date", "rseas_usdm"]
    d["date"] = pd.to_datetime(d["date"])
    d["rseas_usdm"] = pd.to_numeric(d["rseas_usdm"], errors="coerce")
    return d.dropna()


def census_adv44300(refresh: bool = False) -> pd.DataFrame:
    """First block of the text file = adjusted sales in USD millions (the later blocks are seasonal factors)."""
    f = fetch(CENSUS_URL, "census_adv44300.txt", refresh)
    rows = []
    for line in f.read_text(errors="ignore").splitlines():
        m = re.match(r"^(\d{4})\s+(.*)$", line)
        if not m:
            continue
        vals = m.group(2).split()
        if not vals or "." in vals[0]:          # seasonal-factor block (decimals) -> stop
            break
        for i, v in enumerate(vals[:12]):
            rows.append({"date": pd.Timestamp(int(m.group(1)), i + 1, 1), "census_usdm": float(v)})
    return pd.DataFrame(rows)


def build_retail(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    fred, cen = fred_rseas(refresh), census_adv44300(refresh)
    d = fred.merge(cen, on="date", how="left")
    d["diff_pct"] = (d["rseas_usdm"] / d["census_usdm"] - 1) * 100
    both = d.dropna(subset=["census_usdm"])
    check = {"months_compared": int(len(both)), "max_abs_diff_pct": float(both["diff_pct"].abs().max()) if len(both) else None,
             "flagged": int((both["diff_pct"].abs() > 0.5).sum()), "fred_last": str(fred["date"].max().date()), "census_last": str(cen["date"].max().date())}
    d["rseas_yoy_pct"] = (d["rseas_usdm"] / d["rseas_usdm"].shift(12) - 1) * 100
    return d[["date", "rseas_usdm", "rseas_yoy_pct", "census_usdm", "diff_pct"]], check
