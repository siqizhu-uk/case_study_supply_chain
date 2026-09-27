"""Grade-C documents used only as context (Bluetooth SIG market update, Nordic Credit Rating report): the
config row carries the sentence we rely on; the check is that the sentence occurs in the fetched document.
Same rule as Pipeline A's verbal metrics: a quote that cannot be found is a `no`, a page that blocks scripts is `manual`."""
from __future__ import annotations

import re

from .fetch import fetch


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[‘’“”]", "'", s)).lower()


def _text(path) -> str:
    if path.suffix == ".pdf":
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return " ".join((p.extract_text() or "") for p in pdf.pages)
    raw = path.read_text(errors="ignore")
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", raw)


def check_quote(url: str, key: str, quote: str, refresh: bool = False) -> tuple[str, str]:
    """Returns (status, detail): found / not_found / fetch_failed."""
    ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
    try:
        f = fetch(url, f"{key}{ext}", refresh)
    except Exception as e:
        return "fetch_failed", f"{type(e).__name__}: {e}"
    try:
        ok = _norm(quote) in _norm(_text(f))
    except Exception as e:
        return "fetch_failed", f"unreadable: {e}"
    return ("found", "quote found in document") if ok else ("not_found", "quote NOT found — re-read the document")
