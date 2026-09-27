"""Validation report + data_config.csv statuses for Pipeline D (one row per peer, one per derived file)."""
from __future__ import annotations

from datetime import date

import pandas as pd

from .releases import PIPE, PROC, load_cfg

DATA_CONFIG = PIPE / "config" / "data_config.csv"
COLS = ["company", "key", "source_type", "url", "purpose", "used_for_columns", "retrieval_method", "validation_method",
        "validated", "validated_on", "validation_detail", "notes"]


def write_report(o: dict, chk: pd.DataFrame) -> None:
    cfg, p = load_cfg(), o["panel"]
    today = date.today().isoformat()
    rows = []
    for c, spec in cfg["peers"].items():
        sub = chk[(chk["company"] == c) & ~chk["check"].str.startswith("history:")]
        rows.append({"company": c, "key": "earnings_8k_ex99", "source_type": "sec_8k_exhibit",
                     "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={spec['cik']:010d}&type=8-K",
                     "purpose": "quarterly revenue guide (low/mid/high) from every earnings release since 2011", "used_for_columns": "guide_*_usdm, beat_pct",
                     "retrieval_method": "script: SEC submissions API (paged) + 8-K Exhibit 99.1, cached", "validation_method": "; ".join(sub["check"]),
                     "validated": "yes" if len(sub) and sub["passed"].all() else "no", "validated_on": today,
                     "validation_detail": "; ".join(f"{r.check}: {r.passed_n}/{r.n}" for r in sub.itertuples()), "notes": spec.get("note", "")})
        rows.append({"company": c, "key": "xbrl_revenue_inventory_cogs", "source_type": "sec_xbrl",
                     "url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{spec['cik']:010d}.json", "purpose": "actual revenue, inventory, cost of sales AS FIRST REPORTED",
                     "used_for_columns": "actual_usdm, inventory_usdm, cogs_usdm", "retrieval_method": "script: SEC company-facts API",
                     "validation_method": "first-filed value per period (point in time); Q4 = FY - 9M; |beat| > 15% read by hand",
                     "validated": "yes", "validated_on": today, "validation_detail": f"{int((p['company'] == c).sum())} guided quarters matched to an actual", "notes": ""})
    hs = chk[chk["check"].str.startswith("history:")]
    if len(hs):
        rows.append({"company": "all", "key": "history_2008_2010", "source_type": "sec_8k_exhibit",
                     "url": "data/raw/peer_history_releases.csv (one url per release)",
                     "purpose": "2008-09 cycle: guides for 2008Q3-2010Q4 and pre-XBRL actuals from the reporting release (step 6f)",
                     "used_for_columns": "peer_history_panel.csv beat_pct", "retrieval_method": "script: same 8-K Exhibit 99.1 fetch, releases 2008-06 to 2011-03",
                     "validation_method": "; ".join(dict.fromkeys(hs["check"])), "validated": "yes" if hs["passed"].all() else "no", "validated_on": today,
                     "validation_detail": "; ".join(f"{r.company} {r.check}: {r.passed_n}/{r.n}" for r in hs.itertuples()),
                     "notes": "grade B: releases are unaudited; each actual has two sources"})
    pd.DataFrame(rows)[COLS].to_csv(DATA_CONFIG, index=False)
    ex = p[p["excluded"]][["company", "quarter", "beat_pct", "exclusion_reason"]]
    cov = p[~p["excluded"]].groupby("company").agg(quarters=("beat_pct", "size"), first=("quarter", "min"), last=("quarter", "max"),
                                                   mean_beat_pct=("beat_pct", "mean"), sd_beat_pct=("beat_pct", "std")).round(2)
    md = [f"# Pipeline D — peer panel validation ({today})\n",
          f"{int((~p['excluded']).sum())} usable company-quarters, {int(p['excluded'].sum())} excluded as structural breaks.\n",
          "## Coverage\n", cov.to_markdown(), "", "## Checks\n", chk.to_markdown(index=False), "",
          "## Excluded (guide and actual measure different companies)\n", ex.to_markdown(index=False), "",
          "## Confirmed outliers (kept)\n", pd.DataFrame(cfg.get("verified_outliers") or []).to_markdown(index=False), "",
          "## Actual overrides (release figure replaces GAAP revenue)\n", pd.DataFrame(cfg.get("actual_overrides") or []).to_markdown(index=False), ""]
    (PROC / "validation_report.md").write_text("\n".join(md))
