"""Take today's snapshot, append it to the series, write the latest table and the design-win evidence."""
from __future__ import annotations

from datetime import date

import pandas as pd

from . import findchips, mouser, ifixit
from .paths import DATA_PROC, SNAPSHOTS

SNAP_COLS = ["snapshot_date", "part", "family", "listed_mpn", "distributor", "distributor_group", "authorized", "manufacturer",
             "qty_in_stock", "stock_text", "price_1", "price_1000", "currency", "lead_time", "source"]


def take_snapshot(day: str | None = None, refresh: bool = False) -> tuple[pd.DataFrame, list[dict], dict]:
    day = day or date.today().isoformat()
    snap = findchips.snapshot_all(day, refresh)
    checks = findchips.consistency_checks(snap[snap["distributor"] != ""]) if len(snap) else []
    api = {}
    for part in snap["part"].unique():
        m = mouser.snapshot_part(part, day, refresh)
        if m is not None and len(m):
            snap = pd.concat([snap, m], ignore_index=True)
            fc = snap[(snap["part"] == part) & (snap["distributor_group"] == "Mouser") & (~snap["distributor"].str.contains("API"))]["qty_in_stock"].dropna()
            if len(fc):
                a, b = float(m["qty_in_stock"].iloc[0]), float(fc.iloc[0])
                api[part] = {"mouser_api": a, "findchips_mouser_row": b, "ok": abs(a - b) <= 0.05 * max(a, b, 1)}
    for c in SNAP_COLS:
        if c not in snap.columns:
            snap[c] = None
    snap = snap[SNAP_COLS]
    # append to the series (replace same-day rows so a re-run is idempotent)
    if SNAPSHOTS.exists():
        prev = pd.read_csv(SNAPSHOTS, dtype={"snapshot_date": str})
        prev = prev[prev["snapshot_date"] != day]
        series = pd.concat([prev, snap], ignore_index=True)
    else:
        series = snap
    series.to_csv(SNAPSHOTS, index=False)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    snap.to_csv(DATA_PROC / "channel_latest.csv", index=False)
    return snap, checks, api


def authorized_series() -> pd.DataFrame:
    """Per snapshot date and part: authorized-distributor stock (exact MPN), number of authorized distributors listing it, min price."""
    s = pd.read_csv(SNAPSHOTS, dtype={"snapshot_date": str})
    s = s[(s["authorized"] == 1) & s["qty_in_stock"].notna()]
    s = s[s["listed_mpn"].fillna("").str.upper().str.replace("-", "") == s["part"].str.upper().str.replace("-", "")]
    # one number per distributor group (Farnell/Newark/element14 is one pool -> take max, not sum)
    s = s.assign(price_usd=s["price_1"].where(s["currency"] == "USD"))
    g = s.groupby(["snapshot_date", "part", "distributor_group"]).agg(qty=("qty_in_stock", "max"), price_usd=("price_usd", "min")).reset_index()
    out = g.groupby(["snapshot_date", "part"]).agg(authorized_stock=("qty", "sum"), groups_listing=("qty", lambda x: int((x > 0).sum())),
                                                  groups_counted=("distributor_group", lambda x: "|".join(sorted(x))),
                                                  min_price_1_usd=("price_usd", "min")).reset_index()
    out.to_csv(DATA_PROC / "channel_series.csv", index=False)
    return out


def design_wins(day: str | None = None, refresh: bool = False) -> pd.DataFrame:
    day = day or date.today().isoformat()
    guides = ifixit.list_guides(day, refresh)
    ev = ifixit.scan_guides(guides, day, refresh)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    guides.to_csv(DATA_PROC / "ifixit_guides.csv", index=False)
    ev.to_csv(DATA_PROC / "design_win_evidence.csv", index=False)
    return ev
