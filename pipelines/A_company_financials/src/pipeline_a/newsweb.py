"""Oslo Børs NewsWeb (Euronext) as the durable source for Nordic Semiconductor's reports.

Nordic attaches every quarterly report to its stock-exchange announcement, and the NewsWeb reader API is public
and keyless. This avoids nordicsemi.com, which returns HTTP 403 to non-browser clients on some networks.

  list:        https://api3.oslo.oslobors.no/v1/newsreader/list?issuer=NOD&fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
  message:     https://api3.oslo.oslobors.no/v1/newsreader/message?messageId=<id>      (lists attachments)
  attachment:  https://api3.oslo.oslobors.no/v1/newsreader/attachment?messageId=<id>&attachmentId=<id>

Output: PDFs saved as data/cache/filings/nordic/<YYYYQn>.pdf and <ARYYYY>.pdf (same names filings.verify expects),
plus data/processed/newsweb_nordic_index.csv listing every announcement used, with its message id (the citation).
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

import pandas as pd

from .paths import ROOT, DATA_PROC, CACHE as _CACHE

API = "https://api3.oslo.oslobors.no/v1/newsreader"
CACHE = _CACHE / "filings" / "nordic"
UA = {"User-Agent": "Mozilla/5.0 (supply-chain-case-study; siqizhu00@gmail.com)", "Accept": "application/json"}

QUARTER_WORDS = {"first quarter": 1, "second quarter": 2, "third quarter": 3, "fourth quarter": 4,
                 "q1": 1, "q2": 2, "q3": 3, "q4": 4}


def _get(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read())


def list_messages(issuer: str = "NOD", start: str = "2021-01-01", end: str | None = None) -> list[dict]:
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    out = []
    edges = list(pd.date_range(start, end, freq="730D")) + [pd.Timestamp(end)]
    for a, b in zip(edges[:-1], edges[1:]):
        d = _get(f"{API}/list?issuer={issuer}&fromDate={a:%Y-%m-%d}&toDate={b:%Y-%m-%d}")
        out += d["data"]["messages"]
        time.sleep(0.3)
    seen, uniq = set(), []
    for m in out:
        if m["messageId"] not in seen:
            seen.add(m["messageId"]); uniq.append(m)
    return uniq


def classify(title: str, published: str) -> str | None:
    """Map an announcement title to a filing key: '2025Q4' for quarterly results, 'AR2025' for annual reports."""
    t = title.lower()
    year = int(published[:4])
    if "annual report" in t:
        return f"AR{year - 1}"
    for w, q in QUARTER_WORDS.items():
        if w in t and ("result" in t or "report" in t):
            # Q4 results are published in Feb of the following year
            return f"{year - 1 if q == 4 else year}Q{q}"
    return None


def download_nordic_reports(refresh: bool = False) -> pd.DataFrame:
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for m in list_messages():
        key = classify(m["title"], m["publishedTime"])
        if not key or m["numbAttachments"] == 0:
            continue
        detail = _get(f"{API}/message?messageId={m['messageId']}")["data"]["message"]
        atts = detail.get("attachments") or []
        # prefer the report over the presentation; annual report over ESEF zip
        rep = [a for a in atts if a["name"].lower().endswith(".pdf") and re.search(r"report", a["name"], re.I)
               and not re.search(r"presentation|remuneration|esef", a["name"], re.I)]
        if not rep:
            rep = [a for a in atts if a["name"].lower().endswith(".pdf")]
        if not rep:
            continue
        a = rep[0]
        f = CACHE / f"{key}.pdf"
        status = "cached"
        if refresh or not f.exists() or f.stat().st_size < 50_000:
            url = f"{API}/attachment?messageId={m['messageId']}&attachmentId={a['id']}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
                f.write_bytes(r.read())
            status = "downloaded"
            time.sleep(0.5)
        rows.append({"key": key, "message_id": m["messageId"], "published": m["publishedTime"][:10], "title": m["title"],
                     "attachment": a["name"], "bytes": f.stat().st_size, "status": status,
                     "url": f"https://newsweb.oslobors.no/message/{m['messageId']}"})
    out = pd.DataFrame(rows).sort_values("key")
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(DATA_PROC / "newsweb_nordic_index.csv", index=False)
    return out
