"""Nordic and GN: download the filing PDFs listed in manifest.FILINGS, extract their text, and verify that every
figure in the hand-collected CSV appears in the corresponding filing.

No parsing of tables is attempted (fragile and unnecessary): the check is "does the exact figure we typed occur
in the report for that quarter". Output: data/processed/filing_verification.csv with found / not_found /
no_filing per (company, quarter, column).

Nordic's web server returns HTTP 403 to non-browser clients on some networks. If a download fails, open the URL in
a browser, save the PDF as data/cache/filings/<company>/<key>.pdf, and re-run — the verifier picks it up.
"""
from __future__ import annotations

import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .paths import ROOT, DATA_RAW, DATA_PROC, CACHE as _CACHE, MANUAL
from .manifest import COMPANIES, FILINGS, VERIFY_COLUMNS

CACHE = _CACHE / "filings"
UA = "Mozilla/5.0 (compatible; supply-chain-case-study; siqizhu00@gmail.com)"
SEC_UA = "supply-chain-case-study (public research) siqizhu00@gmail.com"   # SEC requires a descriptive UA


def _ext(url: str) -> str:
    return ".htm" if url.lower().split("?")[0].endswith((".htm", ".html")) else ".pdf"


def _doc(c: str, key: str) -> Path | None:
    for ext in (".pdf", ".htm"):
        p = CACHE / c / f"{key}{ext}"
        if p.exists() and p.stat().st_size > 5_000:
            return p
    return None


def download_all(companies=("nordic", "gn", "logitech", "ingram", "tdsynnex"), refresh: bool = False) -> pd.DataFrame:
    rows = []
    for c in companies:
        d = CACHE / c
        d.mkdir(parents=True, exist_ok=True)
        for key, url in FILINGS.get(c, {}).items():
            f = d / f"{key}{_ext(url)}"
            status = "cached"
            if refresh or not (f.exists() and f.stat().st_size > 5_000):
                try:
                    ua = SEC_UA if "sec.gov" in url else UA
                    req = urllib.request.Request(url, headers={"User-Agent": ua})
                    with urllib.request.urlopen(req, timeout=90) as r:
                        f.write_bytes(r.read())
                    status = "downloaded"
                    time.sleep(0.5)
                except Exception as e:  # 403 / timeout / bad URL
                    status = f"failed: {str(e)[:60]}"
            rows.append({"company": c, "key": key, "url": url, "path": str(f), "status": status,
                         "bytes": f.stat().st_size if f.exists() else 0})
    out = pd.DataFrame(rows)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(DATA_PROC / "filing_downloads.csv", index=False)
    return out


def extract_text(doc: Path) -> str:
    """PDF via pdfplumber; HTML (SEC exhibits) via tag stripping. Cached beside the file as .txt."""
    txt = doc.with_suffix(doc.suffix + ".txt")
    if txt.exists() and txt.stat().st_mtime >= doc.stat().st_mtime:
        return txt.read_text()
    if doc.suffix == ".htm":
        import html
        raw = doc.read_text(errors="ignore")
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = re.sub(r"</(td|th|tr|p|div|li|br)>", " \n", raw, flags=re.I)
        text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
        text = re.sub(r"[ \t\xa0]+", " ", text)
    else:
        import pdfplumber
        parts = []
        with pdfplumber.open(doc) as d:
            for page in d.pages:
                parts.append(page.extract_text() or "")
        text = "\n".join(parts)
    txt.write_text(text)
    return text


def _patterns(v: float) -> list[str]:
    """Regexes for the number formats seen in these reports.
    GN (DKK m, integers):   2,171 | 2171 | 2 171
    Nordic (USD m, 1 dp):   218.6  and the USD-thousands tables: 218 6xx / 218,6xx (e.g. 'Consumer 94 312' = 94.3m)
    """
    if float(v).is_integer():
        i = int(v)
        return [re.escape(f"{i:,}"), re.escape(str(i)), re.escape(f"{i:,}".replace(",", " "))]
    return [re.escape(f"{v:.1f}")]


_NUM = re.compile(r"(?<![\d.,])(\d{1,3}(?:[ ,]\d{3})+|\d+)(?:\.(\d+))?(?![\d])")


def _numbers(text: str):
    """Every number in the text, cached per document, as floats (separators removed)."""
    key = id(text)
    if key not in _NUM_CACHE:
        vals = []
        for whole, dec in _NUM.findall(text):
            try:
                vals.append(float(whole.replace(",", "").replace(" ", "") + ("." + dec if dec else "")))
            except ValueError:
                pass
            # Nordic thousands tables put several numbers in a row ('Consumer 111 558 111 316'): the greedy match
            # swallows them as one; add every contiguous sub-run of 3-digit groups as a candidate too
            if " " in whole:
                toks = whole.split(" ")
                for i in range(len(toks)):
                    for k in range(i + 1, len(toks) + 1):
                        if (i, k) != (0, len(toks)) and len(toks[i]) <= 3 and all(len(t) == 3 for t in toks[i + 1:k]):
                            vals.append(float("".join(toks[i:k])))
        _NUM_CACHE[key] = (text, vals)
    return _NUM_CACHE[key][1]


_NUM_CACHE: dict = {}


def _in(text: str, v: float) -> bool:
    """True if the CSV value appears in the document either as printed (218.6 / 2,171) or as a thousands-table
    entry that rounds to it (Nordic '95 257' -> 95.3; Logitech '1,227,234' -> 1227.2; Ingram '11,763,417' -> 11763)."""
    v = float(v)
    if any(re.search(r"(?<![\d.,])" + p + r"(?![\d])", text) for p in _patterns(v)):
        return True
    nd = 0 if v.is_integer() else 1
    target = round(v, nd)
    nums = _numbers(text)
    if any(n == v for n in nums if n >= 1000):                       # printed with a space separator and decimals: '1 252.6' (P132)
        return True
    return any(round(n / 1000, nd) == target for n in nums if n >= 1000)


def _later_filings(c: str, q: str) -> list[Path]:
    """Filings in which a restated comparative for quarter q can legitimately appear: the four following
    quarterly reports and the next two annual reports (taxonomy changes restate two years back)."""
    y, n = int(q[:4]), int(q[-1])
    keys = []
    for k in range(1, 5):
        n2 = n + k; keys.append(f"{y + (n2 - 1) // 4}Q{(n2 - 1) % 4 + 1}")
    keys += [f"AR{y}", f"AR{y + 1}"]
    return [p for p in (_doc(c, k) for k in keys) if p]


GUIDE_COLS = ("guide_low_usdm", "guide_high_usdm", "guide_gm_pct")   # published with the PREVIOUS quarter's report


def _derived(c: str, k: str, q: str, r) -> bool:
    """Cells that are our own arithmetic or estimates, not reported figures: skipped (they cannot be 'found')."""
    if int(r.get("is_estimate", 0) or 0) == 1 and k in ("short_range_usdm", "consumer_usdm", "ind_health_usdm"):
        return True
    if c == "nordic" and k == "ind_health_usdm" and q < "2025Q1":   # Industrial + Healthcare summed by us pre-2025
        return True
    if c == "nordic" and k == "other_tech_usdm":                    # ASIC + consulting summed by us
        return True
    return False


def _prev_quarter(q: str) -> str:
    p = pd.Period(q, "Q") - 1
    return str(p)


def _guide_in(text: str, k: str, v: float) -> bool:
    """A guide range bound as printed ('130-140', 'MUSD 50-55'); a margin guide typed as the midpoint of a stated range
    ('50%-51%' -> 50.5) counts when both bounds are printed."""
    if k == "guide_gm_pct":
        pct = lambda x: re.search(r"(?<![\d.])" + re.escape(f"{x:g}") + r"\s?%", text) is not None   # noqa: E731  '50%', '50.5 %'
        return pct(v) if float(v).is_integer() else (pct(v - 0.5) and pct(v + 0.5))
    return _in(text, v)


def verify(companies=("nordic", "gn", "logitech", "ingram", "tdsynnex")) -> pd.DataFrame:
    rows = []
    for c in companies:
        raw = pd.read_csv(DATA_RAW / COMPANIES[c]["raw_csv"])
        cols = [k for k in VERIFY_COLUMNS[c] if k in raw.columns]
        for _, r in raw.iterrows():
            q = str(r["quarter"])
            # quarter's own document; else the annual report carrying the quarterly table (GN 2021-22, Q4s)
            pdf = _doc(c, q) or _doc(c, f"AR{q[:4]}") or _doc(c, f"AR{int(q[:4]) + 1}")
            for k in [k for k in cols if k in GUIDE_COLS]:       # the guide for q is published with the report of q-1
                v = r.get(k)
                if pd.isna(v):
                    continue
                prev = _doc(c, _prev_quarter(q))
                rows.append({"company": c, "quarter": q, "column": k, "value": v, "filing": prev.name if prev else None,
                             "result": "no_filing" if prev is None else ("found" if _guide_in(extract_text(prev), k, float(v)) else "not_found")})
            cols_here = [k for k in cols if k not in GUIDE_COLS]
            if pdf is None:
                for k in cols_here:
                    if pd.notna(r.get(k)):
                        rows.append({"company": c, "quarter": q, "column": k, "value": r[k], "result": "no_filing"})
                continue
            text = extract_text(pdf)
            for k in cols_here:
                v = r.get(k)
                if pd.isna(v) or _derived(c, k, q, r):
                    continue
                if _in(text, v):
                    rows.append({"company": c, "quarter": q, "column": k, "value": v, "result": "found", "filing": pdf.name})
                    continue
                # Restated values (new taxonomy, continuing ops) live in LATER filings: search those, newest first.
                hit = next((p for p in _later_filings(c, q) if _in(extract_text(p), v)), None)
                rows.append({"company": c, "quarter": q, "column": k, "value": v,
                             "result": "found_in_later_filing" if hit else "not_found", "filing": hit.name if hit else pdf.name})
    out = pd.DataFrame(rows)
    out.to_csv(DATA_PROC / "filing_verification.csv", index=False)
    return out
