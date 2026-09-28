"""Risks the back-test cannot rule out, computed from the step-6c results and shown at the top of the step-6 report,
the model report, the dashboard and the results page. Every sentence is filled from data and every flag has a trigger
(config composite.risk_thresholds), so the box changes when the data change."""
from __future__ import annotations

import pandas as pd

from core.config import step_outputs

FILE = "composite_risks.csv"


def risk_flags(r: dict, cfg: dict) -> pd.DataFrame:
    cc = cfg["composite"]
    th = cc["risk_thresholds"]
    cb, cl, lv = r["concentration"]["bench"], r["concentration"]["longrun"], r["live"]
    worse = cb["last6_rmse_model"] > cb["last6_rmse_base"]
    gap = lv["beat_hat_pct"] - lv["ridge_beat_hat_pct"]
    usd = abs(gap) / 100 * lv["guide_mid"]
    scored = _prereg_scored()
    rows = [
        {"id": "R1", "risk": "Against the 4-quarter benchmark the gain comes from one cycle turn",
         "evidence": _r1_evidence(cb, cl, worse),
         "triggered": bool(cb["top3_share"] > th["top3_gain_share"] or worse)},
        {"id": "R2", "risk": "Factors chosen after seeing the data",
         "evidence": f"{cc['selection_history']} No back-test removes this. The only clean test: {cc['first_clean_test']}"
                     + (f" — {scored} pre-registered print(s) scored so far." if scored else " — none scored yet."),
         "triggered": scored == 0},
        {"id": "R3", "risk": "The composite and its ridge variant disagree on this quarter",
         "evidence": f"{lv['quarter']}: composite (equal weights) beat {lv['beat_hat_pct']:+.2f}% vs ridge challenger {lv['ridge_beat_hat_pct']:+.2f}% "
                     f"({gap:+.2f} pts = USD {usd:.1f}m on the USD {lv['guide_mid']:.0f}m midpoint). Which specification is right is unknown until the print.",
         "triggered": bool(abs(gap) > th["challenger_gap_pts"])},
        {"id": "R4", "risk": "Very few independent observations",
         "evidence": _neff_evidence(r["effective_n"]),
         "triggered": bool(r["effective_n"]["composite_C"]["n_eff"] < th["min_effective_n"])},
    ]
    pp = r.get("peer_panel")
    if pp is not None:
        m = pp["scores"].set_index("model").loc["FE + both"]
        sl = pp["slopes"]
        k = int(m["firms"])
        like = next((f for f in pp.get("meta", {}).get("fits", []) if f["sample"] == "Nordic-like peers"), None)
        mr = (f"A Nordic-like peer set ({like['n']} firms, distribution share >= 35%) predicts Nordic's slope from its distribution share at "
              f"{like['nordic_pred']['mid']['pred']:+.2f} (90% PI {like['nordic_pred']['mid']['pi90'][0]:+.2f} to {like['nordic_pred']['mid']['pi90'][1]:+.2f}); "
              f"distribution share itself explains nothing (t = {like['gamma1_t']:.1f}).") if like else ""
        rows.append({"id": "R5", "risk": f"The channel mechanism itself fails external validation on {k} peers",
                     "evidence": (f"Pooled over {int(m['firm_quarters'])} peer firm-quarters and several cycles, the same channel factors do not beat each "
                                  f"firm's own mean beat out of sample (OOS R² {m['oos_r2_vs_firm_mean']:+.3f}, better in {m['quarters_won_share']:.0%} of quarters). "
                                  f"On the industry factor Nordic's slope is {sl['nordic_industry_b']:+.2f} pts per sd vs {sl['peer_industry_b']:+.2f} for the peers. "
                                  + mr + (" " if mr else "") + "The composite's Nordic result is most likely specific to one cycle of one company."),
                     "triggered": bool(m["oos_r2_vs_firm_mean"] <= 0)})
        cy = pp.get("cycle")
        if cy is not None and len(cy):
            w = cy.set_index(["window", "who"])
            pe, no = w.loc[("nordic_window", "peers")], w.loc[("nordic_window", "NORDIC")]
            common = sorted(set(pe["top3_quarters"].split(", ")) & set(no["top3_quarters"].split(", ")))
            g1 = cy.attrs.get("gap_n_eff", {})
            rows.append({"id": "R6", "risk": "The channel mechanism rests on one cycle turn, for Nordic and for the peers",
                         "evidence": (f"Peers' slope by window: 2008-10 {w.loc[('gfc_2008_10', 'peers'), 'b_quarter_level']:+.2f}, 2011-19 "
                                      f"{w.loc[('normal_2011_19', 'peers'), 'b_quarter_level']:+.2f}, Nordic's window {pe['b_quarter_level']:+.2f} (se {pe['se_q_level_neff']:.2f}). "
                                      f"Three quarters carry {pe['top3_share']:.0%} of the peers' and {no['top3_share']:.0%} of Nordic's slope"
                                      + (f"; {', '.join(common)} are in both" if common else "") + ". "
                                      f"Nordic vs peers in the same window: t = {g1.get('t', float('nan')):.1f} after autocorrelation."),
                         "triggered": bool(pe["top3_share"] > 0.5 or no["top3_share"] > 0.5)})
    return pd.DataFrame(rows)


def _neff_evidence(ne: dict) -> str:
    c, b = ne["composite_C"], ne["beat"]
    return (f"The composite has {c['n']} quarterly values but lag-1 autocorrelation {c['rho1']:.2f}, so it holds about {c['n_eff']:.1f} independent "
            f"observations (Bartlett n(1-ρ)/(1+ρ)); the beat itself holds about {b['n_eff']:.1f} of {b['n']}. Every cycle-dependent conclusion rests on "
            "roughly one downturn and one upturn; each extra fitted parameter (absolute value, separate +/- slopes, regime switches) "
            "would be fitted to those. More independent evidence has to come from more cycles or more companies (peer panel), not from the model's form.")


def _share(c: dict) -> str:
    over = " — above 100% because the other quarters together lose" if c["top3_share"] > 1 else ""
    return f"the three best quarters ({', '.join(c['top3_quarters'])}) carry {c['top3_share']:.0%} of the gain{over}; the composite wins {c['quarters_won']} of {c['n']} quarters"


def _r1_evidence(cb: dict, cl: dict, worse: bool) -> str:
    """Both comparisons, because the concentration is a property of the baseline as much as of the composite."""
    return (f"(a) vs the past-4-quarter beat (the gate's benchmark): {_share(cb)}; over the last six quarters the composite is "
            f"{'WORSE' if worse else 'no worse'} (RMSE {cb['last6_rmse_model']:.2f} vs {cb['last6_rmse_base']:.2f} pts). "
            f"(b) vs the intercept-only model (mean of all past beats, no factors): {_share(cl)} (out-of-sample R² {cl['oos_r2']:+.2f}; "
            f"last six quarters {cl['last6_rmse_model']:.2f} vs {cl['last6_rmse_base']:.2f}). "
            f"Reading: {_reading(cb, cl)} Either way the sample holds one cycle.")


def _reading(cb: dict, cl: dict) -> str:
    """Conditional on the numbers: how different the two baselines' pictures really are."""
    wins = f"the composite wins more quarters against the intercept-only model ({cl['quarters_won']} vs {cb['quarters_won']} of {cb['n']})"
    if cl["top3_share"] > 0.5:
        return (f"{wins} and its top-3 share is lower ({cl['top3_share']:.0%} vs {cb['top3_share']:.0%}), but against both baselines "
                "three quarters still carry most of the gain — the concentration is only partly an artefact of the slow 4-quarter benchmark.")
    return (f"{wins} and three quarters carry only {cl['top3_share']:.0%} of that gain — the concentration against the 4-quarter "
            "benchmark is mostly that benchmark being slow to forget a finished destock.")


def _prereg_scored() -> int:
    f = step_outputs("step6_backtest") / "composite_prereg_log.csv"
    if not f.exists():
        return 0
    log = pd.read_csv(f, dtype=str).fillna("")
    return int((log["actual_usdm"] != "").sum())


def extension_flags(cfg: dict | None = None) -> pd.DataFrame:
    """R7-R8: what Nordic's own record extended to 2019Q1 (F32) shows about the guide-error rule in force; the rule is
    kept (F33) and these are disclosed. Read from steps/step7_forecast/outputs/guide_error_record_extension.csv."""
    f = step_outputs("step7_forecast") / "guide_error_record_extension.csv"
    if not f.exists():
        return pd.DataFrame()
    e = pd.read_csv(f, dtype=str, keep_default_na=False).iloc[0]
    e = e.map(lambda v: v if str(v).strip() else "nan")                 # an empty cell (no group, no walk-forward) reads as NaN
    shocks = "" if e["shock_quarters"] == "nan" else e["shock_quarters"].strip()
    lift = float(e["base_mean_pct"]) - float(e["base_mean_ex_shocks_pct"]) if shocks else 0.0
    r7 = {"id": "R7", "risk": "The channel state cannot see an end-demand shock",
          "evidence": (f"Nordic's record runs {e['first_quarter']}-{e['last_quarter']} ({e['n_guides']} guides, F32). Of the {e['n_base']} quarters "
                       f"that set the habit (channel neither building nor short), "
                       + (f"{shocks} had the guide raised before the print: errors {e['shock_errors_vs_initial_pct']} against the guide the model scores, "
                          f"{e['shock_errors_vs_last_guide_pct']} against the last guide, with the state reading '{e['shock_states']}'. "
                          if shocks else "none had the guide raised before the print. ")
                       + "The state variable is a channel stock (distributor days); it explains misses when "
                       f"distributors build (2023) and is blind to a demand shock (2020). Habit {float(e['base_mean_pct']):+.2f}% with those quarters, "
                       f"{float(e['base_mean_ex_shocks_pct']):+.2f}% without (n {e['n_base_ex_shocks']}); before 2021 {float(e['base_mean_before_2021_pct']):+.2f}% "
                       f"(n {e['n_base_before_2021']}), from 2021 {float(e['base_mean_from_2021_pct']):+.2f}% (n {e['n_base_from_2021']}). "
                       "The rule is kept as pre-stated (F33); the shock sits in the range, not in a new term."),
          "triggered": bool(shocks) and lift > 0.5}
    r8 = {"id": "R8", "risk": "The state split has no walk-forward edge on the longer record",
          "evidence": (f"Walk-forward over {e['wf_n']} quarters from 2023Q1: rule in force {float(e['wf_rmse_rule']):.2f} pts, guide midpoint (zero error) "
                       f"{float(e['wf_rmse_guide_mid']):.2f}, past-4-quarter beat {float(e['wf_rmse_past4']):.2f}, pooled with the peers {float(e['wf_rmse_pooled']):.2f} (F16 challenger). "
                       "The habit's sign replicates out of sample (Nordic guided below the outcome in 8 of the 9 quarters 2019Q1-2021Q1), the "
                       "claim that splitting it by channel state improves the forecast does not; the split is kept for its mechanism (F20, F30), "
                       "and every challenger is scored at the print."),
          "triggered": bool(float(e["wf_rmse_rule"]) >= float(e["wf_rmse_guide_mid"]) - 0.1 or float(e["wf_rmse_pooled"]) < float(e["wf_rmse_rule"]))}
    return pd.DataFrame([r7, r8])


def load_flags() -> pd.DataFrame | None:
    """Step-6 flags (R1-R6) plus the step-7 record-extension flags (R7-R8) when that file exists."""
    f = step_outputs("step6_backtest") / FILE
    base = pd.read_csv(f) if f.exists() else None
    ext = extension_flags()
    if base is None:
        return ext if len(ext) else None
    return pd.concat([base, ext], ignore_index=True) if len(ext) else base


def risk_box_md(flags: pd.DataFrame | None) -> str:
    """A blockquote the results page styles as a red warning box."""
    if flags is None or not flags["triggered"].any():
        return ""
    lines = ["> ### ⚠ Risks the tests cannot rule out (R1-R6 the composite channel factor, a pre-registered challenger; R7-R8 Nordic's own guide-error record, F32)", ">"]
    for _, f in flags[flags["triggered"]].iterrows():
        lines.append(f"> **{f['id']}. {f['risk']}.** {f['evidence']}")
        lines.append(">")
    return "\n".join(lines[:-1]) + "\n"


def risk_box_html(flags: pd.DataFrame | None) -> str:
    if flags is None or not flags["triggered"].any():
        return ""
    items = "".join(f"<li><b>{f['id']}. {f['risk']}.</b> {f['evidence']}</li>" for _, f in flags[flags["triggered"]].iterrows())
    return ('<div style="border:2px solid #c0392b;background:#fdecea;border-radius:8px;padding:10px 16px;margin:16px 0">'
            '<div style="font-weight:700;color:#c0392b;font-size:15px">⚠ Risks the tests cannot rule out — R1-R6 the composite channel factor (pre-registered challenger, not in the forecast); R7-R8 Nordic&#39;s own guide-error record (F32)</div>'
            f'<ol style="margin:8px 0 0 0;padding-left:20px;font-size:13px;line-height:1.5">{items}</ol></div>')
