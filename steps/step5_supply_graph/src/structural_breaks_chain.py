"""Step 5d: every structural break and regime of the last four years read through the chain (decision G23).

One row per entry of config/model.yaml `structural_breaks` and `regimes`. The judgment per event (shock or break, which
graph element changes, which buffer absorbs it, how the model handles it, decision / pitfall ids) is written once in
steps/step5_supply_graph/config/structural_breaks_chain.csv; the consequence for Nordic's revenue is computed
here from data already in the repo (panel, step 2 / 3 / 5 outputs, the event study) - no number is typed in.
    shock      a dated change in flow with every edge unchanged: the graph propagates it (the event study)
    break      an edge changes: lag, share or amplitude (condition on it, exclude it, or split by route)
    reporting basis / node change: a series is redefined (restate or mask; nothing to propagate)
    one-off (margin): no revenue consequence
"""
from __future__ import annotations

import pandas as pd

from core.config import ROOT

CFG = ROOT / "steps" / "step5_supply_graph" / "config" / "structural_breaks_chain.csv"
S2 = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"
S3 = ROOT / "steps" / "step3_inventory_mechanism" / "outputs"
RB = ROOT / "steps" / "step5_supply_graph" / "outputs" / "relationship_breaks.csv"
WEIGHTS = ROOT / "config" / "supply_graph_weights.csv"


def _res(sign: str, timing: str, text: str) -> dict:
    return {"sign": sign, "timing": timing, "nordic_revenue_consequence": text}


# ------------------------------------------------------------------ consequences, one per kind of evidence
def _incident(ctx: dict, key: str) -> dict:
    s = ctx["event"]
    return _res("-", f"{s['tq']}-{s['tq1']}",
                f"{s['tq']} {s['event_q']:+.1f}m gross, {s['net_q']:+.1f}m net of the {s['share_in_guide']:.0%} already in the guide "
                f"(band {s['band_q'][0]:+.1f} to {s['band_q'][1]:+.1f}); {s['tq1']} {s['event_q1']:+.1f}m; all quarters {s['gross_total']:+.1f}m "
                f"= {s['content_pct']:.2f}% x {s['logitech_total']:+.0f}m lost Logitech sales")


def _supply_constrained(ctx: dict, key: str) -> dict:
    p, rg, s = ctx["panel"], ctx["cfg"]["regimes"][key], ctx["event"]
    bl = p["nordic_backlog"].dropna()
    qb = bl.idxmax()
    ratio = bl[qb] / p.loc[qb, "nordic_rev"]
    rev = p["nordic_rev"].loc[qb:qb + 4]
    qr = rev.idxmax()
    return _res("+ then -", f"{qb}-{qr}",
                f"backlog peaked at {ratio:.1f}x quarterly revenue ({ratio * ctx['wq']:.0f} weeks of shipments) in {qb}; revenue kept rising "
                f"{(qr - qb).n} quarters more (peak {qr}): demand cuts hit the backlog before revenue. Edge-2 lead {s['lead_weeks']:.1f} wk "
                f"x lag_multiplier {rg['lag_multiplier']:g} = {s['lead_weeks'] * rg['lag_multiplier']:.1f} wk; amplitude x{rg['amplitude_multiplier']:g}")


def _destock(ctx: dict, key: str) -> dict:
    p, q = ctx["panel"], ctx["cfg"]["regimes"][key]["quarters"]
    a, z = pd.Period(q[0], "Q"), pd.Period(q[1], "Q")
    rev = p["nordic_rev"].loc[a - 1:z]
    pk = rev.idxmax()
    tr = rev.loc[pk:].idxmin()
    tb = pd.read_csv(S3 / "nordic_top10_vs_broad.csv").set_index("year")
    yr = int(tb["broad_yoy_pct"].idxmin())
    bt = pd.read_csv(S3 / "beat_by_cycle_state.csv").query("sample == 'nordic'").set_index("state")
    return _res("-", f"{pk}-{tr}",
                f"Nordic revenue {rev[pk]:.0f}m ({pk}) -> {rev[tr]:.0f}m ({tr}), {rev[tr] / rev[pk] - 1:+.0%}; {yr} top-10 customers "
                f"{tb.loc[yr, 'top10_yoy_pct']:+.1f}% vs broad market {tb.loc[yr, 'broad_yoy_pct']:+.1f}% (the Logitech slice is a top-10 account); "
                f"Nordic's beat in 'building' quarters {bt.loc['building', 'mean_beat_pct']:+.1f}% (n {int(bt.loc['building', 'n'])}) vs "
                f"{bt.loc['lean', 'mean_beat_pct']:+.1f}% lean")


def _normal(ctx: dict, key: str) -> dict:
    return _res("none", "-", "reference: shares and lags as in the graph")


def _asp(ctx: dict, key: str) -> dict:
    from chain_forecast import slice_multiplier                              # step 7c, read only
    cfg = ctx["cfg"]
    pts = cfg["structural_breaks"][key]["asp_tailwind_pts"]
    s = float(pd.read_csv(S2)["share_total_indirect_p50"].dropna().iloc[-1]) / 100
    m = slice_multiplier(cfg)[0]
    g = cfg["forecast"]["nordic_2026Q3"]
    v = s * m * pts / 100 * (g["guide_low"] + g["guide_high"]) / 2
    return _res("+ (if misread)", "2026",
                f"none as modelled; read as units, distributor dollars would overstate the Nordic slice by ~{v:.1f}m a quarter "
                f"(share {s:.1%} x slice multiplier {m:.2f} x {pts} pts x Nordic guide midpoint)")


def _margin(ctx: dict, key: str) -> dict:
    b = ctx["cfg"]["structural_breaks"][key]
    adj = (f"GM adjusted to {b['adj_gm_pct']}%" if "adj_gm_pct" in b else f"GM {b['adj_gm_pts']:+} pts ex the one-off" if "adj_gm_pts" in b else "")
    return _res("none", "-", f"none on revenue ({adj})" if adj else "none on revenue")


def _basis(ctx: dict, key: str) -> dict:
    extra = ""
    if key.startswith("gn_"):
        extra = f"; GN = {ctx['cfg']['supply_graph']['brand_share']['gn']:.1%} of the Logitech + GN slice of Nordic"
    if key.startswith("tdsynnex"):
        w = pd.read_csv(WEIGHTS)["tdsynnex"]
        extra = f"; TD Synnex {w.min():.0%}-{w.max():.0%} of Logitech's gross sales in every 10-K (the edge did not move)"
    return _res("none", "-", "none on Nordic revenue (a series is redefined, nothing flows differently)" + extra)


SIZERS = {"logitech_supplier_incident_2026": _incident, "supply_constrained": _supply_constrained, "destock": _destock,
          "normal": _normal, "distributor_asp_inflation_2026": _asp}
BY_KIND = {"one-off (margin)": _margin, "reporting basis": _basis, "node change": _basis}


# ------------------------------------------------------------------ evidence from the step 5c break tests
def _rb_evidence(rb: pd.DataFrame, key: str, source: str, cfg: dict) -> str:
    if rb.empty:
        return ""
    if source == "regimes":
        a, z = (pd.Period(q, "Q") for q in cfg["regimes"][key]["quarters"])
        hit = rb[rb["break"].astype(str).str.fullmatch(r"\d{4}Q\d")]
        hit = hit[hit["break"].map(lambda q: min(abs((pd.Period(q, "Q") - a).n), abs((pd.Period(q, "Q") - (z + 1)).n)) <= 1)]
        extra = rb[rb["relationship"].isin(["Logitech 10-K customer shares", "Graph lag kernel re-computed at each 10-K"])] if key == "normal" else rb.iloc[0:0]
        hit = pd.concat([hit, extra])
    else:
        hit = rb[rb["treatment"].astype(str).str.contains(f"structural_breaks.{key}", regex=False)]
    return "; ".join(f"5c {r.relationship} @ {r['break']}: {r.verdict}" + (f" (p {r.p:.3f})" if pd.notna(r.p) else "") for _, r in hit.iterrows())


def _dates(cfg: dict, row) -> str:
    if row["source"] == "regimes":
        return "-".join(cfg["regimes"][row["key"]]["quarters"])
    return str(row["dates"])


def breaks_chain(p: pd.DataFrame, cfg: dict, event: dict) -> pd.DataFrame:
    """One row per config structural_breaks entry + regime; judgment from the step-5 config, consequence computed."""
    c = pd.read_csv(CFG, dtype=str).fillna("")
    keys = [("regimes", k) for k in cfg["regimes"]] + [("structural_breaks", k) for k in cfg["structural_breaks"]]
    c = c.set_index("key").reindex([k for _, k in keys]).reset_index()
    rb = pd.read_csv(RB) if RB.exists() else pd.DataFrame()
    ctx = {"panel": p, "cfg": cfg, "event": event, "wq": cfg["supply_graph"]["weeks_per_quarter"]}
    rows = []
    for (src, key), r in zip(keys, c.to_dict("records")):
        f = SIZERS.get(key) or BY_KIND.get(r.get("kind", ""), lambda *_: _res("", "", "not sized"))
        con = f(ctx, key)
        rows.append({"event": key, "source": src, "dates": _dates(cfg, {**r, "source": src, "key": key}),
                     "shock_or_break": r.get("kind") or "not classified", "graph_element": r.get("graph_element", ""),
                     "buffer": r.get("buffer", ""), **con, "handled_in_model": r.get("handled_in_model", ""),
                     "evidence": "; ".join(x for x in (r.get("evidence_files", ""), _rb_evidence(rb, key, src, cfg)) if x),
                     "ids": r.get("ids", "")})
    return pd.DataFrame(rows)


def breaks_chain_md(t: pd.DataFrame) -> str:
    kinds = t["shock_or_break"].value_counts()
    return "\n".join(["", "### Every break and shock of the last four years, through the chain", "",
                      f"{len(t)} events ({', '.join(f'{v} {k}' for k, v in kinds.items())}). Only the rows marked *break* change what the graph "
                      "says about Nordic; the shock is propagated; reporting-basis rows are restated or masked; margin one-offs do not touch revenue. "
                      "Full table: `outputs/structural_breaks_chain.csv`; the judgment per row: `config/structural_breaks_chain.csv`.", "",
                      t[["event", "dates", "shock_or_break", "graph_element", "buffer", "nordic_revenue_consequence", "handled_in_model", "ids"]]
                      .to_markdown(index=False), ""])
