"""Step 3 disclosure table (D23): every tier covered, every model series it names exists in the metric catalogue or the data."""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "steps" / "step3_inventory_mechanism" / "src"))


def test_disclosure_table_names_real_series():
    from disclosure import load, section_html
    d = load()
    assert {"1 Retail", "2 IT distributors", "3 OEM (brand)", "4 ODM / EMS", "5 Component distributors", "6 Chip vendor"} <= set(d["tier"])
    known = set(pd.read_csv(ROOT / "audit" / "metric_catalogue.csv")["metric"]) | {"odm_monthly_revenue", "nordic_top10_vs_broad"}
    named = {t for s in d["series_in_model"] for t in re.findall(r"[a-z][a-z0-9_]+", s) if "_" in t}
    assert named <= known, named - known
    assert "Who holds the inventory" in section_html() or "who holds the inventory" in section_html().lower()
