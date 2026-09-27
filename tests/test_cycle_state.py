"""Channel-cycle state from the mechanism data (steps/step3_inventory_mechanism/src/cycle_state.py).
Run: pytest -q tests/test_cycle_state.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from core.config import load_config  # noqa: E402
import cycle_state as cs  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _series(vals, start="2010Q1"):
    return pd.Series(vals, index=pd.period_range(start, periods=len(vals), freq="Q"), dtype=float)


def test_rule_priority_on_a_hand_built_path(cfg):
    flat = [33.0] * 14
    d = _series(flat + [33, 37, 41, 41, 37, 33, 24, 24, 24, 24])    # rise, plateau, fall, then low and flat
    st = cs.classify(d, cfg)["state"]
    assert st.iloc[15] == "building" and st.iloc[16] == "building"
    assert st.iloc[18] == "drawdown" and st.iloc[19] == "drawdown"
    assert st.iloc[-1] == "lean"
    assert st.iloc[13] == "normal"


def test_state_is_point_in_time(cfg):
    d = cs.load_signal(cfg)
    base = cs.classify(d, cfg)
    cut = pd.Period("2022Q4", "Q")
    d2 = d.copy()
    d2[d2.index > cut] = d2[d2.index > cut] * 3 + 50            # rewrite the future
    pert = cs.classify(d2, cfg)
    pd.testing.assert_series_equal(base.loc[:cut, "state"], pert.loc[:cut, "state"])


def test_too_little_history_gives_no_state(cfg):
    st = cs.classify(_series([30.0] * 5), cfg)["state"]
    assert st.isna().all()


def test_beat_by_state_uses_the_state_known_at_the_forecast(cfg):
    from core.ingest import load_all
    from core.tiers import build_panel
    states = cs.classify(cs.load_signal(cfg), cfg)
    t = cs.beat_by_state(states, cfg, build_panel(load_all(), cfg)["nordic_beat_vs_guide_pct"])
    assert {"peers", "nordic"} <= set(t["sample"])
    assert set(t["state"]) <= set(cfg["cycle_state"]["priority"])
    peers = t[t["sample"] == "peers"]
    assert (peers["n"] >= 1).all() and peers["n"].sum() > 300


def test_transition_rows_are_probabilities(cfg):
    tr = cs.transitions(cs.classify(cs.load_signal(cfg), cfg))
    assert np.allclose(tr.sum(axis=1), 1.0)


def test_contrast_is_computed_with_clustered_errors(cfg):
    c = cs.state_contrast(cs.classify(cs.load_signal(cfg), cfg), cfg)
    assert c["quarters"] < c["n"] and c["se_clustered"] > 0 and np.isfinite(c["t"])


def test_shortage_splits_lean_for_nordic_on_supply_evidence_only(cfg):
    """D24: a lean channel is a shortage for Nordic only with supply-side evidence of unmet demand (backlog above two
    quarters of revenue, or a live lead time above 26 weeks); the industry state is left untouched."""
    out = cs.run_cycle_state(cfg, write=False)["states"]
    q = lambda s: pd.Period(s, "Q")  # noqa: E731
    assert all(out.loc[q(s), "state_nordic"] == "shortage" for s in ("2020Q4", "2021Q2", "2021Q4", "2022Q3"))
    assert out.loc[q("2026Q2"), "state"] == "lean" and out.loc[q("2026Q2"), "state_nordic"] == "lean"   # lead time 16 wk
    assert (out["state_nordic"] == "shortage").sum() == ((out["state"] == "lean") & (out["state_nordic"] == "shortage")).sum()
    diff = out["state"].fillna("") != out["state_nordic"].fillna("")
    assert (out.loc[diff, "state_nordic"] == "shortage").all()                     # the overlay only ever relabels lean
    assert out.loc[q("2021Q4"), "backlog_x_rev"] > cfg["cycle_state"]["shortage"]["backlog_min_quarters_of_revenue"]
