from pathlib import Path

PIPE = Path(__file__).resolve().parents[2]          # pipelines/C_realtime_channel
ROOT = PIPE.parents[1]
CONFIG = PIPE / "config"
DATA_CONFIG = CONFIG / "data_config.csv"
PARTS = CONFIG / "parts.csv"
DISTRIBUTORS = CONFIG / "distributors.csv"
DATA_RAW = PIPE / "data" / "raw"
DATA_PROC = PIPE / "data" / "processed"
CACHE = PIPE / "data" / "cache"
SNAPSHOTS = DATA_RAW / "channel_snapshots.csv"
UA = "Mozilla/5.0 (supply-chain-case-study; siqizhu00@gmail.com)"
