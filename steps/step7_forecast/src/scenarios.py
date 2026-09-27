"""Step 7d — risk scenarios for the note: each one moves ONE named input of an existing model and says which decision
it tests. Nothing here is a new estimate; every number comes from a step output (no probabilities are attached: the
back-test cannot calibrate them on ~4 independent cycles).

    Nordic Q3  base | distributors turn to building / supply shortage (step 7e own state effects, F20/F30, D24) |
               pre-registered challengers (F16 pooled, rule before F30, Nordic's own words F31) | rule before F20 (F14) |
               pull-in (F19) | incident in / not in the guide (step 7c) | distributor restock at step 3's high
    Nordic Q4  base = the point model (GRi since F26: Logitech sell-in through the Nordic -> ODM segment) | graph lags low / high |
               previous rule GR (F24) | restock pays back in Q4 (GRg, a GR variant, stays in forecast_next_quarter.csv only)
"""
from __future__ import annotations

import pandas as pd

from core.config import OUTPUTS, ROOT

CALL = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "channel_call.csv"
NEXT = OUTPUTS / "forecast_next_quarter.csv"
GN_PRINT = "GN cont. ops Q3 2026"          # the same label as outputs/forecasts.csv


def _shift(fn: dict, error_pct: float) -> float:
    """Nordic Q3 with a different expected guide error, every other line (chain, incident) held: guide mid x (1 + e) + adj."""
    return float(fn["point"]) + (error_pct - float(fn["hist_beat_pct"])) * float(fn["guide_mid"]) / 100


def _shortage_rows(fn: dict, gem: dict, cfg: dict) -> list[dict]:
    """Nordic's supply turns short (D24): its base habit + its own shortage effect (F30), the same incident term."""
    pr = gem["predictions"]["Nordic"]
    h = gem["model"]["habits"]["Nordic"]
    if not h.get("own_state") or "shortage_effect" not in pr:
        return []
    wk = float(cfg["cycle_state"]["shortage"]["lead_time_min_weeks"])
    return [{"print": "Nordic Q3 2026", "scenario": f"supply shortage (D24: lead time > {wk:.0f} weeks)", "point": _shift(fn, pr["alpha"] + pr["shortage_effect"]),
             "decision": "Mechanism", "what_moves": f"Nordic's own shortage effect {pr['shortage_effect']:+.2f} pts (n {h.get('n_shortage', '')}) on its base habit {pr['alpha']:+.2f}%; same incident term",
             "source": "steps/step7_forecast/outputs/guide_error_model.csv"}]


def _wording_rows(fn: dict, gem: dict) -> list[dict]:
    """F31: the same own-record model with the state read from Nordic's own words (pre-registered challenger)."""
    w = gem.get("wording_rule_prediction")
    if not w:
        return []
    return [{"print": "Nordic Q3 2026", "scenario": "state from Nordic's own words (F31, pre-registered)", "point": _shift(fn, w["expected_error"]),
             "decision": "Structural breaks", "what_moves": f"expected error {w['expected_error']:+.2f}% (state '{w.get('state_nordic', w['state'])}' from Nordic's words) instead of {fn['hist_beat_pct']:+.2f}%",
             "source": "steps/step7_forecast/outputs/challenger_prereg_log.csv"}]


def build_scenarios(fn: dict, gb: pd.DataFrame, chain: dict, cfg: dict, fg: dict | None = None, gem: dict | None = None) -> pd.DataFrame:
    from forecast_display import regime_sensitivity     # the fork's regime table (same numbers as the dashboard)
    base = float(fn["point"])
    rows = [{"print": "Nordic Q3 2026", "scenario": "base", "point": base, "low": fn["low"], "high": fn["high"],
             "decision": "all", "what_moves": f"guide x (1 {'+' if fn['hist_beat_pct'] >= 0 else '-'} {abs(fn['hist_beat_pct']):.2f}%) + chain terms (7c) + incident (5d); expected error = {fn.get('beat_source', 'historical beat')}",
             "source": "outputs/forecasts.csv"}]
    mid = float(fn["guide_mid"])
    if gem is not None:
        se = gem["model"]["state_effect"]
        g = gem["predictions"]["Nordic"]["building_effect"]
        h = gem["model"]["habits"]["Nordic"]
        rows.append({"print": "Nordic Q3 2026", "scenario": "distributors turn to building (channel state)", "point": base + g * mid / 100,
                     "decision": "Mechanism", "what_moves": f"Nordic's own building effect {g:+.2f} pts (n {h.get('n_building', '')}); peers' {se['gamma']:+.2f} (t {se['t']:.1f})",
                     "source": "steps/step7_forecast/outputs/guide_error_model.csv"})
        rows += _shortage_rows(fn, gem, cfg)
        if "Nordic" in gem.get("challenger_predictions", {}):
            c = gem["challenger_predictions"]["Nordic"]
            rows.append({"print": "Nordic Q3 2026", "scenario": "F16 pooled with peers (pre-registered challenger)", "point": base + (c["expected_error"] - fn["hist_beat_pct"]) * mid / 100,
                         "decision": "Limitations", "what_moves": f"expected error {c['expected_error']:+.2f}% (habit pooled, own weight {gem['model']['challengers']['Nordic']['weight_own']:.0%}) instead of {fn['hist_beat_pct']:+.2f}%",
                         "source": "steps/step7_forecast/outputs/challenger_prereg_log.csv"})
        if gem.get("previous_rule_prediction"):
            pv = gem["previous_rule_prediction"]["expected_error"]
            rows.append({"print": "Nordic Q3 2026", "scenario": "rule before F30: supply-shortage quarters counted as lean (pre-registered challenger)",
                         "point": base + (pv - fn["hist_beat_pct"]) * mid / 100, "decision": "Structural breaks",
                         "what_moves": f"expected error {pv:+.2f}% (14 not-building quarters incl. the 2020Q4-22Q3 shortage) instead of {fn['hist_beat_pct']:+.2f}%",
                         "source": "steps/step7_forecast/outputs/challenger_prereg_log.csv"})
        rows += _wording_rows(fn, gem)
        own = float(gb[(gb["company"] == "Nordic") & gb["window"].str.startswith("normal")].iloc[0]["mean_beat_pct"])
        rows.append({"print": "Nordic Q3 2026", "scenario": "rule before F20 (F14): Nordic's own normal-regime beat, unpooled", "point": base + (own - fn["hist_beat_pct"]) * mid / 100,
                     "decision": "Structural breaks", "what_moves": f"beat {own:+.2f}% (regime dated after the fact, F14) instead of {fn['hist_beat_pct']:+.2f}%",
                     "source": "steps/step6_backtest/outputs/guidance_bias.csv"})
    else:
        rs = regime_sensitivity(fn, gb).set_index("regime")
        rows.append({"print": "Nordic Q3 2026", "scenario": "channel turns: destock regime", "point": float(rs.loc["destock", "point"]),
                     "decision": "Structural breaks", "what_moves": f"beat {rs.loc['destock', 'beat_pct']:+.1f}% (destock, n {int(rs.loc['destock', 'n'])}) instead of {rs.loc['normal', 'beat_pct']:+.1f}%",
                     "source": "steps/step6_backtest/outputs/guidance_bias.csv"})
    pull = float(cfg["forecast"]["nordic_2026Q3"]["pull_in_scenario_usdm"])
    rows.append({"print": "Nordic Q3 2026", "scenario": f"small customers pull in beyond the guide ({pull:+.1f}; F19 keeps the line at 0)", "point": base + pull,
                 "decision": "Mechanism", "what_moves": "sign grade C (CEO, Q2 2026 call: 'some safety stockings for some additional weeks'); size grade D (F19)",
                 "source": "pipelines/A_company_financials/data/manual/nordic_2026Q2.txt"})
    inc = chain["incident"]
    rows.append({"print": "Nordic Q3 2026", "scenario": "supplier incident not in Nordic's guide (net -> gross)", "point": base + inc["nordic_gross_usdm"] - inc["nordic_net_usdm"],
                 "decision": "Lag + Attribution", "what_moves": f"share of the incident already in the 6 Aug guide {inc['share_in_nordic_guide']:.0%} -> 0% (gross {inc['nordic_gross_usdm']:+.1f})",
                 "source": "steps/step7_forecast/outputs/chain_terms.csv"})
    rows.append({"print": "Nordic Q3 2026", "scenario": "supplier incident all in Nordic's guide (net -> 0)", "point": base - inc["nordic_net_usdm"],
                 "decision": "Lag + Attribution", "what_moves": f"share in the 6 Aug guide {inc['share_in_nordic_guide']:.0%} -> 100% (grade D judgment); range of the line 0 to {inc['nordic_gross_usdm']:+.1f}",
                 "source": "steps/step7_forecast/outputs/chain_terms.csv"})
    call = pd.read_csv(CALL).set_index("company").loc["nordic"]
    restock = float(call["adj_high"]) - float(call["config_value"])
    rows.append({"print": "Nordic Q3 2026", "scenario": "distributors restock at step 3's high", "point": base + restock,
                 "decision": "Mechanism", "what_moves": f"channel refill {call['adj_high']:+.1f} instead of the {call['config_value']:+.1f} line ({call['formula']})",
                 "source": "steps/step3_inventory_mechanism/outputs/channel_call.csv"})
    nx = pd.read_csv(NEXT).set_index("model")
    pm = nx.index[nx["is_point"].astype(str).str.lower() == "true"][0]           # GRi since F26
    pt, gr = nx.loc[pm], nx.loc["GR"]
    rows.append({"print": "Nordic Q4 2026", "scenario": f"base: supply graph ({pm}, h=2)", "point": float(pt["point"]), "low": float(pt["low"]), "high": float(pt["high"]),
                 "decision": "Lag", "what_moves": f"{pt['role']}; walk-forward error {pt['rmse_ratio_vs_GB']:.2f}x the guide-based extrapolation (n {int(pt['wf_n'])})",
                 "source": "outputs/forecast_next_quarter.csv"})
    for side in ("low", "high"):
        rows.append({"print": "Nordic Q4 2026", "scenario": f"graph lags and shares at their {side} end ({pm})", "point": float(pt[f"lag_{side}_point"]),
                     "decision": "Lag + Attribution", "what_moves": "every edge lag and share at the end of its grade-based range",
                     "source": "outputs/forecast_next_quarter.csv"})
    rows.append({"print": "Nordic Q4 2026", "scenario": "previous rule: GR (sell-through proxy, whole graph, persistence fill; F24)", "point": float(gr["point"]),
                 "low": float(gr["low"]), "high": float(gr["high"]), "decision": "Limitations",
                 "what_moves": f"pre-registered challenger since F26; walk-forward error {gr['rmse_ratio_vs_GB']:.2f}x (n {int(gr['wf_n'])}); "
                 f"its gap to {pm} is the sell-through vs sell-in driver and the fill",
                 "source": "outputs/forecast_next_quarter.csv; steps/step7_forecast/outputs/q4_prereg_log.csv"})
    rows.append({"print": "Nordic Q4 2026", "scenario": "Q3 restock (step 3 high) pays back in Q4", "point": float(pt["point"]) - float(call["adj_high"]),
                 "decision": "Mechanism", "what_moves": f"the {call['adj_high']:.1f} refill reverses one quarter later (step 3 dates the payback to H1 2027; Q4 is the earliest case)",
                 "source": "steps/step3_inventory_mechanism/outputs/channel_call.csv"})
    lg = chain["logitech"]
    lbase = float(chain.get("logitech_point", lg["live"]["GB_total"] + lg["contribution_usdm"]))
    gap = lg["live"]["chain_total"] - lg["live"]["GB_total"]
    fc = pd.read_csv(OUTPUTS / "forecasts.csv").set_index(["print", "metric"])
    lrow = fc.loc[("Logitech Q2 FY27", "Net sales (USDm)")] if ("Logitech Q2 FY27", "Net sales (USDm)") in fc.index else None
    rows.append({"print": "Logitech Q2 FY27", "scenario": "base", "point": lbase, "decision": "all",
                 "low": float(lrow["low"]) if lrow is not None else None, "high": float(lrow["high"]) if lrow is not None else None,
                 "what_moves": (f"guide x beat + {lg['weight']:.2f} x (chain - guide-anchored); {lg.get('weight_rule', 'inverse MSE')} "
                                f"({lg['n_gb']} explicitly guided quarters)"),
                 "source": "outputs/forecasts.csv"})
    for key, label, n in (("weight_inverse_mse", "chain at its inverse-MSE weight (diagnostic since F29)", lg["n_gb"]),
                          ("weight_cov", f"chain weight with the error covariance (errors correlate {lg['error_corr']:.2f})", lg["n_gb"]),
                          ("weight_with_implied", "chain weight incl. implied guides at the 2023-25 turns", lg["n_with_implied"])):
        w = lg.get(key)
        if w is None or abs(w - lg["weight"]) < 1e-9:           # the same as the base: not a scenario
            continue
        rows.append({"print": "Logitech Q2 FY27", "scenario": label, "point": lbase + (w - lg["weight"]) * gap, "decision": "Limitations",
                     "what_moves": f"weight {w:.2f} instead of {lg['weight']:.2f} (n {n})",
                     "source": "steps/step7_forecast/outputs/chain_terms.csv; pipelines/A_company_financials/data/raw/logitech_implied_quarter_guides.csv"})
    if fg is not None and fg.get("guidance_anchor"):
        a = fg["guidance_anchor"]
        fx = float(fg.get("organic_assumptions", {}).get("fx_pts", 0.0))
        rows.append({"print": GN_PRINT, "scenario": "base", "point": fg["point"], "low": fg["low"], "high": fg["high"], "decision": "all",
                     "what_moves": (f"FY guide mid {a['fy_guide_mid']:+.1f}% + expected guide error {a['august_bias_pts']:+.1f} pts (plain mean of its "
                                    f"own August-guide misses, n {a['august_bias_n']}; F17, F23) + FX {fx:+.1f} pts at ECB rates (F27)"),
                     "source": "outputs/forecast_details.json (gn.guidance_anchor)"})
        for k, v in a.get("q3_if", {}).items():
            rows.append({"print": GN_PRINT, "scenario": f"bias: {k}", "point": v, "decision": "Limitations",
                         "what_moves": f"H2 organic {a['h2_if'][k]:+.1f}% instead of {a['h2_organic_pct']:+.1f}%", "source": "outputs/forecast_details.json"})
        dv = fg.get("division_view", {})
        if dv:
            rows.append({"print": GN_PRINT, "scenario": "division view (Enterprise / Gaming organic, config)", "point": dv["point"], "decision": "Mechanism",
                         "what_moves": "management's divisional H2 language; Enterprise distributor drain ends", "source": "config/model.yaml forecast.gn_2026Q3"})
    if fg is not None and fg.get("ebita_margin_model"):
        em = fg["ebita_margin_model"]
        rows.append({"print": f"{GN_PRINT} adj. EBITA margin (%)", "scenario": "point: Q3 share of H2 EBITA as in 2025", "point": em["point"],
                     "low": em["low"], "high": em["high"], "decision": "all",
                     "what_moves": f"Q3 share {em['q3_share_by_year'].get(2025, em['q3_share_by_year'].get('2025', 0)):.0%} (the one continuing-ops year)",
                     "source": "outputs/forecast_details.json (gn.ebita_margin_model)"})
        rows.append({"print": f"{GN_PRINT} adj. EBITA margin (%)", "scenario": "Q3 share at its 2021-25 mean", "point": em["point_if_share_mean"],
                     "decision": "Limitations", "what_moves": f"Q3 share {em['q3_share_mean']:.0%} (2021-23 GN Audio incl. Consumer: a different perimeter; F23)",
                     "source": "pipelines/A_company_financials/data/raw/gn_quarterly.csv"})
    out = pd.DataFrame(rows)
    b = out.groupby("print")["point"].transform("first")
    out["vs_base"] = out["point"] - b
    return out[["print", "scenario", "point", "low", "high", "vs_base", "decision", "what_moves", "source"]]
