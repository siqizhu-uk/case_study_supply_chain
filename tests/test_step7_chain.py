"""Step 7c (chain_forecast.py): the supply chain as terms inside each forecast, weighted by the back-test."""
import copy
import re
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

import chain_forecast as cf  # noqa: E402

DECISIONS = {"Lag", "Mechanism", "Attribution", "Structural breaks", "Chain", "Limitations", "Lag + Attribution"}


@pytest.fixture(scope="module")
def run():
    from attribution_path import build_path
    from walkforward import live_forecasts, walk_forward
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    path = build_path(cfg, panel=p, n=2000)
    wf = {h: walk_forward(p, cfg, h=h) for h in (1, 2)}
    live = live_forecasts(p, cfg, None, {1: "2026Q3", 2: "2026Q4"}).reset_index()
    return cfg, p, path, cf.run_chain(p, cfg, path, wf, live, write=False)


def test_every_print_has_terms_tied_to_the_briefs_decisions(run):
    t = run[3]["terms"]
    assert {"Nordic Q3 2026", "Logitech Q2 FY27", "GN Q3 2026"} <= set(t["print"])
    assert set(t["decision"]) <= DECISIONS
    nordic = set(t.loc[t["print"] == "Nordic Q3 2026", "decision"])
    assert {"Lag", "Mechanism", "Attribution", "Structural breaks", "Limitations"} <= nordic


def test_weight_rule():
    rng = np.random.default_rng(0)
    x = pd.Series(rng.normal(size=30))
    guide = pd.Series(np.full(30, 100.0))
    strong = cf.encompassing_weight(x, guide + 0.8 * x + rng.normal(scale=0.1, size=30), guide, 2.0)
    assert strong["t"] > 2 and strong["weight"] == pytest.approx(strong["beta"])
    noise = cf.encompassing_weight(x, guide + rng.normal(size=30), guide, 1e9)
    assert noise["weight"] == 0.0
    over = cf.encompassing_weight(x, guide + 3 * x, guide, 2.0)
    assert over["weight"] == 1.0                                   # capped at 1


def test_nordic_weights_follow_the_back_test(run):
    h = run[3]["nordic"]["horizons"]
    for H in (1, 2):
        for r in h[H]["tests"].values():
            assert 0.0 <= r["weight"] <= 1.0
            assert r["weight"] == 0.0 or r["t"] >= run[0]["chain_forecast"]["weight_t_min"]
    assert h[1]["contribution_usdm"] == pytest.approx(h[1]["weight"] * (
        h[1]["live"][f"{h[1]['model_used']}_total"] - h[1]["live"]["GB_total"]) if h[1]["model_used"] else 0.0)


def test_supplier_incident_nets_out_the_share_in_the_guide(run):
    cfg, p, path, res = run
    inc = res["incident"]
    assert inc["nordic_gross_usdm"] < 0 and 5 < inc["lead_weeks"] < 30
    assert inc["nordic_net_usdm"] == pytest.approx(inc["nordic_gross_usdm"] * (1 - inc["share_in_nordic_guide"]))
    cfg2 = copy.deepcopy(cfg)
    cfg2["chain_forecast"]["supplier_incident"]["share_in_nordic_guide"] = 0.0
    assert cf.supplier_incident(cfg2, path)["nordic_net_usdm"] == pytest.approx(inc["nordic_gross_usdm"])


def test_chain_terms_move_the_forecasts(run):
    from backtest import guidance_bias
    from forecast import forecast_logitech, forecast_nordic
    cfg, p, path, res = run
    gb = guidance_bias(p, cfg)
    reg = {"ok": False}
    fl0, fl1 = forecast_logitech(cfg, gb, p), forecast_logitech(cfg, gb, p, chain=res)
    assert fl1["point"] - fl0["point"] == pytest.approx(res["logitech"]["contribution_usdm"], abs=0.15)
    fn0, fn1 = forecast_nordic(cfg, gb, reg, p), forecast_nordic(cfg, gb, reg, p, chain=res)
    moved = res["nordic"]["horizons"][1]["contribution_usdm"] + res["incident"]["nordic_net_usdm"]
    assert fn1["point"] - fn0["point"] == pytest.approx(moved, abs=0.15)


def test_gn_readacross_is_only_used_above_the_bar(run):
    t = run[3]["gn"]["tests"]
    assert (t["used"] == (t["corr"] >= run[0]["chain_forecast"]["gn_min_corr"])).all()


def test_note_quotes_the_scenarios_and_q4_as_computed():
    """Every base and every scenario that moves the print by 2m or more must appear in the note exactly as
    outputs/scenarios.csv holds it (smaller ones stay in the CSV and on the dashboard)."""
    note = (ROOT / "deliverables" / "investment_note.md").read_text()
    sc = pd.read_csv(ROOT / "outputs" / "scenarios.csv")
    for r in sc[(sc["vs_base"].abs() >= 2) | (sc["scenario"].str.startswith("base"))].itertuples():
        v = re.escape(f"{r.point:,.0f}")
        assert re.search(rf"(\| |/ |\*\*){v}( \||\*\*| /)", note), (r.scenario, r.point)     # own cell, bold, or one side of 'a / b'
        if abs(r.vs_base) >= 0.5:
            assert f"{r.vs_base:+.0f}".replace("-", "−") in note, (r.scenario, r.vs_base)
    q4 = sc[(sc["print"] == "Nordic Q4 2026")].iloc[0]
    assert f"{q4.low:.0f} – {q4.high:.0f}" in note or f"{q4.low:.0f}–{q4.high:.0f}" in note


def test_logitech_weight_compares_the_same_quarters(run):
    lg = run[3]["logitech"]
    assert lg["n_chain"] == lg["n_gb"]                                       # P84: same quarters for both forecasters
    inv = (1 / lg["rmse_chain_usdm"] ** 2) / (1 / lg["rmse_chain_usdm"] ** 2 + 1 / lg["rmse_gb_usdm"] ** 2)
    assert lg["weight_inverse_mse"] == pytest.approx(inv)                   # the diagnostic
    assert lg["weight"] == (0.0 if lg["weight_rule"].startswith("guide only") else pytest.approx(inv))   # F29: h1 = guide method
    assert 0 <= lg["weight_cov"] <= 1 and 0 <= lg["weight_with_implied"] <= 1


def test_formulas_reproduce_the_forecast_table():
    """The formula section shows each rule with this run's numbers, and those numbers end in the published point and range."""
    sys.path.insert(0, str(ROOT / "steps" / "step7_forecast" / "src"))
    import formulas
    fc = pd.read_csv(ROOT / "outputs" / "forecasts.csv")
    bl = formulas.blocks()
    assert len(bl) == len(fc) == 6
    for b, (_, r) in zip(bl, fc.iterrows()):
        pts = {f"{r['point']:,.1f}", f"{r['point']:,.0f}", f"{r['point']:.1f}"}
        assert any(p in b["numbers"] for p in pts), (b["print"], r["point"])
        assert any(f"{r['low']:{f}}" in b["range"] for f in (",.1f", ",.0f", ".1f")), (b["print"], r["low"])
