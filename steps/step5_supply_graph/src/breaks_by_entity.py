"""Step 5c: structural breaks by entity, the table under the chain-over-time graph (decision G31).

Only breaks and candidate breaks: a LINK that changed (its lag, its weight, its slope, or what a series measures). Inputs
that moved and one-off shocks stay on the graph and in the forecast terms. Each row is named in config
relationship_breaks.by_entity; every number is computed here, each run, from graph_timeline.csv, relationship_breaks.csv /
event_breaks.csv, the 10-K weights and the FCC census. Before / after windows are the data-dated cycle states (step 3b).
"""
from __future__ import annotations

import html
import re

import pandas as pd

from core.config import OUTPUTS, ROOT, step_outputs

NAMES = {"nordic": "Nordic", "logitech": "Logitech", "gn": "GN", "ingram": "Ingram", "tdsynnex": "TD Synnex", "amazon": "Amazon"}
JOIN_BY_SPACE = ("peak_then_last", "state_windows")        # measures that read as a verb phrase after the lead
COLUMNS = ["entity", "status", "what_changed", "test", "treatment"]


def _series(t: pd.DataFrame, node: str, metric: str) -> pd.Series:
    s = t[(t["node"] == node) & (t["metric"] == metric)].set_index("quarter")["value"]
    return pd.to_numeric(s, errors="coerce").dropna().sort_index()


def _signed(fmt: str) -> str:
    return fmt if "{:+" in fmt else fmt.replace("{:", "{:+", 1)


def _row(table: pd.DataFrame, **match) -> pd.Series:
    r = table
    for col, val in match.items():
        r = r[r[col].astype(str) == str(val)]
    if len(r) != 1:
        raise KeyError(f"break table: {match} matches {len(r)} rows")
    return r.iloc[0]


def _measure(m: dict, t: pd.DataFrame, rb: pd.DataFrame, eb: pd.DataFrame, cfg: dict) -> str:
    kind, f = m["kind"], m.get("fmt", "{}")
    if kind == "peak_then_last":
        s = _series(t, m["node"], m["metric"])
        q = s.idxmax()
        return f"peaked at {f.format(s[q])} ({q}), {f.format(s.iloc[-1])} by {s.index[-1]}"
    if kind == "state_windows":                                         # shortage vs after the last 'building' quarter
        s = _series(t, m["node"], m["metric"])
        st = t[(t["node"] == "all") & (t["metric"] == "cycle_state")].set_index("quarter")["value"].dropna()
        short = s[s.index.isin(st[st == "shortage"].index)]
        after = s[s.index > st[st == "building"].index.max()]
        return (f"averaged {f.format(short.mean())} in the shortage ({short.index[0]}-{short.index[-1]}) and "
                f"{f.format(after.mean())} after the destock ({after.index[0]}-{after.index[-1]}), "
                f"{_signed(f).format(after.mean() - short.mean())}")
    if kind == "first_last":
        s = _series(t, m["node"], m["metric"])
        return f"{f.format(s.iloc[0])} ({s.index[0]}) to {f.format(s.iloc[-1])} ({s.index[-1]}), {len(s)} quarters"
    if kind == "vs_node":
        start = cfg["relationship_breaks"]["event_breaks"][m["from_key"]]

        def avg(node: str) -> str:
            s = _series(t, node, "flow_yoy")
            s = s[s.index >= start]
            return f"{NAMES[node]} {f.format(s.mean())} ({s.index[0]}-{s.index[-1]})"
        return ", ".join(avg(n) for n in m["nodes"]) + f" against {avg(m['other'])}"
    if kind == "evidence":
        r = _row(rb, relationship=m["relationship"], **({"break": m["break"]} if "break" in m else {}))
        hit = re.search(m["pick"], str(r["evidence"]))
        if hit is None:
            raise ValueError(f"relationship_breaks.csv evidence has no match for {m['pick']!r}: {r['evidence']}")
        return hit.group(0).strip()
    if kind == "event_evidence":
        return str(_row(eb, event=m["event"], relationship=m["relationship"])["evidence"]).split(m["clip"])[0].strip()
    if kind == "text":
        return m["text"]
    raise ValueError(f"unknown measure kind {kind!r}")


def _test(test: dict, rb: pd.DataFrame, eb: pd.DataFrame) -> str:
    if "untested" in test:
        return "Not tested: " + test["untested"]
    r = (_row(eb, event=test["event"], relationship=test["relationship"]) if "event" in test
         else _row(rb, relationship=test["relationship"], **{"break": test["break"]}))
    if pd.isna(r["p"]):
        return str(r["verdict"])
    return f"{r['test']} p {r['p']:.3f} (n {r['n_pre']:.0f} before / {r['n_post']:.0f} after): {r['verdict']}"


def _treatment(text: str) -> str:
    edges = pd.read_csv(ROOT / "config" / "supply_graph.csv").set_index("edge_id")

    def lag(mo: re.Match) -> str:
        e = edges.loc[mo.group(1)]
        return f"{e['lag_weeks_low']:g}-{e['lag_weeks_high']:g} weeks"
    return re.sub(r"\{edge:(\w+)\}", lag, text)


def table(cfg: dict) -> pd.DataFrame:
    s5 = step_outputs("step5_supply_graph")
    t = pd.read_csv(s5 / "graph_timeline.csv")
    rb, eb = pd.read_csv(s5 / "relationship_breaks.csv"), pd.read_csv(s5 / "event_breaks.csv")
    rows = []
    for spec in cfg["relationship_breaks"]["by_entity"]:
        m = spec["measure"]
        what = spec["lead"] + (" " if m["kind"] in JOIN_BY_SPACE else ": ") + _measure(m, t, rb, eb, cfg)
        if spec.get("tail"):
            what += "; " + spec["tail"]
        rows.append({"entity": spec["entity"], "status": spec["status"], "what_changed": what,
                     "test": _test(spec["test"], rb, eb), "treatment": _treatment(spec["treatment"])})
    return pd.DataFrame(rows, columns=COLUMNS)


def checked_no_break() -> str:
    """One line under the table: the links read or tested that did not change."""
    w = pd.read_csv(ROOT / "config" / "supply_graph_weights.csv")
    shares = ", ".join(f"{NAMES[c]} {w[c].min() * 100:.0f}-{w[c].max() * 100:.0f}%" for c in ("amazon", "ingram", "tdsynnex"))
    from attribution_path import COHORT_YEARS, _readable_peripheral_grants    # steps/step2_attribution/src
    g = _readable_peripheral_grants()
    ends = sorted(g["year"].unique())[-3:]
    cohorts = ", ".join(f"{int(g[(g['year'] > y - COHORT_YEARS) & (g['year'] <= y)]['nordic'].sum())}/"
                        f"{len(g[(g['year'] > y - COHORT_YEARS) & (g['year'] <= y)])}" for y in ends)
    t = pd.read_csv(step_outputs("step5_supply_graph") / "graph_timeline.csv")
    a = _series(t, "amazon", "cover_weeks")
    return (f"Checked, no break: Logitech's customer shares (10-K FY{w['fiscal_year'].min()}-FY{w['fiscal_year'].max()}: {shares}); "
            f"Nordic's share of Logitech radio designs (FCC photos, {COHORT_YEARS}-year cohorts ending {ends[0]}-{ends[-1]}: {cohorts}); "
            f"Amazon's inventory cover ({a.min():.1f}-{a.max():.1f} weeks, {a.index[0]}-{a.index[-1]}). Inputs that moved without "
            "a break (channel states, Nordic's destock and restock) and one-off shocks (Logitech's 2026 supplier incident) are on "
            "the graph above and in the forecast terms.")


def html_section(cfg: dict) -> str:
    """The table for the dashboard's 'Chain over time' tab; also written to outputs/breaks_by_entity.csv."""
    df = table(cfg)
    df.to_csv(OUTPUTS / "breaks_by_entity.csv", index=False)
    head = "".join(f"<th>{h}</th>" for h in ("Entity / link", "Status", "What changed", "Test", "In the model"))
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(r[c]))}</td>" for c in COLUMNS) + "</tr>" for _, r in df.iterrows())
    return ("<h2>Structural breaks by entity</h2>"
            "<p class=src>Only links that changed (a lag, a weight, a slope, or what a series measures). A node's value moving is "
            "an input moving, not a break. Every number is computed each run from the timeline above, the break tests "
            "(steps/step5_supply_graph/outputs/relationship_breaks.csv, event_breaks.csv), the 10-K weights and the FCC census; "
            "before / after windows are the data-dated cycle states. Table: outputs/breaks_by_entity.csv.</p>"
            f"<table><tr>{head}</tr>{body}</table><p class=src>{html.escape(checked_no_break())}</p>")
