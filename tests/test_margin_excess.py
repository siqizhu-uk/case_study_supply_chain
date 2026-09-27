"""Channel-excess term in Nordic's GM forecast (decision F25): no look-ahead in the walk-forward, the adoption flag follows
the pre-registered rule, and the Nordic GM uses the one-off-adjusted series (P116)."""
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

import margin_excess as me  # noqa: E402
from margin_model import nordic_gm  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def panel(cfg):
    return build_panel(load_all(), cfg)


@pytest.fixture(scope="module")
def inputs(cfg, panel):
    excess = me.load_excess(cfg)
    rows = me.peer_changes(me.load_peer_gm(), excess, cfg)
    nordic = panel["nordic_gm_adj"].dropna()
    nordic.index = pd.PeriodIndex(nordic.index, freq="Q")
    return nordic, rows, excess


def test_spec_is_the_preregistered_one(cfg):
    sp = me.spec(cfg)
    assert sp["states"] == ["building", "drawdown"] and sp["state_lag_quarters"] == 1
    assert sp["max_abs_change_pts"] == 10.0 and sp["t_min"] == 2.0 and sp["first_target"] == "2012Q1"


def test_peer_rows_use_consecutive_quarters_and_flag_accounting_events(cfg, inputs):
    _, rows, _ = inputs
    assert rows["excess_lag"].isin([0.0, 1.0]).all()
    assert (rows["accounting_event"] == (rows["d_gm"].abs() > 10.0)).all()
    gm = me.load_peer_gm().set_index(["company", "quarter"])["gm_pct"]
    for _, r in rows.sample(20, random_state=0).iterrows():          # dGM is this quarter minus the one just before
        assert r["d_gm"] == pytest.approx(gm[(r["company"], r["quarter"])] - gm[(r["company"], r["quarter"] - 1)])


@pytest.mark.parametrize("target", ["2022Q3", "2023Q3", "2025Q2"])
def test_walk_forward_has_no_look_ahead(cfg, inputs, target):
    """Scrambling every datum dated >= t (peer GM changes, cycle states, Nordic GM) leaves the forecast for t unchanged."""
    nordic, rows, excess = inputs
    t = pd.Period(target, "Q")
    rng = np.random.default_rng(1)
    rows2 = rows.copy()
    late = rows2["quarter"] >= t
    rows2.loc[late, "d_gm"] = rng.normal(0, 5, late.sum())
    rows2.loc[late, "excess_lag"] = rng.integers(0, 2, late.sum()).astype(float)
    rows2.loc[late, "accounting_event"] = False
    excess2 = excess.copy()
    excess2[excess2.index >= t] = 1 - excess2[excess2.index >= t]
    nordic2 = nordic.copy()
    nordic2[nordic2.index > t] = nordic2[nordic2.index > t] + 20        # the target's own actual is what is scored, not used
    a = me.walk_forward(nordic, rows, excess, cfg).set_index("target").loc[target]
    b = me.walk_forward(nordic2, rows2, excess2, cfg).set_index("target").loc[target]
    assert a["with_term"] == pytest.approx(b["with_term"]) and a["delta_t"] == pytest.approx(b["delta_t"])
    assert a["last_quarter"] == b["last_quarter"]


def _adopt(cfg, delta, t, r_base, r_term):
    est = {"delta": delta, "se": abs(delta / t), "t": t}
    wf = pd.DataFrame({"err_last_quarter": [r_base], "err_with_term": [r_term], "excess_t_1": [1.0]})
    return me.adoption(est, wf, cfg)


def test_adoption_follows_the_prestated_rule(cfg):
    assert _adopt(cfg, -0.8, -2.5, 2.0, 1.5)["adopted"]                  # negative, |t| >= 2, lower RMSE
    assert not _adopt(cfg, -0.8, -1.9, 2.0, 1.5)["adopted"]              # |t| below the bar
    assert not _adopt(cfg, 0.8, 2.5, 2.0, 1.5)["adopted"]                # wrong sign, however significant
    assert not _adopt(cfg, -0.8, -2.5, 2.0, 2.1)["adopted"]              # does not lower Nordic's walk-forward error
    assert not _adopt(cfg, -0.8, -2.5, 2.0, 2.0)["adopted"]              # a tie is not an improvement


def test_live_result_matches_the_rule(cfg, panel, inputs):
    m = nordic_gm(panel, cfg)
    ex = m["excess"]
    expected = ex["delta"] < 0 and abs(ex["t"]) >= 2.0 and ex["wf_rmse_with_term"] < ex["wf_rmse_last_quarter"]
    assert ex["adopted"] == expected
    if not ex["adopted"]:
        assert ex["applied_pts"] == 0.0
    assert ex["gm_if_excess"] == pytest.approx(m["point"] - ex["applied_pts"] + ex["delta"], abs=0.051)


def test_nordic_gm_uses_the_one_off_adjusted_series(cfg, panel):
    """P116: the Q2 2024 write-down and the Q4 2025 one-off must not enter the rule scores or the base."""
    c2 = copy.deepcopy(cfg)
    c2["structural_breaks"]["nordic_q2_2024_writedown"]["adj_gm_pct"] = 10.0     # an absurd adjustment must move the scores
    p2 = build_panel(load_all(), c2)
    assert nordic_gm(p2, c2)["scores"] != nordic_gm(panel, cfg)["scores"]
    assert nordic_gm(panel, cfg)["series"] == "one-off adjusted"
