"""Dashboard tabs 2-3: the metric catalogue resolves every series; the brief checklist is complete; the timeline has data."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from core.config import load_config  # noqa: E402
from core.ingest import load_all  # noqa: E402
from core.tiers import build_panel  # noqa: E402


@pytest.fixture(scope="module")
def panel():
    cfg = load_config(None)
    return cfg, build_panel(load_all(), cfg)


def test_every_catalogued_series_resolves_and_is_graded(panel):
    from metric_catalogue import catalogue
    cfg, p = panel
    c = catalogue(p)
    assert (c["n"] > 0).all(), c.loc[c["n"] == 0, "metric"].tolist()
    assert set(c["grade"]) <= set("ABCD") and c["brief_item"].str.len().gt(0).all() and c["used_in"].str.len().gt(0).all()


def test_brief_checklist_covers_the_brief_and_says_why():
    chk = pd.read_csv(ROOT / "audit" / "brief_data_checklist.csv").fillna("")
    assert set(chk["status"]) <= {"collected", "partial", "skipped", "live gauge"}
    assert chk["why"].str.len().gt(0).all()
    for item in ("Best Sellers Rank", "Idealo", "Digi-Key", "customer concentration", "Book-to-bill", "restructuring"):
        assert chk["brief_item"].str.contains(item, case=False).any(), item


def test_timeline_has_inventory_for_every_disclosing_node_and_a_frame_per_quarter(panel):
    from supply_graph_timeline import node_states, _frames, COVER
    cfg, p = panel
    st = node_states(p, cfg)
    cov = st[st["metric"] == "cover_weeks"].dropna(subset=["value"])
    assert set(COVER) <= set(cov["node"])
    quarters, frames = _frames(st, cfg)
    assert len(quarters) >= 20 and all({"regime", "nodes", "edges", "reported", "of"} <= set(frames[q]) for q in quarters)
    flows = [sum(e["flow"] for k, e in frames[q]["edges"].items() if k in ("E23", "E24")) for q in quarters]
    assert all(abs(f - 1.0) < 1e-6 for f in flows)                        # all of the slice reaches end demand every quarter
