"""Nordic's guidance history before the hand-typed quarterly series starts (decision F32): every revenue and
gross-margin guidance statement from the Q2 2017 report to the Q4 2020 report, and the half-year outcomes.

Two regimes, kept apart because they are different horizons:
  half-year   H1 2017 - H2 2018: a revenue range for the coming half, reiterated or cut in between (the Dec 2018 cut is
              Nordic's only guidance cut on record). Scored as a separate record; never pooled with quarterly beats.
  quarterly   from the Q4 2018 report (first guide: Q1 2019). The initial statement is the one the model scores
              (actual / guide mid - 1); the two 2020 intra-quarter raises are logged so the beat against the LAST guide
              before the print can be shown beside it (pitfall P130).

Every row carries the cached document it rests on (a NewsWeb report key such as 2019Q2, or msg:<messageId> for an
announcement without a report) and a verbatim excerpt; `build()` checks each excerpt word for word against that
document and records the result in the verification ledger, so a fresh clone shows the recorded check. Values are
typed from the excerpt; the excerpt check guards the typing, and `consistency()` checks that every quarterly initial
guide equals the guide cells in data/raw/nordic_quarterly.csv.
Output: data/raw/nordic_guidance_history.csv.
"""
from __future__ import annotations

import re

import pandas as pd

from .filings import extract_text, _doc
from .newsweb import announcement_path
from .paths import DATA_RAW, DATA_PROC

OUT = DATA_RAW / "nordic_guidance_history.csv"
INDEX = DATA_PROC / "newsweb_nordic_index.csv"

# (statement date, period, metric, low, high, action, source key, excerpt, note)
S = [
    ("2017-06-09", "H1 2017", "revenue_usdm", 100, 107, "reiterated", "msg:429279", "Nordic maintains its H1 2017 guidance on revenue range of MUSD 100 to 107",
     "first stated at the Q4 2016 presentation; that report is an image-only PDF, so the mid-quarter update is the earliest checkable statement"),
    ("2017-07-13", "H2 2017", "revenue_usdm", 120, 130, "initial", "2017Q2", "a solid coverage for our guided range of MUSD 120 - 130 in 2H 2017", ""),
    ("2017-10-17", "H2 2017", "revenue_usdm", 120, 130, "reiterated", "2017Q3", "contributes to a solid coverage for maintaining our guided range of MUSD 120 - 130 in 2H 2017", ""),
    ("2018-02-15", "H1 2018", "revenue_usdm", 123, 133, "initial", "2017Q4", "a total revenue guidance of MUSD 123 in the lower end and MUSD 133 in the higher end for 1H 2018", ""),
    ("2018-04-17", "H1 2018", "revenue_usdm", 123, 133, "reiterated", "2018Q1", "We maintain the H1 2018 guidance range of MUSD 123 to 133 revenue", ""),
    ("2018-07-12", "H2 2018", "revenue_usdm", 150, 160, "initial", "2018Q2", "we provide a revenue guidance range of MUSD 150 to MUSD 160 in H2 2018", ""),
    ("2018-12-03", "H2 2018", "revenue_usdm", 140, 140, "lowered", "msg:464913", "This implies a revenue for the second half of 2018 of around USD 140 million",
     "full year 2018 cut to 'around USD 270 million' on US-China trade tensions; 'around' = point guide; the only cut on record"),
    ("2019-02-05", "2019Q1", "revenue_usdm", 50, 55, "initial", "2018Q4", "Based on current backlog, guidance for Q1 2019 revenue is MUSD 50-55", "first quarterly revenue guide"),
    ("2019-02-05", "2019Q1", "gm_pct", 50, 50, "initial", "2018Q4", "maintaining gross margin of around 50% for Q1 2019", ""),
    ("2019-04-24", "2019Q2", "revenue_usdm", 69, 74, "initial", "2019Q1", "guidance for Q2 2019 revenue is MUSD 69-74", ""),
    ("2019-04-24", "2019Q2", "gm_pct", 50, 50, "initial", "2019Q1", "Nordic maintaining its gross margin of around 50% for Q2 2019", ""),
    ("2019-07-11", "2019Q3", "revenue_usdm", 78, 83, "initial", "2019Q2", "Based on the current backlog, guidance for Q3 2019 revenue is MUSD 78-83", ""),
    ("2019-07-11", "2019Q3", "gm_pct", 50, 50, "initial", "2019Q2", "Nordic maintaining its gross margin of around 50% for Q3 2019", ""),
    ("2019-10-22", "2019Q4", "revenue_usdm", 75, 79, "initial", "2019Q3", "Nordic has issued a revenue guidance of USD 75-79 million for Q4 2019", ""),
    ("2019-10-22", "2019Q4", "gm_pct", 50, 50, "initial", "2019Q3", "a gross margin of around 50% also for Q4 2019", ""),
    ("2020-02-07", "2020Q1", "revenue_usdm", 64, 71, "initial", "2019Q4", "revenue of USD 64-71 million for Q1 2020, a wider range",
     "order push-outs and the first coronavirus disruptions"),
    ("2020-02-07", "2020Q1", "gm_pct", 50, 50, "initial", "2019Q4", "we expect a gross margin level of 50% in Q1 2020", ""),
    ("2020-04-21", "2020Q2", "revenue_usdm", 75, 85, "initial", "2020Q1", "the company guides for a total revenue level of USD 75-85 million for Q2 2020", ""),
    ("2020-04-21", "2020Q2", "gm_pct", 50, 50, "initial", "2020Q1", "The gross margin is expected at around 50% in Q2 2020", ""),
    ("2020-07-03", "2020Q2", "revenue_usdm", 86, 88, "raised", "msg:509236", "now expects revenue for the quarter of USD 86-88 million", "pre-announcement ten days before the report (P130)"),
    ("2020-07-13", "2020Q3", "revenue_usdm", 95, 105, "initial", "2020Q2", "guide for a total revenue level of USD 95-105 million for Q3 2020", ""),
    ("2020-07-13", "2020Q3", "gm_pct", 50, 51, "initial", "2020Q2", "The company expects a gross margins level around 50%-51% for Q3 2020", ""),
    ("2020-09-04", "2020Q3", "revenue_usdm", 112, 118, "raised", "msg:512906", "the company increases its revenue guidance for the third quarter 2020 to USD 112-118 million", "pre-announcement six weeks before the report (P130)"),
    ("2020-10-20", "2020Q4", "revenue_usdm", 115, 125, "initial", "2020Q3", "the current backlog allows Nordic to guide for a total revenue level of USD 115-125 million for the fourth quarter", ""),
    ("2020-10-20", "2020Q4", "gm_pct", 51, 52, "initial", "2020Q3", "Nordic expects a gross margin level of 51%-52% for Q4 2020", ""),
    ("2021-02-04", "2021Q1", "revenue_usdm", 130, 140, "initial", "2020Q4", "guide for a revenue level of USD 130- 140 million for Q1 2021", "the guide the hand-typed series had left blank (P129)"),
    ("2021-02-04", "2021Q1", "gm_pct", 50, 51, "initial", "2020Q4", "For Q1 2021 the company forecasts a gross margin level of 50%-51%", ""),
]

# half-year outcomes: the two quarterly income-statement totals (USD thousand) that make each half, each checked in its report
# (the 2017 reports print thousands with a dot, '65.650'; the text extractor splits the neighbouring column, so the fragment stops at the total)
A = [
    ("H1 2017", [("msg:425330", "Reported First Quarter 2017 revenues of MUSD 47.3", 47300), ("2017Q2", "Total 58 651 52 712", 58651)]),
    ("H2 2017", [("2017Q3", "Total 65.650", 65650), ("2017Q4", "Total 64.366", 64366)]),
    ("H1 2018", [("2018Q1", "Total Revenue 60 125", 60125), ("2018Q2", "Total Revenue 71 158", 71158)]),
    ("H2 2018", [("2018Q3", "Total Revenue 78 725", 78725), ("2018Q4", "Total Revenue 61 126", 61126)]),
]


def announcement_ids() -> list[int]:
    """NewsWeb message ids of the announcements (no report attached) that carry a statement or an outcome here."""
    keys = [r[6] for r in S] + [src for _, parts in A for src, _, _ in parts]
    return sorted({int(k[4:]) for k in keys if k.startswith("msg:")})


def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s.replace("–", "-").replace("’", "'")).strip()
    return re.sub(r"\s*-\s*", "-", s)


def _text(source_key: str) -> tuple[str | None, str]:
    """(normalised text, citation url) of a cached report key or msg:<id> announcement; (None, '') when not cached."""
    if source_key.startswith("msg:"):
        f = announcement_path(int(source_key[4:]))
        if not f.exists():
            return None, ""
        url, _, body = f.read_text().split("\n", 2)
        return _norm(body), url
    doc = _doc("nordic", source_key)
    if doc is None:
        return None, ""
    url = ""
    if INDEX.exists():
        ix = pd.read_csv(INDEX, dtype=str).set_index("key")["url"]
        url = ix.get(source_key, "")
    return _norm(extract_text(doc)), url


def _check(vl, key: str, source_key: str, quote: str) -> tuple[str, str]:
    text, url = _text(source_key)
    if text is None:
        rec = vl.recall("pipeline_a", key)
        return (rec[0] if rec else "not checked (document not cached)"), ""
    return vl.record("pipeline_a", key, "found" if _norm(quote) in text else "NOT FOUND"), url


def build() -> pd.DataFrame:
    from core import verify_ledger as vl
    rows = []
    for day, period, metric, lo, hi, action, src, quote, note in S:
        key = f"nordic_guidance:{day}:{period}:{metric}:{action}"
        check, url = _check(vl, key, src, quote)
        nums = {float(x) for x in re.findall(r"\d+(?:\.\d+)?", quote)}
        rows.append({"company": "nordic", "statement_date": day, "period": period, "metric": metric, "low": lo, "high": hi, "action": action,
                     "source_key": src, "url": url, "quote": quote, "note": note, "quote_check": check,
                     "numbers_in_quote": float(lo) in nums and float(hi) in nums})
    for period, parts in A:
        checks, urls = [], []
        for src, quote, _ in parts:
            c, u = _check(vl, f"nordic_guidance:actual:{period}:{src}", src, quote)
            checks.append(c); urls.append(u)
        total = round(sum(v for _, _, v in parts) / 1000, 1)
        bad = [c for c in checks if not c.startswith("found")]           # a ledger-labelled 'found (recorded ...)' still counts
        rows.append({"company": "nordic", "statement_date": "", "period": period, "metric": "revenue_usdm", "low": total, "high": total,
                     "action": "actual", "source_key": "|".join(s for s, _, _ in parts), "url": "|".join(urls) if any(urls) else "",
                     "quote": " | ".join(q for _, q, _ in parts), "note": "sum of the two quarterly income-statement totals",
                     "quote_check": "; ".join(bad) if bad else checks[0], "numbers_in_quote": True})
    vl.save()
    df = pd.DataFrame(rows)
    if OUT.exists() and (df["url"] == "").any():             # fresh clone: keep the committed citations
        old = pd.read_csv(OUT, dtype=str).fillna("")
        m = df.merge(old[["statement_date", "period", "metric", "action", "url"]], on=["statement_date", "period", "metric", "action"],
                     how="left", suffixes=("", "_old"))
        df["url"] = df["url"].where(df["url"] != "", m["url_old"].fillna(""))
    df.to_csv(OUT, index=False)
    return df


def half_year_record(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each half-year guide: initial range, last range before the period closed, outcome and the error against both."""
    d = df if df is not None else pd.read_csv(OUT)
    h = d[d["period"].str.startswith("H")]
    rows = []
    for period, g in h.groupby("period", sort=False):
        guides, act = g[g["action"] != "actual"].sort_values("statement_date"), g[g["action"] == "actual"]
        if guides.empty or act.empty:
            continue
        first, last, a = guides.iloc[0], guides.iloc[-1], float(act["low"].iloc[0])
        fm, lm = (first["low"] + first["high"]) / 2, (last["low"] + last["high"]) / 2
        rows.append({"period": period, "first_low": first["low"], "first_high": first["high"], "last_low": last["low"], "last_high": last["high"],
                     "actual_usdm": a, "error_vs_first_pct": (a / fm - 1) * 100, "error_vs_last_pct": (a / lm - 1) * 100,
                     "lowered": bool((guides["action"] == "lowered").any())})
    return pd.DataFrame(rows)


def quarterly_guides(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per guided quarter: the initial revenue guide (the one the model scores) and the last one before the print."""
    d = df if df is not None else pd.read_csv(OUT)
    q = d[(d["metric"] == "revenue_usdm") & d["period"].str.match(r"^\d{4}Q\d$")].sort_values("statement_date")
    rows = []
    for period, g in q.groupby("period", sort=False):
        first, last = g.iloc[0], g.iloc[-1]
        rows.append({"quarter": period, "initial_low": first["low"], "initial_high": first["high"], "last_low": last["low"], "last_high": last["high"],
                     "raised_before_print": bool((g["action"] == "raised").any())})
    return pd.DataFrame(rows)


def consistency(df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Every quarterly initial guide here == the guide cells of nordic_quarterly.csv (gm: midpoint of the stated range)."""
    d = df if df is not None else pd.read_csv(OUT)
    n = pd.read_csv(DATA_RAW / "nordic_quarterly.csv").set_index("quarter")
    rows = []
    for _, r in d[(d["action"] == "initial") & d["period"].str.match(r"^\d{4}Q\d$")].iterrows():
        if r["period"] not in n.index:
            rows.append({"quarter": r["period"], "metric": r["metric"], "consistent": False, "detail": "no row in nordic_quarterly.csv"})
            continue
        row = n.loc[r["period"]]
        if r["metric"] == "revenue_usdm":
            ok = row["guide_low_usdm"] == r["low"] and row["guide_high_usdm"] == r["high"]
            detail = f"csv {row['guide_low_usdm']:g}-{row['guide_high_usdm']:g} vs quote {r['low']:g}-{r['high']:g}"
        else:
            ok = abs(row["guide_gm_pct"] - (r["low"] + r["high"]) / 2) < 1e-9
            detail = f"csv {row['guide_gm_pct']:g} vs quote mid {(r['low'] + r['high']) / 2:g}"
        rows.append({"quarter": r["period"], "metric": r["metric"], "consistent": bool(ok), "detail": detail})
    return pd.DataFrame(rows)
