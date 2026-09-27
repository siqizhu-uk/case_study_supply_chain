# Step 5 — Supply-chain structure (the graph)

**Question.** How does a change in end demand reach Nordic's revenue when the chain is a network, not a line? Logitech
sells to Amazon directly (18% of gross sales) and through Ingram Micro and TD Synnex (14% / 12%); Nordic ships to
Logitech's own Suzhou plant and to ODMs, directly and through its distributors; Amazon is also a Nordic customer.

- `config/supply_graph.csv` (repo root): one row per edge — share formula, reorder lag in weeks (low / mid / high), who
  holds the inventory, whether it is disclosed, evidence. `config/supply_graph_nodes.csv`: layers for the drawing.
- `config/supply_graph_weights.csv`: Logitech's customer shares per 10-K, with the sentence and filing date. The graph is
  point in time: `graph_asof(date)` only uses 10-Ks filed by that date.
- Named shares (Nordic distribution share, Suzhou's 35%, assumptions for GN's routes): `config/model.yaml` → `supply_graph`.
- `src/supply_graph.py`: paths, lag kernel, `propagate()` (end demand → Nordic response). `src/supply_graph_report.py`:
  outputs and the SVG. The walk-forward back-test uses it as models GR / GRg / GRi (step 6; GRi = the Nordic Q4 point, F26).
- Decisions G1–G30 in `config/decisions.csv`. `mechanism_and_lags.md` is the original written mechanism.

**Reliability.** Each edge's share and lag carry their own grade (A audited, B filing floor + estimate, C proxy / verbal, D assumption: not public or not collected). Lags are checked against each tier's inventory cover. Shares are mostly A/B, lags mostly C; the retail tier is D (Amazon's weeks-on-hand not collected, other retailers not public). Grades are data support, not levels: every range is at least as wide as its grade requires. Monte Carlo: mean lag 16.6–21.0 weeks (90%); the inputs that move it most are Logitech's in-house wait (D, collectable from XBRL), the ODM build lag (C) and the Logitech → other-retail lag (D, public proxy).

**Result.** Weighted mean lag ≈18 weeks of *physical dwell*, shorter than the single chain's 22
because most of Logitech's flow skips the IT distributors. As an *order signal* (dwell + the buyers' planning delay, G25) it
is ≈26 weeks (section below). The data cannot tell 1-, 2- and 3-quarter lags apart, and the
graph kernel forecasts no better than one lag; its value is structure, attribution by route and scenarios.

**Structural breaks through the chain (5d, decision G23).** A *shock* is a dated change in flow with every edge unchanged
(the graph propagates it); a *break* changes an edge's lag, share or amplitude, or a node's reporting basis (condition,
exclude, split by route or restate). `src/structural_breaks_chain.py` reads every entry of `config/model.yaml`
structural_breaks and regimes, the judgment per event from `config/structural_breaks_chain.csv`, and computes each one's
consequence for Nordic from data in the repo → `outputs/structural_breaks_chain.csv`. The worked example is Logitech's 2026
supplier incident (`src/event_study.py`, `event_study_report.py`, `event_study_svg.py`; assumptions `config/model.yaml` →
`event_study`): lost sales → customers → builds → Nordic shipments in weeks, chips already shipped kept as stock at the
holder and used first at restart, Q3 cuts as push-outs / cancellations of booked orders, the share already in Nordic's
guide netted → `outputs/event_study_supplier_incident.csv` / `.svg`.

## Shock direction rule (G24, P99)

- **Demand shock** (end demand changes, e.g. Amazon sell-out, a channel destock): propagates forward through the
  order-signal lag, Nordic(t) = sum_k kernel_k x D(t - k), k >= 0 (`supply_graph.propagate`; causality test
  `tests/test_step5.py::test_propagate_is_causal`).
- **Dated supply / event shock** (e.g. the 25 Jun 2026 supplier incident): propagates forward from the event date.
  Shipments before the date are sunk (truncation); what a backward lead shift would place before the date becomes stock at
  the holder, used first at restart (conservation). Implemented by the event study (`event_study.py`, G23).
- **Anticipated demand** (seasonal builds, a brand's own guide) moves Nordic *ahead* of sales by the physical lead; YoY
  growth removes seasonality, so the models keep the reaction direction.

## Physical dwell vs order-signal lag (G25, P86, P100, P101)

- The edge lags in `config/supply_graph.csv` are **physical dwell** (Little's-law capped by inventory cover). A demand change
  travels upstream as an **order signal**, which also waits for each buyer's planning decision. Per edge the buyer (the
  `dst` node places the order) adds: review period / 2 + mean age of its exponentially smoothed forecast, (1 − α)/α × R
  (textbook periodic review order-up-to). Planners (weekly replenishment, the brand's monthly S&OP, ODM / plant MRP, Nordic's
  distributors' monthly reorder) and their R / α: `config/model.yaml` → `supply_graph.info_delay` (grade D); which edge
  carries which: `info_delay_planner` / `info_delay_evidence` in the edge table. Physical columns unchanged.
- `src/info_delay.py` (formula, grade widening), `supply_graph.effective_ranges(..., basis="signal")` (cap on the physical
  part only), `src/signal_lag.py` + `signal_lag_report.py` (per edge / per route, paired Monte Carlo with one draw per
  planner, tornado with the planners, consistency check vs step 4's 22 wk and the data's near-optimal sets) →
  `outputs/graph_signal_lag_*.csv`, `graph_info_delay_planners.csv`, `graph_signal_tornado.csv`, report section.
- Which basis where: `supply_graph.lag_answer_basis: signal` (the lag question: this section, step 4's edge priors);
  `supply_graph.lag_basis: physical` (the kernel `propagate()` feeds to step 6 GR / GRg / GRi, the 6c graph factor, step 7c and the
  Q4 line). Switching the forecasting basis moves GRg and a pre-registered challenger (P101); the measured effect is in G25.
  The event study (5d) stays physical: a supply shock moves goods already in the pipe.

## Route proxies as a nowcast of Logitech's unreported quarter (5f, G27, P105-P109)

- At the h=2 origin (the day before Nordic reports t-1) Logitech has not reported t-1; GR fills it by persistence, the point model GRi with our bias-corrected sell-in forecast (F26). Step 5f
  tests whether proxies **released by that date** nowcast it better: TD Synnex (FQ Jun-Aug, 2 of 3 months), Best Buy (May-Jul,
  1 month), US electronics-store sales months 1-2. Amazon, Ingram and CDW report after Nordic and are excluded by the release
  rule (`config/model.yaml` → `route_nowcast.release_lag`: stored filing dates, else graded typical lags).
- `src/route_nowcast_data.py` (release dates, fiscal overlap, vintages), `route_nowcast.py` (N0 persistence, N1 guide as a
  comparison only, N2 = persistence + one slope on standardised proxy changes), `route_nowcast_nordic.py` (each nowcast through
  the kernel into step 6 GR and step 7c CH), `route_nowcast_scores.py` (adoption bar), `route_nowcast_report.py` →
  `outputs/route_nowcast*.csv`, `route_nowcast.md`, `route_nowcast_prereg_log.csv`.
- Adoption rule (analyst, 2026-09-27): persistence is the default; a proxy nowcast replaces it only if it beats persistence
  with |t| >= 2 and does not worsen Nordic GR; Logitech's guide is not a candidate. Result: no proxy nowcast beats
  persistence; the verdict is persistence.

## Industry-cycle regression as a pre-registered Q4 challenger (5g, G29, P111-P115)

- GR's h=2 slope is ~3x the attribution slice (P77). CYC regresses the same target (Nordic consumer YoY; total = guide-anchored
  benchmark + tilt) on US electronics-store sales YoY at t-2 directly, one slope, through step 6's `forecast_row` (same targets,
  training rows and guide). Robustness, pre-stated: WSTS billings instead (CYCw), RSEAS + GR's graph demand (CYCg). Spec, release
  rule and adoption bar: `config/model.yaml` → `cycle_challenger`, written before any score.
- `src/cycle_challenger.py` (point-in-time regressor, walk-forward, live), `cycle_challenger_scores.py` (same quarters as GR / CH / GB,
  DM, encompassing both ways, concentration, bar), `cycle_challenger_md.py`, `cycle_challenger_report.py` →
  `outputs/cycle_challenger.csv`, `cycle_challenger_scores.csv`, `cycle_challenger.md`, `cycle_challenger_prereg_log.csv`.
- Result: bar not met (RMSE 38.8m vs GR 28.0 on 9 quarters). Challenger only: the Q4 point is GRi (F26), GR a challenger. Addendum (G30, `outputs/cycle_decomposition.md`): beyond the slice GRi −3.3 and CYC −3.9 match in level, but against their own histories they read opposite ways (−16.5 vs +11.7), so CYC does not corroborate GRi.
