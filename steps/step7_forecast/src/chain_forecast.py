"""Step 7c — the supply chain inside each forecast: every one of the brief's decisions is a term, and data sets its weight.

For each print the forecast is written as
    final = guide-anchored benchmark (GB)  +  w x (chain forecast - GB)  +  graph-propagated events
where the chain forecast is built from the decisions (lag kernel, inventory mechanism, attribution share, channel state) and the
weight w follows a rule fixed in config/model.yaml (chain_forecast) BEFORE the live numbers are seen:

Nordic (h = 1 and h = 2; target = Nordic total, benchmark GB of step 6):
    CH  "chain as reasoned", nothing fitted:
            slice YoY_t      = m x sum_k kernel_k D_(t-k)      D = Logitech sell-out proxy, kernel = step-5 graph (lag),
                                                             m = step-3 slice multiplier (mechanism)
            tilt_t           = s_t x [rev_(t-4) x (1 + slice YoY_t) - guide_t]      s_t = step-2 share path (attribution)
            i.e. the chain can only speak for the slice of Nordic it describes; the guide covers the rest.
    GR  the same graph kernel with one slope fitted walk-forward (step 6).
    weight = encompassing beta of (actual - guide) on the model's tilt, if t >= t_min, capped to [0, 1]; else 0.
    If both pass, the one with the lower walk-forward RMSE is used.
Logitech (h = 1): sell-in = sell-through + change in channel inventory (the tier identity). With Logitech's channel at
    its target weeks, next quarter's sell-in YoY = this quarter's sell-through YoY (sell-in YoY + disclosed gap).
    Weight = Bates-Granger inverse-MSE against the guide-anchored benchmark (only 5 Logitech guides: too few for an
    encompassing regression).
GN (h = 1): read-across through shared channels (Gaming vs Logitech Gaming; Enterprise vs TD Synnex Endpoint).
    Used only if the same-quarter correlation clears min_corr.
Events: Logitech's supplier incident (lost Logitech sales) propagated back to Nordic's shipments through the graph's
    Nordic->Logitech lead and Nordic's content per Logitech dollar (step 2), minus the share already in Nordic's guide.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT, step_outputs

SLICE_MULT = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "slice_multiplier.csv"
LOGI_RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "logitech_quarterly.csv"
LOGI_IMPLIED = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "logitech_implied_quarter_guides.csv"


# ------------------------------------------------------------------ shared pieces
def slice_multiplier(cfg: dict) -> tuple[float, dict]:
    """Brand-share-weighted step-3 multiplier (mid) from Logitech/GN end demand to Nordic's slice."""
    bs = {k: v for k, v in cfg["supply_graph"]["brand_share"].items() if k != "source"}
    sm = pd.read_csv(SLICE_MULT).set_index("slice")
    parts = {b: float(sm.loc[b, "mult_mid"]) for b in bs if b in sm.index}
    m = sum(bs[b] * parts[b] for b in parts) / sum(bs[b] for b in parts)
    return m, parts


def kernel_summary(cfg: dict, date) -> dict:
    from supply_graph import kernel_asof            # steps/step5_supply_graph/src
    k = kernel_asof(date, cfg)
    return {"weights": {int(i): round(float(w), 3) for i, w in k.items() if w > 0},
            "mean_lag_q": round(float(np.dot(np.asarray(k.index, float), k.values)), 2)}


def encompassing_weight(tilt: pd.Series, actual: pd.Series, guide: pd.Series, t_min: float) -> dict:
    """OLS (actual - guide) = a + b x tilt; weight = clip(b, 0, 1) if t >= t_min else 0 (classical SE; n is small)."""
    d = pd.concat([tilt.rename("x"), (actual - guide).rename("y")], axis=1).dropna()
    if len(d) < 5 or d["x"].std() == 0:
        return {"n": len(d), "beta": np.nan, "t": np.nan, "weight": 0.0}
    X = np.column_stack([np.ones(len(d)), d["x"]])
    b = np.linalg.lstsq(X, d["y"], rcond=None)[0]
    e = d["y"] - X @ b
    se = float(np.sqrt((e ** 2).sum() / (len(d) - 2) / ((d["x"] - d["x"].mean()) ** 2).sum()))
    t = float(b[1] / se) if se > 0 else np.nan
    w = float(np.clip(b[1], 0, 1)) if np.isfinite(t) and t >= t_min else 0.0
    return {"n": len(d), "beta": float(b[1]), "t": t, "weight": w}


def _rmse(e: pd.Series) -> float:
    e = e.dropna()
    return float(np.sqrt((e ** 2).mean())) if len(e) else np.nan


# ------------------------------------------------------------------ Nordic
def nordic_ch_walkforward(p: pd.DataFrame, cfg: dict, wf: pd.DataFrame, h: int, s: pd.Series, m: float) -> pd.DataFrame:
    """CH on the step-6 walk-forward quarters: same origin, same guide, nothing fitted."""
    from walkforward import design                  # steps/step6_backtest/src
    gd = design(p, "GR", cfg, None, h)["graph_demand"]
    rows = []
    for q, r in wf.iterrows():
        t = pd.Period(q, "Q")
        g = gd.get(t, np.nan)
        tilt = s[t] * (p.loc[t - 4, "nordic_rev"] * (1 + m * g / 100) - r["guide_total"])
        rows.append({"quarter": q, "share": s[t], "graph_demand_yoy": g, "slice_yoy": m * g, "guide_total": r["guide_total"],
                     "CH_tilt": tilt, "CH_total": r["guide_total"] + tilt, "GR_tilt": r["GR_total"] - r["guide_total"],
                     "GR_total": r["GR_total"], "GB_total": r["GB_total"], "actual_total": r["actual_total"]})
    return pd.DataFrame(rows).set_index("quarter")


def nordic_live(p: pd.DataFrame, cfg: dict, live: pd.DataFrame, s: pd.Series, m: float) -> dict:
    """CH and GR for the live targets (h = 1: 2026Q3, h = 2: 2026Q4) on the step-6 live rows."""
    from walkforward import design
    out = {}
    for _, r in live.iterrows():
        h, t = int(r["horizon"]), pd.Period(r["quarter"], "Q")
        pe = p.reindex(p.index.union(pd.period_range(p.index.min(), t, freq="Q")))
        g = float(design(pe, "GR", cfg, None, h)["graph_demand"].get(t, np.nan))
        sh = float(s.reindex(pe.index).ffill()[t])
        rev4 = float(pe.loc[t - 4, "nordic_rev"])
        tilt = sh * (rev4 * (1 + m * g / 100) - r["guide_total"])
        out[h] = {"quarter": str(t), "share": sh, "graph_demand_yoy": g, "slice_yoy": m * g, "rev_t4": rev4,
                  "guide_total": float(r["guide_total"]), "GB_total": float(r["GB_total"]), "CH_tilt": tilt,
                  "CH_total": float(r["guide_total"]) + tilt, "GR_total": float(r["GR_total"]),
                  "GR_tilt": float(r["GR_total"] - r["guide_total"]), "GRi_total": float(r.get("GRi_total", np.nan)),
                  "kernel": kernel_summary(cfg, (t - h + 1).start_time + pd.Timedelta(days=20))}
    return out


def nordic_chain(p: pd.DataFrame, cfg: dict, path: pd.DataFrame, wf: dict, live: pd.DataFrame) -> dict:
    from attribution_path import share_series       # steps/step2_attribution/src
    c = cfg["chain_forecast"]
    s = share_series(path, p) / 100
    m, parts = slice_multiplier(cfg)
    lv = nordic_live(p, cfg, live, s, m)
    res = {"multiplier": m, "multiplier_parts": parts, "horizons": {}}
    for h in (1, 2):
        w = nordic_ch_walkforward(p, cfg, wf[h], h, s, m)
        tests = {mod: {**encompassing_weight(w[f"{mod}_tilt"], w["actual_total"], w["guide_total"], c["weight_t_min"]),
                       "rmse": _rmse(w[f"{mod}_total"] - w["actual_total"]),
                       "gb_rmse": _rmse((w["GB_total"] - w["actual_total"])[w[f"{mod}_total"].notna()])}   # benchmark on this model's quarters
                 for mod in ("CH", "GR")}
        gb_rmse = tests["GR"]["gb_rmse"]
        passing = [mod for mod, r in tests.items() if r["weight"] > 0]
        pick = min(passing, key=lambda mod: tests[mod]["rmse"]) if passing else None
        L = lv[h]
        weight = tests[pick]["weight"] if pick else 0.0
        chain_total = L[f"{pick}_total"] if pick else L["CH_total"]
        contribution = weight * (chain_total - L["GB_total"])
        res["horizons"][h] = {"walkforward": w, "tests": tests, "gb_rmse_same_quarters": gb_rmse, "model_used": pick,
                              "weight": weight, "live": L, "contribution_usdm": contribution,
                              "final_before_events": L["GB_total"] + contribution}
    return res


# ------------------------------------------------------------------ Logitech
def logitech_chain(p: pd.DataFrame, cfg: dict, target: str = "2026Q3") -> dict:
    """Tier identity: sell-in_t YoY = sell-through_(t-1) YoY (channel at target weeks); walk-forward, nothing fitted."""
    c = cfg["chain_forecast"]
    y = p["logi_sales_yoy"]
    st = p["sellout_proxy_yoy"]                     # sell-in YoY + Logitech's disclosed sell-through gap
    first = pd.Period(cfg["backtest"]["first_target"], "Q")
    ch = (p["logi_sales"].shift(4) * (1 + st.shift(1) / 100))
    e_ch = (ch - p["logi_sales"])[(p.index >= first) & p["logi_sales"].notna()]
    beats = (p["logi_sales"] / p["logi_guide_mid"] - 1)
    past_beat = beats.shift(1).expanding().mean().fillna(0.0)
    gbq = p["logi_guide_mid"] * (1 + past_beat)
    e_gb = (gbq - p["logi_sales"]).dropna()
    common = e_gb.index.intersection(e_ch.dropna().index)            # Bates-Granger weights need the SAME quarters (P81)
    mse_ch, mse_gb = _rmse(e_ch[common]) ** 2, _rmse(e_gb[common]) ** 2
    rmse_ch_all = _rmse(e_ch)
    w = (1 / mse_ch) / (1 / mse_ch + 1 / mse_gb) if np.isfinite(mse_ch) and np.isfinite(mse_gb) and mse_gb > 0 else 0.0
    # sensitivity 1: Bates-Granger with the error covariance (both miss the same quarters); unreliable on 5 points
    eg, ec = e_gb[common], e_ch[common]
    cov = float(np.mean((eg - eg.mean()) * (ec - ec.mean())))
    vg, vc = float(eg.var(ddof=0)), float(ec.var(ddof=0))
    w_cov = float(np.clip((vg - cov) / (vg + vc - 2 * cov), 0, 1)) if vg + vc - 2 * cov > 0 else 0.0
    rho = cov / np.sqrt(vg * vc) if vg > 0 and vc > 0 else np.nan
    # sensitivity 2: add the implied quarterly guides (official FY / H1 outlook minus reported quarters) at the turns
    w_imp, n_imp = np.nan, 0
    if LOGI_IMPLIED.exists():
        im = pd.read_csv(LOGI_IMPLIED)
        im_mid = pd.Series(((im["implied_low_usdm"] + im["implied_high_usdm"]) / 2).values, index=pd.PeriodIndex(im["target_quarter"], freq="Q"))
        e_im = (im_mid - p["logi_sales"].reindex(im_mid.index)).dropna()
        eg2 = pd.concat([e_gb[common], e_im])
        ec2 = e_ch.reindex(eg2.index)
        ok = ec2.notna()
        m1, m2 = _rmse(ec2[ok]) ** 2, _rmse(eg2[ok]) ** 2
        w_imp, n_imp = float((1 / m1) / (1 / m1 + 1 / m2)), int(ok.sum())
    w_inverse_mse = float(w)
    rule = c.get("logitech_h1_rule", "inverse_mse")
    if rule == "guide_only":                         # F29: h1 = the guide method; the chain's sell-through is information the guide had
        w = 0.0
    t = pd.Period(target, "Q")
    f = cfg["forecast"]["logitech_2026Q3"]
    mid = (f["guide_low"] + f["guide_high"]) / 2
    beat = float(beats.dropna().mean())
    live_gb = mid * (1 + beat)
    live_st = float(st.get(t - 1))
    live_ch = float(p["logi_sales"].get(t - 4)) * (1 + live_st / 100)
    corr_d = pd.concat([y.rename("y"), st.shift(1).rename("x")], axis=1).loc[first:].dropna()
    return {"n_chain": int(len(common)), "n_gb": int(len(common)), "rmse_chain_usdm": float(np.sqrt(mse_ch)),
            "rmse_chain_all_usdm": rmse_ch_all, "n_chain_all": int(e_ch.notna().sum()),
            "weight_cov": w_cov, "error_corr": float(rho), "weight_with_implied": w_imp, "n_with_implied": n_imp,
            "rmse_gb_usdm": float(np.sqrt(mse_gb)), "weight": float(w), "weight_inverse_mse": w_inverse_mse,
            "weight_rule": ("guide only at h1 (F29); inverse-MSE weight shown as a diagnostic" if rule == "guide_only" else "inverse MSE (Bates-Granger)"),
            "corr_chain_actual_yoy": float(corr_d.corr().iloc[0, 1]),
            "live": {"sellthrough_yoy_prev_q": live_st, "sales_t4": float(p["logi_sales"].get(t - 4)), "chain_total": live_ch,
                     "GB_total": live_gb, "guide_mid": mid, "hist_beat": beat},
            "contribution_usdm": float(w * (live_ch - live_gb)),
            "walkforward": pd.DataFrame({"chain_total": ch, "GB_total": gbq, "actual": p["logi_sales"]}).loc[first:].dropna(how="all")}


# ------------------------------------------------------------------ GN
def gn_readacross(p: pd.DataFrame, cfg: dict) -> dict:
    """Same-quarter read-across GN reports after Logitech / TD Synnex: does it carry information?"""
    c = cfg["chain_forecast"]
    l = pd.read_csv(LOGI_RAW)
    l.index = pd.PeriodIndex(l["quarter"], freq="Q")
    logi_gaming_yoy = (l["gaming_usdm"] / l["gaming_usdm"].shift(4) - 1) * 100
    pairs = {"Gaming organic vs Logitech Gaming YoY (same quarter; Logitech reports first)": (p["gn_gaming_org"], logi_gaming_yoy.reindex(p.index)),
             "Enterprise organic vs TD Synnex Endpoint billings YoY (same quarter)": (p["gn_enterprise_org"], p["snx_endpoint_yoy"])}
    rows = []
    for name, (a, b) in pairs.items():
        d = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
        r = float(d.corr().iloc[0, 1]) if len(d) > 3 else np.nan
        rows.append({"pair": name, "n": len(d), "corr": r, "used": bool(np.isfinite(r) and r >= c["gn_min_corr"])})
    return {"tests": pd.DataFrame(rows), "weight": 0.0 if not any(r["used"] for r in rows) else np.nan, "contribution_usdm": 0.0}


# ------------------------------------------------------------------ events through the graph
def nordic_lead_weeks(cfg: dict, date) -> float:
    """Share-weighted lag of the paths Nordic -> ... -> Logitech (how long before a Logitech sale Nordic ships the chip)."""
    from supply_graph import edge_shares, effective_ranges, load_edges
    e, prm = effective_ranges(load_edges(), cfg)
    sh = edge_shares(e, cfg, date, params={k: v["mid"] for k, v in prm.items()})
    e = e[e["brand"].isin(["logitech", "all"])]
    out = {s_: g for s_, g in e.groupby("src")}
    acc = []

    def walk(node, w, lag):
        if node == "logitech":
            acc.append((w, lag))
            return
        for r in out.get(node, pd.DataFrame()).itertuples():
            if r.dst in ("nordic_distributors", "odm", "logitech") and pd.notna(sh.get(r.edge_id)):
                walk(r.dst, w * sh[r.edge_id], lag + float(r.lag_weeks_mid))

    walk("nordic", 1.0, 0.0)
    W = sum(w for w, _ in acc)
    return sum(w * L for w, L in acc) / W


EVENT_STUDY = ROOT / "steps" / "step5_supply_graph" / "outputs" / "event_study_supplier_incident.csv"
EVENT_ROW = "Nordic shipments to the Logitech slice: total"


def supplier_incident(cfg: dict, path: pd.DataFrame, target: str = "2026Q3") -> dict:
    """Logitech's 25 Jun 2026 supplier incident -> Nordic, from the step-5d event study (F21): a DATED supply shock
    propagates forward from the event date (chips shipped before it are sunk; what a backward lead-shift would put before
    the event reappears after it as stock used first at restart). Nordic Q3 net = gross x (1 - share already in the 6 Aug
    guide, grade D); Q4 is not guided, so its term is gross. The old lead-shift arithmetic is kept as a cross-check of the
    gross (it put ~1.5m before the incident: P97)."""
    c = cfg["chain_forecast"]["supplier_incident"]
    wq = cfg["supply_graph"]["weeks_per_quarter"]
    lead_w = nordic_lead_weeks(cfg, pd.Timestamp(c["as_of"]))
    lead_q = lead_w / wq
    lo, frac = int(np.floor(lead_q)), lead_q - np.floor(lead_q)
    content = float(path["nordic_content_pct_of_logi_sales_p50"].dropna().iloc[-1]) / 100
    t = pd.Period(target, "Q")
    sb = cfg["structural_breaks"]["logitech_supplier_incident_2026"]
    lost = {"2026Q3": sb["q2fy27_sales_hit_usdm"], "2026Q4": sb["q3fy27_sales_hit_usdm"]} if sb.get("apply") else {}
    shifted = sum(loss * ((1 - frac) * (pd.Period(q, "Q") - lo == t) + frac * (pd.Period(q, "Q") - lo - 1 == t)) for q, loss in lost.items())
    ev = pd.read_csv(EVENT_STUDY).set_index("row")
    gross = float(ev.loc[EVENT_ROW, str(t)])
    q4 = float(ev.loc[EVENT_ROW, str(t + 1)])
    share = c["share_in_nordic_guide"]
    return {"source": "step 5d event study (F21)", "lead_weeks": lead_w, "lead_quarters": lead_q, "content_pct": content * 100,
            "nordic_gross_usdm": gross, "share_in_nordic_guide": share, "nordic_net_usdm": gross * (1 - share),
            "net_range_usdm": [gross, 0.0], "nordic_q4_usdm": q4,
            "q4_band_usdm": [float(ev.loc["band low (edge lags x frozen window x content)", str(t + 1)]),
                             float(ev.loc["band high (edge lags x frozen window x content)", str(t + 1)])],
            "lead_shift_gross_usdm": -content * shifted}


# ------------------------------------------------------------------ run + report
def run_chain(p: pd.DataFrame, cfg: dict, path: pd.DataFrame, wf: dict, live: pd.DataFrame, write: bool = True) -> dict:
    res = {"nordic": nordic_chain(p, cfg, path, wf, live), "logitech": logitech_chain(p, cfg),
           "gn": gn_readacross(p, cfg), "incident": supplier_incident(cfg, path), "state": nordic_state(p, cfg)}
    res["terms"] = terms_table(res, cfg, path)
    if write:
        d = step_outputs("step7_forecast")
        res["terms"].to_csv(d / "chain_terms.csv", index=False)
        for h in (1, 2):
            res["nordic"]["horizons"][h]["walkforward"].round(2).to_csv(d / f"chain_nordic_walkforward_h{h}.csv")
        res["logitech"]["walkforward"].round(1).to_csv(d / "chain_logitech_walkforward.csv")
        res["gn"]["tests"].round(3).to_csv(d / "chain_gn_readacross.csv", index=False)
        tests = pd.DataFrame([{"print": "Nordic", "horizon": h, "model": mod, **{k: v for k, v in r.items()}}
                              for h in (1, 2) for mod, r in res["nordic"]["horizons"][h]["tests"].items()])
        tests.round(3).to_csv(d / "chain_weight_tests.csv", index=False)
        scores_table(res).round(3).to_csv(d / "chain_scores.csv", index=False)
    return res


def scores_table(res: dict) -> pd.DataFrame:
    """Walk-forward score of each chain model in the model-inventory format (key 'ch:<model>')."""
    rows = []
    for h in (1, 2):
        H = res["nordic"]["horizons"][h]
        for mod in ("CH", "GR"):
            r = H["tests"][mod]
            rows.append({"model": f"{mod}_h{h}", "horizon": h, "n": r["n"], "rmse_total_usdm": r["rmse"],
                         "bench_rmse_usdm": r["gb_rmse"], "rmse_ratio_vs_GB": r["rmse"] / r["gb_rmse"],
                         "encompassing_beta": r["beta"], "encompassing_t": r["t"], "weight": r["weight"]})
    lg = res["logitech"]
    rows.append({"model": "LOGI_ID_h1", "horizon": 1, "n": lg["n_chain"], "rmse_total_usdm": lg["rmse_chain_usdm"],
                 "bench_rmse_usdm": lg["rmse_gb_usdm"], "rmse_ratio_vs_GB": lg["rmse_chain_usdm"] / lg["rmse_gb_usdm"],
                 "encompassing_beta": np.nan, "encompassing_t": np.nan, "weight": lg["weight"]})
    return pd.DataFrame(rows)


def nordic_state(p: pd.DataFrame, cfg: dict, target: str = "2026Q3") -> dict:
    """Nordic's state term as the forecast applies it (step 7e, F20/F30); fitted here because run_chain runs before
    guide_error_model.csv is written, so reading that file would show the previous run."""
    from guide_error_model import fit, predict
    m = fit(p, cfg)
    return {**m["habits"]["Nordic"], **predict(m, "Nordic", pd.Period(target, "Q"))}


def _z(x: float, nd: int = 1) -> float:
    """Rounded, without a signed zero ('-0.0' reads as a cut)."""
    return round(float(x), nd) + 0.0


def _kernel_text(weights: dict) -> str:
    return ", ".join(f"{k} q back {w:.0%}" for k, w in sorted(weights.items()))


def _parts_text(parts: dict) -> str:
    names = {"logitech": "Logitech", "gn": "GN"}
    return ", ".join(f"{names.get(k, k)} {v:.2f}" for k, v in parts.items())


def _state_row(st: dict) -> tuple:
    return ("Nordic Q3 2026", "Structural breaks", "channel state of t−1 (step 3b, data-dated) and its term (pts)",
            f"{st['state_nordic']}: {_z(st['gamma_applied'], 2):+.2f}",
            f"Nordic's own record by the state of t−1 (F20, F30): habit {st['alpha']:+.2f}% on {st['n_not_building']} quarters neither building nor "
            f"short; building {st['own_building_effect']:+.2f} pts ({st['n_building']} q), supply shortage {st['own_shortage_effect']:+.2f} pts "
            f"({st['n_shortage']} q). Config regimes only for GR training and lag fits",
            "steps/step7_forecast/outputs/guide_error_model.csv")


def _q4_row(n2: dict, inc: dict, cfg: dict) -> tuple:
    """Nordic Q4 (h = 2): the point model (F26) and the pre-registered challengers (F22), each with the incident's Q4
    term, as outputs/forecast_next_quarter.csv and q4_prereg_log.csv hold them."""
    L2, ev, t2 = n2["live"], float(inc["nordic_q4_usdm"]), n2["tests"]
    pm = cfg["forecast_next_quarter"]["point_model"]
    models = [pm] + [m for m in ("GR", "CH") if m != pm]
    vals = " / ".join(f"{L2[f'{m}_total'] + ev:.1f}" for m in models)
    return ("Nordic Q4 2026 (h=2)", "Chain", f"{' / '.join(models)} forecast (USDm)", vals,
            f"point {pm} (F26); {' and '.join(models[1:])} pre-registered (F22); each includes the incident's Q4 term {ev:+.1f}. "
            f"Encompassing: CH beta {t2['CH']['beta']:+.2f} t {t2['CH']['t']:+.1f}; GR beta {t2['GR']['beta']:+.2f} t {t2['GR']['t']:+.1f}",
            "outputs/forecast_next_quarter.csv; steps/step7_forecast/outputs/q4_prereg_log.csv")


def _logitech_rows(lg: dict) -> list[tuple]:
    guide_only = str(lg.get("weight_rule", "")).startswith("guide only")
    w_label = (f"weight on the chain (F29: guide only at h1; inverse-MSE {lg['weight_inverse_mse']:.2f} is a diagnostic)" if guide_only
               else "weight on the chain (inverse MSE)")
    contrib = ("0 (F29); the three hand-set lines were removed (F5)" if guide_only
               else "weight x (chain - guide-anchored); replaces the three hand-set channel lines (F5)")
    return [
        ("Logitech Q2 FY27", "Mechanism", "tier identity: sell-in = sell-through + d(channel inventory); channel at target", _z(lg["live"]["sellthrough_yoy_prev_q"]), "Q1 FY27 sell-through YoY (%) carried to Q2", "logitech_quarterly.csv sellthrough gap"),
        ("Logitech Q2 FY27", "Chain", "chain forecast (USDm)", _z(lg["live"]["chain_total"]), f"vs guide-anchored {lg['live']['GB_total']:.1f}", "chain_forecast.py"),
        ("Logitech Q2 FY27", "Limitations", w_label, _z(lg["weight"], 3), f"same {lg['n_gb']} guided quarters: chain RMSE {lg['rmse_chain_usdm']:.0f}m vs guide {lg['rmse_gb_usdm']:.0f}m (chain over all {lg['n_chain_all']} quarters incl. the 2023-24 turn: {lg['rmse_chain_all_usdm']:.0f}m)", "chain_logitech_walkforward.csv"),
        ("Logitech Q2 FY27", "Chain", "chain contribution to the forecast (USDm)", _z(lg["contribution_usdm"]), contrib, ""),
    ]


def terms_table(res: dict, cfg: dict, path: pd.DataFrame) -> pd.DataFrame:
    """One row per term per print: value, which of the brief's decisions it comes from, and the evidence."""
    n1, n2 = res["nordic"]["horizons"][1], res["nordic"]["horizons"][2]
    L1 = n1["live"]
    lg, inc = res["logitech"], res["incident"]
    k = L1["kernel"]
    rows = [
        ("Nordic Q3 2026", "Lag", "graph kernel (share of the demand signal by quarters back)", _kernel_text(k["weights"]), f"mean {k['mean_lag_q']:.2f} q; the demand that sets Q3 is mostly already reported", "config/supply_graph.csv"),
        ("Nordic Q3 2026", "Lag", "end demand fed through the kernel (Logitech sell-out proxy, YoY %)", _z(L1["graph_demand_yoy"]), "Logitech sell-in YoY + disclosed sell-through gap; unreported quarter by persistence", "step 5 / step 6 GR"),
        ("Nordic Q3 2026", "Mechanism", "slice multiplier m (end demand -> Nordic slice)", _z(res["nordic"]["multiplier"], 2), f"step 3 slice_multiplier.csv mid: {_parts_text(res['nordic']['multiplier_parts'])}", "steps/step3_inventory_mechanism"),
        ("Nordic Q3 2026", "Attribution", "Logitech + GN share of Nordic revenue s", _z(L1["share"] * 100), "step 2 share path p50 (%); p10-p90 in attribution_path.csv", "steps/step2_attribution"),
        _state_row(res["state"]),
        ("Nordic Q3 2026", "Chain", "CH (as reasoned, nothing fitted): guide + s x [rev(t-4)(1+m x demand) - guide]", _z(L1["CH_total"]), f"tilt {L1['CH_tilt']:+.1f}; GR (fitted slope) {L1['GR_total']:.1f}", "chain_forecast.py"),
        ("Nordic Q3 2026", "Limitations", "weight on the chain (encompassing test, h=1)", _z(n1["weight"], 2),
         "CH beta {:+.2f} (t {:+.1f}), GR beta {:+.2f} (t {:+.1f}): no information beyond the guide".format(n1["tests"]["CH"]["beta"], n1["tests"]["CH"]["t"], n1["tests"]["GR"]["beta"], n1["tests"]["GR"]["t"]), "chain_weight_tests.csv"),
        ("Nordic Q3 2026", "Chain", "chain contribution to the forecast (USDm)", _z(n1["contribution_usdm"]), "weight x (chain - guide-anchored)", ""),
        ("Nordic Q3 2026", "Lag + Attribution", "Logitech supplier incident through the graph (USDm)", _z(inc["nordic_net_usdm"]),
         f"step 5d event study (forward from 25 Jun; lead {inc['lead_weeks']:.0f} wk, content {inc['content_pct']:.2f}%): gross {inc['nordic_gross_usdm']:+.1f}, {inc['share_in_nordic_guide']:.0%} assumed already in the 6 Aug guide (grade D): range 0 to {inc['nordic_gross_usdm']:+.1f}; Q4 {inc['nordic_q4_usdm']:+.1f}", "steps/step5_supply_graph/outputs/event_study_supplier_incident.csv"),
        _q4_row(n2, inc, cfg),
        *_logitech_rows(lg),
    ]
    for r in res["gn"]["tests"].itertuples():
        rows.append(("GN Q3 2026", "Chain", r.pair, round(r.corr, 2), f"n {r.n}; {'used' if r.used else 'below the ' + str(cfg['chain_forecast']['gn_min_corr']) + ' bar: not used'}", "chain_gn_readacross.csv"))
    rows.append(("GN Q3 2026", "Mechanism", "Enterprise distributor drain (step 3 channel call)", "in the organic assumption", "H2 'positive organic' needs the drain to end; kept in the bottom-up, not a separate term", "steps/step3_inventory_mechanism/outputs/channel_call.csv"))
    return pd.DataFrame(rows, columns=["print", "decision", "term", "value", "evidence", "source"])


def chain_md(res: dict) -> str:
    """Section for model_report.md: how the chain enters each forecast."""
    n1, n2 = res["nordic"]["horizons"][1], res["nordic"]["horizons"][2]
    t1, t2 = n1["tests"], n2["tests"]
    lg = res["logitech"]
    tab = res["terms"].copy()
    tab["value"] = tab["value"].astype(str)
    return "\n".join([
        "## How the supply chain enters each forecast (step 7c)\n",
        "Each forecast = guide-anchored benchmark + weight x (chain forecast − benchmark) + events propagated through the graph. "
        "The chain forecast is built from the brief's decisions (lag kernel, inventory mechanism, attribution share, channel state); "
        "the weight comes from the walk-forward back-test by a rule fixed in `config/model.yaml` (chain_forecast) before the live numbers.\n",
        f"- **Nordic, guided quarter (h=1):** the chain as reasoned (CH, nothing fitted) has walk-forward RMSE {t1['CH']['rmse']:.1f}m vs "
        f"{t1['CH']['gb_rmse']:.1f}m for the guide-anchored benchmark on the same quarters; encompassing beta {t1['CH']['beta']:+.2f} (t {t1['CH']['t']:+.1f}) "
        "- a negative sign: when the Logitech/GN slice lags the guided total, Nordic beats anyway, because the rest drives the quarter. "
        f"Weight {n1['weight']:.0f}. Why, mechanically: Nordic guides from orders in hand, and the lag kernel says the end demand that sets Q3 was "
        "reported before the guide, so it is already in the orders. The chain describes only the Logitech/GN slice; its "
        "disagreement with the guide is about the mix, which the guide total already absorbs.",
        f"- **Nordic, quarter after (h=2):** CH beta {t2['CH']['beta']:+.2f} (t {t2['CH']['t']:+.1f}), GR beta {t2['GR']['beta']:+.2f} "
        f"(t {t2['GR']['t']:+.1f}): the chain carries information where no guide exists. CH gets the direction right but a "
        f"slope of {t2['CH']['beta']:.1f} says Nordic moves about {t2['CH']['beta']:.0f}x what the attribution slice alone implies: its other "
        "consumer customers ride the same end-demand cycle (step 3's whole-company multiplier 2.1–6.5). "
        f"Encompassing picks {n2['model_used']} (lower RMSE), weight {n2['weight']:.2f}; the Q4 point and its pre-registered challengers are the "
        "'Nordic Q4 2026 (h=2)' row below (F26, F22).",
        f"- **Logitech (h=1):** tier identity sell-in = sell-through + Δchannel inventory. On the same {lg['n_gb']} guided quarters: walk-forward RMSE "
        f"{lg['rmse_chain_usdm']:.0f}m vs {lg['rmse_gb_usdm']:.0f}m for the guide (all {lg['n_chain_all']} quarters: {lg['rmse_chain_all_usdm']:.0f}m); "
        f"weight used {lg['weight']:.2f} ({lg['weight_rule']}: {lg['weight_inverse_mse']:.2f}), contribution {_z(lg['contribution_usdm']):+.1f}m. "
        "The three hand-set channel lines were removed (F5).",
        "- **GN (h=1):** same-quarter read-across fails (table below); GN's segments move with its own product cycle and share shifts. "
        "The channel enters only through the Enterprise distributor-drain assumption.",
        f"- **Logitech supplier incident:** {res['incident']['nordic_gross_usdm']:+.1f}m of Nordic Q3 shipments by the graph "
        f"(lead {res['incident']['lead_weeks']:.0f} weeks, content {res['incident']['content_pct']:.2f}%), of which "
        f"{res['incident']['share_in_nordic_guide']:.0%} is assumed already in the 6 Aug guide: {res['incident']['nordic_net_usdm']:+.1f}m.\n",
        tab.to_markdown(index=False), ""])
