"""Step 5f route-proxy nowcast (G27): point in time by release date, fiscal overlap, walk-forward, adoption rule, no mutation."""
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

import route_nowcast as rn  # noqa: E402
import route_nowcast_data as rnd  # noqa: E402
import route_nowcast_nordic as rnn  # noqa: E402
import route_nowcast_scores as sc  # noqa: E402

QUARTERS = ["2024Q3", "2025Q4", "2026Q3"]


@pytest.fixture(scope="module")
def data():
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    return cfg, p, rn.sources(p, cfg)


def _scramble(S: dict, at: pd.Timestamp) -> dict:
    """Every value first published after `at` replaced by an absurd number (new frames)."""
    out = {}
    for k, t in S.items():
        late = pd.to_datetime(t["release_date"]) > at
        out[k] = t.assign(value=np.where(late, 1e6, t["value"]))
    return out


@pytest.mark.parametrize("q", QUARTERS)
def test_scrambling_post_origin_data_changes_nothing(data, q):
    cfg, _, S = data
    q = pd.Period(q, "Q")
    S2 = _scramble(S, rnd.origin(q, cfg))
    for m in cfg["route_nowcast"]["models"]:
        a, b = rn.nowcast(S, q, cfg, m), rn.nowcast(S2, q, cfg, m)
        assert a["value"] == pytest.approx(b["value"], nan_ok=True), m


def test_a_value_released_after_the_origin_is_never_read(data):
    cfg, _, S = data
    for q in (pd.Period(x, "Q") for x in QUARTERS):
        at = rnd.origin(q, cfg)
        for name, spec in cfg["route_nowcast"]["proxies"].items():
            r = rn.x_pit(S[name], spec["source"], q, cfg)
            if np.isfinite(r["value"]):
                assert pd.Timestamp(r["release_date"]) <= at, (name, q)
        assert q not in rn.series(rn.vintage(S, at)["logitech"]).index        # Logitech's own quarter is never known


def test_calendar_reporters_are_excluded_by_the_rule(data):
    cfg, p, S = data
    from route_nowcast_availability import availability
    av = availability(p, cfg, S, pd.Period(cfg["route_nowcast"]["live_quarter"], "Q")).set_index(["source", "period"])
    for src in ("amazon", "ingram", "cdw", "logitech"):
        assert not av.xs(src, level="source")["available_at_origin"].any(), src
    assert av.xs("tdsynnex", level="source")["available_at_origin"].all()
    rs = av.xs("rseas", level="source")["available_at_origin"]
    assert list(rs.values) == [True, True, False]                                   # months 1-2 of the quarter, not month 3


def test_fiscal_quarter_overlap_mapping(data):
    cfg, _, S = data
    q3 = pd.Period("2026Q3", "Q")
    assert rnd.month_end(q3, cfg["route_nowcast"]["tdsynnex_period_end_month"]) == pd.Timestamp("2026-08-31")
    assert rnd.overlap_months(pd.Timestamp("2026-08-31"), q3) == 2                 # TD Synnex Jun-Aug: Jul, Aug
    assert rnd.overlap_months(pd.Timestamp("2026-08-01"), q3) == 1                 # Best Buy May-Jul (4-5-4, ends 1 Aug): Jul
    assert rnd.overlap_months(pd.Timestamp("2026-08-01"), q3 - 1) == 2
    bby = rnd.latest_overlapping(S["bestbuy_computing"], q3, rnd.origin(q3, cfg))
    assert bby["label"] == "2026Q2" and bby["overlap"] == 1                        # the Aug-Oct quarter is filed in late Nov
    snx = rnd.latest_overlapping(S["snx_sales"], q3, rnd.origin(q3, cfg))
    assert snx["label"] == "2026Q3" and snx["overlap"] == 2


def test_proxy_model_is_persistence_until_it_has_enough_history(data):
    cfg, _, S = data
    q = pd.Period(cfg["route_nowcast"]["first_train_quarter"], "Q") + 1
    r, n0 = rn.nowcast(S, q, cfg, "N2c"), rn.nowcast(S, q, cfg, "N0")
    assert r["b"] == 0.0 and not r["fitted"] and r["value"] == pytest.approx(n0["value"])
    assert rn.fit_slope(pd.Series([1.0, 2.0]), pd.Series([1.0, 1.0]), 6) == (0.0, 2)


def test_graph_demand_matches_step6_designs(data):
    cfg, p, _ = data
    from walkforward import design, logitech_guided_demand
    kc = rnn.KernelCache(cfg)
    D = p[cfg["route_nowcast"]["target"]].sum(axis=1, min_count=2)
    gr = rnn.graph_demand(D, None, 2, kc)
    grg = rnn.graph_demand(D, logitech_guided_demand(p), 2, kc)
    assert np.nanmax((gr - design(p, "GR", cfg, None, 2)["graph_demand"]).abs()) < 1e-9
    assert np.nanmax((grg - design(p, "GRg", cfg, None, 2)["graph_demand"]).abs()) < 1e-9


def test_nowcast_ahead_holds_only_the_unreported_quarter():
    D = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.period_range("2025Q1", periods=4, freq="Q"))
    t = pd.Period("2025Q4", "Q")
    k = pd.Series([0.5, 0.5], index=[0, 1])                                         # a lag-0 weight (the low scenario)
    ahead = {t - 1: 9.0}
    assert rnn.graph_demand_at(D, t, 2, k, ahead) == pytest.approx(9.0)            # lag 0 reads the t-1 nowcast, never a forecast of t


def test_adoption_needs_nowcast_evidence_and_never_takes_the_guide(data):
    cfg, _, _ = data
    ns = pd.DataFrame([{"scope": "own quarters", "model": m, "rmse_ratio": 0.9, "dm_t": -1.0, "enc_t": 1.0}
                       for m in ("N2c", "N2s")])
    nd = pd.DataFrame([{"forecast": "GR", "model": m, "rmse_ratio": 0.8} for m in ("N2c", "N2s")])
    assert sc.adoption(ns, nd, cfg)["verdict"].iloc[0] == "N0"                      # lower RMSE alone is not enough
    ns2 = ns.assign(dm_t=[-2.5, -1.0])
    assert sc.adoption(ns2, nd, cfg)["verdict"].iloc[0] == "N2c"
    assert "N1" not in cfg["route_nowcast"]["adoption"]["candidates"]


def test_run_does_not_mutate_config_and_preregisters_no_guide(data):
    cfg, p, _ = data
    import route_nowcast_report as rr
    before = copy.deepcopy(cfg)
    res = rr.run(p, cfg)
    assert cfg == before
    rows = rr.prereg_rows(res, cfg)
    assert {r["model"] for r in rows}.isdisjoint(cfg["route_nowcast"]["adoption"]["comparison_only"])
    assert cfg["route_nowcast"]["adoption"]["default"] in {r["model"] for r in rows}
    assert max(res["checks"].values()) < 1e-9
