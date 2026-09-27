"""Step 5, decision G20: how much of Logitech's unnamed 10-K residual goes through smaller distributors (p).

The 10-K names Amazon, Ingram Micro and TD Synnex; the other ~56% of gross sales is spread over customers each below 10%
and is not split by type. The graph cannot add an entity for 'other distributors' (the entity list is fixed), so the
residual edge E14 (logitech -> other_retail) carries a mixed lag:
    lag_E14 = (1 - p) x direct-retail lag + p x the Ingram / TD Synnex downstream lag
p = config supply_graph.params.logi_residual_via_dist. This module checks every quote behind p against its saved document
(ledger fallback on a fresh clone), shows the reasoning for the range and what p does to the graph's lag.
"""
from __future__ import annotations

import html
import re

import numpy as np
import pandas as pd

from core import verify_ledger as ledger
from core.config import ROOT
from supply_graph import effective_ranges, edge_shares, load_edges, mix_lags, paths

EVIDENCE = ROOT / "steps" / "step5_supply_graph" / "config" / "logi_residual_evidence.csv"
LOGI = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "logitech_quarterly.csv"
PARAM = "logi_residual_via_dist"
EDGE = "E14"                                          # logitech -> other_retail: the residual edge that carries the mixed lag
REGIONS, TWO_TIER = ("americas_usdm", "emea_usdm", "apac_usdm"), ("emea_usdm", "apac_usdm")
YEAR_Q = 4


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'")).strip().lower()


def check_quotes() -> pd.DataFrame:
    """Each quote searched in its document; when the document is not cached, the recorded result is shown."""
    ev = pd.read_csv(EVIDENCE, dtype=str).fillna("")
    status = []
    for r in ev.itertuples():
        f = ROOT / r.document
        if f.exists():
            found = _norm(r.quote) in _norm(f.read_text(errors="ignore"))
            status.append(ledger.record("step5_residual_quote", r.id, "found" if found else "NOT found"))
        else:
            rec = ledger.recall("step5_residual_quote", r.id)
            status.append(rec[0] if rec else "document not cached, never checked")
    ledger.save()
    return ev.assign(quote_check=status)


def lag_by_p(cfg: dict, date, grid=(0.0, None, None, None, 1.0)) -> pd.DataFrame:
    """Flow-weighted mean lag (weeks, mid lags) and E14's lag for p = 0, the configured low / mid / high, and 1."""
    prm = cfg["supply_graph"]["params"][PARAM]
    raw = load_edges()
    base = effective_ranges(raw.drop(columns="lag_mix"), cfg)[0].assign(lag_mix=raw["lag_mix"])
    _, params = effective_ranges(raw, cfg)
    shares = edge_shares(raw, cfg, date)
    labels = ["0 (old setting: residual all direct retail)", f"low {prm['low']}", f"mid {prm['mid']}", f"high {prm['high']}", "1 (residual all distributors)"]
    values = [grid[0], prm["low"], prm["mid"], prm["high"], grid[-1]]
    rows = []
    for lab, p in zip(labels, values):
        e = mix_lags(base, {**params, PARAM: {"low": p, "mid": p, "high": p}})
        pt = paths(e, shares, cfg)
        rows.append({"p": lab, f"{EDGE}_lag_weeks": float(pd.to_numeric(e.loc[e["edge_id"] == EDGE, "lag_weeks_mid"]).iloc[0]),
                     "graph_mean_lag_weeks": float(np.average(pt["lag_weeks"], weights=pt["weight"]))})
    return pd.DataFrame(rows)


def mixed_lag_line(lp: pd.DataFrame, prm: dict, direct: tuple) -> str:
    """E14's lag as the graph uses it, for tooltips and tables: its mid lag at each configured p (rows 'low / mid / high'
    of lag_by_p or graph_residual_lag_by_p.csv) and the direct-retail range (low, mid, high) it is mixed from."""
    at = lp.set_index(lp["p"].astype(str).str.split().str[0])[f"{EDGE}_lag_weeks"]
    lo, mid, hi = direct
    return (f"lag: {at['mid']:.3g} weeks at p = {prm['mid']} ({at['low']:.3g} at p = {prm['low']}, {at['high']:.3g} at p = {prm['high']}; "
            f"mid lags), p-mixed (G20): (1 − p) × direct retail {lo}-{hi} (mid {mid}) + p × the Ingram / TD Synnex route; "
            "p = share of the unnamed 10-K residual sold through smaller distributors")


def lag_lines(edges: pd.DataFrame, o: dict) -> dict:
    """{edge_id: lag text} for the edge whose lag the graph mixes (E14), for the supply-graph tooltip."""
    r = edges[edges["edge_id"] == EDGE]
    if r.empty:
        return {}
    r = r.iloc[0]
    return {EDGE: mixed_lag_line(o["lag_by_p"], o["param"], (r["lag_weeks_low"], r["lag_weeks_mid"], r["lag_weeks_high"]))}


def two_tier_share() -> tuple[float, str, str]:
    """EMEA + APAC share of Logitech sales over the last four reported quarters (%), first and last quarter."""
    d = pd.read_csv(LOGI).dropna(subset=list(REGIONS)).tail(YEAR_Q)
    return float(d[list(TWO_TIER)].sum().sum() / d[list(REGIONS)].sum().sum() * 100), d["quarter"].iloc[0], d["quarter"].iloc[-1]


def run(cfg: dict, date) -> dict:
    return {"evidence": check_quotes(), "lag_by_p": lag_by_p(cfg, date), "param": cfg["supply_graph"]["params"][PARAM]}


def _range_lines(prm: dict) -> list[str]:
    share, q0, q1 = two_tier_share()
    return [
        f"- **Floor {prm['low']} (conditional, from C-grade evidence):** B2B is about 40% of revenue (R8) while Ingram + TD Synnex are 26% of "
        "gross sales (R1). Even if all of the 26% were B2B, at least 14 of the 56 residual points are B2B, and the 10-K says B2B demand "
        "reaches Logitech mainly through distributors (R4): p >= 14 / 56 = 0.25. Condition: that residual B2B goes through distributors, "
        "not direct to resellers such as CDW or Insight (R6).",
        f"- **Cap {prm['high']} (judgment):** the 10-K sells directly to major retail chains with significant shelf space (R5; Best Buy, "
        "Walmart, Target, MediaMarkt named in R7), plus Logitech.com and direct resellers, so the residual cannot be nearly all distribution.",
        f"- **Mid {prm['mid']} (judgment):** rough split of the 56%: direct retail chains ~15-24%, Logitech.com ~2-4%, direct resellers ~3-6%, "
        "other distributors (D&H, ALSO / Actebis, Esprinet, Exertis, Copaco, Daiwabo, Digital China: R7) the rest, ~22-36%, i.e. p ~0.4-0.65. "
        f"EMEA and Asia-Pacific ({share:.0f}% of Logitech's sales over {q0}-{q1}) lean on two-tier distribution; the Americas lean on "
        "direct big-box retail.",
        "- **Not found:** no filing (SEC full-text search 2001-2026), cached call transcript or reachable conference transcript gives a "
        "distributor share of sales. The May 2025 and March 2026 conference transcripts on s1.q4cdn.com return 403.",
        f"- **Grade D.** The value is not public. The project rule for D would be 0-1; the floor rests on the R8 arithmetic and the cap on R5 / R7, "
        "both stated here, so the range is narrower than the rule by design."]


def section(o: dict) -> str:
    ev, lp, prm = o["evidence"], o["lag_by_p"], o["param"]
    show = ev[["id", "source", "grade", "quote", "implies", "used_for", "quote_check"]]
    return "\n".join([
        "## Logitech's unnamed 10-K residual: how much goes through distributors? (G20)\n",
        "The 10-K names Amazon (18%), Ingram Micro (14%) and TD Synnex (12%) of gross sales; the other 56% is not split by customer type. "
        "Treating it all as direct retail (the old setting, p = 0) made the graph's lag too short (P80). The graph has no entity for "
        "'other distributors', so the residual edge E14 carries a mixed lag: (1 − p) × direct-retail lag + p × the Ingram / TD Synnex "
        f"downstream lag. p = `supply_graph.params.{PARAM}` = {prm['low']} / {prm['mid']} / {prm['high']}.\n",
        "**Evidence** (each quote checked against its saved document; `config/logi_residual_evidence.csv`):\n",
        show.to_markdown(index=False), "",
        "**How the range is set:**\n", *_range_lines(prm), "",
        "**What p does to the lag** (mid lags, weeks):\n", lp.round(2).to_markdown(index=False), "",
        f"p moves the graph's mean lag by {lp['graph_mean_lag_weeks'].iloc[-1] - lp['graph_mean_lag_weeks'].iloc[0]:.1f} weeks from 0 to 1 and by "
        f"{lp['graph_mean_lag_weeks'].iloc[3] - lp['graph_mean_lag_weeks'].iloc[1]:.1f} across the configured range: the correction matters for "
        "honesty about the route (p = 0 is ruled out by R2 / R7), not for the forecasts (h = 2 is insensitive to sub-quarter lags, P74).\n"])


def html_box(o: dict, heading: bool = False) -> str:
    """Evidence, range reasoning and lag effect of p. The dashboard wraps it in a <details> whose summary names it, so the
    heading is off by default; the p values and grade then open the first paragraph."""
    ev, lp, prm = o["evidence"], o["lag_by_p"], o["param"]
    col = {"A": "#2e8b57", "B": "#4C78A8", "C": "#d99a00", "D": "#888"}
    rows = "".join(f"<tr><td>{r.id}</td><td>{html.escape(r.source)}</td><td style='color:{col.get(r.grade, '#333')};font-weight:700'>{r.grade}</td>"
                   f"<td><i>“{html.escape(r.quote)}”</i></td><td>{html.escape(r.implies)}</td><td>{html.escape(r.quote_check)}</td></tr>"
                   for r in ev.itertuples())
    lag = "".join(f"<tr><td>{html.escape(str(p))}</td><td>{e:.1f}</td><td>{g:.1f}</td></tr>"
                  for p, e, g in zip(lp["p"], lp[f"{EDGE}_lag_weeks"], lp["graph_mean_lag_weeks"]))
    reason = "".join(f"<li>{html.escape(x[2:]).replace('**', '')}</li>" for x in _range_lines(prm))
    p_txt = f"p = {prm['low']} / {prm['mid']} / {prm['high']} (grade D, G20)"
    head = (f"<h3 style='font-size:14px'>Logitech's unnamed 56%: share through smaller distributors {p_txt}</h3><p class=note>" if heading
            else f"<p class=note>Share of the unnamed 56% sold through smaller distributors: {p_txt}. ")
    return (head + f"The 10-K names Amazon, Ingram and TD Synnex; the rest is not split. Edge {EDGE} carries a mixed lag: (1 − p) × direct retail + "
            "p × the distributor route. The old setting p = 0 is ruled out by the evidence below.</p>"
            f"<ul class=note>{reason}</ul>"
            "<table><tr><th>id</th><th>Source</th><th>Grade</th><th>Quote</th><th>What it implies</th><th>Quote check</th></tr>" + rows + "</table>"
            f"<table style='width:auto'><tr><th>p</th><th>{EDGE} lag (wk)</th><th>Graph mean lag (wk)</th></tr>" + lag + "</table>")
