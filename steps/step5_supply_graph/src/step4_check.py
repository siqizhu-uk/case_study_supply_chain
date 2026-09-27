"""Step 5 vs step 4 (decision G19): does the supply graph's lag agree with step 4's reasoned lag and its measured lag?
A check only - nothing here changes the graph, the kernel or any forecast.

Three comparisons, all in weeks (13 per quarter):
  total   graph flow-weighted mean lag (mid, Monte Carlo 90%) vs step 4 reasoned low / mid / high (config lag_weeks)
  tier    the same split into two stages both sides can name:
            upstream   Nordic -> finished device at the brand (step 4: odm_to_component + oem_to_odm_build)
            downstream brand -> consumer (step 4: distributor_to_oem + sell_out_to_distributor)
          graph side = flow-weighted mean over paths of the edge lags before / after the brand node
  data    the lag (0-4 quarters) with the highest correlation with Nordic consumer YoY, for step 4's driver and the graph's
          driver, with and without the supply-constrained regime: the two steps measure on different bases
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BRANDS = ("logitech", "gn")
UPSTREAM = ("odm_to_component", "oem_to_odm_build")
DOWNSTREAM = ("distributor_to_oem", "sell_out_to_distributor")


def stage_lags(edges: pd.DataFrame, pt: pd.DataFrame) -> pd.DataFrame:
    """Per path: weeks before the brand node (upstream) and after it (downstream); the sum equals the path lag."""
    lag = {}
    for r in edges.itertuples():
        lag[(r.src, r.dst, r.brand)] = float(pd.to_numeric(r.lag_weeks_mid, errors="coerce") or 0.0)
    rows = []
    for r in pt.itertuples():
        n = r.path.split(" > ")
        cut = next(i for i, x in enumerate(n) if x in BRANDS)
        w = [lag.get((a, b, r.brand), lag.get((a, b, "all"), 0.0)) for a, b in zip(n, n[1:])]
        rows.append({"brand": r.brand, "path": r.path, "weight": r.weight, "upstream": sum(w[:cut]), "downstream": sum(w[cut:]),
                     "direct_to_retail": not any(x in ("ingram", "tdsynnex") for x in n),
                     "residual_route": n[cut + 1] == "other_retail"})
    return pd.DataFrame(rows)


def best_lag(y: pd.Series, x: pd.Series, keep: pd.Index, max_q: int = 4) -> dict:
    c = {k: pd.concat([y, x.shift(k)], axis=1).loc[keep].dropna() for k in range(max_q + 1)}
    r = {k: float(d.corr().iloc[0, 1]) for k, d in c.items() if len(d) > 5}
    k = max(r, key=r.get)
    second = sorted(r.values())[-2]
    return {"best_lag_q": k, "best_lag_weeks": 13 * k, "corr": r[k], "runner_up_corr": second, "n": len(c[k]),
            "corr_by_lag": " / ".join(f"{v:.2f}" for v in r.values())}


def compare(p: pd.DataFrame, cfg: dict, edges: pd.DataFrame, pt: pd.DataFrame, mc: dict) -> dict:
    lw = cfg["lag_weeks"]
    reasoned = {sc: sum(v[sc] for v in lw.values()) for sc in ("low", "mid", "high")}
    st = stage_lags(edges, pt)
    wavg = lambda col, m=slice(None): float(np.average(st.loc[m, col], weights=st.loc[m, "weight"]))   # noqa: E731
    g_total = wavg("upstream") + wavg("downstream")
    mcl = mc["mean_lag_weeks"]
    direct = float(st.loc[st["direct_to_retail"], "weight"].sum() / st["weight"].sum())
    total = pd.DataFrame([
        {"measure": "total lag, sell-out -> Nordic revenue", "step4_low": reasoned["low"], "step4_mid": reasoned["mid"], "step4_high": reasoned["high"],
         "graph_mid": g_total, "graph_mc_p5": mcl["p5"], "graph_mc_p95": mcl["p95"], "gap_mid_weeks": g_total - reasoned["mid"]},
        {"measure": "upstream: Nordic -> finished device at the brand", "step4_low": sum(lw[k]["low"] for k in UPSTREAM),
         "step4_mid": sum(lw[k]["mid"] for k in UPSTREAM), "step4_high": sum(lw[k]["high"] for k in UPSTREAM),
         "graph_mid": wavg("upstream"), "graph_mc_p5": np.nan, "graph_mc_p95": np.nan, "gap_mid_weeks": wavg("upstream") - sum(lw[k]["mid"] for k in UPSTREAM)},
        {"measure": "downstream: brand -> consumer", "step4_low": sum(lw[k]["low"] for k in DOWNSTREAM),
         "step4_mid": sum(lw[k]["mid"] for k in DOWNSTREAM), "step4_high": sum(lw[k]["high"] for k in DOWNSTREAM),
         "graph_mid": wavg("downstream"), "graph_mc_p5": np.nan, "graph_mc_p95": np.nan, "gap_mid_weeks": wavg("downstream") - sum(lw[k]["mid"] for k in DOWNSTREAM)},
        {"measure": "downstream, routes through Ingram / TD Synnex only", "step4_low": sum(lw[k]["low"] for k in DOWNSTREAM),
         "step4_mid": sum(lw[k]["mid"] for k in DOWNSTREAM), "step4_high": sum(lw[k]["high"] for k in DOWNSTREAM),
         "graph_mid": wavg("downstream", ~st["direct_to_retail"]), "graph_mc_p5": np.nan, "graph_mc_p95": np.nan,
         "gap_mid_weeks": wavg("downstream", ~st["direct_to_retail"]) - sum(lw[k]["mid"] for k in DOWNSTREAM)}])
    # the 10-K residual ('other_retail') mixes smaller distributors with retailers: give it the distributor routes' downstream lag
    via_down = wavg("downstream", ~st["direct_to_retail"])
    alt = st.assign(downstream=np.where(st["residual_route"], via_down, st["downstream"]))
    alt_total = float(np.average(alt["upstream"] + alt["downstream"], weights=alt["weight"]))
    total = pd.concat([total, pd.DataFrame([{"measure": "total, if the whole 10-K residual went through a distributor (p = 1)", "step4_low": reasoned["low"],
                                            "step4_mid": reasoned["mid"], "step4_high": reasoned["high"], "graph_mid": alt_total,
                                            "graph_mc_p5": np.nan, "graph_mc_p95": np.nan, "gap_mid_weeks": alt_total - reasoned["mid"]}])], ignore_index=True)
    total["graph_inside_step4_range"] = (total["graph_mid"] >= total["step4_low"]) & (total["graph_mid"] <= total["step4_high"])

    y = p["nordic_consumer_yoy"]
    drivers = {"step 4 driver (" + cfg["regression"]["driver"] + ")": p[cfg["regression"]["driver"]],
               "graph driver (Logitech sell-in + sell-through gap)": p["logi_sales_yoy"] + p["logi_st_gap"]}
    samples = {"all quarters": p.index, "ex supply-constrained": p.index[p["regime"] != "supply_constrained"]}
    data = pd.DataFrame([{"driver": dn, "sample": sn, **best_lag(y, dx, keep)} for dn, dx in drivers.items() for sn, keep in samples.items()])
    resid = float(st.loc[st["residual_route"], "weight"].sum() / st["weight"].sum())
    return {"table": total, "data": data, "direct_share": direct, "residual_share": resid, "stages": st}


def section(c: dict) -> str:
    t, d = c["table"], c["data"]
    tot = t.iloc[0]
    down, via = t.iloc[2], t.iloc[3]
    return "\n".join([
        "## Consistency with step 4 (check only, decision G19)\n",
        "Step 4 reasoned the lag tier by tier (config `lag_weeks`); the graph sets its own edge lags (`config/supply_graph.csv`). "
        "Nothing ties them in code, so this compares them. Weeks; the graph side is flow-weighted over all paths.\n",
        t.round(1).to_markdown(index=False), "",
        f"**Where the gap comes from.** Graph {tot['graph_mid']:.1f} weeks vs step 4 {tot['step4_mid']:.0f} ({tot['gap_mid_weeks']:+.1f}); the graph's whole "
        f"Monte Carlo band ({tot['graph_mc_p5']:.1f}-{tot['graph_mc_p95']:.1f}) sits below step 4's mid but inside its low-high range. Upstream agrees "
        f"({t.iloc[1]['graph_mid']:.1f} vs {t.iloc[1]['step4_mid']:.0f}). The gap is downstream: step 4 sends every unit brand -> distributor -> retailer "
        f"({down['step4_mid']:.0f} weeks); the graph sends {c['direct_share']:.0%} of the flow past Ingram / TD Synnex ({down['graph_mid']:.1f} weeks on average), "
        f"because Amazon is supplied directly and only part of the unnamed 10-K residual ({c['residual_share']:.0%} of the flow) goes through smaller "
        f"distributors (p, section above; the old setting p = 0 treated it all as direct retail). If all of it went through a distributor, the graph total would be "
        f"{t.iloc[4]['graph_mid']:.1f} weeks ({t.iloc[4]['gap_mid_weeks']:+.1f} vs step 4). On the Ingram / TD Synnex routes alone the graph has "
        f"{via['graph_mid']:.1f} weeks, close to step 4's {via['step4_mid']:.0f}.\n",
        "**Against the data.** Lag with the highest correlation with Nordic consumer YoY (quarters; correlations at lags 0-4):\n",
        d.round(2).to_markdown(index=False), "",
        "The measured peak depends on the driver and the sample, and the runner-up is close in every row: the data place the lag at "
        "1-3 quarters (13-39 weeks) without separating them (the same point as the fit table below). Step 4's 2-quarter peak (r 0.90) "
        "uses its own driver (its supply-constrained quarters have no driver data, so both samples are the same 15 quarters). "
        "The graph's ~1.4 quarters is at the short end of what the data allow; no row puts the peak below 2 quarters, so the data lean "
        "towards step 4, but with n 15-18 and runner-ups within 0.03-0.11 this is a lean, not a contradiction.\n"])
