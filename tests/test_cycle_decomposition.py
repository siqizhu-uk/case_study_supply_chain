"""Step 5g addendum (G30): gaps to CH and anomalies are internally consistent."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))


def test_summary_arithmetic():
    from cycle_decomposition import summary
    d = pd.DataFrame({m: v for m, v in {"CH_total": [100.0, 110, 120], "actual_total": [105.0, 118, 121],
                                       "GRi_total": [104.0, 116, 125], "GR_total": [102.0, 112, 130], "CYC_total": [90.0, 100, 115]}.items()})
    d = d.assign(**{f"{m}_minus_CH": d[f"{m}_total"] - d["CH_total"] for m in ("GRi", "GR", "CYC")},
                 actual_minus_CH=d["actual_total"] - d["CH_total"])
    lv = {"GRi_minus_CH": -3.0, "GR_minus_CH": 10.0, "CYC_minus_CH": -4.0}
    s = summary(d, lv).set_index("model")
    for m in ("GRi", "GR", "CYC"):
        assert s.loc[m, "live_anomaly"] == pytest.approx(lv[f"{m}_minus_CH"] - d[f"{m}_minus_CH"].mean())
    assert s.loc["actual", "hist_mean_gap"] == pytest.approx(d["actual_minus_CH"].mean())


def test_committed_outputs_consistent():
    s = pd.read_csv(ROOT / "steps" / "step5_supply_graph" / "outputs" / "cycle_decomposition_summary.csv").set_index("model")
    for m in ("GRi", "GR", "CYC"):
        assert s.loc[m, "live_anomaly"] == pytest.approx(s.loc[m, "live_gap"] - s.loc[m, "hist_mean_gap"], abs=0.02)
    assert np.isfinite(s.loc[["GRi", "GR", "CYC"], "corr_with_actual_gap"]).all()
