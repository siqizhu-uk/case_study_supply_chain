"""The pitfall register (audit/pitfalls.csv) rendered for the dashboard and the results page. Every data or method trap
found in the project is one row: what it was, the evidence, what it would have cost, the fix, where it lives, what guards it."""
from __future__ import annotations

import html

import pandas as pd

from core.config import ROOT, OUTPUTS

REGISTER = ROOT / "audit" / "pitfalls.csv"
STATUS_COLOUR = {"fixed": "#2e8b57", "avoided": "#2e8b57", "mitigated": "#d99a00", "disclosed": "#c0392b"}


def load() -> pd.DataFrame:
    return pd.read_csv(REGISTER, dtype=str).fillna("")


def summary(p: pd.DataFrame) -> pd.DataFrame:
    return p.groupby("category").agg(pitfalls=("id", "size"), ids=("id", lambda s: ", ".join(s))).sort_values("pitfalls", ascending=False).reset_index()


def write_md(p: pd.DataFrame) -> None:
    by = p["status"].value_counts()
    md = ["# Pitfall register\n",
          f"{len(p)} data and method traps found so far — {', '.join(f'{v} {k}' for k, v in by.items())}. Source of truth: `audit/pitfalls.csv`; "
          "every new trap gets a row (what, evidence, cost if missed, fix, where, what guards it). *disclosed* = cannot be fixed, shown as a risk.\n",
          "## By category\n", summary(p).to_markdown(index=False), "",
          "## Every pitfall\n", p[["id", "found_on", "area", "category", "status", "pitfall", "evidence", "impact_if_missed", "solution", "implemented_in", "guarded_by"]].to_markdown(index=False), ""]
    (OUTPUTS / "pitfalls.md").write_text("\n".join(md))


def html_section(p: pd.DataFrame, inner_fold: bool = True) -> str:
    """The register as HTML. inner_fold=False drops the show / hide box, for pages that fold the whole section (dashboard)."""
    rows = "".join(
        f"<tr><td>{r['id']}</td><td>{html.escape(r['area'])}<br><span class=src>{html.escape(r['category'])}</span></td>"
        f"<td><b>{html.escape(r['pitfall'])}</b><br><span class=src>{html.escape(r['evidence'])}</span></td>"
        f"<td>{html.escape(r['impact_if_missed'])}</td><td>{html.escape(r['solution'])}<br><span class=src>{html.escape(r['implemented_in'])} · {html.escape(r['guarded_by'])}</span></td>"
        f"<td style='color:{STATUS_COLOUR.get(r['status'], '#777')};font-weight:600'>{r['status']}</td></tr>" for _, r in p.iterrows())
    by = p["status"].value_counts()
    return (f"<h2>Pitfall register ({len(p)} traps: " + ", ".join(f"{v} {k}" for k, v in by.items()) + ")</h2>"
            "<p class=note>Every data or method trap found so far, with its evidence, what it would have cost, the fix and what guards it. "
            "Source: audit/pitfalls.csv — new traps are added there and appear here on the next run.</p>"
            + ("<details open><summary style='cursor:pointer;font-weight:600'>Show / hide the register</summary>" if inner_fold else "")
            + "<table><tr><th>#</th><th>Area</th><th>Pitfall · evidence</th><th>Cost if missed</th><th>Fix · where · guarded by</th><th>Status</th></tr>"
            f"{rows}</table>" + ("</details>" if inner_fold else ""))
