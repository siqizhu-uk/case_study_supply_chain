"""Pipeline D: python pipelines/D_peer_panel/scripts/validate.py   (downloads on first run, cached after; ~3 min first time)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pipeline_d.build import build  # noqa: E402
from pipeline_d.validate import checks  # noqa: E402
from pipeline_d.report import write_report  # noqa: E402
from pipeline_d.history import build_history  # noqa: E402
from pipeline_d.validate import check_history  # noqa: E402
from pipeline_d.releases import load_cfg  # noqa: E402
import pandas as pd  # noqa: E402

if __name__ == "__main__":
    o = build()
    c = checks(o)
    hist = build_history()
    c = pd.concat([c, check_history(hist, load_cfg())], ignore_index=True)
    write_report(o, c)
    p = o["panel"]
    hp = hist["panel"]
    print(f"{int((~p['excluded']).sum())} usable company-quarters (+{int((~hp['excluded']).sum())} in the 2008-10 window); "
          f"{int(c['passed'].sum())}/{len(c)} checks passed")
    if not c["passed"].all():
        print(c[~c["passed"]].to_string(index=False))
    raise SystemExit(0 if c["passed"].all() else 1)
