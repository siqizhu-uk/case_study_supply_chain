# Analysis steps

One folder per step of the plan in the "data source" note. Each holds its README (what the step decides and on what
evidence), its `src/` (the code for that step only), its `config/` where the step has hand-typed evidence, and its
`outputs/` (every table the step logs). `scripts/run_all.py` runs them in order; a step can also be run alone where it has
a `scripts/run.py`. Inputs come from `pipelines/` (A company financials, B macro context and FX rates, C real-time channel, D peer panel).

| Step | Folder | Decides | Grade of the step |
|---|---|---|---|
| 1 | `step1_filing_confidence` | how far each company's quarterly figures can be trusted: Σ4Q vs audited FY, original vs restated segments, reported vs adjusted margins → confidence interval per metric class and a final grade per company | A (arithmetic on filings) |
| 2 | `step2_attribution` | share of Nordic revenue reached through Logitech / GN — five legs, conditional on the invoicing route, plus the share as a **time path** (`outputs/attribution_path.csv`) that steps 4/6/7 read | B (FCC census) |
| 3 | `step3_inventory_mechanism` | where inventory sits and who bears it: inventory factors per company (DIO, forward DIO, stage spreads, DSO, purchases), a channel-inventory index from the sell-through gap, bullwhip link by link (top-10 vs broad market), the ordering-rule regression, and the channel call for the three prints; every judgment call in `config/decisions.csv` | B / C |
| 4 | `step4_lag_structure` | the lag structure: reasoned weeks per tier before any regression (the prior, L1), then timing vs the downstream / industry cycle (correlation - not the chain lag, L2), turning points and amplitude; the lag edge by edge (Amazon / Ingram / TD Synnex -> Logitech / GN -> Nordic: graph prior, channel-reversion and attribution-constrained fits, posterior, route totals; L4-L9) | B |
| 5 | `step5_supply_graph` | the supply chain as a time-versioned graph (edges with share, lag and evidence grade; point-in-time 10-K weights; lag kernel and Monte Carlo), relationship and event breaks (5c), the 2026 supplier incident as an event study (5d), route propagation (5e), route nowcast (5f), the industry-cycle Q4 challenger (5g); the original write-up `mechanism_and_lags.md` is historical | B / D (graded per edge) |
| 6 | `step6_backtest` | walk-forward point-in-time back-test at h = 1 and h = 2 (lag models, GR, GRg, GRi), the channel composite (6c), the 12-peer panel and what the beat is (6d-6h), guidance bias | B |
| 7 | `step7_forecast` | the guide-error model (7e), the chain as terms (7c), the three point forecasts with ranges, Nordic Q4 (7b), risk scenarios (7d), the Logitech ODM challenger (7f), FX (F27), cross-checks and formulas, the model report, the dashboard → `outputs/` | — |
