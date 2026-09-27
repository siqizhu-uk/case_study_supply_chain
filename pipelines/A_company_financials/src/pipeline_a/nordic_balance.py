"""Nordic balance-sheet detail for step 3, read by script from the cached Oslo Børs NewsWeb reports (no hand typing).

  1. Quarterly accounts receivable and inventory — balance-sheet lines "Accounts receivable  115 653  93 488  66 056"
     (current quarter, prior year-end, year-ago quarter; USD thousands).
     Validation (chain check): the year-ago column of report t must equal the current column of report t-4, and the
     inventory read here must equal the hand-typed inventory_usdm in data/raw/nordic_quarterly.csv (0.5% tolerance).
  2. Inventory by stage at each year end — annual-report note "Cost of materials / inventory":
     Raw materials (= wafers: Nordic is fabless, all stock sits at sub-contractors), Work in progress, Finished goods.
     Validation: RM + WIP + FG == total inventory in the same note == hand-typed Q4 inventory_usdm; and the prior-year
     column of AR y must equal the current column of AR y-1.
  3. Customer-concentration disclosures (data/raw/nordic_customer_concentration.csv, hand-typed): every row carries
     one or more verbatim fragments; each fragment must occur in the cited report's text (whitespace-normalised).

Outputs: data/raw/nordic_balance_extract.csv, data/raw/nordic_inventory_stage.csv,
         data/processed/nordic_balance_validation.csv, data/processed/nordic_concentration_check.csv
"""
from __future__ import annotations

import re

import pandas as pd

from .paths import DATA_RAW, DATA_PROC
from .filings import extract_text, _doc

TOL_PCT = 0.5
_NUM = r"(\d{1,3} \d{3})(?!\d)"   # USD thousands, every line < USD 1bn: exactly one thousands group (stops adjacent columns merging)


def _k(s: str | None) -> float | None:
    return None if s is None else int(s.replace(" ", "")) / 1000.0


def parse_balance_line(text: str, label_re: str) -> list[float]:
    """Numbers (USD m) following the first balance-sheet line that starts with `label_re`."""
    t = re.sub(r"[ \t]+", " ", text)
    m = re.search(rf"(?:^|\n){label_re} {_NUM}(?: {_NUM})?(?: {_NUM})?", t)
    return [] if not m else [_k(g) for g in m.groups() if g]


def quarterly_balance(first: str = "2020Q4", last: str = "2026Q2") -> pd.DataFrame:
    rows = []
    for q in (str(p) for p in pd.period_range(first, last, freq="Q")):
        doc = _doc("nordic", q)
        if doc is None:
            rows.append({"quarter": q, "status": "no_filing"})
            continue
        text = extract_text(doc)
        ar = parse_balance_line(text, r"(?:Accounts|Trade) receivables?")
        inv = parse_balance_line(text, r"Inventor(?:y|ies)")
        rows.append({"quarter": q, "receivables_usdm": ar[0] if ar else None, "inventory_usdm": inv[0] if inv else None,
                     "receivables_yago_col_usdm": ar[2] if len(ar) == 3 else None,
                     "inventory_yago_col_usdm": inv[2] if len(inv) == 3 else None,
                     "status": "extracted" if ar and inv else "not_found", "document": doc.name})
    return pd.DataFrame(rows)


def chain_check_quarterly(df: pd.DataFrame) -> pd.DataFrame:
    """Year-ago column in report t vs current column in report t-4 (Q4 reports carry no year-ago column)."""
    d = df.set_index("quarter")
    out = []
    for col in ("receivables", "inventory"):
        cur, yago = d[f"{col}_usdm"], d[f"{col}_yago_col_usdm"]
        for q in d.index:
            q4 = str(pd.Period(q, "Q") - 4)
            if pd.notna(yago.get(q)) and q4 in cur.index and pd.notna(cur[q4]):
                out.append({"metric": col, "quarter": q, "value_in_report_t_minus_4": cur[q4], "year_ago_column_in_report_t": yago[q],
                            "match": abs(cur[q4] - yago[q]) < 0.05})
    return pd.DataFrame(out)


STAGES = {"raw_materials": r"Raw materials", "work_in_progress": r"Work in Progress", "finished_goods": r"Finished goods"}


def annual_stages(years=range(2021, 2026)) -> pd.DataFrame:
    """Two numbers directly before each stage label: '<this year> <prior year> Raw materials'."""
    rows = []
    for y in years:
        doc = _doc("nordic", f"AR{y}")
        if doc is None:
            continue
        t = re.sub(r"\s+", " ", extract_text(doc))
        rec = {"year": y, "quarter": f"{y}Q4", "document": doc.name}
        for k, lab in STAGES.items():
            m = re.search(rf"{_NUM} {_NUM} {lab}\b", t)
            rec[f"{k}_usdm"], rec[f"{k}_prior_usdm"] = (_k(m.group(1)), _k(m.group(2))) if m else (None, None)
        rows.append(rec)
    out = pd.DataFrame(rows)
    out["total_usdm"] = out[["raw_materials_usdm", "work_in_progress_usdm", "finished_goods_usdm"]].sum(axis=1)
    return out


def check_stages(st: pd.DataFrame) -> pd.DataFrame:
    hand = pd.read_csv(DATA_RAW / "nordic_quarterly.csv").set_index("quarter")["inventory_usdm"]
    rows = []
    by_year = st.set_index("year")
    for _, r in st.iterrows():
        parts = r["raw_materials_usdm"] + r["work_in_progress_usdm"] + r["finished_goods_usdm"]
        rows.append({"year": r["year"], "check": "RM+WIP+FG == hand-typed Q4 inventory_usdm",
                     "diff_pct": round((parts / hand.get(r["quarter"]) - 1) * 100, 3)})
        if r["year"] - 1 in by_year.index:
            prev = by_year.loc[r["year"] - 1]
            d = max(abs(r[f"{s}_prior_usdm"] - prev[f"{s}_usdm"]) for s in ("raw_materials", "work_in_progress", "finished_goods"))
            rows.append({"year": r["year"], "check": "prior-year column == previous AR current column", "diff_pct": round(d, 3)})
    out = pd.DataFrame(rows)
    out["passed"] = out["diff_pct"].abs() <= TOL_PCT
    return out


def check_concentration() -> pd.DataFrame:
    """Every '|'-separated fragment of `quote_fragments` must occur in the cited Nordic report."""
    f = DATA_RAW / "nordic_customer_concentration.csv"
    c = pd.read_csv(f)
    rows = []
    for _, r in c.iterrows():
        doc = _doc("nordic", r["document_key"])
        text = re.sub(r"\s+", " ", extract_text(doc)) if doc else ""
        frags = [s.strip() for s in str(r["quote_fragments"]).split("|") if s.strip()]
        missing = [s for s in frags if s not in text]
        rows.append({"year": r["year"], "metric": r["metric"], "value": r["value"], "document_key": r["document_key"],
                     "fragments": len(frags), "missing": " | ".join(missing), "verified": bool(doc) and not missing})
    return pd.DataFrame(rows)


def run() -> dict:
    qb = quarterly_balance()
    chain = chain_check_quarterly(qb)
    hand = pd.read_csv(DATA_RAW / "nordic_quarterly.csv").set_index("quarter")["inventory_usdm"]
    inv_match = qb.dropna(subset=["inventory_usdm"]).assign(hand=lambda d: d["quarter"].map(hand)).dropna(subset=["hand"])
    inv_diff = ((inv_match["inventory_usdm"] / inv_match["hand"] - 1) * 100).abs()
    st = annual_stages()
    stc = check_stages(st)
    conc = check_concentration()
    qb.to_csv(DATA_RAW / "nordic_balance_extract.csv", index=False)
    st.to_csv(DATA_RAW / "nordic_inventory_stage.csv", index=False)
    checks = pd.DataFrame([
        {"check": "nordic AR + inventory line found in every quarterly report", "n": len(qb), "passed": bool((qb["status"] == "extracted").all())},
        {"check": "nordic chain: year-ago column (t) == current column (t-4)", "n": len(chain), "passed": bool(chain["match"].all()) if len(chain) else False},
        {"check": f"nordic extracted inventory == hand-typed (max diff {inv_diff.max():.2f}%)", "n": len(inv_match), "passed": bool((inv_diff <= TOL_PCT).all())},
        {"check": "nordic AR-note stages: sum and prior-year chain", "n": len(stc), "passed": bool(stc["passed"].all())},
        {"check": "nordic customer-concentration quotes found in cited report", "n": len(conc), "passed": bool(conc["verified"].all())},
    ])
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    checks.to_csv(DATA_PROC / "nordic_balance_validation.csv", index=False)
    conc.to_csv(DATA_PROC / "nordic_concentration_check.csv", index=False)
    return {"quarterly": qb, "chain": chain, "stages": st, "stage_checks": stc, "concentration": conc, "checks": checks}
