"""Step 5g addendum: does the Q4 point model agree with the industry-cycle challenger about the cycle beyond the slice?

CH (step 7c) is the chain as reasoned: it speaks only for the Logitech / GN slice of Nordic. Any model minus CH is therefore
the part of Nordic it sees beyond the slice. Compared per quarter (step 6 h=2 walk-forward) and live (Q4 2026):
    GRi - CH   the point model since F26 (Logitech sell-in, Nordic -> ODM -> Logitech segment, forecast fill)
    GR  - CH   the previous point model, now a challenger
    CYC - CH   the industry-cycle challenger (G29: US electronics-store sales)
    actual - CH  what the slice missed in fact
Levels differ by each model's own bias, so the live gap is also read against the model's own historical mean gap
("anomaly"): two models agree on THIS quarter only if their anomalies agree, not just their levels. Kept outside the
pre-registered CYC files so their spec hash does not move.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import step_outputs

MODELS = ["GRi", "GR", "CYC"]


def history(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per h=2 target: actual, CH, GR, GRi (step 6 walk-forward, recomputed) and CYC (step 5g output of this run)."""
    from walkforward import walk_forward                  # steps/step6_backtest/src
    h = int(cfg["cycle_challenger"]["horizon"])
    wf = walk_forward(p, cfg, None, h=h)
    q = wf["quarter"] if "quarter" in wf else wf.index
    s6 = pd.DataFrame({"GRi_total": wf["GRi_total"].values, "GR_total": wf["GR_total"].values}, index=[str(x) for x in q])
    cy = pd.read_csv(step_outputs("step5_supply_graph") / "cycle_challenger.csv")
    cy = cy[cy["kind"] == "walkforward"].set_index("quarter")[["CYC_total", "CH_total", "actual_total"]]
    d = cy.join(s6, how="inner").dropna()
    return d.assign(**{f"{m}_minus_CH": d[f"{m}_total"] - d["CH_total"] for m in MODELS},
                    actual_minus_CH=d["actual_total"] - d["CH_total"])


def live(p: pd.DataFrame, cfg: dict) -> dict:
    """Live Q4 gaps (ex the incident term, which every model carries equally)."""
    from walkforward import live_forecasts
    cc = cfg["cycle_challenger"]
    lv = live_forecasts(p, cfg, None, {int(cc["horizon"]): cc["live_target"]}).reset_index()
    cy = pd.read_csv(step_outputs("step5_supply_graph") / "cycle_challenger.csv")
    c = cy[cy["kind"] != "walkforward"].iloc[-1]
    ch = float(c["CH_total"])
    return {"quarter": cc["live_target"], "CH_total": ch, "GRi_minus_CH": float(lv["GRi_total"].iloc[0]) - ch,
            "GR_minus_CH": float(lv["GR_total"].iloc[0]) - ch, "CYC_minus_CH": float(c["CYC_total"]) - ch}


def summary(d: pd.DataFrame, lv: dict) -> pd.DataFrame:
    rows = []
    act = d["actual_minus_CH"]
    for m in MODELS:
        g = d[f"{m}_minus_CH"]
        rows.append({"model": m, "n": len(d), "hist_mean_gap": g.mean(), "corr_with_actual_gap": float(np.corrcoef(g, act)[0, 1]),
                     "rmse_usdm": float(np.sqrt(((d[f"{m}_total"] - d["actual_total"]) ** 2).mean())),
                     "live_gap": lv[f"{m}_minus_CH"], "live_anomaly": lv[f"{m}_minus_CH"] - g.mean()})
    rows.append({"model": "actual", "n": len(d), "hist_mean_gap": act.mean()})
    return pd.DataFrame(rows)


def sentences(s: pd.DataFrame) -> list[str]:
    r = s.set_index("model")
    gi, gr, cy, a = r.loc["GRi"], r.loc["GR"], r.loc["CYC"], r.loc["actual"]
    agree_level = abs(gi["live_gap"] - cy["live_gap"]) < abs(gr["live_gap"] - cy["live_gap"])
    same_sign_anom = np.sign(gi["live_anomaly"]) == np.sign(cy["live_anomaly"])
    return [
        f"- Live Q4 gap to CH: GRi {gi['live_gap']:+.1f}, GR {gr['live_gap']:+.1f}, CYC {cy['live_gap']:+.1f} USD m. In level, "
        f"{'GRi is closer to CYC than GR was' if agree_level else 'GR is closer to CYC than GRi'}.",
        f"- Against each model's own history ({int(gi['n'])} quarters): mean gaps GRi {gi['hist_mean_gap']:+.1f}, GR "
        f"{gr['hist_mean_gap']:+.1f}, CYC {cy['hist_mean_gap']:+.1f}; the actual was {a['hist_mean_gap']:+.1f} above CH on average. "
        f"Live anomalies: GRi {gi['live_anomaly']:+.1f}, CYC {cy['live_anomaly']:+.1f} - "
        f"{'the same direction' if same_sign_anom else 'opposite directions'}: "
        f"{'the level agreement is also an agreement about this quarter' if same_sign_anom else 'the level agreement is a coincidence of two biases, not a shared reading of this quarter'}.",
        f"- Which gap tracks what CH missed (correlation with actual - CH): GRi {gi['corr_with_actual_gap']:.2f}, GR "
        f"{gr['corr_with_actual_gap']:.2f}, CYC {cy['corr_with_actual_gap']:.2f}; RMSE GRi {gi['rmse_usdm']:.1f}, GR {gr['rmse_usdm']:.1f}, "
        f"CYC {cy['rmse_usdm']:.1f}."]


def run(p: pd.DataFrame, cfg: dict, write: bool = True) -> dict:
    d, lv = history(p, cfg), live(p, cfg)
    s = summary(d, lv)
    if write:
        o = step_outputs("step5_supply_graph")
        d.round(2).to_csv(o / "cycle_decomposition.csv")
        s.round(2).to_csv(o / "cycle_decomposition_summary.csv", index=False)
        (o / "cycle_decomposition.md").write_text("\n".join(
            ["# Cycle beyond the slice: point model vs the industry-cycle challenger (step 5g addendum)\n", __doc__.strip(), "",
             *sentences(s), "", s.round(2).to_markdown(index=False), "", d.round(1).to_markdown(), ""]))
    return {"history": d, "live": lv, "summary": s}
