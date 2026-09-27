"""Smoke + logic tests. Run: pytest -q"""
import copy
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from core.config import load_config
from core.ingest import load_all
from core.tiers import build_panel
from lags import lag_analysis, reasoned_lag_quarters          # steps/step4_lag_structure/src
from backtest import distributed_lag_regression, guidance_bias  # steps/step6_backtest/src
from attribution import attribution                          # steps/step2_attribution/src
from forecast import forecast_nordic, forecast_logitech, forecast_gn, forecast_table


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def panel(cfg):
    return build_panel(load_all(), cfg)


def test_raw_files_have_sources():
    for name, df in load_all().items():
        assert "source" in df.columns, name
        assert df["source"].notna().all(), f"{name}: every row must cite a source"


def test_panel_shape_and_yoy(panel, cfg):
    assert panel.index[0] == pd.Period("2020Q1", "Q")
    # SNX YoY is masked across the Tech Data merger (2021Q4-2022Q3)
    assert pd.isna(panel.loc["2022Q1", "snx_sales_yoy"]) and pd.notna(panel.loc["2022Q4", "snx_sales_yoy"])
    # GN 2026 group revenue = continuing ops + Hearing
    assert panel.loc["2026Q2", "gn_group_rev"] == 2171 + 1772
    # YoY sanity: Nordic 2026Q2 218.6 vs 2025Q2 164.1
    assert abs(panel.loc["2026Q2", "nordic_rev_yoy"] - (218.6 / 164.1 - 1) * 100) < 1e-6
    # Logitech core radio series 2026Q2 = weighted pointing + keyboards + gaming + tablet (weights from config)
    rc = cfg["radio_content"]["logitech"]
    exp = rc["pointing_usdm"]["weight"] * 227.3 + rc["keyboards_usdm"]["weight"] * 227.8 + rc["gaming_usdm"]["weight"] * 354.2 + rc["tablet_usdm"]["weight"] * 89.4
    assert abs(panel.loc["2026Q2", "logi_radio_core"] - exp) < 1e-6
    # GN radio series = weighted Enterprise + Gaming + Consumer (+ Hearing only if its weight > 0)
    rg = cfg["radio_content"]["gn"]
    exp = rg["enterprise_rev_dkkm"]["weight"] * 1997 + rg["gaming_div_rev_dkkm"]["weight"] * 896 + rg["consumer_rev_dkkm"]["weight"] * 368 + rg["hearing_rev_dkkm"]["weight"] * 1808
    assert abs(panel.loc["2023Q4", "gn_radio_all"] - exp) < 1e-6
    # GN continuing-ops base for 2025Q3 = Enterprise 1624 + Gaming division 587
    assert panel.loc["2025Q3", "gn_periph_dkk"] == 1624 + 587


def test_structural_break_adjustments(panel, cfg):
    assert panel.loc["2024Q2", "nordic_gm_adj"] == cfg["structural_breaks"]["nordic_q2_2024_writedown"]["adj_gm_pct"]
    assert abs(panel.loc["2026Q2", "logi_gm_adj"] - (49.8 - 5.0)) < 1e-6


def test_reasoned_lag_is_one_to_three_quarters(cfg):
    r = reasoned_lag_quarters(cfg)
    assert 1.0 <= r["low"]["quarters"] <= r["mid"]["quarters"] <= r["high"]["quarters"] <= 3.0


def test_lag_analysis_peaks_at_positive_lag(panel, cfg):
    lag = lag_analysis(panel, cfg)
    assert lag["best_lag_all"] in (1, 2, 3), "Nordic should lag Logitech by 1-3 quarters"


def test_regression_runs_and_amplifies(panel, cfg):
    reg = distributed_lag_regression(panel, cfg)
    assert reg["ok"], reg
    assert reg["n"] >= cfg["regression"]["min_obs"]
    assert reg["sum_lag_effect"] > 1.0, "component tier should amplify OEM growth (bullwhip)"
    assert reg["rmse_loo"] > reg["rmse_in_sample"]  # honesty check on the reported numbers


def test_guidance_bias_regimes(panel, cfg):
    gb = guidance_bias(panel, cfg)
    normal = gb[(gb.company == "Nordic") & gb.window.str.startswith("normal")].iloc[0]
    destock = gb[(gb.company == "Nordic") & gb.window.str.startswith("destock")].iloc[0]
    assert normal.mean_beat_pct > 0 > destock.mean_beat_pct


def test_attribution_respects_cap(cfg):
    a = attribution(cfg, n=5000)
    cap = cfg["attribution"]["nordic_no_customer_over_pct"] / 100 * cfg["attribution"]["nordic_total_rev_usdm_ttm"]
    assert a["logitech_usdm"]["p90"] <= cap + 1e-9
    assert 0 < a["combined_pct_of_nordic_total"]["p50"] < 30


def test_forecasts_and_config_sensitivity(panel, cfg):
    gb = guidance_bias(panel, cfg)
    reg = distributed_lag_regression(panel, cfg)
    fn, fl, fg = forecast_nordic(cfg, gb, reg, panel), forecast_logitech(cfg, gb, panel), forecast_gn(cfg, panel)
    tab = forecast_table(fn, fl, fg)
    assert len(tab) == 6 and (tab["low"] <= tab["point"]).all() and (tab["point"] <= tab["high"]).all()
    # changing the guidance in config must move the forecast
    cfg2 = copy.deepcopy(cfg)
    cfg2["forecast"]["nordic_2026Q3"]["guide_low"] += 10
    cfg2["forecast"]["nordic_2026Q3"]["guide_high"] += 10
    fn2 = forecast_nordic(cfg2, gb, reg, panel)
    assert fn2["point"] > fn["point"]
    # GN EBITA bridge (cross-check): removing the tariff refund lowers the bridged margin
    cfg3 = copy.deepcopy(cfg)
    cfg3["forecast"]["gn_2026Q3"]["tariff_refund_q3_dkkm"] = 0
    assert forecast_gn(cfg3, panel)["ebita_bridge_margin_pct"] < fg["ebita_bridge_margin_pct"]
    # margin rule (F18): a higher Logitech GM guide moves the GM forecast one for one
    cfg4 = copy.deepcopy(cfg)
    cfg4["forecast"]["logitech_2026Q3"]["guide_gm"] += 1
    assert abs(forecast_logitech(cfg4, gb, panel)["gm_point"] - fl["gm_point"] - 1) < 0.051


def test_step1_filing_confidence_outputs_are_complete():
    from filing_confidence import run_step1                      # steps/step1_filing_confidence/src
    r = run_step1()
    conf = r["confidence"]
    assert set(r["final"]) == {"nordic", "logitech", "gn", "ingram", "tdsynnex"} and set(r["final"].values()) <= {"A", "B", "C"}
    tot = conf[conf["metric_class"].str.startswith("total revenue")]
    assert (tot["grade"] == "A").all()                            # Σ4Q vs audited FY within 0.1% for every company
    t2 = pd.read_csv(r["path"].parent / "test2_restatements.csv")
    # live check, or the recorded one on a fresh clone without the filing cache (audit/verification_ledger.csv)
    assert t2["restated_verified"].str.startswith("found").all() and (t2["csv_uses"] == "restated").all()


def test_step2_legs_and_routes(cfg, panel):
    a = attribution(cfg, n=4000, panel=panel)
    r = a["by_route"]
    cap = cfg["attribution"]["nordic_no_customer_over_pct"] / 100 * cfg["attribution"]["nordic_total_rev_usdm_ttm"]
    assert r["direct"]["logitech_usdm"]["p90"] <= cap + 1e-9 and r["indirect"]["logitech_usdm"]["p90"] >= r["direct"]["logitech_usdm"]["p90"]
    assert a["leg_d_proprietary_floor"]["available"] and a["leg_d_proprietary_floor"]["first_quarter_below_half_peak"] == "2022Q3"
    e = a["leg_e_natural_experiment"]
    assert e["available"] and e["nordic_consumer_drop_pct"] < e["logitech_drop_pct"] < 0     # Nordic swings more than Logitech
    assert a["grade"] in ("B", "D") and a["socket_share_used"]["source"].startswith("prior") == (a["grade"] == "D")


def test_step2b_attribution_path_is_time_varying_and_evidenced(cfg, panel):
    from attribution_path import build_path, time_varying_driver, implied_content_series, BREAK_QUARTER
    path = build_path(cfg, panel=panel, n=4000)
    assert len(path) >= 12 and path["quarter"].is_monotonic_increasing
    # bounded, ordered quantiles; the direct route never exceeds the IFRS 8.34 cap (10% + GN)
    assert (path["share_total_indirect_p10"] <= path["share_total_indirect_p50"]).all() and (path["share_total_indirect_p50"] <= path["share_total_indirect_p90"]).all()
    assert (path["share_total_direct_p50"] < 13).all()
    # it moves: the destock trough share is above the latest share (denominator effect / bullwhip)
    assert path.set_index("quarter").loc["2024Q2", "share_total_indirect_p50"] > path["share_total_indirect_p50"].iloc[-1]
    # evidence flags present on every row; the break is explicit
    assert path["socket_evidence"].str.len().gt(0).all() and set(path["cap_status"]) <= {"found", "assumed"}
    assert (path.set_index("quarter").loc[BREAK_QUARTER:, "break_2022Q3"] == "post").all()
    # consumers: time-varying driver equals the constant driver in the last quarter (weight 1) and differs earlier
    tv = time_varying_driver(panel, path, cfg["regression"]["driver"]).dropna()
    const = panel[cfg["regression"]["driver"]].dropna()
    assert abs(tv.iloc[-1] - const.iloc[-1]) < 1e-9 and (tv / const).dropna().round(3).nunique() > 1
    assert implied_content_series(panel, path).dropna().gt(0).all()
    reg_tv = distributed_lag_regression(panel, cfg, driver=tv)
    assert reg_tv["ok"] and reg_tv["driver"].endswith("_tv")
