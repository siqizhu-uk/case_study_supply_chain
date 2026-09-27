"""Step 5g industry-cycle challenger (G29): point in time, same quarters as GR, pre-stated bar, spec hash, append-once log, no mutation."""
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

import cycle_challenger as cc  # noqa: E402
import cycle_challenger_report as ccr  # noqa: E402
import cycle_challenger_scores as ccs  # noqa: E402

NORDIC_AFTER_ORIGIN = ["nordic_consumer_yoy", "nordic_rev", "nordic_consumer", "nordic_beat_vs_guide_pct"]


@pytest.fixture(scope="module")
def data():
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    before = copy.deepcopy(cfg)
    res = ccr.run(p, cfg)
    return cfg, p, res, before


def _scramble(p: pd.DataFrame, cfg: dict, t: pd.Period) -> pd.DataFrame:
    """Every value published after origin(t) replaced by an absurd number (new frame)."""
    at, out = cc.origin(t, cfg), p.copy()
    for s, spec in cfg["cycle_challenger"]["series"].items():
        late = [q for q in p.index if q.end_time.normalize() + pd.Timedelta(days=cc.release_days(cfg, s)) > at]
        out.loc[late, spec["column"]] = 1e6
    out.loc[out.index >= t - 1, NORDIC_AFTER_ORIGIN] = 1e6      # Nordic reports t-1 the day after the origin
    return out


@pytest.mark.parametrize("q", ["2024Q4", "2025Q3", "2026Q2"])
def test_scrambling_post_origin_data_changes_nothing(data, q):
    cfg, p, _, _ = data
    t = pd.Period(q, "Q")
    ex = cfg["backtest"]["exclude_supply_constrained_from_training"]
    for m in ("CYC", "CYCw"):
        clean = cc.model_row(p, cfg, cc.designs(p, cfg)[m], t, ex)
        s = _scramble(p, cfg, t)
        dirty = cc.model_row(s, cfg, cc.designs(s, cfg)[m], t, ex)
        assert np.isclose(clean["total"], dirty["total"]) and clean["ntrain"] == dirty["ntrain"]


def test_regressor_is_t_minus_2_and_falls_back_by_persistence_when_not_published(data):
    cfg, p, _, _ = data
    t = pd.Period("2025Q3", "Q")
    assert cc.released_value(p["rseas_yoy"], t, cfg, "rseas") == pytest.approx(p.loc[t - 2, "rseas_yoy"])
    slow = copy.deepcopy(cfg)
    slow["cycle_challenger"]["series"]["wsts"]["release_days"] = 120           # t-2 not out at the origin -> t-3
    assert cc.released_value(p["wsts_yoy"], t, slow, "wsts") == pytest.approx(p.loc[t - 3, "wsts_yoy"])


def test_scored_on_the_same_quarters_as_gr_and_gr_is_step6s(data):
    from walkforward import walk_forward
    cfg, p, res, _ = data
    main = res["scores"][res["scores"]["scope"] == "main"]
    d = ccs.common(res["wf"], cfg)
    assert (main["n"] == len(d)).all() and set(main["first"]) == {d.index.min()} and set(main["last"]) == {d.index.max()}
    ref = walk_forward(p, cfg, None, h=2)["GR_total"].reindex(d.index)
    assert np.allclose(d["GR_total"], ref)


def test_spec_hash_moves_with_the_config_block_and_the_code_not_the_check_date(data, tmp_path):
    cfg, _, _, _ = data
    base = ccr.spec_hash(cfg)
    moved = copy.deepcopy(cfg)
    moved["cycle_challenger"]["lag_quarters"] = 3
    dated = copy.deepcopy(cfg)
    dated["cycle_challenger"]["check_on"] = "2027-03-01"
    assert ccr.spec_hash(moved) != base and ccr.spec_hash(dated) == base
    f = tmp_path / "code.py"
    f.write_text("a = 1\n")
    one = ccr.spec_hash(cfg, [f])
    f.write_text("a = 2\n")
    assert ccr.spec_hash(cfg, [f]) != one


def test_prereg_appends_once_per_spec_and_data(data, tmp_path):
    cfg, _, res, _ = data
    ccr.preregister(res, cfg, tmp_path)
    log = ccr.preregister(res, cfg, tmp_path)
    assert len(log) == 1 and log.iloc[0]["model"] == cfg["cycle_challenger"]["primary"]
    other = {**res, "hashes": {**res["hashes"], "data": "changed"}}
    assert len(ccr.preregister(other, cfg, tmp_path)) == 2


def test_committed_log_has_one_row_per_spec_and_data():
    log = pd.read_csv(ROOT / "steps" / "step5_supply_graph" / "outputs" / ccr.PREREG, dtype=str)
    assert not log.duplicated(ccr.KEY).any() and set(log["model"]) == {"CYC"}


def test_adoption_needs_rmse_evidence_and_an_unconcentrated_gain():
    cfg = load_config()
    row = {"scope": "main", "model": "CYC", "vs": "GR", "n": 9, "rmse": 20.0, "rmse_bench_same_quarters": 28.0, "rmse_ratio": 0.7,
           "dm_t": -2.5, "enc_t": 1.0, "gain_share_top3": 0.4}
    assert ccs.adoption(pd.DataFrame([row]), cfg)["bar_met"]
    assert not ccs.adoption(pd.DataFrame([{**row, "gain_share_top3": 0.8}]), cfg)["bar_met"]
    assert not ccs.adoption(pd.DataFrame([{**row, "rmse_ratio": 1.1, "enc_t": 3.0}]), cfg)["bar_met"]
    assert not ccs.adoption(pd.DataFrame([{**row, "dm_t": -1.0}]), cfg)["bar_met"]


def test_config_not_mutated_and_challenger_stays_out_of_the_forecast(data):
    cfg, _, res, before = data
    assert cfg == before
    assert "CYC" not in cfg["forecast_next_quarter"]["models"] and cfg["forecast_next_quarter"]["point_model"] == "GRi"
    assert res["adoption"]["role_this_print"].startswith("pre-registered challenger")
