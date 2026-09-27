"""Local results page: one tab per step, reading the outputs straight from disk.

    python scripts/serve.py            # http://127.0.0.1:8765  (localhost only)

API (read-only, whitelisted to the files listed by webapp/tabs.json):
    /api/tabs?base=<run id>   tabs with their files; each file marked new / changed / same against the baseline run
    /api/file?path=<rel>      current content          /api/file?path=<rel>&run=<id>   content in an earlier run
    /api/runs                 snapshots taken by scripts/run_all.py (newest first)
Assumptions tab (webapp/assumptions.py; scenarios run in a sandbox copy, never in the analyst's files):
    GET  /api/assumptions                     every leaf of config/model.yaml, sections, run status, earlier scenarios
    GET  /api/scenario/status                 the running scenario's state and log tail
    GET  /api/scenario/compare?id=<id>        forecasts committed vs scenario, and which results files differ
    GET  /api/scenario/file?id=<id>&path=<rel>  a results file as the scenario produced it
    POST /api/scenario/run   {edits, name}    validate, copy the repo to runs/scenarios/<id>/repo, run it there
    POST /api/assumptions/save {edits}        the only write to config/model.yaml
POSTs need the X-Results-Page header, a JSON body and a local Host/Origin (no cross-site writes).
Baseline (default): the newest snapshot if the files on disk differ from it (e.g. one step was re-run on its own),
otherwise the snapshot before it (i.e. "what did the last run change").
"""
from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .registry import ROOT, load_tabs, all_paths
from .snapshot import RUNS, list_runs, digest
from . import assumptions

STATIC = Path(__file__).resolve().parent / "static"


def default_baseline(runs: list[dict]) -> str | None:
    if not runs:
        return None
    latest = runs[0]
    same = all((ROOT / p).exists() and digest(ROOT / p) == h for p, h in latest["files"].items())
    if same and len(runs) > 1:
        return runs[1]["id"]
    return latest["id"] if not same else None


def tabs_with_status(base: str | None) -> dict:
    runs = list_runs()
    base = base or default_baseline(runs)
    ref = next((r["files"] for r in runs if r["id"] == base), {})
    tabs = load_tabs()
    for t in tabs:
        for f in t["files"]:
            h = ref.get(f["path"])
            f["status"] = "new" if base and h is None else ("same" if not base or h == digest(ROOT / f["path"]) else "changed")
        t["n_changed"] = sum(f["status"] in ("new", "changed") for f in t["files"])
    return {"baseline": base, "runs": [{"id": r["id"], "created": r["created"]} for r in runs], "tabs": tabs}


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *a):          # keep the terminal quiet
        pass

    def _send(self, body: bytes, ctype: str, code: int = 200) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(json.dumps(obj, default=str).encode(), "application/json", code)

    def do_GET(self):  # noqa: N802
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/tabs":
                return self._json(tabs_with_status(q.get("base")))
            if u.path == "/api/runs":
                return self._json(list_runs())
            if u.path == "/api/file":
                rel = q.get("path", "")
                if rel not in all_paths():
                    return self._json({"error": "not a results-page file"}, HTTPStatus.FORBIDDEN)
                base = RUNS / q["run"] if q.get("run") else ROOT
                p = (base / rel).resolve()
                if not str(p).startswith(str(base.resolve())) or not p.exists():
                    return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return self._send(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "text/plain; charset=utf-8")
            if u.path == "/api/assumptions":
                return self._json(assumptions.state())
            if u.path == "/api/scenario/status":
                return self._json(assumptions.RUNNER.status())
            if u.path == "/api/scenario/compare":
                return self._json(assumptions.compare(q.get("id", "")))
            if u.path == "/api/scenario/file":
                p = assumptions.scenario_file(q.get("id", ""), q.get("path", ""))
                if p is None:
                    return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return self._send(p.read_bytes(), mimetypes.guess_type(p.name)[0] or "text/plain; charset=utf-8")
            if u.path == "/dashboard":
                return self._send((ROOT / "deliverables" / "dashboard.html").read_bytes(), "text/html; charset=utf-8")
            name = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
            f = (STATIC / name).resolve()
            if f.parent != STATIC.resolve() or not f.exists():
                return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return self._send(f.read_bytes(), (mimetypes.guess_type(f.name)[0] or "text/plain") + "; charset=utf-8")
        except Exception as e:  # report, never crash the server
            return self._json({"error": f"{type(e).__name__}: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


    def _local_request(self) -> bool:
        """Refuse cross-site writes: custom header (forces a CORS preflight we never answer), JSON body, local host/origin."""
        host = (self.headers.get("Host") or "").split(":")[0]
        origin = self.headers.get("Origin")
        local = ("127.0.0.1", "localhost")
        return (self.headers.get("X-Results-Page") == "1" and (self.headers.get("Content-Type") or "").startswith("application/json")
                and host in local and (origin is None or urlparse(origin).hostname in local))

    def do_POST(self):  # noqa: N802
        u = urlparse(self.path)
        if not self._local_request():
            return self._json({"error": "forbidden"}, HTTPStatus.FORBIDDEN)
        n = int(self.headers.get("Content-Length") or 0)
        if n > 256_000:
            return self._json({"error": "body too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            edits = body.get("edits", {})
            if not isinstance(edits, dict):
                raise ValueError("edits must be an object {path: value}")
            if u.path == "/api/scenario/run":
                return self._json(assumptions.RUNNER.start(edits, str(body.get("name", ""))))
            if u.path == "/api/assumptions/save":
                return self._json({"saved": assumptions.save_to_model(edits)})
            return self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        except (ValueError, RuntimeError) as e:          # validation: show the reason on the page
            return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
        except Exception as e:  # noqa: BLE001  report, never crash the server
            return self._json({"error": f"{type(e).__name__}: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(port: int = 8765) -> None:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Results page: http://127.0.0.1:{port}   (Ctrl-C to stop; re-run scripts/run_all.py and the page updates)")
    httpd.serve_forever()
