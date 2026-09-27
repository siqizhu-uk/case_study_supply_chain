"""The Nordic Q4 (h = 2) lines as the displays show them: the point model (is_point in forecast_next_quarter.csv; GRi
since F26), GR and the reasoned chain CH as challengers, and step 5g's industry-cycle challenger (CYC, G29) with the
one-line decomposition against CH. CYC is pre-registered, not in the Q4 forecast. Everything is read from outputs."""
from __future__ import annotations

import pandas as pd

from core.config import OUTPUTS, ROOT

S5 = ROOT / "steps" / "step5_supply_graph" / "outputs"
S6 = ROOT / "steps" / "step6_backtest" / "outputs"
LABEL = "CYC (industry-cycle challenger, pre-registered, not in the forecast)"
AGREE_USDM = 5.0            # two lines within this of each other (USDm) are read as agreeing; well inside every h=2 RMSE


def q4() -> dict | None:
    """The point model's row and GR's, from outputs/forecast_next_quarter.csv; None before step 7b has run."""
    try:
        n = pd.read_csv(OUTPUTS / "forecast_next_quarter.csv")
    except FileNotFoundError:
        return None
    pt = n[n["is_point"].astype(str).str.lower() == "true"].iloc[0]
    gr = n.set_index("model").loc["GR"]
    return {"model": str(pt["model"]), "quarter": str(pt["quarter"]), "point": float(pt["point"]), "low": float(pt["low"]),
            "high": float(pt["high"]), "rmse": float(pt["wf_rmse_usdm"]), "ratio": float(pt["rmse_ratio_vs_GB"]), "n": int(pt["wf_n"]),
            "gr_point": float(gr["point"]), "gr_low": float(gr["low"]), "gr_high": float(gr["high"]),
            "gr_rmse": float(gr["wf_rmse_usdm"]), "gr_ratio": float(gr["rmse_ratio_vs_GB"])}


def cyc() -> dict | None:
    """Last pre-registered CYC row + its h=2 record; None if step 5g or step 7b has not run."""
    try:
        r = pd.read_csv(S5 / "cycle_challenger_prereg_log.csv").iloc[-1]
        s = pd.read_csv(S5 / "cycle_challenger_scores.csv")
    except (FileNotFoundError, IndexError):
        return None
    q = q4()
    if q is None:
        return None
    main = s[(s["scope"] == "main") & (s["vs"] == "GR") & (s["model"] == "CYC")].iloc[0]
    ch = float(r["ch_usdm"])
    return {"quarter": str(r["target"]), "point": float(r["point"]), "low": float(r["low"]), "high": float(r["high"]),
            "ch": ch, "bar_met": str(r["bar_met"]).lower() == "true", "check_on": str(r["check_on"]),
            "n": int(main["n"]), "rmse": float(main["rmse"]), "rmse_gr": float(main["rmse_bench_same_quarters"]),
            "bias": float(main["bias"]), "dm_t": float(main["dm_t"]), "q4": q,
            "point_minus_ch": q["point"] - ch, "gr_minus_ch": q["gr_point"] - ch, "cyc_minus_ch": float(r["point"]) - ch}


def _anomalies() -> pd.DataFrame | None:
    """Step 5g addendum (G30): each model's live gap to CH against its own historical mean gap; None if not run."""
    try:
        return pd.read_csv(S5 / "cycle_decomposition_summary.csv").set_index("model")
    except FileNotFoundError:
        return None


def decomposition(c: dict) -> str:
    q = c["q4"]
    head = (f"Beyond the Logitech / GN slice (CH {c['ch']:.1f}m): {q['model']} {c['point_minus_ch']:+.1f}m, CYC {c['cyc_minus_ch']:+.1f}m, "
            f"GR {c['gr_minus_ch']:+.1f}m. ")
    an = _anomalies()
    if an is None or q["model"] not in an.index or "CYC" not in an.index:
        return head + f"CYC's walk-forward bias ({c['bias']:+.1f}m) says its line more likely errs low."
    a_pt, a_cyc = float(an.loc[q["model"], "live_anomaly"]), float(an.loc["CYC", "live_anomaly"])
    same_level = abs(c["point_minus_ch"] - c["cyc_minus_ch"]) < AGREE_USDM
    if same_level and a_pt * a_cyc < 0:
        return head + (f"The levels match, but against each model's own history (mean gap {an.loc[q['model'], 'hist_mean_gap']:+.1f} vs "
                       f"{an.loc['CYC', 'hist_mean_gap']:+.1f}) the live readings point opposite ways ({q['model']} {a_pt:+.1f}, CYC {a_cyc:+.1f}): "
                       f"two biases crossing, not a shared reading of Q4; CYC does not corroborate {q['model']}'s low Q4 (G30, P121).")
    agree = "agree" if a_pt * a_cyc > 0 else "disagree"
    return head + (f"Against each model's own history the live readings {agree} ({q['model']} {a_pt:+.1f}, CYC {a_cyc:+.1f}; G30).")


def record(c: dict) -> str:
    q = c["q4"]
    vs = f"GR {c['rmse_gr']:.1f}m" + (f", {q['model']} {q['rmse']:.1f}m" if q["model"] != "GR" else "")
    return (f"h=2 walk-forward RMSE {c['rmse']:.1f}m vs {vs} (n {c['n']}, DM t vs GR {c['dm_t']:+.1f}); "
            f"adoption bar {'met' if c['bar_met'] else 'not met'}; scored {c['check_on']}")
