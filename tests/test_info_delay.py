"""Order-signal lag = physical dwell + information delay (step 5, decision G25, pitfalls P86 / P100 / P101).
Run: pytest -q tests/test_info_delay.py"""
import copy
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
import info_delay as idl  # noqa: E402
import supply_graph as sg  # noqa: E402

SC = ("low", "mid", "high")


@pytest.fixture(scope="module")
def cfg():
    return load_config(None)


def _num(e: pd.DataFrame, col: str) -> pd.Series:
    return pd.to_numeric(e[col], errors="coerce")


def test_planner_delay_is_half_review_plus_mean_age_of_the_smoothed_forecast():
    p = {"review_weeks": {"low": 1.0, "mid": 4.0, "high": 2.0}, "alpha": {"low": 1.0, "mid": 0.5, "high": 0.25}}
    d = idl.planner_delay(p)
    assert d == pytest.approx({"low": 0.5, "mid": 2.0 + 4.0, "high": 1.0 + 3 * 2.0})
    assert idl.planner_delay(p, count_review_half=False) == pytest.approx({"low": 0.0, "mid": 4.0, "high": 6.0})
    with pytest.raises(ValueError):
        idl.planner_delay({"review_weeks": {k: 1.0 for k in SC}, "alpha": {**{k: 0.5 for k in SC}, "mid": 0.0}})


def test_grade_d_planner_range_is_at_least_plus_minus_the_d_halfwidth(cfg):
    hw = cfg["supply_graph"]["min_halfwidth_by_grade"]["D"]
    for k, v in idl.planner_ranges(cfg).items():
        assert v["grade"] == "D", k
        assert v["low"] <= max(v["mid"] * (1 - hw), 0.0) + 1e-9 and v["high"] >= v["mid"] * (1 + hw) - 1e-9


def test_every_lagged_edge_names_known_planners_and_says_why(cfg):
    e = sg.load_edges()
    known = set(cfg["supply_graph"]["info_delay"]["planners"])
    for eid, pl in idl.planners_of(e).items():
        assert set(pl) <= known, eid
    lagged = e[_num(e, "lag_weeks_mid").notna()]
    sellout = lagged["flow"] == "sell_out"
    assert (lagged.loc[~sellout, "info_delay_planner"].str.len() > 0).all()           # every order decision carries a planner
    assert (lagged.loc[sellout, "info_delay_planner"] == "").all()                    # sell-out is the demand: no order decision
    assert (e["info_delay_evidence"].str.len() > 10).all()


def test_signal_is_physical_plus_info_delay_per_edge(cfg):
    phys, _ = sg.effective_ranges(sg.load_edges(), cfg, "physical")
    sig, _ = sg.effective_ranges(sg.load_edges(), cfg, "signal")
    ok = _num(sig, "lag_weeks_mid").notna()
    for sc in SC:
        np.testing.assert_allclose(_num(sig, f"physical_weeks_{sc}")[ok], _num(phys, f"lag_weeks_{sc}")[ok], atol=0.011)
        np.testing.assert_allclose(_num(sig, f"lag_weeks_{sc}")[ok],
                                   (_num(sig, f"physical_weeks_{sc}") + _num(sig, f"info_weeks_{sc}"))[ok], atol=0.02)
    assert (_num(sig, "info_weeks_mid")[ok] >= 0).all()
    e14 = sig.set_index("edge_id").loc["E14"]                                       # mixed edge: the info part is mixed too
    assert float(e14["info_weeks_mid"]) > idl.planner_ranges(cfg)["weekly_replenishment"]["mid"]


def test_littles_law_cap_acts_on_the_physical_part_only(cfg):
    big = copy.deepcopy(cfg)
    big["supply_graph"]["info_delay"]["planners"]["oem_sop"]["review_weeks"] = {k: 40.0 for k in SC}
    sig, _ = sg.effective_ranges(sg.load_edges(), big, "signal")
    bound = sg._bounds(cfg["supply_graph"]["little_law_tolerance"])
    e08 = sig.set_index("edge_id").loc["E08"]
    assert float(e08["physical_weeks_high"]) <= bound["logi_inv_weeks"] + 0.01          # physical still capped by cover (2-dp rounding)
    assert float(e08["lag_weeks_high"]) > bound["logi_inv_weeks"] + 20                 # the info delay is not capped


def test_lag_basis_switch(cfg):
    date = pd.Timestamp("2026-09-01")
    assert cfg["supply_graph"]["lag_basis"] in sg.LAG_BASES
    k_phys, k_sig = sg.kernel_asof(date, cfg, basis="physical"), sg.kernel_asof(date, cfg, basis="signal")
    mean = lambda k: float((k * k.index).sum())                                      # noqa: E731
    assert mean(k_sig) > mean(k_phys)
    alt = copy.deepcopy(cfg)
    alt["supply_graph"]["lag_basis"] = "signal"
    pd.testing.assert_series_equal(sg.kernel_asof(date, alt), k_sig)
    alt["supply_graph"]["lag_basis"] = "physical"
    pd.testing.assert_series_equal(sg.kernel_asof(date, alt), k_phys)
    with pytest.raises(ValueError):
        sg.effective_ranges(sg.load_edges(), cfg, "dwell")


def test_forecasting_path_stays_physical_until_the_lead_switches_it(cfg):
    """G25 / P101: the graph challenger's pre-registration fingerprint does not cover the kernel, so the forecasting basis
    is a deliberate config switch; the lag answer is on the signal basis."""
    assert cfg["supply_graph"]["lag_basis"] == "physical"
    assert cfg["supply_graph"]["lag_answer_basis"] == "signal"


def test_step4_priors_on_signal_basis_are_at_least_the_physical(cfg):
    from edge_priors import priors
    pri = priors(cfg)
    assert (pri["basis"] == "signal").all()
    for k in SC:
        assert (pri[f"prior_{k}"] >= pri[f"prior_phys_{k}"] - 1e-9).all(), k
    assert (pri["prior_mid"] > pri["prior_phys_mid"]).all()


def test_event_study_stays_physical_whatever_the_basis(cfg):
    import event_study as es
    alt = copy.deepcopy(cfg)
    alt["supply_graph"]["lag_basis"] = "signal"
    date = pd.Timestamp("2026-06-25")
    pd.testing.assert_frame_equal(es.lead_paths(cfg, date), es.lead_paths(alt, date))


def test_monte_carlo_is_paired_and_info_delay_only_adds(cfg):
    import signal_lag as sl
    small = copy.deepcopy(cfg)
    small["supply_graph"]["mc_draws"] = 25
    d = sl.monte_carlo(small, pd.Timestamp("2026-09-01"), seed=1)
    w = d.pivot(index="draw", columns="basis", values="all routes (flow-weighted)")
    assert (w["signal"] >= w["physical"] - 1e-9).all()
    bands = sl.mc_bands(d).set_index(["basis", "route"])
    assert bands.loc[("info delay (signal - physical)", "all routes (flow-weighted)"), "p5"] >= 0


def test_nothing_mutates_config_or_edges(cfg):
    import signal_lag as sl
    cfg0, edges = copy.deepcopy(cfg), sg.load_edges()
    edges0 = edges.copy()
    sg.effective_ranges(edges, cfg, "signal")
    idl.planner_ranges(cfg)
    sl.route_table(cfg, pd.Timestamp("2026-09-01"))
    assert cfg == cfg0
    pd.testing.assert_frame_equal(edges, edges0)
