"""Assumptions tab: every leaf of config/model.yaml as an editable value, edited in place so comments and layout survive.

A scenario runs in a sandbox: a copy of the repo under runs/scenarios/<id>/repo (git-ignored) with the edited model.yaml,
so the committed config and outputs are never written. Only an explicit save writes config/model.yaml or
config/supply_graph.csv (edge lags, the other editable source).

Edits are validated against the committed file: the key structure cannot change, numbers stay numbers (integers stay
integers), booleans stay booleans.
"""
from __future__ import annotations

import re
import os
import subprocess
import time
import sys
import threading
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from .registry import ROOT

MODEL = ROOT / "config" / "model.yaml"
EDGES = ROOT / "config" / "supply_graph.csv"
EDGE_PREFIX = "supply_graph.csv:"
EDGE_COLS = ("lag_weeks_low", "lag_weeks_mid", "lag_weeks_high")
MAX_LAG_WEEKS = 104
SCENARIOS = ROOT / "runs" / "scenarios"
MAX_EDITS = 500

Path_ = tuple  # (key | index, ...)


def fmt_path(path: Path_) -> str:
    out = ""
    for k in path:
        out += f"[{k}]" if isinstance(k, int) else (f".{k}" if out else str(k))
    return out


def _block_comment(lines: list[str], line: int) -> str:
    """Full-line comments directly above `line` (0-based), joined; stops at a blank line or code."""
    out = []
    i = line - 1
    while i >= 0 and lines[i].strip().startswith("#"):
        txt = lines[i].strip().lstrip("#").strip()
        if not re.fullmatch(r"[-=]*", txt):
            out.append(txt)
        i -= 1
    return " ".join(reversed(out))


def _inline_comment(line: str) -> str:
    m = re.search(r"\s#\s?(.*)$", line)
    return m.group(1).strip() if m else ""


def leaves(text: str) -> list[dict]:
    """Every scalar in the document with its path, value, type, text span and the nearest comment."""
    lines = text.splitlines()
    root = yaml.compose(text)
    out: list[dict] = []

    def walk(node, path: Path_, note: str) -> None:
        if isinstance(node, yaml.MappingNode):
            for k, v in node.value:
                own = _inline_comment(lines[k.start_mark.line]) or _block_comment(lines, k.start_mark.line)
                walk(v, path + (k.value,), (own or note) if path else "")   # a section's own comment is shown once, on its header
        elif isinstance(node, yaml.SequenceNode):
            for i, v in enumerate(node.value):
                walk(v, path + (i,), note)
        else:
            value = yaml.safe_load(text[node.start_mark.index:node.end_mark.index]) if node.end_mark.index > node.start_mark.index else None
            out.append({"path": fmt_path(path), "keys": list(path), "value": value, "type": _type(value),
                        "line": node.start_mark.line + 1, "span": (node.start_mark.index, node.end_mark.index),
                        "note": _inline_comment(lines[node.start_mark.line]) or note, "section": str(path[0]) if path else ""})

    walk(root, (), "")
    return out


def sections(text: str) -> dict[str, str]:
    """Top-level key -> the comment block above it (the section's explanation)."""
    lines = text.splitlines()
    root = yaml.compose(text)
    return {k.value: _block_comment(lines, k.start_mark.line) for k, _ in root.value}


def _type(v: Any) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, date):
        return "date"
    return "null" if v is None else "str"


def _coerce(raw: Any, typ: str, path: str) -> Any:
    """The edited value in the leaf's type, or ValueError with a reason the page can show."""
    if typ == "bool":
        if isinstance(raw, bool):
            return raw
        if str(raw).lower() in ("true", "false"):
            return str(raw).lower() == "true"
        raise ValueError(f"{path}: expected true / false")
    if typ in ("int", "float"):
        try:
            v = float(raw)
        except (TypeError, ValueError):
            raise ValueError(f"{path}: expected a number, got {raw!r}") from None
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError(f"{path}: expected a finite number")
        if typ == "int":
            if not v.is_integer():
                raise ValueError(f"{path}: expected a whole number")
            return int(v)
        return v
    if typ == "date":
        try:
            return date.fromisoformat(str(raw))
        except ValueError:
            raise ValueError(f"{path}: expected a date YYYY-MM-DD") from None
    if typ == "null":
        return None if raw in (None, "", "null") else str(raw)
    return str(raw)


def _render(v: Any, original: str) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)                                  # 51.0 stays a float when read back
    quote = original[:1] if original[:1] in "\"'" else ""
    if not quote and (yaml.safe_load(v) != v if v else True):
        quote = '"'                                    # would not read back as the same string: quote it
    return f"{quote}{v}{quote}" if quote != '"' else yaml.safe_dump(v, default_style='"').strip()


def apply_edits(text: str, edits: dict[str, Any]) -> str:
    """Rewrite only the edited scalars' text spans; everything else (comments, spacing) stays byte-identical."""
    if len(edits) > MAX_EDITS:
        raise ValueError(f"too many edits ({len(edits)})")
    by_path = {lf["path"]: lf for lf in leaves(text)}
    unknown = sorted(set(edits) - set(by_path))
    if unknown:
        raise ValueError(f"not an assumption in model.yaml: {', '.join(unknown[:5])}")
    spans = []
    for path, raw in edits.items():
        lf = by_path[path]
        v = _coerce(raw, lf["type"], path)
        if v == lf["value"] and type(v) is type(lf["value"]):
            continue
        a, b = lf["span"]
        spans.append((a, b, _render(v, text[a:b])))
    for a, b, new in sorted(spans, reverse=True):
        text = text[:a] + new + text[b:]
    check_same_structure(yaml.safe_load(MODEL.read_text()) if MODEL.exists() else yaml.safe_load(text), yaml.safe_load(text))
    return text


def check_same_structure(base: Any, new: Any, path: str = "") -> None:
    if isinstance(base, dict):
        if not isinstance(new, dict) or set(base) != set(new):
            raise ValueError(f"{path or 'root'}: keys changed")
        for k in base:
            check_same_structure(base[k], new[k], f"{path}.{k}" if path else str(k))
    elif isinstance(base, list):
        if not isinstance(new, list) or len(base) != len(new):
            raise ValueError(f"{path}: list length changed")
        for i, (b, n) in enumerate(zip(base, new)):
            check_same_structure(b, n, f"{path}[{i}]")
    elif _type(base) != _type(new) and not (_type(base) == "float" and _type(new) == "int") and _type(base) != "null":
        raise ValueError(f"{path}: type changed from {_type(base)} to {_type(new)}")


def changes(base_text: str, new_text: str) -> list[dict]:
    """Assumptions whose value differs between two versions of the file."""
    b = {lf["path"]: lf["value"] for lf in leaves(base_text)}
    return [{"path": lf["path"], "base": b.get(lf["path"]), "value": lf["value"]}
            for lf in leaves(new_text) if b.get(lf["path"]) != lf["value"]]


# ---- supply graph edge lags (config/supply_graph.csv) ---------------------------------------------------------------
# Paths "supply_graph.csv:<edge_id>.<lag column>". The CSV is rewritten cell by cell with the csv module, so an unedited
# file round-trips byte for byte.

def _edge_rows(text: str) -> tuple[list[str], list[list[str]]]:
    import csv
    import io
    rows = list(csv.reader(io.StringIO(text)))
    return rows[0], rows[1:]


def edge_leaves(text: str) -> list[dict]:
    head, rows = _edge_rows(text)
    ix = {c: i for i, c in enumerate(head)}
    out = []
    for r in rows:
        rec = dict(zip(head, r))
        for c in EDGE_COLS:
            try:
                v = float(r[ix[c]])
            except (ValueError, IndexError):
                continue                                   # no lag on this edge (e.g. not propagated)
            ev = rec.get("lag_evidence", "")
            out.append({"path": f"{EDGE_PREFIX}{rec['edge_id']}.{c}", "value": v, "type": "float", "section": "supply_graph.csv",
                        "line": rows.index(r) + 2, "note": f"{rec['src']} -> {rec['dst']} ({rec['brand']}); lag grade {rec.get('lag_grade', '')}; "
                        f"{ev[:160]}{'...' if len(ev) > 160 else ''}"})
    return out


def _fmt_weeks(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else repr(float(v))


def apply_edge_edits(text: str, edits: dict[str, Any]) -> str:
    import csv
    import io
    head, rows = _edge_rows(text)
    ix = {c: i for i, c in enumerate(head)}
    by_id = {r[ix["edge_id"]]: r for r in rows}
    touched = set()
    for path, raw in edits.items():
        eid, _, col = path[len(EDGE_PREFIX):].partition(".")
        if eid not in by_id or col not in EDGE_COLS:
            raise ValueError(f"not an edge lag in supply_graph.csv: {path}")
        v = _coerce(raw, "float", path)
        if not 0 <= v <= MAX_LAG_WEEKS:
            raise ValueError(f"{path}: a lag must be between 0 and {MAX_LAG_WEEKS} weeks")
        if float(by_id[eid][ix[col]] or "nan") != v:
            by_id[eid][ix[col]] = _fmt_weeks(v)
            touched.add(eid)
    for eid in touched:
        lo, md, hi = (float(by_id[eid][ix[c]]) for c in EDGE_COLS)
        if not lo <= md <= hi:
            raise ValueError(f"{eid}: needs lag low <= mid <= high (got {lo:g} / {md:g} / {hi:g})")
    if not touched:
        return text
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\r\n" if "\r\n" in text else "\n").writerows([head] + rows)
    return buf.getvalue()


def edge_changes(base_text: str, new_text: str) -> list[dict]:
    b = {lf["path"]: lf["value"] for lf in edge_leaves(base_text)}
    return [{"path": lf["path"], "base": b.get(lf["path"]), "value": lf["value"]} for lf in edge_leaves(new_text) if b.get(lf["path"]) != lf["value"]]


def split_edits(edits: dict[str, Any]) -> tuple[dict, dict]:
    if len(edits) > MAX_EDITS:
        raise ValueError(f"too many edits ({len(edits)})")
    edge = {k: v for k, v in edits.items() if k.startswith(EDGE_PREFIX)}
    return {k: v for k, v in edits.items() if k not in edge}, edge


def build(edits: dict[str, Any]) -> tuple[str, str, list[dict]]:
    """(new model.yaml text, new supply_graph.csv text, changed assumptions) - validated, nothing written."""
    y, e = split_edits(edits)
    base_y, base_e = MODEL.read_text(), EDGES.read_text()
    new_y, new_e = apply_edits(base_y, y), apply_edge_edits(base_e, e)
    return new_y, new_e, changes(base_y, new_y) + edge_changes(base_e, new_e)


# ---- sandboxed scenario runs -------------------------------------------------------------------------------------
# A scenario never touches the analyst's files: the repo (code, config, committed data; ~11 MB) is copied to
# runs/scenarios/<id>/repo, the edited model.yaml is written into the copy, and the copy's own scripts/run_all.py runs
# there, so every output lands inside the copy. The document caches (~1 GB, read-only inputs to the quote checks) are
# symlinked, not copied. The tab compares the copy's outputs with the committed ones.

SKIP = {".git", "runs", "cache", "__pycache__", ".pytest_cache", ".DS_Store"}
KEEP_SCENARIOS = 6


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in SKIP}


def make_sandbox(model_text: str, sid: str, edges_text: str | None = None) -> Path:
    import shutil
    work = SCENARIOS / sid / "repo"
    shutil.copytree(ROOT, work, ignore=_ignore, symlinks=True)
    for cache in list(ROOT.glob("pipelines/*/data/cache")) + list(ROOT.glob("steps/*/cache")):
        link = work / cache.relative_to(ROOT)
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(cache.resolve(), target_is_directory=True)
    (work / "config" / "model.yaml").write_text(model_text)
    if edges_text is not None:
        (work / "config" / "supply_graph.csv").write_text(edges_text)
    return work


def list_scenarios() -> list[dict]:
    import json
    if not SCENARIOS.exists():
        return []
    out = []
    for d in sorted(SCENARIOS.iterdir(), reverse=True):
        m = d / "scenario.json"
        if m.is_file():
            out.append(json.loads(m.read_text()))
    return out


def _prune() -> None:
    import shutil
    for old in list_scenarios()[KEEP_SCENARIOS:]:
        shutil.rmtree(SCENARIOS / old["id"], ignore_errors=True)


class Runner:
    """One scenario run at a time, in a subprocess inside its sandbox; the page polls status()."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None
        self.log: list[str] = []
        self.info: dict = {"state": "idle"}

    def status(self) -> dict:
        return {**self.info, "log": self.log[-40:]}

    def start(self, edits: dict[str, Any], name: str = "") -> dict:
        import json
        with self.lock:
            if self.proc and self.proc.poll() is None:
                raise RuntimeError("a scenario is already running")
            new, new_edges, ch = build(edits)
            if not ch:
                raise ValueError("no assumption differs from config/model.yaml or config/supply_graph.csv")
            sid = datetime.now().strftime("%Y%m%d-%H%M%S")
            work = make_sandbox(new, sid, new_edges)
            meta = {"id": sid, "name": name[:80] or ", ".join(c["path"] for c in ch[:3]), "changes": ch,
                    "created": datetime.now().isoformat(timespec="seconds"), "state": "running"}
            (SCENARIOS / sid / "scenario.json").write_text(json.dumps(meta, indent=1, default=str))
            self.log = []
            self.info = {"state": "running", "id": sid, "started": time.time()}
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}             # stream the run's output to the page as it happens
            self.proc = subprocess.Popen([sys.executable, "scripts/run_all.py"], cwd=work, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1, env=env)
            threading.Thread(target=self._pump, args=(self.proc, sid), daemon=True).start()
            _prune()
            return self.status()

    def _pump(self, proc: subprocess.Popen, sid: str) -> None:
        import json
        for line in proc.stdout:  # type: ignore[union-attr]
            self.log.append(line.rstrip())
        code = proc.wait()
        state = "done" if code == 0 else "failed"
        self.info = {**self.info, "state": state, "exit_code": code, "seconds": round(time.time() - self.info.get("started", time.time()))}
        m = SCENARIOS / sid / "scenario.json"
        if m.exists():
            meta = json.loads(m.read_text())
            meta.update(state=state, finished=datetime.now().isoformat(timespec="seconds"), log_tail=self.log[-30:])
            m.write_text(json.dumps(meta, indent=1, default=str))


RUNNER = Runner()


def scenario_file(sid: str, rel: str) -> Path | None:
    """A results-page file as the scenario produced it (None if the id or path is not valid)."""
    from .registry import all_paths
    if not re.fullmatch(r"\d{8}-\d{6}", sid) or rel not in all_paths() | COMPARE_EXTRA:
        return None
    p = (SCENARIOS / sid / "repo" / rel).resolve()
    return p if p.is_file() and str(p).startswith(str(SCENARIOS.resolve())) else None


NEXT_Q = "outputs/forecast_next_quarter.csv"
COMPARE_EXTRA = {"outputs/figures/" + f for f in ("tiers_yoy.png", "regression_fit.png", "nordic_guidance_beat.png", "xcorr.png", "inventory_days.png")}


def compare(sid: str) -> dict:
    """Forecasts committed vs scenario, and every results-page file whose content differs."""
    import hashlib
    import pandas as pd
    from .registry import all_paths
    fc = []
    for rel, keys in (("outputs/forecasts.csv", ["print", "metric"]), (NEXT_Q, ["model"])):
        base_f, scen_f = ROOT / rel, scenario_file(sid, rel)
        if not (scen_f and base_f.exists()):
            continue
        b, s = pd.read_csv(base_f), pd.read_csv(scen_f)
        if rel == NEXT_Q:                                  # same shape as the three prints: one row per model
            for d in (b, s):
                d["print"] = d.apply(lambda r: f"Nordic {r['quarter']} (h={r['horizon']}) · {r['model']}", axis=1)
                d["metric"] = d["role"]
            keys = ["print", "metric"]
            b, s = b[keys + ["point", "low", "high"]], s[keys + ["point", "low", "high"]]
        m = b.merge(s, on=keys, how="left", suffixes=("_base", "_scen"))   # committed order
        for r in m.to_dict("records"):
            fc.append({k: (None if isinstance(v, float) and v != v else v) for k, v in r.items()} | {"group": "next" if rel == NEXT_Q else "print"})
    h = lambda p: hashlib.sha1(p.read_bytes()).hexdigest()
    changed = []
    for rel in sorted(all_paths() | COMPARE_EXTRA):
        a, s = ROOT / rel, scenario_file(sid, rel)
        if s and a.exists() and h(a) != h(s):
            changed.append(rel)
    return {"forecasts": fc, "changed_files": changed}


def save_to_model(edits: dict[str, Any]) -> list[dict]:
    """The only write to config/model.yaml and config/supply_graph.csv; the committed outputs are NOT re-run (run
    scripts/run_all.py to adopt)."""
    new, new_edges, ch = build(edits)
    if any(not c["path"].startswith(EDGE_PREFIX) for c in ch):
        MODEL.write_text(new)
    if any(c["path"].startswith(EDGE_PREFIX) for c in ch):
        EDGES.write_text(new_edges)
    return ch


def state() -> dict:
    text = MODEL.read_text()
    secs = sections(text) | {"supply_graph.csv": "Supply graph edge lags in weeks (config/supply_graph.csv): low / mid / high "
                             "per edge. They feed the step-5 lag kernel, the h=2 graph models GR / GRg (the Q4 line) and the graph "
                             "challenger. The grade-based ranges and the inventory-cover bound are applied on top (step 5)."}
    return {"leaves": [{k: v for k, v in lf.items() if k not in ("span", "keys")} for lf in leaves(text)] + edge_leaves(EDGES.read_text()),
            "sections": secs, "run": RUNNER.status(), "scenarios": list_scenarios()}
