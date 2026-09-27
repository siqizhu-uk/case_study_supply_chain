"""Verification ledger: the last result of every quote / filing check that needs a cached document.

The filings and web pages behind the checks live in gitignored caches (~1 GB). When a document is present the check runs
and its result is recorded here; when it is absent (a fresh clone) the recorded result is shown instead, labelled with
the date it was obtained, so a colleague sees the same verification without downloading anything.
`./run.sh --refresh-data` rebuilds the caches, after which every check runs live again.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from core.config import ROOT

PATH = ROOT / "audit" / "verification_ledger.csv"
COLS = ["step", "key", "result", "value", "checked_on"]
_cache: pd.DataFrame | None = None


def _load() -> pd.DataFrame:
    global _cache
    if _cache is None:
        _cache = pd.read_csv(PATH, dtype=str).fillna("") if PATH.exists() else pd.DataFrame(columns=COLS)
    return _cache


def record(step: str, key: str, result: str, value: object = "") -> str:
    """Store a live result; the date moves only when the result or value changes (no churn on re-runs)."""
    global _cache
    d = _load()
    v = "" if value is None else str(value)
    m = (d["step"] == step) & (d["key"] == key)
    if m.any() and d.loc[m, "result"].iloc[0] == result and d.loc[m, "value"].iloc[0] == v:
        return result
    row = pd.DataFrame([{"step": step, "key": key, "result": result, "value": v, "checked_on": date.today().isoformat()}])
    _cache = pd.concat([d[~m], row], ignore_index=True)
    return result


def recall(step: str, key: str) -> tuple[str, str] | None:
    """(labelled result, value) from the ledger, or None if this check was never run with the document present."""
    d = _load()
    m = (d["step"] == step) & (d["key"] == key)
    if not m.any():
        return None
    r = d[m].iloc[0]
    return f"{r['result']} (recorded {r['checked_on']}; document not cached)", r["value"]


def save() -> None:
    if _cache is not None:
        _cache.sort_values(["step", "key"])[COLS].to_csv(PATH, index=False)
