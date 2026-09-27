"""Assumptions tab (webapp/assumptions.py): every model.yaml value editable, edits in place, scenarios sandboxed."""
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import assumptions as A  # noqa: E402
from webapp.server import Handler  # noqa: E402

TEXT = A.MODEL.read_text()


def _flatten(x, n=0):
    if isinstance(x, dict):
        return sum(_flatten(v) for v in x.values())
    if isinstance(x, list):
        return sum(_flatten(v) for v in x)
    return 1


def test_every_scalar_in_model_yaml_is_an_editable_leaf():
    lv = A.leaves(TEXT)
    assert len(lv) == _flatten(yaml.safe_load(TEXT))
    assert len({lf["path"] for lf in lv}) == len(lv)
    guide = next(lf for lf in lv if lf["path"] == "forecast.nordic_2026Q3.guide_low")
    assert guide["value"] == 220 and guide["type"] == "int"


def test_edit_rewrites_only_that_value_and_keeps_comments():
    new = A.apply_edits(TEXT, {"forecast.nordic_2026Q3.guide_low": 225, "supply_graph.lag_check.ci[0]": 0.1})
    old_lines, new_lines = TEXT.splitlines(), new.splitlines()
    assert len(old_lines) == len(new_lines)
    diff = [(a, b) for a, b in zip(old_lines, new_lines) if a != b]
    assert len(diff) == 2 and "225" in diff[0][1] and "0.1" in diff[1][1]
    y = yaml.safe_load(new)
    assert y["forecast"]["nordic_2026Q3"]["guide_low"] == 225 and y["supply_graph"]["lag_check"]["ci"] == [0.1, 0.95]
    assert sorted(c["path"] for c in A.changes(TEXT, new)) == sorted(["forecast.nordic_2026Q3.guide_low", "supply_graph.lag_check.ci[0]"])


def test_unchanged_value_is_a_no_op():
    assert A.apply_edits(TEXT, {"forecast.nordic_2026Q3.guide_low": 220}) == TEXT


@pytest.mark.parametrize("edits, msg", [
    ({"forecast.nordic_2026Q3.no_such_key": 1}, "not an assumption"),
    ({"forecast.nordic_2026Q3.guide_low": "abc"}, "expected a number"),
    ({"forecast.nordic_2026Q3.guide_low": 220.5}, "whole number"),
    ({"forecast.nordic_2026Q3.guide_low": float("nan")}, "finite"),
])
def test_invalid_edits_are_refused_with_a_reason(edits, msg):
    with pytest.raises(ValueError, match=msg):
        A.apply_edits(TEXT, edits)


def test_sandbox_is_a_copy_and_leaves_the_repo_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "SCENARIOS", tmp_path)
    before = A.MODEL.read_bytes()
    work = A.make_sandbox(A.apply_edits(TEXT, {"forecast.nordic_2026Q3.guide_low": 230}), "20990101-000000")
    assert yaml.safe_load((work / "config" / "model.yaml").read_text())["forecast"]["nordic_2026Q3"]["guide_low"] == 230
    assert A.MODEL.read_bytes() == before
    assert (work / "scripts" / "run_all.py").exists() and not (work / ".git").exists() and not (work / "runs").exists()
    for link in work.glob("pipelines/*/data/cache"):
        assert link.is_symlink()                      # read-only inputs, not copied


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
    with urllib.request.urlopen(req) as r:
        return r.status, json.loads(r.read())


def test_api_lists_assumptions(server):
    with urllib.request.urlopen(server + "/api/assumptions") as r:
        d = json.loads(r.read())
    assert len(d["leaves"]) == len(A.leaves(TEXT)) + len(A.edge_leaves(A.EDGES.read_text()))
    assert {"forecast", "supply_graph.csv"} <= set(d["sections"])


@pytest.mark.parametrize("headers", [
    {"Content-Type": "application/json"},                                                     # no page header
    {"Content-Type": "text/plain", "X-Results-Page": "1"},                                    # simple (no-preflight) request
    {"Content-Type": "application/json", "X-Results-Page": "1", "Origin": "https://evil.example"},
])
def test_writes_refuse_cross_site_requests(server, headers):
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/assumptions/save", {"edits": {"forecast.nordic_2026Q3.guide_low": 1}}, headers)
    assert e.value.code == 403
    assert A.MODEL.read_text() == TEXT


def test_invalid_scenario_is_a_400_with_the_reason(server):
    with pytest.raises(urllib.error.HTTPError) as e:
        _post(server + "/api/scenario/run", {"edits": {"forecast.nordic_2026Q3.guide_low": "x"}},
              {"Content-Type": "application/json", "X-Results-Page": "1"})
    assert e.value.code == 400 and "expected a number" in json.loads(e.value.read())["error"]


EDGES = A.EDGES.read_text()


def test_every_numeric_edge_lag_is_editable_and_an_unedited_file_round_trips():
    lv = A.edge_leaves(EDGES)
    assert {"supply_graph.csv:E08.lag_weeks_mid", "supply_graph.csv:E01.lag_weeks_high"} <= {lf["path"] for lf in lv}
    assert A.apply_edge_edits(EDGES, {}) == EDGES
    assert A.apply_edge_edits(EDGES, {"supply_graph.csv:E08.lag_weeks_mid": 8}) == EDGES      # same value: no-op


def test_edge_edit_changes_one_line_and_is_read_back():
    new = A.apply_edge_edits(EDGES, {"supply_graph.csv:E08.lag_weeks_mid": 9.5})
    diff = [(a, b) for a, b in zip(EDGES.splitlines(), new.splitlines()) if a != b]
    assert len(diff) == 1 and diff[0][1].startswith("E08,")
    assert A.edge_changes(EDGES, new) == [{"path": "supply_graph.csv:E08.lag_weeks_mid", "base": 8.0, "value": 9.5}]


@pytest.mark.parametrize("edits, msg", [
    ({"supply_graph.csv:E08.lag_weeks_mid": 12}, "low <= mid <= high"),
    ({"supply_graph.csv:E08.lag_weeks_high": 500}, "between 0 and"),
    ({"supply_graph.csv:E99.lag_weeks_mid": 5}, "not an edge lag"),
    ({"supply_graph.csv:E08.share": 5}, "not an edge lag"),
])
def test_invalid_edge_edits_are_refused(edits, msg):
    with pytest.raises(ValueError, match=msg):
        A.apply_edge_edits(EDGES, edits)


def test_sandbox_gets_the_edited_graph_and_the_repo_keeps_its_own(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "SCENARIOS", tmp_path)
    y, e, ch = A.build({"supply_graph.csv:E08.lag_weeks_high": 11, "forecast.nordic_2026Q3.guide_low": 225})
    assert {c["path"] for c in ch} == {"supply_graph.csv:E08.lag_weeks_high", "forecast.nordic_2026Q3.guide_low"}
    work = A.make_sandbox(y, "20990101-000001", e)
    assert (work / "config" / "supply_graph.csv").read_text() == e != EDGES
    assert A.EDGES.read_text() == EDGES
