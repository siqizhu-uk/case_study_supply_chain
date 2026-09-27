"""Results page, one tab per step: python scripts/serve.py [--port 8765]  ->  http://127.0.0.1:8765"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp.server import serve  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    serve(ap.parse_args().port)
