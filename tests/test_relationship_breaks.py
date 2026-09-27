"""Which breaks changed the supply-chain relationships (steps/step5_supply_graph/src/relationship_breaks.py).
Run: pytest -q tests/test_relationship_breaks.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

import relationship_breaks as rb  # noqa: E402

RNG = np.random.default_rng(7)


def _data(slope_change: float, n: int = 40):
    x = RNG.normal(size=n)
    d = (np.arange(n) >= n // 2).astype(float)
    y = 1.0 + 2.0 * x + slope_change * d * x + RNG.normal(scale=0.5, size=n)
    return y, x, n // 2


def test_chow_finds_a_real_slope_break_and_not_a_fake_one():
    y, x, s = _data(3.0)
    assert rb.chow(y, x, s)["p"] < 0.01
    y, x, s = _data(0.0)
    assert rb.chow(y, x, s)["p"] > 0.05


def test_predictive_chow_works_when_one_segment_is_shorter_than_the_parameters():
    y, x, _ = _data(0.0, 20)
    r = rb.chow(y, x, 2)                          # 2 observations before the break, 2 parameters
    assert r["test"] == "Chow predictive" and 0 <= r["p"] <= 1
    y2 = y.copy()
    y2[:2] += 25                                  # the two early points are off the post-break line
    assert rb.chow(y2, x, 2)["p"] < 0.01


def test_hac_wald_agrees_in_direction_with_chow():
    y, x, s = _data(3.0)
    assert rb.hac_break(y, x, s, lags=1)["p"] < 0.01


@pytest.fixture(scope="module")
def table():
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    cfg = load_config()
    return rb.relationship_breaks(build_panel(load_all(), cfg), cfg)


def test_every_relationship_row_has_evidence_a_verdict_and_a_treatment(table):
    assert {"relationship", "edge", "break", "evidence", "verdict", "treatment"} <= set(table.columns)
    assert table[["relationship", "evidence", "verdict", "treatment"]].apply(lambda c: c.astype(str).str.len() > 3).all().all()
    assert set(table["verdict"]) <= set(rb.VERDICTS)


def test_the_pre_registered_event_dates_are_tested_on_the_nordic_logitech_link(table):
    link = table[table["relationship"].str.startswith("Nordic consumer on Logitech")]
    assert set(link["break"]) >= {"2022Q3", "2024Q2"}
    assert link["p"].between(0, 1).all()


def test_downstream_structure_is_reported_as_stable_and_upstream_share_as_moving(table):
    by = table.set_index("relationship")["verdict"]
    assert by["Logitech 10-K customer shares"] == "stable"
    assert by["Logitech + GN share of Nordic revenue"] == "changed"


# ---- events 2021-26 (G28) -----------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def panel_cfg():
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    cfg = load_config()
    return build_panel(load_all(), cfg), cfg


def test_tariff_price_effect_follows_the_quoted_margin_lift_and_laps(panel_cfg):
    p, cfg = panel_cfg
    e = rb.tariff_price_effect(p, cfg)
    t = cfg["relationship_breaks"]["event_breaks"]["tariff_2025"]
    c = 1 - t["gm_rate"]
    full = 100 * (t["gm_lift_from_price_pts"] / 100 / c) / (1 - t["gm_lift_from_price_pts"] / 100 / c)
    assert e[pd.Period("2025Q3", "Q")] == pytest.approx(full, rel=1e-6)
    assert e.get(pd.Period("2024Q4", "Q"), 0.0) == 0 and e.get(pd.Period("2026Q3", "Q"), 0.0) == 0      # none before, lapped after
    assert 2.0 < full < 3.5                                            # a price step of ~2.7%, not the unsourced 10%


def test_normalisation_decomposition_adds_up(panel_cfg):
    p, cfg = panel_cfg
    d = rb.normalisation_decomposition(p, cfg)
    assert np.allclose(d["slice_contribution"] + d["rest_of_nordic"], d["nordic_consumer_yoy"])
    assert len(d) >= 6


def test_every_event_row_is_typed_and_handled(panel_cfg):
    p, cfg = panel_cfg
    ev = rb.event_rows(p, cfg)
    t = pd.DataFrame(ev)
    assert {"tariff 2025", "post-COVID normalisation", "AI / memory cycle", "Nordic capacity"} <= set(t["event"])
    assert set(t["verdict"]) <= set(rb.VERDICTS)
    assert (t["treatment"].str.len() > 10).all() and (t["evidence"].str.len() > 10).all()
