"""Keyless HTTP fetch, cached under data/cache/<date>/<name> so a day's snapshot is re-readable."""
from __future__ import annotations

import time
import urllib.request
from datetime import date
from pathlib import Path

from .paths import CACHE, UA


def fetch(url: str, name: str, refresh: bool = False, timeout: int = 90, day: str | None = None, data: bytes | None = None,
          headers: dict | None = None) -> Path:
    d = CACHE / (day or date.today().isoformat())
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    if f.exists() and f.stat().st_size > 200 and not refresh:
        return f
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, "Accept": "*/*", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        f.write_bytes(r.read())
    time.sleep(0.7)
    return f
