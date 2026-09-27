"""One FX rule for the three forecasts (F27): ECB rates, disclosed FX effects, post-guide terms. Run: pytest -q tests/test_fx.py"""
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
import fx_update as fx  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def test_ecb_quarterly_rates_are_complete_and_plausible():
    r = fx.rates()
    assert r["dkk_per_EUR"].between(7.46038 * 0.9775, 7.46038 * 1.0225).all()        # ERM II band
    assert (r["n_days"].iloc[:-1] >= 55).all()
    assert r["usd_per_EUR"].between(0.8, 1.6).all()


def test_disclosed_fx_effects_carry_their_quotes():
    d = fx.disclosed()
    assert (d["quote"].str.len() > 20).all()
    logi = d[(d.company == "logitech") & (d.kind == "realised")]
    assert len(logi) >= 14
    assert set(d["kind"]) <= {"realised", "guide_assumed"}


def test_gn_usd_share_fits_and_passes_the_north_america_check(cfg):
    f = fx.gn_fit(cfg)
    assert 0.2 <= f["usd_share"] <= 0.7
    for q, (disclosed, usd_yoy) in f["north_america_check"].items():   # all-USD revenue: effect = USD move
        assert abs(disclosed - usd_yoy) < 1.5, q


def test_gn_q3_fx_term_has_the_sign_of_the_usd_move(cfg):
    t = fx.gn_term(cfg, "2026Q3")
    assert np.sign(t["term_pts"]) == np.sign(t["usd_yoy_pct"]) or abs(t["term_pts"]) < 0.3


def test_logitech_term_is_applied_only_if_it_beats_the_guide(cfg):
    from forecast import _logitech_fx_check
    c = _logitech_fx_check(cfg, 1202.5)
    assert c["applied"] == (c["wf_rmse_guide_fx"] < c["wf_rmse_guide"])


def test_gn_forecast_uses_the_rate_based_term_when_config_is_null(cfg):
    if cfg["forecast"]["gn_2026Q3"].get("fx_pts") is not None:
        pytest.skip("hand-typed fx_pts in force")
    from forecast import forecast_gn
    from core.ingest import load_all
    from core.tiers import build_panel
    g = forecast_gn(cfg, build_panel(load_all(), cfg))
    assert g["organic_assumptions"]["fx_pts"] == pytest.approx(round(fx.gn_term(cfg, "2026Q3")["term_pts"], 2))
