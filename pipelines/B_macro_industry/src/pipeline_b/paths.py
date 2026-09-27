from pathlib import Path

PIPE = Path(__file__).resolve().parents[2]          # pipelines/B_macro_industry
ROOT = PIPE.parents[1]
DATA_CONFIG = PIPE / "config" / "data_config.csv"
DATA_RAW = PIPE / "data" / "raw"
DATA_PROC = PIPE / "data" / "processed"
CACHE = PIPE / "data" / "cache"
UA = "Mozilla/5.0 (supply-chain-case-study; siqizhu00@gmail.com)"
