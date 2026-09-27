"""Step 5g — scores of the industry-cycle challenger against GR, CH and GB on identical quarters, and the adoption bar (G29).

Every comparison runs on the quarters where CYC, its robustness variants, GR, CH, GB and the actual all exist (step 5e's
same-quarter rule). Pairwise: RMSE, bias, Diebold-Mariano (HLN, h=2), encompassing both ways ((actual - B) on (A - B)),
concentration of the squared-error gain (top-3 share). The bar is config cycle_challenger.adoption, fixed before scoring.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

BENCHES = {"GR": "GR (step 6, the Q4 forecast)", "CH": "CH (chain as reasoned)", "GB": "GB (guide-anchored)"}


def models(cfg: dict) -> list[str]:
    return list(cfg["cycle_challenger"]["models"])


def common(wf: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Rows where every model, benchmark and the actual exist (new frame, combination diagnostic added)."""
    cols = [f"{m}_total" for m in models(cfg) + list(BENCHES)] + ["actual_total"]
    d = wf.dropna(subset=cols).copy()
    p = cfg["cycle_challenger"]["primary"]
    return d.assign(COMBO_total=(d["GR_total"] + d[f"{p}_total"]) / 2)


def pair(d: pd.DataFrame, a: str, b: str, h: int, t_min: float) -> dict:
    """Model a against benchmark b (route_nowcast_scores.compare: RMSE, bias, DM-HLN, encompassing a over b, top-3 gain share)."""
    from route_nowcast_scores import compare
    return compare(d[f"{a}_total"], d[f"{b}_total"], d["actual_total"], h, t_min)


def scores(wf: pd.DataFrame, cfg: dict, scope: str = "main") -> pd.DataFrame:
    """One row per (model, benchmark) on the common quarters; plus each model's level row (RMSE / bias alone)."""
    cc = cfg["cycle_challenger"]
    h, t_min = int(cc["horizon"]), float(cc["adoption"]["t_min"])
    d = common(wf, cfg)
    rows = []
    for m in models(cfg) + list(BENCHES) + ["COMBO"]:
        e = d[f"{m}_total"] - d["actual_total"]
        rows.append({"scope": scope, "model": m, "vs": "", "n": len(d), "first": d.index.min(), "last": d.index.max(),
                     "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean())})
    for m in models(cfg) + ["COMBO"]:
        for b in BENCHES:
            rows.append({"scope": scope, "model": m, "vs": b, **pair(d, m, b, h, t_min)})
    rows.append({"scope": scope, "model": "GR", "vs": cc["primary"], **pair(d, "GR", cc["primary"], h, t_min)})
    return pd.DataFrame(rows)


def own_quarters(wf: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Each model on every quarter it forecasts (vs GB on those quarters): its record for the band."""
    rows = []
    for m in models(cfg) + list(BENCHES):
        d = wf.dropna(subset=[f"{m}_total", "actual_total", "GB_total"])
        e, eb = d[f"{m}_total"] - d["actual_total"], d["GB_total"] - d["actual_total"]
        rows.append({"scope": "own quarters", "model": m, "vs": "GB", "n": len(d), "first": d.index.min(), "last": d.index.max(),
                     "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean()),
                     "rmse_bench_same_quarters": float(np.sqrt((eb ** 2).mean()))})
    return pd.DataFrame(rows)


def adoption(sc: pd.DataFrame, cfg: dict) -> dict:
    """The pre-stated bar applied to the primary vs GR on the common quarters."""
    a, prim = cfg["cycle_challenger"]["adoption"], cfg["cycle_challenger"]["primary"]
    r = sc[(sc["scope"] == "main") & (sc["model"] == prim) & (sc["vs"] == "GR")].iloc[0]
    rmse_ok = bool(r["rmse_ratio"] < 1)
    test_ok = bool(r["dm_t"] <= -float(a["t_min"]) or r["enc_t"] >= float(a["t_min"]))
    conc_ok = bool(np.isfinite(r["gain_share_top3"]) and r["gain_share_top3"] < float(a["max_top3_gain_share"]))
    return {"model": prim, "n": int(r["n"]), "rmse": r["rmse"], "rmse_gr": r["rmse_bench_same_quarters"], "rmse_ratio": r["rmse_ratio"],
            "dm_t": r["dm_t"], "enc_t": r["enc_t"], "gain_share_top3": r["gain_share_top3"], "rmse_below_gr": rmse_ok,
            "test_passed": test_ok, "gain_not_concentrated": conc_ok, "bar_met": rmse_ok and test_ok and conc_ok,
            "role_this_print": "pre-registered challenger (not in the Q4 forecast)"}


def encompassing_drop_one(wf: pd.DataFrame, cfg: dict, a: str, b: str) -> dict:
    """Diagnostic added after the first scores (not part of the bar): encompassing t of a over b with each quarter left out."""
    from chain_forecast import encompassing_weight      # steps/step7_forecast/src (read only)
    d = common(wf, cfg)
    t_min = float(cfg["cycle_challenger"]["adoption"]["t_min"])
    ts = {q: encompassing_weight(d.drop(q)[f"{a}_total"] - d.drop(q)[f"{b}_total"], d.drop(q)["actual_total"],
                                 d.drop(q)[f"{b}_total"], t_min)["t"] for q in d.index}
    s = pd.Series(ts)
    return {"t_min_drop_one": float(s.min()), "quarter_dropped": str(s.idxmin()), "t_max_drop_one": float(s.max())}
