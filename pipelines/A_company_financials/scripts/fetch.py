"""Pipeline A entry point: fetch and verify company financial data.  python pipelines/A_company_financials/scripts/fetch.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pipeline_a.fetch_all import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
