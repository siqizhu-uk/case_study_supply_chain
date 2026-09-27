"""Step 6 walk-forward back-test: leakage tests. Run: pytest -q tests/test_step6.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))


# ------------------------------------------------------------------ step 6 walk-forward (no look-ahead)
def test_walkforward_uses_no_future_data():
    """Scramble every value dated >= t: the forecast for t must not move (the canonical leakage test)."""
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from walkforward import design, forecast_row
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    for h in (1, 2):
        t = pd.Period("2025Q3", "Q")
        models = ["L6", "L3"]
        base = forecast_row(p, cfg, {m: design(p, m, cfg, None, h) for m in models}, t, h, False)
        q = p.copy()
        future = q.index >= t - h + 1
        num = q.select_dtypes("number").columns.drop("nordic_guide_mid")      # guidance for the guided quarter is known
        q.loc[future, num] = q.loc[future, num] * 7.0 + 123.0
        if h == 1:
            q.loc[t, "nordic_guide_mid"] = p.loc[t, "nordic_guide_mid"]
        pert = forecast_row(q, cfg, {m: design(q, m, cfg, None, h) for m in models}, t, h, False)
        for m in models:
            assert pert[f"{m}_yoy"] == pytest.approx(base[f"{m}_yoy"]), (h, m)


def test_leaky_variant_is_detected():
    """The old specification (distributor state of the target quarter) DOES move when the future is scrambled."""
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from walkforward import design, forecast_row
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    t = pd.Period("2025Q3", "Q")
    base = forecast_row(p, cfg, {"L6leak": design(p, "L6leak", cfg, None, 1)}, t, 1, False)
    q = p.copy()
    q.loc[t, "nordic_dist_state"] = -1.0
    pert = forecast_row(q, cfg, {"L6leak": design(q, "L6leak", cfg, None, 1)}, t, 1, False)
    assert pert["L6leak_yoy"] != pytest.approx(base["L6leak_yoy"])


# ------------------------------------------------------------------ step 6c composite
def test_expanding_z_uses_only_the_past():
    from composite import expanding_z
    x = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0], index=pd.period_range("2020Q1", periods=5, freq="Q"))
    z = expanding_z(x, 3)
    assert z.iloc[3] == pytest.approx((4 - 2) / 1.0)          # mean/sd of 1,2,3 only
    assert z.iloc[:3].isna().all()


def test_global_sign_flip_gives_identical_forecasts():
    """Flipping every sign only flips b, so the forecasts are the same: why only 2^(K-1) sign combinations are distinct."""
    import numpy as np
    from composite import composite, wf_linear
    idx = pd.period_range("2015Q1", periods=40, freq="Q")
    rng = np.random.default_rng(0)
    Z = pd.DataFrame(rng.normal(size=(40, 3)), index=idx, columns=list("abc"))
    y = pd.Series(rng.normal(size=40), index=idx)
    t = list(idx[20:])
    p1 = wf_linear(y, composite(Z, {"a": 1, "b": -1, "c": 1}).to_frame("c"), t, "2015Q1", 8)
    p2 = wf_linear(y, composite(Z, {"a": -1, "b": 1, "c": -1}).to_frame("c"), t, "2015Q1", 8)
    assert np.allclose(p1.values, p2.values)


def test_composite_uses_no_future_data():
    """Scramble every factor and target value dated >= t: the composite forecast for t must not move."""
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from step3 import run_step3
    from composite import factor_frame, factor_z, composite, wf_linear
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    o = run_step3(p, cfg, write=False)
    s = o["series"].join(o["factors"][["mchp_disti_days", "nordic_fwd_dio"]])
    signs = {k: v["sign"] for k, v in cfg["composite"]["factors"].items()}
    t = pd.Period("2025Q3", "Q")

    def forecast(frame):
        C = composite(factor_z(factor_frame(frame, cfg), cfg), signs)
        return wf_linear(frame[cfg["composite"]["target"]], C.to_frame("c"), [t], cfg["composite"]["first_train_quarter"], 8)[t]

    base = forecast(s)
    q = s.copy()
    cols = [cfg["composite"]["target"]] + [f["column"] for f in cfg["composite"]["factors"].values()]
    q.loc[q.index >= t, cols] = q.loc[q.index >= t, cols] * -3.0 + 50.0      # factors enter at t-1, so dated >= t is future
    assert forecast(q) == pytest.approx(base)


def test_adoption_gate_is_read_from_config():
    from core.config import load_config
    g = load_config()["composite"]["adopt_if"]
    assert {"oos_r2_vs_benchmark_min", "placebo_p_max", "min_forecasts", "leave_one_out_min_share"} <= set(g)


def test_risk_flags_follow_the_data():
    """The risk box is computed, not written: flags switch on and off with the numbers."""
    from core.config import load_config
    from risk_flags import risk_flags, risk_box_md
    cfg = load_config()
    cb = {"top3_quarters": ["2024Q4", "2024Q2", "2024Q1"], "top3_share": 1.32, "quarters_won": 6, "n": 11, "oos_r2": 0.45,
          "last6_rmse_model": 1.80, "last6_rmse_base": 1.67}
    cl = {"top3_quarters": ["2024Q4", "2025Q2", "2023Q4"], "top3_share": 0.8, "quarters_won": 8, "n": 11, "oos_r2": 0.51,
          "last6_rmse_model": 1.80, "last6_rmse_base": 3.98}
    ne = {"composite_C": {"n": 20, "rho1": 0.82, "n_eff": 2.0}, "beat": {"n": 19, "rho1": 0.41, "n_eff": 8.0}}
    base = {"concentration": {"bench": cb, "longrun": cl}, "effective_n": ne,
            "live": {"quarter": "2026Q3", "beat_hat_pct": 4.15, "ridge_beat_hat_pct": 1.93, "guide_mid": 230.0}}
    f = risk_flags(base, cfg).set_index("id")
    ev = f.loc["R1", "evidence"]
    assert f.loc[["R1", "R3"], "triggered"].all() and "132%" in ev and "WORSE" in ev
    assert "intercept-only" in ev and "wins 8 of 11" in ev                    # both baselines are always shown
    assert f.loc["R4", "triggered"] and "about 2.0 independent" in f.loc["R4", "evidence"]
    calm = {"concentration": {"bench": {**cb, "top3_share": 0.4, "last6_rmse_model": 1.5}, "longrun": cl},
            "effective_n": {**ne, "composite_C": {"n": 60, "rho1": 0.3, "n_eff": 32.3}},
            "live": {**base["live"], "ridge_beat_hat_pct": 3.9}}
    g = risk_flags(calm, cfg).set_index("id")
    assert not g.loc["R1", "triggered"] and not g.loc["R3", "triggered"] and not g.loc["R4", "triggered"]
    assert "R1." not in risk_box_md(g.reset_index()) and "R2." in risk_box_md(g.reset_index())


def test_meta_regression_never_fits_nordic_and_tau_floor():
    import numpy as np
    from peer_panel import _dl_tau2_reg, meta_regression
    X = np.column_stack([np.ones(5), [0.4, 0.5, 0.6, 0.7, 0.8]])
    assert _dl_tau2_reg(np.full(5, 0.3), np.full(5, 0.5), X) == 0.0          # homogeneous slopes -> no between-firm variance
    peers = ["adi", "microchip", "onsemi", "silabs", "semtech", "lattice"]
    pf = pd.DataFrame({"company": peers + ["NORDIC"], "b": [0.1, 0.2, 0.3, 0.2, 0.1, 0.3, 99.0], "se": [0.4] * 7})
    cfg = {"peer_similarity": {"nordic": {"distribution_share": {"mid": 0.47}, "consumer_share": 0.6},
                               "criteria": {"min_distribution_share": 0.35}}}
    m = meta_regression({"per_firm": pf}, cfg)
    assert "NORDIC" not in set(m["table"]["company"])
    assert all(abs(f["nordic_pred"][k]["pred"]) < 1 for f in m["fits"] for k in f["nordic_pred"])   # Nordic's 99 never leaks in


def test_cycle_slopes_concentration_and_neff():
    import numpy as np
    from cycle_test import _slopes
    q = pd.period_range("2020Q1", periods=12, freq="Q")
    x = np.r_[np.zeros(10), 3.0, -3.0]                            # the factor moves in two quarters only
    rows = [{"company": c, "quarter": qq, "x": xx, "y": 0.5 * xx} for c in ("a", "b", "c") for qq, xx in zip(q, x)]
    out = _slopes(pd.DataFrame(rows), 3)
    assert abs(out["b_quarter_level"] - 0.5) < 1e-9 and abs(out["b_pooled"] - 0.5) < 1e-9
    assert out["top3_share"] > 0.99                               # all of the slope comes from the two moving quarters
    assert out["se_q_level_neff"] >= out["se_quarter_level"]


def test_relative_optimism_leaves_self_out_and_needs_min_peers():
    from guidance_optimism import relative
    q = pd.Period("2023Q3", "Q")
    peers = pd.DataFrame({"company": ["a", "b", "c", "d", "e", "f"], "quarter": [q] * 6, "g": [1.0, 2.0, 3.0, 4.0, 5.0, 100.0]})
    r = relative(peers, peers, "g", 5)
    assert r.iloc[5] == 100.0 - 3.0                       # f vs the median of a..e, not of itself
    assert r.iloc[0] == 1.0 - 4.0                         # a vs median of b..f
    assert relative(peers, peers, "g", 6).isna().all()    # only 5 OTHER peers -> below the minimum


def test_key_insights_are_built_from_numbers():
    from key_insights import key_insights
    fits = pd.DataFrame([{"spec": s, "sample": "without episode", f"b_{s}": 0.1, f"t_{s}": 0.5}
                         for s in ("rel_raw", "g", "guide_width_pct", "last_beat")] +
                        [{"spec": "x_channel", "sample": "without episode", "b_x_channel": 1.7, "t_x_channel": 2.3}])
    nordic = pd.DataFrame({"g": [0.5], "peer_median_g": [0.6], "rel_raw": [-0.1], "rel_consumer_heavy": [18.8], "beat": [-12.9]},
                          index=pd.PeriodIndex(["2023Q3"], freq="Q"))
    g = {"cycle_in_guide": {"n": 600, "sd_yoy": 29.0, "sd_beat": 3.6, "corr_yoy_beat": 0.2, "deep_n": 20, "deep_mean_beat": -0.2, "deep_within5": 0.95},
         "panel": {"fits": pd.DataFrame([{"spec": "rel_raw", "firm_quarters": 668, "quarters": 70, "b_rel_raw": 0.009, "t_rel_raw": 0.6}]),
                   "oos_r2": -0.004, "quintiles": pd.DataFrame({"miss_rate": [0.26, 0.2, 0.2, 0.2, 0.14]})},
         "nordic_fits": fits, "nordic": nordic}
    cfg = {"guidance_optimism": {"episode_quarters": ["2023Q3", "2023Q4"], "deep_decline_yoy_pct": -30}}
    k = key_insights(g, cfg).set_index("id")
    assert "missed by 12.9%" in k.loc["K2", "evidence"] and "+0.5% q/q" in k.loc["K2", "evidence"]
    assert "none of relative optimism" in k.loc["K3", "evidence"]


def test_revenue_h2_no_lookahead():
    """Row T-1's target is quarter T (not reported at the end of T): changing it must not move the forecast made at T."""
    import numpy as np
    from revenue_h2 import walk_forward
    q = pd.period_range("2012Q1", "2016Q4", freq="Q")
    rng = np.random.default_rng(0)
    G = pd.DataFrame({"company": "a", "quarter": q, "x": rng.normal(size=len(q)), "s": 0.0})
    G["g2"] = 2 * G["x"] + rng.normal(size=len(q))
    G["y"] = G["g2"] - G["s"]
    cfg = {"revenue_h2": {"first_target": "2015Q1", "min_train_quarters": 8}}
    base = walk_forward(G, cfg).set_index("quarter")["pred"]
    T = pd.Period("2016Q1", "Q")
    G2 = G.copy()
    G2.loc[G2["quarter"] == T - 1, ["g2", "y"]] = 1e6          # the not-yet-reported target
    assert walk_forward(G2, cfg).set_index("quarter")["pred"][T] == pytest.approx(base[T], rel=1e-12)   # BLAS rounding only


def test_graph_factor_uses_no_future_data():
    """Graph demand for quarter t (and so its change) may use Logitech sell-out through t-1 only; the swap leaves cfg intact."""
    import copy
    from core.config import load_config
    from composite import graph_demand, graph_challenger_cfg
    cfg = load_config()
    idx = pd.period_range("2019Q1", "2026Q3", freq="Q")
    s = pd.DataFrame({"logi_sellthrough_yoy": [float((i * 7) % 23 - 11) for i in range(len(idx))]}, index=idx)
    t = pd.Period("2025Q3", "Q")
    base = graph_demand(s, cfg)
    q = s.copy()
    q.loc[q.index >= t, "logi_sellthrough_yoy"] = 999.0
    moved = graph_demand(q, cfg)
    assert moved[t] == pytest.approx(base[t]) and moved[t - 1] == pytest.approx(base[t - 1])
    before = copy.deepcopy(cfg["composite"])
    g = graph_challenger_cfg(cfg)
    gc = cfg["composite"]["graph_challenger"]
    assert cfg["composite"] == before and gc["name"] in g["composite"]["factors"] and gc["replaces"] not in g["composite"]["factors"]


def test_grg_uses_only_what_is_known_at_the_q4_origin():
    """GRg at h=2: scramble everything dated t-1 or later except the two guides public at the origin (Nordic's and
    Logitech's for t-1): the forecast must not move; changing Logitech's guide must move it (it is really used)."""
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from walkforward import design, forecast_row
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    t, h = pd.Period("2026Q1", "Q"), 2
    run = lambda d: forecast_row(d, cfg, {"GRg": design(d, "GRg", cfg, None, h)}, t, h, False)["GRg_yoy"]  # noqa: E731
    base = run(p)
    q = p.copy()
    future = q.index >= t - 1
    num = q.select_dtypes("number").columns.drop(["nordic_guide_mid", "logi_guide_mid"])
    q.loc[future, num] = q.loc[future, num] * 7.0 + 123.0
    q.loc[t, ["nordic_guide_mid", "logi_guide_mid"]] = q.loc[t, ["nordic_guide_mid", "logi_guide_mid"]] * 3.0
    assert run(q) == pytest.approx(base)
    g = p.copy()
    g.loc[t - 1, "logi_guide_mid"] *= 1.10
    assert run(g) != pytest.approx(base)


def test_gri_uses_no_future_data():
    """GRi's regressor for t at h = 2 may use Logitech sell-in through t-2 and Logitech's guide for t-1 (given with its t-2 report)."""
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from walkforward import design
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    t = pd.Period("2026Q1", "Q")
    base = design(p, "GRi", cfg, None, h=2).loc[t].iloc[0]
    q = p.copy()
    q.loc[q.index >= t - 1, "logi_sales"] = q.loc[q.index >= t - 1, "logi_sales"] * 3.0      # Logitech's t-1 and t actuals unknown at the origin
    q["logi_sales_yoy"] = (q["logi_sales"] / q["logi_sales"].shift(4) - 1) * 100
    assert design(q, "GRi", cfg, None, h=2).loc[t].iloc[0] == pytest.approx(base)
