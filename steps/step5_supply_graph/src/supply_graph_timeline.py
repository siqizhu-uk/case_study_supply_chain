"""Step 5b — the supply graph quarter by quarter (dashboard tab 'Chain over time').

The structure (nodes, links) is fixed; what moves each quarter is
    node inventory   cover in weeks where a company discloses it (Nordic, Arrow / Avnet, Logitech, Ingram, TD Synnex),
                     coloured by its percentile in the node's own 2020-2026 history (blue lean ... red heavy; grey = no data)
    node flow        YoY growth of what the node sells (sell-out proxy at end demand)
    channel state    Logitech channel weeks vs target, GN channel drain since its first quarter (relative, no anchor),
                     Nordic distributor state (verbal, coded); the quarter is labelled with the data-dated channel state
                     (step 3b cycle_state.csv, P92)
    edge weight      Logitech's customer shares from the 10-K known at the quarter (point in time)
    edge lag bound   Little's law: a tier's reorder lag <= its inventory cover that quarter (data); the regime multiplier
                     of the hand-set config regimes (supply-constrained 2x) is an assumption and labelled so. E14 carries
                     its p-mixed mid lag (G20).
Lags are never observed quarter by quarter; only their data bound moves.
"""
from __future__ import annotations

import html
import json

import numpy as np
import pandas as pd

from core.config import ROOT
from supply_graph import load_edges, edge_shares, paths, NODES
from supply_graph_report import _xy, edge_style, edge_flows, mixed_lags, xbrl_dio, gn_dio, BOX_W, BOX_H, W, LAYER_H

S3 = ROOT / "steps" / "step3_inventory_mechanism" / "outputs"
COVER = {"nordic": "nordic_inv_days", "nordic_distributors": "comp_dist_dio_avg", "logitech": "logi_inv_days",
         "ingram": "ingm_inv_days", "tdsynnex": "snx_inv_days", "amazon": "amazon_dio", "other_retail": "bestbuy_dio", "gn": "gn_dio"}
FLOW = {"nordic": ("nordic_consumer_yoy", "consumer rev"), "logitech": ("logi_sales_yoy", "sales"), "gn": ("gn_periph_yoy", "Ent+Gaming"),
        "ingram": ("ingm_sales_yoy", "sales"), "tdsynnex": ("snx_sales_yoy", "sales"), "consumers": ("sellout_proxy_yoy", "sell-out proxy")}
ANCHOR_NODE = {"arrow_avnet_weeks": "nordic_distributors", "logi_inv_weeks": "logitech", "ingram_weeks": "ingram", "tdsynnex_weeks": "tdsynnex",
               "amazon_weeks": "amazon", "retail_weeks": "other_retail", "gn_inv_weeks": "gn"}
TEXT_METRICS = ("regime", "cycle_state")                          # per-quarter labels, not numbers
ANCHORED_CHANNEL = ("logitech",)                                  # channel index anchored on 'at target' statements; others relative


def _q(s) -> pd.PeriodIndex:
    return pd.PeriodIndex(pd.Index(s).astype(str), freq="Q")


def _channel_weeks(ci: pd.DataFrame) -> pd.Series:
    """Channel weeks from the stored dollars (excess / weekly sell-in, step 3's formula): the stored weeks are rounded to 0.01,
    which can flip the one-decimal label against step 3's own text (-2.055 stored as -2.05 prints -2.0, not -2.1)."""
    from channel_index import WEEKS_Q                                  # steps/step3_inventory_mechanism/src
    return ci["excess_usd"] / (ci["sell_in"] / WEEKS_Q)


def node_states(p: pd.DataFrame, cfg: dict, first: str = "2020Q1") -> pd.DataFrame:
    """Long table: quarter, node, metric, value."""
    f = pd.read_csv(S3 / "factors_quarterly.csv")
    f.index = _q(f["quarter"])
    li = pd.read_csv(S3 / "channel_index_logitech.csv")
    li.index = _q(li["quarter"])
    gi = pd.read_csv(S3 / "channel_index_gn.csv")
    gi.index = _q(gi["quarter"])
    d = p.copy()
    d["comp_dist_dio_avg"] = f["comp_dist_dio_avg"].reindex(d.index)
    d["nordic_ind_health_yoy"] = d["nordic_ind_health"].pct_change(4, fill_method=None) * 100
    d["logi_channel_weeks"] = _channel_weeks(li).reindex(d.index)
    d["gn_channel_weeks"] = _channel_weeks(gi).reindex(d.index)
    dio = xbrl_dio()
    dio.index = _q(dio.index)
    d["amazon_dio"], d["bestbuy_dio"] = dio["amazon"].reindex(d.index), dio["bestbuy"].reindex(d.index)
    g = gn_dio()
    g.index = _q(g.index)
    d["gn_dio"] = g.reindex(d.index)
    d["nordic_backlog_cover"] = d["nordic_backlog"] / d["nordic_rev"]
    cs = pd.read_csv(S3 / "cycle_state.csv")
    d["cycle_state"] = pd.Series(cs["state_nordic"].values, index=_q(cs["quarter"])).reindex(d.index)
    d = d[d.index >= pd.Period(first, "Q")]
    rows = []
    for q, r in d.iterrows():
        for node, col in COVER.items():
            rows.append((str(q), node, "cover_weeks", r[col] / 7 if pd.notna(r[col]) else np.nan))
        for node, (col, _) in FLOW.items():
            rows.append((str(q), node, "flow_yoy", r.get(col, np.nan)))
        rows += [(str(q), "logitech", "channel_weeks", r["logi_channel_weeks"]), (str(q), "gn", "channel_weeks", r["gn_channel_weeks"]),
                 (str(q), "nordic_distributors", "state", r["nordic_dist_state"]), (str(q), "logitech", "st_gap", r["logi_st_gap"]),
                 (str(q), "nordic", "backlog_cover", r["nordic_backlog_cover"]),
                 (str(q), "all", "regime", r["regime"]), (str(q), "all", "cycle_state", r["cycle_state"])]
    return pd.DataFrame(rows, columns=["quarter", "node", "metric", "value"])


def _frames(states: pd.DataFrame, cfg: dict) -> tuple[list[str], dict]:
    """Per quarter: node colour / label lines, edge widths (10-K as of the quarter), edge lag bounds."""
    num = states[~states["metric"].isin(TEXT_METRICS)].copy()
    num["value"] = pd.to_numeric(num["value"], errors="coerce")
    cov = num[num["metric"] == "cover_weeks"].pivot(index="quarter", columns="node", values="value")
    pct = cov.rank(pct=True)                                          # percentile within each node's own history
    wide = num.pivot_table(index=["quarter", "node"], columns="metric", values="value")
    ch = num[num["metric"] == "channel_weeks"].dropna(subset=["value"])
    ch_start = ch.groupby("node")["quarter"].min().to_dict()          # a relative channel index counts from its first quarter
    reg = states[states["metric"] == "regime"].set_index("quarter")["value"]          # hand-set config regime (lag multiplier)
    cst = states[states["metric"] == "cycle_state"].set_index("quarter")["value"].fillna("")   # data-dated channel state (label)
    mult = {k: v.get("lag_multiplier", 1.0) for k, v in cfg["regimes"].items()}
    edges = load_edges()
    mixed = mixed_lags(edges, cfg)
    mid_lag = dict(zip(mixed["edge_id"], pd.to_numeric(mixed["lag_weeks_mid"], errors="coerce")))   # E14 p-mixed (G20)
    is_mixed = set(edges.loc[edges["lag_mix"].astype(str).str.len() > 0, "edge_id"])
    quarters = sorted(cov.index)
    frames = {}
    for q in quarters:
        per = pd.Period(q, "Q")
        sh = edge_shares(edges, cfg, per.end_time)
        fl = edge_flows(edges, paths(edges, sh, cfg))
        nodes = {}
        for n in pd.read_csv(NODES)["node"]:
            v = wide.loc[(q, n)] if (q, n) in wide.index else pd.Series(dtype=float)
            lines = []
            if pd.notna(v.get("cover_weeks", np.nan)):
                lines.append(f"stock {v['cover_weeks']:.1f} wk")
            if pd.notna(v.get("channel_weeks", np.nan)):
                lines.append(_channel_line(n, v["channel_weeks"], ch_start.get(n, "")))
            if pd.notna(v.get("state", np.nan)):
                lines.append(f"state {v['state']:+.1f}")
            if pd.notna(v.get("backlog_cover", np.nan)):
                lines.append(f"backlog {v['backlog_cover']:.1f}x qtr revenue")
            if pd.notna(v.get("flow_yoy", np.nan)) and len(lines) < 3:
                lines.append(f"{FLOW.get(n, ('', 'flow'))[1]} {v['flow_yoy']:+.0f}% YoY")
            pc = pct.loc[q, n] if n in pct.columns and pd.notna(pct.loc[q, n]) else None
            nodes[n] = {"pct": None if pc is None else round(float(pc), 3), "lines": lines}
        e_out = {}
        for r in edges.itertuples():
            s = sh.get(r.edge_id, np.nan)
            node = ANCHOR_NODE.get(r.lag_anchor)
            bound = wide.loc[(q, node), "cover_weeks"] if node and (q, node) in wide.index else np.nan
            mid = mid_lag.get(r.edge_id, np.nan)
            e_out[r.edge_id] = {"share": None if pd.isna(s) else round(float(s), 3), "flow": round(float(fl.get(r.edge_id, 0.0)), 3),
                                "bound": None if pd.isna(bound) else round(float(bound), 1),
                                "lag_regime": None if pd.isna(mid) else round(float(mid) * mult.get(reg.get(q, "normal"), 1.0), 1),
                                "mixed": r.edge_id in is_mixed}
        frames[q] = {"regime": reg.get(q, ""), "state": cst.get(q, ""), "nodes": nodes,
                     "edges": e_out, "reported": int(sum(1 for n in nodes.values() if n["pct"] is not None)), "of": int(len(cov.columns))}
    return quarters, frames


def _channel_line(node: str, weeks: float, start: str) -> str:
    """Logitech's index is anchored on 'at target' statements; GN's has no anchor, so it reads as a change since its start."""
    return f"channel {weeks:+.1f} wk vs target" if node in ANCHORED_CHANNEL else f"channel {weeks:+.1f} wk since {start} (relative)"


def tab_html(p: pd.DataFrame, cfg: dict) -> str:
    states = node_states(p, cfg)
    quarters, frames = _frames(states, cfg)
    full = [i for i, q in enumerate(quarters) if frames[q]["reported"] >= frames[q]["of"] - 1]
    start = full[-1] if full else len(quarters) - 1                # open on the latest quarter every disclosing node has reported
    nodes = pd.read_csv(NODES)
    xy = _xy(nodes)
    edges = load_edges()
    H = 40 + int(nodes["layer"].max()) * LAYER_H + BOX_H + 30
    svg = [f'<svg id=tl-svg viewBox="0 0 {W} {H}" width="100%" font-family="-apple-system,Segoe UI,Helvetica,Arial" font-size="11">',
           '<defs><marker id="tah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="context-stroke" stroke-width="1.5"/></marker></defs>']
    for r in edges.itertuples():
        (x1, y1), (x2, y2) = xy[r.src], xy[r.dst]
        col, dash = edge_style(r)
        d = (f"M{x1 + (BOX_W / 2 if x2 > x1 else -BOX_W / 2)} {y1 + BOX_H / 2} L{x2 - (BOX_W / 2 if x2 > x1 else -BOX_W / 2)} {y2 + BOX_H / 2}"
             if y1 == y2 else f"M{x1} {y1 + BOX_H} L{x2} {y2}")
        svg.append(f'<path id="tle-{r.edge_id}" d="{d}" fill="none" stroke="{col}" stroke-width="1" stroke-opacity="0.8"{dash} marker-end="url(#tah)">'
                   f'<title id="tlt-{r.edge_id}"></title></path>')
    for r in nodes.itertuples():
        x, y = xy[r.node]
        svg.append(f'<rect id="tln-{r.node}" x="{x - BOX_W / 2}" y="{y - 6}" width="{BOX_W}" height="{BOX_H + 26}" rx="6" fill="#eee" stroke="#999" stroke-width="0.8"/>'
                   f'<text x="{x}" y="{y + 8}" text-anchor="middle" font-weight="600" fill="#222">{html.escape(r.label)}</text>'
                   f'<text id="tl1-{r.node}" x="{x}" y="{y + 23}" text-anchor="middle" fill="#333"></text>'
                   f'<text id="tl2-{r.node}" x="{x}" y="{y + 37}" text-anchor="middle" fill="#555"></text>'
                   f'<text id="tl3-{r.node}" x="{x}" y="{y + 50}" text-anchor="middle" fill="#555"></text>')
    svg.append("</svg>")
    data = json.dumps({"quarters": quarters, "frames": frames}, allow_nan=False, default=lambda o: None)
    legend = ("<div class=src style='margin:4px 0'>Node colour = inventory cover vs the node's own 2020-2026 history: "
              "<span style='background:#9ecae1;padding:0 6px'>lean</span> <span style='background:#eee;padding:0 6px'>middle</span> "
              "<span style='background:#fc9272;padding:0 6px'>heavy</span> <span style='background:#f6f6f6;border:1px dashed #999;padding:0 6px'>no data</span>. "
              "Edge width = share of the Logitech + GN slice (Logitech's 10-K as known that quarter); colour = support for the lag, solid / dashed = support for the share (step 5). "
              "Hover an edge: its lag's data bound that quarter (inventory cover, Little's law) and the regime-adjusted lag (assumption: mid lag, "
              "E14 p-mixed (G20), times the lag multiplier of the hand-set config regime; P92: the data-dated state differs).</div>")
    return (f"<h2>The chain over time (step 5b)</h2><p class=note>Same nodes and links every quarter; inventory, flow and channel "
            "state move with the data. The label shows the data-dated channel state (step 3b). Lags are not observed quarter by quarter: "
            "only their data bound (inventory cover) moves; the regime multiplier is an assumption. Series and sources: the 'Data & time "
            "series' tab.</p>"
            "<div style='display:flex;gap:10px;align-items:center;margin:8px 0'><button id=tl-play style='padding:4px 12px'>▶ play</button>"
            f"<input id=tl-q type=range min=0 max={len(quarters) - 1} value={start} style='flex:1'>"
            "<b id=tl-label style='min-width:360px'></b></div>" + "".join(svg) + legend + _TL_JS.replace("__DATA__", data))


_TL_JS = """<script>
(function(){
  var D=__DATA__, slider=document.getElementById('tl-q'), label=document.getElementById('tl-label'), btn=document.getElementById('tl-play'), timer=null;
  function colour(p){ if(p===null) return '#f6f6f6'; if(p<0.34) return '#9ecae1'; if(p>0.66) return '#fc9272'; return '#eeeeee'; }
  function show(i){
    var q=D.quarters[i], f=D.frames[q]; label.textContent=q+' · channel state (data-dated): '+(f.state||'n/a')+(f.reported<f.of-1?' · partial: '+f.reported+' of '+f.of+' stock nodes reported':'');
    Object.keys(f.nodes).forEach(function(n){
      var s=f.nodes[n], r=document.getElementById('tln-'+n); if(!r) return;
      r.setAttribute('fill',colour(s.pct)); r.setAttribute('stroke-dasharray', s.pct===null?'4 3':'');
      for(var k=1;k<=3;k++){ var t=document.getElementById('tl'+k+'-'+n); if(t) t.textContent=s.lines[k-1]||''; }
    });
    Object.keys(f.edges).forEach(function(e){
      var s=f.edges[e], el=document.getElementById('tle-'+e), tt=document.getElementById('tlt-'+e); if(!el) return;
      el.setAttribute('stroke-width', 0.8+6*Math.min(1,s.flow||0));
      if(tt) tt.textContent=e+': share of source '+(s.share===null?'n/a':s.share)+' · flow '+Math.round((s.flow||0)*1000)/10+'% of slice'+(s.bound===null?'':' · lag bound '+s.bound+' wk (inventory cover)')+(s.lag_regime===null?'':' · regime-adjusted lag '+s.lag_regime+' wk (assumption: '+(s.mixed?'p-mixed mid (G20) × ':'mid × ')+'multiplier of hand-set config regime '+f.regime+'; P92)');
    });
  }
  slider.addEventListener('input',function(){ show(+slider.value); });
  btn.addEventListener('click',function(){
    if(timer){ clearInterval(timer); timer=null; btn.textContent='▶ play'; return; }
    btn.textContent='❚❚ pause'; if(+slider.value>=D.quarters.length-1) slider.value=0;
    timer=setInterval(function(){ var i=+slider.value+1; if(i>=D.quarters.length){ clearInterval(timer); timer=null; btn.textContent='▶ play'; return; } slider.value=i; show(i); },900);
  });
  show(+slider.value);
})();
</script>"""
