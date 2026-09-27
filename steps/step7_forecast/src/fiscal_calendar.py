"""Dashboard (Data tab): how every company's fiscal quarter lines up with the calendar quarter of the three prints
(Jul-Sep 2026), and when each report lands. Facts in config/fiscal_calendar.csv. Every source table that stores a period
end (or a fiscal label) next to its calendar quarter is checked row by row against the majority rule (the calendar quarter
holding most of the period's days = period end - 45 days), so a quarter filed wrongly in the data shows as a red cell. Since
P124 the code maps with that same rule, so comparing the code's mapping with the rule could not fail and is not shown.
"""
from __future__ import annotations

import html
import re
import sys

import pandas as pd

from core.config import ROOT

TABLE = ROOT / "config" / "fiscal_calendar.csv"
sys.path.insert(0, str(ROOT / "pipelines" / "A_company_financials" / "src"))


def majority_quarter(end) -> pd.Period:
    """The calendar quarter holding most days of a ~13-week period ending on `end`."""
    return pd.Period(pd.Timestamp(end) - pd.Timedelta(days=45), "Q")


FISCAL_LABELS = (re.compile(r"FY(?P<y>\d{2})Q(?P<q>\d)"), re.compile(r"FQ(?P<q>\d)-(?P<y>\d{2})"))   # Logitech FY21Q1, TD Synnex FQ1-21
QUARTERS_PER_YEAR, MONTHS_PER_QUARTER = 4, 3


def label_end(label, fy_end: str) -> pd.Timestamp | None:
    """Month-end period end implied by a fiscal label and the fiscal year end ('31 Mar'); None if the label is not one."""
    for rx in FISCAL_LABELS:
        m = rx.fullmatch(str(label))
        if m:
            fye = pd.Timestamp(f"{fy_end} 20{m['y']}")
            return fye - pd.DateOffset(months=MONTHS_PER_QUARTER * (QUARTERS_PER_YEAR - int(m["q"]))) + pd.offsets.MonthEnd(0)
    return None


def _stored_ends(path: str, company: str, fy_end: str) -> pd.DataFrame:
    """(quarter, period end) rows of one source table: its period_end column, else its fiscal_label; empty if neither."""
    t = pd.read_csv(ROOT / path)
    if "company" in t:                                                # peer tables hold several firms
        own = t[t["company"].astype(str) == company.split()[0].lower()]
        t = own if len(own) else t
    if {"quarter", "period_end"} <= set(t.columns):
        return t[["quarter", "period_end"]].dropna()
    if {"quarter", "fiscal_label"} <= set(t.columns):
        ends = t["fiscal_label"].map(lambda x: label_end(x, fy_end))
        return pd.DataFrame({"quarter": t["quarter"], "period_end": ends}).dropna()
    return pd.DataFrame(columns=["quarter", "period_end"])


def stored_check(r) -> tuple[int, int]:
    """(rows checked, rows whose stored quarter is not the majority quarter of their period end) over the row's source tables."""
    rows = pd.concat([_stored_ends(t.strip(), r.company, r.fy_end) for t in str(r.source_table).split(";") if t.strip()],
                     ignore_index=True)
    bad = sum(str(majority_quarter(e)) != str(q) for q, e in zip(rows["quarter"], rows["period_end"]))
    return len(rows), int(bad)


def table() -> pd.DataFrame:
    d = pd.read_csv(TABLE).fillna("")
    d["calendar_quarter"] = d["q3_2026_period_end"].map(lambda e: str(majority_quarter(e)))
    chk = [stored_check(r) for r in d.itertuples()]
    d["rows_checked"], d["rows_off"] = [c[0] for c in chk], [c[1] for c in chk]
    d["stored_check"] = [("stores the quarter only" if n == 0 else f"{n - b} of {n} stored rows agree" if b == 0 else
                          f"{b} of {n} stored rows disagree") for n, b in chk]
    return d


def timeline_svg(d: pd.DataFrame, w: int = 1100) -> str:
    """One row per company: its fiscal quarter as a bar (~13 weeks ending on the period end), calendar Q3 2026 shaded,
    the report date as a diamond. Hover a bar for the fiscal label and where the code files it."""
    x0, x1 = pd.Timestamp("2026-05-01"), pd.Timestamp("2026-12-15")
    L, R, T, row = 190, 20, 30, 22
    h = T + row * len(d) + 30
    x = lambda t: L + (pd.Timestamp(t) - x0).days / (x1 - x0).days * (w - L - R)   # noqa: E731
    o = [f'<svg viewBox="0 0 {w} {h}" width="100%" style="font:11px -apple-system,Segoe UI,Helvetica,Arial,sans-serif">',
         f'<rect x="{x("2026-07-01"):.1f}" y="{T - 18}" width="{x("2026-10-01") - x("2026-07-01"):.1f}" height="{h - T - 10}" fill="#eaf2fb"/>',
         f'<text x="{(x("2026-07-01") + x("2026-10-01")) / 2:.1f}" y="{T - 6}" text-anchor="middle" fill="#0b0b0b" font-weight="600">'
         'calendar Q3 2026 (Jul-Sep): the quarter of the three prints</text>']
    for m in pd.date_range("2026-05-01", "2026-12-01", freq="MS"):
        o.append(f'<line x1="{x(m):.1f}" x2="{x(m):.1f}" y1="{T}" y2="{h - 22}" stroke="#e6e5e1"/>'
                 f'<text x="{x(m) + 3:.1f}" y="{h - 8}" fill="#52514e">{m:%b}</text>')
    for i, r in enumerate(d.itertuples()):
        y = T + i * row
        end = pd.Timestamp(r.q3_2026_period_end)
        start = end - pd.Timedelta(days=90)
        col = _colour(r)[1]
        tip = (f"{r.company}: {r.q3_2026_fiscal_label}, ends {end:%d %b %Y}; majority of its days in {r.calendar_quarter}; "
               f"mapped by {r.mapped_by}; source table: {r.stored_check}; reports {r.reports_typical}")
        o.append(f'<text x="{L - 8}" y="{y + 14}" text-anchor="end" fill="#0b0b0b">{html.escape(r.company)}</text>'
                 f'<g><title>{html.escape(tip)}</title><rect x="{x(start):.1f}" y="{y + 4}" width="{x(end) - x(start):.1f}" height="13" rx="3" fill="{col}" opacity=".85"/></g>')
        if r.report_date_approx:
            rx = x(r.report_date_approx)
            o.append(f'<g><title>{html.escape(r.company + " reports " + r.reports_typical)}</title>'
                     f'<path d="M{rx:.1f},{y + 4} l6,6.5 l-6,6.5 l-6,-6.5 z" fill="#0b0b0b"/></g>')
    o.append("</svg>")
    return "".join(o)


def _colour(r) -> tuple[str, str]:
    """(text, bar) colour of a row: green / blue = its stored quarters agree, red = some disagree, grey = not checkable."""
    if r.rows_checked == 0:
        return "#777", "#9a9a96"
    return ("#2e8b57", "#2a78d6") if r.rows_off == 0 else ("#c0392b", "#e34948")


def section_html() -> str:
    d = table()
    rows = "".join(
        f"<tr><td><b>{html.escape(r.company)}</b><br><span class=src>{html.escape(r.role)}</span></td><td>{html.escape(r.fy_end)}</td>"
        f"<td>{html.escape(r.quarter_ends)}</td><td>{html.escape(r.q3_2026_fiscal_label)}</td><td>{r.q3_2026_period_end}</td>"
        f"<td><b>{r.calendar_quarter}</b></td><td style='color:{_colour(r)[0]};font-weight:600'>{r.stored_check}</td>"
        f"<td>{html.escape(r.reports_typical)}</td><td class=src>{html.escape(r.mapped_by)}</td></tr>" for r in d.itertuples())
    bad, checked = d[d["rows_off"] > 0], d[d["rows_checked"] > 0]
    note = (f"For the {len(checked)} companies whose source table stores a period end or fiscal label next to the quarter, every stored "
            "quarter agrees with the majority rule; the other tables store the calendar quarter only." if bad.empty else
            f"<b style='color:#c0392b'>The source tables of {len(bad)} companies store quarters that disagree with the majority rule</b> "
            f"({', '.join(bad['company'])}; see P124).")
    return ("<h2>Fiscal calendars: which fiscal quarter is 'Q3 2026' for each company</h2>"
            "<p class=note>The three prints cover the same months, Jul-Sep 2026: Nordic Q3, GN Q3 and Logitech Q2 FY2027 (fiscal year ends 31 March). "
            "Every other company is lined up the same way: a fiscal period is filed under the calendar quarter that holds most of its days "
            "(period end - 45 days, one rule in the code since P124). Bar = the fiscal quarter; blue = the quarters its source table stores "
            f"agree with that rule, red = some do not, grey = the table stores the quarter only; diamond = report date. {note}</p>"
            + timeline_svg(d) +
            "<table><tr><th>Company</th><th>Fiscal year ends</th><th>Quarter ends</th><th>Fiscal label of the Jul-Sep 2026 period</th>"
            "<th>Period end</th><th>Calendar quarter (majority)</th><th>Stored quarters vs the rule</th><th>Reports</th><th>Mapping in code</th></tr>"
            f"{rows}</table>")
