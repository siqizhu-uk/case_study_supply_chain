"""Every independent check beside each of the six forecasts, in one table (step 7, decision F28).

A forecast is more credible when methods that do not share its inputs land near it. For each print the table lists the
point and its band, then every cross-check the model already computes - other methods, pre-registered challengers,
bridges and one-input scenarios - with its value, whether it falls inside the point's band, and the decision it tests.
Nothing here moves a forecast; the table is read from outputs/forecast_details.json, outputs/scenarios.csv and
steps/step7_forecast/outputs/chain_terms.csv, written to steps/step7_forecast/outputs/cross_checks.csv.

kind:  guide        the company's own guide (a floor is shown, not compared to the band)
       method       an independent way to the same number (different inputs)
       challenger   a pre-registered alternative model, scored after the print
       scenario     one input of the point's own model moved
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from core.config import OUTPUTS, ROOT

CHAIN = ROOT / "steps" / "step7_forecast" / "outputs" / "chain_terms.csv"
# Pre-registered challengers of the guided quarter: (log, print, metric, label, value column, challenger name or None when
# the log holds one model). The last row logged for the target before the print is the challenger's forecast of record.
S6_OUT, S7_OUT = ROOT / "steps" / "step6_backtest" / "outputs", ROOT / "steps" / "step7_forecast" / "outputs"
PREREG = [
    (S6_OUT / "composite_prereg_log.csv", "Nordic Q3 2026", "Revenue (USDm)",
     "channel composite (step 6c, pre-registered)", "revenue_hat_usdm", None),
    (S6_OUT / "composite_graph_prereg_log.csv", "Nordic Q3 2026", "Revenue (USDm)",
     "composite with the supply-graph factor (step 6c-g, pre-registered)", "revenue_hat_usdm", None),
    (S7_OUT / "challenger_prereg_log.csv", "Nordic Q3 2026", "Revenue (USDm)",
     "Nordic's own words as the channel state (D25, F31, pre-registered challenger)", "challenger_usdm",
     "D25 own record with Nordic's own words as the state"),
    (S7_OUT / "logitech_odm_prereg_log.csv", "Logitech Q2 FY27", "Net sales (USDm)",
     "supply-side ODM nowcast, Merry + Chicony (step 7f, F28, pre-registered)", "revenue_hat_usdm", None),
]
TARGET = "2026Q3"
OUT = ROOT / "steps" / "step7_forecast" / "outputs" / "cross_checks.csv"


def _row(print_, metric, point, lo, hi, check, kind, value, tests, source):
    inside = None if value is None or (isinstance(value, float) and np.isnan(value)) else bool(lo <= value <= hi)
    return {"print": print_, "metric": metric, "point": point, "low": lo, "high": hi, "check": check, "kind": kind,
            "value": None if value is None else round(float(value), 1), "gap_vs_point": None if value is None else round(float(value) - point, 1),
            "inside_band": inside, "tests": tests, "source": source}


def build() -> pd.DataFrame:
    d = json.loads((OUTPUTS / "forecast_details.json").read_text())
    sc = pd.read_csv(OUTPUTS / "scenarios.csv") if (OUTPUTS / "scenarios.csv").exists() else pd.DataFrame(columns=["print", "scenario", "point"])
    ch = pd.read_csv(CHAIN) if CHAIN.exists() else pd.DataFrame(columns=["print", "term", "value"])
    rows = []
    n, l, g = d["nordic"], d["logitech"], d["gn"]

    def chain_value(print_, contains):
        m = ch[(ch["print"] == print_) & ch["term"].str.contains(contains, regex=False)]
        if not len(m):
            return None
        v = str(m["value"].iloc[0]).split("/")[0].strip()
        try:
            return float(v)
        except ValueError:
            return None

    # Nordic revenue
    P, M, pt, lo, hi = "Nordic Q3 2026", "Revenue (USDm)", n["point"], n["low"], n["high"]
    rows.append(_row(P, M, pt, lo, hi, "distributed-lag regression on Logitech (consumer only, no guide)", "method",
                     (n.get("regression_crosscheck") or {}).get("implied_total_usdm_at_avg_mix"), "Lag", "step 6 regression.json"))
    rows.append(_row(P, M, pt, lo, hi, "chain as reasoned, nothing fitted (CH)", "method", chain_value(P, "CH (as reasoned"), "Lag + Mechanism + Attribution", "chain_terms.csv"))
    s3 = n.get("step3_channel_call") or {}
    if s3:
        rows.append(_row(P, M, pt, lo, hi, "point + step 3 channel call (mid)", "method", pt - float(n["signal_adjustments"].get("capacity_worry_pull_in", 0) or 0) + float(s3["adj_mid"]),
                         "Mechanism", "step 3 channel_call.csv"))
    for _, r in sc[sc["print"] == P].iterrows():
        if r["scenario"] == "base":
            continue
        kind = "challenger" if "challenger" in r["scenario"] else "scenario"
        rows.append(_row(P, M, pt, lo, hi, r["scenario"], kind, r["point"], r.get("decision", ""), "scenarios.csv"))
    # Nordic GM
    gm = n["gm_model"]
    P2, M2 = "Nordic Q3 2026", "Gross margin (%)"
    for k, v in gm["scores"].items():
        rows.append(_row(P2, M2, n["gm_point"], gm["low"], gm["high"], f"rule '{k}' (walk-forward RMSE {v:.2f} pts)", "method",
                         (gm.get("rule_points") or {}).get(k), "Model limitations", "margin_model.py"))
    rows.append(_row(P2, M2, n["gm_point"], gm["low"], gm["high"], "channel-excess term applied (F25, not adopted)", "challenger", gm["excess"]["gm_if_excess"], "Mechanism", "margin_excess.py"))
    floor = float(str(gm.get("guide", ">50")).lstrip(">").rstrip("%"))
    side = "above" if n["gm_point"] >= floor else "below"
    r = _row(P2, M2, n["gm_point"], gm["low"], gm["high"], f"company guide: a floor of {floor:g}% (the point is {side} it)", "guide", floor, "guide", "Nordic Q2 report")
    r["inside_band"] = None                                        # a floor is not a point: the check is 'point above the floor'
    rows.append(r)
    # Logitech revenue
    P, M, pt, lo, hi = "Logitech Q2 FY27", "Net sales (USDm)", l["point"], l["low"], l["high"]
    rows.append(_row(P, M, pt, lo, hi, "company guide midpoint", "guide", l["guide_mid"], "guide", "Q1 FY27 release"))
    w = chain_value(P, "weight on the chain")
    rows.append(_row(P, M, pt, lo, hi, f"tier identity: sell-in = sell-through (chain forecast, weight {w if w is not None else 'n/a'} in the point)",
                     "method", chain_value(P, "chain forecast (USDm)"), "Mechanism", "chain_terms.csv"))
    fxc = l.get("fx_check") or {}
    if fxc:
        rows.append(_row(P, M, pt, lo, hi, "post-guide FX term applied (F27; not applied: fails walk-forward)", "challenger", pt + fxc["term_usdm"], "FX rule", "fx_update.py"))
    for _, r in sc[sc["print"] == P].iterrows():
        if r["scenario"] != "base":
            rows.append(_row(P, M, pt, lo, hi, r["scenario"], "scenario", r["point"], r.get("decision", ""), "scenarios.csv"))
    # Logitech GM
    lg = l["gm_model"]
    P2, M2 = "Logitech Q2 FY27", "Gross margin non-GAAP (%)"
    rows.append(_row(P2, M2, l["gm_point"], lg["low"], lg["high"], "company guide on the call", "guide",
                     float(str(lg.get("guide", "")).lstrip("~").rstrip("%")) if lg.get("guide") else None, "guide", "Q1 FY27 call"))
    for k, v in (lg.get("scores") or {}).items():
        rows.append(_row(P2, M2, l["gm_point"], lg["low"], lg["high"], f"rule '{k}' (walk-forward RMSE {v:.2f} pts)", "method",
                         (lg.get("rule_points") or {}).get(k), "Model limitations", "margin_model.py"))
    # GN revenue
    P, M, pt, lo, hi = "GN cont. ops Q3 2026", "Revenue (DKKm)", g["point"], g["low"], g["high"]
    rows.append(_row(P, M, pt, lo, hi, "division view (management's Enterprise / Gaming organic)", "method", g["division_view"]["point"], "Mechanism", "forecast.py"))
    for k, v in ((g.get("guidance_anchor") or {}).get("q3_if") or {}).items():
        rows.append(_row(P, M, pt, lo, hi, f"bias: {k}", "scenario", v, "Structural breaks / Model limitations", "guidance_record"))
    fxd = g.get("fx_update") or {}
    if fxd:
        base_fx = 1 + fxd["term_pts"] / 100
        rows.append(_row(P, M, pt, lo, hi, "old hand-typed FX -1.5 pts (superseded, F27)", "scenario", pt / base_fx * (1 - 0.015), "FX rule", "fx_update.py"))
    # GN EBITA
    P2, M2 = "GN cont. ops Q3 2026", "Adj. EBITA margin (%)"
    lo2, hi2 = g["ebita_adj_margin_range"]
    rows.append(_row(P2, M2, g["ebita_adj_margin_point"], lo2, hi2, "Q2 bridge (drop-through + savings + refund)", "method", g["ebita_bridge_margin_pct"], "Mechanism", "forecast.py"))
    rows.append(_row(P2, M2, g["ebita_adj_margin_point"], lo2, hi2, "ex tariff refund", "scenario", g["ebita_margin_ex_tariff_refund"], "one-off rule", "forecast.py"))
    for _, r in sc[sc["print"].str.contains("EBITA")].iterrows():
        if not str(r["scenario"]).startswith("point"):
            rows.append(_row(P2, M2, g["ebita_adj_margin_point"], lo2, hi2, r["scenario"], "scenario", r["point"], r.get("decision", ""), "scenarios.csv"))
    return pd.DataFrame(rows + prereg_rows(rows))


def prereg_rows(rows: list[dict]) -> list[dict]:
    """The forecast of record of each pre-registered challenger (PREREG), unless a challenger row with the same value is
    already there for that print (the scenarios table carries some of them)."""
    by_print, seen = {}, set()
    for r in rows:
        by_print.setdefault((r["print"], r["metric"]), (r["point"], r["low"], r["high"]))
        if r["kind"] == "challenger" and r["value"] is not None:
            seen.add((r["print"], r["metric"], r["value"]))
    out = []
    for path, print_, metric, label, col, name in PREREG:
        if not path.exists() or (print_, metric) not in by_print:
            continue
        log = pd.read_csv(path)
        log = log[(log["target"].astype(str) == TARGET) & ((log["challenger"] == name) if name else True)]
        if not len(log):
            continue
        pt_, lo_, hi_ = by_print[(print_, metric)]
        r = _row(print_, metric, pt_, lo_, hi_, label, "challenger", float(log[col].iloc[-1]), "pre-registered: scored after the print",
                 str(path.relative_to(ROOT)))
        if (print_, metric, r["value"]) not in seen:
            out.append(r)
    return out


def summary(t: pd.DataFrame) -> pd.DataFrame:
    """Per forecast: how many checks, how many carry a number, how many land inside the band (superseded rules left out),
    the widest gap."""
    num = t[t["inside_band"].notna() & ~t["check"].astype(str).str.contains("superseded")]
    num = num.assign(inside=lambda x: x["inside_band"].astype(bool).astype(int))
    g = num.groupby(["print", "metric"])
    return pd.DataFrame({"checks": t.groupby(["print", "metric"]).size(), "compared": g.size(), "inside_band": g["inside"].sum(),
                         "widest_gap": g["gap_vs_point"].apply(lambda s: s.loc[s.abs().idxmax()])}).reset_index()


def write() -> pd.DataFrame:
    t = build()
    t.to_csv(OUT, index=False)
    summary(t).to_csv(OUT.with_name("cross_checks_summary.csv"), index=False)
    return t
