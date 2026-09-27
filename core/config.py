from __future__ import annotations
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "model.yaml"
PIPELINES = ROOT / "pipelines"
PIPE_A = PIPELINES / "A_company_financials"      # company financials: hand CSVs + validation outputs
PIPE_B = PIPELINES / "B_macro_industry"          # macro / industry context series
DATA_RAW = PIPE_A / "data" / "raw"               # model inputs (Pipeline A raw)
MACRO_PROC = PIPE_B / "data" / "processed"       # optional context columns (Pipeline B)
PIPE_C = PIPELINES / "C_realtime_channel"        # distributor-stock snapshots, design-win evidence
CHANNEL_SNAPSHOTS = PIPE_C / "data" / "raw" / "channel_snapshots.csv"
OUTPUTS = ROOT / "outputs"                       # final deliverables (forecasts, report, dashboard, panel, figures)
DATA_PROC = OUTPUTS                              # generated panel lives with the final outputs
STEPS = ROOT / "steps"                           # one folder per analysis step: README, config, src, outputs


def step_outputs(name: str) -> Path:
    """steps/<name>/outputs, created on demand (e.g. step_outputs('step4_lag_structure'))."""
    d = STEPS / name / "outputs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_config(path: Path | str | None = None) -> dict:
    p = Path(path) if path else CONFIG_PATH
    with open(p) as f:
        return yaml.safe_load(f)


def tri(d: dict, key: str = "mid") -> float:
    """Pick low/mid/high from a {low, mid, high} dict."""
    return float(d[key])
