# Step 5g — industry-cycle regression as a pre-registered Q4 challenger (G29)

GR's h=2 slope is ~3x the attribution slice (P77): it partly times the common consumer-electronics / semiconductor cycle. CYC asks whether an industry-cycle series times that cycle better when Nordic is regressed on it directly. It is a challenger only: the Q4 forecast stays GR (F22 / F24).

## Reading (computed)

- On the 9 common quarters (2024Q2-2026Q2) CYC's RMSE is 38.8m against GR 28.0, CH 39.4 and GB 47.2 (bias -30.7m); it is closer than GR in 2 of 9 quarters. The bar is not met.
- CYC adds to GR: beta +2.94 (t +2.3); GR adds to CYC: beta -1.94 (t -1.5); DM-HLN t +1.6. The in-sample encompassing fit has its own intercept (it removes CYC's bias) and rests on few quarters (drop-one t down to +1.5); the average (GR + CYC) / 2 scores 31.5m, worse than GR.
- The WSTS variant scores 25.9m (0.92x GR, DM t -1.0) but its live input (+129% for 2026Q2) is 3.4x the largest value it was scored on (+38%), so its Q4 line is 379m: the AI / memory composition break, not information about Nordic.
- Q4 2026: GR 222.4m, CH 212.2, CYC 208.3 (159-258), GB 221.1. Beyond the Logitech / GN slice GR sees +10.2m of cycle, CYC -3.9m: US electronics-store sales (+7.5% YoY) imply no extra cycle; with CYC's walk-forward bias of -30.7m its line more likely errs low.

## Specification (config `cycle_challenger`, fixed before any score; decision G29)

Nordic consumer YoY at t (GR's target) = a + b x cycle YoY at t-2, OLS on an expanding window through step 6's `forecast_row` at h=2: the same targets, training rows, supply-constrained rule and guide rows as GR. Nordic total = the guide-anchored benchmark (Q3 guide x last year's Q3->Q4 step) + the model's consumer tilt.

| model   | role       | regressors          | what                                                                                                                                                       |
|:--------|:-----------|:--------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| CYC     | primary    | rseas               | US electronics-store sales YoY at t-2 (consumer end demand, one slope)                                                                                     |
| CYCw    | robustness | wsts                | WSTS world semiconductor billings YoY at t-2 (the analyst's candidate; AI / memory composition break from 2024: live input far outside its training range) |
| CYCg    | robustness | rseas, graph_demand | RSEAS at t-2 + GR's graph demand (two slopes: the cycle beyond Logitech)                                                                                   |

Why RSEAS and one slope: consumer end demand is the common driver P77 points at; WSTS world billings carry the AI / memory composition break from 2024 (G28, P110); distributor dollars carry memory ASPs and the merger mask; Microchip distributor days are a channel state already in the 6c composite and the anchor (F20). With 8-18 training rows and one cycle, a second regressor buys noise (P58). Prior before scoring: weak (US-only, nominal, appliances included, +-5% outside COVID).

## What is known at the live origin

A cycle quarter is published when its third month is (month end + release lag: RSEAS = route_nowcast.release_lag.rseas; WSTS from config). The regressor is quarter t-2; t-1 is filled by persistence (F24), no partial quarters.

| series   | quarter   |   value_yoy | period_end   | release_date   | release_rule       | origin     | available_at_origin   | used   |
|:---------|:----------|------------:|:-------------|:---------------|:-------------------|:-----------|:----------------------|:-------|
| rseas    | 2026Q1    |        5.57 | 2026-03-31   | 2026-05-15     | month 3 end + 45 d | 2026-10-21 | True                  | False  |
| rseas    | 2026Q2    |        7.47 | 2026-06-30   | 2026-08-14     | month 3 end + 45 d | 2026-10-21 | True                  | True   |
| rseas    | 2026Q3    |      nan    | 2026-09-30   | 2026-11-14     | month 3 end + 45 d | 2026-10-21 | False                 | False  |
| wsts     | 2026Q1    |       83.01 | 2026-03-31   | 2026-05-15     | month 3 end + 45 d | 2026-10-21 | True                  | False  |
| wsts     | 2026Q2    |      129.4  | 2026-06-30   | 2026-08-14     | month 3 end + 45 d | 2026-10-21 | True                  | True   |
| wsts     | 2026Q3    |      nan    | 2026-09-30   | 2026-11-14     | month 3 end + 45 d | 2026-10-21 | False                 | False  |

## Walk-forward, h=2 (USD m; x = regressor as known at each origin, YoY %)

| quarter   |   actual_total |   GB_total |   GR_total |   CH_total |   CYC_total |   CYCw_total |   CYCg_total |   x_rseas |   x_wsts |
|:----------|---------------:|-----------:|-----------:|-----------:|------------:|-------------:|-------------:|----------:|---------:|
| 2023Q1    |          145.4 |      217.4 |      nan   |      206.3 |       nan   |        nan   |        nan   |      -1.5 |     -3   |
| 2023Q2    |          154.2 |      163.6 |      nan   |      161.8 |       nan   |        nan   |        nan   |      -5.1 |    -14.3 |
| 2023Q3    |          135   |      150   |      nan   |      153.3 |       nan   |        nan   |        nan   |       1.3 |    -21.2 |
| 2023Q4    |          108.2 |      146.1 |      nan   |      151.1 |       nan   |        nan   |        nan   |      -5.4 |    -15.8 |
| 2024Q1    |           74.5 |       89.2 |      nan   |      100.6 |       nan   |        nan   |        nan   |      -2.7 |     -4.5 |
| 2024Q2    |          127.9 |       77   |      124   |       94.1 |       111   |        121.7 |        105.6 |       2.6 |     11.6 |
| 2024Q3    |          158.8 |      106.1 |      130.8 |      114.8 |       107.8 |        133.9 |        103   |      -1   |     18.1 |
| 2024Q4    |          150.2 |      124   |      130.6 |      126.3 |       107.9 |        124.1 |        105.2 |       1.7 |     18.6 |
| 2025Q1    |          155.1 |       94.8 |       91.2 |       92.8 |        73.1 |         93.5 |         81.2 |      -1.1 |     23.7 |
| 2025Q2    |          164.1 |      261.1 |      198.6 |      236.5 |       166.4 |        185.2 |        189.8 |       1.5 |     18.2 |
| 2025Q3    |          179   |      196.6 |      196.6 |      187.1 |       165.1 |        194   |        191.2 |      -1.4 |     18.1 |
| 2025Q4    |          169.5 |      169.7 |      183.8 |      164.4 |       154.1 |        180.2 |        178.1 |      -1   |     20   |
| 2026Q1    |          192.4 |      175   |      188.8 |      169.9 |       168.7 |        191.8 |        187.1 |       3.3 |     26   |
| 2026Q2    |          218.6 |      200   |      209.6 |      193.5 |       184.8 |        230   |        207.8 |       3.4 |     38.4 |

## Scores on identical quarters (h=2)

Level (every model on the same quarters; COMBO = (GR + CYC) / 2, diagnostic only):

| model   |   n | first   | last   |   rmse |   bias |
|:--------|----:|:--------|:-------|-------:|-------:|
| CYC     |   9 | 2024Q2  | 2026Q2 |  38.79 | -30.74 |
| CYCw    |   9 | 2024Q2  | 2026Q2 |  25.93 |  -6.81 |
| CYCg    |   9 | 2024Q2  | 2026Q2 |  36.71 | -18.51 |
| GR      |   9 | 2024Q2  | 2026Q2 |  28.03 |  -6.85 |
| CH      |   9 | 2024Q2  | 2026Q2 |  39.44 | -15.14 |
| GB      |   9 | 2024Q2  | 2026Q2 |  47.21 | -12.36 |
| COMBO   |   9 | 2024Q2  | 2026Q2 |  31.51 | -18.8  |

Pairwise (model vs benchmark; encompassing = (actual - benchmark) on (model - benchmark): does the model add to it? top-3 = share of the squared-error gain from the best three quarters, n/a when there is no net gain):

| model   | vs   |   n | first   | last   |   rmse |   bias |   rmse_bench_same_quarters |   rmse_ratio |   dm_t |   dm_p |   enc_beta |   enc_t |   gain_share_top3 |
|:--------|:-----|----:|:--------|:-------|-------:|-------:|---------------------------:|-------------:|-------:|-------:|-----------:|--------:|------------------:|
| CYC     | GR   |   9 | 2024Q2  | 2026Q2 |  38.79 | -30.74 |                      28.03 |         1.38 |   1.64 |   0.14 |       2.94 |    2.3  |            nan    |
| CYC     | CH   |   9 | 2024Q2  | 2026Q2 |  38.79 | -30.74 |                      39.44 |         0.98 |  -0.1  |   0.92 |       1.28 |    3.29 |             13.08 |
| CYC     | GB   |   9 | 2024Q2  | 2026Q2 |  38.79 | -30.74 |                      47.21 |         0.82 |  -0.82 |   0.44 |       1.23 |    4.68 |              1.82 |
| CYCw    | GR   |   9 | 2024Q2  | 2026Q2 |  25.93 |  -6.81 |                      28.03 |         0.92 |  -1.02 |   0.34 |       1.24 |    1.15 |              1.18 |
| CYCw    | CH   |   9 | 2024Q2  | 2026Q2 |  25.93 |  -6.81 |                      39.44 |         0.66 |  -2.2  |   0.06 |       1.1  |    2.82 |              0.91 |
| CYCw    | GB   |   9 | 2024Q2  | 2026Q2 |  25.93 |  -6.81 |                      47.21 |         0.55 |  -1.85 |   0.1  |       1.18 |    4.2  |              0.98 |
| CYCg    | GR   |   9 | 2024Q2  | 2026Q2 |  36.71 | -18.51 |                      28.03 |         1.31 |   1.08 |   0.31 |      -1.05 |   -1.01 |            nan    |
| CYCg    | CH   |   9 | 2024Q2  | 2026Q2 |  36.71 | -18.51 |                      39.44 |         0.93 |  -0.36 |   0.73 |       0.9  |    1.51 |              3.07 |
| CYCg    | GB   |   9 | 2024Q2  | 2026Q2 |  36.71 | -18.51 |                      47.21 |         0.78 |  -1    |   0.35 |       1.25 |    2.85 |              1.4  |
| COMBO   | GR   |   9 | 2024Q2  | 2026Q2 |  31.51 | -18.8  |                      28.03 |         1.12 |   0.83 |   0.43 |       5.87 |    2.3  |            nan    |
| COMBO   | CH   |   9 | 2024Q2  | 2026Q2 |  31.51 | -18.8  |                      39.44 |         0.8  |  -1.49 |   0.17 |       1.34 |    2.95 |              1.25 |
| COMBO   | GB   |   9 | 2024Q2  | 2026Q2 |  31.51 | -18.8  |                      47.21 |         0.67 |  -1.55 |   0.16 |       1.3  |    4.36 |              1.15 |
| GR      | CYC  |   9 | 2024Q2  | 2026Q2 |  28.03 |  -6.85 |                      38.79 |         0.72 |  -1.64 |   0.14 |      -1.94 |   -1.52 |              0.91 |

**Adoption bar** (RMSE < GR AND (DM t <= -2.0 OR encompassing t >= 2.0) AND top-3 < 0.5): RMSE below GR False, test True, gain not concentrated False -> **not met**. Either way CYC is a pre-registered challenger for this print only.

Diagnostic added after the first scores (not part of the bar): leaving one quarter out, the encompassing t of CYC over GR ranges 1.5 (without 2025Q2) to 4.6.

Step 6's own sensitivity flip (supply-constrained quarters out of training, both models):

| model   | vs   |   n | first   | last   |   rmse |   bias |   rmse_bench_same_quarters |   rmse_ratio |   dm_t |   dm_p |   enc_beta |   enc_t |   gain_share_top3 |
|:--------|:-----|----:|:--------|:-------|-------:|-------:|---------------------------:|-------------:|-------:|-------:|-----------:|--------:|------------------:|
| CYC     |      |   7 | 2024Q4  | 2026Q2 |  36    | -23.71 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| CYCw    |      |   7 | 2024Q4  | 2026Q2 |  29.18 |  -2.66 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| CYCg    |      |   7 | 2024Q4  | 2026Q2 |  33.13 |  -6.01 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| GR      |      |   7 | 2024Q4  | 2026Q2 |  34.53 | -10.22 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| CH      |      |   7 | 2024Q4  | 2026Q2 |  39.5  |  -8.35 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| GB      |      |   7 | 2024Q4  | 2026Q2 |  45.81 |  -1.09 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| COMBO   |      |   7 | 2024Q4  | 2026Q2 |  34.04 | -16.96 |                     nan    |       nan    | nan    | nan    |     nan    |  nan    |            nan    |
| CYC     | GR   |   7 | 2024Q4  | 2026Q2 |  36    | -23.71 |                      34.53 |         1.04 | nan    | nan    |       1.61 |    1.75 |            nan    |
| CYCw    | GR   |   7 | 2024Q4  | 2026Q2 |  29.18 |  -2.66 |                      34.53 |         0.84 |  -0.99 |   0.36 |       1.79 |    1.39 |              1.06 |
| CYCg    | GR   |   7 | 2024Q4  | 2026Q2 |  33.13 |  -6.01 |                      34.53 |         0.96 |  -0.79 |   0.46 |       0.74 |    0.38 |              1.45 |
| COMBO   | GR   |   7 | 2024Q4  | 2026Q2 |  34.04 | -16.96 |                      34.53 |         0.99 |  -0.37 |   0.73 |       3.22 |    1.75 |              4.37 |

## Live: Nordic 2026Q4 (origin 2026-10-21, h=2)

Every line carries Logitech's supplier-incident term for Q4 (step 5d / F21). Band = config band_z x the model's walk-forward RMSE on all its own quarters (GR and CH as in steps/step7_forecast/outputs/q4_prereg_log.csv; GR's lag-scenario widening is in outputs/forecast_next_quarter.csv). minus_CH = the model minus the chain as reasoned (the Logitech / GN slice only): for GR it is the cycle beyond the slice as GR sees it; for CYC the same quantity as the industry series sees it.

| model   |   total_ex_event |   event_usdm |   point |   low |   high |   wf_rmse |   minus_CH |   minus_GB |
|:--------|-----------------:|-------------:|--------:|------:|-------:|----------:|-----------:|-----------:|
| GB      |            222   |         -0.9 |   221.1 | 164.6 |  277.6 |      44.1 |        8.9 |        0   |
| GR      |            223.3 |         -0.9 |   222.4 | 186.5 |  258.3 |      28   |       10.2 |        1.3 |
| CH      |            213.1 |         -0.9 |   212.2 | 163   |  261.4 |      38.4 |        0   |       -8.9 |
| CYC     |            209.2 |         -0.9 |   208.3 | 158.6 |  258   |      38.8 |       -3.9 |      -12.8 |
| CYCw    |            379.7 |         -0.9 |   378.8 | 345.6 |  412.1 |      25.9 |      166.6 |      157.7 |
| CYCg    |            226.7 |         -0.9 |   225.8 | 178.8 |  272.9 |      36.7 |       13.6 |        4.7 |

Pre-registered in `cycle_challenger_prereg_log.csv` (spec 3f98fa80be, data 4eecfc373d); check on 2027-02-05 (Nordic Q4 report). Nordic's Q3 report on 22 Oct adds one training row for later h=2 lines; the Q4 record is the last row logged before the print.
