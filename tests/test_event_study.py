"""Step 5d (event_study.py, event_study_report.py, structural_breaks_chain.py): the 2026 supplier incident pushed back
through the chain, and every structural break / regime read through it (decision G23).
Run: pytest -q tests/test_event_study.py"""
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

from core.config import load_config  # noqa: E402

import event_study as es  # noqa: E402
import event_study_report as esr  # noqa: E402


@pytest.fixture(scope="module")
def mid():
    cfg = load_config()
    x = es.inputs(cfg)
    return cfg, x, es.run(cfg, x)


def _lost_sales(cfg, sc="mid") -> float:
    sb, s = cfg["structural_breaks"]["logitech_supplier_incident_2026"], cfg["event_study"]["scenarios"][sc]
    return sb["q2fy27_sales_hit_usdm"] + sb["q3fy27_sales_hit_usdm"] * s["q3fy27_loss_scale"] + s["q4fy27_loss_usdm"]


def test_block_arithmetic_conserves_mass():
    b = es.Block(2.0, 12.0, -10.0)
    lo, hi = es.split(b, 5.0)
    assert lo.usd + hi.usd == pytest.approx(-10.0) and lo.usd == pytest.approx(-3.0)
    q = es.by_quarter([b, es.Block(13.0, 13.0, 4.0)], pd.Period("2026Q1", "Q"), list(pd.period_range("2026Q1", "2026Q2", freq="Q")), 13.0)
    assert q["2026Q1"] == pytest.approx(-10.0) and q["2026Q2"] == pytest.approx(4.0)
    assert sum(c.usd for c in es.clamp(b, 7.0)) == pytest.approx(-10.0)


def test_propagation_conserves_the_gross_nordic_effect(mid):
    """Before netting the guide and without restock: Nordic's change over all quarters = - content x lost Logitech sales;
    every node carries the whole loss and the shown quarters hold all of it."""
    cfg, x, r = mid
    lost = _lost_sales(cfg)
    assert es.total(r["logitech"]) == pytest.approx(-lost)
    assert es.total(r["build"]) == pytest.approx(-lost)
    assert es.total(r["customers"]) == pytest.approx(-lost * x["named_share"])
    assert es.total(r["nordic"]) == pytest.approx(-lost * x["content"]["p50"])
    assert es.total(r["nordic_cut"]) + es.total(r["nordic_stock"]) == pytest.approx(es.total(r["gross_ship"]))
    q = es.by_quarter(r["nordic"], x["q0"], x["quarters"], x["wq"])
    assert q.sum() == pytest.approx(es.total(r["nordic"]))


def test_no_nordic_effect_before_the_incident(mid):
    """Chips shipped before the incident are stock, not lost shipments: no Nordic (or build) effect before its week,
    and no order cut inside the frozen window."""
    _, x, r = mid
    assert all(b.start >= r["w0"] - 1e-9 for b in r["nordic"] + r["build"] if abs(b.usd) > 1e-12)
    assert all(b.start >= r["w0"] + r["frozen"] - 1e-9 for b in r["nordic_cut"] if abs(b.usd) > 1e-12)
    q = es.by_quarter(r["nordic"], x["q0"], x["quarters"], x["wq"])
    assert q["2026Q1"] == 0 and abs(q["2026Q2"]) < 1e-9
    assert es.total(r["gross_ship"]) == pytest.approx(es.total(r["nordic"]))     # the lead mapping alone does book before


def test_timing_respects_the_lead(mid):
    """A lost Logitech sale is a lost build d weeks earlier and a lost Nordic shipment (lead - d) before that; stock at the
    holder is used from the restart week minus the lead. No lost sale before the pre-incident pipeline has sold."""
    cfg, x, r = mid
    pt = r["paths"]
    last_sale = max(b.end for b in r["logitech"])
    assert min(b.start for b in r["logitech"]) >= r["w0"] + r["d_bar"] - 1e-9
    assert max(b.end for b in r["nordic_cut"]) <= last_sale - pt["lead_weeks"].min() + 1e-9
    assert min(b.start for b in r["nordic_stock"]) == pytest.approx(r["wR"] - pt["lead_weeks"].max())
    assert (pt["build_weeks"] < pt["lead_weeks"]).all() and pt["weight"].sum() == pytest.approx(1.0)


def test_lead_and_gross_match_step7c(mid):
    """Same graph, same lead, same content as step 7c: its Q3 gross is the event study's lead mapping in that quarter."""
    from chain_forecast import nordic_lead_weeks, supplier_incident
    cfg, x, r = mid
    pt = r["paths"]
    assert float(np.dot(pt["weight"], pt["lead_weeks"])) == pytest.approx(nordic_lead_weeks(cfg, pd.Timestamp(x["as_of"])))
    cf = supplier_incident(cfg, pd.read_csv(es.S2_PATH))
    q = es.by_quarter(r["gross_ship"], x["q0"], x["quarters"], x["wq"])
    assert q["2026Q3"] == pytest.approx(cf["lead_shift_gross_usdm"], abs=0.05)   # F21: 7c's gross now comes from the event study;
    #                                                                                     its old lead-shift gross is kept as this cross-check


def test_guide_netting_and_restock_bound(mid):
    cfg, x, r = mid
    bd = esr.band(cfg, x)
    s = esr.summary(cfg, x, r, bd)
    assert s["net_q"] == pytest.approx(s["event_q"] * (1 - cfg["chain_forecast"]["supplier_incident"]["share_in_nordic_guide"]))
    assert (bd["band_low"] <= bd["band_high"] + 1e-12).all()
    up = es.run(cfg, x, "upside")
    lost = _lost_sales(cfg, "upside")
    assert 0 < up["drawn"] <= lost
    assert es.total(up["nordic_restock"]) == pytest.approx(up["drawn"] * cfg["event_study"]["scenarios"]["upside"]["restock_share"] * x["content"]["p50"])
    assert all(0.9 <= v <= 1.0 for v in s["on_order"].values())       # Q3 cuts were booked orders (12-16 wk lead)


def test_config_is_read_not_mutated(mid):
    cfg = load_config()
    before = copy.deepcopy(cfg)
    x = es.inputs(cfg)
    for sc in ("mid", "downside", "upside"):
        es.run(cfg, x, sc)
    esr.band(cfg, x)
    assert cfg == before


def test_breaks_table_has_one_row_per_config_entry(mid):
    from core.ingest import load_all
    from core.tiers import build_panel
    from structural_breaks_chain import breaks_chain
    cfg, x, r = mid
    p = build_panel(load_all(), cfg)
    t = breaks_chain(p, cfg, esr.summary(cfg, x, r, esr.band(cfg, x)))
    assert len(t) == len(cfg["structural_breaks"]) + len(cfg["regimes"])
    assert set(t["event"]) == set(cfg["structural_breaks"]) | set(cfg["regimes"])
    assert (t["shock_or_break"] != "not classified").all() and (t["nordic_revenue_consequence"].str.len() > 3).all()
    assert t.set_index("event").loc["logitech_supplier_incident_2026", "shock_or_break"] == "shock"
    known = set(pd.read_csv(ROOT / "audit" / "pitfalls.csv")["id"])
    known |= {i for f in (ROOT / "steps").glob("step*/config/decisions.csv") for i in pd.read_csv(f).iloc[:, 0]}
    ids = {i.strip() for v in t["ids"] if v and v != "none" for i in v.split(",")}
    assert ids <= known, ids - known
