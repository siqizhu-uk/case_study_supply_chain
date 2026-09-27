"""FCC OET grants for Logitech (grantee code JNZ): the list was exported by hand from the OET Generic Search on
2026-09-22 (apps.fcc.gov returns 403 to non-US / non-browser clients). This module only validates the file's
integrity and reports the state of the internal-photo reading, which is the manual step that turns the list into
design-win evidence (grade D -> B once a photo shows the SoC marking)."""
from __future__ import annotations

import pandas as pd

from .paths import DATA_RAW

FCC = DATA_RAW / "fcc_logitech_grants_2023_2026.csv"


def validate_fcc() -> dict:
    d = pd.read_csv(FCC, dtype=str).fillna("")
    ids_unique = d["fcc_id"].is_unique
    prefix_ok = d["fcc_id"].str.startswith("JNZ").all()
    dates = pd.to_datetime(d["grant_date"], errors="coerce")
    photos_public = d["internal_photos_public"].str.lower().str.startswith("yes").sum()
    read = (d["soc_marking_observed"].str.strip() != "").sum()
    nordic = d["chip_vendor"].str.contains("Nordic", case=False).sum()
    return {"grants": int(len(d)), "fcc_id_unique": bool(ids_unique), "all_jnz": bool(prefix_ok), "grant_dates_parse": bool(dates.notna().all()),
            "first_grant": str(dates.min().date()), "last_grant": str(dates.max().date()), "internal_photos_public": int(photos_public),
            "soc_marking_read": int(read), "nordic_confirmed": int(nordic)}
