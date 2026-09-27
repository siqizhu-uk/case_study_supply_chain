"""Monitoring plan (steps/step7_forecast/src/monitoring.py): triggers quote the current forecasts, never typed numbers."""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

import monitoring as mon  # noqa: E402
from core.config import OUTPUTS  # noqa: E402


def test_plan_quotes_forecasts_through_tokens_not_typed_numbers():
    plan = pd.read_csv(mon.PLAN).fillna("")
    fc_rows = plan[plan["watch"].str.contains("revenue and gross margin|sales and gross margin|EBITA", case=False)]
    assert len(fc_rows) >= 2
    for col in ("trigger", "conclusion_tested"):
        for txt in fc_rows[col]:
            assert "{" in txt, txt                                    # a token, filled from outputs/forecasts.csv
            assert not re.search(r"\d{3}-\d{3}", txt), txt            # no typed revenue range


def test_every_token_resolves_to_the_current_forecast():
    tok = mon.forecast_tokens()
    fc = pd.read_csv(OUTPUTS / "forecasts.csv").set_index(["print", "metric"])
    nordic = fc.loc[("Nordic Q3 2026", "Revenue (USDm)")]
    assert tok["NORDIC_REV"] == f"{nordic['point']:.0f}"
    assert tok["NORDIC_REV_RANGE"] == f"{nordic['low']:.0f}-{nordic['high']:.0f}"
    plan = pd.read_csv(mon.PLAN).fillna("")
    for txt in pd.concat([plan["trigger"], plan["conclusion_tested"], plan["action_if_triggered"]]):
        mon.fill(txt, tok)                                            # raises KeyError on an unknown token
