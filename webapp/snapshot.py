"""Snapshot every file the results page shows into runs/<timestamp>/ at the end of a run, so the page can show what
changed after each code change. Keeps the newest KEEP runs. runs/ is git-ignored."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

from .registry import ROOT, all_paths

RUNS = ROOT / "runs"
KEEP = 15


def digest(p: Path) -> str:
    return hashlib.sha1(p.read_bytes()).hexdigest()


def list_runs() -> list[dict]:
    if not RUNS.exists():
        return []
    out = []
    for d in sorted(RUNS.iterdir(), reverse=True):
        m = d / "manifest.json"
        if m.exists():
            out.append({"id": d.name, **json.loads(m.read_text())})
    return out


def take(label: str = "run_all") -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = RUNS / stamp
    hashes = {}
    for rel in sorted(all_paths()):
        src = ROOT / rel
        tgt = dest / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, tgt)
        hashes[rel] = digest(src)
    (dest / "manifest.json").write_text(json.dumps({"created": datetime.now().isoformat(timespec="seconds"), "label": label,
                                                    "files": hashes}, indent=1))
    for old in list_runs()[KEEP:]:
        shutil.rmtree(RUNS / old["id"], ignore_errors=True)
    return dest
