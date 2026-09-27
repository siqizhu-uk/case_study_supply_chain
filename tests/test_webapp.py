"""Results page (scripts/serve.py): tab registry, whitelist, change detection. Run: pytest -q tests/test_webapp.py"""
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp.registry import load_tabs  # noqa: E402
from webapp.server import Handler  # noqa: E402


def test_every_step_has_a_tab_with_an_analysis_report():
    tabs = {t["id"]: t for t in load_tabs()}
    assert {f"step{i}" for i in range(1, 8)} <= set(tabs)
    for i in (1, 2, 3, 4, 6):
        assert any(f["role"] == "report" for f in tabs[f"step{i}"]["files"]), i


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def _get(url):
    with urllib.request.urlopen(url) as r:
        return r.status, r.read()


def test_api_lists_tabs_and_serves_whitelisted_files(server):
    code, body = _get(server + "/api/tabs")
    d = json.loads(body)
    assert code == 200 and d["tabs"] and all("status" in f for t in d["tabs"] for f in t["files"])
    code, _ = _get(server + "/api/file?path=steps/step3_inventory_mechanism/outputs/channel_call.csv")
    assert code == 200


@pytest.mark.parametrize("path", ["config/model.yaml", "../../etc/passwd", "CLAUDE.md", "pipelines/A_company_financials/data/raw/logitech_quarterly.csv"])
def test_api_refuses_anything_not_on_the_page(server, path):
    with pytest.raises(urllib.error.HTTPError) as e:
        _get(server + "/api/file?path=" + path)
    assert e.value.code == 403
