"""Dashboard forecast section: what each range is, what the beat's sigma is made of, how much the Nordic point depends
on the channel-regime call, the graph-driven Q4 line, and rule-based colours for the indicators that used to be fixed.

Thresholds live in config/model.yaml `dashboard_rules` (decision F9); nothing here changes a forecast.
"""
from __future__ import annotations

import html

import numpy as np

import pandas as pd

from core.config import OUTPUTS, ROOT, load_config
import cycle_view  # noqa: E402   step 5g industry-cycle Q4 challenger (CYC, G29)

GEM = ROOT / "steps" / "step7_forecast" / "outputs" / "guide_error_model.csv"              # guide-error model (F16)
GES = ROOT / "steps" / "step7_forecast" / "outputs" / "guide_error_state_effect.csv"
CYCLE_NOW = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "cycle_state_now.csv"

BASIS_LABEL = {
    "statistical": "statistical ≈80%: ±1.28 × σ × guide midpoint",
    "scenario": "scenario: low / high organic growth (not a probability band)",
    "config": "set in config/model.yaml (judgment)",
    "margin_walkforward": "statistical ≈80%: ±1.28 × the margin rule's walk-forward error (F18)",
    "margin_regime": "statistical ≈80%: ±1.28 × the margin rule's error in current-regime quarters (F18)",
    "gn_organic": "statistical ≈80%: ±1.28 × σ of the implied H2 organic growth, from GN's own August-guide errors (F23)",
    "gn_ebita": "statistical ≈80%: ±1.28 × √(FY-margin error² + Q3-share spread²) (F18, F23)",
    "graph": "statistical + graph scenario: ±√((1.28 × h=2 RMSE)² + (½ lag-scenario spread)²)",
}
STATUS_COL = {"green": "#2e8b57", "amber": "#d99a00", "red": "#c0392b", "judgment": "#8a8f98", "context": "#9a9a94"}


def range_basis(row: dict, cfg: dict) -> str:
    """Which kind of range a forecasts.csv row carries (keyed on the print's company and the metric)."""
    rules = cfg["dashboard_rules"]["range_basis"]
    company = row["print"].split()[0].lower()
    metric = row["metric"].lower()
    for r in rules:
        if company == r["company"] and metric.startswith(r["metric_prefix"].lower()):
            return r["basis"]
    raise KeyError(f"no range basis configured for {row['print']} / {row['metric']} (config dashboard_rules.range_basis)")


def _beat_row(gb: pd.DataFrame, company: str, window: str) -> pd.Series:
    return gb[(gb["company"] == company) & gb["window"].str.startswith(window)].iloc[0]


MODEL_SOURCES = ("guide-error model", "own record by channel state")      # F16 pooled; F20 Nordic on its own record


def _model_on(f: dict) -> bool:
    """True when the expected error comes from guide_error_model.py (any of its methods), so the dashboard describes that
    model; False falls back to the historical-beat texts."""
    return str(f.get("beat_source", "")).startswith(MODEL_SOURCES) and GEM.exists()


def method_line(fn: dict) -> str:
    """One line under the forecast table saying how the points are built (follows the method in force)."""
    if _model_on(fn):
        return ("Guide midpoint × (1 + expected guide error) + supply-chain terms and graph-propagated events (7c, 5d). Expected error: "
                "Nordic = its own record by the data-dated channel state, supply-shortage quarters split out (F20, D24; F30 post-hoc); "
                "the F16 pooled model, the rule before F30 and Nordic's own words (F31) are pre-registered challengers; "
                "Logitech = habit pooled with 12 peers + channel state (F16), guide method only (F29); GN = plain mean of its own "
                "August-guide misses (F17, F23) + FX at ECB rates since the guide (F27); margins = guide + own past error where a "
                "point guide exists, else the rule with the lowest walk-forward error (F18)")
    return "Guide midpoint × (1 + historical beat in the current channel regime) + named adjustments; GN bottom-up (no quarterly guide)"


def beat_footnote(fn: dict, fl: dict, gb: pd.DataFrame, cfg: dict) -> str:
    """What the expected guide error in each band is made of. Guide-error model (F16): company habit (own record,
    partially pooled with the 12 peers) + channel-state effect, and the predictive sd used for the band. Otherwise the
    historical beat: its sigma and n, plus the added model uncertainty."""
    if _model_on(fn):
        gem = pd.read_csv(GEM).set_index("company")
        parts = []
        for name in ("Nordic", "Logitech"):
            r = gem.loc[name]
            if "own_building_effect" in r and pd.notna(r["own_building_effect"]):
                sh = f"; shortage {r['own_shortage_effect']:+.2f} pts, n {int(r['n_shortage'])}" if "n_shortage" in r and pd.notna(r.get("n_shortage")) else ""
                parts.append(f"{name} expected guide error {r['pred_expected_error'] + 0.0:+.2f}% = own record when the channel was neither building "
                             f"nor short of supply ({r['alpha']:+.2f}%, n {int(r['n_not_building'])}; building {r['own_building_effect']:+.2f} pts, "
                             f"n {int(r['n_building'])}{sh}; F30, adopted after seeing the data, walk-forward not better than the rule before) "
                             f"with the state now '{r.get('pred_state_nordic', r['pred_state'])}' ({r['pred_gamma_applied'] + 0.0:+.2f}); "
                             f"predictive σ {r['pred_sd']:.2f} in the band")
                continue
            small = " — small sample" if int(r["n"]) < cfg["dashboard_rules"]["min_n_beat"] else ""
            pool = ", pooled with the 12 peers" if bool(r["pooled"]) else ""
            parts.append(f"{name} expected guide error {r['pred_expected_error'] + 0.0:+.2f}% = habit {r['alpha']:+.2f}% (own record "
                         f"{r['own_mean']:+.2f}% on n {int(r['n'])}{small}, own weight {r['weight_own']:.0%}{pool}) + channel state "
                         f"'{r['pred_state']}' ({r['pred_gamma_applied'] + 0.0:+.2f}); predictive σ {r['pred_sd']:.2f} in the band")
        return "; ".join(parts)
    parts = []
    for name, f, window, key in (("Nordic", fn, fn.get("regime_window", "normal"), "nordic_2026Q3"), ("Logitech", fl, "quarterly", "logitech_2026Q3")):
        r = _beat_row(gb, name, window)
        extra = float(cfg["forecast"][key].get("extra_uncertainty_pct", 0))
        small = " — small sample" if int(r["n"]) < cfg["dashboard_rules"]["min_n_beat"] else ""
        parts.append(f"{name} beat {float(f['hist_beat_pct']):+.2f}% (historical σ {float(r['std_pct']):.2f} on n {int(r['n'])}, {r['window']}{small}; "
                     f"+ {extra:.1f} model uncertainty → σ {float(f['hist_beat_sd_pct']):.2f} in the band)")
    return "; ".join(parts)


def state_sensitivity(fn: dict) -> dict | None:
    """Nordic's point now and if the channel turned to 'building' (guide-error model's state effect), adjustments fixed."""
    if not (_model_on(fn) and GES.exists()):
        return None
    ges = pd.read_csv(GES).set_index("lag")
    gem = pd.read_csv(GEM).set_index("company").loc["Nordic"]
    lag_used = int(ges.index[ges["gamma_used"].notna()][0])
    g = float(ges.loc[lag_used, "gamma_used"])
    own = "own_building_effect" in gem and pd.notna(gem["own_building_effect"])
    effect = float(gem["own_building_effect"]) if own else g                   # F20: Nordic's own building effect
    mid = float(fn["guide_mid"])
    adj = float(fn["point"]) - mid * (1 + float(fn["hist_beat_pct"]) / 100)
    now = pd.read_csv(CYCLE_NOW).iloc[0] if CYCLE_NOW.exists() else None
    probs = eval(now["next_state_probs"], {"__builtins__": {}}) if now is not None else {}      # noqa: S307  a dict literal we wrote
    other = [l for l in ges.index if l != lag_used]
    sh = float(gem["own_shortage_effect"]) if own and pd.notna(gem.get("own_shortage_effect")) else None     # F30 / D24
    return {"state": gem["pred_state"], "state_nordic": gem.get("pred_state_nordic", gem["pred_state"]),
            "applied": float(gem["pred_gamma_applied"]) + 0.0,
            "latest_quarter": now["latest_quarter"] if now is not None else "",
            "base_point": float(fn["point"]),
            "building_point": mid * (1 + (float(gem["alpha"]) + effect) / 100) + adj, "building_effect": effect, "own_effect": own,
            "shortage_point": None if sh is None else mid * (1 + (float(gem["alpha"]) + sh) / 100) + adj, "shortage_effect": sh,
            "n_shortage": int(gem["n_shortage"]) if own and pd.notna(gem.get("n_shortage")) else None,
            "shortage_weeks": float(load_config()["cycle_state"]["shortage"]["lead_time_min_weeks"]),
            "gamma": g, "gamma_t": float(ges.loc[lag_used, "t"]), "gamma_n": int(ges.loc[lag_used, "n"]),
            "gamma_alt": float(ges.loc[other[0], "gamma"]) if other else np.nan, "alt_lag": other[0] if other else None,
            "p_building_next": float(probs.get("building", np.nan))}


def regime_sensitivity(fn: dict, gb: pd.DataFrame) -> pd.DataFrame:
    """The Nordic point under each channel regime's historical beat, adjustments held fixed."""
    mid = float(fn["guide_mid"])
    adj = float(fn["point"]) - mid * (1 + float(fn["hist_beat_pct"]) / 100)
    rows = []
    for regime, window in (("normal", "normal"), ("destock", "destock"), ("all quarters", "all")):
        r = _beat_row(gb, "Nordic", window)
        rows.append({"regime": regime, "window": r["window"], "beat_pct": float(r["mean_beat_pct"]), "n": int(r["n"]),
                     "point": mid * (1 + float(r["mean_beat_pct"]) / 100) + adj})
    return pd.DataFrame(rows)


def _shortage_sentence(st: dict) -> str:
    """What a supply shortage (D24: live lead time above the config threshold) would do to the Nordic point (F30)."""
    if st.get("shortage_point") is None:
        return ""
    if st.get("state_nordic") == "shortage":
        return f"Nordic's supply is short (D24): its own shortage effect ({st['shortage_effect']:+.2f} pts) is already in the point. "
    return (f"If Nordic's supply turns short (live lead time above {st['shortage_weeks']:.0f} weeks, D24), its own shortage effect "
            f"({st['shortage_effect']:+.2f} pts, n {st['n_shortage']}) takes it to <b>{st['shortage_point']:.1f}</b>. ")


def regime_html(fn: dict, gb: pd.DataFrame) -> str:
    st = state_sensitivity(fn)
    if st is not None:
        lo = fn["guide"][0]
        below = " <span style='color:#c0392b'>below the guide</span>" if st["building_point"] < lo else ""
        effect = (f"Nordic's own building effect ({st['building_effect']:+.2f} pts; peers {st['gamma']:+.2f}, t {st['gamma_t']:.1f}, {st['gamma_n']} firm-quarters)"
                  if st.get("own_effect") else
                  f"the peers' building effect ({st['gamma']:+.2f} pts, t {st['gamma_t']:.1f}, {st['gamma_n']} firm-quarters; "
                  f"{st['gamma_alt']:+.2f} with the state lagged {st['alt_lag']})")
        if st["state"] == "building":
            body = (f"the channel is building ({st['latest_quarter']}): {effect} is already in the point <b>{st['base_point']:.1f}</b>. ")
        else:
            body = (f"the channel is '{st['state']}' ({st['latest_quarter']}), so the state adds {st['applied']:+.2f} pts. If distributors turn to building, "
                    f"{effect} takes Nordic from <b>{st['base_point']:.1f}</b> to <b>{st['building_point']:.1f}</b>{below}; building followed "
                    f"'{st['state']}' in {st['p_building_next']:.0%} of past quarters. ")
        return (f"<p class=src><b>Channel-state sensitivity</b> (Nordic's own record by the data-dated channel state, F20/F30; state from "
                f"distributor days, step 3b; supply shortage D24): {body}{_shortage_sentence(st)}"
                "Monitoring plan: W10 (state), W11 (Arrow / Avnet days), W4 (lead time, D24), W2 (Nordic's words, F31).</p>")
    s = regime_sensitivity(fn, gb)
    lo, hi = fn["guide"]
    cells = " · ".join(f"{r.regime} ({r.beat_pct:+.1f}%, n {r.n}): <b>{r.point:.0f}</b>" + (" <span style='color:#c0392b'>below the guide</span>" if r.point < lo else "")
                       for r in s.itertuples())
    return (f"<p class=src><b>Nordic depends on the regime call</b> (config forecast.nordic_2026Q3.regime = normal; guide {lo}–{hi}). "
            f"Point with the same adjustments under each regime's historical beat: {cells}. W2 (Nordic's words), W10 (state) and W11 (Arrow / Avnet days) of the monitoring plan test the call.</p>")


def next_quarter_rows(path=None) -> list[dict]:
    f = path or OUTPUTS / "forecast_next_quarter.csv"
    if not f.exists():
        return []
    return pd.read_csv(f).to_dict("records")


def next_quarter_section() -> str:
    """Nordic Q4 (h = 2) models behind the Q4 rows of the risk scenarios. Not one of the brief's three prints, so it sits
    under the scenarios, not in the forecast table (analyst decision 2026-09-26, F10)."""
    rows = next_quarter_rows()
    if not rows:
        return ""
    body = []
    for r in rows:
        b, e = ("<b>", "</b>") if r["is_point"] else ("", "")
        yoy = "" if pd.isna(r["yoy_pct"]) else f"{r['yoy_pct']:+.1f}%"
        basis = BASIS_LABEL["graph"] if str(r["model"]).startswith("GR") else "statistical ≈80%: ±1.28 × h=2 RMSE"
        body.append(f"<tr><td>{html.escape(r['model'])}</td><td>{html.escape(r['role'])}</td><td>{b}{r['point']:.1f}{e}</td>"
                    f"<td>{r['low']:.1f} – {r['high']:.1f}</td><td>{yoy}</td><td class=src>{basis}</td></tr>")
    return (f"<h3 style='font-size:14px;margin:14px 0 6px'>Behind the Q4 scenarios: Nordic {rows[0]['quarter']} graph models (h = {rows[0]['horizon']})</h3>"
            f"<p class=src>{html.escape(_q4_text())}</p>"
            "<table><tr><th>Model</th><th>Role</th><th>USDm</th><th>Range</th><th>YoY</th><th>What the range is</th></tr>"
            + "".join(body) + _cyc_row() + "</table>" + _cyc_note())


def _q4_text() -> str:
    q = cycle_view.q4()
    if q is None:
        return ""
    return ("Not one of the three forecast prints. Shown as evidence for the lag structure and the model's limits: the chain adds "
            "nothing to a guided quarter (weight 0) but is the best model one quarter past the guide. No company guide exists for this "
            f"quarter yet. The number is {q['model']} (F26): Logitech's sell-in through the Nordic -> ODM / distributor -> Logitech segment, "
            f"the unreported quarter filled by our bias-corrected sell-in forecast; walk-forward error {q['rmse']:.1f}m, {q['ratio']:.2f}x the "
            f"guide-based extrapolation (n {q['n']}), against GR's {q['gr_rmse']:.1f}m ({q['gr_ratio']:.2f}x). The gain over GR is a tie within "
            "noise and was found after looking (post-hoc, disclosed), and the fill fails F24's bar; it was chosen for the mechanism "
            "(Logitech's shipments set its production, which is what its ODMs buy Nordic chips for; the sell-through gap it avoids "
            "is unforecastable). Pre-registered "
            "(F22, q4_prereg_log.csv): GR (sell-through proxy, persistence fill) and the chain as reasoned (CH) are the challengers. "
            "The graph models still regress all Nordic consumer revenue on Logitech: a proxy for the common consumer cycle, not only "
            "the Logitech / GN slice; they fail when Logitech diverges from the rest of consumer electronics (e.g. the 2026 supplier incident).")


def _cyc_row() -> str:
    c = cycle_view.cyc()
    if c is None:
        return ""
    return (f"<tr><td>CYC</td><td>{html.escape('industry-cycle challenger, pre-registered, not in the forecast')}</td><td>{c['point']:.1f}</td>"
            f"<td>{c['low']:.1f} – {c['high']:.1f}</td><td></td><td class=src>{html.escape(cycle_view.record(c))}</td></tr>")


def _cyc_note() -> str:
    c = cycle_view.cyc()
    return "" if c is None else f"<p class=src>{html.escape(cycle_view.decomposition(c))} (step 5g, G29; cycle_challenger_prereg_log.csv)</p>"


def gn_enterprise_level(org_pct: float, cfg: dict) -> str:
    return "amber" if org_pct < cfg["dashboard_rules"]["gn_enterprise_org_amber_below"] else "green"


def nordic_dist_level(state: float, cfg: dict) -> str:
    return "amber" if abs(state) >= cfg["dashboard_rules"]["nordic_dist_state_amber_abs"] else "green"


def status_html(level: str) -> str:
    col = STATUS_COL[level]
    ring = "border:1.5px solid " + col + ";background:transparent" if level in ("judgment", "context") else "background:" + col
    return f'<span style="display:inline-block;width:11px;height:11px;border-radius:50%;{ring};margin-right:6px"></span>{level}'


def _margin_regime_detail(row: dict) -> str:
    """The numbers behind the current-regime margin band (forecast_details.json <company>.gm_model), with the rule's
    walk-forward RMSE on all quarters beside it, so the band is not read as the walk-forward error."""
    import json
    g = json.loads((OUTPUTS / "forecast_details.json").read_text())[row["print"].split()[0].lower()].get("gm_model", {})
    if not {"n_regime", "sd_pts", "scores"} <= set(g):
        return ""
    rule, rmse = min(g["scores"].items(), key=lambda kv: kv[1])
    return f": σ {g['sd_pts']:.2f} pts on n {g['n_regime']}; walk-forward RMSE on all quarters {rmse:.2f} ({rule})"


def basis_cell(row: dict, cfg: dict) -> str:
    b = range_basis(row, cfg)
    detail = _margin_regime_detail(row) if b == "margin_regime" else ""
    return f"<span class=src>{html.escape(BASIS_LABEL[b] + detail)}</span>"

