"""Screenshots of every dashboard tab for the README (docs/screenshots/<tab>.png), taken with headless Chrome.

    python scripts/screenshot_dashboard.py                                   # the committed file (the sandbox shows its hint)
    python scripts/screenshot_dashboard.py --url http://127.0.0.1:8765/dashboard   # served: Predict shows the live sandbox

Optional and not part of run_all (it needs a local Chrome); re-run it when the layout changes.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
TABS = ["charts", "analysis", "time", "predict", "monitor", "data", "audit"]
CHROME = os.environ.get("CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def shoot(url: str, tab: str, size: str) -> Path:
    """A 3 s virtual-time wait lets late content (the sandbox frame) load; a tab whose animation never lets virtual time
    finish is shot again without it."""
    try:
        return _shoot(url, tab, size, ["--virtual-time-budget=3000"], timeout=60)
    except SystemExit:
        return _shoot(url, tab, size, [], timeout=60)


def _shoot(url: str, tab: str, size: str, extra: list[str], timeout: float) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{tab}.png"
    profile = tempfile.mkdtemp(prefix="dash-shot-")          # own profile: a running Chrome would otherwise block headless
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--no-default-browser-check",
           f"--user-data-dir={profile}", f"--window-size={size}", *extra, f"--screenshot={out}", f"{url}#{tab}"]
    out.unlink(missing_ok=True)
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        raise SystemExit(f"Chrome did not start for tab '{tab}': {e}. Set CHROME to your Chrome binary.")
    try:                                  # Chrome writes the file, then may linger (its updater): stop it once the file is complete
        _wait_for_file(out, proc, timeout=timeout)
    finally:
        proc.kill()
    return out


def _wait_for_file(out: Path, proc: subprocess.Popen, timeout: float) -> None:
    end, last = time.time() + timeout, -1
    while time.time() < end:
        size = out.stat().st_size if out.exists() else -1
        if size > 0 and size == last:
            return
        if proc.poll() is not None and size <= 0:
            raise SystemExit(f"Chrome exited without writing {out.name}")
        last = size
        time.sleep(1.5)
    raise SystemExit(f"no screenshot {out.name} after {timeout:.0f} s")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=(ROOT / "deliverables" / "dashboard.html").as_uri(), help="dashboard URL or file URI")
    ap.add_argument("--size", default="1400,1000", help="window width,height in pixels")
    a = ap.parse_args()
    for tab in TABS:
        print(shoot(a.url, tab, a.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
