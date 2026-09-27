"""Step 5 outputs: path table, lag kernel (by scenario and over time), edge flows, the graph as SVG, step5_report.md."""
from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import step_outputs
from core.config import ROOT
from step4_check import compare, section as step4_section  # noqa: E402
from gap_decomposition import decompose  # noqa: E402
from lag_gap import continuous_lag_table, gap_section  # noqa: E402
from residual_evidence import run as residual_run, section as residual_section, lag_lines as residual_lag_lines  # noqa: E402
from supply_graph import (mix_lags, load_edges, edge_shares, effective_ranges, paths, kernel, kernel_asof, load_weights, propagate, NODES, WEIGHTS)

W, LAYER_H, BOX_W, BOX_H = 900, 92, 170, 40
LAG_COL = {"A": "#185FA5", "B": "#185FA5", "C": "#BA7517", "D": "#888780"}
GRADE_STYLE = {g: (c, "" if g in "AB" else ' stroke-dasharray="7 3"') for g, c in LAG_COL.items()}   # kept for callers


def edge_style(r) -> tuple[str, str]:
    """Two separate channels: colour = support for the LAG, line style = support for the SHARE (solid A/B, dashed C/D)."""
    return LAG_COL.get(r.lag_grade, "#888780"), ("" if r.share_grade in ("A", "B") else ' stroke-dasharray="7 3"')
RANK = {"A": 0, "B": 1, "C": 2, "D": 3}


def edge_grade(r) -> str:
    """An edge is as reliable as the weaker of its share and its lag."""
    g = [x for x in (r.share_grade, r.lag_grade) if x in RANK]
    return max(g, key=RANK.get) if g else "D"


# ------------------------------------------------------------------ data anchors for the lags (Little's law)
def xbrl_dio() -> pd.DataFrame:
    """Quarterly inventory days (inventory / quarterly cost of sales x 91.25) per XBRL filer in Pipeline A's detail file."""
    x = pd.read_csv(ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "inventory_detail_xbrl.csv")
    w = x.pivot_table(index=["company", "quarter"], columns="metric", values="value_usdm").reset_index()
    w["dio"] = w["inventory"] / w["cogs"] * 91.25
    return w.pivot(index="quarter", columns="company", values="dio")


def gn_dio() -> pd.Series:
    """GN inventory days on a peripherals basis: Audio segment 2021-2023; continuing operations from 2026 (Hearing moved to
    assets held for sale). 2024-2025 group inventory mixes Hearing in: left blank rather than compared across bases."""
    g = pd.read_csv(ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "gn_quarterly.csv").set_index("quarter")
    audio = g["audio_inventory_dkkm"] / (g["audio_rev_dkkm"] * (1 - g["audio_gm_pct"] / 100)) * 91.25
    cont = g["inventory_dkkm"] / (g["cont_ops_rev_dkkm"] * (1 - g["cont_ops_gm_pct"] / 100)) * 91.25
    cont = cont[cont.index >= "2026Q1"]
    return audio.combine_first(cont).dropna().rename("gn_dio")


def logi_stage_weeks() -> pd.DataFrame:
    """Logitech raw-material and finished-goods weeks on quarterly cost of sales (XBRL stage split, hand-typed sales / GM)."""
    x = pd.read_csv(ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "inventory_detail_xbrl.csv")
    w = x[x["company"] == "logitech"].pivot(index="quarter", columns="metric", values="value_usdm")
    l = pd.read_csv(ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "logitech_quarterly.csv").set_index("quarter")
    cogs = l["net_sales_usdm"] * (1 - l["gm_gaap_pct"] / 100)
    return pd.DataFrame({"rm_weeks": w["inv_raw_materials"] / cogs * 13, "fg_weeks": w["inv_finished_goods"] / cogs * 13}).dropna()


def lag_anchors(p: pd.DataFrame) -> dict:
    """Upper bounds on each tier's reorder lag in weeks at the latest quarter (Little's law: a unit cannot on average wait
    longer than the stock's cover). Composite bounds add the stages a path crosses."""
    last = lambda s: float(s.dropna().iloc[-1]) if len(s.dropna()) else np.nan   # noqa: E731
    dio = xbrl_dio()
    ch = pd.read_csv(ROOT / "pipelines" / "C_realtime_channel" / "data" / "raw" / "channel_snapshots.csv")
    lt = ch[ch["part"].str.startswith(("nRF54", "nRF5340"), na=False)]["lead_time"].dropna()
    lt = float(lt.max()) if len(lt) else np.nan
    logi_inv = last(p["logi_inv_days"]) / 7
    return {"ingram_weeks": last(p["ingm_inv_days"]) / 7, "tdsynnex_weeks": last(p["snx_inv_days"]) / 7, "logi_inv_weeks": logi_inv,
            "arrow_avnet_weeks": min(last(dio["arrow"]), last(dio["avnet"])) / 7, "nrf54_leadtime_weeks": lt,
            "amazon_weeks": last(dio["amazon"]) / 7, "retail_weeks": last(dio["bestbuy"]) / 7, "reseller_weeks": last(dio["cdw"]) / 7,
            "gn_inv_weeks": last(gn_dio()) / 7, "logi_inhouse_weeks": lt + logi_inv, "logi_stock_inhouse_weeks": 2 + logi_inv,
            "logi_rm_weeks": last(logi_stage_weeks()["rm_weeks"])}


def lag_checks(edges: pd.DataFrame, anchors: dict, tol: float) -> pd.DataFrame:
    rows = []
    for r in edges[edges["lag_anchor"].isin(anchors)].itertuples():
        a, hi = anchors[r.lag_anchor], float(r.lag_weeks_high)
        rows.append({"edge_id": r.edge_id, "anchor": r.lag_anchor, "anchor_weeks": a, "lag_high_weeks": hi,
                     "check": "ok" if np.isnan(a) or hi <= a * tol else "EXCEEDS cover", "lag_grade": r.lag_grade})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ uncertainty: path grades, Monte Carlo, tornado
def path_grades(edges: pd.DataFrame, pt: pd.DataFrame) -> pd.DataFrame:
    g = {}
    for r in edges.itertuples():
        g[(r.src, r.dst, r.brand)] = edge_grade(r)
    out = []
    for r in pt.itertuples():
        n = r.path.split(" > ")
        grades = [g.get((a, b, r.brand), g.get((a, b, "all"), "D")) for a, b in zip(n, n[1:])]
        out.append(max(grades, key=RANK.get))
    return pt.assign(grade=out)


def _mean_lag(edges, cfg, params, lags) -> tuple[float, pd.Series]:
    e = edges.copy()
    e["lag_weeks_mid"] = lags
    pt = paths(e, edge_shares(e, cfg, pd.Timestamp.today(), params=params), cfg)
    return float((pt["weight"] * pt["lag_weeks"]).sum() / pt["weight"].sum()), kernel(pt, cfg)


def tier_grades(edges: pd.DataFrame, flows: pd.Series) -> pd.DataFrame:
    """Share of the flow crossing each tier by grade, for the SHARE and the LAG separately (support, not level)."""
    nodes = pd.read_csv(NODES).set_index("node")
    tier = {0: "Nordic → buyer / own plant", 1: "buyer → brand", 2: "brand → channel", 3: "distributor → retail", 4: "retail → end demand"}
    e = edges.assign(flow=flows.reindex(edges["edge_id"]).values, tier=edges["src"].map(nodes["layer"]).map(tier))
    e = e[e["flow"] > 0]
    out = []
    for what, col in (("share", "share_grade"), ("lag", "lag_grade")):
        t = e.pivot_table(index="tier", columns=col, values="flow", aggfunc="sum", fill_value=0.0)
        t = t.div(t.sum(axis=1), axis=0).reindex(columns=["A", "B", "C", "D"], fill_value=0.0)
        out.append(t.reindex([v for v in tier.values() if v in t.index]).add_prefix(f"{what}_"))
    return pd.concat(out, axis=1)


def data_gaps(edges: pd.DataFrame, flows: pd.Series) -> pd.DataFrame:
    """Every D-graded share or lag, whether the data are not public or merely not collected, and the flow it touches."""
    rows = []
    for r in edges.itertuples():
        for what, g, av, ev in (("share", r.share_grade, r.share_availability, r.evidence), ("lag", r.lag_grade, r.lag_availability, r.lag_evidence)):
            if g == "D":
                rows.append({"edge_id": r.edge_id, "edge": f"{r.src} → {r.dst}", "what": what, "availability": av,
                             "flow": float(flows.get(r.edge_id, 0.0)), "why": ev})
    return pd.DataFrame(rows).sort_values(["availability", "flow"], ascending=[True, False]).reset_index(drop=True)


def monte_carlo(edges: pd.DataFrame, cfg: dict, seed: int = 0) -> dict:
    """Draw every named share and every edge lag from triangular(low, mid, high); return the mean-lag distribution and
    the kernel band. Logitech's 10-K shares are grade A and held fixed."""
    rng = np.random.default_rng(seed)
    edges, sgp = effective_ranges(edges, cfg)
    lo, md, hi = (pd.to_numeric(edges[f"lag_weeks_{k}"], errors="coerce").fillna(0).values for k in ("low", "mid", "high"))
    tri = lambda a, m, b: rng.triangular(a, m, b) if b > a else m   # noqa: E731
    lags, ks = [], []
    for _ in range(cfg["supply_graph"]["mc_draws"]):
        params = {k: tri(v["low"], v["mid"], v["high"]) for k, v in sgp.items()}
        L = np.array([tri(a, m, b) for a, m, b in zip(lo, md, hi)])
        ml, k = _mean_lag(edges, cfg, params, L)
        lags.append(ml)
        ks.append(k.values)
    lags, ks = np.array(lags), np.array(ks)
    q = lambda a, p: np.percentile(a, p, axis=0)   # noqa: E731
    band = pd.DataFrame({"p5": q(ks, 5), "p50": q(ks, 50), "p95": q(ks, 95)}, index=range(ks.shape[1]))
    band.index.name = "lag_quarters"
    return {"mean_lag_weeks": {"p5": float(q(lags, 5)), "p50": float(q(lags, 50)), "p95": float(q(lags, 95))}, "kernel_band": band}


def _unmixed(raw: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Effective (grade-widened, bounded) lags before any lag mix is applied."""
    return effective_ranges(raw.drop(columns="lag_mix", errors="ignore"), cfg)[0].assign(lag_mix=raw.get("lag_mix", ""))


def tornado(edges: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Swing one input from low to high (grade-based effective range), everything else at mid: change in the weighted mean
    lag (weeks). Swing = sensitivity x uncertainty, so a D input with a wide range can rank high: that is the point."""
    raw = edges
    edges, sgp = effective_ranges(raw, cfg)
    mid_p = {k: v["mid"] for k, v in sgp.items()}
    mid_l = pd.to_numeric(edges["lag_weeks_mid"], errors="coerce").fillna(0).values
    base, _ = _mean_lag(edges, cfg, mid_p, mid_l)
    mixed = set(raw["lag_mix"].astype(str).str.split(":").str[0]) if "lag_mix" in raw else set()
    rows = []
    for k, v in sgp.items():
        if k in mixed:      # a lag-mix share moves the mixed edge's lag, not a path weight: rebuild the mid lags at its low / high
            lag_at = lambda x: pd.to_numeric(mix_lags(raw_eff, {**sgp, k: {"low": x, "mid": x, "high": x}})["lag_weeks_mid"],   # noqa: E731
                                             errors="coerce").fillna(0).values
            raw_eff = _unmixed(raw, cfg)
            a, _ = _mean_lag(edges, cfg, mid_p, lag_at(v["low"]))
            b, _ = _mean_lag(edges, cfg, mid_p, lag_at(v["high"]))
        else:
            a, _ = _mean_lag(edges, cfg, {**mid_p, k: v["low"]}, mid_l)
            b, _ = _mean_lag(edges, cfg, {**mid_p, k: v["high"]}, mid_l)
        rows.append({"input": f"share: {k}", "grade": cfg["supply_graph"]["params"][k].get("grade", "D"), "low_weeks": a, "high_weeks": b, "swing_weeks": abs(b - a)})
    for i, r in enumerate(edges.itertuples()):
        lo_, hi_ = pd.to_numeric(pd.Series([r.lag_weeks_low, r.lag_weeks_high]), errors="coerce")
        if pd.isna(lo_) or lo_ == hi_:
            continue
        L1, L2 = mid_l.copy(), mid_l.copy()
        L1[i], L2[i] = lo_, hi_
        a, _ = _mean_lag(edges, cfg, mid_p, L1)
        b, _ = _mean_lag(edges, cfg, mid_p, L2)
        rows.append({"input": f"lag: {r.edge_id} {r.src}→{r.dst}", "grade": r.lag_grade, "low_weeks": a, "high_weeks": b, "swing_weeks": abs(b - a)})
    return pd.DataFrame(rows).assign(base_weeks=base).sort_values("swing_weeks", ascending=False).reset_index(drop=True)


def edge_flows(edges: pd.DataFrame, pt: pd.DataFrame) -> pd.Series:
    """Share of the Nordic slice passing each edge = sum of the weights of the paths that use it."""
    flow = pd.Series(0.0, index=edges["edge_id"])
    for r in pt.itertuples():
        nodes = r.path.split(" > ")
        for a, b in zip(nodes, nodes[1:]):
            m = edges[(edges["src"] == a) & (edges["dst"] == b) & edges["brand"].isin([r.brand, "all"])]
            if len(m):
                flow[m["edge_id"].iloc[0]] += r.weight
    return flow


def _xy(nodes: pd.DataFrame) -> dict:
    """Node centre-top positions: x is a fraction of the width (config/supply_graph_nodes.csv), y from the layer."""
    return {r.node: (W * float(r.x), 40 + int(r.layer) * LAYER_H) for r in nodes.itertuples()}


def mixed_lags(edges: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """The edge table with every lag mix applied at the configured p (low p with low lags, mid with mid, high with high):
    the lag the graph uses for an edge whose flow splits over routes it has no entity for, e.g. E14 = (1 - p) x direct
    retail + p x the Ingram / TD Synnex route (G20). Other edges keep their table lags (not grade-widened)."""
    return mix_lags(edges, effective_ranges(edges, cfg)[1])


def _tip(r, flow: float | None, lag_line: str | None = None) -> str:
    """Edge details for the tooltip: one field per line. `lag_line` replaces the table lag where the graph mixes it (E14)."""
    lag = (f"{lag_line} — grade {r.lag_grade} ({r.lag_availability})" if lag_line else
           f"lag: {r.lag_weeks_low}-{r.lag_weeks_high} weeks (mid {r.lag_weeks_mid}) — grade {r.lag_grade} ({r.lag_availability})"
           if r.lag_weeks_mid else f"lag: n/a — grade {r.lag_grade}")
    lines = [f"{r.edge_id}  {r.src} → {r.dst}  ({r.brand})  ·  edge grade {edge_grade(r)}",
             f"share: {r.share or 'n/a'} — grade {r.share_grade} ({r.share_availability})" + (f" · flow {flow:.1%} of the Nordic slice" if flow is not None else ""),
             f"  source: {r.evidence or '—'}",
             lag,
             f"  source: {r.lag_evidence or '—'}",
             f"inventory: {r.inventory_holder} (disclosed: {r.inventory_disclosed})"] + ([f"note: {r.note}"] if r.note else [])
    return "\n".join(lines)


def _hit(d: str, tip: str) -> str:
    """Invisible 14 px strip over the edge: easy to hover or tap; carries the details (and a native <title> fallback)."""
    t = html.escape(tip)
    return (f'<path class="sg-hit" d="{d}" fill="none" stroke="transparent" stroke-width="14" pointer-events="stroke" '
            f'style="cursor:pointer" data-tip="{t}"><title>{t}</title></path>')


def render_svg(edges: pd.DataFrame, flows: pd.Series, lag_lines: dict | None = None) -> str:
    """The graph as SVG; `lag_lines` (edge_id -> text) replaces the tooltip's table lag for p-mixed edges (G20)."""
    lag_lines = lag_lines or {}
    nodes = pd.read_csv(NODES)
    xy = _xy(nodes)
    H = 40 + int(nodes["layer"].max()) * LAYER_H + BOX_H + 60
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg" font-family="-apple-system,Segoe UI,Helvetica,Arial" font-size="12">',
             '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="context-stroke" stroke-width="1.5"/></marker></defs>']
    for r in edges.itertuples():
        (x1, y1), (x2, y2) = xy[r.src], xy[r.dst]
        f = float(flows.get(r.edge_id, 0.0))
        col, dash = edge_style(r)
        wdt = 0.8 + 6 * f
        if r.edge_id == "E25":                                    # Nordic -> Amazon devices: no demand series, dotted
            d = f"M{x1} {y1 + BOX_H} L{x2} {y2}"
            parts.append(f'<path d="{d}" fill="none" stroke="#7F77DD" stroke-width="1" stroke-dasharray="2 3" marker-end="url(#ah)"/>')
            parts.append(_hit(d, _tip(r, None, lag_lines.get(r.edge_id))))
            continue
        if y1 == y2:
            d = f"M{x1 + (BOX_W / 2 if x2 > x1 else -BOX_W / 2)} {y1 + BOX_H / 2} L{x2 - (BOX_W / 2 if x2 > x1 else -BOX_W / 2)} {y2 + BOX_H / 2}"
        else:
            d = f"M{x1} {y1 + BOX_H} L{x2} {y2}"
        parts.append(f'<path class="sg-edge" d="{d}" fill="none" stroke="{col}" stroke-width="{wdt:.2f}" stroke-opacity="0.85"{dash} marker-end="url(#ah)"/>')
        parts.append(_hit(d, _tip(r, f, lag_lines.get(r.edge_id))))
    for r in nodes.itertuples():
        x, y = xy[r.node]
        fill, stroke = ("#E6F1FB", "#185FA5") if r.named_in_brief == "yes" else ("#F1EFE8", "#888780")
        dash = "" if r.named_in_brief == "yes" else ' stroke-dasharray="4 3"'
        parts.append(f'<rect x="{x - BOX_W / 2}" y="{y}" width="{BOX_W}" height="{BOX_H}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="0.8"{dash}/>'
                     f'<text x="{x}" y="{y + BOX_H / 2 + 4}" text-anchor="middle" fill="#222">{html.escape(r.label)}</text>')
    ly = H - 24
    parts.append(f'<text x="20" y="{ly + 4}" fill="#444">lag support (colour):</text>'
                 f'<line x1="140" y1="{ly}" x2="165" y2="{ly}" stroke="#185FA5" stroke-width="3"/><text x="170" y="{ly + 4}" fill="#444">A/B</text>'
                 f'<line x1="200" y1="{ly}" x2="225" y2="{ly}" stroke="#BA7517" stroke-width="3"/><text x="230" y="{ly + 4}" fill="#444">C bound only</text>'
                 f'<line x1="310" y1="{ly}" x2="335" y2="{ly}" stroke="#888780" stroke-width="3"/><text x="340" y="{ly + 4}" fill="#444">D none</text>'
                 f'<text x="410" y="{ly + 4}" fill="#444">share support (line):</text>'
                 f'<line x1="530" y1="{ly}" x2="555" y2="{ly}" stroke="#444" stroke-width="2"/><text x="560" y="{ly + 4}" fill="#444">A/B</text>'
                 f'<line x1="590" y1="{ly}" x2="615" y2="{ly}" stroke="#444" stroke-width="2" stroke-dasharray="7 3"/><text x="620" y="{ly + 4}" fill="#444">C/D</text>'
                 f'<text x="680" y="{ly + 4}" fill="#444">width = flow</text>')
    parts.append("</svg>")
    return "".join(parts)


def run_step5(p: pd.DataFrame, cfg: dict, write: bool = True) -> dict:
    anchors = lag_anchors(p)                            # data bounds first: effective ranges below read them
    pd.DataFrame({"anchor": list(anchors), "weeks": list(anchors.values()), "as_of": str(p.index.max())}).round(2).to_csv(
        step_outputs("step5_supply_graph") / "graph_lag_bounds.csv", index=False)
    edges = load_edges()
    eff = effective_ranges(edges, cfg)[0]                 # mid lags incl. the lag mix of Logitech's 10-K residual (G20)
    today = pd.Timestamp.today().normalize()
    shares = edge_shares(edges, cfg, today)
    pt = paths(eff, shares, cfg)
    flows = edge_flows(edges, pt)
    kern = pd.DataFrame({sc: kernel_asof(today, cfg, sc) for sc in ("low", "mid", "high")})
    kern.index.name = "lag_quarters"
    mean_lag = {sc: float((kernel_asof(today, cfg, sc) * kern.index).sum()) for sc in ("low", "mid", "high")}
    w = load_weights()
    k_hist = pd.DataFrame({r.published: kernel_asof(pd.Timestamp(r.published), cfg) for r in w.itertuples()}).T
    D = p["logi_sales_yoy"] + p["logi_st_gap"]
    y = p["nordic_consumer_yoy"]
    ok = p.index[p["regime"] != "supply_constrained"]
    fit = []
    for sc in ("low", "mid", "high"):
        d = pd.concat([y, propagate(D, cfg, 0, scenario=sc)], axis=1).loc[ok].dropna()
        fit.append({"kernel": f"graph ({sc} lags)", "corr_with_nordic_consumer_yoy": d.corr().iloc[0, 1], "n": len(d)})
    for k in range(4):
        d = pd.concat([y, D.shift(k)], axis=1).loc[ok].dropna()
        fit.append({"kernel": f"single lag {k}q", "corr_with_nordic_consumer_yoy": d.corr().iloc[0, 1], "n": len(d)})
    fit = pd.DataFrame(fit)
    by_route = pt.assign(route=pt["path"].str.extract(r"logitech > (\w+)|gn > (\w+)").bfill(axis=1).iloc[:, 0]).groupby(["brand", "route"]).apply(
        lambda g: pd.Series({"weight": g["weight"].sum(), "lag_weeks": np.average(g["lag_weeks"], weights=g["weight"])}), include_groups=False).reset_index()
    resid = residual_run(cfg, today)
    svg = render_svg(edges, flows, residual_lag_lines(edges, resid))
    sgc = cfg["supply_graph"]
    checks = lag_checks(edges, anchors, sgc["little_law_tolerance"])
    pg = path_grades(edges, pt)
    tg = tier_grades(edges, flows)
    gaps = data_gaps(edges, flows)
    mc = monte_carlo(edges, cfg)
    tor = tornado(edges, cfg)
    s4 = compare(p, cfg, eff, pt, mc)
    s4 = {**s4, "decomposition": decompose(edges, eff, pt, cfg), "continuous": continuous_lag_table(p, cfg, s4["table"])}   # G21
    out = {"checks": checks, "path_grades": pg, "tier_grades": tg, "gaps": gaps, "mc": mc, "tornado": tor,
           "edges": edges.assign(share_value=shares.reindex(edges["edge_id"]).values, flow=flows.reindex(edges["edge_id"]).values),
           "paths": pt, "kernel": kern, "mean_lag_q": mean_lag, "kernel_history": k_hist, "fit": fit, "by_route": by_route, "svg": svg, "step4_check": s4, "residual": resid, "panel": p}
    if write:
        d = step_outputs("step5_supply_graph")
        out["edges"].round(4).to_csv(d / "graph_edges_today.csv", index=False)
        pt.round(4).to_csv(d / "graph_paths.csv", index=False)
        kern.round(4).to_csv(d / "graph_kernel.csv")
        k_hist.round(4).to_csv(d / "graph_kernel_history.csv")
        fit.round(3).to_csv(d / "graph_lag_fit.csv", index=False)
        s4["table"].round(2).to_csv(d / "graph_vs_step4.csv", index=False)
        resid["evidence"].to_csv(d / "graph_residual_evidence.csv", index=False)
        resid["lag_by_p"].round(2).to_csv(d / "graph_residual_lag_by_p.csv", index=False)
        s4["data"].round(3).to_csv(d / "graph_vs_step4_data.csv", index=False)
        s4["decomposition"].round(3).to_csv(d / "graph_vs_step4_decomposition.csv", index=False)
        s4["continuous"].round(3).to_csv(d / "graph_vs_step4_continuous_lag.csv", index=False)
        by_route.round(4).to_csv(d / "graph_by_route.csv", index=False)
        (d / "supply_graph.svg").write_text(svg)
        checks.round(2).to_csv(d / "graph_lag_checks.csv", index=False)
        pg.round(4).to_csv(d / "graph_path_grades.csv", index=False)
        tg.round(3).to_csv(d / "graph_tier_grades.csv")
        gaps.round(4).to_csv(d / "graph_data_gaps.csv", index=False)
        mc["kernel_band"].round(3).to_csv(d / "graph_kernel_band.csv")
        pd.DataFrame([mc["mean_lag_weeks"]]).round(2).to_csv(d / "graph_mean_lag_mc.csv", index=False)
        tor.round(2).to_csv(d / "graph_tornado.csv", index=False)
        from supply_graph_timeline import node_states
        node_states(p, cfg).to_csv(d / "graph_timeline.csv", index=False)
        from odm_lead import lead_test
        lt = lead_test(p)
        if len(lt):
            lt.round(3).to_csv(d / "odm_lead_test.csv", index=False)
        from relationship_breaks import run_relationship_breaks, breaks_md     # step 5c (G22)
        out["relationship_breaks"] = run_relationship_breaks(p, cfg)
        from event_study_report import run_event_study                           # step 5d: shocks vs breaks, the incident (G23)
        out["event_study"] = run_event_study(p, cfg)
        from signal_lag import run as signal_run                                 # physical dwell vs order-signal lag (G25)
        from signal_lag_report import section_md as signal_md, write as signal_write
        out["signal_lag"] = signal_run(cfg, today, s4["continuous"])
        signal_write(out["signal_lag"], d)
        from route_propagation_report import run_route_propagation              # step 5e: CH by route (G26) -> route_propagation.md
        out["route_propagation"] = run_route_propagation(p, cfg)
        from route_nowcast_report import run_route_nowcast                      # step 5f: route proxies nowcast Logitech's unreported quarter (G27)
        out["route_nowcast"] = run_route_nowcast(p, cfg)
        from cycle_challenger_report import run_cycle_challenger                # step 5g: industry-cycle regression, pre-registered Q4 challenger (G29)
        out["cycle_challenger"] = run_cycle_challenger(p, cfg)
        from cycle_decomposition import run as run_cycle_decomposition          # step 5g addendum: GRi / GR / CYC gap to CH (G30)
        out["cycle_decomposition"] = run_cycle_decomposition(p, cfg)
        (d / "step5_report.md").write_text(_report(out, cfg) + signal_md(out["signal_lag"], cfg) + breaks_md(out["relationship_breaks"])
                                           + out["event_study"]["md"])
    return out


def _report(o: dict, cfg: dict) -> str:
    m, f = o["mean_lag_q"], o["fit"].set_index("kernel")["corr_with_nordic_consumer_yoy"]
    wq = cfg["supply_graph"]["weeks_per_quarter"]
    return "\n".join([
        "# Step 5 — Supply-chain structure as a graph\n",
        "Edges: `config/supply_graph.csv` (share formula, reorder lag in weeks, who holds the inventory, disclosed or not, evidence). "
        "Logitech's customer shares change by fiscal year and are read from each 10-K (`config/supply_graph_weights.csv`, with the "
        "sentence and filing date); `graph_asof(date)` uses only 10-Ks filed by that date. Named shares: `config/model.yaml` → `supply_graph`.\n",
        "![graph](supply_graph.svg)\n",
        "## Paths and lag\n",
        f"{len(o['paths'])} paths from Nordic to end demand. Weighted mean lag (physical dwell; the order-signal lag is in its own section below): **{m['mid'] * wq:.0f} weeks ({m['mid']:.2f} quarters)** with the "
        f"mid lags; {m['low'] * wq:.0f} weeks (low) to {m['high'] * wq:.0f} weeks (high). The single-chain lag (step 4) assumed every unit crossed a "
        "distributor; in the graph most of Logitech's flow goes to Amazon, other retail or its own site directly, which is why the mean is shorter.\n",
        "By route (Logitech / GN → first customer):\n", o["by_route"].round(3).to_markdown(index=False), "",
        "Lag kernel (weight on each quarterly lag):\n", o["kernel"].round(3).to_markdown(), "",
        "Kernel with the graph known at each 10-K filing date (point in time):\n", o["kernel_history"].round(3).to_markdown(), "",
        "## How reliable is each link? (grades A-D for share and lag separately)\n",
        "A = audited filing measuring the edge; B = filing floor or disclosure combined with an estimate; C = indirect (proxy on a broader "
        "base, verbal, one snapshot); D = assumption — either not public or not yet collected. An edge is as reliable as the weaker of its "
        "share and its lag; a path as its weakest edge.\n",
        "Share of the flow crossing each tier, by grade:\n", o["tier_grades"].round(2).to_markdown(), "",
        f"Paths graded A-C end to end: {o['path_grades'].loc[o['path_grades']['grade'] != 'D', 'weight'].sum():.0%} of the flow. "
        "Every route ends at the retail tier, where weeks-on-hand are not public (other retailers) or not collected (Amazon), so no path "
        "is data-backed end to end.\n",
        "Lag ranges checked against inventory cover (Little's law: a tier's reorder lag cannot reasonably exceed the time a unit sits "
        "in its stock):\n", o["checks"].round(1).to_markdown(index=False), "",
        f"Monte Carlo ({cfg['supply_graph']['mc_draws']} draws, every share and lag triangular low/mid/high): weighted mean lag "
        f"{o['mc']['mean_lag_weeks']['p5']:.1f}-{o['mc']['mean_lag_weeks']['p95']:.1f} weeks (90%), median {o['mc']['mean_lag_weeks']['p50']:.1f}.\n",
        "Kernel band (weight per quarterly lag, 5th / 50th / 95th percentile):\n", o["mc"]["kernel_band"].round(3).to_markdown(), "",
        "Which inputs move the lag most (swing low → high, everything else at mid):\n", o["tornado"].head(8).round(2).to_markdown(index=False), "",
        "Data gaps (D-graded shares and lags):\n", o["gaps"].round(3).to_markdown(index=False), "",
        residual_section(o["residual"]),
        step4_section(o["step4_check"]),
        gap_section(o["step4_check"], o["panel"], cfg),
        "## What the data can and cannot tell\n",
        o["fit"].round(3).to_markdown(index=False), "",
        f"Every kernel correlates about equally with Nordic's consumer revenue ({f.min():.2f}–{f.max():.2f}): 16 autocorrelated quarters cannot "
        "separate a 1-, 2- or 3-quarter lag, so the lag comes from the structure and the data only check it is consistent. In the walk-forward "
        "back-test (step 6, model GR) the graph kernel equals the single lag-2 model at h=2 (both collapse onto the latest known quarter) and "
        "adds nothing at h=1. The graph's value is structural: where the lag comes from, which routes carry the flow, and scenarios.\n"])
