"""Currency effects the companies disclose themselves, quote by quote (input to step 7 fx_update.py).

Logitech: each quarterly release states sales growth 'in US dollars' and 'in constant currency' (realised FX effect =
the difference), and each outlook states the guided growth in both (the FX effect the guide assumes). GN: each quarterly
report states '<x>% impact from the development in foreign exchange rates' on group revenue.

Extracted from the cached filings when present; data/raw/fx_effects_disclosed.csv is committed (with the sentence) so a
fresh clone needs no cache. Validation: every row's quote must be found verbatim in its cached document when the cache
exists (recorded in the verification ledger otherwise).
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
CACHE = ROOT / "pipelines" / "A_company_financials" / "data" / "cache" / "filings"
OUT = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "fx_effects_disclosed.csv"

LOGI_Q = re.compile(r"(up|down|increased|decreased)\s+(\d+)\s+percent in US dollars and\s+(up |down )?(\d+)\s+percent in constant "
                    r"currency,? compared to Q\d of the prior year")
LOGI_G = re.compile(r"Sales growth \(in US dollars, year over year\)\s*(-?\d+)%\s*-\s*(-?\d+)%\s*Sales growth \(in constant currency, "
                    r"year over year\)\s*(-?\d+)%\s*-\s*(-?\d+)%")
GN_Q = re.compile(r"(-?\s?\d+)\s?%\s+impact from the develop-?\s?ment in foreign exchange rates")


def _text(f: Path) -> str:
    return re.sub(r"\s+", " ", f.read_text(errors="ignore"))


def logitech_rows() -> list[dict]:
    rows = []
    for f in sorted((CACHE / "logitech").glob("20*.htm.txt")):
        q = pd.Period(f.name[:6], "Q")
        t = _text(f)
        m = LOGI_Q.search(t)
        if m:
            s = -1 if m.group(1) in ("down", "decreased") else 1
            s2 = -1 if (m.group(3) or "").strip() == "down" else (s if not m.group(3) else 1)
            usd, cc = s * int(m.group(2)), s2 * int(m.group(4))
            rows.append({"company": "logitech", "quarter": str(q), "kind": "realised", "scope": "group", "usd_growth_pct": usd, "cc_growth_pct": cc,
                         "fx_pts": usd - cc, "quote": m.group(0), "source": f"filings/logitech/{f.name[:-4]}"})
        g = LOGI_G.search(t)
        if g:                                                  # the outlook given with quarter q is for q + 1
            ul, uh, cl, ch = (int(x) for x in g.groups())
            rows.append({"company": "logitech", "quarter": str(q + 1), "kind": "guide_assumed", "scope": "group", "usd_growth_pct": (ul + uh) / 2,
                         "cc_growth_pct": (cl + ch) / 2, "fx_pts": (ul + uh) / 2 - (cl + ch) / 2, "quote": g.group(0),
                         "source": f"filings/logitech/{f.name[:-4]}"})
    return rows


def gn_rows() -> list[dict]:
    rows = []
    for f in sorted((CACHE / "gn").glob("20*.pdf.txt")):
        t = _text(f)
        m = GN_Q.search(t)
        if m:
            scope = "north_america" if "North America" in t[max(0, m.start() - 160):m.start()] else "group"
            rows.append({"company": "gn", "quarter": f.name[:6], "kind": "realised", "scope": scope, "usd_growth_pct": None,
                         "cc_growth_pct": None, "fx_pts": float(m.group(1).replace(" ", "")), "quote": m.group(0),
                         "source": f"filings/gn/{f.name[:-4]}"})
    return rows


def build(write: bool = True) -> pd.DataFrame:
    """Re-extract when the cache exists; otherwise return the committed table."""
    if not (CACHE / "logitech").exists():
        return pd.read_csv(OUT)
    d = pd.DataFrame(logitech_rows() + gn_rows())
    if write:
        d.to_csv(OUT, index=False)
    return d


def verify(d: pd.DataFrame) -> pd.DataFrame:
    """Each quote found verbatim in its cached document ('not cached' when the document is absent)."""
    out = []
    for r in d.itertuples():
        f = CACHE.parent / (str(r.source) + ".txt")
        out.append("not cached" if not f.exists() else ("found" if r.quote in _text(f) else "NOT FOUND"))
    return d.assign(quote_check=out)
