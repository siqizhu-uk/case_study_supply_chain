# Step 5f — route proxies as a nowcast of Logitech's unreported quarter

- No route-proxy nowcast beats persistence for Logitech's unreported quarter: RMSE ratio vs N0 N2c 1.13 (n 13, DM t +0.5), N2s 1.06 (n 8, DM t +0.7), N2e 1.01 (n 8, DM t +0.1).
- Logitech's guide (comparison only) misses by more than persistence: RMSE 4.04 vs 2.93 pts on its 5 quarters (bias -2.1).
- Nordic h=2 GR: persistence 28.0m (n 9); best alternative N2c 27.4m (DM t -2.5, 95% of the gain from 3 quarters, mean change 0.9m): a Nordic-level gain without a better nowcast is not evidence the proxies know Logitech's quarter (P109).
- Verdict under the rule fixed before scoring: N0 (persistence stays the default); no candidate met the nowcast bar.
- Logitech is ~0.8% of TD Synnex's revenue (10-K share x sales, last 4 quarters): the distributor's number is the all-vendor cycle, not Logitech.

## Reasoning (decision G27, written before any score)

**The gap.** Step 5e showed that routes only re-allocate a KNOWN Logitech total. At the h=2 origin of Nordic Q4 2026 (the day
before Nordic reports Q3, ~21 Oct) the total for Jul-Sep (Logitech Q2 FY27, reported ~27 Oct) is not known. Step 6 GR fills it
by persistence (the last reported quarter); GRg with Logitech's guide. Route data published before the origin could nowcast it.

**Point in time by release date.** A proxy value is used for quarter q only if first published by origin(q) = q end + 21 days
(Nordic Q3 2026: 22 Oct; Nordic's Q4 reports come in February, so 21 days is early - conservative). Release date = the filing
date stored in the repo (Best Buy), else period end + a documented typical lag (config `route_nowcast.release_lag`, graded;
the rule errs long, which can only drop data). Calendar-quarter reporters (Amazon, Ingram, CDW) publish ~30 days after quarter
end, after Nordic: excluded by the rule, not by hand.

**Fiscal vs calendar.** TD Synnex's FQ ends Feb/May/Aug/Nov; the quarter labelled q (e.g. Jun-Aug for Q3) shares 2 of 3 months
with q and is out ~4-6 weeks later, before the origin. Best Buy's quarter ends a month after the calendar quarter (P83): the one
filed by the origin (May-Jul for Q3) shares ONE month with q - it mostly describes the quarter Logitech already reported. US
electronics-store sales (Census, monthly): months 1-2 of q are out by the origin, month 3 is not (partial-quarter YoY).

**Model (few parameters, nests the default).** y(q) = y(q-1) + b x C(q), C = mean over the available proxies of their change since
q-1 (each as released by its own origin), scaled by its sd point in time; b = OLS through the origin, expanding window from
2021Q4 (2021's lockdown-base YoY excluded), b = 0 below 6 pairs. One slope, no level: an all-vendor proxy's level (TD Synnex +38%
in 2026 on memory prices) never becomes Logitech's level; only its change, standardised, moves the nowcast.

**Prior.** Modest at best. The proxies are all-vendor and all-category and carry the common PC / consumer-electronics cycle;
Logitech is a small share of each (computed below); two of three overlap the target by 1-2 months; TD Synnex's 2026 dollar
growth is memory ASPs, and its Endpoint split (the closest to Logitech) is not in the FQ3 FY26 release. Logitech's YoY is
persistent (a cycle moves over several quarters), so persistence is a hard benchmark for a one-quarter step.

## Adoption rule (the analyst, 2026-09-27; config `route_nowcast.adoption`, fixed before scoring)

- **Default = persistence (N0):** the last reported Logitech quarter fills the unreported one. A modelling assumption, stated.
- A route-proxy nowcast replaces it only with walk-forward evidence: nowcast RMSE below N0's on the same quarters AND
  (Diebold-Mariano t <= -2.0 OR encompassing t >= 2.0), AND Nordic h=2 GR fed with it no worse than GR on the same quarters.
  If the bar is not met the verdict is persistence, whatever the point estimates say.
- **Logitech's guide (N1) is not a candidate:** the analyst considers it known to be inaccurate. It is scored in one labelled
  comparison row (it is what step 6 GRg uses) and never pre-registered or recommended.

## Availability at the live origin (2026-10-21, target Logitech 2026Q3)

| source | period | months_in_target | release_date | release_basis | available_at_origin | value | grade | used_in |
|---|---|---|---|---|---|---|---|---|
| logitech | 2026Q3 | 3 | 2026-10-26 | rule: +26 d | False | n/a | B | target (known only after the origin) |
| amazon | 2026Q3 | 3 | 2026-10-29 | rule: +29 d | False | n/a | C | excluded by the availability rule |
| ingram | 2026Q3 | 3 | 2026-10-30 | rule: +30 d | False | n/a | B | excluded by the availability rule |
| cdw | 2026Q3 | 3 | 2026-10-30 | rule: +30 d | False | n/a | C | excluded by the availability rule |
| tdsynnex | 2026Q3 (FQ ending Aug 2026) | 2 | 2026-10-15 | rule: FQ end +45 d | True | 35.24 | C | N2 (snx_sales) |
| tdsynnex | 2026Q3 (FQ ending Aug 2026) | 2 | 2026-10-15 | rule: FQ end +45 d | True | n/a | C | released, but this split is not in the release (no value) |
| bestbuy | 2026Q2 (fiscal, ends 01 Aug 2026) | 1 | 2026-08-27 | 8-K filing date | True | 6.80 | A | N2c (1 month of the target) |
| bestbuy | 2026Q3 (fiscal, ends 31 Oct 2026) | 2 | 2026-11-26 | median stored filing lag 26 d | False | n/a | A | not yet filed |
| rseas | 2026-07 | 1 | 2026-09-14 | rule: month end +45 d | True | 8180.00 | B | N2c (partial-quarter YoY) |
| rseas | 2026-08 | 1 | 2026-10-15 | rule: month end +45 d | True | 8307.00 | B | N2c (partial-quarter YoY) |
| rseas | 2026-09 | 1 | 2026-11-14 | rule: month end +45 d | False | n/a | B | after the origin |
| logitech_guide | 2026Q3 | 3 | 2026-07-26 | rule: +26 d after q-1 | True | 5.38 | B | N1 / GRg (comparison only: user rule) |

## Nowcast of Logitech sell-through YoY (pts), walk-forward, vs persistence on the same quarters

| scope | model | role | n | first | last | rmse | rmse_bench_same_quarters | rmse_ratio | dm_t | enc_t | rmse_ratio_last6 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| own quarters | N1 | comparison only (user rule: not a candidate) | 5 | 2025Q2 | 2026Q2 | 4.04 | 2.93 | 1.38 | 1.19 | -0.28 | 1.38 |
| own quarters | N2c | candidate | 13 | 2023Q2 | 2026Q2 | 5.60 | 4.96 | 1.13 | 0.53 | -0.55 | 0.81 |
| own quarters | N2s | candidate | 8 | 2024Q3 | 2026Q2 | 4.49 | 4.22 | 1.06 | 0.74 | -0.65 | 1.06 |
| own quarters | N2e | sensitivity (cannot be adopted) | 8 | 2024Q3 | 2026Q2 | 4.25 | 4.22 | 1.01 | 0.07 | 0.23 | 1.02 |
| common quarters | N2c | candidate | 8 | 2024Q3 | 2026Q2 | 4.14 | 4.22 | 0.98 | -0.12 | 0.68 | 0.81 |
| common quarters | N2s | candidate | 8 | 2024Q3 | 2026Q2 | 4.49 | 4.22 | 1.06 | 0.74 | -0.65 | 1.06 |
| common quarters | N2e | sensitivity (cannot be adopted) | 8 | 2024Q3 | 2026Q2 | 4.25 | 4.22 | 1.01 | 0.07 | 0.23 | 1.02 |
| all quarters | N0 | default | 20 | 2021Q3 | 2026Q2 | 15.51 | n/a | n/a | n/a | n/a | n/a |

## Nordic h=2 (USD m): step 6 GR and step 7c CH with each nowcast for the unreported quarter, vs the persistence version

| forecast | model | role | n | rmse | rmse_bench_same_quarters | rmse_ratio | dm_t | dm_p | enc_t | gain_share_top3 | mean_abs_change_vs_N0_usdm | enc_vs_guide_t |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GR | N0 | default | 9 | 28.03 | n/a | n/a | n/a | n/a | n/a | n/a | 0.00 | 3.57 |
| GR | N1 | comparison only (user rule: not a candidate) | 9 | 28.44 | 28.03 | 1.01 | 1.32 | 0.22 | -0.53 | n/a | 1.05 | 3.45 |
| GR | N2c | candidate | 9 | 27.43 | 28.03 | 0.98 | -2.54 | 0.03 | 1.85 | 0.95 | 0.85 | 3.67 |
| GR | N2s | candidate | 9 | 28.47 | 28.03 | 1.02 | 1.11 | 0.30 | -3.66 | n/a | 0.45 | 3.45 |
| GR | N2e | sensitivity (cannot be adopted) | 9 | 27.71 | 28.03 | 0.99 | -1.06 | 0.32 | 1.09 | 1.13 | 0.64 | 3.65 |
| CH | N0 | default | 14 | 38.38 | n/a | n/a | n/a | n/a | n/a | n/a | 0.00 | 2.57 |
| CH | N1 | comparison only (user rule: not a candidate) | 14 | 38.40 | 38.38 | 1.00 | 1.54 | 0.15 | -0.33 | n/a | 0.09 | 2.56 |
| CH | N2c | candidate | 14 | 38.29 | 38.38 | 1.00 | -1.51 | 0.16 | 0.90 | 1.01 | 0.25 | 2.61 |
| CH | N2s | candidate | 14 | 38.41 | 38.38 | 1.00 | 0.83 | 0.42 | -1.68 | n/a | 0.04 | 2.55 |
| CH | N2e | sensitivity (cannot be adopted) | 14 | 38.36 | 38.38 | 1.00 | -0.95 | 0.36 | 0.89 | 1.06 | 0.05 | 2.57 |

## Adoption (bar above)

| model | nowcast_rmse_ratio | nowcast_dm_t | nowcast_enc_t | nowcast_bar_met | nordic_gr_rmse_ratio | nordic_bar_met | adopted | verdict |
|---|---|---|---|---|---|---|---|---|
| N2c | 1.13 | 0.53 | -0.55 | False | 0.98 | True | False | N0 |
| N2s | 1.06 | 0.74 | -0.65 | False | 1.02 | False | False | N0 |

## Live: Logitech 2026Q3 nowcast and Nordic 2026Q4 (h=2)

| model | label | logitech_st_yoy_nowcast | live_value | nordic_GR_usdm | nordic_CH_usdm |
|---|---|---|---|---|---|
| N0 | persistence (default) | 10.93 | yes | 223.28 | 213.09 |
| N1 | Logitech's guide (comparison only: user rule) | 5.38 | yes | 217.13 | 212.15 |
| N2c | composite of available proxies | 12.65 | yes | 223.86 | 213.38 |
| N2s | TD Synnex revenue alone | 11.83 | yes | 223.85 | 213.24 |
| N2e | TD Synnex Endpoint alone (no live value) | 10.93 | no (= persistence) | 223.67 | 213.09 |

N2c components for 2026Q3 (change since the previous quarter, pts): snx_sales +6.8, rseas -0.8, bestbuy_computing +2.6; composite +0.53 sd x slope 3.25 (n 19).

**Dated check (2026-10-27, Logitech reports 2026Q3):** fill `logitech_st_yoy_actual` (sales YoY + disclosed sell-through gap) in `route_nowcast_prereg_log.csv`; Nordic's actual for the h=2 target after its February report. The last row logged before the print is the record.

Replication checks (0 = identical to step 6's own design): graph_demand_N0_vs_step6_GR_max_abs 0, graph_demand_N1_vs_step6_GRg_max_abs 0. Spec hash 18567fc427, data hash 4c34ad9eb0.
