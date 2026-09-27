"""Dashboard forecast section (steps/step7_forecast/src/forecast_display.py): every range says what kind of range it is,
the beat footnote separates historical dispersion from added model uncertainty and shows n, the Nordic regime
sensitivity is shown, the Q4 line is on the page, and no indicator light is a hard-coded colour."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from core.config import load_config, OUTPUTS  # noqa: E402
import forecast_display as fd  # noqa: E402


@pytest.fixture(scope="module")
def ctx():
    import json
    cfg = load_config()
    det = json.loads((OUTPUTS / "forecast_details.json").read_text())
    return cfg, det["nordic"], det["logitech"], pd.read_csv(OUTPUTS.parent / "steps" / "step6_backtest" / "outputs" / "guidance_bias.csv"), pd.read_csv(OUTPUTS / "forecasts.csv")


def test_every_forecast_row_names_its_range_basis(ctx):
    cfg, *_, ftab = ctx
    basis = [fd.range_basis(r, cfg) for r in ftab.to_dict("records")]
    assert all(b in fd.BASIS_LABEL for b in basis)
    by = dict(zip(ftab["print"] + " | " + ftab["metric"], basis))
    assert by["Nordic Q3 2026 | Revenue (USDm)"] == "statistical"
    assert by["GN cont. ops Q3 2026 | Revenue (DKKm)"] == "gn_organic"
    assert by["Nordic Q3 2026 | Gross margin (%)"] == "margin_regime"          # band = the rule's error in current-regime quarters
    import json
    g = json.loads((OUTPUTS / "forecast_details.json").read_text())["nordic"]["gm_model"]
    cell = fd.basis_cell({"print": "Nordic Q3 2026", "metric": "Gross margin (%)"}, cfg)
    assert f"σ {g['sd_pts']:.2f} pts on n {g['n_regime']}" in cell and f"{min(g['scores'].values()):.2f}" in cell


def test_beat_footnote_shows_what_the_expected_guide_error_is_made_of(ctx):
    """With the guide-error model on (F16 pooled or F20 own record): what the error is made of, n, predictive sd."""
    cfg, fn, fl, gb, _ = ctx
    txt = fd.beat_footnote(fn, fl, gb, cfg)
    if fd._model_on(fn):
        gem = pd.read_csv(fd.GEM).set_index("company")
        for name in ("Nordic", "Logitech"):
            r = gem.loc[name]
            assert f"{name} expected guide error" in txt and f"{r['pred_sd']:.2f}" in txt
            n = int(r["n_not_building"]) if pd.notna(r.get("n_not_building", float("nan"))) else int(r["n"])
            assert f"n {n}" in txt
        assert "channel" in txt
    else:                                                              # fallback: the historical-beat method
        assert "historical σ" in txt and "model uncertainty" in txt


def test_state_sensitivity_prices_a_turn_to_building(ctx):
    cfg, fn, _, gb, _ = ctx
    s = fd.state_sensitivity(fn)
    if s is None:
        pytest.skip("guide-error model not in force")
    assert s["base_point"] == pytest.approx(fn["point"], abs=0.1)
    assert s["building_point"] < s["base_point"]
    assert s["gamma_t"] < -2 and 0 <= s["p_building_next"] <= 1
    assert "building" in fd.regime_html(fn, gb)


def test_q4_line_rows_come_from_the_csv():
    rows = fd.next_quarter_rows()
    q = pd.read_csv(OUTPUTS / "forecast_next_quarter.csv")
    assert len(rows) == len(q) and sum(r["is_point"] for r in rows) == 1


def test_q4_is_not_in_the_forecast_table():
    """The brief asks for three prints; Q4 sits under the risk scenarios as evidence (decision F10, 2026-09-26)."""
    import dashboard
    src = Path(dashboard.__file__).read_text()
    table_line = next(line for line in src.splitlines() if 'for r in ft.to_dict("records"))' in line)
    assert "next_quarter" not in table_line
    assert "Not one of the three forecast prints" in fd.next_quarter_section()


@pytest.mark.parametrize("gn_org, state, want_gn, want_nd", [(-7.0, 0.5, "amber", "amber"), (2.0, 0.0, "green", "green"), (0.0, -0.5, "green", "amber")])
def test_verbal_indicators_follow_rules_not_fixed_colours(ctx, gn_org, state, want_gn, want_nd):
    cfg = ctx[0]
    assert fd.gn_enterprise_level(gn_org, cfg) == want_gn
    assert fd.nordic_dist_level(state, cfg) == want_nd


def test_judgment_status_renders_distinctly():
    assert "judgment" in fd.status_html("judgment")
    assert fd.status_html("green") != fd.status_html("judgment")


def test_method_line_names_the_method_in_force(ctx):
    _, fn, *_ = ctx
    line = fd.method_line(fn)
    assert ("expected guide error" in line) == fd._model_on(fn)


def test_nordic_own_record_method_is_recognised_and_priced_with_its_own_building_effect(ctx):
    """F20: Nordic on its own record by channel state. The dashboard must describe that method (not fall back to the
    old regime text) and price a turn to building with Nordic's own effect."""
    _, fn, *_ = ctx
    if not str(fn.get("beat_source", "")).startswith("own record by channel state"):
        pytest.skip("F20 not in force")
    assert fd._model_on(fn)
    assert "F20" in fd.method_line(fn)
    st = fd.state_sensitivity(fn)
    gem = pd.read_csv(fd.GEM).set_index("company").loc["Nordic"]
    assert st["own_effect"] and st["building_effect"] == pytest.approx(gem["pred_building_effect"])
    assert "Nordic's own building effect" in fd.regime_html(fn, pd.read_csv(OUTPUTS.parent / "steps" / "step6_backtest" / "outputs" / "guidance_bias.csv"))
