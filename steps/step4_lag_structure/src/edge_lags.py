"""Step 4 — the lag of THIS chain, edge by edge (decisions L4-L9).

    Amazon / Ingram Micro / TD Synnex --edge 1--> Logitech / GN --edge 2--> Nordic

Order = order of the reasoning: priors from the step 5 graph (edge_priors, L4-L5) -> edge 1 estimate from the channel
inventory's partial adjustment (edge1_channel, L6) -> edge 2 estimate with the slice size fixed by attribution and the
common cycle controlled (edge2_constrained, L7) -> posterior per edge (precision-weighted, or = prior when the data cannot
place the lag, L8) -> route totals (means add; simulated range, L9). Every number is computed; config edge_lags.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import edge1_channel
import edge2_constrained as e2
from edge_posterior import combine, totals
from edge_priors import priors
from core.config import step_outputs

WPQ = 13.0
ALL = "all routes (flow-weighted)"


# ------------------------------------------------------------------ fixed inputs from steps 2 and 3
def shares(cfg: dict, attr: dict | None) -> dict:
    """Each brand's share of Nordic consumer revenue (p10 / p50 / p90): step 2's Logitech + GN share x step 2's brand split."""
    if attr is None:
        attr = json.loads((step_outputs("step2_attribution") / "attribution.json").read_text())
    c = attr["combined_pct_of_nordic_consumer"]
    split = cfg["supply_graph"]["brand_share"]
    return {b: {"low": c["p10"] / 100 * split[b], "mid": c["p50"] / 100 * split[b], "high": c["p90"] / 100 * split[b]}
            for b in ("logitech", "gn")}


def multipliers() -> dict:
    """Slice amplitude multiplier per brand (step 3, slice_multiplier.csv): low / mid / high."""
    m = pd.read_csv(step_outputs("step3_inventory_mechanism") / "slice_multiplier.csv").set_index("slice")
    return {b: {k: float(m.loc[b, f"mult_{k}"]) for k in ("low", "mid", "high")} for b in ("logitech", "gn")}


# ------------------------------------------------------------------ edge 1
def edge1(cfg: dict) -> pd.DataFrame:
    """Edge 1 rows per brand from step 3's channel index (GN: shorter than min_obs -> no rows, prior only)."""
    d = step_outputs("step3_inventory_mechanism")
    out = []
    for b in ("logitech", "gn"):
        idx = pd.read_csv(d / f"channel_index_{b}.csv", index_col=0)[cfg["edge_lags"]["edge1"]["series"]]
        r = edge1_channel.estimate(idx, cfg["edge_lags"]["edge1"], cfg["supply_graph"]["lag_check"])
        out += [r.assign(brand=b)] if len(r) else []
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# ------------------------------------------------------------------ edge 2
def _variants(p: pd.DataFrame, cfg: dict, s: dict, m: dict) -> list[tuple]:
    """(label, brand, driver, control, keep, s x m, dummy) per fit; the first per brand is the primary."""
    c = cfg["edge_lags"]["edge2"]
    keep = p.index[p["regime"].isin(c["regimes"])]
    normal = p.index[p["regime"] == "normal"]
    destock = (p["regime"] == "destock").astype(float)
    sl, ml = s["logitech"], m["logitech"]
    L, W = c["driver"]["logitech"], c["control"]
    return [("primary", "logitech", L, W, keep, sl["mid"] * ml["mid"], None),
            ("attribution low (step 2 p10)", "logitech", L, W, keep, sl["low"] * ml["mid"], None),
            ("attribution high (step 2 p90)", "logitech", L, W, keep, sl["high"] * ml["mid"], None),
            ("slice multiplier low (step 3)", "logitech", L, W, keep, sl["mid"] * ml["low"], None),
            ("slice multiplier high (step 3)", "logitech", L, W, keep, sl["mid"] * ml["high"], None),
            ("control: RSEAS instead of WSTS", "logitech", L, c["control_alt"], keep, sl["mid"] * ml["mid"], None),
            ("driver: radio categories (" + c["driver_alt"] + ")", "logitech", c["driver_alt"], W, keep, sl["mid"] * ml["mid"], None),
            ("regime: destock intercept", "logitech", L, W, keep, sl["mid"] * ml["mid"], destock),
            ("regime: normal only", "logitech", L, W, normal, sl["mid"] * ml["mid"], None),
            ("primary", "gn", c["driver"]["gn"], W, keep, s["gn"]["mid"] * m["gn"]["mid"], None)]


def _wk(r: dict, keys: tuple) -> dict:
    return {f"{k.removesuffix('_q')}_weeks": r[k] * WPQ for k in keys if k in r}


def edge2(p: pd.DataFrame, cfg: dict, s: dict, m: dict) -> pd.DataFrame:
    """Edge 2 rows: the constrained fits (primary + sensitivities), the unconstrained fit, step 5's end-to-end correlation."""
    lc, chi2 = cfg["supply_graph"]["lag_check"], cfg["edge_lags"]["edge2"]["profile_chi2"]
    y, rows = p[cfg["edge_lags"]["edge2"]["target"]], []
    for label, brand, xc, wc, keep, sm, dm in _variants(p, cfg, s, m):
        r = e2.constrained(y, p[xc], p[wc], keep, sm, lc, chi2, dm)
        rows.append({"brand": brand, "fit": label, "driver": xc, "control": wc, "slope": sm, "slope_kind": "fixed s x m",
                     "n": r["n"], "first_quarter": r.get("first_quarter"), "coverage": max(r.get("ci_share", 1), r.get("set_share", 1)),
                     **_wk(r, ("kappa_q", "tau_q", "ci_lo_q", "ci_hi_q", "set_lo_q", "set_hi_q"))})
    c = cfg["edge_lags"]["edge2"]
    u = e2.unconstrained(y, p[c["driver"]["logitech"]], p[c["control"]], p.index[p["regime"].isin(c["regimes"])], lc, chi2)
    rows.append({"brand": "logitech", "fit": "unconstrained (slope free)", "driver": c["driver"]["logitech"], "control": c["control"],
                 "slope": u["slope"], "slope_kind": "fitted b", "n": u["n"], "first_quarter": u["first_quarter"],
                 "coverage": u["set_share"], **_wk(u, ("kappa_q", "tau_q", "set_lo_q", "set_hi_q"))})
    return pd.DataFrame(rows + _step5_row())


def _step5_row() -> list[dict]:
    """Step 5's end-to-end correlation (no size constraint, no control), read from its output (G21)."""
    f = step_outputs("step5_supply_graph") / "graph_vs_step4_continuous_lag.csv"
    if not f.exists():
        return []
    r = pd.read_csv(f).query("kind == 'sell-in' and sample == 'ex supply-constrained'").iloc[0]
    return [{"brand": "logitech", "fit": "step 5 end-to-end correlation (no constraint, no control)", "driver": "logi_ble_yoy",
             "control": "", "slope": np.nan, "slope_kind": "correlation", "n": int(r["n"]), "first_quarter": r["first_quarter"],
             "coverage": np.nan, "tau_weeks": r["tau_weeks"], "ci_lo_weeks": r["ci_lo_weeks"], "ci_hi_weeks": r["ci_hi_weeks"],
             "set_lo_weeks": r["near_optimal_lo_weeks"], "set_hi_weeks": r["near_optimal_hi_weeks"]}]


# ------------------------------------------------------------------ combine and write
def estimates_for_posterior(r1: pd.DataFrame, r2: pd.DataFrame) -> dict:
    """(edge, brand) -> {mid, lo, hi, coverage, method} in weeks from each brand's primary fit."""
    out = {}
    for r in r1[r1["primary"]].to_dict("records") if len(r1) else []:
        out[("edge 1", r["brand"])] = {"mid": r["lag_weeks"], "lo": r["lag_lo_weeks"], "hi": r["lag_hi_weeks"],
                                       "coverage": 0.0, "method": r["spec"] + "; " + r["interval"]}
    for r in r2[r2["fit"] == "primary"].to_dict("records"):
        if pd.notna(r.get("tau_weeks")):
            out[("edge 2", r["brand"])] = {"mid": r["tau_weeks"], "lo": r["ci_lo_weeks"], "hi": r["ci_hi_weeks"], "coverage": r["coverage"],
                                           "method": f"attribution-constrained, {r['control']} control; block bootstrap 90%"}
    return out


def run(p: pd.DataFrame, cfg: dict, attr: dict | None = None) -> dict:
    """Priors -> estimates -> posterior -> totals. Returns DataFrames plus the fixed inputs used."""
    el = cfg["edge_lags"]
    s, m = shares(cfg, attr), multipliers()
    pri = priors(cfg)
    r1, r2 = edge1(cfg), edge2(p, cfg, s, m)
    post = combine(pri, estimates_for_posterior(r1, r2), el["uninformative_share"])
    d, col = step_outputs("step3_inventory_mechanism"), el["edge1"]["series"]
    return {"priors": pri, "edge1": r1, "edge2": r2, "combined": post, "totals": totals(post, el["total_draws"], el["seed"]),
            "shares": s, "multipliers": m, "index": pd.read_csv(d / "channel_index_logitech.csv", index_col=0)[col],
            "gn_index_n": int(pd.read_csv(d / "channel_index_gn.csv")[col].notna().sum())}


def write(res: dict, out: Path) -> dict[str, Path]:
    """edge_lags.csv (prior / estimate / posterior per edge), edge_lags_total.csv, and the two estimate tables."""
    files = {"combined": out / "edge_lags.csv", "totals": out / "edge_lags_total.csv",
             "edge1": out / "edge_lags_edge1_fits.csv", "edge2": out / "edge_lags_edge2_fits.csv"}
    for k, f in files.items():
        res[k].round(4).to_csv(f, index=False)
    return files
