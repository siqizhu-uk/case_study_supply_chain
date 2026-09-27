"""Folder layout of Pipeline A (company financials). Everything the pipeline reads or writes lives under
pipelines/A_company_financials/ so that config, code and outputs of each pipeline are separate."""
from pathlib import Path

PIPE = Path(__file__).resolve().parents[2]          # pipelines/A_company_financials
ROOT = PIPE.parents[1]                               # repository root
CONFIG = PIPE / "config"
DATA_CONFIG = CONFIG / "data_config.csv"
DATA_RAW = PIPE / "data" / "raw"
DATA_PROC = PIPE / "data" / "processed"
CACHE = PIPE / "data" / "cache"
MANUAL = PIPE / "data" / "manual"
