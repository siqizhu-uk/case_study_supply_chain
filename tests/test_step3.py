"""Step 3 (inventory mechanism): formula tests on toy data with known answers, parsers for the new data, and a smoke
test of the full step on the real panel. Run: pytest -q tests/test_step3.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipelines" / "A_company_financials" / "src"))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from inventory_factors import dio, forward_dio, growth_spread, dso          # steps/step3_inventory_mechanism/src
from channel_index import excess_fill, anchor_level
from bullwhip import variance_ratio, block_bootstrap_ci
from amplification import fit_link
from pipeline_a.inventory_detail import parse_mchp, chain_check, fiscal_to_calendar_quarter
from pipeline_a.nordic_balance import parse_balance_line

Q = pd.period_range("2021Q1", "2024Q4", freq="Q")


# ------------------------------------------------------------------ inventory factors
def test_dio_and_forward_dio():
    inv, cogs = pd.Series([100.0]), pd.Series([91.25])
    assert dio(inv, cogs).iloc[0] == pytest.approx(100.0)          # 100 of stock on 91.25 of quarterly COGS = 100 days
    assert forward_dio(inv, pd.Series([182.5])).iloc[0] == pytest.approx(50.0)


def test_growth_spread_is_inventory_growth_minus_sales_growth():
    inv = pd.Series([100, 100, 100, 100, 130.0], index=Q[:5])
    rev = pd.Series([100, 100, 100, 100, 110.0], index=Q[:5])
    assert growth_spread(inv, rev).iloc[-1] == pytest.approx(20.0)


def test_dso():
    assert dso(pd.Series([50.0]), pd.Series([91.25])).iloc[0] == pytest.approx(50.0)


# ------------------------------------------------------------------ channel index
def _channel(sell_through, fills):
    s_in = pd.Series(np.array(sell_through) + np.array(fills), index=Q[:len(fills)])
    t = pd.Series(sell_through, index=Q[:len(fills)], dtype=float)
    g_in = (s_in / s_in.shift(4) - 1) * 100
    g_out = (t / t.shift(4) - 1) * 100
    return s_in, (g_out - g_in)


def test_excess_fill_recovers_true_fill_and_does_not_double_count_lapping():
    # steady sell-through 100; the channel is drained by 5 in year 2 Q1 and flat again in year 3 Q1
    st = [100.0] * 12
    fills = [0, 0, 0, 0, -5, 0, 0, 0, 0, 0, 0, 0]
    s_in, gap = _channel(st, fills)
    out = excess_fill(s_in, gap, start=str(Q[4]))
    assert out.loc[Q[4], "fill_exact"] == pytest.approx(-5.0)
    assert out.loc[Q[8], "fill_exact"] == pytest.approx(0.0, abs=1e-9)   # sell-in +5.3% vs sell-through flat is just lapping
    assert out.loc[Q[8], "fill_naive"] == pytest.approx(5.0, rel=1e-6)   # the naive gap x sales would call it a +5 build
    assert out.loc[Q[11], "level_raw"] == pytest.approx(-5.0)            # level: drained once, never refilled


def test_anchor_level_sets_anchor_mean_to_zero_and_reports_dispersion():
    level = pd.Series([-10.0, -4.0, -6.0], index=Q[:3])
    sell_in = pd.Series([130.0, 130.0, 130.0], index=Q[:3])
    out, disp = anchor_level(level, sell_in, [str(Q[1]), str(Q[2])])
    assert out["excess_usd"].loc[[Q[1], Q[2]]].mean() == pytest.approx(0.0)
    assert out["excess_weeks"].loc[Q[0]] == pytest.approx(-5.0 / 10.0)   # -5 of stock / (130/13 per week)
    assert disp["rms_weeks"] == pytest.approx(0.1)


# ------------------------------------------------------------------ bullwhip
def test_variance_ratio_and_bootstrap_brackets_truth():
    rng = np.random.default_rng(0)
    d = rng.normal(0, 1, 200)
    o = 2.0 * d
    assert variance_ratio(o, d) == pytest.approx(4.0)
    lo, hi = block_bootstrap_ci(lambda a, b: variance_ratio(a, b), [o, d], reps=200, block=4, seed=1)
    assert lo == pytest.approx(4.0) and hi == pytest.approx(4.0)


# ------------------------------------------------------------------ amplification (stock-adjustment regression)
def test_fit_link_recovers_cover_from_stock_adjustment_orders():
    # orders under a TTM cover target c (years): g_O = g + c * (g - g_{t-4}); c = 0.4 year = 20.8 weeks
    rng = np.random.default_rng(3)
    idx = pd.period_range("2010Q1", "2026Q4", freq="Q")
    g = pd.Series(np.cumsum(rng.normal(0, 3, len(idx))), index=idx)
    c = 0.4
    y = 2.0 + g.shift(2) + c * (g - g.shift(4)).shift(2) + rng.normal(0, 0.5, len(idx))
    res = fit_link(y, g, lag=2, sample=("2012Q1", "2026Q4"), accel=True, boot={"reps": 200, "block": 4, "seed": 1})
    assert res["coef"]["g"] == pytest.approx(1.0, abs=0.1)
    assert res["coef"]["d4g"] == pytest.approx(c, abs=0.05)
    assert res["implied_cover_weeks"] == pytest.approx(c * 52, abs=3)
    lo, hi = res["ci90"]["d4g"]
    assert lo < c < hi


# ------------------------------------------------------------------ parsers for the new data
def test_parse_microchip_sentence_and_chain():
    t = ("... At June 30, 2025, our distributors maintained 29 days of inventory of our products compared to 33 days at "
         "March 31, 2025. Over the past ten fiscal years ...")
    r = parse_mchp(t)
    assert (r["disti_days"], r["prior_days"], r["period_end"], r["prior_end"]) == (29, 33, "2025-06-30", "2025-03-31")
    df = pd.DataFrame([{"period_end": "2025-03-31", "disti_days": 33, "prior_days": 41, "prior_end": "2024-03-31"},
                       {"period_end": "2025-06-30", "disti_days": 29, "prior_days": 33, "prior_end": "2025-03-31"},
                       {"period_end": "2025-09-30", "disti_days": 27, "prior_days": 34, "prior_end": "2025-03-31"}])
    assert chain_check(df)["chain_ok"].tolist() == [True, True, False]


def test_fiscal_quarter_mapping():
    assert str(fiscal_to_calendar_quarter("2026-07-04")) == "2026Q2"    # Arrow 53-week close
    assert str(fiscal_to_calendar_quarter("2026-06-30")) == "2026Q2"
    assert str(fiscal_to_calendar_quarter("2025-09-27")) == "2025Q3"


def test_parse_nordic_balance_line_does_not_merge_columns():
    t = "Current assets\nInventory 217 294 154 994 135 850\nAccounts receivable 115 653 93 488 66 056\n"
    assert parse_balance_line(t, r"Inventor(?:y|ies)") == [217.294, 154.994, 135.85]
    assert parse_balance_line(t, r"(?:Accounts|Trade) receivables?") == [115.653, 93.488, 66.056]


# ------------------------------------------------------------------ full step on the real data
@pytest.fixture(scope="module")
def step3():
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from step3 import run_step3
    cfg = load_config()
    return run_step3(build_panel(load_all(), cfg), cfg, write=False)


def test_step3_outputs_are_complete(step3):
    assert {"factors", "channel", "bullwhip", "concentration", "mechanism", "call", "decisions"} <= set(step3)
    assert set(step3["call"]["company"]) == {"nordic", "logitech", "gn"}
    for _, r in step3["call"].iterrows():
        assert r["adj_low"] <= r["adj_mid"] <= r["adj_high"], r["company"]


def test_step3_every_decision_has_a_reason(step3):
    d = step3["decisions"]
    assert d["reason"].str.len().min() > 20 and d["id"].is_unique


def test_logitech_channel_anchors_are_consistent(step3):
    # five management 'at target' statements; if the index is right they should agree within ~1.5 weeks
    assert step3["channel"]["logitech"]["anchor_fit"]["rms_weeks"] < 1.5

