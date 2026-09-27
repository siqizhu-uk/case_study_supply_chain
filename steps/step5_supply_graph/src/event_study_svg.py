"""Step 5d drawing: the supplier incident travelling back through the chain (one row per node, x = calendar weeks summed
into quarters, bars = USD m change on a per-row scale), the lag between rows as arrows between the rows' time centroids,
and the Nordic guided-quarter waterfall (step 7c gross -> re-timed by stock -> already in the guide -> net). Also the
dashboard section (Audit tab)."""
from __future__ import annotations

import html
import re

import pandas as pd

from core.config import step_outputs
from event_study_report import ROWS

W, X0, X1, TOP, ROW_H, HALF = 900, 215, 885, 78, 128, 36
RED, AMBER, GREEN, INK, MUTED, GRID = "#B5534B", "#BA7517", "#3B8C5A", "#222", "#666", "#DDD"
NODE_ROWS = [("customers", "Amazon + Ingram + TD Synnex", "sell-in from Logitech"), ("logitech", "Logitech", "sales"),
             ("build", "Build / component call-off", "ODM kit, Suzhou (at sales value)"), ("nordic", "Nordic", "shipments to the Logitech slice")]
STACK = [("nordic_cut", RED, "orders pushed out / cancelled"), ("nordic_stock", AMBER, "stock at the holder used first"),
         ("nordic_restock", GREEN, "channel restock (upside)")]


def _t(x, y, s, size=11, fill=INK, anchor="start", weight="normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">'
            f'{html.escape(str(s))}</text>')


def _geom(res: dict) -> dict:
    x = res["inputs"]
    shown = [q for q in x["quarters"] if str(q) in res["table"].columns]
    wa, wz = (shown[0] - x["q0"]).n * x["wq"], ((shown[-1] - x["q0"]).n + 1) * x["wq"]
    return {"shown": [str(q) for q in shown], "wa": wa, "px": (X1 - X0) / (wz - wa), "wq": x["wq"]}


def _xw(g: dict, week: float) -> float:
    return X0 + (week - g["wa"]) * g["px"]


def _row_values(res: dict, key: str, g: dict) -> pd.Series:
    t = res["table"]
    return t.loc[t["row"] == next(lab for _, k, lab, _ in ROWS if k == key), g["shown"]].iloc[0]


def _peak(res: dict, key: str, g: dict) -> float:
    return float(_row_values(res, key, g).abs().max())


def _axis(g: dict, H: int) -> list[str]:
    out = []
    for i, q in enumerate(g["shown"]):
        xa = X0 + i * g["wq"] * g["px"]
        out += [f'<line x1="{xa:.1f}" y1="{TOP - 16}" x2="{xa:.1f}" y2="{H}" stroke="{GRID}"/>',
                _t(xa + g["wq"] * g["px"] / 2, TOP - 22, q, 12, INK, "middle", "600")]
    return out


def _bars(res: dict, g: dict, i: int, key: str, scale_max: float) -> list[str]:
    yc = TOP + i * ROW_H + ROW_H / 2
    out = [f'<line x1="{X0}" y1="{yc}" x2="{X1}" y2="{yc}" stroke="#999" stroke-width="0.8"/>']
    parts = STACK if key == "nordic" else [(key, RED, "")]
    bw = g["wq"] * g["px"] * 0.46
    for j, q in enumerate(g["shown"]):
        xc = X0 + (j + 0.5) * g["wq"] * g["px"]
        neg, pos = 0.0, 0.0
        for k, col, _ in parts:
            v = float(_row_values(res, k, g)[q])
            h = abs(v) / scale_max * HALF
            y = yc + neg if v < 0 else yc - pos - h
            neg, pos = (neg + h, pos) if v < 0 else (neg, pos + h)
            out += [f'<rect x="{xc - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{col}" fill-opacity="0.85"/>'] if h > 0.2 else []
        tot = float(_row_values(res, "nordic" if key == "nordic" else key, g)[q])
        out += [_t(xc, yc + neg + 12 if tot < 0 else yc - pos - 4, f"{tot:+.1f}", 10.5, INK, "middle")] if abs(tot) >= 0.05 else []
    return out


def _band(res: dict, g: dict, i: int, scale_max: float) -> list[str]:
    yc, bd, out = TOP + i * ROW_H + ROW_H / 2, res["band"], []
    for j, q in enumerate(g["shown"]):
        xb = X0 + (j + 0.5) * g["wq"] * g["px"] + g["wq"] * g["px"] * 0.30
        lo, hi = (yc - v / scale_max * HALF for v in (bd.loc[q, "band_low"], bd.loc[q, "band_high"]))
        if abs(hi - lo) > 0.5:
            out.append(f'<path d="M{xb - 4:.1f} {lo:.1f}H{xb + 4:.1f}M{xb:.1f} {lo:.1f}V{hi:.1f}M{xb - 4:.1f} {hi:.1f}H{xb + 4:.1f}" stroke="{INK}" fill="none" stroke-width="1"/>')
        for s, col, dy in (("downside", RED, 1), ("upside", GREEN, -1)):
            yv = yc - bd.loc[q, s] / scale_max * HALF
            if abs(bd.loc[q, s]) >= 0.05:
                out.append(f'<path d="M{xb + 8:.1f} {yv:.1f}l6 {-4 * dy}l0 {8 * dy}z" fill="{col}"/>')
    return out


def _arrows(res: dict, g: dict) -> list[str]:
    s, c = res["summary"], res["summary"]["centroids"]
    xs = [c["logitech"], c["logitech"], c["build"], c["nordic"]]
    labels = [f"same invoice (0 wk); a ~{s['customer_cover_weeks']:.0f}-wk channel cover keeps sell-out going",
              f"build -> sale {s['build_weeks']:.1f} wk (ODM E08, in-house E05)",
              f"Nordic ship -> build {s['ship_to_build_weeks']:.1f} wk (E01-E03); lead {s['lead_weeks']:.1f} wk in all"]
    out = []
    for i in range(3):
        y1, y2 = TOP + i * ROW_H + ROW_H / 2 + HALF + 18, TOP + (i + 1) * ROW_H + ROW_H / 2 - HALF - 6
        xa, xb = _xw(g, xs[i]), _xw(g, xs[i + 1])
        out += [f'<path d="M{xa:.1f} {y1:.1f}L{xb:.1f} {y2:.1f}" stroke="#185FA5" stroke-width="1.6" fill="none" marker-end="url(#esah)"/>',
                _t(min(xa, xb) - 10, (y1 + y2) / 2 + 4, labels[i], 10.5, "#185FA5", "end") if i == 0 else
                _t(max(xa, xb) + 10, (y1 + y2) / 2 + 4, labels[i], 10.5, "#185FA5")]
    return out


def _markers(res: dict, g: dict) -> list[str]:
    r, x, s = res["run"], res["inputs"], res["summary"]
    guide_w = r["w0"] + (pd.Timestamp(res["as_of"]) - pd.Timestamp(s["incident"])).days / 7
    yb, ln = TOP + 4 * ROW_H, TOP + 3 * ROW_H + ROW_H / 2          # bottom of the rows; Nordic's zero line
    lg = TOP + ROW_H + ROW_H / 2                                      # Logitech's zero line
    items = [(r["w0"], TOP - 12, yb, TOP - 2, f"incident {s['incident']:%d %b}", INK, "5 3", 1),
             (guide_w, ln - HALF - 10, yb, ln + HALF + 22, f"Nordic guides {pd.Timestamp(res['as_of']):%d %b}", MUTED, "2 3", -1),
             (r["wR"], lg - HALF - 10, lg + HALF + 10, lg - HALF - 14, "Logitech sales back to normal", GREEN, "5 3", 1),
             (r["wR"] - s["lead_weeks"], ln - HALF - 10, yb, ln + HALF + 22, "chips for those sales ship", GREEN, "2 3", 1)]
    out = []
    for w, ya, yz, yt, lab, col, dash, side in items:
        xv = _xw(g, w)
        out += [f'<line x1="{xv:.1f}" y1="{ya}" x2="{xv:.1f}" y2="{yz}" stroke="{col}" stroke-dasharray="{dash}"/>',
                _t(xv + 3 * side, yt, lab, 9.5, col, "start" if side > 0 else "end")]
    return out


def _waterfall(res: dict, y0: float) -> list[str]:
    s = res["summary"]
    steps = [("step 7c gross|(lead mapped back)", s["chain_gross_q"], True), ("re-timed by stock|and orders", s["event_q"] - s["chain_gross_q"], False),
             ("= event-study|gross", s["event_q"], True), (f"already in the {pd.Timestamp(res['as_of']):%d %b}|guide ({s['share_in_guide']:.0%}, grade D)", -s["in_guide"], False),
             ("= net vs|the guide", s["net_q"], True)]
    m = max(abs(s["event_q"]), abs(s["chain_gross_q"]), 1e-9)
    k, zero, bw, gap = 95 / m, y0 + 26, 70, 118
    out = [_t(20, y0 + 6, f"Nordic {s['tq']}, USD m (the guided quarter)", 12, INK, "start", "600"),
           f'<line x1="20" y1="{zero}" x2="{20 + gap * 5}" y2="{zero}" stroke="#999"/>']
    level = 0.0
    for i, (lab, v, is_total) in enumerate(steps):
        a, b = (0.0, v) if is_total else (level, level + v)
        level = b
        ytop, h = zero - max(a, b) * k, abs(b - a) * k
        col = "#4C78A8" if is_total else (AMBER if v < 0 else GREEN)
        xa = 30 + i * gap
        out += [f'<rect x="{xa}" y="{ytop:.1f}" width="{bw}" height="{max(h, 0.8):.1f}" fill="{col}" fill-opacity="0.85"/>',
                _t(xa + bw / 2, ytop + h + 13, f"{v:+.1f}", 11, INK, "middle"), _t(xa + bw / 2, zero + 120, lab.split("|")[0], 10, MUTED, "middle"),
                _t(xa + bw / 2, zero + 133, lab.split("|")[1], 10, MUTED, "middle")]
    return out


def _recovery_note(res: dict, y0: float) -> list[str]:
    s = res["summary"]
    lines = [f"{s['tq1']} (one quarter past the guide): {s['event_q1']:+.1f}m mid",
             f"band {s['band_q1'][0]:+.1f} to {s['band_q1'][1]:+.1f} (lags, frozen window, content)",
             f"downside {s['scen_q1']['downside']:+.1f} (restart a quarter later)",
             f"upside {s['scen_q1']['upside']:+.1f} (channel refills its cover)",
             f"stock at holders {-s['stock_total']:.1f}m = up to {s['stock']['weeks'].max():.1f} wk of use:",
             "Nordic orders resume after it is used"]
    return [_t(640, y0 + 6, "Recovery", 12, INK, "start", "600")] + [_t(640, y0 + 26 + 17 * i, l, 10.5, INK) for i, l in enumerate(lines)]


def render(res: dict) -> str:
    g = _geom(res)
    H = int(TOP + 4 * ROW_H + 270)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Helvetica,Arial" font-size="12">',
           '<defs><marker id="esah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#185FA5" stroke-width="1.5"/></marker></defs>',
           f'<rect width="{W}" height="{H}" fill="#fff"/>',
           _t(12, 20, "Logitech's 2026 supplier incident pushed back through the chain: USD m change vs no incident, by calendar quarter", 13, INK, "start", "600"),
           _t(12, 37, f"Each row has its own scale (Logitech's ${_peak(res, 'logitech', g):.0f}m vs Nordic's ${_peak(res, 'nordic', g):.1f}m at the peak); "
              "blue arrows join the rows' time centres: the lead between nodes.", 10.5, MUTED)] + _axis(g, TOP + 4 * ROW_H)
    for i, (key, name, sub) in enumerate(NODE_ROWS):
        vals = [abs(float(v)) for v in _row_values(res, key, g)]
        extra = [abs(float(v)) for v in res["band"].loc[g["shown"]].to_numpy().ravel()] if key == "nordic" else []
        sm = max(vals + extra + [1e-9])
        yc = TOP + i * ROW_H + ROW_H / 2
        out += [_t(12, yc - 12, name, 12, INK, "start", "600"), _t(12, yc + 3, sub, 10.5, MUTED), _t(12, yc + 18, f"row scale: half-height = ${sm:.1f}m", 10, MUTED)]
        out += _bars(res, g, i, key, sm) + (_band(res, g, i, sm) if key == "nordic" else [])
    out += _arrows(res, g) + _markers(res, g)
    ly = TOP + 4 * ROW_H + 8
    out += [f'<rect x="{X0 + 150 * j}" y="{ly}" width="10" height="10" fill="{c}"/>' + _t(X0 + 150 * j + 14, ly + 9, lab, 10) for j, (_, c, lab) in enumerate(STACK)]
    out += [_t(X0, ly + 25, "I = band over edge lags x frozen window x Nordic content;  triangles: red = downside (restart a quarter later), green = upside (restock)", 10, MUTED)]
    out += _waterfall(res, TOP + 4 * ROW_H + 56) + _recovery_note(res, TOP + 4 * ROW_H + 56) + ["</svg>"]
    return "".join(out)


def dashboard_section() -> str:
    """Audit tab: the event study SVG and the structural-breaks-through-the-chain table (step 5d, G23)."""
    d = step_outputs("step5_supply_graph")
    svg, tab, brk = (d / f for f in ("event_study_supplier_incident.svg", "event_study_supplier_incident.csv", "structural_breaks_chain.csv"))
    if not svg.exists():
        return ""
    b = pd.read_csv(brk).fillna("") if brk.exists() else pd.DataFrame()
    t = pd.read_csv(tab).round(2).fillna("") if tab.exists() else pd.DataFrame()
    cols = [c for c in ("event", "dates", "shock_or_break", "graph_element", "buffer", "nordic_revenue_consequence", "handled_in_model", "ids") if c in b]
    years = re.findall(r"(?:19|20)\d\d", " ".join(b["dates"].astype(str))) if "dates" in b else []
    since = f"since {min(years)}" if years else "in the data"
    return ("<h2>Structural breaks through the chain: shocks vs breaks (step 5d)</h2>"
            "<p class=note>A <b>shock</b> leaves every edge as it is and the graph carries it; a <b>break</b> changes an edge (lag, share, amplitude) "
            "or the reporting basis. Worked example: Logitech's 2026 supplier incident pushed back node by node (per-row scale).</p>"
            f"<div style='max-width:900px'>{svg.read_text()}</div>"
            f"<details><summary><b>Propagation table</b> — USD m by node and quarter</summary>{t.to_html(index=False, border=0)}</details>"
            f"<details><summary><b>Every break and shock {since}</b> — element changed, buffer, consequence for Nordic, handling</summary>"
            f"{b[cols].to_html(index=False, border=0) if len(b) else ''}</details>"
            "<p class=src>steps/step5_supply_graph/outputs/event_study_supplier_incident.csv, structural_breaks_chain.csv; "
            "assumptions config/model.yaml event_study (grades in comments).</p>")
