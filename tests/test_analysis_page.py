"""The analyst's write-up (deliverables/my_analysis.html, the dashboard's Analysis tab, and its working draft
my_analysis.md) is hand-written: the analyst's reading of the values of one run. Its headline numbers must match the
outputs of the latest run, or this test names the one to revisit.
Run: pytest -q tests/test_analysis_page.py"""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "steps" / "step7_forecast" / "src"))

DOCS = [ROOT / "deliverables" / "my_analysis.md", ROOT / "deliverables" / "my_analysis.html"]
pytestmark = pytest.mark.skipif(not all(d.exists() for d in DOCS), reason="no analysis write-up in this checkout")


def _texts():
    return {d.name: d.read_text(encoding="utf-8") for d in DOCS}


def _forms(v: float) -> set[str]:
    return {f"{v:,.1f}", f"{v:,.0f}"}


def test_the_six_forecasts_and_ranges_are_the_computed_ones():
    fc = pd.read_csv(ROOT / "outputs" / "forecasts.csv")
    for name, t in _texts().items():
        for r in fc.itertuples():
            assert any(p in t for p in _forms(r.point)), (name, r.print, r.metric, r.point)
            rng = {f"{a}–{b}" for a in _forms(r.low) for b in _forms(r.high)}
            assert any(x in t for x in rng), (name, r.print, r.metric, r.low, r.high)


def test_attribution_headline_and_expected_guide_errors_are_the_computed_ones():
    d = json.loads((ROOT / "outputs" / "forecast_details.json").read_text())
    tot = d["attribution"]["combined_pct_of_nordic_total"]
    con = d["attribution"]["combined_pct_of_nordic_consumer"]
    for name, t in _texts().items():
        for v in (tot, con):                    # '16% (13–20%)' or '27% of Nordic Consumer (22–34%'
            pat = rf"{v['p50']:.0f}%[^()]{{0,30}}\({v['p10']:.0f}–{v['p90']:.0f}%"
            assert re.search(pat, t), (name, pat)
        for co in ("nordic", "logitech"):
            assert f"{d[co]['hist_beat_pct']:.2f}%" in t, (name, co, d[co]["hist_beat_pct"])
        assert f"{d['gn']['guidance_anchor']['august_bias_pts']:.1f}".replace("-", "−") in t, (name, "GN August bias")


def test_dashboard_carries_the_analysis_tab():
    import analysis_tab
    tab = analysis_tab.analysis_tab_html()
    assert "srcdoc=" in tab and "src=\"figures/" not in tab          # every chart embedded, nothing fetched
    assert "data-tab=analysis" in (ROOT / "deliverables" / "dashboard.html").read_text()
