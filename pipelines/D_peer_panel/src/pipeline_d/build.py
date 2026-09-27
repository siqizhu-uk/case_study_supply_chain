"""Peer panel: for every company and quarter, the revenue guide given one quarter earlier, the actual (SEC XBRL), the
beat vs the guide midpoint, and (NXP) channel-inventory weeks. Every guide keeps its sentence; every check is recorded.

Quarter mapping: a release reports the latest XBRL quarter that ended before its filing date (<= 75 days earlier) and
guides the next one. 52/53-week fiscal closes map to calendar quarters with the Pipeline A rule (end date - 15 days).
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .releases import ROOT, RAW, PROC, load_cfg, earnings_releases
from .parse import parse_guide, parse_backward, parse_channel_weeks

sys.path.insert(0, str(ROOT / "pipelines" / "A_company_financials" / "src"))
from pipeline_a.sec import fetch_companyfacts, _facts  # noqa: E402
from pipeline_a.inventory_detail import fiscal_to_calendar_quarter  # noqa: E402

REV_TAGS = ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"]


def xbrl_quarters(cik: int) -> pd.DataFrame:
    """Quarterly revenue as first reported, with period end dates (Q4 = FY - 9M), USD m."""
    f = _facts(fetch_companyfacts(cik), REV_TAGS)
    f = f.dropna(subset=["start"]).copy()
    f["days"] = (f["end"] - f["start"]).dt.days
    # FIRST-reported values (point in time): the guide targeted the company as it was then; later filings restate
    # comparatives for divestitures / discontinued operations (e.g. Silicon Labs after selling I&A to Skyworks in 2021)
    q = f[f["days"].between(80, 100)].sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
    a = f[f["days"].between(350, 380)].sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
    rows = {e: v for e, v in zip(q["end"], q["val"])}
    for _, r in a.iterrows():
        inside = q[(q["end"] > r["start"]) & (q["end"] < r["end"])]
        if len(inside) == 3:
            rows[r["end"]] = r["val"] - inside["val"].sum()
    out = pd.DataFrame({"period_end": list(rows), "actual_usdm": [v / 1e6 for v in rows.values()]}).sort_values("period_end")
    out["quarter"] = out["period_end"].map(fiscal_to_calendar_quarter)
    return out.drop_duplicates("quarter", keep="last").reset_index(drop=True)


def xbrl_balance(cik: int) -> pd.DataFrame:
    """First-reported quarterly inventory (instant) and cost of sales (duration, Q4 = FY - 9M), USD m, by calendar quarter."""
    facts = fetch_companyfacts(cik)
    inv = _facts(facts, ["InventoryNet"])
    inv = inv[inv["start"].isna()] if "start" in inv else inv
    inv = inv.sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
    iv = pd.Series({fiscal_to_calendar_quarter(e): v / 1e6 for e, v in zip(inv["end"], inv["val"])})
    f = _facts(facts, ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"]).dropna(subset=["start"]).copy()
    f["days"] = (f["end"] - f["start"]).dt.days
    q = f[f["days"].between(80, 100)].sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
    a = f[f["days"].between(350, 380)].sort_values(["end", "filed"]).drop_duplicates("end", keep="first")
    rows = {e: v for e, v in zip(q["end"], q["val"])}
    for _, r in a.iterrows():
        inside = q[(q["end"] > r["start"]) & (q["end"] < r["end"])]
        if len(inside) == 3:
            rows[r["end"]] = r["val"] - inside["val"].sum()
    cg = pd.Series({fiscal_to_calendar_quarter(e): v / 1e6 for e, v in rows.items()})
    out = pd.DataFrame({"inventory_usdm": iv, "cogs_usdm": cg}).sort_index()
    out.index = out.index.astype(str)
    return out


def _fix_unit(v: float | None, ref: float, ratio: float) -> tuple[float | None, str]:
    """A value 100x+ off the company's own revenue is a unit typo in the filing ('$1,240 billion'): rescale by 1000, flag it."""
    if v is None or pd.isna(v) or not ref:
        return v, ""
    if v / ref > ratio:
        return v / 1000, "unit typo in filing corrected (/1000)"
    if v / ref < 1 / ratio:
        return v * 1000, "unit typo in filing corrected (x1000)"
    return v, ""


def company_rows(company: str, spec: dict, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rel = earnings_releases(company, spec["cik"], cfg["first_release_date"])
    xq = xbrl_quarters(spec["cik"])
    ref = float(xq["actual_usdm"].median())
    rows, ch = [], []
    for r in rel:
        d = pd.Timestamp(r["date"])
        prior = xq[(xq["period_end"] < d) & (xq["period_end"] >= d - pd.Timedelta(days=75))]
        if prior.empty:
            continue
        rep_q = prior.iloc[-1]["quarter"]
        rep_rev = float(prior.iloc[-1]["actual_usdm"])
        lo_r, hi_r = cfg["plausible_guide_ratio"]
        g = parse_guide(r["text"], spec["patterns"], plausible=lambda mid: lo_r * rep_rev <= mid <= hi_r * rep_rev) or {}
        b = parse_backward(r["text"], spec.get("backward")) or {}
        if g.get("pattern_kind") == "pct_seq":        # 'up 4-8% sequentially' -> USD on the reported quarter's revenue
            base_rev = float(prior.iloc[-1]["actual_usdm"])
            g = {**g, "guide_low_usdm": base_rev * (1 + g["guide_pct_low"] / 100), "guide_high_usdm": base_rev * (1 + g["guide_pct_high"] / 100)}
            g["guide_mid_usdm"] = (g["guide_low_usdm"] + g["guide_high_usdm"]) / 2
        rec = {"company": company, "release_date": r["date"], "reported_quarter": str(rep_q), "guided_quarter": str(rep_q + 1),
               "url": r["url"], **g, **b}
        flags = []
        for k in ("guide_low_usdm", "guide_mid_usdm", "guide_high_usdm", "backward_mid_usdm"):
            if k in rec:
                rec[k], fl = _fix_unit(rec[k], ref, cfg["unit_typo_ratio"])
                if fl:
                    flags.append(f"{k}: {fl}")
        rec["flags"] = "; ".join(flags)
        rec["parsed"] = "guide_mid_usdm" in rec
        rows.append(rec)
        c = parse_channel_weeks(r["text"], spec.get("channel_weeks"))
        if c:
            ch.append({"company": company, "release_date": r["date"], "quarter": str(rep_q), "url": r["url"], **c})
    g = pd.DataFrame(rows)
    # Several Item 2.02 filings can map to one reported quarter: pre-announcements (no guide) and, at TI until ~2013,
    # MID-QUARTER outlook updates (half the quarter already seen). The benchmark is the INITIAL guide: keep the earliest
    # filing that carries a guide; a quarter without any parsed guide keeps its (unparsed) row for the coverage report.
    g = g.assign(_order=(~g["parsed"]).astype(int)).sort_values(["reported_quarter", "_order", "release_date"])
    g = g.drop_duplicates("reported_quarter", keep="first").drop(columns="_order")
    return g, pd.DataFrame(ch), xq


def panel(guides: pd.DataFrame, actuals: dict[str, pd.DataFrame], sanity: float, breaks: list | None = None,
          overrides_list: list | None = None) -> pd.DataFrame:
    """`overrides_list`: quarters where the release's comparable figure replaces GAAP revenue (quote checked in validate)."""
    overrides = {(o["company"], o["quarter"]): o for o in (overrides_list or [])}
    rows = []
    for c, g in guides.groupby("company"):
        xq = actuals[c].set_index(actuals[c]["quarter"].astype(str))
        for _, r in g[g["parsed"]].iterrows():
            q = r["guided_quarter"]
            if q not in xq.index:
                continue
            act = float(overrides.get((c, q), {}).get("actual_usdm", xq.loc[q, "actual_usdm"]))
            beat = (act / r["guide_mid_usdm"] - 1) * 100
            rows.append({"company": c, "quarter": q, "guide_release": r["release_date"], "guide_low_usdm": r["guide_low_usdm"],
                         "guide_mid_usdm": r["guide_mid_usdm"], "guide_high_usdm": r["guide_high_usdm"], "actual_usdm": round(act, 1),
                         "beat_pct": round(beat, 2), "above_high": act > r["guide_high_usdm"], "below_low": act < r["guide_low_usdm"],
                         "manual_check": abs(beat) > sanity, "flags": r["flags"], "quote": r["quote"], "url": r["url"],
                         "actual_source": "release (override)" if (c, q) in overrides else "XBRL first reported"})
    out = pd.DataFrame(rows).sort_values(["company", "quarter"]).reset_index(drop=True)
    br = {(b["company"], b["quarter"]): b["reason"] for b in (breaks or [])}
    out["excluded"] = [(c, q) in br for c, q in zip(out["company"], out["quarter"])]
    out["exclusion_reason"] = [br.get((c, q), "") for c, q in zip(out["company"], out["quarter"])]
    return out


def build(write: bool = True) -> dict:
    cfg = load_cfg()
    gs, chs, acts = [], [], {}
    for c, spec in cfg["peers"].items():
        g, ch, xq = company_rows(c, spec, cfg)
        gs.append(g); chs.append(ch); acts[c] = xq
    guides = pd.concat(gs, ignore_index=True)
    channel = pd.concat([c for c in chs if len(c)], ignore_index=True) if any(len(c) for c in chs) else pd.DataFrame()
    pnl = panel(guides, acts, cfg["sanity_abs_beat_pct"], cfg.get("structural_breaks"), cfg.get("actual_overrides"))
    bal = pd.concat([xbrl_balance(spec["cik"]).assign(company=c) for c, spec in cfg["peers"].items()])
    bal.index.name = "quarter"
    bal = bal.reset_index()
    if write:
        RAW.mkdir(parents=True, exist_ok=True)
        guides.drop(columns=[c for c in ("backward_quote",) if c not in guides]).to_csv(RAW / "peer_guidance.csv", index=False)
        channel.to_csv(RAW / "peer_channel_weeks.csv", index=False)
        pd.concat([a.assign(company=c) for c, a in acts.items()]).to_csv(RAW / "peer_actuals_xbrl.csv", index=False)
        PROC.mkdir(parents=True, exist_ok=True)
        pnl.to_csv(RAW / "peer_panel.csv", index=False)          # model input: committed like Pipeline A's extracts
        bal.to_csv(RAW / "peer_balance_xbrl.csv", index=False)
    return {"overrides": cfg.get("actual_overrides"), "balance": bal, "guides": guides, "channel": channel, "actuals": acts, "panel": pnl, "verified_outliers": cfg.get("verified_outliers")}
