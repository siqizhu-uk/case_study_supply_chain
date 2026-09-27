"""Step 4 edge-by-edge lag (decisions L4-L9): estimators recover known lags on synthetic data, the posterior rule, totals."""
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
import edge1_channel as e1  # noqa: E402
import edge2_constrained as e2  # noqa: E402
from edge_posterior import combine, posterior, route_total, totals  # noqa: E402
from edge_priors import priors  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def _ar1(rho: float, n: int, seed: int, trend: float = 0.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = np.zeros(n + 50)
    for i in range(1, n + 50):
        d[i] = rho * d[i - 1] + rng.standard_normal()
    return d[50:] + trend * np.arange(n)


def test_edge1_ols_recovers_rho_on_long_ar1_with_trend():
    d = _ar1(0.5, 2000, seed=1, trend=0.01)
    assert abs(float(e1.ols_rho(d, trend=True)) - 0.5) < 0.05


def test_edge1_lag_formula():
    assert float(e1.weeks(np.exp(-13 / 5.0), 13)) == pytest.approx(5.0)          # continuous: rho = exp(-13 / T)
    assert float(e1.weeks(0.5, 13, "koyck")) == pytest.approx(13.0)             # Koyck: rho / (1 - rho) quarters
    assert float(e1.weeks(-0.2, 13)) == 0.0 and np.isinf(e1.weeks(1.0, 13))


def test_edge1_median_unbiased_inverts_the_simulated_median(cfg):
    mu = cfg["edge_lags"]["edge1"]["median_unbiased"]
    grid, q = e1.simulated_quantiles(14, True, mu)
    at = int(np.argmin(np.abs(grid - 0.6)))
    est = e1.median_unbiased(float(q[at, 1]), 14, True, mu)
    assert est["rho"] == pytest.approx(0.6, abs=0.03)
    assert q[at, 1] < 0.6                                   # OLS median is biased towards zero at n 14 with a trend
    assert est["rho_lo"] < est["rho"] < est["rho_hi"]


def test_edge2_constrained_recovers_tau_with_a_common_factor(cfg):
    rng = np.random.default_rng(3)
    idx = pd.period_range("2010Q1", periods=60, freq="Q")
    f = pd.Series(np.cumsum(rng.standard_normal(60)) * 3, index=idx)            # common cycle
    x = pd.Series(rng.standard_normal(60) * 10, index=idx) + 0.5 * f           # brand sell-in shares the cycle
    w = f + pd.Series(rng.standard_normal(60) * 0.5, index=idx)                # cycle control
    from continuous_lag import lagged
    y = 1.0 * lagged(x, 1.5) + 2.0 * w + pd.Series(rng.standard_normal(60) * 0.5, index=idx)
    lc = {**cfg["supply_graph"]["lag_check"], "boot_draws": 200}
    x0, y0 = x.copy(), y.copy()
    r = e2.constrained(y, x, w, idx, 1.0, lc, 2.706)
    assert r["tau_q"] == pytest.approx(1.5, abs=0.1)
    assert r["set_share"] < 0.25 and r["ci_lo_q"] <= 1.5 <= r["ci_hi_q"]
    pd.testing.assert_series_equal(x, x0)
    pd.testing.assert_series_equal(y, y0)                                        # inputs not mutated


def test_posterior_is_prior_when_estimate_uninformative():
    prior = {"mid": 14.0, "sd": 4.0, "low": 7.0, "high": 21.0}
    for est in ({"mid": 13.0, "lo": 0.0, "hi": 52.0, "coverage": 1.0}, {"mid": 28.0, "lo": 0.0, "hi": np.inf, "coverage": 0.0}, None):
        post = posterior(prior, est, 0.75)
        assert (post["post_mid"], post["post_sd"], post["moved_by_weeks"]) == (14.0, 4.0, 0.0) and not post["informative"]


def test_posterior_precision_weights_an_informative_estimate():
    prior = {"mid": 10.0, "sd": 2.0, "low": 6.7, "high": 13.3}
    est = {"mid": 20.0, "lo": 20 - 2 * 1.6449, "hi": 20 + 2 * 1.6449, "coverage": 0.1}    # estimate sd = 2
    post = posterior(prior, est, 0.75)
    assert post["post_mid"] == pytest.approx(15.0) and post["post_sd"] == pytest.approx(2 ** 0.5)


def test_totals_add_up_along_routes(cfg):
    pri = priors(cfg)
    post = combine(pri, {}, 0.75)
    tot = totals(post, 5000, 1).set_index("route")
    ix = post.set_index(["edge", "brand", "route"])
    a = tot.loc["Amazon -> Logitech -> Nordic"]
    want = ix.loc[("edge 1", "logitech", "Amazon direct"), "post_mid"] + ix.loc[("edge 2", "logitech", "all routes (flow-weighted)"), "post_mid"]
    assert a["total_weeks"] == pytest.approx(want)
    assert a["sim_p5_weeks"] < a["total_weeks"] < a["sim_p95_weeks"]
    assert a["comonotone_low_weeks"] <= a["sim_p5_weeks"] and a["sim_p95_weeks"] <= a["comonotone_high_weeks"]
    r = route_total({"post_mid": 3.0, "post_sd": 1.0, "post_low": 1.4, "post_high": 4.6},
                    {"post_mid": 14.0, "post_sd": 4.0, "post_low": 7.4, "post_high": 20.6}, 20000, 2)
    assert r["total_weeks"] == 17.0


def test_priors_come_from_the_graph_and_are_ordered(cfg):
    cfg0 = copy.deepcopy(cfg)
    pri = priors(cfg)
    assert len(pri) == 8 and (pri["prior_low"] <= pri["prior_mid"]).all() and (pri["prior_mid"] <= pri["prior_high"]).all()
    amazon = pri[(pri["edge"] == "edge 1") & (pri["brand"] == "logitech") & (pri["route"] == "Amazon direct")].iloc[0]
    edges = pd.read_csv(ROOT / "config" / "supply_graph.csv").set_index("edge_id")
    assert amazon["prior_phys_mid"] == pytest.approx(float(edges.loc["E11", "lag_weeks_mid"]))    # Amazon direct = edge E11
    from info_delay import planner_ranges                                   # signal basis (G25): + Amazon's weekly replenishment
    info = planner_ranges(cfg)[edges.loc["E11", "info_delay_planner"]]["mid"]
    assert amazon["prior_mid"] == pytest.approx(float(edges.loc["E11", "lag_weeks_mid"]) + info)
    assert cfg == cfg0
