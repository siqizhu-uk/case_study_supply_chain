"""Guidance track record (step 7, F12): sources verified, scoring rules as stated. Run: pytest -q tests/test_guidance_record.py"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "steps" / "step7_forecast" / "src"))
RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"


def test_every_guidance_number_is_quote_checked():
    lg = pd.read_csv(RAW / "logitech_guidance_history.csv")
    assert lg["quote_check"].str.startswith("found").all() and lg["numbers_in_quote"].all()
    gn = pd.read_csv(RAW / "gn_guidance_history.csv")
    assert gn["quote"].notna().all() and gn["url"].str.startswith("https://").all()


def test_label_rule():
    from guidance_record import label
    assert label(pd.Series([1, 2, 3, -1])) == "conservative"
    assert label(pd.Series([-1, -2, -3, 1])) == "aggressive"
    assert label(pd.Series([1, -1, 2, -2])) == "mixed"
    assert label(pd.Series([5, 5, 5])) == "too few"


def test_late_statements_are_not_initial_guides():
    from guidance_record import logitech_annual, MIN_MONTHS_AHEAD
    a = logitech_annual()
    assert (a["initial"] == (a["months_ahead"] >= MIN_MONTHS_AHEAD)).all()
    assert not a.set_index(["period", "metric"]).loc[("FY2026", "sales_usdm"), "initial"]     # given Jan 2026, one quarter left


def test_gn_actual_on_the_guide_basis_only():
    from guidance_record import gn_annual
    a = gn_annual().set_index(["fiscal_year", "metric"])
    assert a.loc[(2024, "organic_growth_pct"), "actual"] == 1.0      # reported organic incl. wind-down (the 2024 guide basis), not 4
    assert a.loc[(2025, "organic_growth_pct"), "actual"] == -1.0     # excl. wind-down (the 2025 guide basis), not -4
    assert a.loc[(2022, "organic_growth_pct"), "scope"] == "audio"   # no group guide before 2023


def test_anchor_table_matches_the_forecasts():
    """Nordic and Logitech forecasts use the anchor table's bias; GN's H2 follows from its FY expectation and reported H1."""
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    from guidance_record import anchor_table
    from forecast import gn_anchor
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    at = anchor_table(p, cfg)
    gn = at[at["company"] == "GN"].reset_index(drop=True)
    assert int(at.set_index("company").loc["Logitech", "n"]) == 5
    a = gn_anchor(cfg, p)
    # F15: the first GN row is the bias the forecast applies (same-regime years); the last is every year (its sd sets the range)
    assert int(gn.loc[0, "n"]) == a["august_bias_n"] and abs(gn.loc[0, "mean_beat_pct"] - a["august_bias_pts"]) < 0.01
    assert int(gn.iloc[-1]["n"]) == 5
    assert abs(a["fy_expected_pct"] - (a["fy_guide_mid"] + a["august_bias_pts"])) < 1e-6
    assert a["h2_sd_pts"] > gn.iloc[-1]["std_pct"]           # H1 is known: the whole FY error lands on H2


def test_brief_audit_evidence_exists():
    """Every evidence path in audit/brief_audit.csv exists; every brief item has a verdict."""
    from brief_audit import audit
    a = audit()
    assert (a["missing"] == "").all(), a.loc[a["missing"] != "", ["item", "missing"]].to_string()
    assert a["status"].isin(["supported", "partial", "weak"]).all() and len(a) == 13
