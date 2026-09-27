"""Pre-registration of Nordic Q4 2026 (h = 2), decision F22: the point model (GRi since F26; GR before) is the forecast,
GR and CH (the chain as reasoned, nothing fitted) the challengers, all with the incident's Q4 term (F21), next to the
guide-anchored benchmark carried forward (GB). One row per model, appended only when the spec or the data changes;
the last rows before the print (early February 2027) are the forecast of record. Score by filling actual_usdm.

Unlike the step 6c log (P101), the spec fingerprint covers the graph: the supply-graph config, the edge table, the 10-K
weights, the step 3 slice multiplier, the step 2 share path and the code that turns them into GR and CH.
"""
from __future__ import annotations

import hashlib
from datetime import date

import pandas as pd

from core.config import ROOT

LOG = ROOT / "steps" / "step7_forecast" / "outputs" / "q4_prereg_log.csv"
SPEC_FILES = [ROOT / "config" / f for f in ("supply_graph.csv", "supply_graph_weights.csv", "supply_graph_nodes.csv")] + [
    ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "slice_multiplier.csv",
    ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv",
    ROOT / "steps" / "step5_supply_graph" / "src" / "supply_graph.py",
    ROOT / "steps" / "step6_backtest" / "src" / "walkforward.py",
    ROOT / "steps" / "step7_forecast" / "src" / "chain_forecast.py",
    ROOT / "steps" / "step7_forecast" / "src" / "forecast_next.py"]
SPEC_CFG = ("supply_graph", "forecast_next_quarter", "chain_forecast", "backtest", "regression", "regimes")
DATA_COLS = ("nordic_rev", "nordic_consumer", "nordic_guide_mid", "logi_sales", "logi_st_gap", "logi_guide_mid")


def spec_hash(cfg: dict) -> str:
    h = hashlib.sha1(repr([cfg.get(k) for k in SPEC_CFG]).encode())
    for f in SPEC_FILES:
        h.update(f.read_bytes() if f.exists() else b"missing:" + f.name.encode())
    return h.hexdigest()[:10]


def data_hash(p: pd.DataFrame, event_usdm: float) -> str:
    cols = [c for c in DATA_COLS if c in p]
    return hashlib.sha1((p[cols].round(4).to_csv() + f"{event_usdm:.4f}").encode()).hexdigest()[:10]


def rows_now(nxt: pd.DataFrame, chain: dict, cfg: dict) -> list[dict]:
    """The point model (forecast; GRi from F26), GR and CH (challengers) for the h = 2 target, all with the incident's Q4 term."""
    n = nxt.set_index("model")
    point_model = cfg["forecast_next_quarter"]["point_model"]
    gr, gb = n.loc[point_model], n.loc["GB"]
    ev = float(chain["incident"]["nordic_q4_usdm"])
    h2 = chain["nordic"]["horizons"][2]
    ch_point = float(h2["live"]["CH_total"]) + ev
    ch_band = float(cfg["forecast_next_quarter"]["band_z"]) * float(h2["tests"]["CH"]["rmse"])
    base = {"target": str(gr["quarter"]), "benchmark_gb_usdm": round(float(gb["point"]), 1), "event_usdm": round(ev, 2)}
    rows = [{**base, "model": point_model, "role": "forecast", "point": round(float(gr["point"]), 1), "low": round(float(gr["low"]), 1),
             "high": round(float(gr["high"]), 1), "wf_rmse_usdm": round(float(gr["wf_rmse_usdm"]), 1)}]
    if point_model != "GR" and "GR" in n.index:          # F26: GR, the point until then, stays logged as a challenger
        g = n.loc["GR"]
        rows.append({**base, "model": "GR", "role": "challenger", "point": round(float(g["point"]), 1), "low": round(float(g["low"]), 1),
                     "high": round(float(g["high"]), 1), "wf_rmse_usdm": round(float(g["wf_rmse_usdm"]), 1)})
    return rows + [
            {**base, "model": "CH", "role": "challenger", "point": round(ch_point, 1), "low": round(ch_point - ch_band, 1),
             "high": round(ch_point + ch_band, 1), "wf_rmse_usdm": round(float(h2["tests"]["CH"]["rmse"]), 1)}]


def log_q4(nxt: pd.DataFrame, chain: dict, p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    s, d = spec_hash(cfg), data_hash(p, float(chain["incident"]["nordic_q4_usdm"]))
    new = [{**r, "spec_hash": s, "data_hash": d, "logged_on": date.today().isoformat(), "actual_usdm": "", "scored_on": "",
            "abs_error_usdm": "", "benchmark_abs_error_usdm": "", "closer_than_benchmark": ""} for r in rows_now(nxt, chain, cfg)]
    log = pd.read_csv(LOG, dtype=str) if LOG.exists() else pd.DataFrame(columns=list(new[0]))
    seen = (log["spec_hash"] == s) & (log["data_hash"] == d) & (log["target"] == new[0]["target"])
    if not seen.any():
        log = pd.concat([log, pd.DataFrame(new).astype(str)], ignore_index=True)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        log.to_csv(LOG, index=False)
    return log


def score(log: pd.DataFrame, actual_usdm: float, scored_on: str) -> pd.DataFrame:
    """Fill the outcome into the forecast-of-record rows (the last spec/data pair logged before the print)."""
    log = log.copy()
    last = log.iloc[-1][["spec_hash", "data_hash", "target"]]
    m = (log["spec_hash"] == last["spec_hash"]) & (log["data_hash"] == last["data_hash"]) & (log["target"] == last["target"])
    pt, gb = log.loc[m, "point"].astype(float), log.loc[m, "benchmark_gb_usdm"].astype(float)
    log.loc[m, "actual_usdm"] = str(actual_usdm)
    log.loc[m, "scored_on"] = scored_on
    log.loc[m, "abs_error_usdm"] = (pt - actual_usdm).abs().round(1).astype(str)
    log.loc[m, "benchmark_abs_error_usdm"] = (gb - actual_usdm).abs().round(1).astype(str)
    log.loc[m, "closer_than_benchmark"] = ((pt - actual_usdm).abs() < (gb - actual_usdm).abs()).astype(str)
    return log
