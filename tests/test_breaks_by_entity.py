"""Decision G31: the structural-breaks-by-entity table lists only breaks and candidate breaks, and every number in it is
read from the timeline, the break tests and the config (none typed)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

from core.config import load_config, step_outputs  # noqa: E402
import breaks_by_entity as bbe  # noqa: E402


@pytest.fixture(scope="module")
def built():
    cfg = load_config()
    return cfg, bbe.table(cfg), pd.read_csv(step_outputs("step5_supply_graph") / "graph_timeline.csv")


def test_one_row_per_configured_break_and_nothing_empty(built):
    cfg, df, _ = built
    assert len(df) == len(cfg["relationship_breaks"]["by_entity"])
    assert (df[bbe.COLUMNS].astype(str).apply(lambda c: c.str.strip().str.len()) > 0).all().all()
    assert df["status"].str.match(r"^(Break|Candidate) ").all()            # breaks and candidates only, no inputs or shocks


def test_the_six_entities_are_covered_by_the_table_or_the_checked_line(built):
    _, df, _ = built
    text = " ".join(df["entity"]) + " " + " ".join(df["what_changed"]) + " " + bbe.checked_no_break()
    for name in ("Nordic", "Logitech", "GN", "Ingram", "TD Synnex", "Amazon"):
        assert name in text, name


def test_numbers_are_read_from_the_timeline_and_the_tests(built):
    _, df, t = built
    backlog = bbe._series(t, "nordic", "backlog_cover")
    row = df[df["what_changed"].str.startswith("Order backlog")].iloc[0]
    assert f"{backlog.max():.1f}x ({backlog.idxmax()})" in row["what_changed"]
    rb = pd.read_csv(step_outputs("step5_supply_graph") / "relationship_breaks.csv")
    p = rb[(rb["relationship"] == "Nordic consumer on Logitech sell-through (t-2)") & (rb["break"] == "2022Q4")]["p"].iloc[0]
    assert f"p {p:.3f}" in row["test"]
    cover = bbe._series(t, "logitech", "cover_weeks")
    st = t[(t["node"] == "all") & (t["metric"] == "cycle_state")].set_index("quarter")["value"].dropna()
    after = cover[cover.index > st[st == "building"].index.max()]
    assert f"{after.mean():.1f} weeks after the destock" in df[df["what_changed"].str.startswith("Logitech's own inventory")].iloc[0]["what_changed"]


def test_a_missing_test_row_fails_loudly():
    rb = pd.DataFrame({"relationship": ["a"], "break": ["2022Q4"], "p": [0.04], "test": ["Chow"], "n_pre": [3], "n_post": [15], "verdict": ["changed"]})
    with pytest.raises(KeyError):
        bbe._test({"relationship": "a", "break": "2030Q1"}, rb, rb)
