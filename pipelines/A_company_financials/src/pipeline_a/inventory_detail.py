"""Step-3 inventory detail: the balance-sheet and channel data that step 3 (inventory mechanism) needs beyond headline
inventory. Three sources, each fetched by script from a primary filing and each with its own validation check:

  1. SEC XBRL company facts (keyless)
       Logitech  : inventory split raw materials / finished goods, trade receivables  -> finished-goods share, DSO
       Arrow     : revenue, cost of sales, inventory, receivables                      -> franchised-distributor DIO
       Avnet     : revenue, cost of sales, inventory, receivables                      -> franchised-distributor DIO
     Validation: (a) Logitech RM + FG == InventoryNet (tolerance 0.5%); (b) Logitech InventoryNet == the hand-typed
     inventory_usdm in data/raw/logitech_quarterly.csv (tolerance 0.5%); (c) Arrow / Avnet revenue > cost of sales > 0
     and inventory > 0 in every quarter (catches Q4-derivation and tag-switch errors).

  2. Microchip 10-Q / 10-K text (EDGAR primary documents, cached)
       "At <date>, our distributors maintained NN days of inventory of our products compared to MM days at <date>."
     This is the only numeric, recurring, audited-filing disclosure of MCU distribution-channel inventory we found
     (Silicon Labs, the closest BLE peer, discloses only its OWN days of inventory — checked in its 10-Qs).
     Validation: the sentence is extracted verbatim and stored as `quote`; and the chain check — the "compared to MM
     days at <date>" in filing t must equal the NN that the filing for <date> reported (Microchip compares with its
     last fiscal year end) — is a second, independent reading of every value. The ten-year range sentence that
     follows ("fluctuated between approximately 17 days and 43 days") is captured too.

Why Arrow and Avnet rather than more Ingram / TD Synnex: they are Nordic's franchised distributors (Pipeline C
config/distributors.csv), while Ingram / TD Synnex sit on the Logitech side and peripherals are 1-2% of their sales.
Caveat carried into step 3: Arrow's total includes its Enterprise Computing segment (ECS, ~30% of sales), so Arrow
DIO is a components-plus-IT blend; Avnet is almost pure components (Electronic Components + Farnell).

Output (source-stamped, read by steps/step3_inventory_mechanism):
  data/raw/inventory_detail_xbrl.csv   long format: company, quarter, metric, value_usdm, xbrl_tag, form, filed
  data/raw/mchp_distributor_days.csv   quarter, period_end, disti_days, prior_days, chain check, 10-year range, form, url, quote
  data/processed/inventory_detail_validation.csv   one row per check
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

import pandas as pd

from .paths import DATA_RAW, DATA_PROC, CACHE, CONFIG as CONFIG_DIR
from .sec import fetch_companyfacts, _facts, _duration_quarters, _instant, UA
from .manifest import COMPANIES

SEC_CIK = {c: COMPANIES[c]["sec_cik"] for c in ("logitech", "arrow", "avnet", "microchip", "amazon", "bestbuy", "walmart", "target", "cdw")}
RETAIL = ("amazon", "bestbuy", "walmart", "target", "cdw")      # step 5: retail / reseller inventory cover (all categories)
START = pd.Period("2020Q1", "Q")
TOL_PCT = 0.5

TAGS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "inventory": ["InventoryNet"],
    "inv_raw_materials": ["InventoryRawMaterialsNetOfReserves"],
    "inv_finished_goods": ["InventoryFinishedGoodsNetOfReserves"],
    "receivables": ["AccountsReceivableNetCurrent"],
}
DURATION = {"revenue", "cogs"}
WANT = {
    "logitech": ["inventory", "inv_raw_materials", "inv_finished_goods", "receivables"],
    "arrow": ["revenue", "cogs", "inventory", "receivables"],
    "avnet": ["revenue", "cogs", "inventory", "receivables"],
    **{c: ["revenue", "cogs", "inventory"] for c in RETAIL},
}


def fiscal_to_calendar_quarter(end) -> pd.Period:
    """Alias of sec.calendar_quarter, the single mapping rule (P124: the former end - 15 days filed quarters closing a month
    after the calendar quarter - Walmart, Target, Best Buy, ADI, Semtech - one quarter late)."""
    from .sec import calendar_quarter
    return calendar_quarter(end)


# ------------------------------------------------------------------ 1. XBRL
def xbrl_detail(refresh: bool = False) -> pd.DataFrame:
    rows = []
    for company, metrics in WANT.items():
        facts = fetch_companyfacts(SEC_CIK[company], refresh)
        for m in metrics:
            f = _facts(facts, TAGS[m])
            if f.empty:
                continue
            s = _duration_quarters(f, fiscal_to_calendar_quarter) if m in DURATION else _instant(f, fiscal_to_calendar_quarter)
            tag = f["tag"].iloc[-1]
            rows += [{"company": company, "quarter": str(q), "metric": m, "value_usdm": round(v / 1e6, 1),
                      "xbrl_tag": tag, "source": f"SEC XBRL companyfacts CIK{SEC_CIK[company]:010d}"}
                     for q, v in s.items() if q >= START]
    out = pd.DataFrame(rows).sort_values(["company", "metric", "quarter"]).reset_index(drop=True)
    out.to_csv(DATA_RAW / "inventory_detail_xbrl.csv", index=False)
    return out


def validate_xbrl(detail: pd.DataFrame) -> pd.DataFrame:
    w = detail.pivot_table(index=["company", "quarter"], columns="metric", values="value_usdm")
    checks = []
    logi = w.loc["logitech"].dropna(subset=["inventory", "inv_raw_materials", "inv_finished_goods"])
    diff = ((logi["inv_raw_materials"] + logi["inv_finished_goods"]) / logi["inventory"] - 1) * 100
    checks.append({"check": "logitech RM + FG == InventoryNet", "n": len(diff), "max_abs_diff_pct": round(diff.abs().max(), 3),
                   "passed": bool((diff.abs() <= TOL_PCT).all())})
    hand = pd.read_csv(DATA_RAW / "logitech_quarterly.csv").set_index("quarter")["inventory_usdm"].dropna()
    common = logi.index.intersection(hand.index)
    d2 = (logi.loc[common, "inventory"] / hand.loc[common] - 1) * 100
    checks.append({"check": "logitech XBRL InventoryNet == hand-typed inventory_usdm", "n": len(d2),
                   "max_abs_diff_pct": round(d2.abs().max(), 3), "passed": bool((d2.abs() <= TOL_PCT).all())})
    for c in ("arrow", "avnet"):
        x = w.loc[c].dropna(subset=["revenue", "cogs", "inventory"])
        ok = (x["revenue"] > x["cogs"]) & (x["cogs"] > 0) & (x["inventory"] > 0)
        gm = (1 - x["cogs"] / x["revenue"]) * 100
        checks.append({"check": f"{c} revenue > COGS > 0, inventory > 0; GM {gm.min():.1f}-{gm.max():.1f}%", "n": len(x),
                       "max_abs_diff_pct": float("nan"), "passed": bool(ok.all()) and gm.between(5, 20).all()})
    # retail / reseller cover proxies (step 5): same identity checks; plausible gross-margin band per business model
    band = {"amazon": (30, 60), "bestbuy": (15, 30), "walmart": (18, 30), "target": (20, 35), "cdw": (15, 28)}
    for c in RETAIL:
        if c not in w.index.get_level_values(0):
            checks.append({"check": f"{c}: XBRL revenue / cost of sales / inventory found", "n": 0, "max_abs_diff_pct": float("nan"), "passed": False})
            continue
        x = w.loc[c].dropna(subset=["revenue", "cogs", "inventory"])
        ok = (x["revenue"] > x["cogs"]) & (x["cogs"] > 0) & (x["inventory"] > 0)
        gm = (1 - x["cogs"] / x["revenue"]) * 100
        lo, hi = band[c]
        checks.append({"check": f"{c} revenue > cost of sales > 0, inventory > 0; GM {gm.min():.1f}-{gm.max():.1f}% within {lo}-{hi}%", "n": len(x),
                       "max_abs_diff_pct": float("nan"), "passed": bool(ok.all()) and len(x) >= 8 and bool(gm.between(lo, hi).all())})
    return pd.DataFrame(checks)


# ------------------------------------------------------------------ 2. Microchip distributor days
_D = r"([A-Z][a-z]+ \d{1,2}, \d{4})"
MCHP_RE = re.compile(r"(?:At|As of) " + _D + r" ?,? our distributors maintained (\d+) days of inventory of our products ?,? (?:as )?compared to "
                     r"(\d+) days(?: of inventory)?(?: at our distributors)? at " + _D)
# older 10-Qs: 'At June 30, 2012 and March 31, 2012, our distributors maintained 31 days of inventory of our products.'
MCHP_SAME_RE = re.compile(r"(?:At|As of) " + _D + r" and " + _D + r" ?,? our distributors maintained (\d+) days of inventory of our products")
# 2018-12: 'Our distributors maintained 36 days of inventory of our products at December 31, 2018 and March 31, 2018'
MCHP_SAME_END_RE = re.compile(r"[Oo]ur distributors maintained (\d+) days of inventory of our products at " + _D + r" and " + _D)
# 2009 / 2015-16: '... 37 days of inventory of our products which was flat compared to the days of inventory at our distributors at
# March 31, 2015' (prior = current); 2009-09: '... which is in line with their inventory levels at March 31, 2009' (no number: prior unknown)
MCHP_FLAT_RE = re.compile(r"(?:At|As of) " + _D + r" ?,? our distributors maintained (\d+) days of inventory of our products,? which (?:was|is) "
                          r"(flat|in line)[^.]{0,120}? at " + _D)
MCHP_RANGE_RE = re.compile(r"fluctuated between (?:approximately )?(\d+) days and (\d+) days")


def parse_mchp(text: str) -> dict | None:
    """First 'our distributors maintained NN days ... compared to MM days' sentence in a Microchip filing (both wordings used
    since 2010), plus the 'over the past N fiscal years ... between LO days and HI days' range that follows it."""
    m = MCHP_RE.search(text)
    if m:
        cur_end, cur, prior, prior_end = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    elif (m := MCHP_SAME_RE.search(text)):
        cur_end, prior_end, cur = m.group(1), m.group(2), int(m.group(3))
        prior = cur
    elif (m := MCHP_SAME_END_RE.search(text)):
        cur, cur_end, prior_end = int(m.group(1)), m.group(2), m.group(3)
        prior = cur
    elif (m := MCHP_FLAT_RE.search(text)):
        cur_end, cur, prior_end = m.group(1), int(m.group(2)), m.group(4)
        prior = cur if m.group(3) == "flat" else None          # 'in line with' states no number
    else:
        return None
    rng = MCHP_RANGE_RE.search(text, m.end())
    return {"period_end": pd.Timestamp(cur_end).date().isoformat(), "disti_days": cur, "prior_days": prior,
            "prior_end": pd.Timestamp(prior_end).date().isoformat(), "quote": m.group(0),
            "range10y_low": int(rng.group(1)) if rng else None, "range10y_high": int(rng.group(2)) if rng else None}


def chain_check(df: pd.DataFrame) -> pd.DataFrame:
    """Filing t says 'compared to MM days at <prior date>'; MM must equal the NN filing t-1 reported for that date."""
    by_end = dict(zip(df["period_end"], df["disti_days"]))
    out = df.copy()
    out["chain_value"] = out["prior_end"].map(by_end)
    out["chain_ok"] = out["chain_value"].isna() | out["prior_days"].isna() | (out["chain_value"] == out["prior_days"])
    return out


def _html_text(raw: str) -> str:
    import html
    raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw)))


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "identity"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    time.sleep(0.2)
    return data


def _fill_from_comparatives(df: pd.DataFrame, since: str) -> pd.DataFrame:
    """A quarter with no filing of its own (e.g. 2008Q1: the FY2008 10-K predates the disclosure) takes the value later filings
    state for it as a comparative - only when every such statement agrees. Marked form 'comparative', grade B."""
    have = set(df["period_end"])
    comp = df.dropna(subset=["prior_days"]).groupby("prior_end")["prior_days"].agg(["nunique", "first", "count"])
    add = [{"period_end": e, "disti_days": r["first"], "prior_days": None, "prior_end": None, "form": "comparative",
            "quote": f"stated as the comparative in {int(r['count'])} later filings", "accession": "", "url": "", "report_date": e,
            "range10y_low": None, "range10y_high": None}
           for e, r in comp.iterrows() if e not in have and r["nunique"] == 1 and e >= since]
    if not add:
        return df
    out = pd.concat([df, pd.DataFrame(add)], ignore_index=True).sort_values("period_end")
    out["quarter"] = out["period_end"].map(lambda e: str(fiscal_to_calendar_quarter(e)))
    return out.reset_index(drop=True)


def mchp_distributor_days(refresh: bool = False, since: str = "2010-06-01", out_name: str = "mchp_distributor_days.csv",
                          fill_from_comparatives: bool = False) -> pd.DataFrame:
    cik = SEC_CIK["microchip"]
    cdir = CACHE / "filings" / "microchip"
    cdir.mkdir(parents=True, exist_ok=True)
    sub_f = cdir / "submissions.json"
    if refresh or not sub_f.exists():
        sub_f.write_bytes(_get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))
    sub = json.loads(sub_f.read_text())
    pages = [sub["filings"]["recent"]]
    for pf in sub["filings"].get("files", []):            # older filings are in paged files
        f_ = cdir / pf["name"]
        if refresh or not f_.exists():
            f_.write_bytes(_get(f"https://data.sec.gov/submissions/{pf['name']}"))
        pages.append(json.loads(f_.read_text()))
    filings = [(fm, a, d, r) for rec in pages for fm, a, d, r in zip(rec["form"], rec["accessionNumber"], rec["primaryDocument"], rec["reportDate"])]
    rows = []
    for form, acc, doc, rep in filings:
        if form not in ("10-Q", "10-K") or rep < since:
            continue
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
        f = cdir / f"{acc}.htm"
        if refresh or not f.exists():
            f.write_bytes(_get(url))
        hit = parse_mchp(_html_text(f.read_text(errors="ignore")))
        base = {"form": form, "accession": acc, "url": url, "report_date": rep}
        rows.append({**base, **hit} if hit else {**base, "period_end": rep, "quote": "", "disti_days": None, "prior_days": None, "prior_end": None})
    df = pd.DataFrame(rows).sort_values("period_end").reset_index(drop=True)
    df["quarter"] = df["period_end"].map(lambda e: str(fiscal_to_calendar_quarter(e)))
    unparsed = df[df["disti_days"].isna()]
    unparsed[["period_end", "form", "accession", "url"]].to_csv(DATA_PROC / out_name.replace("distributor_days", "unparsed_filings"), index=False)
    df = df.dropna(subset=["disti_days"]).drop_duplicates("quarter", keep="last").reset_index(drop=True)
    if fill_from_comparatives:
        df = _fill_from_comparatives(df, since)
    df = chain_check(df)
    known = pd.read_csv(CONFIG_DIR / "known_filing_issues.csv", dtype=str)
    explained = set(known.loc[known["company"] == "microchip", "period_end"])
    df["chain_ok"] = df["chain_ok"] | df["period_end"].isin(explained)
    df["chain_note"] = df["period_end"].map(lambda e: "explained: see config/known_filing_issues.csv" if e in explained else "")
    df.attrs["n_filings"], df.attrs["n_unparsed"] = len(df) + len(unparsed), len(unparsed)
    df["grade"] = df["form"].map({"10-K": "A", "10-Q": "B", "comparative": "B"})
    cols = ["quarter", "period_end", "disti_days", "prior_days", "prior_end", "chain_value", "chain_ok", "chain_note", "range10y_low", "range10y_high",
            "form", "grade", "accession", "url", "quote"]
    df[cols].to_csv(DATA_RAW / out_name, index=False)
    return df[cols]


def run(refresh: bool = False) -> dict:
    detail = xbrl_detail(refresh)
    checks = validate_xbrl(detail)
    mchp = mchp_distributor_days(refresh)
    # long history for the cycle-stability test only (Pipeline D / step 6f): Microchip first discloses distributor days in the
    # June-2008 10-Q (with June 2007 as comparative); the main series keeps its 2010 start so the composite's spec is unchanged
    long = mchp_distributor_days(refresh, since="2007-06-01", out_name="mchp_distributor_days_long.csv", fill_from_comparatives=True)
    found = mchp["disti_days"].notna()
    checks = pd.concat([checks, pd.DataFrame([
        {"check": f"microchip sentence found in >= 80% of 10-Q/10-K since 2010 ({len(mchp)} of {mchp.attrs.get('n_filings', len(mchp))}; unparsed listed in data/processed/mchp_unparsed_filings.csv)",
         "n": int(mchp.attrs.get("n_filings", len(mchp))), "max_abs_diff_pct": float("nan"), "passed": bool(len(mchp) >= 0.8 * mchp.attrs.get("n_filings", len(mchp)))},
        {"check": "microchip chain: 'compared to MM days' == prior filing's NN (documented filing errors: config/known_filing_issues.csv)", "n": int(mchp["chain_value"].notna().sum()),
         "max_abs_diff_pct": float("nan"), "passed": bool(mchp["chain_ok"].all())},
        {"check": "microchip long history (2008+): chain check", "n": int(long["chain_value"].notna().sum()),
         "max_abs_diff_pct": float("nan"), "passed": bool(long["chain_ok"].all())},
        {"check": "microchip: no quarter missing between the first and last parsed quarter (a gap blanks the change on both sides)",
         "n": len(mchp), "max_abs_diff_pct": float("nan"),
         "passed": bool(pd.PeriodIndex(mchp["quarter"], freq="Q").sort_values().to_series().diff().dropna().map(lambda d: d.n).max() == 1)},
    ])], ignore_index=True)
    DATA_PROC.mkdir(parents=True, exist_ok=True)
    checks.to_csv(DATA_PROC / "inventory_detail_validation.csv", index=False)
    return {"detail": detail, "mchp": mchp, "mchp_long": long, "checks": checks}
