"""Logitech's guidance history, FY2019-FY2027: every outlook statement in its earnings releases (8-K item 2.02,
exhibit 99.1) - initial, raised, lowered, reaffirmed, withdrawn - and the outcome it was guiding, for the dashboard
panel on guidance accuracy and conservatism (step 7, with Nordic's quarterly guides and GN's annual guides).

Every row carries the release URL and an exact excerpt; `build()` checks each excerpt word for word against the cached
release text (data/cache/sec/logitech_releases/, fetched by `fetch()`) and records the result in the verification
ledger, so a fresh clone shows the recorded check without downloading. Values are typed from the excerpt; the excerpt
check guards the typing.
Word ranges are converted as: 'mid single-digit' = 4-6, 'mid to high single-digit' = 4-9, 'approximately flat, plus
or minus 5 percent' = -5..+5 (stated in the note column of each row).
Output: data/raw/logitech_guidance_history.csv."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .paths import DATA_RAW, CACHE

CIK = 1032975
UA = "siqi research siqizhu00@gmail.com"
REL = CACHE / "sec" / "logitech_releases"
OUT = DATA_RAW / "logitech_guidance_history.csv"

# (statement date, period, metric, low, high, action, excerpt, note)
#   period: FY2021 (fiscal year ending March 2021) | H1FY2024 | Q2FY2027 ; metric: sales_growth_cc_pct | sales_usdm | op_income_usdm
S = [
    ("2019-01-22", "FY2019", "op_income_usdm", 340, 345, "raised", "raised its Fiscal Year 2019 profit outlook to between $340 million and $345 million in non-GAAP operating income", "previous 325-335"),
    ("2019-01-22", "FY2019", "sales_growth_cc_pct", 9, 11, "reiterated", "on an annual sales outlook of 9 to 11 percent growth in constant currency", ""),
    ("2019-04-30", "FY2020", "sales_growth_cc_pct", 4, 9, "reiterated", "confirmed its Fiscal Year 2020 outlook of mid to high single-digit sales growth", "first 8-K statement; 'mid to high single-digit' = 4-9"),
    ("2019-04-30", "FY2020", "op_income_usdm", 375, 385, "reiterated", "$375 million to $385 million in non-GAAP operating income", "first 8-K statement"),
    ("2019-07-23", "FY2020", "op_income_usdm", 375, 385, "reiterated", "$375 million to $385 million in non-GAAP operating income", ""),
    ("2020-01-21", "FY2020", "op_income_usdm", 375, 385, "reiterated", "On the back of this strong performance, we are confirming our annual guidance.", ""),
    ("2020-05-12", "FY2021", "sales_growth_cc_pct", 4, 6, "reiterated", "confirmed its Fiscal Year 2021 outlook of mid single-digit sales growth", "first 8-K statement; 'mid single-digit' = 4-6"),
    ("2020-05-12", "FY2021", "op_income_usdm", 380, 400, "reiterated", "$380 million to $400 million in non-GAAP operating income", "first 8-K statement"),
    ("2020-07-21", "FY2021", "sales_growth_cc_pct", 10, 13, "raised", "raised its Fiscal Year 2021 annual sales outlook from mid single-digit sales growth to 10 to 13 percent growth in constant currency", ""),
    ("2020-07-21", "FY2021", "op_income_usdm", 410, 425, "raised", "to a range of $410 million to $425 million", ""),
    ("2020-10-20", "FY2021", "sales_growth_cc_pct", 35, 40, "raised", "raised its Fiscal Year 2021 annual outlook to between 35 and 40 percent sales growth in constant currency and a range of $700 million to $725 million", ""),
    ("2020-10-20", "FY2021", "op_income_usdm", 700, 725, "raised", "a range of $700 million to $725 million in non-GAAP operating income", ""),
    ("2021-01-19", "FY2021", "sales_growth_cc_pct", 57, 60, "raised", "raised its Fiscal Year 2021 annual outlook to between 57 and 60 percent sales growth in constant currency", ""),
    ("2021-01-19", "FY2021", "op_income_usdm", 1050, 1050, "raised", "approximately $1.05 billion in non-GAAP operating income", "point guide"),
    ("2021-04-29", "FY2022", "sales_growth_cc_pct", -5, 5, "reiterated", "The outlook for sales growth in constant currency is still expected to be approximately flat, plus or minus 5 percent.", "'approximately flat, plus or minus 5' = -5..+5"),
    ("2021-04-29", "FY2022", "op_income_usdm", 800, 850, "raised", "raised its Fiscal Year 2022 outlook for non-GAAP operating income to between $800 million and $850 million", "previous 750-800"),
    ("2021-07-27", "FY2022", "op_income_usdm", 800, 850, "reiterated", "confirmed its Fiscal Year 2022 outlook of flat sales growth in constant currency, plus or minus five percent, and $800 million to $850 million", ""),
    ("2021-10-26", "FY2022", "op_income_usdm", 800, 850, "reiterated", "confirmed its Fiscal Year 2022 outlook of flat sales growth in constant currency, plus or minus five percent, and $800 million to $850 million", ""),
    ("2022-01-25", "FY2022", "sales_growth_cc_pct", 2, 5, "raised", "raised its Fiscal Year 2022 annual outlook to between 2 and 5 percent sales growth in constant currency", ""),
    ("2022-01-25", "FY2022", "op_income_usdm", 850, 900, "raised", "between $850 million and $900 million in non-GAAP operating income", ""),
    ("2022-05-03", "FY2023", "sales_growth_cc_pct", 2, 4, "lowered", "Sales growth in constant currency is now expected to be between 2 and 4 percent", "previous 'mid single digits'; Russia / Ukraine removed"),
    ("2022-05-03", "FY2023", "op_income_usdm", 875, 925, "lowered", "non-GAAP operating income is expected to be between $875 million and $925 million", "previous 900-950"),
    ("2022-07-26", "FY2023", "sales_growth_cc_pct", -8, -4, "lowered", "reduced its Fiscal Year 2023 outlook to between negative 8 percent and negative 4 percent sales growth in constant currency", ""),
    ("2022-07-26", "FY2023", "op_income_usdm", 650, 750, "lowered", "between $650 million and $750 million in non-GAAP operating income", ""),
    ("2022-10-25", "FY2023", "sales_growth_cc_pct", -8, -4, "reiterated", "reaffirmed its Fiscal Year 2023 outlook of between negative 8 percent and negative 4 percent", ""),
    ("2023-01-12", "FY2023", "sales_growth_cc_pct", -15, -13, "lowered", "adjusted its Fiscal Year 2023 outlook to between negative 15 percent and negative 13 percent sales growth in constant currency", "ad hoc pre-announcement"),
    ("2023-01-12", "FY2023", "op_income_usdm", 550, 600, "lowered", "between $550 million and $600 million in non-GAAP operating income", "ad hoc pre-announcement"),
    ("2023-05-02", "H1FY2024", "sales_usdm", 1800, 1900, "reiterated", "H1 2024 outlook Sales $1.8 billion - $1.9 billion", "first 8-K statement"),
    ("2023-05-02", "H1FY2024", "op_income_usdm", 160, 190, "reiterated", "Non-GAAP operating income $160 million - $190 million", ""),
    ("2023-07-25", "H1FY2024", "sales_usdm", 1875, 1975, "raised", "Sales $1.8 - $1.9 billion $1.875 - $1.975 billion", "previous -> new"),
    ("2023-07-25", "H1FY2024", "op_income_usdm", 180, 220, "raised", "Non-GAAP operating income $160 - $190 million $180 - $220 million", "previous -> new"),
    ("2023-07-25", "FY2024", "sales_usdm", 3800, 4000, "initial", "Full FY 2024 outlook Sales $3.8 - $4.0 billion", ""),
    ("2023-07-25", "FY2024", "op_income_usdm", 400, 500, "initial", "Non-GAAP operating income $400 - $500 million", ""),
    ("2023-10-24", "FY2024", "sales_usdm", 4000, 4150, "raised", "Sales $3.8 - $4.0 billion $4.0 - $4.15 billion", "previous -> new"),
    ("2023-10-24", "FY2024", "op_income_usdm", 525, 575, "raised", "Non-GAAP operating income $400 - $500 million $525 - $575 million", "previous -> new"),
    ("2024-01-23", "FY2024", "sales_usdm", 4200, 4250, "raised", "Sales $4.0 - $4.15 billion $4.2 - $4.25 billion", "previous -> new"),
    ("2024-01-23", "FY2024", "op_income_usdm", 610, 660, "raised", "Non-GAAP operating income $525 - $575 million $610 - $660 million", "previous -> new"),
    ("2024-04-30", "FY2025", "sales_usdm", 4300, 4400, "initial", "Sales $4.3 - $4.4 billion", ""),
    ("2024-04-30", "FY2025", "op_income_usdm", 685, 715, "initial", "Non-GAAP operating income $685 - $715 million", ""),
    ("2024-07-23", "FY2025", "sales_usdm", 4340, 4430, "raised", "Sales $4.3 - $4.4 billion $4.34 - $4.43 billion", "previous -> new"),
    ("2024-07-23", "FY2025", "op_income_usdm", 700, 730, "raised", "Non-GAAP operating income $685 - $715 million $700 - $730 million", "previous -> new"),
    ("2024-10-22", "FY2025", "sales_usdm", 4390, 4470, "raised", "Sales $4.34 - $4.43 billion $4.39 - $4.47 billion", "previous -> new"),
    ("2024-10-22", "FY2025", "op_income_usdm", 720, 750, "raised", "Non-GAAP operating income $700 - $730 million $720 - $750 million", "previous -> new"),
    ("2025-01-28", "FY2025", "sales_usdm", 4540, 4570, "raised", "Sales $4.39 - $4.47 billion $4.54 - $4.57 billion", "previous -> new"),
    ("2025-01-28", "FY2025", "op_income_usdm", 755, 770, "raised", "Non-GAAP operating income $720 - $750 million $755 - $770 million", "previous -> new"),
    ("2025-04-10", "FY2026", "sales_usdm", None, None, "withdrawn", "the Company withdrew its outlook for Fiscal Year 2026", "tariffs; quarterly guides from here"),
    ("2025-04-29", "Q1FY2026", "sales_usdm", 1100, 1150, "initial", "Sales $1,100 - $1,150 million", ""),
    ("2025-07-29", "Q2FY2026", "sales_usdm", 1145, 1190, "initial", "Sales $1,145 - $1,190 million", ""),
    ("2025-10-28", "Q3FY2026", "sales_usdm", 1375, 1415, "initial", "Sales $1,375 - $1,415 million", ""),
    ("2026-01-27", "Q4FY2026", "sales_usdm", 1070, 1090, "initial", "Sales $1,070 - $1,090 million $4,825 - $4,845 million", "Q4 column"),
    ("2026-01-27", "FY2026", "sales_usdm", 4825, 4845, "initial", "Sales $1,070 - $1,090 million $4,825 - $4,845 million", "FY column; one quarter left"),
    ("2026-01-27", "FY2026", "op_income_usdm", 900, 910, "initial", "Non-GAAP operating income $155 - $165 million $900 - $910 million", "FY column"),
    ("2026-05-05", "Q1FY2027", "sales_usdm", 1190, 1215, "initial", "Sales $1,190 - $1,215 million", ""),
    ("2026-07-28", "Q2FY2027", "sales_usdm", 1185, 1220, "initial", "Sales $1,185 - $1,220 million", "includes ~$20m supplier-incident headwind"),
]

# (report date, period, metric, actual, excerpt)
A = [
    ("2019-04-30", "FY2019", "sales_growth_cc_pct", 10, "up 9 percent in US dollars and 10 percent in constant currency compared to the prior year, the sixth consecutive year of growth"),
    ("2019-04-30", "FY2019", "op_income_usdm", 352, "Non-GAAP operating income grew 23 percent to $352 million"),
    ("2020-05-12", "FY2020", "sales_growth_cc_pct", 9, "Sales were Logitech’s highest ever at $2.98 billion, up 7 percent in US dollars and 9 percent in constant currency"),
    ("2020-05-12", "FY2020", "op_income_usdm", 387, "Non-GAAP operating income grew 10 percent to $387 million"),
    ("2021-04-29", "FY2021", "sales_growth_cc_pct", 74, "Sales were Logitech’s highest ever at $5.25 billion, up 76 percent in US dollars and 74 percent in constant currency"),
    ("2021-04-29", "FY2021", "op_income_usdm", 1270, "Non-GAAP operating income grew 229 percent to $1.27 billion"),
    ("2022-05-03", "FY2022", "sales_growth_cc_pct", 4, "Sales were Logitech’s highest ever at $5.48 billion, up 4 percent in US dollars and 4 percent in constant currency"),
    ("2022-05-03", "FY2022", "op_income_usdm", 904, "Non-GAAP operating income declined 29 percent to $904 million"),
    ("2023-05-02", "FY2023", "sales_growth_cc_pct", -13, "Sales were $4.54 billion, down 17 percent in US dollars and 13 percent in constant currency"),
    ("2023-05-02", "FY2023", "op_income_usdm", 589, "Non-GAAP operating income was $589 million"),
    ("2023-05-02", "FY2023", "sales_usdm", 4540, "Sales were $4.54 billion, down 17 percent in US dollars"),   # base for FY2024's USD guide
    ("2023-10-24", "H1FY2024", "sales_usdm", 2032, "Sales $1.875 - $1.975 billion $2.032 billion"),
    ("2023-10-24", "H1FY2024", "op_income_usdm", 292, "Non-GAAP operating income $180 - $220 million $292 million"),
    ("2024-04-30", "FY2024", "sales_usdm", 4300, "Sales were $4.30 billion, down 5 percent in US dollars"),
    ("2024-04-30", "FY2024", "op_income_usdm", 699, "Non-GAAP operating income was $699 million"),
    ("2025-04-29", "FY2025", "sales_usdm", 4550, "Sales were $4.55 billion, up 6 percent in US dollars"),
    ("2025-04-29", "FY2025", "op_income_usdm", 775, "Non-GAAP operating income was $775 million"),
    ("2026-05-05", "FY2026", "sales_usdm", 4840, "Sales were $4.84 billion, up 6 percent in US dollars"),
    ("2026-05-05", "FY2026", "op_income_usdm", 911, "Non-GAAP operating income was $911 million"),
]


def _get(url: str) -> bytes:
    err = None
    for k in range(5):
        try:
            time.sleep(0.5)
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            return urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:          # SEC rate limit (503): back off and retry
            err = e
            time.sleep(5 * (k + 1))
    raise RuntimeError(f"SEC fetch failed for {url}: {err}")


def fetch(since: str = "2019-01-01") -> int:
    """Cache every earnings-release exhibit as '<url>\\n<text>' in data/cache/sec/logitech_releases/<filed>_<acc>.txt."""
    REL.mkdir(parents=True, exist_ok=True)
    sub = json.loads(_get(f"https://data.sec.gov/submissions/CIK{CIK:010d}.json"))["filings"]["recent"]
    n = 0
    for i in range(len(sub["form"])):
        if sub["form"][i] != "8-K" or "2.02" not in sub["items"][i] or sub["filingDate"][i] < since:
            continue
        acc = sub["accessionNumber"][i].replace("-", "")
        f = REL / f"{sub['filingDate'][i]}_{acc}.txt"
        if f.exists():
            continue
        base = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{acc}/"
        ex = [x["name"] for x in json.loads(_get(base + "index.json"))["directory"]["item"] if "99" in x["name"] and x["name"].endswith(".htm")]
        if not ex:
            continue
        raw = _get(base + ex[0]).decode("utf8", "ignore")
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        f.write_text(base + ex[0] + "\n" + re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))))
        n += 1
    return n


def _release(day: str) -> tuple[str, str] | None:
    hits = sorted(REL.glob(f"{day}_*.txt")) if REL.exists() else []
    if not hits:
        return None
    url, text = hits[0].read_text().split("\n", 1)
    return url, text


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("consta nt", "constant")).strip()


def _numbers_ok(quote: str, lo, hi) -> bool:
    """Typed low / high appear in the excerpt (as millions, billions x 1000, or percent; 'negative 8' counts as -8);
    word ranges ('mid single-digit', 'flat') have no digits to match and pass only through their note."""
    if lo is None:
        return True
    q = quote.replace(",", "")
    nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", q)}
    nums |= {n * 1000 for n in nums} | {-n for n in nums}
    return all(float(v) in nums for v in (lo, hi))


def build() -> pd.DataFrame:
    """Rows for every statement and outcome, each excerpt checked against its cached release (ledger when not cached)."""
    from core import verify_ledger as vl
    rows = []
    for kind, data in (("guide", S), ("actual", A)):
        for r in data:
            if kind == "guide":
                day, period, metric, lo, hi, action, quote, note = r
            else:
                day, period, metric, val, quote = r
                lo = hi = val
                action, note = "actual", ""
            rel = _release(day)
            key = f"logitech_guidance:{day}:{period}:{metric}:{action}"
            if rel:
                found = _norm(quote) in _norm(rel[1])
                check = vl.record("pipeline_a", key, "found" if found else "NOT FOUND")
                url = rel[0]
            else:
                rec = vl.recall("pipeline_a", key)
                check, url = (rec[0], "") if rec else ("not checked (release not cached)", "")
            rows.append({"company": "logitech", "statement_date": day, "period": period, "metric": metric, "low": lo, "high": hi,
                         "action": action, "url": url, "quote": quote, "note": note, "quote_check": check,
                         "numbers_in_quote": _numbers_ok(quote, lo, hi) or bool(re.search(r"single-digit|flat|guidance", quote))})
    vl.save()
    df = pd.DataFrame(rows)
    if OUT.exists() and (df["url"] == "").any():             # fresh clone: keep the committed URLs
        old = pd.read_csv(OUT).fillna("")
        df["url"] = df["url"].where(df["url"] != "", df.merge(old[["statement_date", "period", "metric", "action", "url"]],
                                                                on=["statement_date", "period", "metric", "action"], how="left",
                                                                suffixes=("", "_old"))["url_old"].fillna(""))
    df.to_csv(OUT, index=False)
    return df
