"""Pipeline A entry point: python pipelines/A_company_financials/scripts/fetch.py [--refresh] [--skip-pdf]

1. SEC XBRL company facts -> data/processed/sec_quarterly.csv   (Logitech, Ingram Micro, TD Synnex, Amazon)
2. Reconcile hand CSVs vs XBRL -> data/processed/sec_reconciliation.csv
3. Download Nordic / GN filing PDFs -> data/cache/filings/   (Nordic may 403: drop the PDFs in manually)
4. Verify hand CSV figures against filing text -> data/processed/filing_verification.csv
5. Step-3 inventory detail: Logitech RM/FG + receivables, Arrow / Avnet (XBRL), Microchip distributor days (10-Q text),
   Nordic receivables / inventory by stage / customer concentration (cached reports) -> data/raw/*, checks in data/processed/
Prints a one-screen summary. No API keys, no AI: everything is deterministic and re-runnable.
"""
from __future__ import annotations

import argparse
import sys

from .sec import build_sec_quarterly
from .reconcile import reconcile
from .filings import download_all, verify
from .newsweb import download_nordic_reports, download_announcements
from .nordic_guidance import announcement_ids
from .extend import extend_from_xbrl
from . import inventory_detail, nordic_balance


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download even if cached")
    ap.add_argument("--skip-pdf", action="store_true", help="skip Nordic/GN PDF download and verification")
    a = ap.parse_args(argv)

    print("== 1. SEC XBRL company facts ==")
    try:
        sec = build_sec_quarterly(refresh=a.refresh)
        print(sec.groupby("company")["revenue_usdm"].count().rename("quarters_with_revenue").to_string())
    except Exception as e:
        print(f"SEC fetch failed ({e}); using cached data/processed/sec_quarterly.csv if present", file=sys.stderr)
        sec = None

    print("\n== 1b. Extend raw CSVs backwards from XBRL (headline only, pre-2022 quarters) ==")
    try:
        print(extend_from_xbrl(sec).to_string(index=False))
    except Exception as e:
        print(f"extend skipped ({e})")

    print("\n== 2. Hand CSV vs XBRL reconciliation ==")
    rec = reconcile(sec)
    print(f"{len(rec)} checks, {int(rec['flag'].sum())} flagged (>0.5% difference)")
    if rec["flag"].any():
        print(rec[rec["flag"]].to_string(index=False))

    if not a.skip_pdf:
        print("\n== 3a. Nordic reports via Oslo Børs NewsWeb API ==")
        try:
            nw = download_nordic_reports(refresh=a.refresh)
            print(f"{len(nw)} Nordic filings ({nw['status'].eq('downloaded').sum()} downloaded, rest cached); index in data/processed/newsweb_nordic_index.csv")
            an = download_announcements(announcement_ids(), refresh=a.refresh)      # guidance updates without a report (F32)
            print(f"{len(an)} Nordic announcements ({an['status'].eq('downloaded').sum()} downloaded, rest cached)")
        except Exception as e:
            print(f"NewsWeb fetch failed ({e}); falling back to nordicsemi.com URLs", file=sys.stderr)
        print("\n== 3b. Filing PDFs from company IR sites (GN; Nordic only where NewsWeb missed) ==")
        dl = download_all(refresh=False)
        print(dl.groupby(["company", "status"]).size().to_string())
        if (dl["status"].str.startswith("failed")).any():
            print("Some IR-site downloads failed (nordicsemi.com returns 403 to non-browser clients); the NewsWeb copies cover them.\n"
                  "To add one manually: save the PDF as data/cache/filings/<company>/<key>.pdf and re-run.")
        print("\n== 4. Hand CSV vs filing text verification ==")
        v = verify()
        print(v.groupby(["company", "result"]).size().to_string())
        nf = v[v["result"] == "not_found"]
        if len(nf):
            print("NOT FOUND — check these rows:")
            print(nf.to_string(index=False))
        print("\n== 5. Step-3 inventory detail (XBRL detail, Microchip distributor days, Nordic balance sheet) ==")
        try:
            print(inventory_detail.run(refresh=a.refresh)["checks"].to_string(index=False))
            print(nordic_balance.run()["checks"].to_string(index=False))
        except Exception as e:
            print(f"step-3 inventory detail failed ({e}); existing data/raw extracts kept", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
