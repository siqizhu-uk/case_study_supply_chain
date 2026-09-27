"""Fiscal-calendar alignment (Data tab): every row describes the Jul-Sep 2026 period; the majority rule files it under 2026Q3."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "steps" / "step7_forecast" / "src"))


def test_majority_rule_on_known_closes():
    from fiscal_calendar import majority_quarter
    for end, q in [("2026-09-30", "2026Q3"), ("2026-07-04", "2026Q2"), ("2026-09-26", "2026Q3"), ("2026-08-01", "2026Q2"),
                   ("2026-10-31", "2026Q3"), ("2026-08-31", "2026Q3"), ("2027-01-30", "2026Q4"), ("2026-10-25", "2026Q3")]:
        assert str(majority_quarter(end)) == q, end


def test_every_row_is_the_jul_sep_quarter():
    from fiscal_calendar import table
    d = table()
    assert (d["calendar_quarter"] == "2026Q3").all()
    assert {"Nordic Semiconductor", "Logitech", "GN Store Nord"} <= set(d["company"])
