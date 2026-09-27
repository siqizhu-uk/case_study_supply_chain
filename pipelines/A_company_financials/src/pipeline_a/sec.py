"""SEC XBRL company-facts → tidy quarterly table for the US filers.

Source: https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json (free, no key; SEC asks for a
descriptive User-Agent and ≤10 requests/s). Cached to data/cache/sec/ so re-runs are offline.

Quarterly derivation: companies file Q1–Q3 as 3-month durations and Q4 only inside the annual (10-K) figure,
so Q4 = FY − (Q1 + Q2 + Q3). Instants (inventory) are taken at each period end. Periods are mapped to the
calendar quarter containing the period-end date, which matches the hand-collected CSVs (TD Synnex's
Feb/May/Aug/Nov quarters land in Q1..Q4).
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .paths import ROOT, DATA_PROC, CACHE as _CACHE
from .manifest import COMPANIES, XBRL_TAGS

CACHE = _CACHE / "sec"
UA = "supply-chain-case-study (public research) siqizhu00@gmail.com"


def fetch_companyfacts(cik: int, refresh: bool = False) -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"CIK{cik:010d}.json"
    if f.exists() and not refresh:
        return json.loads(f.read_text())
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    f.write_text(json.dumps(data))
    time.sleep(0.15)  # stay well under the 10 req/s limit
    return data


def _facts(facts: dict, tags: list[str]) -> pd.DataFrame:
    """Union of all candidate tags (companies switch tags over time); later de-duplicated per period end."""
    usd = facts.get("facts", {}).get("us-gaap", {})
    frames = []
    for tag in tags:
        if tag in usd and "USD" in usd[tag]["units"]:
            df = pd.DataFrame(usd[tag]["units"]["USD"])
            df = df[df["form"].isin(["10-K", "10-Q", "10-K/A", "10-Q/A"])].copy()
            if df.empty:
                continue
            df["tag"] = tag
            df["end"] = pd.to_datetime(df["end"])
            df["start"] = pd.to_datetime(df["start"]) if "start" in df else pd.NaT
            frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def calendar_quarter(end) -> pd.Period:
    """The ONE rule for filing a ~13-week fiscal period under a calendar quarter (P124): the calendar quarter holding most of
    the period's days = period end - 45 days. Month-end closes (Logitech 30 Jun) and 52/53-week closes a few days either side
    of the quarter end (Arrow 4 Jul, Avnet 27 Jun, Ingram 27 Dec or 2 Jan) keep their quarter; closes about a month after it
    (Walmart / Target / Best Buy 31 Jul, ADI 2 Aug, Semtech 26 Apr) go to the quarter they mostly cover, not the next one."""
    return pd.Period(pd.Timestamp(end) - pd.Timedelta(days=45), "Q")


def _duration_quarters(df: pd.DataFrame, to_q=calendar_quarter) -> pd.Series:
    """Return a Series indexed by calendar Period('Q') of 3-month values, deriving Q4 from annual figures.
    `to_q` maps a period-end date to its calendar quarter (52/53-week filers need a shifted mapping)."""
    if df.empty:
        return pd.Series(dtype=float)
    df = df.dropna(subset=["start"]).copy()
    df["days"] = (df["end"] - df["start"]).dt.days
    q = df[(df["days"] >= 80) & (df["days"] <= 100)].sort_values(["end", "filed"]).drop_duplicates("end", keep="last")
    a = df[(df["days"] >= 350) & (df["days"] <= 380)].sort_values(["end", "filed"]).drop_duplicates("end", keep="last")
    out = {to_q(e): float(v) for e, v in zip(q["end"], q["val"])}
    for _, row in a.iterrows():
        inside = q[(q["end"] > row["start"]) & (q["end"] < row["end"])]
        if len(inside) == 3:
            out[to_q(row["end"])] = float(row["val"] - inside["val"].sum())
    return pd.Series(out).sort_index()


def _instant(df: pd.DataFrame, to_q=calendar_quarter) -> pd.Series:
    if df.empty:
        return pd.Series(dtype=float)
    d = df[df.get("start").isna()] if "start" in df else df
    d = d.sort_values(["end", "filed"]).drop_duplicates("end", keep="last")
    return pd.Series({to_q(e): float(v) for e, v in zip(d["end"], d["val"])}).sort_index()


def quarterly_table(company: str, refresh: bool = False) -> pd.DataFrame:
    cik = COMPANIES[company]["sec_cik"]
    facts = fetch_companyfacts(cik, refresh)
    rev = _duration_quarters(_facts(facts, XBRL_TAGS["revenue"]))
    cogs = _duration_quarters(_facts(facts, XBRL_TAGS["cogs"]))
    gp = _duration_quarters(_facts(facts, XBRL_TAGS["gross_profit"]))
    inv = _instant(_facts(facts, XBRL_TAGS["inventory"]))
    t = pd.DataFrame({"revenue_usdm": rev / 1e6, "cogs_usdm": cogs / 1e6, "gross_profit_usdm": gp / 1e6,
                      "inventory_usdm": inv / 1e6})
    t["gross_profit_usdm"] = t["gross_profit_usdm"].fillna(t["revenue_usdm"] - t["cogs_usdm"])
    t["cogs_usdm"] = t["cogs_usdm"].fillna(t["revenue_usdm"] - t["gross_profit_usdm"])
    t["gm_pct"] = t["gross_profit_usdm"] / t["revenue_usdm"] * 100
    t["company"] = company
    t.index.name = "quarter"
    return t[t.index >= pd.Period("2020Q1", "Q")]


def build_sec_quarterly(refresh: bool = False) -> pd.DataFrame:
    frames = [quarterly_table(c, refresh) for c, m in COMPANIES.items() if m["sec_cik"] and m.get("in_sec_quarterly", True)]
    out = pd.concat(frames).reset_index()
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(DATA_PROC / "sec_quarterly.csv", index=False)
    return out
