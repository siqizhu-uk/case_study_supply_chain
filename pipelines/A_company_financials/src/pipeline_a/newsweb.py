"""Oslo Børs NewsWeb (Euronext) as the durable source for Nordic Semiconductor's reports.

Nordic attaches every quarterly report to its stock-exchange announcement, and the NewsWeb reader API is public
and keyless. This avoids nordicsemi.com, which returns HTTP 403 to non-browser clients on some networks.

  list:        https://api3.oslo.oslobors.no/v1/newsreader/list?issuer=NOD&fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD
  message:     https://api3.oslo.oslobors.no/v1/newsreader/message?messageId=<id>      (lists attachments)
  attachment:  https://api3.oslo.oslobors.no/v1/newsreader/attachment?messageId=<id>&attachmentId=<id>

Output: PDFs saved as data/cache/filings/nordic/<YYYYQn>.pdf and <ARYYYY>.pdf (same names filings.verify expects),
plus data/processed/newsweb_nordic_index.csv listing every announcement used, with its message id (the citation).
Announcement bodies (guidance updates and pre-announcements without an attachment) are cached as
data/cache/filings/nordic/newsweb_<messageId>.txt by `download_announcements`, for the quote checks in nordic_guidance.py.

History starts with the Q2 2017 report (START): Nordic guided by half-year in 2017-18 and by quarter from the Q4 2018
report (first quarterly guide: Q1 2019), so the reports from mid-2017 carry every guidance statement the model uses
(decision F32). Earlier reports (Q4 2016, Q1 2017) are image-only PDFs with no extractable text.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path

import pandas as pd

from .paths import ROOT, DATA_PROC, CACHE as _CACHE

API = "https://api3.oslo.oslobors.no/v1/newsreader"
START = "2017-07-01"          # first announcement window: the Q2 2017 report (first half-year guide the model records)
CACHE = _CACHE / "filings" / "nordic"

UA = {"User-Agent": "Mozilla/5.0 (supply-chain-case-study; siqizhu00@gmail.com)", "Accept": "application/json"}

QUARTER_WORDS = {"first quarter": 1, "second quarter": 2, "third quarter": 3, "fourth quarter": 4,
                 "q1": 1, "q2": 2, "q3": 3, "q4": 4}


def _get(url: str) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read())


def _window(issuer: str, a: pd.Timestamp, b: pd.Timestamp) -> list[dict]:
    """One list call; the endpoint returns at most 50 messages and flags 'overflow', so a full window is split in two
    (P131: a 2-year window silently dropped the 2022 annual report)."""
    d = _get(f"{API}/list?issuer={issuer}&fromDate={a:%Y-%m-%d}&toDate={b:%Y-%m-%d}")["data"]
    time.sleep(0.3)
    if d.get("overflow"):
        if (b - a).days > 7:
            mid = a + (b - a) / 2
            return _window(issuer, a, mid) + _window(issuer, mid, b)
        import sys
        print(f"NewsWeb: window {a:%Y-%m-%d}..{b:%Y-%m-%d} still overflows at 50 messages; some announcements are missing", file=sys.stderr)
    return d["messages"]


def list_messages(issuer: str = "NOD", start: str = START, end: str | None = None) -> list[dict]:
    end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
    out = []
    edges = list(pd.date_range(start, end, freq="180D")) + [pd.Timestamp(end)]
    for a, b in zip(edges[:-1], edges[1:]):
        out += _window(issuer, a, b)
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
    rows, seen = [], set()
    index = DATA_PROC / "newsweb_nordic_index.csv"
    cited = pd.read_csv(index, dtype=str).set_index("key")["message_id"].to_dict() if index.exists() else {}
    # newest first: a corrected re-issue of a report (e.g. 'Correction - Q2 2017 Report', the version with the
    # board statement) is the one kept for its key; the original announcement is skipped as a duplicate
    for m in sorted(list_messages(start=START), key=lambda x: x["publishedTime"], reverse=True):
        key = classify(m["title"], m["publishedTime"])
        if not key or m["numbAttachments"] == 0 or key in seen:
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
        seen.add(key)                                       # only once this message yields the report PDF
        f = CACHE / f"{key}.pdf"
        status = "cached"
        if refresh or not f.exists() or f.stat().st_size < 50_000 or cited.get(key, str(m["messageId"])) != str(m["messageId"]):
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


def announcement_path(message_id: int) -> "Path":
    return CACHE / f"newsweb_{int(message_id)}.txt"


def download_announcements(message_ids, refresh: bool = False) -> pd.DataFrame:
    """Cache the plain text of announcements that carry a guidance statement but no report (mid-quarter updates,
    guidance cuts, pre-announcements). The first line of each file is the message page URL (the citation)."""
    import html as _html
    CACHE.mkdir(parents=True, exist_ok=True)
    rows = []
    for mid in message_ids:
        f = announcement_path(mid)
        status = "cached"
        if refresh or not f.exists():
            d = _get(f"{API}/message?messageId={int(mid)}")["data"]["message"]
            body = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", d.get("body") or ""))).strip()
            f.write_text(f"https://newsweb.oslobors.no/message/{int(mid)}\n{d.get('title', '')}\n{body}")
            status = "downloaded"
            time.sleep(0.3)
        rows.append({"message_id": int(mid), "status": status, "bytes": f.stat().st_size})
    return pd.DataFrame(rows)
