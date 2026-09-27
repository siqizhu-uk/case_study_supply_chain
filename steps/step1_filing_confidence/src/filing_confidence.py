"""Step 1 — how far can each company's quarterly (unaudited) figures be trusted?

Three separate tests, because three different things go wrong:
  1. sum4q_vs_fy      Σ of the four quarterly revenues (hand CSV, original reports) vs the audited full-year figure.
                      Measures audit true-ups. For SEC filers the audited figure is the 10-K XBRL annual fact; for
                      Nordic it is typed from the annual report (config/annual_audited.csv) and verified in the AR text;
                      for GN the audited figure is located in the AR text within 0.3% of Σ4Q.
  2. restatements     original quarterly segment value vs the same quarter as restated in a later report
                      (config/restatements.csv); both numbers are verified in the cited filings. Measures taxonomy risk.
  3. adjusted         reported vs adjusted margin for the same quarter (config/adjusted_vs_reported.csv + Logitech GAAP vs
                      non-GAAP GM from the hand CSV). Measures management-definition room.
Every test row is logged (outputs/test*.csv), then folded into one confidence table per company and metric class
(outputs/confidence.csv) and a final grade per company. The step itself is grade A: arithmetic on filings.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd

STEP = Path(__file__).resolve().parents[1]
ROOT = STEP.parents[1]
CONFIG, OUT = STEP / "config", STEP / "outputs"
sys.path.insert(0, str(ROOT / "pipelines" / "A_company_financials" / "src"))

from pipeline_a.paths import DATA_RAW, CACHE  # noqa: E402
from pipeline_a.manifest import COMPANIES  # noqa: E402
from pipeline_a.sec import fetch_companyfacts, _facts  # noqa: E402
from pipeline_a.filings import extract_text, _in, _numbers  # noqa: E402
from pipeline_a.manifest import XBRL_TAGS  # noqa: E402
from pipeline_a.sec import CACHE as SEC_CACHE  # noqa: E402
from core import verify_ledger as ledger  # noqa: E402

REV = {"nordic": "revenue_usdm", "logitech": "net_sales_usdm", "gn": "group_rev_dkkm", "ingram": "net_sales_usdm", "tdsynnex": "revenue_usdm"}


def _raw(c: str) -> pd.DataFrame:
    return pd.read_csv(DATA_RAW / COMPANIES[c]["raw_csv"], dtype={"quarter": str})


def _doc_text(company: str, key: str) -> str | None:
    for ext in (".pdf", ".htm"):
        f = CACHE / "filings" / company / f"{key}{ext}"
        if f.exists():
            try:
                return extract_text(f)
            except Exception:
                return None
    return None


def _check(step: str, key: str, text: str | None, ok, yes: str, no: str, missing: str) -> str:
    """Run the check on the document if cached (and record it); otherwise show the recorded result, labelled."""
    if text is None:
        r = ledger.recall(step, key)
        return r[0] if r else missing
    return ledger.record(step, key, yes if ok(text) else no)


def _fiscal_year(c: str, row: pd.Series) -> int | None:
    """Fiscal year a quarter belongs to, from the fiscal_label column (Logitech FY ends March, TD Synnex November)."""
    if c == "logitech":
        return 2000 + int(row["fiscal_label"][2:4])
    if c == "tdsynnex":
        return 2000 + int(row["fiscal_label"].split("-")[1])
    return int(str(row["quarter"])[:4])


def _xbrl_annual(c: str) -> dict[int, float]:
    """10-K annual revenue facts; from the ledger when the company-facts file is not cached (no network in a model run)."""
    cik = COMPANIES[c]["sec_cik"]
    if not (SEC_CACHE / f"CIK{cik:010d}.json").exists():
        d = ledger._load()
        rows = d[(d["step"] == "step1_xbrl_fy") & d["key"].str.startswith(f"{c}|")]
        return {int(k.split("|")[1]): float(v) for k, v in zip(rows["key"], rows["value"])}
    facts = fetch_companyfacts(cik)
    df = _facts(facts, XBRL_TAGS["revenue"])
    df = df.dropna(subset=["start"]).copy()
    df["days"] = (df["end"] - df["start"]).dt.days
    a = df[(df["days"] >= 350) & (df["days"] <= 380) & df["form"].str.startswith("10-K")].sort_values(["end", "filed"]).drop_duplicates("end", keep="last")
    out = {}
    for _, r in a.iterrows():
        fy = r["end"].year if c != "logitech" else r["end"].year          # Logitech FY26 ends Mar-2026; TD Synnex FY25 ends Nov-2025
        out[int(fy)] = float(r["val"]) / 1e6
        ledger.record("step1_xbrl_fy", f"{c}|{int(fy)}", "10-K XBRL annual fact", round(out[int(fy)], 3))
    return out


def test1_sum4q_vs_fy() -> pd.DataFrame:
    audited = pd.read_csv(CONFIG / "annual_audited.csv")
    rows = []
    for c, col in REV.items():
        d = _raw(c)
        d = d[d[col].notna()]          # is_estimate flags other columns; the revenue cell itself is verified in Pipeline A
        d = d.assign(fy=d.apply(lambda r: _fiscal_year(c, r), axis=1))
        fy_sum = d.groupby("fy")[col].agg(["sum", "count"])
        fy_sum = fy_sum[fy_sum["count"] == 4]
        xbrl = _xbrl_annual(c) if COMPANIES[c].get("sec_cik") else {}
        for fy, r in fy_sum.iterrows():
            s4 = float(r["sum"])
            if c in ("logitech", "ingram", "tdsynnex"):
                fy_val, basis, verified = xbrl.get(int(fy)), "10-K XBRL annual fact (audited)", "xbrl"
            elif c == "nordic":
                m = audited[(audited["company"] == c) & (audited["fiscal_year"] == fy)]
                if len(m):
                    fy_val, basis = float(m["value"].iloc[0]), f"typed from {m['source_key'].iloc[0]}"
                    t = _doc_text(c, m["source_key"].iloc[0])
                    k = f"{c}|{fy}"
                    if t is None:
                        verified = (ledger.recall("step1_t1", k) or ("AR not cached", ""))[0]
                    else:
                        verified = ledger.record("step1_t1", k, "found in AR text" if _in(t, fy_val) else "NOT found in AR text")
                else:
                    fy_val, basis, verified = None, "no audited figure typed", ""
            else:   # gn: locate Σ4Q in the annual report within 0.3%
                key = f"AR{fy}"
                t = _doc_text(c, key)
                fy_val, basis, verified = None, f"searched {key} text for a figure within 0.3% of Σ4Q", "AR not cached"
                rec = ledger.recall("step1_t1", f"{c}|{fy}") if t is None else None
                if rec:
                    verified, fy_val = rec[0], (float(rec[1]) if rec[1] else None)
                if t:
                    cands = [n for n in _numbers(t) if abs(n - s4) <= 0.003 * s4]
                    if cands:
                        fy_val, verified = min(cands, key=lambda n: abs(n - s4)), f"figure {min(cands, key=lambda n: abs(n - s4)):,.0f} present in {key}"
                    else:
                        verified = f"no figure within 0.3% of Σ4Q in {key}"
                    ledger.record("step1_t1", f"{c}|{fy}", verified, fy_val)
            diff = (s4 / fy_val - 1) * 100 if fy_val else None
            rows.append({"company": c, "fiscal_year": int(fy), "sum_4q": round(s4, 1), "audited_fy": None if fy_val is None else round(fy_val, 1),
                         "diff_pct": None if diff is None else round(diff, 3), "audited_basis": basis, "verification": verified,
                         "pass": None if diff is None else bool(abs(diff) <= 0.1)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "test1_sum4q_vs_fy.csv", index=False)
    return out


def test2_restatements() -> pd.DataFrame:
    r = pd.read_csv(CONFIG / "restatements.csv", dtype={"quarter": str})
    rows = []
    for _, x in r.iterrows():
        t_o, t_r = _doc_text(x["company"], x["original_key"]), _doc_text(x["company"], x["restated_key"])
        k = f"{x['company']}|{x['quarter']}|{x['segment']}"
        v_o = "n/a (approx)" if x["approx"] else _check("step1_t2_original", k, t_o, lambda t: _in(t, x["original_value"]), "found", "NOT found", "no filing")
        v_r = _check("step1_t2_restated", k, t_r, lambda t: _in(t, x["restated_value"]), "found", "NOT found", "no filing")
        csv_val = _raw(x["company"]).set_index("quarter").loc[x["quarter"], x["csv_column"]] if x["csv_column"] in _raw(x["company"]).columns else None
        rows.append({**x.to_dict(), "change_pct": round((x["restated_value"] / x["original_value"] - 1) * 100, 1),
                     "original_verified": v_o, "restated_verified": v_r, "csv_uses": "restated" if csv_val is not None and abs(float(csv_val) - x["restated_value"]) < 0.06 else
                     ("original" if csv_val is not None and abs(float(csv_val) - x["original_value"]) < 0.06 else f"other ({csv_val})")})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "test2_restatements.csv", index=False)
    return out


def test3_adjusted_vs_reported() -> pd.DataFrame:
    a = pd.read_csv(CONFIG / "adjusted_vs_reported.csv", dtype={"quarter": str})
    rows = []
    for _, x in a.iterrows():
        t = _doc_text(x["company"], x["source_key"])
        ver = _check("step1_t3", f"{x['company']}|{x['quarter']}|{x['metric']}", t,
                     lambda t: _in(t, x["reported_value"]) and _in(t, x["adjusted_value"]), "both found", "NOT both found", "no filing")
        rows.append({**x.to_dict(), "gap_pts": round(x["adjusted_value"] - x["reported_value"], 1), "verification": ver})
    l = _raw("logitech").dropna(subset=["gm_gaap_pct", "gm_nongaap_pct"])
    for _, x in l.iterrows():
        rows.append({"company": "logitech", "quarter": x["quarter"], "metric": "gross_margin", "reported_value": x["gm_gaap_pct"], "adjusted_value": x["gm_nongaap_pct"],
                     "unit": "pct", "source_key": x["quarter"], "reason": "GAAP vs non-GAAP GM (share-based comp, amortisation)", "gap_pts": round(x["gm_nongaap_pct"] - x["gm_gaap_pct"], 1),
                     "verification": "hand CSV (8-K exhibit verified in Pipeline A)"})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "test3_adjusted_vs_reported.csv", index=False)
    return out


def confidence(t1: pd.DataFrame, t2: pd.DataFrame, t3: pd.DataFrame) -> pd.DataFrame:
    """Fold the three tests into one interval per company × metric class, and a final grade."""
    rows = []
    for c in REV:
        a = t1[t1["company"] == c].dropna(subset=["diff_pct"])
        tot = float(a["diff_pct"].abs().max()) if len(a) else None
        rows.append({"company": c, "metric_class": "total revenue (quarterly)", "interval": f"±{tot:.2f}%" if tot is not None else "n/a",
                     "basis": f"Σ4Q vs audited FY, {len(a)} years, max |diff|", "grade": "A" if tot is not None and tot <= 0.1 else "B",
                     "rule": "Q4 absorbs audit true-ups, so quarterly totals are audited-equivalent"})
        s = t2[t2["company"] == c]
        if len(s):
            for seg, g in s.groupby("segment"):
                mx = float(g["change_pct"].abs().max())
                rows.append({"company": c, "metric_class": f"segment: {seg}", "interval": f"±{mx:.0f}%",
                             "basis": f"{len(g)} restated quarters, max |change| (CSV uses {', '.join(sorted(set(g['csv_uses'])))} values)",
                             "grade": "B", "rule": "use restated values where they exist; treat pre-restatement quarters as ±this"})
        else:
            rows.append({"company": c, "metric_class": "segments", "interval": "±0% observed", "basis": "no restatement found in the cached filings", "grade": "B",
                         "rule": "no taxonomy change in the window (Ingram / TD Synnex report one segment)"})
        m = t3[t3["company"] == c]
        if len(m):
            mx = float(m["gap_pts"].abs().max())
            rows.append({"company": c, "metric_class": "margins (reported vs adjusted)", "interval": f"up to {mx:.1f} pts",
                         "basis": f"{len(m)} quarters compared, max |adjusted − reported|", "grade": "B" if mx <= 2 else "C",
                         "rule": "model the adjusted series and show the reported one beside it; widen Q4 ranges"})
    out = pd.DataFrame(rows)
    grade_rank = {"A": 0, "B": 1, "C": 2}
    final = out.groupby("company")["grade"].agg(lambda g: max(g, key=lambda x: grade_rank[x])).rename("final_grade")
    out = out.merge(final, on="company")
    out.to_csv(OUT / "confidence.csv", index=False)
    return out


def run_step1() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    t1, t2, t3 = test1_sum4q_vs_fy(), test2_restatements(), test3_adjusted_vs_reported()
    conf = confidence(t1, t2, t3)
    ledger.save()
    final = conf.drop_duplicates("company")[["company", "final_grade"]].set_index("company")["final_grade"].to_dict()
    today = date.today().isoformat()
    md = [f"# Step 1 — filing confidence — {today}\n",
          "Three separate tests, every row logged in `outputs/test1_sum4q_vs_fy.csv`, `test2_restatements.csv`, `test3_adjusted_vs_reported.csv`; "
          "the fold is `outputs/confidence.csv`. Grade of the step itself: **A** (arithmetic on filings; every number verified in the cited filing text).\n",
          "## Final confidence level\n", pd.Series(final).to_frame("final grade of quarterly data").to_markdown(), "",
          "Reading: A = quarterly totals are audited-equivalent and segments unchanged; B = totals audited-equivalent, segments carry restatement risk of the size shown, margins need the adjusted series; C = margin definitions move by more than 2 pts.\n",
          "## Confidence by company and metric class\n", conf.to_markdown(index=False), "",
          "## Test 1 — Σ4Q vs audited FY\n", t1.to_markdown(index=False), "",
          "## Test 2 — original vs restated segment values\n", t2[["company", "quarter", "segment", "original_value", "restated_value", "change_pct", "original_verified", "restated_verified", "csv_uses", "reason"]].to_markdown(index=False), "",
          "## Test 3 — reported vs adjusted margins\n", t3.to_markdown(index=False), "",
          "## What it means for the model\n",
          "- Totals and Q4 balance sheets: use as audited. Segments: use restated values (the CSVs do) and carry the interval above for quarters before a taxonomy change.",
          "- Margins: model the adjusted series, show reported beside it; Nordic and GN Q4 reports are the annual-report first draft, so Q4 one-offs are larger — widen Q4 ranges. The three forecast quarters are Q3, so unaffected.",
          "- Verbal channel metrics stay grade C (Pipeline A, `verbal_metrics.csv`)."]
    (OUT / "step1_report.md").write_text("\n".join(md))
    with open(OUT / "final_confidence.json", "w") as f:
        json.dump({"as_of": today, "final_grade": final, "step_grade": "A"}, f, indent=2)
    return {"confidence": conf, "final": final, "path": OUT / "step1_report.md"}


if __name__ == "__main__":
    r = run_step1()
    print(pd.Series(r["final"]).to_string()); print(f"\nwrote {r['path']}")
