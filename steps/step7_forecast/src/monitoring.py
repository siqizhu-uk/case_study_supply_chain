"""Monitoring plan (dashboard tab Monitor): each item ties a data release to a conclusion of the note, with a trigger that
would change it. audit/monitoring_plan.csv is hand-written; the 'latest' column is computed from the data on every run,
every forecast number in a trigger or conclusion is a {TOKEN} filled from outputs/forecasts.csv and
forecast_details.json, and every threshold is a {TOKEN} read from config/model.yaml, so the plan cannot quote a
superseded forecast or a rule the model no longer uses."""
from __future__ import annotations

import html

import pandas as pd

from core.config import OUTPUTS, ROOT, load_config, step_outputs

PLAN = ROOT / "audit" / "monitoring_plan.csv"


def _latest(key: str, p: pd.DataFrame) -> str:
    def last(col, fmt="{:+.1f}", unit=""):
        s = p[col].dropna() if col in p else pd.Series(dtype=float)
        return f"{fmt.format(s.iloc[-1])}{unit} ({s.index[-1]})" if len(s) else "—"
    if key in ("nordic_dist_state",):
        return last(key, "{:+.1f}", " coded")
    if key in ("nordic_inv_days",):
        return last(key, "{:.0f}", " days")
    if key in ("logi_st_gap", "gn_enterprise_org", "logi_emea_yoy"):
        return last(key, "{:+.1f}", " pts" if key == "logi_st_gap" else "%")
    if key == "mchp_disti_days":
        f = pd.read_csv(ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "mchp_distributor_days.csv")
        return f"{f['disti_days'].iloc[-1]:.0f} days ({f['quarter'].iloc[-1]})"
    if key == "comp_dist_dio":
        from supply_graph_report import xbrl_dio
        d = xbrl_dio()
        return "; ".join(f"{c.title()} {d[c].dropna().iloc[-1]:.0f} d ({d[c].dropna().index[-1]})" for c in ("arrow", "avnet"))
    if key == "dist_days":
        return f"Ingram {last('ingm_inv_days', '{:.0f}', ' d')}; TD Synnex {last('snx_inv_days', '{:.0f}', ' d')}"
    if key == "gauge":
        from live_gauge import readings
        r = readings()
        cur = r[r["snapshot_date"] == r["snapshot_date"].max()]
        return "; ".join(f"{x.part.split('-')[0]} {x.stock:,.0f}" for x in cur.itertuples()) + f" ({r['snapshot_date'].max()})"
    return "—"


def forecast_tokens() -> dict[str, str]:
    """{NORDIC_REV}, {NORDIC_REV_RANGE}, ... from the current forecasts."""
    import json
    fc = pd.read_csv(OUTPUTS / "forecasts.csv").set_index(["print", "metric"])
    keys = {"NORDIC_REV": ("Nordic", "Revenue", 0), "NORDIC_GM": ("Nordic", "Gross margin", 1),
            "LOGI_REV": ("Logitech", "Net sales", 0), "LOGI_GM": ("Logitech", "Gross margin", 1),
            "GN_REV": ("GN", "Revenue", 0), "GN_EBITA": ("GN", "Adj. EBITA", 1)}
    tok = {}
    for name, (co, metric, d) in keys.items():
        r = fc[[i[0].startswith(co) and i[1].startswith(metric) for i in fc.index]].iloc[0]
        f = f"{{:.{d}f}}"
        tok[name] = f.format(r["point"])
        tok[name + "_RANGE"] = f"{f.format(r['low'])}-{f.format(r['high'])}"
    det = json.loads((OUTPUTS / "forecast_details.json").read_text())
    tok["GN_EBITA_EX_REFUND"] = f"{det['gn'].get('ebita_margin_ex_tariff_refund', float('nan')):.1f}"
    inc = det["nordic"].get("signal_adjustments", {}).get("logitech_supplier_incident (graph)")
    tok["INCIDENT_NORDIC_Q3"] = "n/a" if inc is None else f"{abs(inc):.1f}"
    return {**tok, **rule_tokens()}


def rule_tokens() -> dict[str, str]:
    """Thresholds the plan quotes, from config/model.yaml, and Nordic's own state effects (guide-error model, F20/F30)."""
    cfg = load_config()
    cs, dr = cfg["cycle_state"], cfg["dashboard_rules"]
    gem = ROOT / "steps" / "step7_forecast" / "outputs" / "guide_error_model.csv"
    nordic = pd.read_csv(gem).set_index("company").loc["Nordic"] if gem.exists() else {}
    effect = lambda k: "n/a" if k not in nordic or pd.isna(nordic[k]) else f"{nordic[k]:+.1f}"  # noqa: E731
    return {"SHORTAGE_LEAD_WEEKS": f"{cs['shortage']['lead_time_min_weeks']:g}",
            "BUILDING_DAYS": f"{cs['building_min_change_days']:g}", "STATE_QUARTERS": f"{cs['change_quarters']:g}",
            "NORDIC_INV_DAYS_AMBER": f"{dr['nordic_inv_days_amber_above']:g}",
            "DIST_DAYS_CHANGE": f"{dr['distributor_inv_days_amber_change']:g}",
            "NORDIC_BUILDING_EFFECT": effect("own_building_effect"), "NORDIC_SHORTAGE_EFFECT": effect("own_shortage_effect")}


def fill(text: str, tok: dict[str, str]) -> str:
    return text.format(**tok) if "{" in text else text


def plan_html(p: pd.DataFrame) -> str:
    if not PLAN.exists():
        return ""
    m = pd.read_csv(PLAN).fillna("")
    tok = forecast_tokens()
    for c in ("trigger", "conclusion_tested", "action_if_triggered"):
        m[c] = m[c].map(lambda t: fill(t, tok))
    rows = "".join(
        f"<tr><td>{r.id}</td><td><b>{html.escape(r.watch)}</b><br><span class=src>{html.escape(r.source)}</span></td><td>{html.escape(r.next_reading)}</td>"
        f"<td>{html.escape(_latest(r.reading_key, p))}</td><td>{html.escape(r.trigger)}</td><td>{html.escape(r.conclusion_tested)}</td>"
        f"<td>{html.escape(r.action_if_triggered)}</td></tr>" for r in m.itertuples())
    return ("<h2>Monitoring plan: what would change the final calls</h2>"
            "<table><tr><th>#</th><th>Watch</th><th>Next reading</th><th>Latest</th><th>Trigger</th><th>Conclusion it tests</th><th>If triggered</th></tr>"
            f"{rows}</table><p class=src>Dates marked ~ are expected, not announced. Source list: audit/monitoring_plan.csv.</p>")
