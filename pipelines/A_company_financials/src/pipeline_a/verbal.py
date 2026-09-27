"""Grade-C data: verbal metrics from earnings calls and report commentary.

data/raw/verbal_metrics.csv holds one row per verbal data point — company, quarter, metric, the value we coded,
the phrase it rests on, the source URL, a grade (always C), and an is_estimate flag when the call gave direction
but not magnitude. This module (1) fetches each source (transcript page, PDF, or cached filing) and checks that
the quoted phrase occurs in it, writing found / not_found / fetch_failed back into the `verified` column, and
(2) asserts that the values in the company CSVs match this table, so the grade-C cells cannot drift from their
evidence. Transcript sites often block automated fetches; a `fetch_failed` row is a to-do for a manual check,
not a failure of the data.
"""
from __future__ import annotations

import re
import time
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

from .paths import ROOT, DATA_RAW, DATA_PROC, CACHE as _CACHE, MANUAL
from .manifest import COMPANIES
from .filings import extract_text, CACHE as FILING_CACHE

VERBAL = DATA_RAW / "verbal_metrics.csv"
CACHE = _CACHE / "verbal"
UA = "Mozilla/5.0 (compatible; supply-chain-case-study; siqizhu00@gmail.com)"

# verbal metric -> company csv column (the grade-C columns; every non-null cell needs a row in verbal_metrics.csv)
COLUMN = {"sellthrough_minus_sellin_pts": "sellthrough_minus_sellin_pts", "dist_inventory_state": "dist_inventory_state",
          "enterprise_sellout_minus_sellin_pts": "enterprise_sellout_minus_sellin_pts",
          "endpoint_gb_yoy_pct": "endpoint_gb_yoy_pct", "ces_yoy_pct": "ces_yoy_pct"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[‘’“”]", "'", s)).lower()


def _fetch(url: str, download: bool = True) -> Path | None:
    """Cached copy of the source page/PDF under data/cache/verbal/; download=False uses the cache only."""
    CACHE.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:]
    ext = ".pdf" if url.lower().endswith(".pdf") else ".htm"
    f = CACHE / f"{name}{ext}"
    if f.exists() and f.stat().st_size > 2_000:
        return f
    if not download:
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=60) as r:
            f.write_bytes(r.read())
        time.sleep(0.5)
        return f if f.stat().st_size > 2_000 else None
    except Exception:
        return None


MANUAL_DIR = MANUAL   # drop transcript text/PDF here as <company>_<quarter>.txt|.pdf|.htm


def _manual_doc(company: str, quarter: str) -> Path | None:
    for ext in (".txt", ".pdf", ".htm"):
        f = MANUAL_DIR / f"{company}_{quarter}{ext}"
        if f.exists():
            return f
    return None


def _cached_filing(company: str, quarter: str) -> Path | None:
    """The quarterly report already downloaded by fetch_all (NewsWeb PDF, IR PDF or 8-K exhibit) for this quarter."""
    for ext in (".pdf", ".htm"):
        f = FILING_CACHE / company / f"{quarter}{ext}"
        if f.exists():
            return f
    return None


def _contains(doc: Path, quote: str) -> bool | None:
    try:
        text = doc.read_text(errors="ignore") if doc.suffix == ".txt" else extract_text(doc)
        return _norm(quote) in _norm(text)
    except Exception:
        return None


def verify_verbal(fetch: bool = True) -> pd.DataFrame:
    """Result codes written to `verified`:
        found_manual          a human opened the url, found the quote and wrote 'confirmed' in `manual_check`
                              (the verifier never overwrites this; write 'rejected' if the quote/value is wrong)
        found_manual_file     quote occurs in a transcript you saved as data/manual/<company>_<quarter>.txt (or .pdf)
        found                 quote occurs in the cited source (fetched and cached under data/cache/verbal/)
        found_in_filing       cited page could not be fetched or did not contain it, but the quarter's cached
                              report (data/cache/filings/<company>/<quarter>.pdf) does — same words, primary source
        not_found             source readable, quote absent in both  -> fix the quote or the value
        fetch_failed          site blocks automated fetch and no cached report has the words -> manual check
    """
    v = pd.read_csv(VERBAL, dtype={"verified": str, "verified_on": str, "manual_check": str}).fillna({"verified": "", "verified_on": "", "manual_check": ""})
    if "manual_check" not in v.columns:
        v["manual_check"] = ""
    today = date.today().isoformat()
    for i, r in v.iterrows():
        quote = str(r["quote"])
        if str(r["manual_check"]).strip().lower() in ("confirmed", "rejected"):
            v.loc[i, "verified"] = "found_manual" if r["manual_check"].strip().lower() == "confirmed" else "not_found"
            continue
        man = _manual_doc(r["company"], r["quarter"])
        f = _fetch(r["source_url"], download=fetch)
        hit = _contains(f, quote) if f is not None else None
        if man is not None and _contains(man, quote):
            res = "found_manual_file"
        elif hit:
            res = "found"
        else:
            local = _cached_filing(r["company"], r["quarter"])
            if local is not None and _contains(local, quote):
                res = "found_in_filing"
            elif f is None:
                res = "fetch_failed"
            elif hit is None:
                res = "unreadable"
            else:
                res = "not_found"
        v.loc[i, "verified"] = res
        v.loc[i, "verified_on"] = today
    v.to_csv(VERBAL, index=False)
    return v


# which grade-C columns each company CSV carries
GRADE_C_COLUMNS = {"logitech": ["sellthrough_minus_sellin_pts"], "nordic": ["dist_inventory_state"],
                   "gn": ["enterprise_sellout_minus_sellin_pts"], "tdsynnex": ["endpoint_gb_yoy_pct"], "ingram": ["ces_yoy_pct"]}


def uncited_cells() -> pd.DataFrame:
    """Reverse check: grade-C cells in the company CSVs that have NO evidence row in verbal_metrics.csv.
    These are carried-forward states or values coded from research notes without a retained quote — effectively
    grade D. They are listed in the validation report and in data/processed/verbal_uncited.csv."""
    v = pd.read_csv(VERBAL)
    rows = []
    for c, cols in GRADE_C_COLUMNS.items():
        raw = pd.read_csv(DATA_RAW / COMPANIES[c]["raw_csv"])
        for col in cols:
            if col not in raw.columns:
                continue
            cited = set(v[(v["company"] == c) & (v["metric"] == col)]["quarter"])
            for _, r in raw[raw[col].notna()].iterrows():
                if r["quarter"] not in cited:
                    rows.append({"company": c, "quarter": r["quarter"], "metric": col, "csv_value": r[col]})
    out = pd.DataFrame(rows, columns=["company", "quarter", "metric", "csv_value"])
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(DATA_PROC / "verbal_uncited.csv", index=False)
    return out


def check_consistency() -> pd.DataFrame:
    """Every verbal value must equal the cell in the company CSV it feeds (and vice-versa for flagged cells)."""
    v = pd.read_csv(VERBAL)
    rows = []
    for c in v["company"].unique():
        raw = pd.read_csv(DATA_RAW / COMPANIES[c]["raw_csv"]).set_index("quarter")
        for _, r in v[v["company"] == c].iterrows():
            col = COLUMN[r["metric"]]
            cell = raw.loc[r["quarter"], col] if (r["quarter"] in raw.index and col in raw.columns) else None
            ok = cell is not None and pd.notna(cell) and float(cell) == float(r["value"])
            rows.append({"company": c, "quarter": r["quarter"], "metric": r["metric"], "verbal_value": r["value"],
                         "csv_value": cell, "consistent": ok})
    out = pd.DataFrame(rows)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(DATA_PROC / "verbal_consistency.csv", index=False)
    return out
