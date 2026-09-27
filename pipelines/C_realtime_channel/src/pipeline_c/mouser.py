"""Optional official provider: Mouser Search API (free key, https://www.mouser.com/api-hub/).

Runs only when MOUSER_API_KEY is set; then Mouser's own stock for each part is the cross-check for the findchips
Mouser row (must agree within 5% on the same day). Kept keyless-by-default so the pipeline stays reproducible
without registrations; the code path is exercised by the tests with a canned response.
"""
from __future__ import annotations

import json
import os

import pandas as pd

from .fetch import fetch

ENDPOINT = "https://api.mouser.com/api/v1/search/partnumber?apiKey={key}"


def parse_response(payload: dict, part: str, day: str) -> pd.DataFrame:
    rows = []
    for p in payload.get("SearchResults", {}).get("Parts", []) or []:
        qty = p.get("AvailabilityInStock") or p.get("Availability", "0")
        try:
            qty = float(str(qty).split()[0].replace(",", ""))
        except Exception:
            qty = None
        prices = sorted(((int(x["Quantity"]), float(str(x["Price"]).replace("$", "").replace(",", ""))) for x in (p.get("PriceBreaks") or [])), key=lambda t: t[0])
        def _p(q):
            if not prices:
                return None
            if q <= 1:
                return prices[0][1]                                   # smallest break
            c = [pr for qty, pr in prices if qty >= q]
            return min(c) if c else None
        rows.append({"snapshot_date": day, "part": part, "listed_mpn": p.get("ManufacturerPartNumber", ""), "distributor": "Mouser (API)",
                     "distributor_group": "Mouser", "authorized": 1, "manufacturer": p.get("Manufacturer", ""), "qty_in_stock": qty,
                     "stock_text": p.get("Availability", ""), "price_1": _p(1), "price_1000": _p(1000), "currency": "USD",
                     "lead_time": p.get("LeadTime", ""), "source": "api.mouser.com/api/v1/search/partnumber"})
    return pd.DataFrame(rows)


def snapshot_part(part: str, day: str, refresh: bool = False) -> pd.DataFrame | None:
    key = os.environ.get("MOUSER_API_KEY")
    if not key:
        return None
    body = json.dumps({"SearchByPartRequest": {"mouserPartNumber": part, "partSearchOptions": "Exact"}}).encode()
    f = fetch(ENDPOINT.format(key=key), f"mouser_{part}.json", refresh, day=day, data=body, headers={"Content-Type": "application/json"})
    return parse_response(json.loads(f.read_text()), part, day)
