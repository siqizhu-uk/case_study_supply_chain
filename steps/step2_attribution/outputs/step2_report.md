# Step 2 — attribution: Logitech + GN as a share of Nordic

**Grade B** — inputs A (filings), estimate B (FCC census in force). Use: timing / direction signal for Nordic's consumer line, not a level input.

## Result by invoicing route (p10 / p50 / p90, % of Nordic total revenue)

| route | Logitech $m | Logitech + GN, % of Nordic total | % of Nordic Consumer |
|---|---|---|---|
| direct | 76 / 76 / 76 | 10.8 / 11.0 / 11.3 | 18 / 19 / 19 |
| indirect | 89 / 115 / 146 | 12.8 / 16.2 / 20.3 | 22 / 27 / 34 |
| mixed | 89 / 115 / 146 | 12.8 / 16.2 / 20.3 | 22 / 27 / 34 |

Share of Leg-A draws above the IFRS 8.34 ceiling: 99% — the bottom-up and the ceiling disagree at the median, which is why the route matters and why the output is conditional.
Socket share used: FCC census (peripheral grants) — low 0.62 / mid 0.77 / high 0.87. FCC census: 38 of 101 grants read, 33 legible (5 unreadable); peripherals 23/30 Nordic ({'Nordic': 23, 'Telink': 5, 'other (unidentified marking)': 2}); audio 0/3 Nordic ({'Airoha': 2, 'Realtek': 1}). Headset share used: {'low': 0.0, 'mid': 0.0, 'high': 0.3}. Logitech TTM sales: peripherals $3286m, headsets $178m. The prior is replaced once 10 peripheral grants are legible. Evidence photos: pipelines/C_realtime_channel/data/manual/fcc_photos/.

**Reading the census honestly.** It is a count of *designs* (one FCC grant = one product), not of units. The two non-Nordic peripherals are Telink parts in entry-level SKUs, which typically ship in larger unit volumes than the MX / G-series designs that carry Nordic — so the unit-weighted Nordic share is likely below the 85% design share (the Wilson low end, ~63%, is the safer working number). With the census share, Leg A exceeds the IFRS 8.34 ceiling in almost every draw: either Logitech's radios are invoiced to ODMs / distributors (consistent with two distributors taking 42% of Nordic's revenue), or the units / ASP priors are high. Both are stated; neither is assumed.

## Leg D — proprietary-2.4GHz floor

Nordic's Proprietary line peaked at $96m TTM (2022Q2), 14% of Nordic revenue then; it fell -66% to $33m by 2024Q1, first quarter below half its peak: 2022Q3. floor for PC-peripheral exposure before the BLE/Bolt migration folded it into Short-range; a lower bound, not Logitech alone.

## Leg E — natural experiment (2022-24 destock)

Nordic consumer 2022Q3 → 2024Q1: -41% ($203m). Logitech BLE-core categories 2022Q1 → 2023Q3: -14% ($399m). For Logitech alone to explain Nordic's drop, Nordic content would have to be 51% of Logitech's sell-in value; on the Leg-A priors Nordic content is ≈3.6% of Logitech's sell-in value, so Logitech alone explains ≈7% of Nordic's drop: the OEM tier is a timing/direction signal, the level is broad-market.

## Attribution path (time-varying; `outputs/attribution_path.csv`)

The share is not a constant: the back-test and the forecast read this path, not the headline number. Three drivers are observed per quarter — Nordic's own TTM revenue (denominator), Logitech's category mix (wireless weight), and the Nordic socket share of the design cohort in the market (FCC grants of the last three years). The IFRS 8.34 cap is applied with the year it is evidenced for.

| quarter | regime | Nordic TTM $m | Logitech periph TTM $m | socket cohort (k/n) | Logitech $m p50 | cap $m (status) | share of Nordic total, indirect p10/p50/p90 | direct p50 |
|---|---|---|---|---|---|---|---|---|
| 2022Q1 | supply_constrained | 650 | 3200 | 2023-2024 (extrapolated back) (12/18) | 87 | 65 (assumed) | 10.5 / 14.7 / 19.6 | 11.2 |
| 2022Q2 | supply_constrained | 703 | 3173 | 2023-2024 (extrapolated back) (12/18) | 87 | 70 (assumed) | 9.6 / 13.5 / 17.9 | 11.1 |
| 2022Q3 | destock | 757 | 3125 | 2023-2024 (extrapolated back) (12/18) | 85 | 76 (assumed) | 8.8 / 12.3 / 16.5 | 10.9 |
| 2022Q4 | destock | 777 | 2974 | 2023-2024 (extrapolated back) (12/18) | 81 | 78 (assumed) | 8.2 / 11.5 / 15.2 | 10.8 |
| 2023Q1 | destock | 739 | 2853 | 2021-2023 (widened to 2021-2024) (12/18) | 85 | 74 (assumed) | 10.0 / 12.8 / 16.4 | 11.2 |
| 2023Q2 | destock | 693 | 2766 | 2021-2023 (widened to 2021-2024) (12/18) | 82 | 69 (assumed) | 10.4 / 13.2 / 16.9 | 11.2 |
| 2023Q3 | destock | 626 | 2727 | 2021-2023 (widened to 2021-2024) (12/18) | 82 | 63 (assumed) | 11.3 / 14.5 / 18.5 | 11.4 |
| 2023Q4 | destock | 543 | 2740 | 2021-2023 (widened to 2021-2024) (12/18) | 82 | 54 (assumed) | 13.1 / 16.8 / 21.3 | 11.6 |
| 2024Q1 | destock | 472 | 2796 | 2022-2024 (12/18) | 84 | 47 (found) | 15.4 / 19.7 / 25.1 | 11.9 |
| 2024Q2 | normal | 446 | 2888 | 2022-2024 (12/18) | 86 | 45 (found) | 16.8 / 21.5 / 27.4 | 12.1 |
| 2024Q3 | normal | 469 | 2926 | 2022-2024 (12/18) | 88 | 47 (found) | 16.1 / 20.7 / 26.3 | 12.0 |
| 2024Q4 | normal | 511 | 3002 | 2022-2024 (12/18) | 90 | 51 (found) | 15.2 / 19.4 / 24.7 | 11.8 |
| 2025Q1 | normal | 592 | 3010 | 2023-2025 (22/29) | 103 | 59 (found) | 15.1 / 19.0 / 23.8 | 11.6 |
| 2025Q2 | normal | 628 | 3029 | 2023-2025 (22/29) | 104 | 63 (found) | 14.3 / 17.9 / 22.5 | 11.4 |
| 2025Q3 | normal | 648 | 3103 | 2023-2025 (22/29) | 106 | 65 (found) | 14.1 / 17.7 / 22.2 | 11.3 |
| 2025Q4 | normal | 668 | 3161 | 2023-2025 (22/29) | 108 | 67 (found) | 13.9 / 17.5 / 22.0 | 11.2 |
| 2026Q1 | normal | 705 | 3211 | 2024-2026 (21/26) | 117 | 70 (found) | 14.1 / 17.7 / 22.3 | 11.2 |
| 2026Q2 | normal | 760 | 3286 | 2024-2026 (21/26) | 119 | 76 (found) | 13.3 / 16.8 / 21.1 | 11.1 |

Reading: the indirect-route share peaks at 21% in 2024Q2 — the destock trough, when Nordic's broad-market revenue collapsed faster than Logitech's sell-in — and is 17% in 2026Q2. Pre-break (2022Q1–2022Q2) the median share was 14%, post-break 18%; Nordic's proprietary-2.4GHz line was 14% of revenue at the start of the path and 7% at its last disclosure. Socket cohorts before 2023 are extrapolated from the 2023-24 grants with the prior's low end as the floor (flagged in `socket_evidence`); the cap is evidenced from AR2025 for 2024-25 only and assumed earlier (`cap_status`).

## Constraints and evidence used

| constraint                        | company   | value                                               | source_key                                                                                                                                         | verified               | role                                                                                                                                                                                                                                                                                                                                    |
|:----------------------------------|:----------|:----------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------------------|:-----------------------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| top10_share_2025                  | nordic    | 57                                                  | AR2025                                                                                                                                             | found                  | context: concentration is high but spread; Logitech is never named                                                                                                                                                                                                                                                                      |
| ifrs834_major_customers_2025      | nordic    | distributors 30% and 12%                            | AR2025                                                                                                                                             | found                  | Leg B: the only >=10% customers are two DISTRIBUTORS (and three in 2024: 35%, 13%, 10%). So no OEM is >=10% -> Logitech < 10% if invoiced direct; and ~42% of revenue flows through two distributors, so Logitech's ODMs / Suzhou plant may well buy from a distributor, in which case the cap sits on the distributor, not on Logitech |
| ifrs834_major_customers_2024      | nordic    | distributors 35%, 13%, 10%                          | AR2025                                                                                                                                             | found                  | Leg B (prior year): same structure                                                                                                                                                                                                                                                                                                      |
| named_large_customers             | nordic    | Amazon; Google; Microsoft                           | ncr_2025                                                                                                                                           | no document cached     | context: the named large customers are not Logitech or GN                                                                                                                                                                                                                                                                               |
| logitech_inhouse_production_share | logitech  | 35                                                  | 10KFY26                                                                                                                                            | found                  | route: the Suzhou plant builds ~35% of Logitech's output, so at most ~35% of its radios are bought by Logitech itself (direct or via distributor); the other ~65% are bought by ODMs/CMs. Sets the direct-share prior (low 0.15 / mid 0.35 / high 0.5)                                                                                  |
| route_direct_share                | logitech  | 0.15|0.35|0.5                                       |                                                                                                                                                    | prior                  | route: share of Logitech's Nordic volume invoiced by Nordic to Logitech directly — prior anchored on the 35% in-house share; even Suzhou may buy through a distributor                                                                                                                                                                  |
| nordic_pr_logitech_2005           | logitech  | V200 / V500 cordless mice on nRF24xx                | https://www.design-reuse.com/news/202509680--logitech-chooses-the-nrf2402-and-nrf2401a-chipsets-for-the-new-logitech-v200-cordless-notebook-mouse/ | found                  | relationship evidence: Nordic itself announced Logitech design wins (28 Jun 2005, nRF2402/nRF2401A); Nordic stopped naming customers later, so absence of recent releases is policy, not evidence of absence                                                                                                                            |
| jabra_evolve2_buds_radios         | gn        | Qualcomm QCC5141 (buds) / QCC5126 (Link 380 dongle) | https://www.qucox.com/jabra-evolve2-buds-teardown/                                                                                                 | found in saved excerpt | GN: in the one Jabra product with a public teardown the Bluetooth audio SoCs are Qualcomm, in the earbuds and in the USB dongle — no Nordic part; supports keeping GN's Nordic content small (Leg A GN priors)                                                                                                                          |
| gn_fcc_grantee                    | gn        | BCE (GN Audio USA)                                  | https://fccid.io/BCE                                                                                                                               | found in saved excerpt | route to close GN: the same FCC internal-photo census as Logitech (grantee JNZ), under grantee code BCE                                                                                                                                                                                                                                 |

## Upgrade path

1. FCC internal-photo census (Pipeline C `fcc_logitech_grants_2023_2026.csv`, fill `soc_marking_observed` / `chip_vendor`) — turns the socket share from prior into observation, grade D → B.
2. Bluetooth SIG product listings per Logitech product (qualified design shows the radio).
3. Nordic press releases / case studies naming Logitech designs — cite only if found.
4. Import records or expert calls would settle the route — paid, outside the brief.