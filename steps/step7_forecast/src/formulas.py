"""The concrete formula behind each forecast, with this run's values substituted: one block per forecast (the rule in
symbols, the same rule with the numbers, where the range comes from), every value read from the run's outputs.

Not displayed (the Analysis tab shows each formula in prose); tests/test_step7_chain.py uses it to prove, every run,
that each published point and range follows from its components.
"""
from __future__ import annotations

import json

import pandas as pd

from core.config import OUTPUTS, ROOT, load_config

S7 = ROOT / "steps" / "step7_forecast" / "outputs"
Z = 1.2816


def _chain(term: str, printed: str) -> str:
    t = pd.read_csv(S7 / "chain_terms.csv")
    return str(t[(t["print"] == printed) & (t["term"].str.startswith(term))]["value"].iloc[0])


def blocks() -> list[dict]:
    d = json.loads((OUTPUTS / "forecast_details.json").read_text())
    gm = pd.read_csv(S7 / "guide_error_model.csv").set_index("company")
    ges = pd.read_csv(S7 / "guide_error_state_effect.csv").iloc[0]
    n, lg, gn = d["nordic"], d["logitech"], d["gn"]
    out = []

    # --- Nordic revenue: own record by the channel state (F20) + graph-propagated incident (F21)
    r = gm.loc["Nordic"]
    adj = n["signal_adjustments"]
    inc = adj.get("logitech_supplier_incident (graph)", 0.0)
    other = sum(v for k, v in adj.items() if k != "logitech_supplier_incident (graph)")
    share_in = float(load_config()["chain_forecast"]["supplier_incident"]["share_in_nordic_guide"])
    ch, wn = float(_chain("CH", "Nordic Q3 2026")), float(_chain("weight on the chain", "Nordic Q3 2026"))
    out.append({"print": "Nordic Q3 2026 revenue", "rule":
                "point = guide mid × (1 + e) + w × (chain − guide-anchored) + incident + other lines;  e = Nordic's mean guide miss in quarters whose previous "
                "quarter was neither a distributor build nor a supply shortage (own record, F20, F30) [+ its own build or shortage effect if t−1 was one];  "
                "chain CH = guide + s × [rev(t−4) × (1 + m × demand) − guide], w = encompassing β capped to [0, 1] if t ≥ 2, else 0 (7c);  "
                "incident = event-study gross × (1 − share already in the guide) (F21)",
                "numbers": f"{n['guide_mid']:g} × (1 + {n['hist_beat_pct']:.2f}%) {inc:+.2f} {other:+.2f} = {n['point']:.1f}.  "
                           f"e = {r['alpha']:+.2f}% (n {int(r['n_not_building'])}); state now '{r.get('pred_state_nordic', r['pred_state'])}', so the build effect "
                           f"{r['own_building_effect']:+.2f} pts (n {int(r['n_building'])}) is not applied;  CH = {ch:.1f}, w = {wn:g} (encompassing test: "
                           f"no information beyond the guide), so the chain adds 0;  incident = {inc / (1 - share_in):.1f} × (1 − {share_in:g}) = {inc:.2f}",
                "range": f"± {Z} × σ × guide mid, σ = √(s² + s²/n) = √({r['resid_sd']:.2f}² + {r['resid_sd']:.2f}²/{int(r['n_not_building'])}) = "
                         f"{r['pred_sd']:.2f}% → ± {Z * r['pred_sd'] / 100 * n['guide_mid']:.1f} → {n['low']:.1f}–{n['high']:.1f}"})

    # --- Nordic gross margin (F18, F25)
    g = n["gm_model"]
    ex = g.get("excess", {})
    out.append({"print": "Nordic Q3 2026 gross margin", "rule":
                "point = last reported quarter's GM, one-offs adjusted (the guide is only a floor, >50%; the simple rule with the lowest "
                "walk-forward error) + channel-excess term (F25: applied only if the peer estimate is negative with |t| ≥ 2)",
                "numbers": f"{n['gm_point']:.1f}% = last quarter {ex.get('applied_pts', 0.0):+.1f} (walk-forward RMSE: "
                           + ", ".join(f"{k} {v:.2f}" for k, v in g["scores"].items())
                           + f"; excess term {ex.get('why', 'n/a')})",
                "range": f"± {Z} × σ, σ = the rule's error on {g['n_regime']} normal-regime quarters = {g['sd_pts']:.2f} pts → "
                         f"{n['gm_range'][0]:.1f}–{n['gm_range'][1]:.1f}% (the underlying margin: a reported one-off lands outside it, P117)"})

    # --- Logitech revenue: habit pooled with the peers (F16) + chain term (7c)
    r = gm.loc["Logitech"]
    chain_tot, w = float(_chain("chain forecast", "Logitech Q2 FY27")), float(_chain("weight on the chain", "Logitech Q2 FY27"))
    ctr = lg["signal_adjustments"].get("supply_chain_term (step 7c)", 0.0)
    gb = chain_tot - ctr / w if w else float("nan")
    base = lg["guide_mid"] * (1 + lg["hist_beat_pct"] / 100)
    chain_rule = ("w = 0: guide method only at h1 (F29); the chain is shown, not used" if w == 0 else
                  "GB = guide mid × (1 + mean past beat);  w = (1/RMSE_chain²) / (1/RMSE_chain² + 1/RMSE_GB²) on the same guided quarters (7c)")
    chain_num = (f"point = {lg['guide_mid']:,g} × (1 + {lg['hist_beat_pct']:.2f}%) = {base:,.1f} (+ 0 × chain) = {lg['point']:,.1f}" if w == 0 else
                 f"GB = {gb:,.1f};  point = {lg['guide_mid']:,g} × (1 + {lg['hist_beat_pct']:.2f}%) + {w:.3f} × ({chain_tot:,.1f} − {gb:,.1f}) = "
                 f"{base:,.1f} + {ctr:.1f} = {lg['point']:,.1f}")
    st = float(_chain("tier identity", "Logitech Q2 FY27"))
    tau2, mu = float(ges["prior_tau2"]), float(ges["prior_mu"])
    out.append({"print": "Logitech Q2 FY27 net sales", "rule":
                "point = guide mid × (1 + e) + w × (chain − GB);  e = w_i × own mean miss + (1 − w_i) × μ (partial pooling with 12 "
                "peers, F16), w_i = τ² / (τ² + s²/n);  chain = sales(t−4) × (1 + sell-through YoY(t−1)) (tier identity, channel weeks "
                "held flat);  " + chain_rule,
                "numbers": f"w_i = {tau2:.3f} / ({tau2:.3f} + {r['resid_sd']:.2f}²/{int(r['n'])}) = {r['weight_own']:.3f};  e = {r['weight_own']:.3f} × "
                           f"{r['own_mean']:+.2f} + {1 - r['weight_own']:.3f} × {mu:+.2f} = {r['alpha']:+.2f}%;  chain = sales(2025Q3) × "
                           f"(1 + {st:.1f}%) = {chain_tot:,.1f};  " + chain_num,
                "range": f"± {Z} × σ × guide mid, σ = √(s² + var(e)) = {r['pred_sd']:.2f}% → ± {Z * r['pred_sd'] / 100 * lg['guide_mid']:.1f} → "
                         f"{lg['low']:,.1f}–{lg['high']:,.1f}"})

    # --- Logitech gross margin (F18)
    sd = (lg["gm_range"][1] - lg["gm_point"]) / Z
    out.append({"print": "Logitech Q2 FY27 gross margin (non-GAAP)", "rule": "point = the GM guide from the call + Logitech's mean past error on it",
                "numbers": f"{lg['gm_point']:.1f}% = {lg['gm_rule']}",
                "range": f"± {Z} × σ, σ = max(walk-forward error, spread of past errors) = {sd:.1f} pts → {lg['gm_range'][0]:.1f}–{lg['gm_range'][1]:.1f}%"})

    # --- GN revenue: full-year guide + own August-guide record (F17, F23)
    a = gn["guidance_anchor"]
    base = gn["base_q3_2025"]["total"]
    fx = gn["organic_assumptions"]["fx_pts"]
    out.append({"print": "GN Q3 2026 revenue (continuing ops)", "rule":
                "FY organic = FY guide mid + GN's mean miss on its August guide (own record, plain mean; F17, F23);  "
                "H2 organic = (FY × (H1b + H2b) − H1 × H1b) / H2b (H1 reported; b = 2025 revenue weights);  "
                "Q3 = Q3 2025 revenue × (1 + H2 organic) × (1 + FX)",
                "numbers": f"FY = {a['fy_guide_mid']:+.1f} {a['august_bias_pts']:+.2f} = {a['fy_expected_pct']:+.2f}%;  H1 = {a['h1_2026_organic_pct']:+.2f}% → "
                           f"H2 = {a['h2_organic_pct']:+.2f}%;  Q3 = {base:,.0f} × (1 {a['h2_organic_pct']:+.2f}%) × (1 {fx:+.1f}%) = {gn['point']:,.0f}",
                "range": f"± {Z} × σ_H2 × base × FX, σ_H2 = σ_FY × (H1b + H2b)/H2b = {a['h2_sd_pts']:.2f} pts → {gn['low']:,.0f}–{gn['high']:,.0f}"})

    # --- GN adjusted EBITA margin (F18, F23)
    m = gn["ebita_margin_model"]
    out.append({"print": "GN Q3 2026 adj. EBITA margin", "rule":
                "FY margin = FY guide mid + mean August error;  FY revenue = H1 2026 reported + H2 (2025 H2 × Q3 forecast / Q3 2025);  "
                "H2 EBITA = FY margin × FY revenue − H1 EBITA reported;  Q3 EBITA = 2025's Q3 share of H2 EBITA × H2 EBITA;  "
                "margin = Q3 EBITA / Q3 revenue",
                "numbers": f"{m['rule']};  H2 EBITA = {m['h2_ebita_dkkm']:,.0f};  Q3 EBITA = {m['q3_share_by_year'].get('2025', m['q3_share_by_year'].get(2025)):.1%} × "
                           f"{m['h2_ebita_dkkm']:,.0f} = {m['q3_ebita_dkkm']:,.0f};  margin = {m['q3_ebita_dkkm']:,.0f} / {gn['point']:,.0f} = {m['point']:.1f}%.  "
                           f"Cross-check, Q2 bridge (Q2 EBITA + drop-through + savings + tariff refund): {gn['ebita_bridge_margin_pct']:.1f}%",
                "range": f"± {Z} × √(σ_FY-error² + σ_Q3-share²) = √({m['sd_from_fy_error_pts']:.2f}² + {m['sd_from_share_pts']:.2f}²) = {m['sd_pts']:.2f} pts → "
                         f"{m['low']:.1f}–{m['high']:.1f}%"})
    return out
