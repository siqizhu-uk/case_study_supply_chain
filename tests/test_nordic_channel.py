"""Nordic's own channel (steps/step3_inventory_mechanism/src/nordic_channel.py, D25, P128).
Run: pytest -q tests/test_nordic_channel.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "steps" / "step3_inventory_mechanism" / "src"))

from core.config import load_config  # noqa: E402
import cycle_state as cs  # noqa: E402
import nordic_channel as nc  # noqa: E402


def _conc():
    return pd.DataFrame({"year": [2021, 2022, 2023], "top10_basis": ["40% x Bluetooth revenue", "USD disclosed", "USD disclosed"],
                         "broad_usdm": [100.0, 110.0, 55.0], "top10_yoy_pct": [None, 20.0, 0.0], "broad_yoy_pct": [None, 10.0, -50.0]})


def _factors():
    q = [f"{y}Q{k}" for y in (2021, 2022, 2023) for k in (1, 2, 3, 4)]
    return pd.DataFrame({"arrow_dio": 49.0, "avnet_dio": 63.0}, index=q)


def test_gap_times_last_years_broad_market_is_the_channel_change():
    s = nc.annual_size(_conc(), _factors()).set_index("year")
    assert s.loc[2022, "gap_pts"] == -10.0 and s.loc[2022, "channel_change_usdm"] == -10.0      # -10 pts x 100
    assert s.loc[2023, "channel_change_usdm"] == -55.0                                           # -50 pts x 110
    assert s.loc[2023, "cum_change_usdm"] == -65.0
    assert s.loc[2023, "weeks_of_prior_year_broad_sales"] == pytest.approx(-55 / (110 / 52), abs=0.05)
    assert s.loc[2021, "top10_estimated"] and not s.loc[2022, "top10_estimated"]
    assert s.loc[2022, "arrow_weeks_q4"] == 7.0


@pytest.fixture(scope="module")
def live():
    from core.ingest import load_all
    from core.tiers import build_panel
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    states = cs.run_cycle_state(cfg, write=False)["states"]
    out = ROOT / "steps" / "step3_inventory_mechanism" / "outputs"
    conc = pd.read_csv(out / "nordic_top10_vs_broad.csv")
    f = pd.read_csv(out / "factors_quarterly.csv").set_index("quarter")
    return nc.run_nordic_channel(conc, f, p, states, write=False)


def test_microchip_days_are_not_nordics_channel_level(live):
    """P128: Nordic's own channel level (cumulated wording) and Microchip's days move in opposite phase, so the proxy
    cannot size Nordic's channel; it is kept only as a state signal."""
    sh = live["shifts"].set_index("mchp_shift_q")["corr_level_vs_mchp_days"]
    assert (sh.loc[-3:4] < 0).all()
    assert live["size"]["channel_change_usdm"].sum() < 0                       # the route drained over 2022-24


def test_the_state_turns_agree_within_a_quarter(live):
    """The proxy is kept as a state signal because its turn into excess matches Nordic's own words within one quarter."""
    q = live["quarterly"]
    idx = list(q.index)
    nordic_turn = idx.index(q.index[(q["nordic_wording"] < 0)][0])
    mchp_turn = idx.index(q.index[q["mchp_state"] == "building"][0])
    assert abs(nordic_turn - mchp_turn) <= 1
