# Step 6 — Back-test with structural breaks

**Question.** Would the lag model have improved the forecast, using only the information that existed on each forecast date, across the destock and normal regimes?

- `src/walkforward.py` + `src/backtest_report.py` — **walk-forward, point-in-time back-test** (the answer to the question). The forecast date for quarter t is the day before Nordic reports t. At that point Logitech and Nordic are known through t−1, and so is Nordic's guidance for t. All models are re-fit on an expanding window, with lags and ridge alpha fixed from the reasoned prior. Two horizons: h = 1 (the guided quarter) and h = 2 (the quarter after). Benchmarks: guidance and guidance + real-time beat. Tests: RMSE compared with the benchmark on the same quarters, Diebold–Mariano (HLN) and an encompassing regression. Every choice is in `config/decisions.csv` (B1–B46). Leakage tests are in `tests/test_step6.py`.
- Models at h = 2: GR (the graph's sell-through proxy, persistence fill), GRg (Logitech's guide for the unreported quarter, a sensitivity) and GRi (Logitech sell-in through the Nordic → ODM → Logitech segment, our bias-corrected fill: the Nordic Q4 point, F26; `outputs/gri_fill_check.csv`). `src/logitech_explore.py` (6i, B46) explores Logitech's own series.
- `src/composite.py` + `src/composite_report.py` — **composite channel factor (step 6c)**. It predicts Nordic's *guidance miss*, not revenue, because guidance already contains the order book. Four channel factors are fixed in `config/model.yaml` → `composite` before the run: Logitech sell-through acceleration, Nordic distributor state, change in Microchip distributor days, Nordic forward DIO. Each is a point-in-time z-score, and they are equal-weighted: beat = a + b·C, two parameters. Over-fitting tests:
  - placebo (1000 noise composites through the same pipeline);
  - leave-one-factor-out;
  - every distinct sign combination;
  - estimated-weight challengers (OLS, ridge);
  - slope stability;
  - out-of-sample R², Diebold–Mariano and the cumulative squared-error gain.

  Step 7 uses the composite only if the adoption gate in config passes. The live forecast (primary and ridge challenger) is appended once to `outputs/composite_prereg_log.csv`. Decisions are B12–B19.
- `src/peer_panel.py` + `src/peer_panel_report.py` — **peer panel (step 6d)**: the composite's mechanism tested on 12 peers (Pipeline D), plus Nordic-like peer shrinkage and a meta-regression of each slope on distribution share (step 6e, `peer_panel_meta_regression.csv`), and `src/cycle_test.py` — **cycle stability (step 6f)**: the same slope by cycle window (2008-10 / 2011-19 / 2020-26 / Nordic's window), quarter-level with autocorrelation-scaled se, concentration in the top three quarters (`cycle_stability.csv`, risk R6). The model is pooled and walk-forward, with standard errors clustered by quarter, and is estimated on the peers only; it is then applied to Nordic as an external test. Decisions B20–B25; risk R5.
- `src/backtest.py` — the full-sample ridge distributed-lag regression (in-sample fit and leave-one-out; this is **not** a back-test, see B1) and the regime-conditioned guidance-bias table.

Outputs: `outputs/step6_report.md` (answer, live Q3/Q4 2026 forecasts, metrics), `walkforward_h1.csv`, `walkforward_h2.csv`, `walkforward_metrics_h*.csv`, `walkforward_encompassing_h*.csv`, `walkforward_live.csv`, `walkforward.png`, `regression.json`, `regression_fit.png`, `guidance_bias.csv`, `nordic_guidance_beat.png`.
- `src/guidance_optimism.py` + `src/guidance_optimism_report.py` — **what the beat is (step 6g)**: guidance-setting factors (relative guidance optimism vs the other peers' median, guided growth, guide width, last beat) tested on the 12-peer panel and on Nordic; `src/key_insights.py` writes `outputs/key_insights.csv`, the computed key-insight box shown above the risk box.
- `src/revenue_h2.py` — **revenue beyond the guided quarter (step 6h)**: g2 = actual(t+1)/guide(t) - 1 on the peer panel, seasonal benchmark vs seasonal + channel factor, walk-forward (`revenue_h2_scores.csv`, key insight K4).
