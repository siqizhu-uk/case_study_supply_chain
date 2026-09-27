"""Dashboard tab 'Data & time series': every time series the model has, where it comes from, how reliable it is, and where it is used.

The catalogue (audit/metric_catalogue.csv) is hand-written; coverage, latest value and the sparkline are computed from the
data on every run, so the table cannot drift from what the model actually reads. audit/brief_data_checklist.csv maps each
data item the brief listed to collected / partial / skipped and why.
"""
from __future__ import annotations

import html

import numpy as np
import pandas as pd

from core.config import ROOT, load_config

CAT, CHECK = ROOT / "audit" / "metric_catalogue.csv", ROOT / "audit" / "brief_data_checklist.csv"
FACTORS = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "factors_quarterly.csv"
WEIGHTS, GND = ROOT / "config" / "supply_graph_weights.csv", ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "gn_top_distributor.csv"
ODM = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "odm_monthly_revenue.csv"
PEERS = [ROOT / "pipelines" / "D_peer_panel" / "data" / "raw" / f for f in ("peer_panel.csv", "peer_history_panel.csv")]
TWD_M = 1000                                         # MOPS monthly revenue is in TWD thousands
GRADE_COL = {"A": "#2e8b57", "B": "#4C78A8", "C": "#d99a00", "D": "#888"}


def _q(idx) -> pd.PeriodIndex:
    return pd.PeriodIndex(pd.Index(idx).astype(str), freq="Q")


def series(spec: str, p: pd.DataFrame) -> pd.Series:
    """'panel:col' | 'factors:col' | 'file:<path>:col' (quarter column) | 'weights:col' (per fiscal year) | 'gnd:col' |
    'dio:<company>' (XBRL inventory days) | 'gndio:' | 'logirm:col' | 'peers:col' (median over the peer panel's firms per
    quarter) | 'odm:<code+code>' (ODM monthly revenue, summed; empty = the codes of config logitech_odm_challenger)."""
    kind, _, rest = spec.partition(":")
    if kind == "panel":
        return p[rest].dropna() if rest in p else pd.Series(dtype=float)
    if kind == "factors":
        f = pd.read_csv(FACTORS)
        return pd.Series(f[rest].values, index=_q(f["quarter"])).dropna()
    if kind == "file":
        path, col = rest.rsplit(":", 1)
        f = pd.read_csv(ROOT / path)
        s = pd.Series(f[col].values, index=_q(f["quarter"])).dropna()
        return s[~s.index.duplicated(keep="last")].sort_index()
    if kind == "weights":
        w = pd.read_csv(WEIGHTS)
        return pd.Series(w[rest].values * 100, index=pd.Index(w["fiscal_year"].map(lambda y: f"FY{y}"))).dropna()
    if kind == "dio":
        from supply_graph_report import xbrl_dio
        d = xbrl_dio()
        return pd.Series(d[rest].values, index=_q(d.index)).dropna()
    if kind == "gndio":
        from supply_graph_report import gn_dio
        g = gn_dio()
        return pd.Series(g.values, index=_q(g.index))
    if kind == "logirm":
        from supply_graph_report import logi_stage_weeks
        w = logi_stage_weeks()
        return pd.Series(w[rest].values, index=_q(w.index)).dropna()
    if kind == "gnd":
        g = pd.read_csv(GND)
        return pd.Series(g[rest].values, index=pd.Index(g["year"].astype(str))).dropna()
    if kind == "peers":
        return _peer_median(rest)
    if kind == "odm":
        return _odm_monthly(rest.split("+") if rest else load_config()["logitech_odm_challenger"]["odm_codes"])
    raise ValueError(spec)


def _peer_median(col: str) -> pd.Series:
    """Median over the peer firms of one column per quarter, exclusions dropped (as step 7e reads the panel)."""
    d = pd.concat([pd.read_csv(f) for f in PEERS if f.exists()], ignore_index=True)
    d = d[~d["excluded"].fillna(False).astype(bool)].drop_duplicates(["company", "quarter"])
    m = d.groupby("quarter")[col].median().dropna()
    return pd.Series(m.values, index=_q(m.index)).sort_index()


def _odm_monthly(codes: list) -> pd.Series:
    """Summed monthly revenue of the given ODMs (TWD m), months where every one of them reported."""
    o = pd.read_csv(ODM, dtype={"code": str})
    o = o[o["code"].isin([str(c) for c in codes])].drop_duplicates(["month", "code"], keep="last")
    w = o.pivot(index="month", columns="code", values="revenue").dropna()
    return (w.sum(axis=1) / TWD_M).sort_index()


def sparkline(s: pd.Series, w: int = 120, h: int = 26) -> str:
    v = s.astype(float).values
    if len(v) < 2:
        return ""
    lo, hi = np.nanmin(v), np.nanmax(v)
    rng = hi - lo or 1.0
    xs = np.linspace(2, w - 2, len(v))
    ys = h - 3 - (v - lo) / rng * (h - 6)
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
    zero = f'<line x1="0" x2="{w}" y1="{h - 3 - (0 - lo) / rng * (h - 6):.1f}" y2="{h - 3 - (0 - lo) / rng * (h - 6):.1f}" stroke="#ddd"/>' if lo < 0 < hi else ""
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}">{zero}<polyline points="{pts}" fill="none" stroke="#4C78A8" stroke-width="1.3"/>'
            f'<circle cx="{xs[-1]:.1f}" cy="{ys[-1]:.1f}" r="2" fill="#4C78A8"/></svg>')


def catalogue(p: pd.DataFrame) -> pd.DataFrame:
    c = pd.read_csv(CAT).fillna("")
    rows = []
    for r in c.itertuples():
        try:
            s = series(r.series, p)
        except (FileNotFoundError, KeyError, ValueError):
            s = pd.Series(dtype=float)
        rows.append({**r._asdict(), "n": len(s), "first": str(s.index[0]) if len(s) else "", "last": str(s.index[-1]) if len(s) else "",
                     "latest": float(s.iloc[-1]) if len(s) else np.nan, "spark": sparkline(s), "_series": s})
    return pd.DataFrame(rows).drop(columns="Index")


def write_catalogue(cat: pd.DataFrame, out) -> None:
    cat.drop(columns=["spark", "_series"]).round(2).to_csv(out, index=False)


def tab_html(cat: pd.DataFrame) -> str:
    chk = pd.read_csv(CHECK).fillna("")
    st = {"collected": "#2e8b57", "partial": "#d99a00", "skipped": "#c0392b", "live gauge": "#4C78A8"}
    ck = "".join(f"<tr><td>{html.escape(r.brief_item)}</td><td style='color:{st.get(r.status, '#333')};font-weight:600'>{r.status}</td>"
                 f"<td><code>{html.escape(r.where)}</code></td><td>{html.escape(r.why)}</td></tr>" for r in chk.itertuples())
    body = []
    for tier, g in cat.groupby("tier", sort=True):
        body.append(f"<tr><th colspan=8 style='background:#eef2f7'>{html.escape(tier)}</th></tr>")
        for r in g.itertuples():
            latest = "" if pd.isna(r.latest) else f"{r.latest:,.1f}"
            body.append(f"<tr><td><b>{html.escape(r.label)}</b><br><span class=src><code>{r.metric}</code> · {html.escape(r.kind)} · {html.escape(r.unit)}</span></td>"
                        f"<td>{r.spark}</td><td>{latest}</td><td>{r.first}–{r.last}<br><span class=src>{r.n} obs</span></td>"
                        f"<td style='color:{GRADE_COL.get(r.grade, '#333')};font-weight:700;text-align:center'>{r.grade}</td>"
                        f"<td>{html.escape(r.brief_item)}</td><td>{html.escape(r.used_in)}</td><td class=src>{html.escape(r.note)}</td></tr>")
    flow = ROOT / "docs" / "data_flow.svg"
    flow_html = (f"<h2>How the data flow</h2>{flow.read_text()}" if flow.exists() else "")
    return (flow_html + f"<h2>Every series behind the six forecasts and the six answers</h2><p class=note>{len(cat)} series, each feeding a "
            "forecast, a cross-check or the evidence of an answer (the 'Used in' column says which); series that fed none of them are not listed. "
            "Coverage, latest value and the sparkline are computed from the data on every run. Grade: A filed statements (audited annual / "
            "reviewed quarterly), B unaudited company disclosure, C verbal / proxy, D derived estimate. Full table: outputs/metric_catalogue.csv; "
            "source list: audit/metric_catalogue.csv.</p>"
            "<table><tr><th>Metric</th><th>Trend</th><th>Latest</th><th>Coverage</th><th>Grade</th><th>Brief item</th><th>Used in</th><th>Note</th></tr>"
            + "".join(body) + "</table>"
            "<h2>The brief's data list: what was collected, what was skipped</h2>"
            f"<table><tr><th>Brief item</th><th>Status</th><th>Where</th><th>Why</th></tr>{ck}</table>")
