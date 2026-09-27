"""Run Step 1 alone:  python steps/step1_filing_confidence/scripts/run.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from filing_confidence import run_step1  # noqa: E402

if __name__ == "__main__":
    r = run_step1()
    print(r["confidence"].to_string(index=False)); print(f"\nwrote {r['path']}")
