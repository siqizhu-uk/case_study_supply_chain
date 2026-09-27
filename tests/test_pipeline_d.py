"""Pipeline D (peer panel): guide parsers for every wording seen in the filings, the traps they must survive, and the
peer-panel point-in-time property. Run: pytest -q tests/test_pipeline_d.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipelines" / "D_peer_panel" / "src"))
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from pipeline_d.parse import parse_guide, parse_channel_weeks  # noqa: E402

CFG = yaml.safe_load((ROOT / "pipelines" / "D_peer_panel" / "config" / "peers.yaml").read_text())


def P(c):
    return CFG["peers"][c]["patterns"]


@pytest.mark.parametrize("company,text,mid", [
    ("ti", "TI's third quarter outlook is for revenue in the range of $5.65 billion to $6.15 billion and earnings", 5900),
    ("ti", "Outlook For the second quarter of 2012, TI expects: Ÿ Revenue: $3.22 – 3.48 billion Ÿ Earnings", 3350),
    ("ti", "TI's outlook for the third quarter of 2014 is for revenue in the range of $3.31 billion to $3.59 billion", 3450),
    ("adi", "we are forecasting revenue of $4.3 billion, +/- $100 million.", 4300),
    ("adi", "forecasting revenue of $2.60 Billion , +/- $100 Million.", 2600),
    ("adi", "Non-GAAP Revenue $1.57 billion (+/- $40 million) - $1.57 billion", 1570),
    ("adi", "planning for revenue in the fourth quarter to be in the range of $1.36 billion to $1.44 billion", 1400),
    ("nxp", "Guidance for the Second Quarter 2021: ($ millions) (1) Guidance Range Low Mid High Total Revenue $ 2,500 $ 2,570 $ 2,640", 2570),
    ("onsemi", "outlook. Total onsemi GAAP Special Items Revenue $1,650 to $1,750 million - $1,650 to $1,750 million", 1700),
    ("silabs", "The company expects second quarter revenue to be in the range of $262 to $272 million, with IoT", 267),
    ("silabs", "the company expects revenue for the second quarter to be $140 to $146 million.", 143),
    ("microchip", "Microchip Consolidated Guidance Net Sales $1.519 to $1.577 billion GAAP", 1548),
])
def test_every_guide_wording(company, text, mid):
    g = parse_guide(text, P(company))
    assert g is not None and g["guide_mid_usdm"] == pytest.approx(mid, rel=1e-3)


def test_sequential_percent_guides_are_kept_as_percent_until_build():
    g = parse_guide("ADI's outlook for the first quarter of fiscal 2012 is as follows: Revenue: Down 5% to 10% sequentially.", P("adi"))
    assert g["pattern_kind"] == "pct_seq" and (g["guide_pct_low"], g["guide_pct_high"]) == (-10.0, -5.0)
    g = parse_guide("we expect revenue in the second quarter to be in the range of -2% to +4% sequentially.", P("adi"))
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-2.0, 4.0)


def test_plausibility_guard_skips_sub_item_sentences():
    """Microchip '$51-54 million' is a sub-item (0.1x revenue): with the guard the parser moves on to the real guide."""
    text = "net sales to be between $51 million and $54 million ... Microchip Consolidated Guidance Net Sales $540 to $560 million"
    g = parse_guide(text, P("microchip"), plausible=lambda m: 0.25 * 530 <= m <= 4 * 530)
    assert g["guide_mid_usdm"] == pytest.approx(550)


def test_plausibility_band_keeps_a_real_destock_guide():
    """Silicon Labs guided $85m after a $204m quarter (0.42x): a 0.5-2x band would have dropped it (selection bias)."""
    lo, hi = CFG["plausible_guide_ratio"]
    assert lo <= 85 / 203.8 <= hi


def test_nxp_channel_inventory_months_converted_to_weeks():
    c = parse_channel_weeks("Cash Conversion Cycle 32 31 58 Channel Inventory (months) 1.6 1.6 2.4 Financial", CFG["peers"]["nxp"]["channel_weeks"])
    assert c["channel_unit_reported"] == "months" and c["channel_weeks"] == pytest.approx(1.6 * 52 / 12)


def test_unit_typo_is_detected():
    from pipeline_d.build import _fix_unit
    v, flag = _fix_unit(1240 * 1000.0, ref=1300.0, ratio=CFG["unit_typo_ratio"])        # '$1,240 billion'
    assert v == pytest.approx(1240.0) and "typo" in flag


def test_every_structural_break_and_override_has_a_reason():
    for b in CFG["structural_breaks"] + CFG.get("actual_overrides", []) + CFG.get("verified_outliers", []):
        assert len(b["reason"]) > 30, b


def test_peer_design_is_point_in_time():
    """A firm's FE, past-4 and z of quarter t must not change when quarter t's own beat and factor are scrambled."""
    from core.config import load_config
    from peer_panel import load_panel, industry_factor, build_design
    cfg = load_config()
    p = load_panel()
    base = build_design(p, industry_factor(), cfg).set_index(["company", "quarter"])
    t = pd.Period("2022Q3", "Q")
    q = p.copy()
    m = (q["company"] == "ti") & (q["quarter"] >= t)
    q.loc[m, ["beat_pct", "own_fwd_dio"]] = q.loc[m, ["beat_pct", "own_fwd_dio"]] * -5 + 99
    pert = build_design(q, industry_factor(), cfg).set_index(["company", "quarter"])
    for col in ("fe", "past4"):
        assert pert.loc[("ti", t), col] == pytest.approx(base.loc[("ti", t), col])


@pytest.mark.parametrize("company,text,mid", [
    ("semtech", "Fourth Quarter of Fiscal Year 2024 Outlook (in millions, except per share data) Net sales $ 190.0 +/- $10.0 Non-GAAP", 190),
    ("power_integrations", "Revenues are expected to be $107 million plus or minus $3 million. GAAP gross margin", 107),
    ("power_integrations", "Revenues are expected to be between $86 million and $92 million.", 89),
    ("lattice", "Revenue for the second quarter of 2026 is expected to be between $175 million and $195 million.", 185),
    ("maxlinear", "We expect revenue in the third quarter of 2013 to increase approximately 4 percent to 7 percent sequentially to $31 million to $32 million.", 31.5),
    ("maxlinear", "GAAP Non-GAAP (except for revenue) Revenue $210 - $220 $210 - $220 Gross Margin 57.0%", 215),
    ("monolithic_power", "we are forecasting: • Revenue in the range of $1,140 million to $1,160 million.", 1150),
    ("alpha_omega", "We expect: • Revenue to be approximately $168 million, plus or minus $10.0 million.", 168),
])
def test_new_peer_wordings(company, text, mid):
    g = parse_guide(text, P(company))
    assert g is not None and g["guide_mid_usdm"] == pytest.approx(mid, rel=1e-3)


def test_flat_plus_minus_percent_guides():
    g = parse_guide("Revenues are expected to be flat compared to the first quarter of 2021, plus or minus five percent.", P("power_integrations"))
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-5.0, 5.0)
    g = parse_guide("Revenue is expected to be approximately flat to down 4%, as compared to the third quarter", P("lattice"))
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-4.0, 0.0)


@pytest.mark.parametrize("text", [
    # pre-announcement that repeats the OLD guide for the quarter just ended (not a guide for the next quarter)
    "The company expects the revenue for the fiscal quarter ended December 31, 2013 to be within the range of guidance previously provided in the press release dated October 30, 2013 (i.e., $75 million to $79 million)",
    # mid-quarter update (half the quarter already seen) - the initial guide must stay the benchmark
    "The Company now expects revenue for the fiscal first quarter to be between $148 million and $152 million. This exceeds prior guidance",
])
def test_alpha_omega_traps_are_not_read_as_guides(text):
    assert parse_guide(text, P("alpha_omega")) is None


def test_center_plus_minus_percent_guide():
    g = parse_guide("Revenues are expected to decrease by three percent compared to the second quarter of 2021, plus or minus five percent.", P("power_integrations"))
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-8.0, 2.0)


def test_exhibit_picker():
    from pipeline_d.releases import pick_exhibits
    items = [{"name": "0001437749-20-021991-index-headers.html"}, {"name": "0001437749-20-021991-index.html"},
             {"name": "ex_209041.htm", "size": 383272}, {"name": "mpwr20201026_8k.htm", "size": 29611}, {"name": "R1.htm", "size": 38877}]
    assert pick_exhibits(items)[0] == "ex_209041.htm"
    assert pick_exhibits([{"name": "d359276dex991.htm", "size": 10}, {"name": "big.htm", "size": 999}])[0] == "d359276dex991.htm"


def test_history_actual_needs_a_revenue_row_not_the_outlook():
    from pipeline_d.history import release_actual
    from pipeline_d.releases import load_cfg
    h = load_cfg()["history"]
    outlook_only = "Record Quarterly Revenue of $562.7 Million ... Q3 OUTLOOK Revenue $570 to $585 million Gross Margin 37.5%"
    a = release_actual(outlook_only, h)
    assert a["actual_release_usdm"] == 562.7 and a["actual_table_usdm"] is None          # outlook row is not a second source
    with_table = outlook_only + " June 27, 2008 March 30, 2008 Net revenues $ 562.7 $ 421.9 $ 381.2 Cost of revenues 371.1"
    assert release_actual(with_table, h)["actual_table_usdm"] == 562.7
    thousands = "Net revenues for the quarter were $53.8 million ... Net revenues $ 53,812 $ 49,701"
    assert abs(release_actual(thousands, h)["actual_table_usdm"] - 53.812) < 1e-9
    assert release_actual("we expect revenues of $60 million next quarter", h) is None     # forward-looking sentence skipped


def test_history_quarter_ends_include_december_before_xbrl():
    import pandas as pd
    from pipeline_d.history import quarter_ends
    xq = pd.DataFrame({"period_end": pd.to_datetime(["2009-06-30", "2009-09-30", "2010-12-31"])})
    ends = set(quarter_ends(xq).dt.strftime("%Y-%m-%d"))
    assert {"2008-12-31", "2009-12-31", "2008-06-30"} <= ends


def test_history_guide_wordings():
    pats = CFG["history"]["patterns"]
    g = parse_guide("Our operating plan is for revenues to decline sequentially by approximately 20% in the first quarter", pats["adi"])
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-20.0, -20.0)
    g = parse_guide("Revenue is expected to be minus 2% to plus 3% on a sequential basis", pats["lattice"])
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-2.0, 3.0)
    g = parse_guide("Revenue is expected to be flat to down three percent on a sequential basis", pats["lattice"])
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (-3.0, 0.0)
    g = parse_guide("expects its revenues for the fourth quarter of 2009 to increase by five to 10 percent compared", pats["power_integrations"])
    assert (g["guide_pct_low"], g["guide_pct_high"]) == (5.0, 10.0)
    # Microchip's mid-quarter pre-announcement wording must not parse as an initial guide
    assert parse_guide("Net sales for the third fiscal quarter are expected to be down 29 to 31% sequentially", pats["microchip"]) is None
