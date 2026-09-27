"""Step 7f Logitech ODM challenger (F28): the forecast date's information set in history and live, no look-ahead, stays out of the forecast."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for s in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(s))


def test_every_reported_quarter_uses_three_months_and_no_future_beats():
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    import logitech_odm as L
    cfg = load_config()
    p = build_panel(load_all(), cfg)
    wf = L.run(p, cfg)["walkforward"]
    assert (wf["odm_months"] == cfg["logitech_odm_challenger"]["months_known"]).all()   # same information set in history and live
    assert (wf["n_train"] == range(len(wf))).all()                      # each quarter trains on the quarters before it only
    assert cfg["logitech_odm_challenger"]["role"] == "challenger"
