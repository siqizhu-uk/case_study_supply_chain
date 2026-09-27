"""Offline tests for Pipeline B (macro / industry context). No network: parsers are exercised on fixtures."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines" / "B_macro_industry" / "src"))

from pipeline_b.wsts import _sheet_to_long  # noqa: E402
from pipeline_b.quotes import _norm  # noqa: E402
from pipeline_b.paths import DATA_CONFIG  # noqa: E402


def test_wsts_bluebook_layout_parses_worldwide_rows():
    rows = [["36 Years"] + [None] * 12, [None, "January", "February"] + [None] * 10,
            [2024.0] + [None] * 12, ["Americas", 1000, 1100] + [None] * 10, ["Worldwide", 40000, 41000] + [None] * 10,
            [2025.0] + [None] * 12, ["Worldwide", 50000, 0] + [None] * 10]
    s = _sheet_to_long(pd.DataFrame(rows))
    assert s[pd.Timestamp(2024, 1, 1)] == 40.0 and s[pd.Timestamp(2024, 2, 1)] == 41.0 and s[pd.Timestamp(2025, 1, 1)] == 50.0
    assert pd.Timestamp(2025, 2, 1) not in s.index          # zero = not yet reported


def test_quote_normalisation():
    assert _norm("Projected  to “surpass” 5.3\nbillion") == "projected to 'surpass' 5.3 billion"


def test_pipeline_b_config_lists_method_and_status_for_every_source():
    cfg = pd.read_csv(DATA_CONFIG, dtype=str).fillna("")
    for col in ("source", "key", "url", "grade", "retrieval_method", "validation_method", "validated"):
        assert col in cfg.columns
    assert cfg["key"].is_unique and (cfg["retrieval_method"] != "").all() and (cfg["validation_method"] != "").all()
    assert set(cfg["validated"]) <= {"yes", "no", "partial", "manual", "not_fetched", "rejected", ""}
    assert (cfg.loc[cfg["quote"] != "", "grade"] == "C").all()      # every grade-C document carries the sentence relied on
