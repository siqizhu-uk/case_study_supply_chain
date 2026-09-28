# Step 5e — Route-level propagation (CH by route)

## Reasoning (decision G26, written before any score)

Step 7c's CH ("chain as reasoned") feeds one demand series, Logitech's sell-out proxy (sell-in YoY + disclosed sell-through
gap), through one flow-weighted kernel. The analyst's structural version goes route by route: route demand x route weight
(Logitech 10-K: Amazon, Ingram, TD Synnex, the residual 'other retail / resellers') -> each route's own lag -> attribution
share x slice multiplier -> Nordic slice revenue change.

- **The total stays Logitech's own number.** The route proxies are all-vendor and all-category (Amazon incl. AWS and ads;
  distributors incl. memory, servers and 2026 ASP inflation; CDW is B2B IT) and carry the common cycle. So they only
  ALLOCATE Logitech's sell-through across routes: D_r = total + shrink x sd(total) x (z_r - sum_r w_r z_r), z = each proxy
  standardised with its own mean and sd over the quarters known at the origin (min_obs quarters, else the route takes the
  total). sum_r w_r D_r = total exactly. Distributor dollars from 2026Q1 are cut by the configured ASP tailwind first.
- **Each route has its own kernel** (the graph's paths through that Logitech customer, lag basis from config, 10-K weights
  as filed by the origin). GN stays on the aggregate path: it discloses no routes beyond its annual-report caps.
- **Prior (what to expect).** With the total pinned, the split can only change CH through differences between the route
  kernels: sum_r M_r sum_k (K_r,k - K_k) dev_r(t-k). The routes' lags differ by a few weeks and all sit on lags 1-2, so at
  h=1 the split only re-weights t-1 against t-2, and at h=2 (every lag below h reads t-2) it cannot change anything. Any
  gain would have to come from mix divergence (e.g. 2026: distributors vs Amazon vs Best Buy) timed differently by route.
  Expected: small. The shrink is fixed at 1 before scoring; 0 (= CH-aggregate), 0.5 and 'demean' are reported, not selected.

## Route proxies (data already in the repo)

| route        | proxy                  | first   | last   |   n_quarters | combine   | asp_adjusted   | what_it_measures                                                                     |
|:-------------|:-----------------------|:--------|:-------|-------------:|:----------|:---------------|:-------------------------------------------------------------------------------------|
| amazon       | amazon_revenue_yoy     | 2021Q1  | 2026Q2 |           22 | first     | False          | Amazon total revenue YoY (XBRL; all categories incl. AWS and ads): weak              |
| ingram       | ingm_ces_yoy           | 2024Q3  | 2026Q2 |            8 | first     | True           | Ingram client & endpoint YoY (2024Q3+), else total sales YoY                         |
| ingram       | ingm_sales_yoy         | 2023Q1  | 2026Q2 |           14 | first     | True           | Ingram client & endpoint YoY (2024Q3+), else total sales YoY                         |
| tdsynnex     | snx_endpoint_yoy       | 2022Q4  | 2026Q2 |           15 | first     | True           | TD Synnex Endpoint Solutions gross billings YoY (2022Q4-2023Q4 magnitudes estimated) |
| other_retail | bestbuy_computing_comp | 2020Q1  | 2026Q2 |           26 | mean      | False          | Best Buy Computing & Mobile comps, CDW revenue YoY, US electronics-store sales YoY   |
| other_retail | cdw_revenue_yoy        | 2021Q1  | 2026Q2 |           22 | mean      | False          | Best Buy Computing & Mobile comps, CDW revenue YoY, US electronics-store sales YoY   |
| other_retail | rseas_yoy              | 2020Q1  | 2026Q2 |           26 | mean      | False          | Best Buy Computing & Mobile comps, CDW revenue YoY, US electronics-store sales YoY   |

## Route kernels at the live origin

| route        |   kernel_mass |   mean_lag_weeks |   lag 0q |   lag 1q |   lag 2q |   lag 3q |   lag 4q |
|:-------------|--------------:|-----------------:|---------:|---------:|---------:|---------:|---------:|
| amazon       |         0.168 |           17.3   |        0 |    0.669 |    0.331 |        0 |        0 |
| gn           |         0.065 |           19.085 |        0 |    0.532 |    0.468 |        0 |        0 |
| ingram       |         0.131 |           20.4   |        0 |    0.431 |    0.569 |        0 |        0 |
| other_retail |         0.524 |           18.8   |        0 |    0.554 |    0.446 |        0 |        0 |
| tdsynnex     |         0.112 |           20.4   |        0 |    0.431 |    0.569 |        0 |        0 |

Checks: reconciliation max |sum_r w_r D_r - total| = 1.4e-14 pts; shrink 0 vs CH-aggregate max gap 2.8e-14 USD m; route kernels vs `kernel_asof` max gap 1.7e-16.

## Key results (computed)

1. **Structure.** Route mean lags 17.3-20.4 weeks; all route kernel weight sits on lag 1q, lag 2q. Largest walk-forward gap CH-route minus CH-aggregate: h=1 0.29m; h=2 0.00m.
2. **h=1.** RMSE CH-route 12.7m, CH-aggregate 12.7m, GB 7.4m (14 quarters); CH-route vs GB encompassing beta -0.25 (t -1.0). Route split: no measurable help: encompassing of the route increment over CH-aggregate beta -11.46 (t -0.3, bar 2.0), RMSE ratio 1.001.
3. **h=2.** RMSE CH-route 38.4m, CH-aggregate 38.4m, GB 44.1m (14 quarters); CH-route vs GB encompassing beta +2.76 (t +2.9). Route split: identical to CH-aggregate on every quarter (no route information can reach this horizon).
4. **Sensitivity, basis signal lags** (each basis against its own CH-aggregate): h=1 max gap 0.17m, route-increment t -0.7; h=2 max gap 0.21m, route-increment t +0.1.
5. **Where the routes diverged most** (h=1, top 5): the split was closer to the actual in 2 of 5 quarters, by at most 0.29m; drivers: other_retail 2x, tdsynnex 2x, amazon 1x.
6. **Live 2026Q3 (h=1).** Slice demand +9.33% by routes vs +9.33% aggregate -> Nordic slice +3.07m YoY; CH-route 224.5m vs CH-aggregate 224.5m (GB 234.7m). Largest re-allocation: tdsynnex +1.44 pts of slice demand, offset by the other routes.
7. **Live 2026Q4 (h=2).** Slice demand +10.93% by routes vs +10.93% aggregate -> Nordic slice +3.40m YoY; CH-route 213.1m vs CH-aggregate 213.1m (GB 222.0m). Largest re-allocation: tdsynnex +1.02 pts of slice demand, offset by the other routes.

## Live targets: route breakdown

| target       | route                            |   kernel_mass |   mean_lag_weeks |   contribution_pts |   vs_aggregate_pts |   nordic_slice_usdm |
|:-------------|:---------------------------------|--------------:|-----------------:|-------------------:|-------------------:|--------------------:|
| 2026Q3 (h=1) | amazon                           |          0.17 |            17.3  |               2.11 |               0.46 |                0.69 |
| 2026Q3 (h=1) | gn                               |          0.06 |            19.08 |               0.6  |               0    |                0.2  |
| 2026Q3 (h=1) | ingram                           |          0.13 |            20.4  |              -0.19 |              -1.36 |               -0.06 |
| 2026Q3 (h=1) | other_retail                     |          0.52 |            18.8  |               4.38 |              -0.53 |                1.44 |
| 2026Q3 (h=1) | tdsynnex                         |          0.11 |            20.4  |               2.44 |               1.44 |                0.8  |
| 2026Q3 (h=1) | TOTAL slice (routes | aggregate) |        nan    |           nan    |               9.33 |               0.01 |                3.07 |
| 2026Q4 (h=2) | amazon                           |          0.17 |            17.3  |               2.46 |               0.62 |                0.77 |
| 2026Q4 (h=2) | gn                               |          0.06 |            19.08 |               0.71 |               0    |                0.22 |
| 2026Q4 (h=2) | ingram                           |          0.13 |            20.4  |               0.7  |              -0.73 |                0.22 |
| 2026Q4 (h=2) | other_retail                     |          0.52 |            18.8  |               4.81 |              -0.91 |                1.5  |
| 2026Q4 (h=2) | tdsynnex                         |          0.11 |            20.4  |               2.25 |               1.02 |                0.7  |
| 2026Q4 (h=2) | TOTAL slice (routes | aggregate) |        nan    |           nan    |              10.93 |              -0    |                3.4  |

Route deviations in the live vintage (YoY pts of Logitech sell-through; origin 2026Q2):

| quarter   |   amazon |   ingram |   other_retail |   tdsynnex |
|:----------|---------:|---------:|---------------:|-----------:|
| 2025Q1    |    -16.1 |     17.6 |           -1.2 |        9.2 |
| 2025Q2    |     -8.7 |     10.9 |           -3.6 |       17.2 |
| 2025Q3    |     -7.1 |      9.1 |           -2.5 |       11.6 |
| 2025Q4    |     -5.4 |     -3   |           -1.2 |       17.4 |
| 2026Q1    |      0.8 |    -14.1 |           -0.1 |       15.6 |
| 2026Q2    |      3.7 |     -5.6 |           -1.7 |        9.1 |

## Walk-forward scores (same quarters, same guide, same origin as step 6 / 7c)

|   horizon | model                          |   n |   rmse_usdm |   mae_usdm |   bias_usdm |   rmse_ratio_vs_GB |   rmse_ratio_vs_CH_agg |   enc_beta_vs_GB |   enc_t_vs_GB |   enc_beta_vs_CH_agg |   enc_t_vs_CH_agg |   max_abs_gap_vs_CH_agg_usdm |
|----------:|:-------------------------------|----:|------------:|-----------:|------------:|-------------------:|-----------------------:|-----------------:|--------------:|---------------------:|------------------:|-----------------------------:|
|         1 | CH-route                       |  14 |      12.743 |     10.797 |      -1.631 |              1.716 |                  1.001 |           -0.247 |        -1.015 |              -11.456 |            -0.323 |                        0.285 |
|         1 | CH-aggregate                   |  14 |      12.732 |     10.767 |      -1.628 |              1.715 |                  1     |           -0.246 |        -1.012 |              nan     |           nan     |                        0     |
|         1 | GB (guide-anchored)            |  14 |       7.426 |      5.671 |      -0.878 |              1     |                  0.583 |          nan     |       nan     |                1.246 |             5.118 |                       15.583 |
|         1 | CH-route (shrink 0.5)          |  14 |      12.737 |     10.782 |      -1.629 |              1.715 |                  1     |           -0.247 |        -1.014 |              -22.911 |            -0.323 |                        0.143 |
|         1 | CH-route (demean (no scaling)) |  14 |      12.732 |     10.769 |      -1.628 |              1.715 |                  1     |           -0.247 |        -1.014 |               -1.336 |            -0.009 |                        0.054 |
|         1 | CH-route (basis signal)        |  14 |      12.467 |     10.779 |      -1.954 |              1.679 |                  1.002 |           -0.233 |        -0.924 |              -28     |            -0.685 |                        0.171 |
|         1 | CH-aggregate (basis signal)    |  14 |      12.448 |     10.771 |      -1.936 |              1.676 |                  1     |           -0.23  |        -0.91  |              nan     |           nan     |                        0     |
|         2 | CH-route                       |  14 |      38.385 |     32.357 |       1.397 |              0.871 |                  1     |            2.76  |         2.856 |              nan     |           nan     |                        0     |
|         2 | CH-aggregate                   |  14 |      38.385 |     32.357 |       1.397 |              0.871 |                  1     |            2.76  |         2.856 |              nan     |           nan     |                        0     |
|         2 | GB (guide-anchored)            |  14 |      44.086 |     34.996 |       2.698 |              1     |                  1.149 |          nan     |       nan     |               -1.76  |            -1.821 |                       24.625 |
|         2 | CH-route (shrink 0.5)          |  14 |      38.385 |     32.357 |       1.397 |              0.871 |                  1     |            2.76  |         2.856 |              nan     |           nan     |                        0     |
|         2 | CH-route (demean (no scaling)) |  14 |      38.385 |     32.357 |       1.397 |              0.871 |                  1     |            2.76  |         2.856 |              nan     |           nan     |                        0     |
|         2 | CH-route (basis signal)        |  14 |      38.362 |     32.365 |       1.345 |              0.87  |                  1     |            2.777 |         2.875 |               12.691 |             0.103 |                        0.211 |
|         2 | CH-aggregate (basis signal)    |  14 |      38.365 |     32.372 |       1.354 |              0.87  |                  1     |            2.782 |         2.878 |              nan     |           nan     |                        0     |

## Against GR (step 6), same quarters (`route_vs_gr.csv`)

|   horizon | model                             |   n | first   | last   |   rmse_usdm |   bias_usdm |   rmse_ratio_vs_GR |   beta |      t |
|----------:|:----------------------------------|----:|:--------|:-------|------------:|------------:|-------------------:|-------:|-------:|
|         1 | CH-route                          |  10 | 2024Q1  | 2026Q2 |       11.24 |       -6.76 |               0.53 | nan    | nan    |
|         1 | CH-aggregate                      |  10 | 2024Q1  | 2026Q2 |       11.23 |       -6.75 |               0.53 | nan    | nan    |
|         1 | GR (step 6)                       |  10 | 2024Q1  | 2026Q2 |       21.05 |        2.93 |               1    | nan    | nan    |
|         1 | GB (guide-anchored)               |  10 | 2024Q1  | 2026Q2 |        5.27 |       -3.88 |               0.25 | nan    | nan    |
|         1 | encompassing: CH-route adds to GR |  10 | nan     | nan    |      nan    |      nan    |             nan    |   1.41 |   8.01 |
|         1 | encompassing: GR adds to CH-route |  10 | nan     | nan    |      nan    |      nan    |             nan    |  -0.41 |  -2.32 |
|         2 | CH-route                          |   9 | 2024Q2  | 2026Q2 |       39.44 |      -15.14 |               1.41 | nan    | nan    |
|         2 | CH-aggregate                      |   9 | 2024Q2  | 2026Q2 |       39.44 |      -15.14 |               1.41 | nan    | nan    |
|         2 | GR (step 6)                       |   9 | 2024Q2  | 2026Q2 |       28.03 |       -6.85 |               1    | nan    | nan    |
|         2 | GB (guide-anchored)               |   9 | 2024Q2  | 2026Q2 |       47.21 |      -12.36 |               1.68 | nan    | nan    |
|         2 | encompassing: CH-route adds to GR |   9 | nan     | nan    |      nan    |      nan    |             nan    |  -0.36 |  -0.67 |
|         2 | encompassing: GR adds to CH-route |   9 | nan     | nan    |      nan    |      nan    |             nan    |   1.36 |   2.53 |

- h=1 (10 quarters 2024Q1–2026Q2): RMSE CH-route 11.2, GR 21.1, GB 5.3 USD m; lowest: GB (guide-anchored). CH-route adds to GR: beta +1.41 (t +8.0); GR adds to CH-route: beta -0.41 (t -2.3).
- h=2 (9 quarters 2024Q2–2026Q2): RMSE CH-route 39.4, GR 28.0, GB 47.2 USD m; lowest: GR (step 6). CH-route adds to GR: beta -0.36 (t -0.7); GR adds to CH-route: beta +1.36 (t +2.5).

## Quarters where the routes diverged most

|   horizon | quarter   |   gap_route_minus_agg_usdm |   err_route_usdm |   err_agg_usdm | route_split_helped   | driver_route   |   driver_pts |
|----------:|:----------|---------------------------:|-----------------:|---------------:|:---------------------|:---------------|-------------:|
|         1 | 2024Q3    |                      -0.29 |            -2.77 |          -2.49 | False                | other_retail   |        -2.41 |
|         1 | 2025Q2    |                      -0.15 |           -12.84 |         -12.69 | False                | amazon         |        -3.02 |
|         1 | 2024Q2    |                       0.14 |             2.89 |           2.76 | False                | tdsynnex       |         1.61 |
|         1 | 2026Q2    |                       0.1  |           -13.6  |         -13.7  | True                 | tdsynnex       |         2    |
|         1 | 2025Q4    |                       0.07 |            -5.16 |          -5.23 | True                 | other_retail   |        -2.54 |
|         2 | 2023Q1    |                       0    |            60.93 |          60.93 | False                | amazon         |         0.32 |
|         2 | 2023Q2    |                       0    |             7.57 |           7.57 | False                | amazon         |         1.66 |
|         2 | 2023Q3    |                       0    |            18.33 |          18.33 | False                | amazon         |         1.96 |
|         2 | 2023Q4    |                       0    |            42.91 |          42.91 | False                | amazon         |         1.25 |
|         2 | 2024Q1    |                       0    |            26.08 |          26.08 | False                | amazon         |         1.61 |

## What this cannot tell

- The proxies are all-vendor: a deviation says Amazon (or distributors) grew faster than retail overall, not that Logitech's units on that route did. Logitech discloses no sell-through by customer.
- The 10-K route weights are annual and gross-sales based; the residual 'other retail' (~56%) mixes direct retail, resellers and smaller distributors (G20).
- Not built: route-specific content or multipliers (no evidence Nordic content differs by route); route levels in place of Logitech's total (would import the all-vendor cycle).
