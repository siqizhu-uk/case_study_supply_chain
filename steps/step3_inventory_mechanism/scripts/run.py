"""Run step 3 on its own: python steps/step3_inventory_mechanism/scripts/run.py  (writes steps/step3_inventory_mechanism/outputs/)"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from core.config import load_config  # noqa: E402
from core.ingest import load_all  # noqa: E402
from core.tiers import build_panel  # noqa: E402
from step3 import run_step3  # noqa: E402

if __name__ == "__main__":
    cfg = load_config()
    out = run_step3(build_panel(load_all(), cfg), cfg)
    print(out["call"][["company", "print", "adj_low", "adj_mid", "adj_high", "unit", "watch_flag", "config_inside_range"]].to_string(index=False))
    for k, v in out["paths"].items():
        print(f"  {k:15s} {v}")
