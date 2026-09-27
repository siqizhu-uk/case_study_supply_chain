"""Load the hand-collected public data (data/raw/*.csv).

Every row in the raw CSVs carries a `source` column pointing at the filing or
transcript it came from, and an `is_estimate` flag where a value was derived
rather than reported. Nothing here touches the network; see `sec_xbrl.py` for
the optional cross-check against SEC XBRL company facts.
"""
from __future__ import annotations

import pandas as pd

from .config import DATA_RAW, CHANNEL_SNAPSHOTS

FILES = {
    "nordic": "nordic_quarterly.csv",
    "logitech": "logitech_quarterly.csv",
    "gn": "gn_quarterly.csv",
    "ingram": "ingram_quarterly.csv",
    "tdsynnex": "tdsynnex_quarterly.csv",
}


def _read(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA_RAW / FILES[name])
    if "quarter" in df.columns:
        df["quarter"] = pd.PeriodIndex(df["quarter"], freq="Q")
        df = df.sort_values("quarter").set_index("quarter")
    return df


def load_channel() -> pd.DataFrame:
    """Pipeline C distributor-stock series (all dated snapshots); empty frame if the pipeline has not run."""
    if not CHANNEL_SNAPSHOTS.exists():
        return pd.DataFrame(columns=["snapshot_date", "part", "distributor_group", "authorized", "listed_mpn", "qty_in_stock", "lead_time"])
    return pd.read_csv(CHANNEL_SNAPSHOTS, dtype={"snapshot_date": str})


def load_all() -> dict[str, pd.DataFrame]:
    """Return a dict of DataFrames keyed by company, indexed by calendar quarter, plus the Pipeline C channel series."""
    d = {k: _read(k) for k in FILES}
    d["channel"] = load_channel()
    return d


def reported_only(df: pd.DataFrame, col: str) -> pd.Series:
    """Drop rows that are pure guidance placeholders (no actuals yet)."""
    return df[col].dropna()
