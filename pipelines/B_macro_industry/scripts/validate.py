"""Pipeline B in one command:  python pipelines/B_macro_industry/scripts/validate.py [--refresh]

Fetches the two context series (FRED RSEAS, WSTS billings), cross-checks each against a second primary source
(Census MARTS text table; SIA press-release headline), quote-checks the grade-C documents, writes
data/processed/macro_monthly.csv, macro_quarterly.csv and validation_report.md, and fills the validated /
validated_on / validation_detail columns of config/data_config.csv.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pipeline_b.paths import DATA_CONFIG, DATA_PROC  # noqa: E402
from pipeline_b.build import build_all  # noqa: E402
from pipeline_b.quotes import check_quote  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args(argv)
    today = date.today().isoformat()
    cfg = pd.read_csv(DATA_CONFIG, dtype=str).fillna("")

    res = build_all(refresh=a.refresh)
    rc, wc, cyc = res["retail_check"], res["wsts_check"], res["cycle"]

    def setrow(key, validated, detail):
        i = cfg.index[cfg["key"] == key][0]
        cfg.loc[i, ["validated", "validated_on", "validation_detail"]] = [validated, today, detail]

    setrow("fred_rseas", "no" if rc["flagged"] else "yes",
           f"{rc['months_compared']} months vs Census, {rc['flagged']} flagged, max diff {rc['max_abs_diff_pct']:.3f}%; FRED last {rc['fred_last']}, Census last {rc['census_last']}")
    setrow("census_adv44300", "yes" if not rc["flagged"] else "no", "cross-check source; agrees with FRED" if not rc["flagged"] else "disagrees with FRED — investigate")
    if wc.get("sia_status") == "ok":
        setrow("wsts_billings", "no" if wc["flagged"] else "yes",
               f"{wc['months']} months to {wc['last_month']}; SIA {wc['sia_month']} 3MMA ${wc['sia_usdm']:.0f}m vs WSTS ${wc['wsts_3mma_usdm']:.0f}m ({wc['diff_pct']:+.2f}%)")
        setrow("sia_latest", "yes" if not wc["flagged"] else "no", f"cross-check source: {wc['sia_url']}")
    else:
        setrow("wsts_billings", "partial", f"{wc['months']} months to {wc['last_month']}; SIA cross-check unavailable: {wc.get('sia_status')}")
        setrow("sia_latest", "manual", wc.get("sia_status", ""))

    for _, r in cfg[cfg["quote"] != ""].iterrows():
        st, detail = check_quote(r["url"], r["key"], r["quote"], a.refresh)
        setrow(r["key"], {"found": "yes", "not_found": "no", "fetch_failed": "manual"}[st], detail)
    cfg.to_csv(DATA_CONFIG, index=False)

    q = res["quarterly"]
    md = [f"# Pipeline B validation report — {today}\n",
          "## 1. Series fetched and cross-checked\n",
          f"- FRED RSEAS vs Census adv44300.txt: {rc['months_compared']} months compared, {rc['flagged']} flagged, max |diff| {rc['max_abs_diff_pct']:.3f}%.",
          f"- WSTS worldwide billings: {wc['months']} months to {wc['last_month']} from `{wc['workbook_url']}`; SIA cross-check: {wc.get('sia_status')}"
          + (f" — {wc['sia_month']} 3MMA ${wc['sia_usdm']:.0f}m vs ${wc['wsts_3mma_usdm']:.0f}m ({wc['diff_pct']:+.2f}%)" if wc.get("sia_status") == "ok" else ""), "",
          "## 2. Industry cycle dating (sanity check for the model's regimes)\n",
          f"WSTS worldwide YoY < 0 in: {', '.join(cyc['wsts_negative_yoy_quarters']) or 'none'}. Longest run = **{cyc['industry_destock_window']}**. "
          "The model's `destock` regime (config/model.yaml) is 2022Q3–2024Q1: same start as the industry aggregate, but Nordic's distributor adjustment ran two quarters longer "
          "(Nordic's Q1 2024 report is the first to call the adjustments 'predominately behind us' — Pipeline A, verbal_metrics.csv). Use: a check that the regime dates are not idiosyncratic, not a model input.", "",
          "## 3. Quarterly context table (last 12)\n", q.tail(12).assign(quarter=lambda d: d["quarter"].astype(str)).round(1).to_markdown(index=False), "",
          "## 4. Sources and status\n", cfg[["source", "grade", "retrieval_method", "validation_method", "validated", "validation_detail"]].to_markdown(index=False), "",
          "Rule: these series never enter the regression or the forecast. They appear as context columns in the tier panel and in this report only."]
    (DATA_PROC / "validation_report.md").write_text("\n".join(md))
    print("\n".join(md[:9]))
    print(f"\nconfig: {cfg['validated'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
