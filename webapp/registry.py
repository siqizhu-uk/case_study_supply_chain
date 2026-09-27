"""Which files each tab of the results page shows. The tab list is webapp/tabs.json; a tab with a `folder` gets that
folder's README.md, its outputs/*.{csv,md,png,svg,json} and config/*.csv automatically, plus any extra `files`."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABS_FILE = Path(__file__).resolve().parent / "tabs.json"
KINDS = {".csv": "table", ".md": "markdown", ".png": "image", ".svg": "image", ".json": "json", ".html": "html"}


def _rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def _entry(p: Path, role: str) -> dict:
    st = p.stat()
    return {"path": _rel(p), "name": p.name, "kind": KINDS.get(p.suffix, "text"), "role": role, "mtime": st.st_mtime, "size": st.st_size}


def resolve_tab(t: dict) -> dict:
    folder = ROOT / t["folder"] if t.get("folder") else None
    files: list[dict] = []
    seen: set[str] = set()

    def add(p: Path, role: str) -> None:
        if p.exists() and p.is_file() and _rel(p) not in seen and p.suffix in KINDS:
            seen.add(_rel(p))
            files.append(_entry(p, role))

    report = (folder / t["report"]) if (folder and t.get("report")) else (ROOT / t["report"] if t.get("report") else None)
    if report is not None:
        add(report, "report")
    if folder:
        add(folder / "README.md", "readme")
        for p in sorted((folder / "config").glob("*.csv")):
            add(p, "decisions" if p.name == "decisions.csv" else "config")
        for ext in ("*.csv", "*.png", "*.svg", "*.json", "*.md"):
            for p in sorted((folder / "outputs").glob(ext)):
                add(p, {".csv": "table", ".png": "figure", ".svg": "figure", ".json": "json", ".md": "report_extra"}[p.suffix])
    for f in t.get("files", []):
        p = ROOT / f
        add(p, "figure" if p.suffix in (".png", ".svg") else ("report_extra" if p.suffix == ".md" else "table"))
    return {"id": t["id"], "title": t["title"], "question": t.get("question", ""), "folder": t.get("folder", ""),
            "link": t.get("link", ""), "files": files}


def load_tabs() -> list[dict]:
    return [resolve_tab(t) for t in json.loads(TABS_FILE.read_text())]


def all_paths() -> set[str]:
    return {f["path"] for t in load_tabs() for f in t["files"]}
