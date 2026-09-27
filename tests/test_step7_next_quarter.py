"""Step 7: the graph-driven forecast one quarter past the guide (Nordic Q4 2026, h=2)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))


@pytest.fixture(scope="module")
def fc():
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from forecast_next import forecast_next_quarter
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    return forecast_next_quarter(p, cfg, None).set_index("model"), cfg


def test_every_configured_model_has_a_point_inside_its_range(fc):
    df, cfg = fc
    assert list(df.index) == cfg["forecast_next_quarter"]["models"]
    assert ((df["low"] <= df["point"]) & (df["point"] <= df["high"])).all()
    assert (df["quarter"] == cfg["forecast_next_quarter"]["target"]).all()


def test_graph_lags_reach_grg_but_collapse_in_gr(fc):
    """The documented trap (P74): at h=2 GR puts every lag below 2 quarters on the same quarter, so the lag scenario
    barely moves it; GRg reads Logitech's guide for the unreported quarter, so it does move."""
    df, _ = fc
    spread = df["lag_high_point"] - df["lag_low_point"]
    assert abs(spread["GRg"]) > abs(spread["GR"])
    assert df.loc["G", "lag_low_point"] != df.loc["G", "lag_low_point"]      # NaN: no graph in the benchmark
