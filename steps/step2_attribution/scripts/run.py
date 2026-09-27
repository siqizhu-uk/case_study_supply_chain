"""Run Step 2 alone:  python steps/step2_attribution/scripts/run.py"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core.config import load_config  # noqa: E402
from core.ingest import load_all  # noqa: E402
from core.tiers import build_panel  # noqa: E402
from attribution import attribution, write_step2, OUT  # noqa: E402
from attribution_path import build_path, write_path  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    panel = build_panel(load_all(), cfg)
    attr = attribution(cfg, panel=panel)
    path = build_path(cfg, panel=panel)
    OUT.mkdir(parents=True, exist_ok=True)
    write_path(path)
    (OUT / "attribution.json").write_text(json.dumps(attr, indent=2, default=str))
    attr["path"] = path
    print(write_step2(attr).read_text())
