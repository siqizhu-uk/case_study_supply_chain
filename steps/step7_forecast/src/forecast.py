"""Point forecasts and ranges for the three October/November prints.

Method (same for each name):
  point = guidance midpoint × (1 + expected guide error) + explicit signal adjustments
          expected guide error = step 7e model (F16): company habit pooled with 12 peers + channel-state effect
          + the supply-chain term of step 7c (weight × (chain forecast − guide-anchored), weight from the back-test)
          + events propagated through the graph (Logitech's supplier incident -> Nordic)
  range = point ± 1.28 × (the model's predictive sd of the guide error) × guidance midpoint   [≈ 80% band]
Every adjustment is a named line in config/model.yaml or a computed step-7c term, so it can be argued with.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z80 = 1.2816


def _beat_stats(gb: pd.DataFrame, company: str, window_startswith: str) -> tuple[float, float]:
    r = gb[(gb["company"] == company) & (gb["window"].str.startswith(window_startswith))].iloc[0]
    return float(r["mean_beat_pct"]) / 100, float(r["std_pct"]) / 100


def _chain_lines(chain: dict | None, company: str) -> dict:
    """Step 7c terms (chain_forecast.py) as named adjustment lines; empty without the chain run."""
    if chain is None:
        return {}
    if company == "nordic":
        return {"supply_chain_term (step 7c)": round(chain["nordic"]["horizons"][1]["contribution_usdm"], 2),
                "logitech_supplier_incident (graph)": round(chain["incident"]["nordic_net_usdm"], 2)}
    return {"supply_chain_term (step 7c)": round(chain["logitech"]["contribution_usdm"], 2)}


def _model_beat(gem: dict, company: str) -> tuple[float, float, str]:
    """Expected guide error and its predictive sd from the step-7e model, with the words that say where they come from."""
    pr, h = gem["predictions"][company], gem["model"]["habits"][company]
    if h.get("own_state"):
        return pr["expected_error"] / 100, pr["sd"] / 100, (
            f"own record by channel state (F20, F30): {pr['alpha']:+.2f}% when neither building nor short of supply (n {h['n_not_building']}), "
            f"{h['own_building_effect']:+.2f} pts when building (n {h['n_building']}), {h.get('own_shortage_effect', 0.0):+.2f} pts in a supply "
            f"shortage (n {h.get('n_shortage', 0)}); state now '{pr.get('state_nordic', pr['state'])}' ({pr['gamma_applied'] + 0.0:+.2f}); "
            "the shortage split was adopted after seeing the data and its walk-forward does not beat the rule before it")
    pool = f"pooled with 12 peers, own record {h['weight_own']:.0%}" if h["pooled"] else "own record, no comparable peer population"
    src = (f"guide-error model (F16): habit {pr['alpha']:+.2f}% ({pool}) + channel state '{pr['state']}' ({pr['gamma_applied'] + 0.0:+.2f})")
    return pr["expected_error"] / 100, pr["sd"] / 100, src


def forecast_nordic(cfg: dict, gb: pd.DataFrame, reg: dict, p: pd.DataFrame, composite: dict | None = None,
                    chain: dict | None = None, gem: dict | None = None) -> dict:
    """If step 6c's composite passed its pre-stated adoption gate, the beat is the composite's forecast and the error is
    its walk-forward RMSE; adjustment lines the composite already captures (forecast config `composite_overlaps`) are
    dropped so the same signal is not counted twice. Otherwise: regime-conditioned historical beat as before."""
    f = cfg["forecast"]["nordic_2026Q3"]
    mid = (f["guide_low"] + f["guide_high"]) / 2
    adjs = dict(f["signal_adjustments_usdm"])
    use = cfg["composite"].get("use_in_forecast", True)
    if composite is not None and composite.get("adopted") and use:
        beat = composite["live"]["beat_hat_pct"] / 100
        sd = composite["oos_rmse_pts"] / 100 * composite.get("live_band_scale", 1.0)      # scaled by |C| only if step 6c's band test passed
        adjs = {k: v for k, v in adjs.items() if k not in f.get("composite_overlaps", [])}
        beat_source = (f"step 6c composite (C = {composite['live']['composite_C']:+.2f}; walk-forward RMSE {composite['oos_rmse_pts']:.2f} pts"
                       f"{'; band scaled by |C| x' + format(composite.get('live_band_scale', 1.0), '.2f') if composite.get('use_scaled_band') else ''})")
    elif gem is not None:
        beat, sd, beat_source = _model_beat(gem, "Nordic")
    else:
        beat, sd = _beat_stats(gb, "Nordic", "normal")
        sd = float(np.hypot(sd, f.get("extra_uncertainty_pct", 0) / 100))
        beat_source = "regime-conditioned historical beat (normal channel)" + (
            "; step 6c composite kept as pre-registered challenger (analyst decision B26)" if composite is not None and not use else "")
    adjs.update(_chain_lines(chain, "nordic"))
    adj = sum(adjs.values())
    point = mid * (1 + beat) + adj
    band = Z80 * sd * mid
    # cross-check from the distributed-lag regression: implied consumer YoY from lagged Logitech
    xcheck = None
    if reg.get("ok"):
        prof = reg["lag_profile_pts"]
        drv = reg.get("driver_series", p["logi_ble_yoy"])      # the regression's own driver (path-weighted when step 2b's path is in force)
        q = pd.Period("2026Q3", "Q")
        contrib, used = 0.0, {"driver": reg.get("driver", "logi_ble_yoy")}
        for k, b in prof.items():
            v = drv.get(q - k, np.nan)
            if not np.isnan(v):
                contrib += b * v; used[f"L{k}"] = round(float(v), 1)
        # missing lag-0 (Logitech Q3 not reported): substitute Logitech guidance-implied YoY (share weight of the last quarter = 1)
        if 0 in prof and np.isnan(drv.get(q, np.nan)):
            lg = cfg["forecast"]["logitech_2026Q3"]
            logi_q3_yoy = ((lg["guide_low"] + lg["guide_high"]) / 2 / p["logi_sales"].get(q - 4) - 1) * 100
            contrib += prof[0] * logi_q3_yoy; used["L0(guide-implied)"] = round(float(logi_q3_yoy), 1)
        # add mean of fitted-minus-lag part (intercept + controls at their recent values) via last fitted residual approach:
        last = reg["fitted"].index[-1]
        base = float(reg["fitted"].loc[last] - sum(prof[k] * (drv.get(last - k, 0.0) if not np.isnan(drv.get(last - k, np.nan)) else 0.0) for k in prof))
        implied_yoy = base + contrib
        cons_ly = float(p["nordic_consumer"].get(q - 4))
        implied_consumer = cons_ly * (1 + implied_yoy / 100)
        cons_share = float((p["nordic_consumer"] / p["nordic_rev"]).loc["2025Q3":"2026Q2"].mean())
        xcheck = {"implied_consumer_yoy_pct": round(implied_yoy, 1), "implied_consumer_usdm": round(implied_consumer, 1),
                  "implied_total_usdm_at_avg_mix": round(implied_consumer / cons_share, 1), "inputs": used,
                  "note": "regression-only view; ignores I&H and guidance, shown as a sanity check not the forecast"}
    return {"name": "Nordic Semiconductor Q3 2026 (reports 22 Oct 2026)", "metric": "Revenue USDm",
            "guide": [f["guide_low"], f["guide_high"]], "guide_mid": mid, "hist_beat_pct": round(beat * 100, 2),
            "hist_beat_sd_pct": round(sd * 100, 2), "signal_adjustments": adjs, "beat_source": beat_source,
            "point": round(point, 1), "low": round(point - band, 1), "high": round(point + band, 1),
            "yoy_pct": round((point / float(p["nordic_rev"].get(pd.Period("2025Q3", "Q"))) - 1) * 100, 1),
            **_gm("nordic", cfg, p), "regression_crosscheck": xcheck}


def forecast_logitech(cfg: dict, gb: pd.DataFrame, p: pd.DataFrame, chain: dict | None = None, gem: dict | None = None) -> dict:
    f = cfg["forecast"]["logitech_2026Q3"]
    mid = (f["guide_low"] + f["guide_high"]) / 2
    if gem is not None:
        beat, sd, beat_source = _model_beat(gem, "Logitech")
    else:
        beat, sd = _beat_stats(gb, "Logitech", "quarterly")
        sd = float(np.hypot(sd, f.get("extra_uncertainty_pct", 0) / 100))
        beat_source = "historical beat on explicit quarterly guides"
    adjs = {**(f["signal_adjustments_usdm"] or {}), **_chain_lines(chain, "logitech")}
    fxc = _logitech_fx_check(cfg, mid)
    if fxc and fxc["applied"]:                                   # F27: only when guide + FX term beats the guide walk-forward
        adjs["fx_since_guide (F27)"] = fxc["term_usdm"]
    adj = sum(adjs.values())
    point = mid * (1 + beat) + adj
    band = Z80 * sd * mid
    ly = float(p["logi_sales"].get(pd.Period("2025Q3", "Q")))
    return {"name": "Logitech Q2 FY2027 (Jul-Sep 2026; reports ~27 Oct 2026)", "metric": "Net sales USDm",
            "guide": [f["guide_low"], f["guide_high"]], "guide_mid": mid, "hist_beat_pct": round(beat * 100, 2),
            "hist_beat_sd_pct": round(sd * 100, 2), "signal_adjustments": adjs, "beat_source": beat_source,
            "point": round(point, 1), "low": round(point - band, 1), "high": round(point + band, 1),
            "yoy_pct": round((point / ly - 1) * 100, 1), **_gm("logitech", cfg, p),
            "gm_note": "non-GAAP; GAAP ≈ 0.3pt lower; excludes any further tariff refunds",
            "fx_check": fxc}


def _logitech_fx_check(cfg: dict, mid: float) -> dict | None:
    """F27 for Logitech: the post-guide FX term is computed but applied only if guide + term beats the guide walk-forward.
    Logitech's guide is set at the guide-date rates, its past FX surprises are ~0 and the structural estimate is noisier
    than they are, so on the record so far the term is not applied (reported)."""
    if "fx" not in cfg:
        return None
    from fx_update import logitech_term, logitech_walk_forward, logitech_calibration
    t, wf, cal = logitech_term(cfg, "2026Q3", mid), logitech_walk_forward(cfg), logitech_calibration(cfg)
    applied = wf["rmse_guide_fx"] < wf["rmse_guide"]
    return {"term_pts": round(t["term_pts"], 2), "term_usdm": round(t["term_usdm"], 1), "guide_assumed_pts": t["guide_assumed_pts"],
            "calibration_slope": round(cal["slope"], 2), "calibration_r2": round(cal["r2"], 2), "wf_rmse_guide": round(wf["rmse_guide"], 1),
            "wf_rmse_guide_fx": round(wf["rmse_guide_fx"], 1), "wf_n": wf["n"], "applied": bool(applied)}


def gn_anchor(cfg: dict, p: pd.DataFrame, gem: dict | None = None) -> dict:
    """GN, decisions F16 / F17: full-year organic growth = midpoint of GN's latest full-year guide + GN's expected guide
    error from the step-7e model (its own August-guide record net of the channel-state effect; no comparable peer
    population to pool with) - or, without the model, the plain mean of its August-guide errors. H1 is reported, so the
    implied H2 follows from prior-year half-year weights, H2 = (FY x (H1b + H2b) - H1 x H1b) / H2b, and the H2 sd =
    FY sd x (H1b + H2b) / H2b (H1 carries no error). Q3 is taken to grow at the H2 rate."""
    from guidance_record import gn_headline, gn_statement_errors, GN_HIST
    h = gn_headline(pd.read_csv(GN_HIST))
    last = h[(h["metric"] == "organic_growth_pct") & (h["action"] != "actual") & h["low"].notna()].sort_values("statement_date").iloc[-1]
    fy_mid = (last["low"] + last["high"]) / 2
    e = gn_statement_errors(cfg.get("guidance_anchor", {}).get("gn", {}).get("statement_month", 8)).dropna(subset=["error_pts"])
    if gem is not None:
        pr = gem["predictions"]["GN"]
        h = gem["model"]["habits"]["GN"]
        how = "plain mean of its own August-guide misses (F17, F23)" if h.get("state_adjusted") is False else f"own record net of channel state ({pr['state']})"
        bias, fy_sd, src = pr["expected_error"], pr["sd"], f"guide-error model: {how}, {pr['expected_error']:+.2f} pts (n {h['n']})"
        peer_mu = gem["model"]["prior"]["mu"]
    else:
        bias, fy_sd, src, peer_mu = float(e["error_pts"].mean()), float(e["error_pts"].std(ddof=1)), "mean August-guide error (F14)", None
    fy_exp = fy_mid + bias
    q = lambda s: pd.Period(s, "Q")                                                     # noqa: E731
    ent, gam = p["gn_enterprise_dkk"], p["gn_gaming_dkk"]
    eo, go = p["gn_enterprise_org"], p["gn_gaming_org"]
    h1b = {k: float(ent.get(q(k)) + gam.get(q(k))) for k in ("2025Q1", "2025Q2")}
    h1g = sum((float(ent.get(q(k))) * float(eo.get(q(k).__add__(4))) + float(gam.get(q(k))) * float(go.get(q(k).__add__(4)))) for k in h1b) / sum(h1b.values())
    H1b, H2b = sum(h1b.values()), float(ent.get(q("2025Q3")) + gam.get(q("2025Q3")) + ent.get(q("2025Q4")) + gam.get(q("2025Q4")))
    h2_of = lambda b: ((fy_mid + b) * (H1b + H2b) - h1g * H1b) / H2b          # noqa: E731
    h2 = h2_of(bias)
    alts = {"no bias (guide as given)": h2_of(0.0)}
    if peer_mu is not None:
        alts["pooled with the semiconductor peers' habit"] = h2_of(peer_mu)
    return {"fy_guide": [float(last["low"]), float(last["high"]), last["statement_date"]], "fy_guide_mid": fy_mid,
            "august_bias_pts": bias, "august_bias_n": len(e), "bias_source": src, "august_bias_all_years_pts": float(e["error_pts"].mean()),
            "august_bias_by_year": {int(y): float(v) for y, v in zip(e["fiscal_year"], e["error_pts"])},
            "fy_expected_pct": round(fy_exp, 2), "h2_if": alts,
            "h1_2026_organic_pct": round(h1g, 2), "h2_organic_pct": round(h2, 2),
            "h2_sd_pts": round(fy_sd * (H1b + H2b) / H2b, 2)}


def _gm(company: str, cfg: dict, p: pd.DataFrame) -> dict:
    """Gross-margin point and range from the one margin rule (margin_model, decision F18)."""
    from margin_model import logitech_gm, nordic_gm
    m = nordic_gm(p, cfg) if company == "nordic" else logitech_gm(cfg)
    return {"gm_point": m["point"], "gm_range": [m["low"], m["high"]], "gm_rule": m["rule"], "gm_model": m}


def _gn_margin(cfg: dict, p: pd.DataFrame, q3_revenue: float) -> dict:
    from margin_model import gn_ebita
    m = gn_ebita(p, cfg, q3_revenue)
    refund = cfg["forecast"]["gn_2026Q3"]["tariff_refund_q3_dkkm"]
    return {"ebita_adj_margin_point": m["point"], "ebita_adj_margin_range": [m["low"], m["high"]], "ebita_margin_rule": m["rule"],
            "ebita_margin_model": m, "ebita_adj_point_dkkm": m["q3_ebita_dkkm"],                       # the rule's basis
            "ebita_margin_ex_tariff_refund": round((m["q3_ebita_dkkm"] - refund) / q3_revenue * 100, 1)}


def forecast_gn(cfg: dict, p: pd.DataFrame, gem: dict | None = None) -> dict:
    f = cfg["forecast"]["gn_2026Q3"]
    q0 = pd.Period(f["base_quarter"], "Q")
    ent0, gam0 = float(p["gn_enterprise_dkk"].get(q0)), float(p["gn_gaming_dkk"].get(q0))
    fx_detail = None
    if f.get("fx_pts") is None:                                   # F27: translation effect from ECB rates (fx_update.py)
        from fx_update import gn_term
        fx_detail = gn_term(cfg, "2026Q3")
        fx_pts = round(fx_detail["term_pts"], 2)
    else:
        fx_pts = f["fx_pts"]
    fx = 1 + fx_pts / 100

    def rev(k):
        return (ent0 * (1 + f["enterprise_org_pct"][k] / 100) + gam0 * (1 + f["gaming_org_pct"][k] / 100)) * fx

    division_view = {"point": round(rev("mid"), 0), "low": round(rev("low"), 0), "high": round(rev("high"), 0)}
    if f.get("method", "division_assumptions") in ("guidance_record", "guide_error_model"):
        anchor = gn_anchor(cfg, p, gem if f.get("method") == "guide_error_model" else None)
        g2 = anchor["h2_organic_pct"] / 100
        base = ent0 + gam0
        point = base * (1 + g2) * fx
        band = Z80 * anchor["h2_sd_pts"] / 100 * base * fx
        low, high = point - band, point + band
        anchor["q3_if"] = {k: round(base * (1 + v / 100) * fx, 0) for k, v in anchor["h2_if"].items()}
    else:
        anchor = None
        point, low, high = rev("mid"), rev("low"), rev("high")
    # EBITA bridge from Q2 2026 adjusted EBITA (DKK m): drop-through on incremental revenue + savings + tariff refund
    q2 = pd.Period("2026Q2", "Q")
    q2_rev = float(p["gn_cont_ops_rev"].get(q2)); q2_m = float(p["gn_cont_ops_ebita_adj_m"].get(q2)) / 100
    q2_ebita = q2_rev * q2_m
    gm = float(p["gn_cont_ops_gm"].get(q2)) / 100
    bridge = {"q2_2026_adj_ebita": round(q2_ebita, 0), "drop_through_on_incremental_rev": round((point - q2_rev) * gm, 0),
              "cost_savings": f["cost_savings_q3_dkkm"], "tariff_refund": f["tariff_refund_q3_dkkm"]}
    ebita = sum(bridge.values())
    return {"name": "GN Store Nord — GN Audio successor = continuing ops (Enterprise + Gaming), Q3 2026 (reports 5 Nov 2026)",
            "metric": "Revenue DKKm", "base_q3_2025": {"enterprise": ent0, "gaming": gam0, "total": ent0 + gam0},
            "organic_assumptions": {"enterprise": f["enterprise_org_pct"], "gaming": f["gaming_org_pct"], "fx_pts": fx_pts},
            "fx_update": None if fx_detail is None else {k: v for k, v in fx_detail.items() if k != "fit"} | {"fit": fx_detail["fit"]},
            "method": f.get("method", "division_assumptions"), "guidance_anchor": anchor, "division_view": division_view,
            "point": round(point, 0), "low": round(low, 0), "high": round(high, 0),
            "yoy_pct": round((point / (ent0 + gam0) - 1) * 100, 1),
            "ebita_bridge_dkkm": bridge, "ebita_bridge_point_dkkm": round(ebita, 0),
            **_gn_margin(cfg, p, point),
            "ebita_bridge_margin_pct": round(ebita / point * 100, 1),                      # Q2 bridge: cross-check of the margin rule
            "ebita_bridge_margin_ex_tariff_refund": round((ebita - f["tariff_refund_q3_dkkm"]) / point * 100, 1)}


def forecast_table(fn: dict, fl: dict, fg: dict) -> pd.DataFrame:
    rows = [
        {"print": "Nordic Q3 2026", "metric": "Revenue (USDm)", "point": fn["point"], "low": fn["low"], "high": fn["high"], "guide": f"{fn['guide'][0]}-{fn['guide'][1]}", "yoy_pct": fn["yoy_pct"]},
        {"print": "Nordic Q3 2026", "metric": "Gross margin (%)", "point": fn["gm_point"], "low": fn["gm_range"][0], "high": fn["gm_range"][1], "guide": ">50", "yoy_pct": None},
        {"print": "Logitech Q2 FY27", "metric": "Net sales (USDm)", "point": fl["point"], "low": fl["low"], "high": fl["high"], "guide": f"{fl['guide'][0]}-{fl['guide'][1]}", "yoy_pct": fl["yoy_pct"]},
        {"print": "Logitech Q2 FY27", "metric": "Gross margin non-GAAP (%)", "point": fl["gm_point"], "low": fl["gm_range"][0], "high": fl["gm_range"][1], "guide": "~44", "yoy_pct": None},
        {"print": "GN cont. ops Q3 2026", "metric": "Revenue (DKKm)", "point": fg["point"], "low": fg["low"], "high": fg["high"], "guide": "FY org 0-3%", "yoy_pct": fg["yoy_pct"]},
        {"print": "GN cont. ops Q3 2026", "metric": "Adj. EBITA margin (%)", "point": fg["ebita_adj_margin_point"], "low": fg["ebita_adj_margin_range"][0], "high": fg["ebita_adj_margin_range"][1], "guide": "FY adj 9-10%", "yoy_pct": None},
    ]
    return pd.DataFrame(rows)
