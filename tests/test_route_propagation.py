"""Step 5e route-level propagation (G26): reconciliation, shrink 0 = aggregate CH, point in time, no mutation."""
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

from core.config import load_config  # noqa: E402
from core.ingest import load_all  # noqa: E402
from core.tiers import build_panel  # noqa: E402

import route_demand as rd  # noqa: E402
import route_propagation as rp  # noqa: E402

ORIGINS = ["2023Q4", "2025Q1", "2026Q2"]


@pytest.fixture(scope="module")
def data():
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    return cfg, p, rd.total_demand(p, cfg), rd.load_route_proxies(p)


def _weights(cfg, origin):
    rk = rp.route_kernels(rp.origin_date(pd.Period(origin, "Q") + 1, 1), cfg)
    return rp.logitech_weights(rk, cfg)


@pytest.mark.parametrize("origin", ORIGINS)
@pytest.mark.parametrize("method", ["zscore", "demean", "none"])
def test_weighted_route_demand_equals_the_total(data, origin, method):
    cfg, _, total, px = data
    long = rd.route_demand_asof(total, px, cfg, pd.Period(origin, "Q"), _weights(cfg, origin), method=method)
    assert rd.reconciliation_error(long) < 1e-9
    assert long["quarter"].max() <= origin                       # nothing after the origin


def test_route_kernels_add_up_to_the_aggregate_kernel(data):
    cfg = data[0]
    rk = rp.route_kernels(pd.Timestamp("2026-07-21"), cfg)
    assert rk["check"] < 1e-12
    assert set(rk["kernels"]) == set(cfg["route_propagation"]["routes"]) | {"gn"}
    assert rk["mass"].sum() == pytest.approx(1.0)


@pytest.mark.parametrize("h", [1, 2])
def test_shrink_zero_reproduces_the_aggregate_ch(data, h):
    from walkforward import design                               # step 6: what step 7c's CH reads
    cfg, p, total, px = data
    gr = design(p, "GR", cfg, None, h)["graph_demand"]
    kc = rp._KernelCache(cfg)
    for t in rp.targets(p, cfg, h):
        g = rp.route_slice_demand(total, px, cfg, t, h, kc, shrink=0.0)["slice_demand"]
        assert g == pytest.approx(gr[t], abs=1e-9), t


def test_route_split_is_identical_when_every_kernel_lag_is_at_or_below_h(data):
    """The prior of G26: with the total pinned, routes act only through kernel differences; at lags <= h they vanish."""
    cfg, p, total, px = data
    kc = rp._KernelCache(cfg)
    h = 2
    for t in rp.targets(p, cfg, h)[-4:]:
        rk = kc(rp.origin_date(t, h))
        if max(int(k.index[k > 0].max()) for k in rk["kernels"].values()) > h:
            continue                                            # a lag basis with weight beyond h: no identity to test
        g = rp.route_slice_demand(total, px, cfg, t, h, kc)["slice_demand"]
        g0 = rp.route_slice_demand(total, px, cfg, t, h, kc, shrink=0.0)["slice_demand"]
        assert g == pytest.approx(g0, abs=1e-9)


@pytest.mark.parametrize("h,t", [(1, "2025Q3"), (1, "2026Q2"), (2, "2025Q4"), (2, "2026Q2")])
def test_point_in_time_data_after_the_origin_is_never_read(data, h, t):
    cfg, _, total, px = data
    t = pd.Period(t, "Q")
    rng = np.random.default_rng(1)
    late_t, late_p = total.index > t - h, px.index > t - h
    total_s = total.where(~late_t, rng.normal(50, 30, len(total)))
    px_s = px.where(~pd.DataFrame(np.repeat(late_p[:, None], px.shape[1], 1), index=px.index, columns=px.columns),
                    rng.normal(50, 30, px.shape))
    a = rp.route_slice_demand(total, px, cfg, t, h)
    b = rp.route_slice_demand(total_s, px_s, cfg, t, h)
    assert a["slice_demand"] == pytest.approx(b["slice_demand"], abs=1e-12)
    pd.testing.assert_frame_equal(a["long"], b["long"])
    c = rp.route_slice_demand(total.where(total.index != t - h, total[t - h] + 10), px, cfg, t, h)
    assert c["slice_demand"] != pytest.approx(a["slice_demand"])      # the origin quarter itself IS read (test not vacuous)


def test_missing_proxy_takes_the_total_and_short_history_is_ignored(data):
    cfg = data[0]
    idx = pd.period_range("2024Q1", "2026Q2", freq="Q")
    total = pd.Series(np.linspace(1, 10, len(idx)), index=idx)
    px = pd.DataFrame({c: np.linspace(0, 9, len(idx)) + i for i, c in enumerate(
        ["amazon_revenue_yoy", "ingm_ces_yoy", "snx_endpoint_yoy", "bestbuy_computing_comp"])}, index=idx)
    px.loc[idx[-1], "amazon_revenue_yoy"] = np.nan                 # one quarter missing
    px.loc[idx[:-3], "ingm_ces_yoy"] = np.nan                      # 3 quarters: below min_obs
    w = {"amazon": 0.2, "ingram": 0.15, "tdsynnex": 0.15, "other_retail": 0.5}
    long = rd.route_demand_asof(total, px, cfg, idx[-1], w)
    last = long[long["quarter"] == str(idx[-1])].set_index("route")
    assert last.loc["amazon", "deviation"] == 0.0 and last.loc["amazon", "demand"] == pytest.approx(total.iloc[-1])
    assert (long.loc[long["route"] == "ingram", "deviation"] == 0.0).all()
    assert rd.reconciliation_error(long) < 1e-9


def test_config_and_inputs_are_not_mutated(data):
    cfg, _, total, px = data
    cfg0, px0, total0 = copy.deepcopy(cfg), px.copy(), total.copy()
    rp.route_slice_demand(total, px, cfg, pd.Period("2026Q3", "Q"), 1)
    rd.asp_adjusted(px, cfg)
    assert cfg == cfg0
    pd.testing.assert_frame_equal(px, px0)
    pd.testing.assert_series_equal(total, total0)


def test_asp_tailwind_cuts_distributor_dollars_only_from_2026(data):
    cfg, _, _, px = data
    adj = rd.asp_adjusted(px, cfg)
    pts = cfg["structural_breaks"]["distributor_asp_inflation_2026"]["asp_tailwind_pts"]
    q = pd.Period("2026Q2", "Q")
    assert adj.loc[q, "snx_endpoint_yoy"] == pytest.approx(px.loc[q, "snx_endpoint_yoy"] - pts)
    assert adj.loc[q, "amazon_revenue_yoy"] == pytest.approx(px.loc[q, "amazon_revenue_yoy"])
    assert adj.loc[pd.Period("2025Q4", "Q"), "ingm_ces_yoy"] == pytest.approx(px.loc[pd.Period("2025Q4", "Q"), "ingm_ces_yoy"])


def test_route_vs_gr_same_quarters():
    """CH-route, CH-aggregate, GR and GB are scored on identical quarters; GR's ratio to itself is 1; both encompassing
    directions are reported per horizon."""
    import pandas as pd
    from core.config import ROOT
    v = pd.read_csv(ROOT / "steps" / "step5_supply_graph" / "outputs" / "route_vs_gr.csv")
    for h, g in v.groupby("horizon"):
        models = g.dropna(subset=["rmse_usdm"])
        assert models["n"].nunique() == 1 and models["first"].nunique() == 1
        assert models.set_index("model").loc["GR (step 6)", "rmse_ratio_vs_GR"] == pytest.approx(1.0)
        assert {"encompassing: CH-route adds to GR", "encompassing: GR adds to CH-route"} <= set(g["model"])
