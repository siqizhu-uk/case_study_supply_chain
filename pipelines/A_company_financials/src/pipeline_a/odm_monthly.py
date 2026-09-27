"""Monthly revenue of the Taiwan-listed ODMs that ship to Logitech / GN (config/odm_candidates.csv, identity evidence
grade B-C: US customs records), from the TWSE market observation post (MOPS) static monthly pages:
    https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{ROC year}_{month}_0.html   (ROC year = year - 1911; from Jan 2010)
One Big5 table per month with every listed company: revenue this month / last month / same month last year (NT$ '000).
Validation: the 'same month last year' printed on page t must equal the revenue printed on page t-12 (chain check;
differences are restatements, listed). Caveat carried into step 4: these ODMs are diversified; Logitech's / GN's share
of their revenue is not disclosed, so the series is a diluted proxy of peripheral production.
Output: data/raw/odm_monthly_revenue.csv (month, code, name, revenue, prior_month, same_month_last_year, url)."""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import date

import pandas as pd

from .paths import DATA_RAW, DATA_PROC, CACHE, CONFIG as CONFIG_DIR

URL = "https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{roc}_{m}_0.html"
UA = "Mozilla/5.0 (supply-chain-case-study; siqizhu00@gmail.com)"


def _num(s: str) -> float | None:
    s = s.replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _page(year: int, month: int, refresh: bool = False) -> str | None:
    d = CACHE / "mops"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"t21sc03_{year}_{month:02d}.html"
    if refresh or not f.exists():
        url = URL.format(roc=year - 1911, m=month)
        try:
            raw = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60).read()
        except Exception:
            return None
        f.write_bytes(raw)
        time.sleep(0.6)
    return f.read_bytes().decode("big5", errors="ignore")


def parse(html: str, codes: list[str]) -> dict:
    out = {}
    for code in codes:
        m = re.search(r"<td[^>]*>\s*" + code + r"\s*</td>(.*?)</tr>", html, re.S)
        if not m:
            continue
        cells = [re.sub(r"<[^>]+>|&nbsp;", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", m.group(1), re.S)]
        if len(cells) >= 4:
            out[code] = {"name": cells[0], "revenue": _num(cells[1]), "prior_month": _num(cells[2]), "same_month_last_year": _num(cells[3])}
    return out


def fetch(refresh: bool = False, start: str = "2010-01") -> pd.DataFrame:
    cand = pd.read_csv(CONFIG_DIR / "odm_candidates.csv", dtype=str)
    codes = cand.loc[cand["monthly_revenue"] == "yes", "code"].tolist()
    names = dict(zip(cand["code"], cand["name"]))
    rows = []
    today = date.today()
    for per in pd.period_range(start, f"{today.year}-{today.month:02d}", freq="M"):
        html = _page(per.year, per.month, refresh and per >= pd.Period(today, "M") - 2)
        if not html:
            continue
        for code, v in parse(html, codes).items():                    # the page's company name is Chinese: keep the English one
            rows.append({"month": str(per), "code": code, **v, "name": names[code], "url": URL.format(roc=per.year - 1911, m=per.month)})
    df = pd.DataFrame(rows).sort_values(["code", "month"]).reset_index(drop=True)
    df.to_csv(DATA_RAW / "odm_monthly_revenue.csv", index=False)
    return df


def chain_check(df: pd.DataFrame) -> pd.DataFrame:
    """'same month last year' on page t vs revenue on page t-12 (0.5% tolerance)."""
    d = df.copy()
    d["period"] = pd.PeriodIndex(d["month"], freq="M")
    prev = d.set_index(["code", "period"])["revenue"]
    d["t12"] = [prev.get((c, p - 12)) for c, p in zip(d["code"], d["period"])]
    d = d.dropna(subset=["t12", "same_month_last_year"])
    d["ok"] = (d["same_month_last_year"] / d["t12"] - 1).abs() <= 0.005
    out = d.groupby("code").agg(n=("ok", "size"), agree=("ok", "sum")).reset_index()
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    d.loc[~d["ok"], ["code", "month", "same_month_last_year", "t12"]].to_csv(DATA_PROC / "odm_monthly_restatements.csv", index=False)
    return out
