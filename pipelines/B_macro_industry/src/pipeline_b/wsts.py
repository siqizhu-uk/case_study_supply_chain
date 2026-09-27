"""Global semiconductor billings (WSTS Blue Book), monthly, USD millions.

Primary: the WSTS Historical Billings Report workbook (public download; the link on the WSTS page changes each
month, so the page is scraped for the current .xlsx).  Cross-check: the SIA monthly press release quotes the
worldwide 3-month moving average ("$X billion during the month of <Month YYYY>"); that figure must equal the
WSTS 3MMA sheet for the same month to 0.5%.
Grade B (industry association). Used to date the 2022–24 industry destock; Nordic is ~0.1% of WSTS. Not in the model.
"""
from __future__ import annotations

import re

import pandas as pd

from .fetch import fetch

WSTS_PAGE = "https://www.wsts.org/67/Historical-Billings-Report"
SIA_NEWS = "https://www.semiconductors.org/news-events/latest-news/"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def wsts_workbook_url(refresh: bool = False) -> str:
    html = fetch(WSTS_PAGE, "wsts_page.html", refresh).read_text(errors="ignore")
    m = re.search(r'href="(https://www\.wsts\.org/[^"]*Historical-Billings-Report[^"]*\.xlsx)"', html)
    if not m:
        raise RuntimeError("WSTS workbook link not found on page")
    return m.group(1)


def _sheet_to_long(df: pd.DataFrame, region: str = "Worldwide") -> pd.Series:
    """Blue Book layout: a year row, then one row per region with Jan..Dec in columns 1..12."""
    out = {}
    year = None
    for _, r in df.iterrows():
        c0 = r.iloc[0]
        if isinstance(c0, (int, float)) and not pd.isna(c0) and 1980 < float(c0) < 2100:
            year = int(c0); continue
        if isinstance(c0, str) and c0.strip().lower().startswith(region.lower()) and year:
            for i in range(12):
                v = r.iloc[1 + i]
                if pd.notna(v) and v != 0:
                    out[pd.Timestamp(year, i + 1, 1)] = float(v) / 1000.0    # 1000 US$ -> USD m
    return pd.Series(out).sort_index()


def build_wsts(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    url = wsts_workbook_url(refresh)
    f = fetch(url, "wsts_historical_billings.xlsx", refresh)
    x = pd.ExcelFile(f)
    monthly = _sheet_to_long(x.parse("Monthly Data", header=None))
    mma = _sheet_to_long(x.parse("3MMA", header=None))
    d = pd.DataFrame({"wsts_ww_usdm": monthly, "wsts_ww_3mma_usdm": mma}).rename_axis("date").reset_index()
    d["wsts_ww_yoy_pct"] = (d["wsts_ww_usdm"] / d["wsts_ww_usdm"].shift(12) - 1) * 100
    d["wsts_3mma_yoy_pct"] = (d["wsts_ww_3mma_usdm"] / d["wsts_ww_3mma_usdm"].shift(12) - 1) * 100
    check = {"workbook_url": url, "months": int(len(d)), "last_month": str(d["date"].max().date())} | sia_crosscheck(d, refresh)
    return d, check


def sia_crosscheck(d: pd.DataFrame, refresh: bool = False) -> dict:
    """Latest SIA monthly release: '$X billion during the month of <Month> <Year>' vs WSTS 3MMA."""
    try:
        html = fetch(SIA_NEWS, "sia_news.html", refresh).read_text(errors="ignore")
        links = re.findall(r'href="(https://www\.semiconductors\.org/global-semiconductor-sales-[^"]*month-to-month[^"]*)"', html)
        if not links:
            return {"sia_status": "no monthly release link found"}
        rel = fetch(links[0], "sia_latest_release.html", refresh).read_text(errors="ignore")
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", rel))
        m = re.search(r"\$([\d.]+) billion (?:during|for) the month of (%s) (\d{4})" % "|".join(MONTHS), text)
        if not m:
            return {"sia_status": "headline figure not parsed", "sia_url": links[0]}
        val, month, year = float(m.group(1)) * 1000, MONTHS.index(m.group(2)) + 1, int(m.group(3))
        row = d[d["date"] == pd.Timestamp(year, month, 1)]
        if row.empty:
            return {"sia_status": f"WSTS workbook has no {m.group(2)} {year}", "sia_url": links[0], "sia_usdm": val}
        w = float(row["wsts_ww_3mma_usdm"].iloc[0])
        return {"sia_status": "ok", "sia_url": links[0], "sia_month": f"{year}-{month:02d}", "sia_usdm": val, "wsts_3mma_usdm": w,
                "diff_pct": (val / w - 1) * 100, "flagged": abs(val / w - 1) > 0.005}
    except Exception as e:  # network or layout change: report, don't fail the pipeline
        return {"sia_status": f"cross-check failed: {e}"}
