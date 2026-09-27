"""Step 5 supply graph: shares, point-in-time weights, kernel, propagation. Run: pytest -q tests/test_step5.py"""
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
import supply_graph as sg  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config(None)


@pytest.mark.parametrize("scenario", ["low", "mid", "high"])
def test_outflow_shares_sum_to_one_per_node_and_brand(cfg, scenario):
    e = sg.load_edges()
    s = sg.edge_shares(e, cfg, "2026-09-26", scenario)
    flow = e.assign(share=s.reindex(e["edge_id"]).values).dropna(subset=["share"])
    for brand in ("logitech", "gn"):
        for src, g in flow[flow["brand"].isin([brand, "all"])].groupby("src"):
            if src == "gn" and brand == "logitech" or src in ("logitech", "suzhou") and brand == "gn":
                continue                                       # the other brand's node
            assert g["share"].sum() == pytest.approx(1.0), (brand, src)


def test_paths_weights_sum_to_one_and_kernel_is_a_distribution(cfg):
    e = sg.load_edges()
    pt = sg.paths(e, sg.edge_shares(e, cfg, "2026-09-26"), cfg)
    assert pt["weight"].sum() == pytest.approx(1.0)
    k = sg.kernel(pt, cfg)
    assert k.sum() == pytest.approx(1.0) and (k >= 0).all()


def test_weights_are_point_in_time():
    w = sg.load_weights()
    for r in w.itertuples():
        day_before = pd.Timestamp(r.published) - pd.Timedelta(days=1)
        assert sg.weights_asof(day_before)["fiscal_year"] < r.fiscal_year or r.Index == 0      # not visible before filing
        assert sg.weights_asof(r.published)["fiscal_year"] == r.fiscal_year


def test_weights_come_with_their_10k_sentence():
    w = sg.load_weights()
    for k in ("amazon", "ingram", "tdsynnex"):
        for share, quote in zip(w[k], w[f"quote_{k}"]):
            assert f"{round(share * 100)}" in quote.replace(" ", "")


def test_propagation_of_a_constant_is_that_constant_and_h_pushes_mass_to_known_lags(cfg):
    q = pd.period_range("2022Q1", "2026Q2", freq="Q")
    D = pd.Series(5.0, index=q)
    assert np.allclose(sg.propagate(D, cfg).dropna(), 5.0)
    D2 = pd.Series(np.arange(len(q), dtype=float), index=q)
    r2 = sg.propagate(D2, cfg, h=2)
    t = q[-1]
    assert r2[t] == pytest.approx(D2[t - 2])          # the mid kernel sits on lags 1-2: at h=2 all of it is the latest known value


def test_every_edge_has_valid_grades_and_every_d_says_why():
    e = sg.load_edges()
    assert set(e["share_grade"]) <= set("ABCD") and set(e["lag_grade"]) <= set("ABCD")
    for g, av, ev in [(r.share_grade, r.share_availability, r.evidence) for r in e.itertuples()] + \
                     [(r.lag_grade, r.lag_availability, r.lag_evidence) for r in e.itertuples()]:
        assert av in {"collected", "not_public", "not_collected"}
        if g == "D":
            assert av in {"not_public", "not_collected"} and ev          # a D must say whether the data exist, and why
        else:
            assert av == "collected" and ev                             # an A-C must cite its source


def test_lag_ranges_respect_inventory_cover(cfg):
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from core.ingest import load_all
    from core.tiers import build_panel
    from supply_graph_report import lag_anchors, lag_checks
    p = build_panel(load_all(), cfg)
    c = lag_checks(sg.load_edges(), lag_anchors(p), cfg["supply_graph"]["little_law_tolerance"])
    assert len(c) >= 8 and (c["check"] == "ok").all(), c[c["check"] != "ok"]


def test_monte_carlo_band_contains_the_mid(cfg):
    from supply_graph_report import monte_carlo, _mean_lag
    import copy
    e = sg.load_edges()
    c2 = copy.deepcopy(cfg)
    c2["supply_graph"]["mc_draws"] = 60
    m = monte_carlo(e, c2)["mean_lag_weeks"]
    mid, _ = _mean_lag(e, cfg, {k: v["mid"] for k, v in cfg["supply_graph"]["params"].items()},
                       pd.to_numeric(e["lag_weeks_mid"], errors="coerce").fillna(0).values)
    assert m["p5"] <= mid <= m["p95"]


def test_ranges_widen_with_weaker_support(cfg):
    """Grade = data support, not level: a D lag's effective range is at least +/-100% of its mid, a C lag +/-50% unless a
    data bound (inventory cover) cuts the top; named shares keep their filing floors / caps."""
    e, prm = sg.effective_ranges(sg.load_edges(), cfg)
    hw = cfg["supply_graph"]["min_halfwidth_by_grade"]
    for r in e.itertuples():
        mid = pd.to_numeric(r.lag_weeks_mid, errors="coerce")
        if pd.isna(mid) or mid == 0:
            continue
        lo, hi = float(r.lag_weeks_low), float(r.lag_weeks_high)
        assert lo <= mid * (1 - hw[r.lag_grade]) + 1e-9
        if not r.lag_anchor:
            assert hi >= mid * (1 + hw[r.lag_grade]) - 1e-9
    assert prm["gn_distrib"]["low"] >= 0.21 and prm["gn_amazon"]["high"] <= 0.175 and prm["dist"]["low"] >= 0.42


def test_a_known_forecast_of_an_unreported_quarter_replaces_persistence(cfg):
    """h=2 with Logitech's own guide for t-1 (known at the origin): lags 0-1 read the guided value, lag 2 the actual, so
    the split of the kernel between lags 1 and 2 (i.e. the edge lags) moves the result."""
    q = pd.period_range("2022Q1", "2026Q2", freq="Q")
    D = pd.Series(np.arange(len(q), dtype=float), index=q)
    t = q[-1]
    ahead = pd.Series({t - 1: 100.0})
    r = sg.propagate(D, cfg, h=2, ahead=ahead)[t]
    k = sg.kernel_asof(t.end_time, cfg)
    expected = k.loc[:1].sum() * 100.0 + sum(k.loc[j] * D[t - j] for j in k.index if j >= 2)
    assert r == pytest.approx(expected)
    assert r != pytest.approx(D[t - 2])
    lo = sg.propagate(D, cfg, h=2, ahead=ahead, scenario="low")[t]
    hi = sg.propagate(D, cfg, h=2, ahead=ahead, scenario="high")[t]
    assert lo != pytest.approx(hi)                    # the lag scenario now reaches the forecast


def test_without_a_known_forecast_nothing_changes(cfg):
    q = pd.period_range("2022Q1", "2026Q2", freq="Q")
    D = pd.Series(np.arange(len(q), dtype=float), index=q)
    pd.testing.assert_series_equal(sg.propagate(D, cfg, h=2), sg.propagate(D, cfg, h=2, ahead=pd.Series(dtype=float)))


def test_step4_check_stages_add_up():
    """Upstream + downstream weeks per path equal the path's lag; the check changes no edge."""
    import pandas as pd
    from core.config import load_config
    from supply_graph import load_edges, effective_ranges, edge_shares, paths
    from step4_check import stage_lags
    cfg = load_config()
    e, _ = effective_ranges(load_edges(), cfg)
    before = e.copy()
    pt = paths(e, edge_shares(e, cfg, pd.Timestamp.today()), cfg)
    st = stage_lags(e, pt)
    assert (st["upstream"] + st["downstream"]).round(6).tolist() == pt["lag_weeks"].round(6).tolist()
    pd.testing.assert_frame_equal(e, before)


def test_residual_lag_mix():
    """E14's lag is (1-p) x its own lag + p x the Ingram / TD Synnex downstream lag, per scenario; other edges unchanged."""
    import pandas as pd
    from core.config import load_config
    from supply_graph import load_edges, effective_ranges
    cfg = load_config()
    raw = load_edges()
    mixed, prm = effective_ranges(raw, cfg)
    plain = effective_ranges(raw.drop(columns="lag_mix"), cfg)[0]
    L = {sc: dict(zip(plain["edge_id"], pd.to_numeric(plain[f"lag_weeks_{sc}"]))) for sc in ("low", "mid", "high")}
    for sc in ("low", "mid", "high"):
        p = prm["logi_residual_via_dist"][sc]
        via = ((L[sc]["E12"] + L[sc]["E15"]) + (L[sc]["E13"] + L[sc]["E17"])) / 2
        got = float(pd.to_numeric(mixed.loc[mixed["edge_id"] == "E14", f"lag_weeks_{sc}"]).iloc[0])
        assert got == pytest.approx((1 - p) * L[sc]["E14"] + p * via, abs=0.01)
    others = mixed["edge_id"] != "E14"
    assert mixed.loc[others, "lag_weeks_mid"].tolist() == plain.loc[others, "lag_weeks_mid"].tolist()


def test_gap_decomposition_adds_up_to_the_total_gap(cfg):
    """G21: the route-group contributions sum to graph total - step 4 mid (as in graph_vs_step4.csv); no edge changed."""
    from supply_graph import load_edges, effective_ranges, edge_shares, paths
    from gap_decomposition import decompose
    raw = load_edges()
    before = raw.copy()
    eff = effective_ranges(raw, cfg)[0]
    pt = paths(eff, edge_shares(raw, cfg, pd.Timestamp("2026-09-26")), cfg)
    d = decompose(raw, eff, pt, cfg)
    groups, total = d.iloc[:-1], d.iloc[-1]
    step4_mid = sum(v["mid"] for v in cfg["lag_weeks"].values())
    graph = float(np.average(pt["lag_weeks"], weights=pt["weight"]))
    assert groups["contribution_weeks"].sum() == pytest.approx(graph - step4_mid, abs=0.01)
    assert total["contribution_weeks"] == pytest.approx(graph - step4_mid, abs=0.01)
    rows = groups.dropna(subset=["flow_share"])
    assert (rows["flow_share"] * (rows["graph_weeks"] - rows["reference_weeks"])).round(6).tolist() == rows["contribution_weeks"].round(6).tolist()
    pd.testing.assert_frame_equal(raw, before)


def test_lagged_interpolates_between_integer_lags():
    from continuous_lag import lagged
    x = pd.Series(np.arange(10.0) ** 2, index=pd.period_range("2020Q1", periods=10, freq="Q"))
    assert lagged(x, 2.0).equals(x.shift(2))
    assert np.allclose(lagged(x, 1.25).dropna(), (0.75 * x.shift(1) + 0.25 * x.shift(2)).dropna())


def test_continuous_lag_recovers_a_known_fractional_lag(cfg):
    """y is x delayed by 1.4 quarters (same interpolation) plus noise: the estimate lands within 0.15 quarters."""
    from continuous_lag import common_axis, estimate, lagged, tau_grid
    lc = cfg["supply_graph"]["lag_check"]
    rng = np.random.default_rng(7)
    t = np.arange(48)
    x = pd.Series(10 * np.sin(2 * np.pi * t / 14) + 5 * np.sin(2 * np.pi * t / 9 + 1) + rng.normal(0, 1, t.size),
                  index=pd.period_range("2012Q1", periods=t.size, freq="Q"))
    y = lagged(x, 1.4) + rng.normal(0, 0.5, t.size)
    axis = common_axis(y, [x], x.index, tau_grid(lc))
    assert abs(estimate(y, x, axis, lc)["tau_q"] - 1.4) <= 0.15


def test_block_bootstrap_is_seeded_and_made_of_blocks(cfg):
    from continuous_lag import block_indices, common_axis, estimate, tau_grid
    a, b = block_indices(17, 4, 500, seed=21), block_indices(17, 4, 500, seed=21)
    assert np.array_equal(a, b) and not np.array_equal(a, block_indices(17, 4, 500, seed=22))
    assert a.shape == (500, 17) and a.min() >= 0 and a.max() <= 16
    blocks = a[:, :16].reshape(500, 4, 4)
    assert (np.diff(blocks, axis=2) == 1).all()                       # consecutive quarters inside each block
    lc = {**cfg["supply_graph"]["lag_check"], "boot_draws": 300}
    x = pd.Series(np.sin(np.arange(30) / 2.0), index=pd.period_range("2015Q1", periods=30, freq="Q"))
    y = x.shift(2) + 0.1 * np.cos(np.arange(30))
    axis = common_axis(y, [x], x.index, tau_grid(lc))
    idx = block_indices(len(axis), lc["block_len"], lc["boot_draws"], lc["seed"])
    assert np.array_equal(estimate(y, x, axis, lc, idx)["boot"], estimate(y, x, axis, lc, idx)["boot"], equal_nan=True)


def test_integer_lag_on_white_noise_is_recovered_and_inside_its_near_optimal_set(cfg):
    """True lag an integer (2 quarters), x white noise: interpolating between lags gives no smoothing advantage (a 2-tap
    average of white noise only dilutes the match), so the point lands within 0.15 q of 2 and the near-optimal set (P86)
    contains the point."""
    from continuous_lag import common_axis, estimate, tau_grid
    lc = cfg["supply_graph"]["lag_check"]
    rng = np.random.default_rng(11)
    x = pd.Series(rng.normal(0, 1, 80), index=pd.period_range("2006Q1", periods=80, freq="Q"))
    y = x.shift(2) + rng.normal(0, 0.3, 80)
    axis = common_axis(y, [x], x.index, tau_grid(lc))
    e = estimate(y, x, axis, lc)
    assert abs(e["tau_q"] - 2.0) <= 0.15
    assert e["near_lo_q"] <= e["tau_q"] <= e["near_hi_q"]
    assert e["near_hi_q"] - e["near_lo_q"] < 1.0                      # a sharp peak gives a narrow set


def test_near_optimal_set_is_every_tau_within_the_gap():
    from continuous_lag import near_optimal
    curve = pd.Series([0.50, 0.88, 0.90, 0.86, 0.89, np.nan], index=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5])
    assert near_optimal(curve, 0.03) == {"near_lo_q": 0.5, "near_hi_q": 2.0, "near_contiguous": False}
    assert near_optimal(pd.Series([np.nan, np.nan]), 0.03)["near_contiguous"] is None


@pytest.mark.parametrize("h", [0, 1, 2])
def test_propagate_is_causal(h):
    """Demand-shock rule (G24): graph demand at t uses demand dated t-h or earlier only. Scrambling everything after t-h
    (and t itself) must not move R(t); a dated supply shock goes through the event study instead (G23)."""
    import numpy as np
    import pandas as pd
    from core.config import load_config
    from supply_graph import propagate
    cfg = load_config()
    idx = pd.period_range("2019Q1", "2026Q4", freq="Q")
    D = pd.Series(np.sin(np.arange(len(idx)) / 2.0) * 10, index=idx)
    t = pd.Period("2025Q3", "Q")
    base = propagate(D, cfg, h)[t]
    moved = D.copy()
    moved[moved.index > t - h] = 999.0
    assert propagate(moved, cfg, h)[t] == pytest.approx(base)
