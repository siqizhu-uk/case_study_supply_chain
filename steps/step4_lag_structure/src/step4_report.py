"""Step 4 write-up (outputs/step4_report.md), generated from the lag analysis (lags.py) and step 5's continuous-lag check.

Order of the report = order of the reasoning: the reasoned lag first (the documented prior, decision L1), then the
empirical correlation, labelled for what it measures - the timing of Nordic's consumer revenue against the downstream /
industry cycle, not the Logitech -> Nordic chain lag (decision L2). Every number is read from an output file or config.
"""
from __future__ import annotations

import pandas as pd

from edge_lags_report import section_md
from core.config import step_outputs

CONTINUOUS = "graph_vs_step4_continuous_lag.csv"   # steps/step5_supply_graph/outputs (decision G21)
SAMPLE = "all quarters"


def load_continuous() -> pd.DataFrame | None:
    """Step 5's continuous-lag table; None if step 5 has not written it yet (report then says so, no number invented)."""
    path = step_outputs("step5_supply_graph") / CONTINUOUS
    return pd.read_csv(path) if path.exists() else None


def _label(driver: str) -> str:
    return driver.removeprefix("control: ").split(" (")[0]


def _controls_line(cl: pd.DataFrame) -> tuple[str, list[str]]:
    """(c): each common-cycle control's timing and its paired difference to the step 4 driver (all-quarters sample); and the
    controls whose difference cannot be told from zero."""
    ct = cl[(cl["kind"] == "control") & (cl["sample"] == SAMPLE)]
    parts, same = [], []
    for r in ct.itertuples():
        zero = r.diff_ci_lo_weeks <= 0 <= r.diff_ci_hi_weeks
        parts.append(f"{_label(r.driver)} {r.tau_weeks:.0f} weeks (n {r.n}; minus the Logitech driver on the same "
                     f"{int(r.diff_n)} quarters {r.diff_vs_step4_driver_weeks:+.0f}, 90% CI {r.diff_ci_lo_weeks:+.0f} to "
                     f"{r.diff_ci_hi_weeks:+.0f}: {'cannot be told apart' if zero else 'different'})")
        same += [_label(r.driver)] if zero else []
    return "; ".join(parts), same


def _reading(cl: pd.DataFrame | None, attr: dict, gap: float) -> list[str]:
    """(a)-(e) of decision L2, numbers from step 2 (attribution) and step 5 (continuous lag)."""
    tot, con = attr["combined_pct_of_nordic_total"], attr["combined_pct_of_nordic_consumer"]
    lines = ["**How to read it (decision L2).**\n",
             "- (a) **Driver = Logitech sell-in.** `logi_ble_yoy` is Logitech's reported revenue in its radio categories, i.e. what "
             "Logitech sells into its channel, not what consumers buy.",
             f"- (b) **Target = all consumer customers.** Nordic Consumer revenue covers every consumer customer; Logitech + GN are "
             f"≈{tot['p50']:.0f}% of Nordic revenue (80% range {tot['p10']:.0f}–{tot['p90']:.0f}%), ≈{con['p50']:.0f}% of Nordic "
             "Consumer (step 2). Most of what the correlation sees is not Logitech's orders."]
    if cl is None:
        return lines + ["- (c)-(d) Step 5's continuous-lag check (`" + CONTINUOUS + "`) has not been run yet.\n"]
    s4 = cl[(cl["kind"] == "sell-in") & (cl["sample"] == SAMPLE)].iloc[0]
    so = cl[(cl["kind"] == "sell-out proxy") & (cl["sample"] == SAMPLE)].iloc[0]
    text, same = _controls_line(cl)
    head = (f"Common-cycle controls give the same timing: {' and '.join(same)}" if same
            else "No common-cycle control gives the same timing")
    return lines + [
        f"- (c) **{head}** (step 5, decision G21, `{CONTINUOUS}`). On a continuous lag Nordic lags Logitech sell-in by "
        f"{s4.tau_weeks:.0f} weeks (n {s4.n} from {s4.first_quarter}); drivers outside the chain: {text}. Where the difference "
        "cannot be told from zero, the '2-quarter' timing is the consumer-electronics / semiconductor cycle at Nordic, not a "
        "Logitech -> Nordic order lag.",
        f"- (d) **The data do not pin the lag.** One down-up cycle ({s4.n} quarters from {s4.first_quarter}): every lag from "
        f"{s4.near_optimal_lo_weeks:.0f} to {s4.near_optimal_hi_weeks:.0f} weeks fits within {gap} of the best correlation "
        f"(90% bootstrap CI {s4.ci_lo_weeks:.0f}–{s4.ci_hi_weeks:.0f} weeks). The integer '2 quarters' below had no band at all.",
        f"- (e) **The reasoned lag stays the documented prior** (decision L1); step 5's supply graph is its flow-weighted "
        f"refinement (≈{so.like_graph_weeks:.0f} weeks sell-out -> Nordic). No lag in `config/model.yaml` is set from this "
        "correlation, and no two-factor regression (Logitech + cycle) is fitted (decision L3).\n"]


def step4_md(lag: dict, cfg: dict, attr: dict) -> str:
    """Step 4 report: reasoned lag first, then the timing check with its reading."""
    r, amp, tp = lag["reasoned"], lag["amplitude"], lag["turning_points"]
    xa = lag["xcorr_all"].dropna()
    best = xa.loc[xa["corr"].idxmax()] if len(xa) else None
    peak = (f"Integer-lag correlation of Nordic consumer YoY with Logitech sell-in YoY peaks at **{int(best['lag_q'])}q** "
            f"(r = {best['corr']:.2f}, n = {int(best['n'])}): a timing statistic, not the chain lag (read with (a)-(e) above)."
            if best is not None else "Correlation not computable.")
    md = ["# Step 4 — Revenue propagation (lag structure)\n",
          "## 1. Reasoned lag (stated before any data; the documented prior, decision L1)\n",
          f"Sell-out → Nordic revenue: **{r['low']['weeks']} / {r['mid']['weeks']} / {r['high']['weeks']} weeks** "
          f"(≈ {r['low']['quarters']} / {r['mid']['quarters']} / {r['high']['quarters']} quarters). Per tier (weeks, mid): "
          + ", ".join(f"{k} {v['mid']}" for k, v in cfg["lag_weeks"].items()) + ".\n",
          "## 2. Nordic consumer revenue vs the downstream / industry cycle: timing\n",
          *_reading(load_continuous(), attr, cfg["supply_graph"]["lag_check"]["near_optimal_corr_gap"]), peak,
          "", lag["xcorr_all"].round(2).to_markdown(index=False), "", "By regime:\n", lag["xcorr_by_regime"].round(2).to_markdown(index=False), "",
          "Turning points (peak / trough of YoY growth, sign changes):\n",
          pd.DataFrame(tp).T.astype(str).to_markdown(), "",
          f"Amplitude (Nordic consumer swing ÷ Logitech radio swing, peak-to-trough): destock {amp['destock_2022_2024']:.1f}×, recovery "
          f"{amp['recovery_2024_2026']:.1f}× — step 3 shows the recovery figure is a small-denominator artefact and that the whole-company "
          "amplitude does not apply to the Logitech slice.\n",
          "Out of sample (step 6 walk-forward): the Logitech-driven lag models are informative for the quarter AFTER the guided one, "
          "not for the guided quarter - as a proxy for the common consumer cycle, not for the Logitech / GN slice.\n",
          "![xcorr](xcorr.png)\n"]
    edge = [section_md(lag["edge_lags"], cfg)] if lag.get("edge_lags") else []
    return "\n".join(md + edge + ["Decisions: `config/decisions.csv` (L1–L9).\n"])
