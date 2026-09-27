"""The cross-checks beside each forecast (steps/step7_forecast/outputs/cross_checks.csv, built by cross_checks.py) as the
dashboard shows them: per forecast, how many independent checks land inside its band, every check
with its gap, and one computed sentence where the point sits at the edge of its alternatives."""
from __future__ import annotations

import html
import re

import pandas as pd

from core.config import ROOT

S7 = ROOT / "steps" / "step7_forecast" / "outputs"
ALTERNATIVES = ("method", "challenger", "scenario")   # every non-guide check; superseded ones (old rules) are left out
KIND_LABEL = {"guide": "company guide", "method": "other method", "challenger": "pre-registered challenger", "scenario": "one input moved"}


def load() -> pd.DataFrame | None:
    try:
        return pd.read_csv(S7 / "cross_checks.csv")
    except FileNotFoundError:
        return None


def _fmt(v: float, metric: str) -> str:
    return f"{v:.1f}%" if "%" in metric else f"{v:,.0f}" if abs(v) >= 1000 else f"{v:,.1f}"


def counts(t: pd.DataFrame) -> pd.DataFrame:
    """Per forecast: checks compared with the band and how many land inside (a floor guide is shown, not compared; a
    superseded rule is shown, not counted)."""
    c = t[t["inside_band"].notna() & ~t["check"].astype(str).str.contains("superseded")]
    c = c.assign(inside=lambda d: d["inside_band"].astype(str).str.lower() == "true")
    return c.groupby(["print", "metric"], sort=False).agg(compared=("inside", "size"), inside=("inside", "sum")).reset_index()


def _short(label: str) -> str:
    """Drop bookkeeping parentheticals (RMSE, decision ids, weights); keep the ones that name the variant, e.g. '(last 4)'."""
    return re.sub(r"\s*\([^()]*(?:RMSE|F\d|weight|errors correlate)[^()]*\)", "", str(label)).strip()


def edge_sentence(g: pd.DataFrame) -> str:
    """'The point is below every alternative ...' when every non-guide, non-superseded check sits on one side of it."""
    alt = g[g["kind"].isin(ALTERNATIVES) & g["gap_vs_point"].notna() & (g["gap_vs_point"].abs() > 0)
            & ~g["check"].astype(str).str.contains("superseded")]
    if len(alt) < 2 or not ((alt["gap_vs_point"] > 0).all() or (alt["gap_vs_point"] < 0).all()):
        return ""
    side = "below" if (alt["gap_vs_point"] > 0).all() else "above"
    m = str(g["metric"].iloc[0])
    vals = ", ".join(f"{_short(r.check)} {_fmt(r.value, m)}" for r in alt.itertuples())
    return f"The point is {side} every alternative ({vals})."


def html_section() -> str:
    t = load()
    if t is None:
        return ""
    n = counts(t).set_index(["print", "metric"])
    blocks = []
    for (pr, me), g in t.groupby(["print", "metric"], sort=False):
        c = n.loc[(pr, me)]
        rows = "".join(
            f"<tr><td>{html.escape(r.check)}</td><td class=src>{KIND_LABEL.get(r.kind, r.kind)}</td><td>{_fmt(r.value, me)}</td>"
            f"<td>{r.gap_vs_point:+,.1f}</td><td>{'' if pd.isna(r.inside_band) else ('inside' if str(r.inside_band).lower() == 'true' else '<b>outside</b>')}</td>"
            f"<td class=src>{html.escape(str(r.tests))}</td></tr>" for r in g.itertuples())
        edge = edge_sentence(g)
        blocks.append(f"<h4 style='margin:10px 0 2px'>{html.escape(pr)} · {html.escape(me)}: {_fmt(g['point'].iloc[0], me)} "
                      f"({_fmt(g['low'].iloc[0], me)} – {_fmt(g['high'].iloc[0], me)}) · {int(c['inside'])} of {int(c['compared'])} checks inside the band</h4>"
                      + (f"<p class=src>{html.escape(edge)}</p>" if edge else "")
                      + "<table><tr><th>Check</th><th>Kind</th><th>Value</th><th>Gap to point</th><th>Band</th><th>Decision it tests</th></tr>"
                      + rows + "</table>")
    return ("<details><summary><b>Cross-checks beside each forecast</b> — every independent way to the same number, and whether it "
            "lands inside the point's ≈80% band (steps/step7_forecast/outputs/cross_checks.csv)</summary>" + "".join(blocks) + "</details>")
