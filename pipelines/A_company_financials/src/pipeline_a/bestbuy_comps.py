"""Best Buy comparable sales by category (Domestic segment), from its quarterly earnings releases (8-K item 2.02, exhibit 99).
Computing & Mobile Phones is where Logitech's mice, keyboards and webcams sit; Consumer Electronics holds headsets and
speakers. A US retail sell-out proxy for Logitech's consumer channel, free and quarterly since FY2020.

Each release prints the category table for this quarter AND the same quarter a year earlier. Validation: the prior-year
figure in release t must equal the current figure in release t-4 (chain check; a difference is a restatement, e.g. the
FY27 reclassification of credit-card and digital revenue, listed and kept as reported in real time).
Fiscal quarters close on the Saturday nearest the end of Jan / Apr / Jul / Oct, so they are one month behind the
calendar quarter they are mapped to (FQ ending 1 Aug 2026 = May-Jul -> 2026Q2, two of three months overlap).
Output: data/raw/bestbuy_category_comps.csv (quarter, period_end, filed, category comps now and a year ago, url)."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request

import pandas as pd

from .paths import DATA_RAW, CACHE

CIK = 764478
UA = "siqi research siqizhu00@gmail.com"
ARCH = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
CATS = {"computing_mobile": "Computing and Mobile Phones", "consumer_electronics": "Consumer Electronics"}
_PCT = r"\(?(-?[\d.]+)\)?\s*%"


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    time.sleep(0.2)
    return data


def _pct(m: str, raw: str) -> float:
    """'(5.2)' is negative in the release's table notation."""
    return -float(m) if raw.strip().startswith("(") else float(m)


def _filings() -> list[dict]:
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{CIK:010d}.json"))["filings"]["recent"]
    return [{"filed": sub["filingDate"][i], "acc": sub["accessionNumber"][i].replace("-", ""), "report_date": sub["reportDate"][i]}
            for i in range(len(sub["form"])) if sub["form"][i] == "8-K" and "2.02" in sub["items"][i]]


def _exhibit(f: dict, refresh: bool) -> tuple[str, str] | None:
    d = CACHE / "sec" / "bestbuy"
    d.mkdir(parents=True, exist_ok=True)
    cache = d / f"{f['acc']}.txt"
    base = ARCH.format(cik=CIK, acc=f["acc"])
    if cache.exists() and not refresh:
        url, text = cache.read_text().split("\n", 1)
        return url, text
    items = json.loads(_get(base + "index.json"))["directory"]["item"]
    ex = [i["name"] for i in items if re.search(r"ex-?x?99|exx99|ex99", i["name"], re.I) and i["name"].endswith(".htm")]
    if not ex:
        return None
    url = base + ex[0]
    raw = _get(url).decode("utf8", "ignore")
    text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    cache.write_text(url + "\n" + text)
    return url, text


def parse(text: str) -> dict:
    """Domestic category table: '<category> mix_now % mix_prior % comp_now % comp_prior %' ('(5.2) %' negative, '- %' zero);
    the fiscal quarter end is the first date of the table header just before it."""
    val = r"(\(?-?[\d.]+\)?|-|—)\s*%"
    out = {}
    first = None
    for key, label in CATS.items():
        m = re.search(re.escape(label) + r"\s+" + r"\s+".join([val] * 4), text)
        if not m:
            continue
        first = first if first is not None else m.start()
        vals = [0.0 if g in ("-", "—") else _pct(re.sub(r"[()]", "", g), g) for g in m.groups()]
        out[f"{key}_mix_pct"], out[f"{key}_comp_pct"], out[f"{key}_comp_prior_pct"] = vals[0], vals[2], vals[3]
    if first is not None:
        dates = re.findall(r"([A-Z][a-z]+ \d{1,2}, \d{4})", text[max(0, first - 400): first])
        if dates:
            out["period_end"] = str(pd.Timestamp(dates[-4] if len(dates) >= 4 else dates[0]).date())
    return out


def fiscal_quarter(end) -> pd.Period:
    """Best Buy's quarters end about a month after the calendar quarter they mostly cover (1 Aug 2026 = May-Jul -> Q2):
    the shared rule sec.calendar_quarter (P124)."""
    from .sec import calendar_quarter
    return calendar_quarter(end)


def fetch(refresh: bool = False) -> pd.DataFrame:
    rows = []
    for f in _filings():
        got = _exhibit(f, refresh)
        if got is None:
            continue
        url, text = got
        r = parse(text)
        if "computing_mobile_comp_pct" not in r or "period_end" not in r:
            continue
        rows.append({"quarter": str(fiscal_quarter(r["period_end"])), "filed": f["filed"], "url": url, **r})
    df = pd.DataFrame(rows).drop_duplicates("quarter").sort_values("quarter").reset_index(drop=True)
    df.to_csv(DATA_RAW / "bestbuy_category_comps.csv", index=False)
    return df


def chain_check(df: pd.DataFrame, tol: float = 0.05) -> pd.DataFrame:
    """Prior-year comp printed in quarter t vs the comp printed in quarter t-4."""
    d = df.set_index(pd.PeriodIndex(df["quarter"], freq="Q"))
    rows = []
    for q in d.index:
        if q - 4 in d.index:
            a, b = d.loc[q, "computing_mobile_comp_prior_pct"], d.loc[q - 4, "computing_mobile_comp_pct"]
            rows.append({"quarter": str(q), "prior_as_printed_now": a, "as_printed_a_year_ago": b,
                         "agree": pd.notna(a) and pd.notna(b) and abs(a - b) <= tol})
    return pd.DataFrame(rows)
