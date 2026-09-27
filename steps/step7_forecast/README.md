# Step 7 — Forecasts, report, dashboard

`src/forecast.py`: Nordic Q3 2026 revenue and GM, Logitech Q2 FY2027 revenue and GM, GN Audio (continuing operations) Q3 2026 revenue and EBITA margin — guide midpoint × (1 + expected guide error from `src/guide_error_model.py`, step 7e: F16, F20, F23) + chain terms (7c) + the supplier incident (F21) + FX (F27, `src/fx_update.py`); range = the model's predictive sd; the GN division view is a scenario. `src/report.py` writes the tier panel, the model report and the figures; `src/dashboard.py` the self-contained HTML dashboard. Final deliverables land in the repository's `outputs/` (`forecasts.csv`, `model_report.md`, `dashboard.html`, `tier_panel.csv`, `figures/`); the per-step evidence lands in each step's `outputs/`.

**Question.** How does the supply chain enter each forecast, and how much does it count?

`src/chain_forecast.py` (step 7c) writes each forecast as *guide-anchored + weight × (chain − anchor) + events pushed
through the graph*. The chain forecast is assembled from the brief's decisions — the step-5 lag kernel (Lag), the
step-3 slice multiplier and the tier identity sell-in = sell-through + Δchannel inventory (Mechanism), the step-2 share
path (Attribution), the regime (Structural breaks) — and the weight comes from the walk-forward back-test under rules
fixed in `config/model.yaml` → `chain_forecast` (Limitations). Outputs in `outputs/`: `chain_terms.csv` (every term,
its decision, value, evidence), `chain_weight_tests.csv`, `chain_scores.csv`, `chain_nordic_walkforward_h{1,2}.csv`,
`chain_logitech_walkforward.csv`, `chain_gn_readacross.csv`. Chain weights: Nordic Q3 0 (encompassing test), Logitech 0 (F29: guide method only; the inverse-MSE weight 0.23 is reported as a diagnostic). Decisions F1–F29 in `config/decisions.csv`.

Margins (`src/margin_model.py`, F18): Nordic GM is scored on the one-off-adjusted series (P116). A pre-registered channel-excess term (`src/margin_excess.py`, F25; spec in `config/model.yaml` guidance_anchor.margins.nordic_excess) is estimated on the 12 peers and walk-forward on Nordic; it enters the point only if its stated rule is met (outputs `margin_excess_effect.csv`, `margin_excess_walkforward.csv`).

Other modules: `src/forecast_next.py` (7b, Nordic Q4: the point model GRi, F26) and `src/prereg_q4.py` (F22, `outputs/q4_prereg_log.csv`);
`src/scenarios.py` (7d); `src/logitech_odm.py` (7f, the supply-side ODM nowcast, a pre-registered challenger, F28); `src/cross_checks.py` and
`src/cross_checks_view.py` (every check beside each forecast, `outputs/cross_checks*.csv`); `src/formulas.py` (the formula behind each number,
with this run's values); `src/cycle_view.py` (the Q4 lines and the CYC anomaly reading on the dashboard); `src/fiscal_calendar.py` (the Data
tab's fiscal calendars, P124); `src/brief_audit.py` (the brief checklist); `src/charts.py` (the Charts tab).
