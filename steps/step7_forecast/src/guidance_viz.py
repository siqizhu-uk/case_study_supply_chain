"""Dashboard charts for the guidance track record (inline SVG, native hover tooltips on every mark).

1. Nordic: each quarter's guide range (grey bar, as % of its midpoint) and the actual (dot), channel regimes shaded
   behind - conservative in normal quarters, missed in the destock.
2. Small multiples, one panel per fiscal year: every guide statement as a vertical range at the month it was given
   (x = months before the year ends), coloured by action (raised / lowered / initial or reaffirmed), and the outcome as
   a dashed line - the staircase shows how far the first guide was from the outcome and which way it was revised.
   Logitech sales and non-GAAP operating income as growth vs the prior year (constant currency to FY23, USD from FY24);
   GN organic growth and EBITA margin as stated (scope in each tooltip).
Colours: polarity (above / below the midpoint) = blue / orange; actions = blue raised, orange lowered, grey otherwise;
text in ink, never in series colour.
"""
from __future__ import annotations

import html

import numpy as np
import pandas as pd

from guidance_record import (GN_HIST, LOGI_HIST, MIN_MONTHS_AHEAD, gn_headline, logitech_annual, nordic_quarters, period_end)

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
UP, DOWN, NEUTRAL = "#2a78d6", "#eb6834", "#8a8984"
REGIME_FILL = {"supply_constrained": "#f3f1ea", "destock": "#fbece6", "normal": "#eaf2fb"}
ACTION_COL = {"raised": UP, "lowered": DOWN}


def _t(s: str) -> str:
    return html.escape(str(s), quote=True)


# ------------------------------------------------------------------ 1. Nordic quarterly
def nordic_svg(p: pd.DataFrame, w: int = 1100, h: int = 270) -> str:
    d = nordic_quarters(p).dropna(subset=["revenue_usdm"])
    n = len(d)
    L, R, T, B = 48, 12, 34, 34
    lo_y, hi_y = -15.0, 10.0
    x = lambda i: L + (i + 0.5) * (w - L - R) / n                         # noqa: E731
    y = lambda v: T + (hi_y - np.clip(v, lo_y, hi_y)) / (hi_y - lo_y) * (h - T - B)   # noqa: E731
    bw = (w - L - R) / n
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Nordic actual revenue vs quarterly guide range" style="font:11px -apple-system,Segoe UI,Helvetica,Arial,sans-serif">']
    # regime bands with the regime's median error
    reg = d["regime"].fillna("")
    i = 0
    while i < n:
        j = i
        while j + 1 < n and reg.iloc[j + 1] == reg.iloc[i]:
            j += 1
        med = d["error_pct"].iloc[i:j + 1].median()
        out.append(f'<rect x="{x(i) - bw / 2:.1f}" y="{T}" width="{(j - i + 1) * bw:.1f}" height="{h - T - B}" fill="{REGIME_FILL.get(reg.iloc[i], "#fff")}"/>')
        out.append(f'<text x="{(x(i) + x(j)) / 2:.1f}" y="{T - 8}" text-anchor="middle" fill="{INK}">{_t(reg.iloc[i].replace("_", "-"))}: median {med:+.1f}%</text>')
        i = j + 1
    for v in (-15, -10, -5, 0, 5, 10):
        out.append(f'<line x1="{L}" x2="{w - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{INK if v == 0 else GRID}" stroke-width="{1 if v == 0 else .7}"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end" fill="{MUTED}">{v:+d}%</text>')
    for k, (q, r) in enumerate(d.iterrows()):
        glo, ghi = (r["guide_low_usdm"] / r["mid"] - 1) * 100, (r["guide_high_usdm"] / r["mid"] - 1) * 100
        e = r["error_pct"]
        col = UP if e >= 0 else DOWN
        tip = (f"{q}: guide USD {r['guide_low_usdm']:g}-{r['guide_high_usdm']:g}m, actual {r['revenue_usdm']:g}m "
               f"({e:+.1f}% vs midpoint; {'inside' if r['in_range'] else 'outside'} the range)")
        out.append(f'<g><title>{_t(tip)}</title><rect x="{x(k) - bw / 2:.1f}" y="{T}" width="{bw:.1f}" height="{h - T - B}" fill="transparent"/>'
                   f'<rect x="{x(k) - 5:.1f}" y="{y(ghi):.1f}" width="10" height="{y(glo) - y(ghi):.1f}" rx="2" fill="{NEUTRAL}" opacity=".45"/>'
                   f'<circle cx="{x(k):.1f}" cy="{y(e):.1f}" r="5" fill="{col}" stroke="#fff" stroke-width="2"/></g>')
        if k % 2 == 0 or k == n - 1:
            out.append(f'<text x="{x(k):.1f}" y="{h - B + 16}" text-anchor="middle" fill="{MUTED}">{q}</text>')
    out.append("</svg>")
    return "".join(out)


# ------------------------------------------------------------------ 2. annual small multiples
def _panel(title: str, stmts: pd.DataFrame, actual: float | None, unit: str, pw: int = 178, ph: int = 190,
           perimeter: tuple[float, str] | None = None) -> str:
    """stmts: months_before_end, low, high, action, tip. x runs 12 -> 0 months before the period end. `perimeter`
    (months before the end, tooltip) marks a change of reporting perimeter: statements either side are not comparable."""
    L, R, T, B = 36, 8, 22, 26
    vals = list(stmts["low"]) + list(stmts["high"]) + ([actual] if actual is not None and pd.notna(actual) else [])
    lo, hi = min(vals), max(vals)
    pad = max((hi - lo) * 0.12, 1.0)
    lo, hi = lo - pad, hi + pad
    x = lambda m: L + (12 - np.clip(m, 0, 12)) / 12 * (pw - L - R)     # noqa: E731
    y = lambda v: T + (hi - v) / (hi - lo) * (ph - T - B)               # noqa: E731
    o = [f'<svg viewBox="0 0 {pw} {ph}" width="{pw}" height="{ph}" style="font:10px -apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
         f'<text x="{L}" y="13" fill="{INK}" font-weight="600">{_t(title)}</text>']
    ticks = np.linspace(lo + pad, hi - pad, 3) if hi - lo > 2 * pad else [lo, hi]
    for v in ticks:
        o.append(f'<line x1="{L}" x2="{pw - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{GRID}" stroke-width=".7"/>'
                 f'<text x="{L - 4}" y="{y(v) + 3:.1f}" text-anchor="end" fill="{MUTED}">{v:.0f}{unit}</text>')
    if lo < 0 < hi:
        o.append(f'<line x1="{L}" x2="{pw - R}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="{MUTED}" stroke-width=".8"/>')
    for m in (12, 6, 0):
        o.append(f'<text x="{x(m):.1f}" y="{ph - B + 13}" text-anchor="middle" fill="{MUTED}">{m}m</text>')
    if perimeter is not None:
        px = x(perimeter[0]) - 5
        o.append(f'<g><title>{_t(perimeter[1])}</title><line x1="{px:.1f}" x2="{px:.1f}" y1="{T}" y2="{ph - B}" stroke="{MUTED}" '
                 f'stroke-width="1.2" stroke-dasharray="2 2"/><text x="{px + 2:.1f}" y="{ph - B - 3}" fill="{MUTED}">perimeter</text></g>')
    if actual is not None and pd.notna(actual):
        o.append(f'<g><title>{_t(f"outcome {actual:.1f}{unit}")}</title><line x1="{L}" x2="{pw - R}" y1="{y(actual):.1f}" y2="{y(actual):.1f}" '
                 f'stroke="{INK}" stroke-width="2" stroke-dasharray="5 3"/></g>'
                 f'<text x="{L + 2}" y="{y(actual) + (12 if y(actual) < T + 14 else -4):.1f}" fill="{INK}">actual {actual:+.0f}{unit}</text>')
    for r in stmts.itertuples():
        col = ACTION_COL.get(r.action, NEUTRAL)
        cx = x(r.months)
        top, bot = y(r.high), y(r.low)
        if bot - top < 4:
            top, bot = top - 2, bot + 2
        o.append(f'<g><title>{_t(r.tip)}</title><rect x="{cx - 7:.1f}" y="{top - 4:.1f}" width="14" height="{bot - top + 8:.1f}" fill="transparent"/>'
                 f'<rect x="{cx - 3:.1f}" y="{top:.1f}" width="6" height="{bot - top:.1f}" rx="3" fill="{col}"/></g>')
    o.append("</svg>")
    return "".join(o)


def _logitech_growth() -> pd.DataFrame:
    """Every Logitech annual statement and outcome as growth vs the prior fiscal year (%)."""
    h = pd.read_csv(LOGI_HIST)
    h = h[h["period"].str.startswith("FY")].copy()
    act = h[h["action"] == "actual"].set_index(["period", "metric"])["low"]
    prior = lambda period, metric: act.get((f"FY{int(period[2:]) - 1}", metric), np.nan)   # noqa: E731
    rows = []
    for r in h[h["low"].notna()].itertuples():
        if r.metric == "sales_growth_cc_pct":
            lo, hi, kind = r.low, r.high, "sales"
        else:
            base = prior(r.period, r.metric)
            if pd.isna(base):
                continue
            lo, hi = (r.low / base - 1) * 100, (r.high / base - 1) * 100
            kind = "sales" if r.metric == "sales_usdm" else "op_income"
        rows.append({"period": r.period, "kind": kind, "action": r.action, "low": lo, "high": hi, "date": r.statement_date,
                     "months": (period_end(r.period) - pd.Timestamp(r.statement_date)).days / 30.44,
                     "tip": f"{r.statement_date} {r.action}: {r.low:g}-{r.high:g} ({r.metric}) - \"{r.quote}\""})
    return pd.DataFrame(rows)


def logitech_html() -> str:
    if not LOGI_HIST.exists():
        return ""
    g = _logitech_growth()
    ann = logitech_annual().set_index("period")
    keep = sorted(p for p in ann.index.unique() if bool(ann.loc[[p], "initial"].any()) and p.startswith("FY"))
    rows = []
    for kind, label in (("sales", "Sales growth"), ("op_income", "Non-GAAP operating income growth")):
        panels = []
        for per in keep:
            s = g[(g["period"] == per) & (g["kind"] == kind)]
            a = s[s["action"] == "actual"]
            st = s[s["action"] != "actual"]
            if st.empty:
                continue
            panels.append(_panel(f"{per} {'sales' if kind == 'sales' else 'op. income'}", st, float(a["low"].iloc[0]) if len(a) else None, "%"))
        rows.append(f"<div style='margin:4px 0 2px;font-size:12px;color:{MUTED}'>{label} vs the prior year (%): each bar = one statement, placed by months before year end</div>"
                    f"<div style='display:flex;flex-wrap:wrap;gap:4px'>{''.join(panels)}</div>")
    return "".join(rows)


def _gn_perimeter(raw: pd.DataFrame, fy: int, metric: str) -> tuple[float, str] | None:
    """The first continuing-operations statement of a year (GN guided the group until the Hearing sale): where the
    staircase changes perimeter, so the step there is a basis change, not a revision."""
    c = raw[(raw["fiscal_year"] == fy) & (raw["metric"] == metric) & (raw["scope"] == "continuing_ops")].sort_values("statement_date")
    if c.empty:
        return None
    d = c["statement_date"].iloc[0]
    return ((period_end(fy) - pd.Timestamp(d)).days / 30.44,
            f"{d}: perimeter changes from the group (incl. Hearing) to continuing operations; statements before and after are not comparable")


def gn_html() -> str:
    if not GN_HIST.exists():
        return ""
    raw = pd.read_csv(GN_HIST)
    h = gn_headline(raw)
    out = []
    for metric, label in (("organic_growth_pct", "Organic growth (%)"), ("ebita_margin_pct", "EBITA margin (%)")):
        panels = []
        for fy, g in h[h["metric"] == metric].groupby("fiscal_year"):
            st = g[(g["action"] != "actual") & g["low"].notna()].copy()
            if st.empty:
                continue
            st["months"] = [(period_end(fy) - pd.Timestamp(d)).days / 30.44 for d in st["statement_date"]]
            st["tip"] = [f"{r.statement_date} {r.action} ({r.scope}): {r.low:g}-{r.high:g} - {r.note if isinstance(r.note, str) else ''} - \"{r.quote}\""
                         for r in st.itertuples()]
            a = g[g["action"] == "actual"]
            per = _gn_perimeter(raw, fy, metric)
            scope = "Audio div." if st["scope"].iloc[0] == "audio" else ("group → cont. ops" if per else "group")
            panels.append(_panel(f"{int(fy)} {scope}", st, float(a["low"].iloc[-1]) if len(a) else None, "%", perimeter=per))
        out.append(f"<div style='margin:4px 0 2px;font-size:12px;color:{MUTED}'>GN {label}: Audio division until GN guided the group (2023 / 2024); "
                   f"2026 = continuing operations from May (Hearing sold)</div><div style='display:flex;flex-wrap:wrap;gap:4px'>{''.join(panels)}</div>")
    return "".join(out)


def legend() -> str:
    sw = lambda c, t: f"<span style='display:inline-flex;align-items:center;gap:5px;margin-right:14px'><span style='width:10px;height:10px;border-radius:3px;background:{c};display:inline-block'></span>{t}</span>"   # noqa: E731
    return (f"<div style='font-size:12px;color:{INK};margin:6px 0'>{sw(UP, 'actual above the midpoint / guide raised')}"
            f"{sw(DOWN, 'actual below the midpoint / guide lowered')}{sw(NEUTRAL, 'guide range / initial or reaffirmed')}"
            f"<span style='margin-right:14px'>– – actual outcome</span>hover any mark for the date, range and the company's words</div>")


def charts_html(p: pd.DataFrame) -> str:
    return (legend() + f"<h3 style='font-size:14px;margin:10px 0 2px'>Nordic: actual vs each quarter's guide (as % of the guide midpoint)</h3>{nordic_svg(p)}"
            f"<h3 style='font-size:14px;margin:12px 0 2px'>Logitech: how the annual outlook moved within each year</h3>{logitech_html()}"
            + (f"<h3 style='font-size:14px;margin:12px 0 2px'>GN: how the annual guidance moved within each year</h3>{gn_html()}" if GN_HIST.exists() else "")
            + f"<p class=src>Only guides given ≥ {MIN_MONTHS_AHEAD} months before the period end count as initial guides in the table; later ones are shown but not scored.</p>")
