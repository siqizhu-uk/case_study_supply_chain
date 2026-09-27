"""Keyless HTTP fetch with an on-disk cache under data/cache/<name>."""
from __future__ import annotations

import time
import urllib.request
from pathlib import Path

from .paths import CACHE, UA


def fetch(url: str, name: str, refresh: bool = False, timeout: int = 90) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / name
    if f.exists() and f.stat().st_size > 500 and not refresh:
        return f
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        f.write_bytes(r.read())
    time.sleep(0.5)
    return f
