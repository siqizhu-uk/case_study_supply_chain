"""Step 3: who holds inventory at each tier, who bears it, and what each company discloses about its own and its channel's
inventory (numeric / verbal / nothing) - the brief's 'Mechanism' question as one table (steps/step3_inventory_mechanism/config/inventory_disclosure.csv,
decision D23). Rendered on the dashboard; every series named in the last column is checked to exist in the metric catalogue."""
from __future__ import annotations

import html

import pandas as pd

from core.config import ROOT, load_config

TABLE = ROOT / "steps" / "step3_inventory_mechanism" / "config" / "inventory_disclosure.csv"
TYPE_COL = {"numeric": "#2e8b57", "verbal": "#d99a00", "n/a": "#999"}


class _Tokens(dict):
    def __missing__(self, key: str) -> str:
        return "n/a"


def _tokens(cfg: dict | None = None) -> dict:
    """{token} values the table's text reads from config/model.yaml (so an edited assumption shows where it is used)."""
    cfg = cfg or load_config()
    sh = cfg.get("inventory_mechanism", {}).get("nordic_distribution_share")
    return _Tokens({"nordic_dist_share": f"{sh['low'] * 100:.0f}–{sh['high']:.0%} (mid {sh['mid']:.0%})"} if sh else {})


def load(cfg: dict | None = None) -> pd.DataFrame:
    d = pd.read_csv(TABLE).fillna("")
    tok = _tokens(cfg)
    text = [c for c in d.columns if d[c].dtype == object]
    return d.assign(**{c: d[c].map(lambda s: s.format_map(tok)) for c in text})


def _badge(t: str) -> str:
    key = next((k for k in TYPE_COL if t.startswith(k)), "")
    return f"<span style='color:{TYPE_COL.get(key, '#333')};font-weight:600'>{html.escape(t)}</span>"


def section_html() -> str:
    d = load()
    rows = "".join(
        f"<tr><td>{html.escape(r.tier)}</td><td><b>{html.escape(r.holder)}</b></td><td>{html.escape(r.bears_the_risk_of)}</td>"
        f"<td>{html.escape(r.own_inventory_disclosed)}<br>{_badge(r.own_type)}</td>"
        f"<td>{html.escape(r.channel_inventory_disclosed)}<br>{_badge(r.channel_type)}</td>"
        f"<td style='color:#c0392b'>{html.escape(r.hidden)}</td><td class=src>{html.escape(r.series_in_model)}</td></tr>"
        for r in d.itertuples())
    return ("<h2>Mechanism: who holds the inventory, and who discloses it</h2>"
            "<p class=note>Own balance-sheet inventory is disclosed as a number by every listed company; channel inventory, the part that "
            "moves the next tier's orders, is disclosed as a number by one company in the chain's reach (Microchip's distributor days) and only in "
            "words by Logitech, GN and Nordic. Every model series that stands in for a hidden quantity is named in the last column "
            "(grades in the Data tab). Source: steps/step3_inventory_mechanism/config/inventory_disclosure.csv.</p>"
            "<table><tr><th>Tier</th><th>Holder</th><th>Bears the risk of</th><th>Own inventory: disclosed</th>"
            f"<th>Channel inventory: disclosed</th><th>Hidden</th><th>Series in the model</th></tr>{rows}</table>")
