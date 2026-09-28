"""Nordic's guidance history 2017-2021 (pipelines/A_company_financials/src/pipeline_a/nordic_guidance.py, F32) and the
rows it adds to nordic_quarterly.csv. Run: pytest -q tests/test_nordic_guidance.py"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "pipelines" / "A_company_financials" / "src")] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

from pipeline_a import nordic_guidance as ng  # noqa: E402
from pipeline_a.newsweb import classify  # noqa: E402

RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"


@pytest.fixture(scope="module")
def hist():
    return pd.read_csv(RAW / "nordic_guidance_history.csv", dtype={"quote_check": str}).fillna("")


def test_every_excerpt_is_checked_and_carries_its_numbers(hist):
    """Each statement rests on a cached document (or the ledger's recorded check on a fresh clone) and the typed range
    appears in its excerpt."""
    assert hist["quote_check"].str.startswith("found").all(), hist[~hist["quote_check"].str.startswith("found")]
    assert hist["numbers_in_quote"].astype(str).str.lower().eq("true").all()
    assert hist["source_key"].str.len().gt(0).all()


def test_quarterly_initial_guides_equal_the_typed_series(hist):
    c = ng.consistency(hist)
    assert len(c) >= 18 and c["consistent"].all(), c[~c["consistent"]]


def test_half_year_guides_are_a_separate_record_and_never_pooled_with_quarterly_beats(hist):
    """2017-18 guides are half-year ranges (a different horizon); they stay out of the quarterly guide-error series."""
    h = ng.half_year_record(hist)
    assert list(h["period"]) == ["H1 2017", "H2 2017", "H1 2018", "H2 2018"]
    assert h["lowered"].sum() == 1 and h.loc[h["period"] == "H2 2018", "error_vs_first_pct"].iloc[0] < -9
    from guidance_record import nordic_quarters
    p = pd.read_csv(ROOT / "outputs" / "tier_panel.csv")
    p.index = pd.PeriodIndex(p["quarter"], freq="Q")
    n = nordic_quarters(p).dropna(subset=["revenue_usdm"])
    assert n.index.min() == pd.Period("2019Q1", "Q") and len(n) >= 30          # quarterly record starts with the first quarterly guide


def test_intra_quarter_raises_are_logged_not_scored(hist):
    """P130: the model scores the initial (report) guide; the two 2020 raises are kept beside it."""
    q = ng.quarterly_guides(hist)
    raised = set(q.loc[q["raised_before_print"], "quarter"])
    assert raised == {"2020Q2", "2020Q3"}
    n = pd.read_csv(RAW / "nordic_quarterly.csv").set_index("quarter")
    assert (n.loc["2020Q3", ["guide_low_usdm", "guide_high_usdm"]].tolist() == [95.0, 105.0])


def test_newsweb_titles_before_2021_classify_to_the_right_key():
    assert classify("Nordic Semiconductor ASA's Fourth Quarter 2018 and Full Year 2018 Results", "2019-02-05") == "2018Q4"
    assert classify("Nordic Semiconductor ASA – First quarter 2020 results", "2020-04-21") == "2020Q1"
    assert classify("Correction - Q2 2017 Report", "2017-10-23") == "2017Q2"
    assert classify("Nordic Semiconductor: Annual Report 2019 and update on the impact of the coronavirus", "2020-03-19") == "AR2019"
    assert classify("Nordic Semiconductor sees third quarter revenue exceeding previous guidance", "2020-09-04") is None
