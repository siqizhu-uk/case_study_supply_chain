"""Distributor stock per part from findchips.com (Supplyframe), which aggregates the distributors' own feeds.

Digi-Key and Mouser return 403 to scripts; findchips serves the same feed data as structured table rows
(`data-distributor_name`, `data-stock`, `data-mfrpartnumber`, `data-price`). Which distributors appear varies with
the requesting region, so every row is kept and the series is built on the *authorized* subset (config/distributors.csv).
Grade D: a point-in-time scrape of an aggregator; becomes useful only as a series of dated snapshots.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date

import pandas as pd

from .fetch import fetch
from .paths import DISTRIBUTORS, PARTS

ROW = re.compile(r'<tr data-id="\d+" data-distributor_name="([^"]*)" data-mfr="([^"]*)" data-instock="([^"]*)" '
                 r'data-stock="([^"]*)" data-mfrpartnumber="([^"]*)" data-price="([^"]*)"')


def _stock(raw: str) -> tuple[float | None, str]:
    """'9817' -> 9817; 'Global - 9887' / 'Stock HK - 66000' -> sum of the numbers; '' -> None."""
    txt = re.sub(r"<[^>]+>", " ", html.unescape(raw))
    g = re.search(r"Global\s*-\s*(\d[\d,]*)", txt)          # element14: 'Local - 70  Global - 9887' -> the global pool
    if g:
        return float(g.group(1).replace(",", "")), txt.strip()
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", txt)]
    if not nums:
        return None, txt.strip()
    return float(sum(nums)) if len(nums) > 1 else float(nums[0]), txt.strip()   # Rutronik/ComSIT: sum of regional stocks


def _price(raw: str, currency_pref=("USD", "GBP", "EUR")) -> tuple[float | None, float | None, str]:
    try:
        tiers = json.loads(html.unescape(raw))
    except Exception:
        return None, None, ""
    if not tiers:
        return None, None, ""
    cur = tiers[0][1]
    by_qty = {int(q): float(p) for q, c, p in tiers if c == cur}
    p1 = by_qty.get(min(by_qty)) if by_qty else None
    p1k = min((p for q, p in by_qty.items() if q >= 1000), default=None)
    return p1, p1k, cur


def _distributor_table() -> pd.DataFrame:
    return pd.read_csv(DISTRIBUTORS)


def classify(name: str, dist: pd.DataFrame) -> tuple[str, bool]:
    for _, r in dist.iterrows():
        if r["distributor_pattern"].lower() in name.lower():
            return r["group"], bool(r["authorized"])
    return name, False


def snapshot_part(part: str, day: str | None = None, refresh: bool = False) -> pd.DataFrame:
    day = day or date.today().isoformat()
    f = fetch(f"https://www.findchips.com/search/{part}", f"findchips_{part}.html", refresh, day=day)
    h = f.read_text(errors="ignore")
    dist = _distributor_table()
    rows = []
    for name, mfr, _instock, stock, mpn, price in ROW.findall(h):
        qty, stock_txt = _stock(stock)
        p1, p1k, cur = _price(price)
        group, auth = classify(name, dist)
        rows.append({"snapshot_date": day, "part": part, "listed_mpn": mpn, "distributor": name, "distributor_group": group,
                     "authorized": int(auth), "manufacturer": html.unescape(mfr), "qty_in_stock": qty, "stock_text": stock_txt,
                     "price_1": p1, "price_1000": p1k, "currency": cur, "source": f"findchips.com/search/{part}"})
    out = pd.DataFrame(rows)
    # one row per (distributor, listed_mpn): the page repeats a row per price-break block
    if len(out):
        out = out.drop_duplicates(subset=["distributor", "listed_mpn"], keep="first")
    return out


def snapshot_all(day: str | None = None, refresh: bool = False) -> pd.DataFrame:
    parts = pd.read_csv(PARTS)
    frames = []
    for _, p in parts.iterrows():
        try:
            d = snapshot_part(p["part"], day, refresh)
            d["family"] = p["family"]
            frames.append(d)
        except Exception as e:
            frames.append(pd.DataFrame([{"snapshot_date": day or date.today().isoformat(), "part": p["part"], "family": p["family"],
                                         "distributor": "", "qty_in_stock": None, "source": f"fetch failed: {e}"}]))
    return pd.concat(frames, ignore_index=True)


def consistency_checks(snap: pd.DataFrame) -> list[dict]:
    """Deterministic checks a scrape can pass or fail:
    1. Farnell / Newark / element14 (global) report one inventory pool -> their stock for the same MPN must agree within 15%
       (the three feeds refresh at different times of day).
    2. Every authorized row has a numeric stock (a parse failure shows as None).
    3. The exact-MPN row (…-R) exists for every part on an authorized distributor."""
    out = []
    s = snap[snap["authorized"] == 1]
    for (part, mpn), g in s.groupby(["part", "listed_mpn"]):
        fam = g[g["distributor_group"] == "Farnell/Newark/element14"]["qty_in_stock"].dropna()
        if len(fam) >= 2:
            spread = (fam.max() - fam.min()) / max(fam.max(), 1)
            out.append({"check": "farnell_group_agreement", "part": part, "mpn": mpn, "values": list(fam.astype(int)),
                        "ok": bool(spread <= 0.15 or fam.max() < 500)})
    for part, g in snap.groupby("part"):
        a = g[g["authorized"] == 1]
        out.append({"check": "authorized_rows_parsed", "part": part, "mpn": "", "values": [int(a["qty_in_stock"].notna().sum()), int(len(a))],
                    "ok": bool(len(a) and a["qty_in_stock"].notna().all())})
        exact = a[a["listed_mpn"].str.upper().str.replace("-", "") == part.upper().replace("-", "")]
        out.append({"check": "exact_mpn_present", "part": part, "mpn": part, "values": sorted(exact["distributor"].tolist()), "ok": bool(len(exact))})
    return out
