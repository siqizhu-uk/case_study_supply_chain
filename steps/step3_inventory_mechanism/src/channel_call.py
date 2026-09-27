"""Step 3e — the channel call for the next three prints: state, direction, a revenue adjustment range with its formula,
the forecast line it should be compared with, and the questions for the call.

  Logitech (Q2 FY27): refill = -W x (guided sell-in / 13) x refill share x supply availability
      W = channel excess weeks at 2026Q2: low = latest-anchor reading, mid = mean(latest-anchor, all-anchor),
      high = the most negative of (all-anchor, alternative start) (decision D21)
  Nordic (Q3 2026):   distributor safety stock = extra weeks x (guided revenue / 13) x distribution share
      (a pull-forward: the same amount is a payback risk for H1 2027)
  GN (Q3 2026):       Enterprise organic = sell-out growth - gap; adjustment = (that - forecast mid) x Q3 2025 base

watch_flag = receivables growing >dso_flag_days faster than revenue (DSO up YoY) while the channel is being filled
(Logitech: sell-in > sell-through; Nordic: coded distributor state > 0). It is a question for the call, not a verdict
of channel stuffing: a back-end-loaded quarter or a shift to distributors with longer terms gives the same pattern.

Every coefficient is a {low, mid, high} in config/model.yaml inventory_mechanism.channel_call; the adjustment is the
product of the lows, mids and highs respectively (a deliberately wide, not a probabilistic, range).
"""
from __future__ import annotations

import pandas as pd

K = ("low", "mid", "high")


def _tri(d: dict) -> tuple[float, float, float]:
    return tuple(float(d[k]) for k in K)


def logitech_call(p: pd.DataFrame, f: pd.DataFrame, ch: dict, cfg: dict) -> dict:
    cc = cfg["inventory_mechanism"]["channel_call"]
    fc = cfg["forecast"]["logitech_2026Q3"]
    q = pd.Period("2026Q2", "Q")
    prim, alt = ch["logitech"], ch["logitech_alt"]
    w_all = float(prim["table"].loc[q, "excess_weeks"])
    last_anchor = prim["anchor_fit"]["anchors_used"][-1]
    w_latest = w_all - prim["anchor_fit"]["anchor_weeks"][last_anchor]
    w_alt = float(alt["table"].loc[q, "excess_weeks"])
    weekly = (fc["guide_low"] + fc["guide_high"]) / 2 / 13
    rs, sa = _tri(cc["refill_share_next_q"]), _tri(cc["logitech_supply_availability"])
    # D21: the anchors drift down ~2 wk over 2025Q1-2026Q1 (target being lowered, or gaps coded high), so the
    # latest-anchor reading is the smallest deficit; mid = average of latest-anchor and all-anchor; high = the worst reading
    deficit = [-max(w_latest, w_all, w_alt), -(w_latest + w_all) / 2, -min(w_latest, w_all, w_alt)]
    adj = [max(d, 0) * weekly * r * s for d, r, s in zip(deficit, rs, sa)]
    dso_chg = float(f.loc[q, "logi_dso_yoy_chg"])
    gap = float(p.loc[q, "logi_st_gap"])
    cfg_line = float(sum((fc["signal_adjustments_usdm"] or {}).values()))   # hand-set lines; since F5 none: step 7c computes a data-weighted chain term
    return {"company": "logitech", "print": "Q2 FY27 net sales (Jul-Sep 2026)", "unit": "USDm",
            "state": f"lean: channel {w_all:+.1f} wk vs target (all anchors) / {w_latest:+.1f} wk (latest anchor {last_anchor}); sell-through ran {gap:+.0f} pts above sell-in in 2026Q2",
            "direction": "refill tailwind to sell-in, capped by the late-June supplier incident",
            "watch_flag": bool(gap < 0 and dso_chg > cc["dso_flag_days"]),
            "evidence": f"DSO {f.loc[q, 'logi_dso']:.0f} d ({dso_chg:+.1f} YoY); own DIO {f.loc[q, 'logi_dio']:.0f} d; FG growth - sales growth {f.loc[q, 'logi_fg_spread']:+.0f} pts; purchases {f.loc[q, 'logi_purchases_yoy']:+.0f}% YoY",
            "adj_low": adj[0], "adj_mid": adj[1], "adj_high": adj[2],
            "formula": f"deficit wk {deficit[0]:.1f}/{deficit[1]:.1f}/{deficit[2]:.1f} x USD {weekly:.0f}m/wk x refill {rs} x supply {sa}",
            "config_line": "forecast.logitech_2026Q3.signal_adjustments_usdm (sum of hand-set lines)", "config_value": cfg_line,
            "questions": "Weeks on hand at end-September vs target? How much of the refill was blocked by the supplier incident, and when does supply normalise?"}


def nordic_call(p: pd.DataFrame, f: pd.DataFrame, cfg: dict) -> dict:
    cc = cfg["inventory_mechanism"]["channel_call"]
    fc = cfg["forecast"]["nordic_2026Q3"]
    q = pd.Period("2026Q2", "Q")
    weekly = (fc["guide_low"] + fc["guide_high"]) / 2 / 13
    wk, sh = _tri(cc["nordic_safety_stock_weeks"]), _tri(cfg["inventory_mechanism"]["nordic_distribution_share"])
    adj = [w * weekly * s for w, s in zip(wk, sh)]
    mchp = f["mchp_disti_days"].dropna()
    pos = float(f["mchp_pos_in_10y_range"].dropna().iloc[-1])
    dso_chg = float(f.loc[q, "nordic_dso_yoy_chg"])
    state = p.loc[q, "nordic_dist_state"]
    cfg_line = fc["signal_adjustments_usdm"].get("capacity_worry_pull_in")
    return {"company": "nordic", "print": "Q3 2026 revenue", "unit": "USDm",
            "state": f"distribution restocking from a lean base (coded state {state:+.1f}); component distributors lean: Avnet {f.loc[q, 'avnet_dio']:.0f} d, Arrow {f.loc[q, 'arrow_dio']:.0f} d, Microchip distributor days {mchp.iloc[-1]:.0f} ({pos:.0%} of the way up its 10-year range)",
            "direction": "small Q3 upside (mostly in the guide); the same amount is a payback risk in H1 2027",
            "watch_flag": bool(state > 0 and dso_chg > cc["dso_flag_days"]),
            "evidence": f"own DIO {f.loc[q, 'nordic_dio']:.0f} d (forward {f.loc[q, 'nordic_fwd_dio']:.0f} d on the Q3 guide); inventory growth - revenue growth {f.loc[q, 'nordic_inv_spread']:+.0f} pts; DSO {f.loc[q, 'nordic_dso']:.0f} d ({dso_chg:+.1f} YoY; receivables {f.loc[q, 'nordic_ar_spread']:+.0f} pts faster than revenue)",
            "adj_low": adj[0], "adj_mid": adj[1], "adj_high": adj[2],
            "formula": f"extra distributor weeks {wk} x USD {weekly:.1f}m/wk x distribution share {sh}",
            "config_line": "forecast.nordic_2026Q3.signal_adjustments_usdm.capacity_worry_pull_in", "config_value": cfg_line,
            "questions": "Distributor weeks on hand and sell-through vs revenue in Q3? Split of the USD 217m inventory into wafers / WIP / finished goods? Why did receivables grow 2x revenue (timing, terms, or distributor mix)?"}


def gn_call(p: pd.DataFrame, ch: dict, cfg: dict) -> dict:
    cc = cfg["inventory_mechanism"]["channel_call"]
    fc = cfg["forecast"]["gn_2026Q3"]
    base = float(p.loc[pd.Period(fc["base_quarter"], "Q"), "gn_enterprise_dkk"])
    so, gp = _tri(cc["gn_sellout_growth_next_q_pct"]), _tri(cc["gn_gap_next_q_pts"])
    org = [s - g for s, g in zip(so, gp)]
    cfg_mid = float(fc["enterprise_org_pct"]["mid"])
    adj = [(o - cfg_mid) / 100 * base for o in org]
    t = ch["gn"]["table"]
    drain = t["excess_weeks"].dropna()
    last = drain.index[-1]
    return {"company": "gn", "print": "Q3 2026 Enterprise revenue (continuing ops)", "unit": "DKKm",
            "state": f"distributors draining for {len(drain)} quarters: cumulative {t.loc[last, 'excess_usd']:.0f} DKKm = {t.loc[last, 'excess_weeks']:.1f} wk of Enterprise sell-in since {drain.index[0]} (no anchor: relative, grade D)",
            "direction": "H2 'positive organic' needs the drain to END more than sell-out to accelerate",
            "watch_flag": False,
            "evidence": f"latest gap {p.loc[pd.Period('2026Q2', 'Q'), 'gn_st_gap']:+.0f} pts (sell-out flat, sell-in -7% / -3% ex FalCom); group balance sheet not used (Hearing mix, held-for-sale 2026)",
            "adj_low": adj[0], "adj_mid": adj[1], "adj_high": adj[2],
            "formula": f"Enterprise organic = sell-out {so} - gap {gp} = {org} vs forecast mid {cfg_mid:+.0f}% on base DKK {base:.0f}m",
            "config_line": "forecast.gn_2026Q3.enterprise_org_pct.mid", "config_value": cfg_mid,
            "questions": "Enterprise sell-out vs sell-in in Q3 and distributor weeks on hand by region (EMEA)? Is the North America reduction finished?"}


def build_call(p: pd.DataFrame, f: pd.DataFrame, ch: dict, cfg: dict) -> pd.DataFrame:
    rows = [nordic_call(p, f, cfg), logitech_call(p, f, ch, cfg), gn_call(p, ch, cfg)]
    t = pd.DataFrame(rows)
    for c in ("adj_low", "adj_mid", "adj_high"):
        t[c] = t[c].astype(float).round(1)
    t["config_inside_range"] = [
        (r["adj_low"] <= r["config_value"] <= r["adj_high"]) if r["company"] != "gn" else (r["adj_low"] <= 0 <= r["adj_high"])
        for _, r in t.iterrows()]
    return t
