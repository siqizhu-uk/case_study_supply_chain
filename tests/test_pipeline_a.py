"""Offline tests for the company-financial pipeline (no network)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines" / "A_company_financials" / "src"))

from pipeline_a.manifest import COMPANIES, FILINGS, VERIFY_COLUMNS
from pipeline_a.sec import _duration_quarters, _instant
from pipeline_a.filings import _patterns, _in
from pipeline_a.paths import DATA_RAW, DATA_PROC


def test_manifest_covers_six_companies_and_raw_files_exist():
    model = {c for c, m in COMPANIES.items() if m.get("in_sec_quarterly", True)}
    assert model == {"nordic", "logitech", "gn", "ingram", "tdsynnex", "amazon"}
    assert set(COMPANIES) - model == {"arrow", "avnet", "microchip", "silicon_labs",          # step-3 context filers
                                      "bestbuy", "walmart", "target", "cdw"}           # step-5 retail / reseller cover proxies
    for c, m in COMPANIES.items():
        if m["raw_csv"]:
            assert (DATA_RAW / m["raw_csv"]).exists(), c
    for c in VERIFY_COLUMNS:
        cols = pd.read_csv(DATA_RAW / COMPANIES[c]["raw_csv"], nrows=1).columns
        assert set(VERIFY_COLUMNS[c]) <= set(cols)
    assert all(u.startswith("https://") for f in FILINGS.values() for u in f.values())


def test_q4_is_derived_from_annual_minus_three_quarters():
    df = pd.DataFrame({
        "start": pd.to_datetime(["2024-04-01", "2024-07-01", "2024-10-01", "2024-04-01"]),
        "end":   pd.to_datetime(["2024-06-30", "2024-09-30", "2024-12-31", "2025-03-31"]),
        "val":   [100.0, 110.0, 120.0, 450.0], "filed": ["a", "b", "c", "d"]})
    s = _duration_quarters(df)
    assert s[pd.Period("2025Q1", "Q")] == pytest.approx(120.0)   # 450 - (100+110+120)
    assert len(s) == 4


def test_instant_dedupes_by_latest_filing():
    df = pd.DataFrame({"start": [pd.NaT, pd.NaT], "end": pd.to_datetime(["2024-12-31", "2024-12-31"]),
                       "val": [1.0, 2.0], "filed": ["2025-01-01", "2025-06-01"]})
    assert _instant(df)[pd.Period("2024Q4", "Q")] == 2.0


def test_number_variants_and_matching():
    assert any("218" in p for p in _patterns(218.6)) and any("2,171" in p for p in _patterns(2171.0))
    assert _in("Consumer 94 312 67 411", 94.3)          # Nordic USD-thousands table
    assert _in("Revenue was USD 218.6 million", 218.6)
    assert not _in("Revenue was USD 1218.6 million", 218.6)   # no partial match
    assert _in("Revenue DKK 2,171m", 2171)


def test_data_config_integrity():
    from pipeline_a.manifest import DATA_CONFIG, filings_from_config
    cfg = pd.read_csv(DATA_CONFIG, dtype=str).fillna("")
    assert {"company", "key", "source_type", "url", "validated"} <= set(cfg.columns)
    assert cfg["url"].str.startswith("https://").all()
    assert set(cfg["company"]) <= set(COMPANIES)
    assert cfg["validated"].isin(["", "yes", "no", "manual", "unused", "no_cells", "n/a", "rejected"]).all()
    f = filings_from_config()
    assert "2026Q2" in f["gn"] and "2026Q2" in f["logitech"] and "2026Q2" in f["tdsynnex"]


def test_verbal_metrics_match_company_csv_cells():
    from pipeline_a.verbal import check_consistency, COLUMN
    v = pd.read_csv(DATA_RAW / "verbal_metrics.csv")
    assert set(v["metric"]) <= set(COLUMN)
    assert (v["grade"] == "C").all() and v["quote"].str.len().gt(3).all() and v["source_url"].str.startswith("http").all()
    out = check_consistency()
    assert len(out) == len(v) and out["consistent"].all(), out[~out["consistent"]]


def test_verbal_quote_check_uses_cached_report(tmp_path, monkeypatch):
    from pipeline_a import verbal
    monkeypatch.setattr(verbal, "CACHE", tmp_path / "verbal")
    monkeypatch.setattr(verbal, "FILING_CACHE", tmp_path / "filings")
    (tmp_path / "filings" / "acme").mkdir(parents=True)
    (tmp_path / "filings" / "acme" / "2025Q1.htm").write_text("<p>Channel  inventory was reduced in the quarter.</p>")
    doc = verbal._cached_filing("acme", "2025Q1")
    assert doc is not None and verbal._contains(doc, "channel inventory was reduced") is True
    assert verbal._contains(doc, "inventory increased") is False
    assert verbal._fetch("https://example.invalid/x", download=False) is None


def test_uncited_grade_c_cells_are_listed_not_hidden():
    from pipeline_a.verbal import uncited_cells
    u = uncited_cells()
    assert set(u.columns) == {"company", "quarter", "metric", "csv_value"}
    assert (DATA_PROC / "verbal_uncited.csv").exists()
