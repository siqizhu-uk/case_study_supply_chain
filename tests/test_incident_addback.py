"""Decision F34: Logitech's disclosed supplier-incident loss is added back to what GRi reads, so the incident reaches Nordic's
Q4 once (the event term), not twice (the event term plus a guide fill that already carries it, amplified as the common cycle)."""
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

from core.config import load_config  # noqa: E402
import walkforward as wf  # noqa: E402

Q = pd.period_range("2025Q1", "2026Q3", freq="Q")


@pytest.fixture
def panel() -> pd.DataFrame:
    """Seven quarters: sales reported to 2026Q2, 2026Q3 guided but not reported (the live quarter)."""
    sales = pd.Series([1000.0, 1100.0, 1200.0, 1300.0, 1050.0, 1150.0, np.nan], index=Q)
    guide = pd.Series([990.0, 1080.0, 1190.0, 1280.0, 1040.0, 1140.0, 1202.5], index=Q)
    return pd.DataFrame({"logi_sales": sales, "logi_guide_mid": guide, "logi_sales_yoy": sales.pct_change(4, fill_method=None) * 100})


def _cfg(apply: bool = True) -> dict:
    cfg = copy.deepcopy(load_config())
    cfg["forecast_next_quarter"]["gri_ex_incident"]["apply"] = apply
    return cfg


def test_the_loss_sits_in_its_quarter_and_nowhere_else(panel):
    add = wf.incident_addback(panel, _cfg())
    loss = load_config()["structural_breaks"]["logitech_supplier_incident_2026"]["q2fy27_sales_hit_usdm"]
    assert add[pd.Period("2026Q3", "Q")] == pytest.approx(loss)
    assert (add.drop(pd.Period("2026Q3", "Q")) == 0).all()
    assert (wf.incident_addback(panel, _cfg(apply=False)) == 0).all()


def test_the_fill_gains_exactly_the_loss_and_nothing_else_moves(panel):
    add = wf.incident_addback(panel, _cfg())
    before, after = wf.logitech_sellin_forecast(panel), wf.logitech_sellin_forecast(panel, add)
    live = pd.Period("2026Q3", "Q")
    base = panel.loc[live - 4, "logi_sales"]
    assert (after[live] - before[live]) * base / 100 == pytest.approx(add[live])      # the level rises by the loss, in USD m
    assert after.drop(live).equals(before.drop(live))                                 # every other quarter bit-identical
    assert wf.logitech_sellin_forecast(panel, add * 0).equals(before)                 # no loss -> the F26 fill exactly


def test_a_reported_incident_quarter_and_its_year_later_base_are_both_adjusted(panel):
    p = panel.copy()
    p.loc[pd.Period("2026Q3", "Q"), "logi_sales"] = 1180.0                           # suppose the quarter is now reported
    p["logi_sales_yoy"] = p["logi_sales"].pct_change(4, fill_method=None) * 100
    add = pd.Series(0.0, index=Q)
    add[pd.Period("2025Q3", "Q")] = 20.0                                              # an incident a year earlier: the base quarter
    add[pd.Period("2026Q3", "Q")] = 20.0
    y = wf.logitech_sellin_yoy_ex(p, add)
    assert y[pd.Period("2026Q3", "Q")] == pytest.approx((1180 + 20) / (1200 + 20) * 100 - 100)
    untouched = [q for q in Q if q not in (pd.Period("2025Q3", "Q"), pd.Period("2026Q3", "Q"))]
    assert y[untouched].equals(p["logi_sales_yoy"][untouched])
    assert wf.logitech_sellin_yoy_ex(p, add * 0) is p["logi_sales_yoy"]              # nothing to add back -> the reported series itself


def test_monitor_flags_a_non_nordic_radio_certified_after_the_incident(monkeypatch):
    """Monitor row: 'judgment' while no grant since the incident is read; amber as soon as one shows a non-Nordic radio."""
    import attribution_path
    import dashboard
    cfg = load_config()
    real = attribution_path._readable_peripheral_grants()
    if (pd.to_datetime(real["grant_date"]) < pd.Timestamp(cfg["event_study"]["incident_date"])).all():   # nothing read since the incident
        assert dashboard._fcc_vendor_row(cfg)["level"] == "judgment"
    after = pd.Timestamp(cfg["event_study"]["incident_date"]) + pd.Timedelta(days=30)
    fake = pd.concat([real, pd.DataFrame([{"fcc_id": "JNZMR9999", "grant_date": f"{after:%Y-%m-%d}", "chip_vendor": "Telink",
                                           "year": after.year, "nordic": False}])], ignore_index=True)
    monkeypatch.setattr(attribution_path, "_readable_peripheral_grants", lambda: fake)
    row = dashboard._fcc_vendor_row(cfg)
    assert row["level"] == "amber" and "1 of the 1 read since the incident carry a non-Nordic radio" in row["read"]
