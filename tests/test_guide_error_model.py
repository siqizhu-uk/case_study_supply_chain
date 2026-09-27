"""Step 7e (guide_error_model.py): one model of the guide error - habit partially pooled with the peers + channel state."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

import guide_error_model as gem  # noqa: E402


def _synthetic(gamma=-1.5, n_firms=12, n_q=40, seed=0):
    rng = np.random.default_rng(seed)
    q = pd.period_range("2011Q1", periods=n_q, freq="Q")
    building = (rng.random(n_q) < 0.3).astype(float)
    rows = []
    for f in range(n_firms):
        a = 2.0 + rng.normal(0, 0.5)
        for i, qq in enumerate(q):
            rows.append({"company": f"f{f}", "q": qq, "building": building[i], "error": a + gamma * building[i] + rng.normal(0, 3)})
    return pd.DataFrame(rows).assign(state=lambda d: np.where(d["building"] == 1, "building", "normal"))


def test_state_effect_recovers_gamma_with_firm_fixed_effects():
    se = gem.state_effect(_synthetic(gamma=-1.5))
    assert se["gamma"] == pytest.approx(-1.5, abs=0.5) and se["t"] < -2


def test_few_noisy_guides_shrink_toward_the_peers_and_unpooled_keeps_its_own():
    prior = {"mu": 2.0, "tau2": 0.25, "resid_sd": 4.0}
    e = pd.Series([-3.0, -2.0, -4.0, -1.0, -5.0])
    b = pd.Series(np.zeros(5))
    pooled = gem.company_habit(e, b, 0.0, prior, nu=8, pooled=True)
    own = gem.company_habit(e, b, 0.0, prior, nu=8, pooled=False)
    assert own["alpha"] == pytest.approx(-3.0) and own["weight_own"] == 1.0
    assert -3.0 < pooled["alpha"] < 2.0 and pooled["weight_own"] < 0.2          # tau small vs noise: mostly the peers
    many = gem.company_habit(pd.Series(np.full(200, -3.0) + np.random.default_rng(1).normal(0, 4, 200)), pd.Series(np.zeros(200)), 0.0, prior, 8)
    assert many["weight_own"] > pooled["weight_own"]                              # more own guides, more own weight


@pytest.fixture(scope="module")
def fitted():
    from core.config import load_config
    cfg = load_config()
    p = pd.read_csv(ROOT / "outputs" / "tier_panel.csv")
    p.index = pd.PeriodIndex(p["quarter"], freq="Q")
    return cfg, p, gem.fit(p, cfg)


def test_real_fit_follows_the_pre_stated_rules(fitted):
    cfg, p, m = fitted
    c = cfg["guide_error_model"]
    se = m["state_effect"]
    assert m["gamma_used"] == (se["gamma"] if abs(se["t"]) >= c["state_t_min"] else 0.0)
    assert {"Nordic", "Logitech", "GN"} <= set(m["habits"])
    assert m["habits"]["GN"]["pooled"] is False and m["habits"]["Logitech"]["pooled"] is True
    assert m["habits"]["Nordic"].get("own_state") is True and "Nordic" in m["challengers"]        # F20: own record by state; pooled = challenger
    for co in ("Nordic", "Logitech", "GN"):
        pr = gem.predict(m, co, pd.Period("2026Q3", "Q"))
        assert np.isfinite(pr["expected_error"]) and pr["sd"] > 0


def test_walk_forward_uses_only_earlier_data(fitted):
    cfg, p, _ = fitted
    t = pd.Period("2024Q1", "Q")
    m = gem.fit(p, cfg, before=t)
    full = gem.fit(p, cfg)
    assert m["habits"]["Nordic"]["n"] < full["habits"]["Nordic"]["n"]
    assert m["state_effect"]["n"] < full["state_effect"]["n"]


def test_forecasts_apply_the_model():
    import json
    d = json.loads((ROOT / "outputs" / "forecast_details.json").read_text())
    assert d["nordic"]["beat_source"].startswith("own record by channel state")
    assert d["logitech"]["beat_source"].startswith("guide-error model")
    g = pd.read_csv(ROOT / "steps" / "step7_forecast" / "outputs" / "guide_error_model.csv").set_index("company")
    assert d["nordic"]["hist_beat_pct"] == pytest.approx(g.loc["Nordic", "pred_expected_error"], abs=0.01)
    assert d["gn"]["guidance_anchor"]["august_bias_pts"] == pytest.approx(g.loc["GN", "pred_expected_error"], abs=0.01)


def test_challenger_is_pre_registered_once_per_spec_and_data():
    log = pd.read_csv(ROOT / "steps" / "step7_forecast" / "outputs" / "challenger_prereg_log.csv", dtype=str)
    assert len(log) >= 1 and not log.duplicated(["target", "spec_hash", "data_hash", "challenger"]).any()
    assert set(log["challenger"]) <= {"F16 pooled guide-error model", "F20 before F30 (supply-shortage quarters counted as lean)",
                                      "D25 own record with Nordic's own words as the state"}


def test_gn_habit_is_the_plain_mean_of_its_own_errors(fitted):
    cfg, p, m = fitted
    from guidance_record import gn_statement_errors
    e = gn_statement_errors(8).dropna(subset=["error_pts"])["error_pts"]
    h = m["habits"]["GN"]
    assert h["alpha"] == pytest.approx(e.mean()) and h.get("state_adjusted") is False          # F23
    assert gem.predict(m, "GN", pd.Period("2026Q3", "Q"))["gamma_applied"] == 0.0


def test_nordic_habit_excludes_shortage_quarters_and_keeps_the_previous_rule(fitted):
    """F30: Nordic's habit is its mean error when the channel was neither building nor in a supply shortage; the rule
    before F30 (shortage merged into lean) stays computable as a pre-registered challenger."""
    cfg, p, m = fitted
    h = m["habits"]["Nordic"]
    assert h["n_shortage"] >= 5 and h["n_not_building"] + h["n_building"] + h["n_shortage"] == h["n"]
    old = gem.fit(p, cfg, shortage=False)["habits"]["Nordic"]
    assert old.get("n_shortage", 0) == 0 and old["n_not_building"] == h["n_not_building"] + h["n_shortage"]
    pr = gem.predict(m, "Nordic", pd.Period("2026Q3", "Q"))
    assert pr["state_nordic"] == "lean" and pr["expected_error"] == pytest.approx(h["alpha"])


def test_nordic_walk_forward_scores_every_quarter(fitted):
    """P127: a rule with no estimate yet must fall back, not drop out of the score (NaN rows would flatter it)."""
    cfg, p, _ = fitted
    w = gem.walk_forward_nordic(p, cfg)
    assert w[["model", "previous_rule", "pooled_challenger", "wording_rule"]].notna().all().all()
