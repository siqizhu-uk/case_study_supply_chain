"""2008-09 cycle: guides and actuals for the releases that guide 2008Q3-2010Q4 (config `history` in peers.yaml).

Before XBRL (2009Q2 for most peers) the actual comes from the release that reports the quarter, read twice: the narrative
sentence ('Net revenues for the quarter were $53.8 million') and the income-statement table ('Net sales $ 53,812'). Both
must agree; where XBRL also exists, the first-reported XBRL value is used and the release value is only a check.
The reported quarter of a release is found from the firm's own quarter-end calendar (XBRL ends projected back by whole
years; 52/53-week drift is a few days), exactly as build.company_rows does for the XBRL era.
"""
from __future__ import annotations

import re

import pandas as pd

from .releases import RAW, load_cfg, earnings_releases
from .parse import parse_guide, UNIT, _num
from .build import xbrl_quarters, fiscal_to_calendar_quarter


def quarter_ends(xq: pd.DataFrame, back_years: int = 3) -> pd.Series:
    """The firm's quarter ends: XBRL ends plus every XBRL end projected back 1..back_years years (the first XBRL year has
    no Q4: Q4 = FY - 9M needs three tagged quarters, so December ends must come from later years)."""
    past = [e - pd.DateOffset(years=k) for e in xq["period_end"] for k in range(1, back_years + 1)]
    return pd.Series(sorted(set(xq["period_end"]) | set(past)))


def release_actual(text: str, h: dict) -> dict | None:
    """Revenue the release reports for its own quarter: first narrative sentence (not a forward-looking one) and the first
    income-statement row; the table may be in thousands or millions."""
    m = next((m for rx in (h["actual_headline_re"], h["actual_re"]) for m in re.finditer(rx, text, re.I)
              if not re.search(r"expect|anticipat|guid|outlook", text[max(0, m.start() - 120):m.start()], re.I)), None)
    if m is None:
        return None
    val = _num(m.group(1)) * UNIT[m.group(2).lower()]
    tab = next((_num(t.group(1)) / k for t in re.finditer(h["table_re"], text, re.I) for k in (1000.0, 1.0)
                if abs(_num(t.group(1)) / k / val - 1) <= h["actual_tolerance"]), None)
    return {"actual_release_usdm": val, "actual_quote": m.group(0)[:200], "actual_table_usdm": tab}


def company_history(company: str, spec: dict, cfg: dict) -> pd.DataFrame:
    h = cfg["history"]
    xq = xbrl_quarters(spec["cik"])
    ends = quarter_ends(xq)
    excl = {e["release"] for e in h.get("exclude_releases", []) if e["company"] == company}
    pats = h["patterns"].get(company, []) + spec["patterns"]
    rows = []
    for r in earnings_releases(company, spec["cik"], h["release_from"]):
        if r["date"] >= h["release_to"] or not r["text"] or r["date"] in excl:
            continue
        d = pd.Timestamp(r["date"])
        prior = ends[(ends < d) & (ends >= d - pd.Timedelta(days=75))]
        if prior.empty:
            continue
        rep_q = fiscal_to_calendar_quarter(prior.iloc[-1])
        a = release_actual(r["text"], h) or {}
        rows.append({"company": company, "release_date": r["date"], "reported_quarter": str(rep_q), "guided_quarter": str(rep_q + 1),
                     "url": r["url"], **a, **(parse_guide(r["text"], pats) or {})})
    g = pd.DataFrame(rows)
    if g.empty:
        return g
    for c in ("guide_pct_low", "guide_pct_high", "guide_low_usdm", "guide_mid_usdm", "guide_high_usdm", "quote",
              "actual_release_usdm", "actual_table_usdm", "actual_quote"):
        if c not in g:
            g[c] = float("nan") if c != "quote" and c != "actual_quote" else ""
    g["parsed"] = (g["guide_pct_low"].notna() | g["guide_mid_usdm"].notna()) & (g["release_date"] < h["guide_release_to"])
    # one row per reported quarter: the earliest filing that reports the quarter's actual (pre-announcements carry none)
    # (an investor presentation filed under Item 2.02 can carry a spurious 'revenues of $3.5 billion' but no guide: guide first)
    g = g.assign(_g=(~g["parsed"]).astype(int), _o=g["actual_release_usdm"].isna().astype(int))
    g = g.sort_values(["reported_quarter", "_g", "_o", "release_date"]).drop_duplicates("reported_quarter", keep="first").drop(columns=["_g", "_o"])
    xa = xq.assign(quarter=xq["quarter"].astype(str)).set_index("quarter")["actual_usdm"]
    g["actual_xbrl_usdm"] = g["reported_quarter"].map(xa)
    g["actual_usdm"] = g["actual_xbrl_usdm"].fillna(g["actual_release_usdm"])
    g["actual_source"] = g["actual_xbrl_usdm"].notna().map({True: "XBRL first reported", False: "release (narrative = table)"})
    # sequential-% guides are converted on the reported quarter's revenue
    pct = g["guide_pct_low"].notna()
    g.loc[pct, "guide_low_usdm"] = g.loc[pct, "actual_usdm"] * (1 + g.loc[pct, "guide_pct_low"] / 100)
    g.loc[pct, "guide_high_usdm"] = g.loc[pct, "actual_usdm"] * (1 + g.loc[pct, "guide_pct_high"] / 100)
    g.loc[pct, "guide_mid_usdm"] = (g.loc[pct, "guide_low_usdm"] + g.loc[pct, "guide_high_usdm"]) / 2
    return g.sort_values("reported_quarter").reset_index(drop=True)


def history_panel(g: pd.DataFrame, breaks: list) -> pd.DataFrame:
    """beat of guided quarter q = actual(q) / guide mid given in the release that reported q-1."""
    act = g.set_index(["company", "reported_quarter"])["actual_usdm"]
    src = g.set_index(["company", "reported_quarter"])["actual_source"]
    br = {(b["company"], b["quarter"]): b["reason"] for b in breaks}
    rows = []
    for r in g[g["parsed"]].itertuples():
        k = (r.company, r.guided_quarter)
        if k not in act.index or pd.isna(act[k]):
            continue
        rows.append({"company": r.company, "quarter": r.guided_quarter, "guide_release": r.release_date, "guide_low_usdm": r.guide_low_usdm,
                     "guide_mid_usdm": r.guide_mid_usdm, "guide_high_usdm": r.guide_high_usdm, "actual_usdm": round(float(act[k]), 2),
                     "beat_pct": round((float(act[k]) / r.guide_mid_usdm - 1) * 100, 2), "actual_source": src[k],
                     "excluded": k in br, "exclusion_reason": br.get(k, ""), "quote": r.quote, "url": r.url})
    return pd.DataFrame(rows)


def build_history(write: bool = True) -> dict:
    cfg = load_cfg()
    h = cfg["history"]
    gs = [company_history(c, spec, cfg) for c, spec in cfg["peers"].items()]
    g = pd.concat([x.dropna(axis=1, how="all") for x in gs if len(x)], ignore_index=True)
    p = history_panel(g, h.get("structural_breaks", []) + cfg.get("structural_breaks", []))
    if write:
        g.to_csv(RAW / "peer_history_releases.csv", index=False)
        p.to_csv(RAW / "peer_history_panel.csv", index=False)
    return {"releases": g, "panel": p}
