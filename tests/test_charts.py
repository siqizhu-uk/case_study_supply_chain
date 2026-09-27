"""Dashboard 'Charts' tab (steps/step7_forecast/src/charts.py): every chart draws from the step outputs."""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

import charts  # noqa: E402


def test_every_chart_draws_with_a_computed_takeaway():
    p = pd.read_csv(ROOT / "outputs" / "tier_panel.csv")
    p.index = pd.PeriodIndex(p["quarter"], freq="Q")
    h = charts.charts_tab(p)
    assert "not drawn" not in h
    assert h.count("<div class=chart>") == 8 and h.count("<svg") >= 8
    takes = re.findall(r"<p class=take>(.*?)</p>", h)
    assert len(takes) == 8 and all(re.search(r"\d", t) for t in takes)       # each takeaway quotes a number from the data
    for name in ("forecast_bridges", "chain_over_time", "bullwhip", "inventory", "lag", "attribution", "relationship_breaks", "backtest"):
        assert (charts.STORY / f"{name}.svg").exists()
