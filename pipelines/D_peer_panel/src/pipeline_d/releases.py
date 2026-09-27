"""Fetch every earnings 8-K (Item 2.02) Exhibit 99.1 for the peers in config/peers.yaml, cached under data/cache/.
Keyless SEC endpoints with a descriptive User-Agent, <= 10 requests/s."""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from pathlib import Path

import yaml

PIPE = Path(__file__).resolve().parents[2]
ROOT = PIPE.parents[1]
CONFIG = PIPE / "config" / "peers.yaml"
CACHE = PIPE / "data" / "cache"
RAW = PIPE / "data" / "raw"
PROC = PIPE / "data" / "processed"
UA = "supply-chain-case-study (public research) siqizhu00@gmail.com"


def load_cfg() -> dict:
    return yaml.safe_load(CONFIG.read_text())


def _get(url: str, tries: int = 4) -> bytes:
    """SEC answers 503 ('File Unavailable') intermittently for single files and 429 when rate-limited: back off 10, 20, 40 s.
    A file that still fails is skipped by the caller and retried on the next run (every file is cached)."""
    import urllib.error
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            time.sleep(0.35)          # ~3 requests/s: well under SEC's 10/s, and gentle on the Archives host
            return data
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503) or k == tries - 1:
                raise
            time.sleep(10 * 2 ** k)
        except (urllib.error.URLError, TimeoutError, ConnectionError):     # network dropped (laptop asleep, DNS): wait and retry
            if k == tries - 1:
                raise
            time.sleep(10 * 2 ** k)
    raise RuntimeError(url)


def _cached(path: Path, url: str, refresh: bool = False) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if refresh or not path.exists():
        path.write_bytes(_get(url))
    return path.read_bytes()


def html_text(raw: bytes) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw.decode(errors="ignore"), flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t))).replace("’", "'")


def pick_exhibits(items: list[dict]) -> list[str]:
    """The press-release exhibit of an Item 2.02 8-K. Filing agents name it 'ex99-1.htm', 'exhibit991.htm', but also
    'ex_209041.htm' (no '99'): prefer ex-99 names, then 'ex_<digits>' names, then the largest document that is not an
    index page, the 8-K cover or an R*.htm XBRL viewer page."""
    docs = [(x["name"], int(x.get("size") or 0)) for x in items if x["name"].lower().endswith((".htm", ".html"))
            and "index" not in x["name"].lower() and not re.match(r"R\d+\.htm", x["name"])]
    ex99 = [n for n, _ in docs if re.search(r"(ex|exhibit)[-_]?0?99|99[-_.]?1|earningsrel|pressrelease|press", n, re.I)]
    exnum = [n for n, _ in docs if re.match(r"ex[-_]?\d", n, re.I)]
    rest = [n for n, _ in sorted(docs, key=lambda d: -d[1]) if not re.search(r"8-?k", n, re.I)]
    return list(dict.fromkeys(ex99 + exnum + rest))


def earnings_releases(company: str, cik: int, since: str, refresh: bool = False) -> list[dict]:
    """[{date, accession, url, text}] for every Item 2.02 8-K since `since`, Exhibit 99.1 text."""
    sub = json.loads(_cached(CACHE / company / "submissions.json", f"https://data.sec.gov/submissions/CIK{cik:010d}.json", refresh))
    pages = [sub["filings"]["recent"]]
    for f in sub["filings"].get("files", []):            # older filings live in paged files
        pages.append(json.loads(_cached(CACHE / company / f["name"], f"https://data.sec.gov/submissions/{f['name']}", refresh)))
    out = []
    for rec in pages:
      for form, acc, d, items in zip(rec["form"], rec["accessionNumber"], rec["filingDate"], rec.get("items", [""] * len(rec["form"]))):
          if form != "8-K" or "2.02" not in (items or "") or d < since:
              continue
          base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}"
          try:
              idx = json.loads(_cached(CACHE / company / acc / "index.json", f"{base}/index.json", False))
              ex = pick_exhibits(idx["directory"]["item"])
              texts = [(n, html_text(_cached(CACHE / company / acc / n, f"{base}/{n}"))) for n in ex[:3]]
          except Exception as e:                        # SEC 'File Unavailable' after retries: skip, list it, retry next run
              out.append({"company": company, "date": d, "accession": acc, "url": base, "text": "", "unavailable": str(e)[:80]})
              continue
          n, t = max(texts, key=lambda x: len(x[1])) if texts else ("", "")
          out.append({"company": company, "date": d, "accession": acc, "url": f"{base}/{n}", "text": t})
    return sorted(out, key=lambda r: r["date"])
