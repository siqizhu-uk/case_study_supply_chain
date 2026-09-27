"""Step 5f — scores of the Logitech nowcasts and of the Nordic h=2 forecasts they feed, and the adoption verdict (G27).

Every comparison is against persistence (N0) on the same quarters. Nowcast: RMSE, Diebold-Mariano (HLN, h=1) and the
encompassing regression y - N0 = a + b (N - N0). Nordic: RMSE, DM (h=2) and encompassing of the increment over the
persistence version of the same model (GR or CH). Adoption follows config route_nowcast.adoption, fixed before scoring:
nowcast RMSE below N0 AND (DM t <= -t_min OR encompassing t >= t_min) AND Nordic GR RMSE not above GR's; else N0.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rmse(e: pd.Series) -> float:
    return float(np.sqrt((e ** 2).mean())) if len(e) else np.nan


def role(cfg: dict, m: str) -> str:
    a = cfg["route_nowcast"]["adoption"]
    if m == a["default"]:
        return "default"
    if m in a["comparison_only"]:
        return "comparison only (user rule: not a candidate)"
    return "candidate" if m in a["candidates"] else "sensitivity (cannot be adopted)"


def compare(model: pd.Series, bench: pd.Series, actual: pd.Series, h: int, t_min: float) -> dict:
    """RMSE ratio, DM-HLN and encompassing of model vs bench on the quarters where all three exist."""
    from chain_forecast import encompassing_weight      # steps/step7_forecast/src (read only)
    from walkforward import _dm_hln                      # steps/step6_backtest/src
    d = pd.concat([model.rename("m"), bench.rename("b"), actual.rename("a")], axis=1).dropna()
    e_m, e_b = d["m"] - d["a"], d["b"] - d["a"]
    dm, dm_p = _dm_hln(e_m.values, e_b.values, h)
    enc = encompassing_weight(d["m"] - d["b"], d["a"], d["b"], t_min)
    gain = e_b ** 2 - e_m ** 2
    top3 = float(gain.nlargest(3).sum() / gain.sum()) if gain.sum() > 0 else np.nan
    last = d.tail(6)
    return {"n": len(d), "first": str(d.index[0]) if len(d) else "", "last": str(d.index[-1]) if len(d) else "",
            "rmse": _rmse(e_m), "rmse_bench_same_quarters": _rmse(e_b), "rmse_ratio": _rmse(e_m) / _rmse(e_b) if len(d) else np.nan,
            "bias": float(e_m.mean()) if len(d) else np.nan, "dm_t": dm, "dm_p": dm_p, "enc_beta": enc["beta"], "enc_t": enc["t"],
            "gain_share_top3": top3, "rmse_ratio_last6": _rmse(last["m"] - last["a"]) / _rmse(last["b"] - last["a"]) if len(last) else np.nan}


def nowcast_scores(wf: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Each model on its own fitted quarters vs N0 on the same quarters; then every proxy model on their common quarters."""
    rc = cfg["route_nowcast"]
    t_min, models = float(rc["adoption"]["t_min"]), [m for m in rc["models"] if m != rc["adoption"]["default"]]
    N0, y = wf[rc["adoption"]["default"]], wf["actual"]
    rows = [{"scope": "own quarters", "model": m, "label": rc["models"][m]["label"], "role": role(cfg, m),
             **compare(wf[m].where(wf[f"{m}_fitted"].astype(bool)), N0, y, 1, t_min)} for m in models]
    proxy = [m for m in models if rc["models"][m]["kind"] == "proxy_change"]
    common = wf[wf[[f"{m}_fitted" for m in proxy]].astype(bool).all(axis=1)].index
    rows += [{"scope": "common quarters", "model": m, "label": rc["models"][m]["label"], "role": role(cfg, m),
              **compare(wf.loc[common, m], N0.loc[common], y.loc[common], 1, t_min)} for m in proxy]
    b = wf.dropna(subset=["actual", rc["adoption"]["default"]])
    rows.append({"scope": "all quarters", "model": rc["adoption"]["default"], "label": rc["models"]["N0"]["label"], "role": "default",
                 "n": len(b), "first": b.index[0], "last": b.index[-1], "rmse": _rmse(b["N0"] - b["actual"]),
                 "bias": float((b["N0"] - b["actual"]).mean())})
    return pd.DataFrame(rows)


def nordic_scores(wf_long: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """GR and CH fed with each nowcast vs the persistence version of the same model (same quarters), h=2."""
    rc = cfg["route_nowcast"]
    from chain_forecast import encompassing_weight      # steps/step7_forecast/src (read only)
    t_min, h, base = float(rc["adoption"]["t_min"]), int(rc["nordic_horizon"]), rc["adoption"]["default"]
    rows = []
    for fc in ("GR_total", "CH_total"):
        w = wf_long.pivot(index="quarter", columns="model", values=fc)
        a = wf_long.groupby("quarter")["actual_total"].first()
        g = wf_long.groupby("quarter")["guide_total"].first()
        for m in rc["models"]:
            eg = encompassing_weight(w[m] - g, a, g, t_min)
            ok = pd.concat([w[m], a], axis=1).dropna().index
            r = compare(w[m], w[base], a, h, t_min) if m != base else {"n": len(ok), "first": ok[0], "last": ok[-1], "rmse": _rmse(w[m][ok] - a[ok])}
            rows.append({"forecast": fc.replace("_total", ""), "model": m, "role": role(cfg, m), **r,
                         "enc_vs_guide_beta": eg["beta"], "enc_vs_guide_t": eg["t"],
                         "mean_abs_change_vs_N0_usdm": float((w[m] - w[base]).abs().mean())})
    return pd.DataFrame(rows)


def adoption(ns: pd.DataFrame, nd: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """The bar of config route_nowcast.adoption applied to each candidate; verdict = the first that passes, else N0."""
    a = cfg["route_nowcast"]["adoption"]
    t_min, rows = float(a["t_min"]), []
    for m in a["candidates"]:
        s = ns[(ns["scope"] == "own quarters") & (ns["model"] == m)].iloc[0]
        g = nd[(nd["forecast"] == "GR") & (nd["model"] == m)].iloc[0]
        test = (s["dm_t"] <= -t_min) or (s["enc_t"] >= t_min)
        now_ok = bool(s["rmse_ratio"] < 1 and test)
        nordic_ok = bool(g["rmse_ratio"] <= 1)
        rows.append({"model": m, "nowcast_rmse_ratio": s["rmse_ratio"], "nowcast_dm_t": s["dm_t"], "nowcast_enc_t": s["enc_t"],
                     "nowcast_bar_met": now_ok, "nordic_gr_rmse_ratio": g["rmse_ratio"], "nordic_bar_met": nordic_ok,
                     "adopted": now_ok and nordic_ok})
    out = pd.DataFrame(rows)
    passed = out[out["adopted"]]["model"].tolist()
    return out.assign(verdict=passed[0] if passed else a["default"])
