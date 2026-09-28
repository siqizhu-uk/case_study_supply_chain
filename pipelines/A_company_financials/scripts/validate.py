"""One command to answer "is the data correct?" without reading the filings yourself.

    python pipelines/A_company_financials/scripts/validate.py            # uses cached downloads; add --fetch to (re)download first

It runs three mechanical checks and writes data/processed/validation_report.md, then fills the `validated`,
`validated_on` and `validation_detail` columns of config/data_config.csv so the source list doubles as the audit trail.

  1. Coverage   — quarters per company vs the 16 needed for the four-year regime study (2022Q3–2026Q2)
  2. XBRL       — every hand-typed headline figure for the US filers vs the SEC company-facts API (tolerance 0.5%)
  3. Filings    — every hand-typed figure searched in the text of the filing it cites (PDF or 8-K exhibit);
                  restated figures may legitimately appear in one of the next four quarterly or two annual reports

  5. Step 3    — inventory detail: Logitech RM + FG == inventory; Arrow / Avnet identities; Microchip distributor-days
                  sentence found and chained filing to filing; Nordic balance-sheet extract chained to the year-ago column;
                  Nordic AR-note stages sum to inventory; Nordic customer-concentration quotes found in the cited report
  4. Grade C   — every verbal data point in data/raw/verbal_metrics.csv (sell-through gap, distributor-inventory
                  state, distributor segment growth): (a) the quoted phrase is searched in the cited transcript page
                  or, failing that, in the quarter's cached report; (b) the coded value must equal the cell in the
                  company CSV it feeds. Rows whose source blocks automated fetch are listed as manual to-dos.

What it cannot check (listed in the report as "manual"): adjusted margins we chose, the magnitude of grade-C rows
flagged is_estimate=1 (the call gave direction, not a number), and the Ingram 2022–H1 2023 quarters (pre-IPO).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))          # core.verify_ledger (nordic_guidance excerpt checks)

from pipeline_a.paths import DATA_RAW, DATA_PROC  # noqa: E402
from pipeline_a.manifest import COMPANIES, DATA_CONFIG  # noqa: E402
from pipeline_a.reconcile import reconcile  # noqa: E402
from pipeline_a.filings import verify  # noqa: E402
from pipeline_a.verbal import verify_verbal, check_consistency, uncited_cells  # noqa: E402
from pipeline_a import inventory_detail, nordic_balance, nordic_guidance  # noqa: E402

NEEDED = pd.period_range("2022Q3", "2026Q2", freq="Q")   # four years
HEADLINE = {"nordic": "revenue_usdm", "logitech": "net_sales_usdm", "gn": "group_rev_dkkm",
            "ingram": "net_sales_usdm", "tdsynnex": "revenue_usdm"}


def coverage() -> pd.DataFrame:
    rows = []
    for c, col in HEADLINE.items():
        d = pd.read_csv(DATA_RAW / COMPANIES[c]["raw_csv"])
        d["quarter"] = pd.PeriodIndex(d["quarter"], freq="Q")
        have = d.loc[d[col].notna(), "quarter"]
        missing = [str(q) for q in NEEDED if q not in set(have)]
        extra = "GN continuing ops (cont_ops_rev_dkkm) exists only from 2025Q1 by definition; Enterprise+Gaming covers 2022Q2+" if c == "gn" else ""
        rows.append({"company": c, "series": col, "quarters": len(have), "first": str(have.min()), "last": str(have.max()),
                     "missing_in_last_4y": ", ".join(missing) or "none", "note": extra})
    return pd.DataFrame(rows)


VERBAL_STATUS = {"found": "yes", "found_in_filing": "yes", "found_manual": "yes", "found_manual_file": "yes", "not_found": "no", "fetch_failed": "manual", "unreadable": "manual"}


def transcript_rows(vb: pd.DataFrame, vc: pd.DataFrame, today: str) -> pd.DataFrame:
    """One data_config row per grade-C source URL, status = quote check AND value-consistency check."""
    vc = vc.set_index(["company", "quarter", "metric"])["consistent"]
    rows = []
    for (c, url), g in vb.groupby(["company", "source_url"], sort=False):
        r = g.iloc[0]
        cons = all(vc.get((x["company"], x["quarter"], x["metric"]), False) for _, x in g.iterrows())
        st = VERBAL_STATUS.get(r["verified"], "manual")
        if not cons:
            st = "no"
        detail = {"found": "quote found in cited page", "found_manual": "quote confirmed by hand (manual_check=confirmed)", "found_manual_file": "quote found in transcript saved under data/manual/", "found_in_filing": "cited page not fetchable; quote found in the quarter's cached report",
                  "not_found": "quote NOT found — fix quote or value", "fetch_failed": "site blocks automated fetch — open url and search the quote by hand"}.get(r["verified"], r["verified"])
        detail += "; value matches company CSV" if cons else "; VALUE DIFFERS from company CSV"
        rows.append({"company": c, "key": f"{r['quarter']}_verbal", "source_type": "transcript", "url": url,
                     "purpose": f"Grade-C verbal metric (earnings call / report commentary), is_estimate={int(r['is_estimate'])}",
                     "used_for_columns": "|".join(sorted(set(g["metric"]))), "validated": st, "validated_on": today,
                     "validation_detail": detail, "notes": f"quote: '{r['quote']}' — {r['note']}"})
    return pd.DataFrame(rows)


# how each source type is obtained and checked — written into data_config.csv so the audit trail is self-describing
METHODS = {
    "sec_xbrl":          ("script: SEC company-facts API (data.sec.gov, keyless, User-Agent header)", "every hand-typed headline cell vs XBRL value, tolerance 0.5%"),
    "sec_8k_exhibit":    ("script: EDGAR document download", "each CSV cell searched in exhibit text (thousands-table rounding); restatements in next 4 quarterly / 2 annual filings"),
    "sec_10k":           ("script: EDGAR document download", "as sec_8k_exhibit (annual figures / restated comparatives)"),
    "sec_s1":            ("script: EDGAR document download", "as sec_8k_exhibit (pre-IPO quarters)"),
    "newsweb_attachment":("script: Oslo Børs NewsWeb API attachment (message id cited)", "each CSV cell searched in PDF text (pdfplumber); restatements in later reports; guidance excerpts (nordic_guidance.py) word for word"),
    "newsweb_message":   ("script: Oslo Børs NewsWeb API message body (no attachment; cached as newsweb_<id>.txt)", "guidance excerpt searched word for word in the announcement text (nordic_guidance.py); ledger on a fresh clone"),
    "ir_pdf":            ("script: company IR PDF download", "each CSV cell searched in PDF text (pdfplumber); restatements in later reports"),
    "ir_pdf_fallback":   ("not downloaded — NewsWeb copy used instead", "none (fallback URL only)"),
    "transcript":        ("script fetch of transcript page, else quarter's cached report, else hand-saved excerpt in data/manual/ (see RETRIEVAL_LOG.md)", "quoted phrase searched in source text + coded value must equal the company-CSV cell"),
    "press_release":     ("manual: read in browser", "read once and cited; qualitative"),
    "web_snapshot":      ("manual: page snapshot on the date given", "read once and cited; point-in-time"),
    "fcc_oet":           ("script: FCC OET grantee search export; attachments manual", "grant list checked for duplicates; SoC markings pending manual read"),
    "third_party":       ("manual: PDF read in browser", "read once and cited; corroborates public figures only"),
    "sec_xbrl_detail":   ("script: SEC company-facts API (inventory_detail.py; 52/53-week closes mapped to calendar quarters)", "identities: RM + FG == inventory (Logitech), revenue > COGS > 0 and GM 5-20% (Arrow, Avnet); Logitech total == hand-typed"),
    "sec_filing_text":   ("script: EDGAR submissions API + primary 10-Q/10-K documents, regex on the disclosure sentence", "verbatim quote stored; 'compared to MM days at <date>' == value in the filing for <date>"),
    "filing_extract":    ("script: text of the cached NewsWeb report / annual report (pdfplumber), balance-sheet line or inventory note", "chain: year-ago / prior-year column == earlier report's current column; sum == hand-typed inventory"),
    "filing_quote":      ("manual: hand-typed value + verbatim fragments", "every fragment searched in the cited cached report"),
    "rejected":          ("checked and not used", "see validation_detail"),
}


# which step-3 checks validate which data_config row: (company, key) -> substrings of the check names
STEP3_CHECKS = {
    ("logitech", "xbrl_inventory_detail"): ["logitech"],
    ("arrow", "xbrl_distributor"): ["arrow"],
    ("avnet", "xbrl_distributor"): ["avnet"],
    ("microchip", "distributor_days"): ["microchip"],
    ("nordic", "balance_sheet_extract"): ["AR + inventory line", "chain: year-ago", "extracted inventory"],
    ("nordic", "ar_inventory_note"): ["AR-note"],
    ("nordic", "customer_concentration"): ["concentration"],
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="run pipelines/A_company_financials/scripts/fetch.py first")
    ap.add_argument("--no-fetch-verbal", action="store_true", help="check grade-C quotes against cached pages/reports only")
    a = ap.parse_args(argv)
    if a.fetch or not (DATA_PROC / "sec_quarterly.csv").exists():
        if not a.fetch:
            print("no cached downloads yet — running scripts/fetch.py first (needs network, ~2 min)\n")
        from pipeline_a.fetch_all import main as fetch_main
        fetch_main([])

    inv = inventory_detail.run()
    nb = nordic_balance.run()
    step3_checks = pd.concat([inv["checks"], nb["checks"]], ignore_index=True)
    cov = coverage()
    rec = reconcile()
    ver = verify()
    vb = verify_verbal(fetch=not a.no_fetch_verbal)
    vc = check_consistency()
    vu = uncited_cells()
    ng = nordic_guidance.build()                       # F32: every pre-2021 guidance excerpt vs its cached document
    ngc = nordic_guidance.consistency(ng)
    today = date.today().isoformat()

    # ---- fill data_config.csv -------------------------------------------------------------
    cfg = pd.read_csv(DATA_CONFIG, dtype=str).fillna("")
    cfg = cfg[cfg["source_type"] != "transcript"]
    cfg = pd.concat([cfg, transcript_rows(vb, vc, today)], ignore_index=True)
    ver["key"] = ver["filing"].fillna("").str.replace(r"\.(pdf|htm)$", "", regex=True)
    for i, r in cfg.iterrows():
        c, k, st = r["company"], r["key"], r["source_type"]
        if st == "sec_xbrl":
            sub = rec[rec["company"] == c]
            if len(sub):
                cfg.loc[i, "validated"] = "no" if sub["flag"].any() else "yes"
                cfg.loc[i, "validation_detail"] = f"{len(sub)} cells vs XBRL, {int(sub['flag'].sum())} flagged, max diff {sub['diff_pct'].abs().max():.2f}%"
            else:
                cfg.loc[i, "validated"] = "n/a"; cfg.loc[i, "validation_detail"] = "no XBRL comparison (context only)"
        elif st in ("newsweb_attachment", "ir_pdf", "ir_pdf_fallback", "sec_8k_exhibit", "newsweb_message"):
            sub = ver[(ver["company"] == c) & (ver["key"] == k) & ver["result"].str.startswith("found")]
            bad = ver[(ver["company"] == c) & (ver["key"] == k) & (ver["result"] == "not_found")]
            gq = ng[(c == "nordic") & ng["source_key"].str.split("|").map(lambda ks: k in ks)] if c == "nordic" else ng.iloc[0:0]
            gq_found = gq["quote_check"].astype(str).str.startswith("found")          # 'found' or 'found (recorded ...; document not cached)'
            gq_ok, gq_bad = int(gq_found.sum()), int((~gq_found).sum())
            if len(sub) or len(bad) or len(gq):
                cfg.loc[i, "validated"] = "no" if (len(bad) or gq_bad) else "yes"
                cfg.loc[i, "validation_detail"] = (f"{len(sub)} CSV cells found in this document" + (f", {len(bad)} NOT found" if len(bad) else "")
                                                   + (f"; {gq_ok} guidance excerpts found" + (f", {gq_bad} NOT found" if gq_bad else "") if len(gq) else ""))
            else:
                cfg.loc[i, "validated"] = "unused" if st == "ir_pdf_fallback" else "no_cells"
                cfg.loc[i, "validation_detail"] = "document downloaded but no CSV cell cites this key" if st != "ir_pdf_fallback" else "NewsWeb copy used instead"
        elif st == "transcript":
            continue   # filled by transcript_rows()
        elif (c, k) in STEP3_CHECKS:
            pat = "|".join(__import__("re").escape(x) for x in STEP3_CHECKS[(c, k)])
            sub = step3_checks[step3_checks["check"].str.contains(pat, regex=True)]
            cfg.loc[i, "validated"] = "yes" if len(sub) and sub["passed"].all() else "no"
            cfg.loc[i, "validation_detail"] = "; ".join(f"{r['check']} (n={r['n']}): {'pass' if r['passed'] else 'FAIL'}" for _, r in sub.iterrows())
        elif st == "rejected":
            cfg.loc[i, "validated"] = "rejected"
            cfg.loc[i, "validation_detail"] = r["notes"]
        else:
            cfg.loc[i, "validated"] = "manual"
            cfg.loc[i, "validation_detail"] = "qualitative source: read once and cite; not machine-checkable"
        cfg.loc[i, "validated_on"] = today
    for col in ("retrieval_method", "validation_method"):
        if col not in cfg.columns:
            cfg[col] = ""
    cfg["retrieval_method"] = cfg["source_type"].map(lambda t: METHODS.get(t, ("manual", ""))[0])
    cfg["validation_method"] = cfg["source_type"].map(lambda t: METHODS.get(t, ("", "manual"))[1])
    cols = ["company", "key", "source_type", "url", "purpose", "used_for_columns", "retrieval_method", "validation_method",
            "validated", "validated_on", "validation_detail", "notes"]
    cfg = cfg[cols + [c for c in cfg.columns if c not in cols]]
    cfg.to_csv(DATA_CONFIG, index=False)

    # ---- report --------------------------------------------------------------------------
    md = [f"# Data validation report — {today}\n",
          "## 1. Coverage (need 2022Q3–2026Q2 = 16 quarters for the regime study)\n", cov.to_markdown(index=False), "",
          "## 2. Hand CSV vs SEC XBRL (US filers)\n",
          rec.groupby("company").agg(cells=("diff_pct", "size"), flagged=("flag", "sum"), max_abs_diff_pct=("diff_pct", lambda s: s.abs().max())).round(3).to_markdown(), "",
          "## 3. Hand CSV vs filing text\n",
          ver.groupby(["company", "result"]).size().unstack(fill_value=0).to_markdown(), "",
          "`found_in_later_filing` = restated comparative located in one of the next four quarterly or two annual reports (taxonomy changes). "
          "`no_filing` = no document cached for that quarter (Ingram pre-IPO quarters come from XBRL-derived aggregator data, flagged `is_estimate`).", ""]
    nf = ver[ver["result"] == "not_found"]
    md += ["### Cells NOT found — check these by hand\n", nf.to_markdown(index=False) if len(nf) else "none", ""]
    md += ["## 3b. Nordic guidance history 2017-2021 (`data/raw/nordic_guidance_history.csv`, F32)\n",
           f"{int(ng['quote_check'].astype(str).str.startswith('found').sum())}/{len(ng)} excerpts found word for word in the cited cached document (or recorded in the ledger); "
           f"{int(ngc['consistent'].sum())}/{len(ngc)} quarterly initial guides equal the guide cells of nordic_quarterly.csv.", ""]
    md += ["## 4. Grade-C verbal metrics (`data/raw/verbal_metrics.csv`)\n",
           "Each coded value carries the phrase it rests on and its source. `found` = phrase in the cited page; `found_in_filing` = cited page "
           "blocks bots but the quarter's report (already cached for check 3) contains the phrase; `fetch_failed` = open the url and search the phrase by hand. "
           "Consistency = the value equals the cell in the company CSV it feeds.\n",
           vb.groupby(["company", "verified"]).size().unstack(fill_value=0).to_markdown(), "",
           f"Value consistency: {int(vc['consistent'].sum())}/{len(vc)} rows match their company CSV cell.", "",
           "### Manual to-dos (source blocks automated fetch)\n",
           vb[vb["verified"].isin(["fetch_failed", "not_found", "unreadable"])][["company", "quarter", "metric", "value", "quote", "source_url"]].to_markdown(index=False), "",
           f"### Grade-C cells with no evidence row ({len(vu)}) — carried-forward states / coded from research notes; treat as grade D\n",
           vu.to_markdown(index=False) if len(vu) else "none", "",
           "## 5. Not machine-checkable (read once, cite, keep the `is_estimate` flag)\n",
           "- Magnitude of grade-C rows with `is_estimate=1`: the call gave the direction, the number is our coding (see `note`).",
           "- Adjusted margins chosen in `config/model.yaml` (Nordic Q2'24 / Q4'25, Logitech Q1 FY27 tariff refund).",
           "- Logitech regional sales (10-Q segment note; 10-Qs not in `data_config.csv`).",
           "- Ingram 2022Q1–2023Q2 (aggregator, `is_estimate=1`).", "",
           "## 6. How to spot-check one number yourself (2 minutes)\n",
           "1. Open `config/data_config.csv`, find the company + quarter row, open its `url`.",
           "2. Search the document for the value in `data/raw/<company>_quarterly.csv` (Nordic tables are in USD thousands: 218.6 appears as `218 6xx`; Logitech/Ingram/SNX exhibits are in USD thousands with commas).",
           "3. If it differs, fix the CSV, re-run `python pipelines/A_company_financials/scripts/validate.py`, and the `validated` column updates.", "",
           "## 7. Step-3 inventory detail (script-read from filings; every check must pass)\n", step3_checks.to_markdown(index=False), "",
           "Or paste this into Claude with the filing attached: *\"Here is <company>'s <quarter> report. Confirm or correct each of these figures, quoting the page and line: <paste the CSV row>. Flag any figure that is restated elsewhere or is an adjusted rather than reported number.\"*"]
    (DATA_PROC / "validation_report.md").write_text("\n".join(md))
    print("\n".join(md[:20]))
    print(f"\nWrote pipelines/A_company_financials/data/processed/validation_report.md and updated its config/data_config.csv "
          f"({(cfg['validated'] == 'yes').sum()} sources validated, {(cfg['validated'] == 'no').sum()} with problems, "
          f"{(cfg['validated'] == 'manual').sum()} manual; grade-C: {int(vb['verified'].str.startswith('found').sum())}/{len(vb)} quotes verified, "
          f"{int(vc['consistent'].sum())}/{len(vc)} values consistent, {len(vu)} grade-C cells uncited)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
