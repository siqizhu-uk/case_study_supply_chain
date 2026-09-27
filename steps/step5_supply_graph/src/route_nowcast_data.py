"""Step 5f — route proxies as released: every value carries its period end and its first-publication date (decision G27).

A nowcast of Logitech's quarter q is made at origin(q) = q end + route_nowcast.origin_days_after_quarter_end (the day before
Nordic reports q). A proxy value can be used only if release_date <= origin(q); the release date is the filing date where the
repo stores one (Best Buy `filed`), else period end + a documented typical lag (config route_nowcast.release_lag, graded).
Fiscal calendars: TD Synnex's FQ ends in month 2 of the calendar quarter it is labelled with (2 of 3 months overlap); Best
Buy's quarter ends one month after its label's calendar quarter (P83), so the latest release at origin(q) is label q-1, which
overlaps q by one month. `x_pit(proxy, q)` = the latest released period that overlaps q (or, monthly, the released months
of q, as a partial-quarter YoY). Nothing here reads a value released after the origin: every lookup goes through released().
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

BESTBUY = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "bestbuy_category_comps.csv"
MACRO_MONTHLY = ROOT / "pipelines" / "B_macro_industry" / "data" / "processed" / "macro_monthly.csv"
COLUMNS = ["label", "value", "period_end", "release_date"]


def origin(q: pd.Period, cfg: dict) -> pd.Timestamp:
    """The day before Nordic reports q (q end + configured days)."""
    return q.end_time.normalize() + pd.Timedelta(days=int(cfg["route_nowcast"]["origin_days_after_quarter_end"]))


def _lag(cfg: dict, source: str) -> pd.Timedelta:
    return pd.Timedelta(days=int(cfg["route_nowcast"]["release_lag"][source]["days"]))


def month_end(q: pd.Period, month: int) -> pd.Timestamp:
    """Last day of month `month` (1-3) of calendar quarter q."""
    return (q.asfreq("M", "start") + (month - 1)).end_time.normalize()


def quarter_table(values: pd.Series, period_end: pd.Series, release: pd.Series) -> pd.DataFrame:
    """One row per labelled period (quarterly), NaN values dropped."""
    t = pd.DataFrame({"label": values.index, "value": values.values, "period_end": period_end.values,
                      "release_date": release.values})
    return t.dropna(subset=["value"]).reset_index(drop=True)


def calendar_table(values: pd.Series, cfg: dict, source: str) -> pd.DataFrame:
    """Calendar-quarter reporters (Logitech, Amazon, Ingram, CDW): period end = quarter end; release = end + lag."""
    ends = pd.Series([q.end_time.normalize() for q in values.index], index=values.index)
    return quarter_table(values, ends, ends + _lag(cfg, source))


def tdsynnex_table(values: pd.Series, cfg: dict) -> pd.DataFrame:
    """TD Synnex (FQ ends Feb/May/Aug/Nov, labelled with the calendar quarter holding 2 of its months): release = FQ end + lag."""
    m = int(cfg["route_nowcast"]["tdsynnex_period_end_month"])
    ends = pd.Series([month_end(q, m) for q in values.index], index=values.index)
    return quarter_table(values, ends, ends + _lag(cfg, "tdsynnex"))


def bestbuy_table(column: str) -> pd.DataFrame:
    """Best Buy comps with their 8-K filing dates and fiscal period ends (both stored in the Pipeline A file)."""
    b = pd.read_csv(BESTBUY)
    idx = pd.PeriodIndex(b["quarter"], freq="Q")
    return quarter_table(pd.Series(b[column].values, index=idx), pd.Series(pd.to_datetime(b["period_end"]).values, index=idx),
                         pd.Series(pd.to_datetime(b["filed"]).values, index=idx))


def rseas_table(cfg: dict) -> pd.DataFrame:
    """US electronics & appliance store sales, monthly levels; release = month end + lag."""
    m = pd.read_csv(MACRO_MONTHLY, parse_dates=["date"])
    months = pd.PeriodIndex(m["date"], freq="M")
    ends = pd.Series([x.end_time.normalize() for x in months], index=months)
    return quarter_table(pd.Series(m["rseas_usdm"].values, index=months), ends, ends + _lag(cfg, "rseas"))


def released(table: pd.DataFrame, at: pd.Timestamp) -> pd.DataFrame:
    """The vintage known at `at`: only rows first published on or before it (new frame)."""
    return table[pd.to_datetime(table["release_date"]) <= at].copy()


def overlap_months(period_end: pd.Timestamp, q: pd.Period, length: int = 3) -> int:
    """Months of the `length`-month period ending at period_end that fall in calendar quarter q. A retail 4-5-4 period
    ending in the first days of a month (Best Buy: 1 Aug) belongs to the previous month: the end is read 15 days earlier."""
    last = pd.Period(pd.Timestamp(period_end) - pd.Timedelta(days=15), "M")
    return sum(1 for k in range(length) if (last - k).asfreq("Q") == q)


def latest_overlapping(table: pd.DataFrame, q: pd.Period, at: pd.Timestamp) -> dict:
    """Latest period released by `at` that overlaps q: {'value', 'label', 'overlap', 'release_date'} (NaN if none)."""
    v = released(table, at)
    v = v.assign(overlap=[overlap_months(pd.Timestamp(e), q) for e in v["period_end"]])
    v = v[v["overlap"] > 0].sort_values("period_end")
    if v.empty:
        return {"value": np.nan, "label": "", "overlap": 0, "release_date": pd.NaT}
    r = v.iloc[-1]
    return {"value": float(r["value"]), "label": str(r["label"]), "overlap": int(r["overlap"]), "release_date": r["release_date"]}


def monthly_partial_yoy(table: pd.DataFrame, q: pd.Period, at: pd.Timestamp) -> dict:
    """YoY of the months of q released by `at` against the same months a year earlier (partial-quarter bridge)."""
    v = released(table, at).set_index("label")["value"]
    months = [m for m in pd.period_range(q.asfreq("M", "start"), q.asfreq("M", "end"), freq="M") if m in v.index]
    base = [m - 12 for m in months]
    if not months or any(b not in v.index for b in base):
        return {"value": np.nan, "label": "", "overlap": 0, "release_date": pd.NaT}
    yoy = (float(v.loc[months].sum()) / float(v.loc[base].sum()) - 1) * 100
    return {"value": yoy, "label": "|".join(str(m) for m in months), "overlap": len(months),
            "release_date": table.set_index("label").loc[months[-1], "release_date"]}


def asp_adjusted(values: pd.Series, cfg: dict) -> pd.Series:
    """Distributor dollar YoY minus the configured 2026 ASP tailwind from asp_adjust_from on (new series)."""
    sb = cfg["structural_breaks"]["distributor_asp_inflation_2026"]
    if not sb.get("apply"):
        return values.copy()
    mask = values.index >= pd.Period(cfg["route_nowcast"]["asp_adjust_from"], "Q")
    return values - np.where(mask, float(sb["asp_tailwind_pts"]), 0.0)
