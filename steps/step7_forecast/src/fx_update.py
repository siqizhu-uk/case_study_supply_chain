"""One FX rule for the three forecasts (step 7, decision F27): the translation effect of the rates actually seen, minus
the FX effect the company's guide already assumed.

    FX term (pts of revenue) = sum_c exposure_c x (average rate of the target quarter / average rate a year earlier - 1)
                               - FX effect assumed in the guide

Rates: ECB reference rates, quarterly averages of the value of each currency in the reporting currency
(pipelines/B_macro_industry/data/raw/fx_quarterly_ecb.csv). Exposures from each company's own disclosures:
    Logitech (reports USD): regional sales shares of the last four quarters, Americas -> USD, EMEA -> EUR, Asia Pacific ->
             an equal basket of CNY / JPY / AUD; checked against the 15 quarters of 'US dollars vs constant currency'
             growth Logitech disclosed. The guide assumes (USD guide - cc guide) points; Q2 FY27: 0.
    GN (reports DKK): the USD share is fitted to GN's disclosed group FX effects (APAC basket share fixed in config);
             GN's EUR sales translate at the peg (no effect). The organic guide assumes no FX, so the whole YoY effect applies.
    Nordic: guide, reporting and price lists in USD, so no translation effect; its NOK costs touch the gross margin, not
             revenue (not modelled).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

RATES = ROOT / "pipelines" / "B_macro_industry" / "data" / "raw" / "fx_quarterly_ecb.csv"
DISCLOSED = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "fx_effects_disclosed.csv"
LOGI_RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "logitech_quarterly.csv"


def rates() -> pd.DataFrame:
    r = pd.read_csv(RATES)
    r.index = pd.PeriodIndex(r.pop("quarter"), freq="Q")
    return r


def yoy(reporting: str, currencies: list[str]) -> pd.DataFrame:
    """YoY % change of the quarterly average value of each currency in the reporting currency (USD -> 0 for USD itself)."""
    r = rates()
    pre = "usd_per_" if reporting == "USD" else "dkk_per_"
    out = {}
    for c in currencies:
        if c == reporting:
            out[c] = pd.Series(0.0, index=r.index)
        else:
            s = r[pre + c]
            out[c] = (s / s.shift(4) - 1) * 100
    return pd.DataFrame(out)


def disclosed() -> pd.DataFrame:
    d = pd.read_csv(DISCLOSED)
    d["q"] = pd.PeriodIndex(d["quarter"], freq="Q")
    return d


# ------------------------------------------------------------------ Logitech
def logitech_shares(cfg: dict, asof: pd.Period | None = None) -> dict:
    c = cfg["fx"]["logitech"]
    d = pd.read_csv(LOGI_RAW).set_index("quarter")[["americas_usdm", "emea_usdm", "apac_usdm"]].dropna()
    d.index = pd.PeriodIndex(d.index, freq="Q")
    if asof is not None:
        d = d[d.index < asof]
    t = d.tail(c["share_quarters"]).sum()
    return {k: float(t[f"{k}_usdm"] / t.sum()) for k in ("americas", "emea", "apac")}


def logitech_structural(cfg: dict) -> pd.Series:
    """Predicted FX effect (pts of USD sales growth) for every quarter, shares as known before the quarter."""
    c = cfg["fx"]["logitech"]
    y = yoy("USD", ["USD", "EUR"] + c["apac_basket"])
    apac = y[c["apac_basket"]].mean(axis=1)
    out = {}
    for q in y.index:
        sh = logitech_shares(cfg, q)
        out[q] = sh["americas"] * y.loc[q, "USD"] + sh["emea"] * y.loc[q, "EUR"] + sh["apac"] * apac.loc[q]
    return pd.Series(out, name="fx_pred_pts")


def logitech_calibration(cfg: dict) -> dict:
    """Disclosed realised FX effect on the structural prediction (no intercept): slope near 1 = the mapping is right."""
    d = disclosed()
    real = d[(d.company == "logitech") & (d.kind == "realised")].set_index("q")["fx_pts"]
    pred = logitech_structural(cfg).reindex(real.index)
    m = pd.concat([real.rename("y"), pred.rename("x")], axis=1).dropna()
    b = float((m.x * m.y).sum() / (m.x ** 2).sum())
    resid = m.y - b * m.x
    r2 = 1 - float((resid ** 2).sum() / ((m.y - m.y.mean()) ** 2).sum())
    return {"slope": b, "r2": r2, "n": len(m), "rmse_pts": float(np.sqrt((resid ** 2).mean())),
            "mean_abs_gap_unscaled": float((m.y - m.x).abs().mean())}


def logitech_guide_fx_surprises(cfg: dict) -> pd.DataFrame:
    """Past guided quarters: FX assumed in the guide vs realised. Small surprises = the habit holds little FX to double count."""
    d = disclosed()
    lg = d[d.company == "logitech"].pivot_table(index="q", columns="kind", values="fx_pts")
    lg = lg.dropna(subset=["guide_assumed"])
    lg["surprise_pts"] = lg.get("realised") - lg["guide_assumed"]
    return lg


def logitech_term(cfg: dict, target: str, guide_mid: float) -> dict:
    t = pd.Period(target, "Q")
    raw = float(logitech_structural(cfg).get(t, np.nan))
    slope = logitech_calibration(cfg)["slope"] if cfg["fx"]["logitech"].get("calibrate_slope") else 1.0
    pred = slope * raw
    d = disclosed()
    g = d[(d.company == "logitech") & (d.kind == "guide_assumed") & (d.q == t)]["fx_pts"]
    assumed = float(g.iloc[0]) if len(g) else np.nan         # unknown when the outlook is not in the cache: no term
    pts = pred - assumed
    return {"predicted_pts": pred, "structural_pts": raw, "slope": slope, "guide_assumed_pts": assumed, "term_pts": pts,
            "term_usdm": pts / 100 * guide_mid,
            "shares": logitech_shares(cfg, t), "rates_days": int(rates()["n_days"].get(t, 0))}


def logitech_walk_forward(cfg: dict) -> dict:
    """Does guide + FX term beat the guide alone on Logitech's explicit quarterly guides (each with rates known after)?"""
    raw = pd.read_csv(LOGI_RAW).set_index("quarter")[["net_sales_usdm", "guide_low_usdm", "guide_high_usdm"]].dropna()
    raw.index = pd.PeriodIndex(raw.index, freq="Q")
    rows = []
    for q, r in raw.iterrows():
        mid = (r.guide_low_usdm + r.guide_high_usdm) / 2
        term = logitech_term(cfg, str(q), mid)
        if not np.isfinite(term["term_pts"]):                 # the guide's own FX assumption is not on file: skip
            continue
        rows.append({"quarter": str(q), "actual": r.net_sales_usdm, "guide_mid": mid, "fx_term_usdm": term["term_usdm"],
                     "err_guide": r.net_sales_usdm - mid, "err_guide_fx": r.net_sales_usdm - mid - term["term_usdm"]})
    w = pd.DataFrame(rows)
    rm = lambda e: float(np.sqrt((e ** 2).mean()))  # noqa: E731
    return {"table": w, "rmse_guide": rm(w.err_guide), "rmse_guide_fx": rm(w.err_guide_fx), "n": len(w)}


# ------------------------------------------------------------------ GN
def gn_fit(cfg: dict) -> dict:
    """USD share fitted to GN's disclosed group FX effects; the North America disclosure (all USD) is the out-of-fit check."""
    c = cfg["fx"]["gn"]
    y = yoy("DKK", ["USD"] + c["apac_basket"])
    apac = y[c["apac_basket"]].mean(axis=1)
    d = disclosed()
    g = d[(d.company == "gn") & (d.kind == "realised")].set_index("q")
    grp = g[g["scope"] == "group"]["fx_pts"]
    x_usd, x_apac = y["USD"].reindex(grp.index), apac.reindex(grp.index)
    target = grp - c["apac_share"] * x_apac
    w = float((x_usd * target).sum() / (x_usd ** 2).sum())
    w = min(max(w, 0.0), 1.0)
    fitted = w * x_usd + c["apac_share"] * x_apac
    na = g[g["scope"] == "north_america"]["fx_pts"]
    check = {str(q): (float(v), float(y["USD"].get(q, np.nan))) for q, v in na.items()}
    return {"usd_share": w, "apac_share": c["apac_share"], "prior_usd_share": c["usd_share_prior"], "n": len(grp),
            "fit": {str(q): (float(grp[q]), round(float(fitted[q]), 2)) for q in grp.index},
            "rmse_pts": float(np.sqrt(((grp - fitted) ** 2).mean())),
            "north_america_check": check}


def gn_term(cfg: dict, target: str) -> dict:
    c = cfg["fx"]["gn"]
    t = pd.Period(target, "Q")
    f = gn_fit(cfg)
    y = yoy("DKK", ["USD"] + c["apac_basket"])
    apac = float(y[c["apac_basket"]].mean(axis=1).get(t, np.nan))
    usd = float(y["USD"].get(t, np.nan))
    pts = f["usd_share"] * usd + c["apac_share"] * apac
    return {"term_pts": pts, "usd_yoy_pct": usd, "apac_yoy_pct": apac, "usd_share": f["usd_share"], "fit": f,
            "rates_days": int(rates()["n_days"].get(t, 0))}


def summary(cfg: dict, logi_guide_mid: float) -> pd.DataFrame:
    """One row per forecast: the FX term, its basis and evidence (written by run_all to steps/step7_forecast/outputs)."""
    lt, gt = logitech_term(cfg, "2026Q3", logi_guide_mid), gn_term(cfg, "2026Q3")
    cal, wf, sur = logitech_calibration(cfg), logitech_walk_forward(cfg), logitech_guide_fx_surprises(cfg)
    return pd.DataFrame([
        {"forecast": "Nordic Q3 2026 revenue", "fx_term_pts": 0.0, "basis": cfg["fx"]["nordic"]["note"]},
        {"forecast": "Logitech Q2 FY27 net sales", "fx_term_pts": round(lt["term_pts"], 2),
         "basis": (f"predicted {lt['predicted_pts']:+.2f} pts (structural {lt['structural_pts']:+.2f} x slope {lt['slope']:.2f}; shares Americas {lt['shares']['americas']:.0%} / EMEA {lt['shares']['emea']:.0%} / "
                   f"APAC {lt['shares']['apac']:.0%}) minus {lt['guide_assumed_pts']:+.1f} assumed in the guide (USD = cc 0-3%) = "
                   f"{lt['term_usdm']:+.1f}m; mapping vs 15 disclosed quarters: slope {cal['slope']:.2f}, R2 {cal['r2']:.2f}; past guides' FX "
                   f"surprises {', '.join(f'{v:+.0f}' for v in sur['surprise_pts'].dropna())} pts; walk-forward RMSE guide {wf['rmse_guide']:.1f}m "
                   f"vs guide + FX {wf['rmse_guide_fx']:.1f}m (n {wf['n']})")},
        {"forecast": "GN cont. ops Q3 2026 revenue", "fx_term_pts": round(gt["term_pts"], 2),
         "basis": (f"USD {gt['usd_yoy_pct']:+.1f}% vs DKK x USD share {gt['usd_share']:.2f} (fitted to {gt['fit']['n']} disclosed group FX "
                   f"effects, RMSE {gt['fit']['rmse_pts']:.1f} pts) + APAC basket {gt['apac_yoy_pct']:+.1f}% x {cfg['fx']['gn']['apac_share']:.2f}; "
                   f"replaces the hand-typed -1.5 (Q2's effect carried forward, wrong sign for Q3)")}])
