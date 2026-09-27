"""Margin forecasts by one rule (step 7, decision F18), the margin counterpart of the revenue guide-error rule:
margin = the company's margin guide + its own past error on that guide; where no point guide exists, the simple rule with
the lowest walk-forward error. Ranges from out-of-sample errors (80%: +/- 1.28 sd), never typed.

    Nordic GM      guide is only a floor ('above 50%'): candidates last quarter / 4-quarter mean / same quarter last year,
                   scored walk-forward on every quarter of the one-off-adjusted GM (P116); the best one is the point, its RMSE in
                   the current regime the spread. A pre-registered channel-excess term (F25, margin_excess.py) is added only if
                   its rule is met; otherwise it is reported as a scenario (gm_if_excess).
    Logitech GM    non-GAAP GM guided on each call (~44% for Q2 FY27): guide + mean of past (actual - guide); spread from the
                   walk-forward errors of that rule (each quarter uses only earlier guides).
    GN adj. EBITA  annual guide only (9-10% for continuing ops, 19 Aug 2026): FY margin = guide midpoint + GN's mean error on its
                   August margin guides over all years (GN's own record, as F16 for revenue); FY EBITA = that x FY revenue (H1 reported +
                   H2 from the revenue forecast); H2 EBITA = FY - H1; Q3 = H2 x last year's Q3 share of H2 EBITA. Spread from
                   all years' August errors. The Q2 bridge (drop-through + savings + tariff refund) is shown as a cross-check.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"
Z80 = 1.2816


def _rmse(e: pd.Series) -> float:
    e = e.dropna()
    return float(np.sqrt((e ** 2).mean())) if len(e) else np.nan


# ------------------------------------------------------------------ Nordic
def _nordic_gm_series(p: pd.DataFrame) -> pd.Series:
    """One-off-adjusted GM (config structural_breaks: Q2 2024 write-down, Q4 2025 one-off; core.tiers). The reported
    series (nordic_quarterly.csv) scored a write-down as a forecast error and set the 2025Q4 base at 54.9% (P116, F25)."""
    s = p["nordic_gm_adj"].dropna()
    s.index = pd.PeriodIndex(s.index, freq="Q")
    return s


def nordic_gm(p: pd.DataFrame, cfg: dict, excess: dict | None = None) -> dict:
    from margin_excess import run as run_excess
    s = _nordic_gm_series(p)
    g = pd.read_csv(RAW / "nordic_quarterly.csv").set_index("quarter")["guide_gm_pct"]
    g.index = pd.PeriodIndex(g.index, freq="Q")
    g = g.reindex(s.index)
    past_err = s - g                                          # the unified rule applied to Nordic's GM guides (floors / points)
    rules = {"last quarter": s.shift(1), "4-quarter mean": s.rolling(4).mean().shift(1), "same quarter last year": s.shift(4),
             "guide + mean past error (last 4)": g + past_err.rolling(4).mean().shift(1),
             "guide + mean past error (all)": g + past_err.expanding().mean().shift(1)}
    first = s.index[4]
    scores = {k: _rmse((v - s).loc[first:]) for k, v in rules.items()}
    best = min(scores, key=scores.get)
    regime = cfg["forecast"]["nordic_2026Q3"].get("regime", "normal")
    reg = p["regime"].reindex(s.index) if "regime" in p else pd.Series("normal", index=s.index)
    t = pd.Period("2026Q3", "Q")
    floor_now = cfg["forecast"]["nordic_2026Q3"].get("guide_gm_floor", 50.0)
    rule_points = {"last quarter": s.iloc[-1], "4-quarter mean": s.iloc[-4:].mean(), "same quarter last year": s.get(t - 4, np.nan),
                   "guide + mean past error (last 4)": floor_now + past_err.iloc[-4:].mean(),
                   "guide + mean past error (all)": floor_now + past_err.mean()}
    point = rule_points[best]
    # F25: channel-excess term, pre-registered (guidance_anchor.margins.nordic_excess); applied only if its rule is met
    ex = excess or run_excess(s, cfg)
    est, ad, wf = ex["estimate"], ex["adoption"], ex["walk_forward"]
    lag = cfg["guidance_anchor"]["margins"]["nordic_excess"]["state_lag_quarters"]
    x_now = ex["excess"].get(t - lag, np.nan)
    term = float(est["delta"] * x_now) if ad["adopted"] and pd.notna(x_now) else 0.0
    if ad["adopted"]:                                        # the band from the adopted rule's own walk-forward errors
        e = wf.set_index(pd.PeriodIndex(wf["target"], freq="Q"))["err_with_term"]
        err_reg = e[reg.reindex(e.index) == regime]
    else:
        err_reg = (rules[best] - s)[reg == regime]
    sd = _rmse(err_reg)
    point = float(point) + term
    floor = cfg["forecast"]["nordic_2026Q3"].get("guide_gm_floor", 50.0)
    rule = (f"F18 branch: Nordic guides only a floor ('>{floor_now:g}%'), so the walk-forward winner is used: {best} (RMSE {scores[best]:.2f} pts; "
            + ", ".join(f"{k} {v:.2f}" for k, v in scores.items() if k != best)
            + f"; one-off-adjusted GM) + channel-excess term {term:+.1f} (F25 {'adopted' if ad['adopted'] else 'not adopted'}: peer delta "
            f"{est['delta']:+.2f} pts, t {est['t']:.2f}; state {lag}q before = {'excess' if x_now == 1 else 'not excess'})")
    return {"rule": rule, "point": round(point, 1), "low": round(float(point - Z80 * sd), 1), "high": round(float(point + Z80 * sd), 1),
            "sd_pts": round(sd, 2), "n_regime": int(err_reg.notna().sum()), "scores": {k: round(v, 2) for k, v in scores.items()},
            "rule_points": {k: round(float(v), 2) for k, v in rule_points.items()},
            "floor_met_share": round(float((s >= floor).mean()), 2), "guide": f">{floor:g}%", "series": "one-off adjusted",
            "excess": {"delta": round(est["delta"], 3), "se": round(est["se"], 3), "t": round(est["t"], 2), "n": est["n"],
                       "n_quarters": est["n_quarters"], "adopted": ad["adopted"], "why": ad["why"],
                       "wf_rmse_last_quarter": round(ad["rmse_last_quarter"], 2), "wf_rmse_with_term": round(ad["rmse_with_term"], 2),
                       "wf_n": ad["n_targets"], "wf_n_excess": ad["n_targets_excess"],
                       "state_t_minus_1": "excess" if x_now == 1 else ("not excess" if x_now == 0 else "unknown"),
                       "applied_pts": round(term, 2), "gm_if_excess": round(point - term + float(est["delta"]), 1)}}


def write_excess_outputs(p: pd.DataFrame, cfg: dict) -> dict:
    """steps/step7_forecast/outputs/margin_excess_effect.csv (peer estimate + labelled diagnostics) and
    margin_excess_walkforward.csv (Nordic, one row per target)."""
    from margin_excess import run as run_excess
    from core.config import step_outputs
    ex = run_excess(_nordic_gm_series(p), cfg)
    d = step_outputs("step7_forecast")
    ad = ex["adoption"]
    eff = ex["effect_table"].assign(adopted=[ad["adopted"]] + [None] * (len(ex["effect_table"]) - 1),
                                    wf_rmse_last_quarter=[ad["rmse_last_quarter"]] + [None] * (len(ex["effect_table"]) - 1),
                                    wf_rmse_with_term=[ad["rmse_with_term"]] + [None] * (len(ex["effect_table"]) - 1),
                                    wf_n=[ad["n_targets"]] + [None] * (len(ex["effect_table"]) - 1))
    eff.round(3).to_csv(d / "margin_excess_effect.csv", index=False)
    ex["walk_forward"].round(3).to_csv(d / "margin_excess_walkforward.csv", index=False)
    return ex


# ------------------------------------------------------------------ Logitech
def logitech_gm(cfg: dict) -> dict:
    """F18 branch: Logitech guides a point GM on each call, so guide + mean past error is the default; for symmetry with
    Nordic the same walk-forward race is run (last quarter, 4-quarter mean on the non-GAAP GM ex tariff refunds) on the
    guided quarters and reported; the default is replaced only if another rule has the lower RMSE."""
    d = pd.read_csv(RAW / "logitech_quarterly.csv").set_index("quarter")[["gm_nongaap_pct", "guide_gm_pct"]]
    d.index = pd.PeriodIndex(d.index, freq="Q")
    gm = d["gm_nongaap_pct"].copy()
    refund = cfg["structural_breaks"].get("logitech_tariff_refund_q1fy27", {})
    if refund.get("apply"):
        q_ref = pd.Period("2026Q2", "Q")                      # Q1 FY27: $61m refunds inside the reported non-GAAP GM
        gm[q_ref] = gm[q_ref] + refund["adj_gm_pts"]
    err = (d["gm_nongaap_pct"] - d["guide_gm_pct"]).dropna()
    race = {"guide + mean past error": {}, "last quarter": {}, "4-quarter mean": {}}
    for i, q in enumerate(err.index):
        act = d.loc[q, "gm_nongaap_pct"]
        race["guide + mean past error"][q] = d.loc[q, "guide_gm_pct"] + (err.iloc[:i].mean() if i else 0.0) - act
        race["last quarter"][q] = gm.shift(1)[q] - act
        race["4-quarter mean"][q] = gm.rolling(4).mean().shift(1)[q] - act
    scores = {k: _rmse(pd.Series(v, dtype=float)) for k, v in race.items()}
    best = min(scores, key=scores.get)
    guide = cfg["forecast"]["logitech_2026Q3"]["guide_gm"]
    bias = float(err.mean())
    gm_ok = gm.dropna()
    rule_points = {"guide + mean past error": guide + bias, "last quarter": float(gm_ok.iloc[-1]), "4-quarter mean": float(gm_ok.iloc[-4:].mean())}
    point = rule_points[best]
    sd = max(scores[best], float(err.std(ddof=1)))            # out-of-sample error, never below the in-sample spread
    return {"rule": (f"F18 branch: point guide ({guide:g}% on the call) -> guide + mean past error {bias:+.1f} pts (n {len(err)}: "
                     + ", ".join(f"{v:+.1f}" for v in err) + f"); walk-forward race on the {len(err)} guided quarters: "
                     + ", ".join(f"{k} {v:.2f}" for k, v in scores.items()) + f" pts -> {best}"),
            "point": round(point, 1), "low": round(point - Z80 * sd, 1), "high": round(point + Z80 * sd, 1), "sd_pts": round(sd, 2),
            "n": int(len(err)), "walk_forward_rmse": round(scores["guide + mean past error"], 2), "scores": {k: round(v, 2) for k, v in scores.items()},
            "chosen": best, "guide": f"~{guide:g}%", "rule_points": {k: round(float(v), 2) for k, v in rule_points.items()}}


# ------------------------------------------------------------------ GN
def _gn_margin_errors(month: int = 8) -> pd.DataFrame:
    from guidance_record import GN_HIST, gn_headline
    h = gn_headline(pd.read_csv(GN_HIST))
    h = h[h["metric"] == "ebita_margin_pct"]
    rows = []
    for fy, g in h.groupby("fiscal_year"):
        act = g[g["action"] == "actual"]["low"]
        st = g[(g["action"] != "actual") & g["low"].notna() & (pd.to_datetime(g["statement_date"]).dt.month == month)]
        if len(st) and len(act):
            r = st.iloc[-1]
            rows.append({"fiscal_year": int(fy), "statement_date": r["statement_date"], "mid": (r["low"] + r["high"]) / 2,
                         "actual": float(act.iloc[-1]), "error_pts": float(act.iloc[-1]) - (r["low"] + r["high"]) / 2})
    return pd.DataFrame(rows)


def gn_ebita(p: pd.DataFrame, cfg: dict, q3_revenue: float) -> dict:
    from guidance_record import GN_HIST, gn_headline
    ga = cfg.get("guidance_anchor", {}).get("margins", {}).get("gn", {})
    h = gn_headline(pd.read_csv(GN_HIST))
    last = h[(h["metric"] == "ebita_margin_pct") & (h["action"] != "actual") & h["low"].notna()].sort_values("statement_date").iloc[-1]
    e = _gn_margin_errors(ga.get("statement_month", 8))
    # all years, no channel-state adjustment: F16's state effect is estimated on revenue-guide errors (other units) and the
    # state at the forecast date is not 'building', where it would apply (decision F18)
    bias, sd = float(e["error_pts"].mean()), float(e["error_pts"].std(ddof=1))
    fy_mid = (last["low"] + last["high"]) / 2
    fy_m = fy_mid + bias
    g = pd.read_csv(RAW / "gn_quarterly.csv").set_index("quarter")
    rev, mg = g["cont_ops_rev_dkkm"], g["cont_ops_ebita_adj_margin_pct"] / 100
    ebita = rev * mg
    h1_rev, h1_ebita = rev[["2026Q1", "2026Q2"]].sum(), ebita[["2026Q1", "2026Q2"]].sum()
    h2_base, q3_base = rev[["2025Q3", "2025Q4"]].sum(), rev["2025Q3"]
    h2_rev = h2_base * q3_revenue / q3_base                  # H2 grows like the Q3 revenue forecast
    fy_rev = h1_rev + h2_rev
    q3_share = float(ebita["2025Q3"] / ebita[["2025Q3", "2025Q4"]].sum())
    # F23: the Q3 share of H2 EBITA has one continuing-ops year (2025); GN Audio (incl. Consumer, a different perimeter)
    # gives 2021-23. Point stays on 2025; the band adds the share's spread across all four years; mean is a scenario.
    a_eb = g["audio_rev_dkkm"] * g["audio_ebita_adj_margin_pct"] / 100
    shares = {y: float(a_eb[f"{y}Q3"] / (a_eb[f"{y}Q3"] + a_eb[f"{y}Q4"])) for y in (2021, 2022, 2023)
              if f"{y}Q4" in a_eb and pd.notna(a_eb.get(f"{y}Q3")) and pd.notna(a_eb.get(f"{y}Q4"))}
    shares[2025] = q3_share
    share_sd = float(pd.Series(shares).std(ddof=1)) if len(shares) > 1 else 0.0
    h2_ebita = fy_m / 100 * fy_rev - h1_ebita
    q3_ebita = q3_share * h2_ebita
    m = q3_ebita / q3_revenue * 100
    sd_fy = sd / 100 * fy_rev * q3_share / q3_revenue * 100    # the FY error lands on H2 (H1 is reported), split like the EBITA
    sd_share = share_sd * h2_ebita / q3_revenue * 100          # which part of H2 falls in Q3
    sd_q3 = float((sd_fy ** 2 + sd_share ** 2) ** 0.5)
    share_mean = float(pd.Series(shares).mean())
    return {"rule": (f"F18 branch: annual point guide -> guide + mean past error (no walk-forward race: quarterly continuing-ops EBITA "
                     f"exists from 2025 only). FY guide {last['low']:g}-{last['high']:g}% ({last['statement_date']}) + mean August error {bias:+.2f} pts "
                     f"(all {len(e)} years) = {fy_m:.2f}% of FY revenue {fy_rev:,.0f}; H1 EBITA {h1_ebita:,.0f} reported; Q3 = {q3_share:.0%} of H2 (2025 split)"),
            "point": round(m, 1), "low": round(m - Z80 * sd_q3, 1), "high": round(m + Z80 * sd_q3, 1), "sd_pts": round(sd_q3, 2),
            "q3_share_by_year": {int(k): round(v, 3) for k, v in shares.items()}, "q3_share_sd": round(share_sd, 3),
            "sd_from_fy_error_pts": round(sd_fy, 2), "sd_from_share_pts": round(sd_share, 2),
            "point_if_share_mean": round(share_mean * h2_ebita / q3_revenue * 100, 1), "q3_share_mean": round(share_mean, 3),
            "fy_margin_expected": round(fy_m, 2), "q3_ebita_dkkm": round(q3_ebita, 0), "h2_ebita_dkkm": round(h2_ebita, 0),
            "august_errors": e.round(2).to_dict("records"), "guide": f"FY {last['low']:g}-{last['high']:g}%"}
