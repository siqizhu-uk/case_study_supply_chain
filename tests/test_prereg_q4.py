"""Nordic Q4 pre-registration (prereg_q4.py, F22): once per spec/data, graph changes re-log, scoring fills the record."""
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)] + [str(p) for p in sorted((ROOT / "steps").glob("step*/src"))]

import prereg_q4 as pq  # noqa: E402


def test_committed_log_has_one_forecast_and_one_challenger_per_spec_and_data():
    log = pd.read_csv(pq.LOG, dtype=str)
    assert not log.duplicated(["target", "model", "spec_hash", "data_hash"]).any()
    last = log[(log["spec_hash"] == log.iloc[-1]["spec_hash"]) & (log["data_hash"] == log.iloc[-1]["data_hash"])]
    assert set(last["role"]) == {"forecast", "challenger"} and (last["role"] == "forecast").sum() == 1
    assert set(last["model"]) in ({"GR", "CH"}, {"GRi", "GR", "CH"})         # F26: GRi the forecast, GR kept as a challenger


def test_spec_hash_changes_when_the_edge_table_changes(tmp_path, monkeypatch):
    from core.config import load_config
    cfg = load_config()
    edges = tmp_path / "supply_graph.csv"
    shutil.copy(ROOT / "config" / "supply_graph.csv", edges)
    monkeypatch.setattr(pq, "SPEC_FILES", [edges] + pq.SPEC_FILES[1:])
    before = pq.spec_hash(cfg)
    e = pd.read_csv(edges, dtype=str, keep_default_na=False)
    e.loc[e["edge_id"] == "E08", "lag_weeks_mid"] = "9"                      # one edge lag moved: E08 ODM -> Logitech 8 -> 9 weeks
    e.to_csv(edges, index=False)
    assert pq.spec_hash(cfg) != before


def test_score_fills_only_the_forecast_of_record():
    log = pd.DataFrame([{"target": "2026Q4", "model": m, "spec_hash": s, "data_hash": "d", "point": pt, "benchmark_gb_usdm": "221.1",
                         "actual_usdm": "", "scored_on": ""} for s, m, pt in (("old", "GR", "230"), ("new", "GR", "222.4"), ("new", "CH", "212.2"))])
    out = pq.score(log, 215.0, "2027-02-05")
    assert out.loc[0, "actual_usdm"] == "" and (out.loc[1:, "actual_usdm"] == "215.0").all()
    assert out.loc[2, "closer_than_benchmark"] == "True" and out.loc[1, "closer_than_benchmark"] == "False"
