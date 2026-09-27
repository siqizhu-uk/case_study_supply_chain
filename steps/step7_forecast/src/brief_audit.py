"""Dashboard: is each answer the brief asks for supported by data, a chart and a prior (reasoning stated before the
regression)? Hand-written verdicts in audit/brief_audit.csv. On every run its {token} placeholders are filled from the
outputs (forecast points and ranges, Nordic's guide-error walk-forward and gross-margin statistics, the lag weeks of
steps 4 and 5) and every evidence path is checked to exist, so a moved or deleted output shows as missing."""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from core.config import OUTPUTS, ROOT, load_config

AUDIT = ROOT / "audit" / "brief_audit.csv"
COL = {"supported": "#2e8b57", "partial": "#d99a00", "weak": "#c0392b"}
TEXT_COLS = ("answer", "data", "prior", "gap")                  # columns whose {token} placeholders are filled
S4, S5, S7 = (ROOT / "steps" / s / "outputs" for s in ("step4_lag_structure", "step5_supply_graph", "step7_forecast"))
NORDIC_RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_quarterly.csv"
AMAZON_ROUTE = ("Amazon direct", "Amazon -> Logitech -> Nordic")   # step 5 MC route name, step 4 route total name


class _Tokens(dict):
    """A token whose source output is missing renders as 'n/a' instead of stopping the dashboard."""
    def __missing__(self, key: str) -> str:
        return "n/a"


def _forecasts() -> dict:
    f = pd.read_csv(OUTPUTS / "forecasts.csv")
    get = lambda prn, m: f[f["print"].str.startswith(prn) & f["metric"].str.contains(m)].iloc[0]   # noqa: E731
    fmt = lambda r, u: f"{r['point']:,g}{u} ({r['low']:,g}-{r['high']:,g})"                           # noqa: E731
    return {"nordic_rev": fmt(get("Nordic", "Revenue"), ""), "nordic_gm": fmt(get("Nordic", "Gross"), "%"),
            "logi_rev": fmt(get("Logitech", "Net sales"), ""), "logi_gm": fmt(get("Logitech", "Gross"), "%"),
            "gn_rev": fmt(get("GN", "Revenue"), ""), "gn_ebita": fmt(get("GN", "EBITA"), "%")}


def _nordic_guide_error() -> dict:
    """Nordic's habit n and the walk-forward RMSE (pts) of the rule used and its pre-registered challengers (step 7e)."""
    gm = pd.read_csv(S7 / "guide_error_model.csv").set_index("company")
    w = pd.read_csv(S7 / "guide_error_walkforward_nordic.csv")
    rmse = lambda c: f"{np.sqrt(((w[c] - w['actual_error']) ** 2).mean()):.2f}"     # noqa: E731
    return {"nordic_n_habit": int(gm.loc["Nordic", "n_not_building"]), "nordic_wf_used": rmse("model"),
            "nordic_wf_prev": rmse("previous_rule"), "nordic_wf_pooled": rmse("pooled_challenger"),
            "nordic_wf_words": rmse("wording_rule"), "nordic_wf_n": len(w)}


def _share(hit: pd.Series) -> str:
    return f"{hit.mean():.0%} ({int(hit.sum())} of {len(hit)})"


def _nordic_gm() -> dict:
    """The GM rule's walk-forward scores, band, channel-excess test (F25) and how often the guided floor was met."""
    g = json.loads((OUTPUTS / "forecast_details.json").read_text())["nordic"]["gm_model"]
    sc, ex = sorted(g["scores"].items(), key=lambda kv: kv[1]), g["excess"]
    q = pd.read_csv(NORDIC_RAW).dropna(subset=["gm_pct", "guide_gm_pct"])
    floor = float(load_config()["forecast"]["nordic_2026Q3"].get("guide_gm_floor", 50.0))
    return {"nordic_gm_n_rules": len(sc), "nordic_gm_best": f"{sc[0][0]} {sc[0][1]:.2f}, then {sc[1][0]} {sc[1][1]:.2f}",
            "nordic_gm_scores": ", ".join(f"{k} {v:.2f}" for k, v in sc),
            "nordic_gm_band": f"{g['low']:.1f}-{g['high']:.1f}", "nordic_gm_n_regime": g["n_regime"], "nordic_gm_sd": f"{g['sd_pts']:.1f}",
            "nordic_gm_excess": (f"delta {ex['delta']:+.2f} pts after an excess quarter (t {ex['t']:.2f}, n {ex['n']} firm-quarters, "
                                 f"{ex['n_quarters']} quarters), Nordic walk-forward RMSE {ex['wf_rmse_with_term']:.2f} with it vs "
                                 f"{ex['wf_rmse_last_quarter']:.2f} without (n {ex['wf_n']})"),
            "nordic_gm_if_excess": f"{ex['gm_if_excess']:.1f}%", "nordic_gm_floor_now": f"{floor:g}%",
            "nordic_gm_floor_own": _share(q["gm_pct"] >= q["guide_gm_pct"]), "nordic_gm_floor_now_met": _share(q["gm_pct"] >= floor)}


def _lag() -> dict:
    """Amazon route: order-signal and physical weeks with the graph Monte Carlo band (step 5), edge means and the
    independent-edges range (step 4)."""
    mc = pd.read_csv(S5 / "graph_signal_lag_mc.csv").set_index(["basis", "route"])
    sig, phys = mc.loc[("signal", AMAZON_ROUTE[0])], mc.loc[("physical", AMAZON_ROUTE[0])]
    t = pd.read_csv(S4 / "edge_lags_total.csv").set_index("route").loc[AMAZON_ROUTE[1]]
    return {"lag_signal": f"{sig['p50']:.0f}", "lag_signal_band": f"{sig['p5']:.0f}-{sig['p95']:.0f}", "lag_physical": f"{phys['p50']:.0f}",
            "lag_edge1": f"{t['edge1_weeks']:.1f}", "lag_edge2": f"{t['edge2_weeks']:.1f}",
            "lag_indep": f"{t['sim_p5_weeks']:.0f}-{t['sim_p95_weeks']:.0f}"}


def _numbers() -> dict:
    out = _Tokens()
    for part in (_forecasts, _nordic_guide_error, _nordic_gm, _lag):
        try:
            out.update(part())
        except (FileNotFoundError, KeyError, IndexError) as e:        # an output not built yet: its tokens show 'n/a'
            out[f"_error_{part.__name__}"] = str(e)
    return out


def audit() -> pd.DataFrame:
    a = pd.read_csv(AUDIT).fillna("")
    nums = _numbers()
    for c in TEXT_COLS:
        a[c] = a[c].map(lambda s: s.format_map(nums))
    a["missing"] = a["evidence"].map(lambda e: "; ".join(p.strip() for p in e.split(";") if p.strip() and not (ROOT / p.strip()).exists()))
    return a


def section_html() -> str:
    a = audit()
    rows = []
    for r in a.itertuples():
        ev = "<br>".join(f"<code>{html.escape(p.strip())}</code>" for p in r.evidence.split(";") if p.strip())
        miss = f"<br><b style='color:#c0392b'>missing: {html.escape(r.missing)}</b>" if r.missing else ""
        rows.append(f"<tr><td><b>{html.escape(r.item)}</b></td><td>{html.escape(r.answer)}</td><td>{html.escape(r.data)}</td>"
                    f"<td>{html.escape(r.plot)}</td><td>{html.escape(r.prior)}</td>"
                    f"<td style='color:{COL.get(r.status, '#333')};font-weight:700'>{r.status}</td>"
                    f"<td>{html.escape(r.gap)}</td><td class=src>{ev}{miss}</td></tr>")
    n = a["status"].value_counts()
    return ("<h2>Brief checklist: is every answer backed by data, a chart and a prior?</h2>"
            f"<p class=note>{int(n.get('supported', 0))} supported, {int(n.get('partial', 0))} partial, {int(n.get('weak', 0))} weak "
            f"(of {len(a)} items the brief asks for). Read from the outputs each run: the forecast points and ranges (outputs/forecasts.csv), "
            "Nordic's guide-error walk-forward and gross-margin statistics (steps/step7_forecast/outputs, outputs/forecast_details.json) and the "
            "Amazon-route lag weeks (steps 4 and 5). Other numbers and every verdict are hand-written in audit/brief_audit.csv; every "
            "evidence path is checked to exist.</p>"
            "<table><tr><th>Brief item</th><th>Answer</th><th>Data</th><th>Chart</th><th>Prior (reasoning before regression)</th>"
            "<th>Verdict</th><th>Gap</th><th>Evidence</th></tr>" + "".join(rows) + "</table>")
