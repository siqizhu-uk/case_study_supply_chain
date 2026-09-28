# Step 1 — filing confidence — 2026-09-28

Three separate tests, every row logged in `outputs/test1_sum4q_vs_fy.csv`, `test2_restatements.csv`, `test3_adjusted_vs_reported.csv`; the fold is `outputs/confidence.csv`. Grade of the step itself: **A** (arithmetic on filings; every number verified in the cited filing text).

## Final confidence level

|          | final grade of quarterly data   |
|:---------|:--------------------------------|
| nordic   | C                               |
| logitech | B                               |
| gn       | C                               |
| ingram   | B                               |
| tdsynnex | B                               |

Reading: A = quarterly totals are audited-equivalent and segments unchanged; B = totals audited-equivalent, segments carry restatement risk of the size shown, margins need the adjusted series; C = margin definitions move by more than 2 pts.

## Confidence by company and metric class

| company   | metric_class                     | interval       | basis                                                        | grade   | rule                                                                           | final_grade   |
|:----------|:---------------------------------|:---------------|:-------------------------------------------------------------|:--------|:-------------------------------------------------------------------------------|:--------------|
| nordic    | total revenue (quarterly)        | ±0.02%         | Σ4Q vs audited FY, 7 years, max |diff|                       | A       | Q4 absorbs audit true-ups, so quarterly totals are audited-equivalent          | C             |
| nordic    | segment: Consumer                | ±7%            | 4 restated quarters, max |change| (CSV uses restated values) | B       | use restated values where they exist; treat pre-restatement quarters as ±this  | C             |
| nordic    | segment: Industrial & Healthcare | ±15%           | 4 restated quarters, max |change| (CSV uses restated values) | B       | use restated values where they exist; treat pre-restatement quarters as ±this  | C             |
| nordic    | margins (reported vs adjusted)   | up to 7.8 pts  | 2 quarters compared, max |adjusted − reported|               | C       | model the adjusted series and show the reported one beside it; widen Q4 ranges | C             |
| logitech  | total revenue (quarterly)        | ±0.00%         | Σ4Q vs audited FY, 6 years, max |diff|                       | A       | Q4 absorbs audit true-ups, so quarterly totals are audited-equivalent          | B             |
| logitech  | segment: Gaming                  | ±8%            | 3 restated quarters, max |change| (CSV uses restated values) | B       | use restated values where they exist; treat pre-restatement quarters as ±this  | B             |
| logitech  | segment: Video Collaboration     | ±26%           | 3 restated quarters, max |change| (CSV uses restated values) | B       | use restated values where they exist; treat pre-restatement quarters as ±this  | B             |
| logitech  | margins (reported vs adjusted)   | up to 0.5 pts  | 21 quarters compared, max |adjusted − reported|              | B       | model the adjusted series and show the reported one beside it; widen Q4 ranges | B             |
| gn        | total revenue (quarterly)        | ±0.00%         | Σ4Q vs audited FY, 4 years, max |diff|                       | A       | Q4 absorbs audit true-ups, so quarterly totals are audited-equivalent          | C             |
| gn        | segment: Enterprise              | ±4%            | 2 restated quarters, max |change| (CSV uses restated values) | B       | use restated values where they exist; treat pre-restatement quarters as ±this  | C             |
| gn        | margins (reported vs adjusted)   | up to 19.3 pts | 3 quarters compared, max |adjusted − reported|               | C       | model the adjusted series and show the reported one beside it; widen Q4 ranges | C             |
| ingram    | total revenue (quarterly)        | ±0.00%         | Σ4Q vs audited FY, 4 years, max |diff|                       | A       | Q4 absorbs audit true-ups, so quarterly totals are audited-equivalent          | B             |
| ingram    | segments                         | ±0% observed   | no restatement found in the cached filings                   | B       | no taxonomy change in the window (Ingram / TD Synnex report one segment)       | B             |
| tdsynnex  | total revenue (quarterly)        | ±0.00%         | Σ4Q vs audited FY, 6 years, max |diff|                       | A       | Q4 absorbs audit true-ups, so quarterly totals are audited-equivalent          | B             |
| tdsynnex  | segments                         | ±0% observed   | no restatement found in the cached filings                   | B       | no taxonomy change in the window (Ingram / TD Synnex report one segment)       | B             |

## Test 1 — Σ4Q vs audited FY

| company   |   fiscal_year |   sum_4q |   audited_fy |   diff_pct | audited_basis                                        | verification                    | pass   |
|:----------|--------------:|---------:|-------------:|-----------:|:-----------------------------------------------------|:--------------------------------|:-------|
| nordic    |          2019 |    288.4 |        288.4 |      0     | typed from AR2019                                    | found in AR text                | True   |
| nordic    |          2020 |    405.2 |        405.2 |      0     | typed from AR2020                                    | found in AR text                | True   |
| nordic    |          2021 |    610.5 |        610.5 |      0     | typed from AR2022                                    | found in AR text                | True   |
| nordic    |          2022 |    776.8 |        776.7 |      0.013 | typed from AR2022                                    | found in AR text                | True   |
| nordic    |          2023 |    542.8 |        542.9 |     -0.018 | typed from AR2023                                    | found in AR text                | True   |
| nordic    |          2024 |    511.4 |        511.4 |      0     | typed from AR2024                                    | found in AR text                | True   |
| nordic    |          2025 |    667.7 |        667.6 |      0.015 | typed from AR2025                                    | found in AR text                | True   |
| logitech  |          2021 |   5252.3 |       5252.3 |      0     | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| logitech  |          2022 |   5481.2 |       5481.1 |      0.002 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| logitech  |          2023 |   4538.9 |       4538.8 |      0.002 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| logitech  |          2024 |   4298.5 |       4298.5 |      0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| logitech  |          2025 |   4554.9 |       4554.9 |      0     | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| logitech  |          2026 |   4840.8 |       4840.8 |      0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| gn        |          2021 |  15775   |        nan   |    nan     | searched AR2021 text for a figure within 0.3% of Σ4Q | AR not cached                   |        |
| gn        |          2022 |  18687   |      18687   |      0     | searched AR2022 text for a figure within 0.3% of Σ4Q | figure 18,687 present in AR2022 | True   |
| gn        |          2023 |  18120   |      18120   |      0     | searched AR2023 text for a figure within 0.3% of Σ4Q | figure 18,120 present in AR2023 | True   |
| gn        |          2024 |  17985   |      17985   |      0     | searched AR2024 text for a figure within 0.3% of Σ4Q | figure 17,985 present in AR2024 | True   |
| gn        |          2025 |  16782   |      16782   |      0     | searched AR2025 text for a figure within 0.3% of Σ4Q | figure 16,782 present in AR2025 | True   |
| ingram    |          2022 |  50825   |      50824.5 |      0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| ingram    |          2023 |  48040   |      48040.4 |     -0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| ingram    |          2024 |  47984   |      47983.7 |      0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| ingram    |          2025 |  52557   |      52556.3 |      0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| tdsynnex  |          2020 |  19977.1 |      19977.2 |     -0     | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| tdsynnex  |          2021 |  31614.2 |      31614.2 |      0     | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| tdsynnex  |          2022 |  62344   |      62343.8 |      0     | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| tdsynnex  |          2023 |  57555   |      57555.4 |     -0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| tdsynnex  |          2024 |  58453   |      58452.4 |      0.001 | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |
| tdsynnex  |          2025 |  62508   |      62508.1 |     -0     | 10-K XBRL annual fact (audited)                      | xbrl                            | True   |

## Test 2 — original vs restated segment values

| company   | quarter   | segment                 |   original_value |   restated_value |   change_pct | original_verified   | restated_verified   | csv_uses   | reason                                                                                                                |
|:----------|:----------|:------------------------|-----------------:|-----------------:|-------------:|:--------------------|:--------------------|:-----------|:----------------------------------------------------------------------------------------------------------------------|
| gn        | 2024Q1    | Enterprise              |           1751   |           1811   |          3.4 | no filing           | found               | restated   | 2025: BlueParrott moved from Gaming & Consumer into Enterprise; 2024 comparatives restated                            |
| gn        | 2024Q3    | Enterprise              |           1680   |           1740   |          3.6 | found               | found               | restated   | 2025: BlueParrott moved into Enterprise; 2024 comparatives restated                                                   |
| logitech  | 2022Q2    | Gaming                  |            282.8 |            297.9 |          5.3 | found               | found               | restated   | FY24 category recast: Streamlabs into Gaming; Webcams / Headsets split out of Video Collaboration                     |
| logitech  | 2022Q2    | Video Collaboration     |            246.2 |            181.6 |        -26.2 | found               | found               | restated   | FY24 category recast                                                                                                  |
| logitech  | 2022Q3    | Gaming                  |            297.7 |            322   |          8.2 | found               | found               | restated   | FY24 category recast                                                                                                  |
| logitech  | 2022Q3    | Video Collaboration     |            236.2 |            179.2 |        -24.1 | found               | found               | restated   | FY24 category recast                                                                                                  |
| logitech  | 2022Q4    | Gaming                  |            392   |            411.9 |          5.1 | found               | found               | restated   | FY24 category recast                                                                                                  |
| logitech  | 2022Q4    | Video Collaboration     |            226.4 |            173.5 |        -23.4 | found               | found               | restated   | FY24 category recast                                                                                                  |
| nordic    | 2024Q1    | Consumer                |             50.8 |             54.2 |          6.7 | found               | found               | restated   | 2025 taxonomy (Consumer / Industrial & Healthcare / Other) restated 2024 comparatives                                 |
| nordic    | 2024Q1    | Industrial & Healthcare |             20.3 |             17.3 |        -14.8 | n/a (approx)        | found               | restated   | 2025 taxonomy restated 2024 comparatives; original = Industrial + Healthcare lines summed (not printed as one figure) |
| nordic    | 2024Q2    | Consumer                |             83   |             87.5 |          5.4 | found               | found               | restated   | 2025 taxonomy restated 2024 comparatives                                                                              |
| nordic    | 2024Q2    | Industrial & Healthcare |             41.5 |             37   |        -10.8 | n/a (approx)        | found               | restated   | 2025 taxonomy restated 2024 comparatives; original = Industrial + Healthcare lines summed (not printed as one figure) |
| nordic    | 2024Q3    | Consumer                |            109   |            111.3 |          2.1 | n/a (approx)        | found               | restated   | 2025 taxonomy; original read as ~109 (approx)                                                                         |
| nordic    | 2024Q3    | Industrial & Healthcare |             47   |             44.3 |         -5.7 | n/a (approx)        | found               | restated   | 2025 taxonomy; original read as ~47 (approx)                                                                          |
| nordic    | 2024Q4    | Consumer                |             94.3 |             96.6 |          2.4 | found               | found               | restated   | 2025 taxonomy restated 2024 comparatives                                                                              |
| nordic    | 2024Q4    | Industrial & Healthcare |             50.5 |             48.2 |         -4.6 | n/a (approx)        | found               | restated   | 2025 taxonomy restated 2024 comparatives; original = Industrial + Healthcare lines summed (not printed as one figure) |

## Test 3 — reported vs adjusted margins

| company   | quarter   | metric                |   reported_value |   adjusted_value | unit   | source_key   | reason                                                                   |   gap_pts | verification                                  |
|:----------|:----------|:----------------------|-----------------:|-----------------:|:-------|:-------------|:-------------------------------------------------------------------------|----------:|:----------------------------------------------|
| nordic    | 2024Q2    | gross_margin          |             42   |             49.8 | pct    | 2024Q2       | USD 10m nRF9160 inventory write-down excluded from adjusted GM           |       7.8 | both found                                    |
| nordic    | 2025Q4    | gross_margin          |             54.9 |             52   | pct    | 2025Q4       | one-off positive item excluded from adjusted GM                          |      -2.9 | both found                                    |
| gn        | 2026Q1    | ebita_margin_cont_ops |            -19   |              0.3 | pct    | 2026Q1       | FalCom / restructuring and impairment items excluded from adjusted EBITA |      19.3 | both found                                    |
| gn        | 2023Q4    | audio_ebita_margin    |             10.8 |             13.2 | pct    | AR2023       | FY2023 GN Audio EBITA reported vs adjusted (full year)                   |       2.4 | both found                                    |
| gn        | 2022Q4    | audio_ebita_margin    |              5.3 |              9.6 | pct    | 2022Q4       | Q4 2022 GN Audio EBITA reported vs adjusted                              |       4.3 | no filing                                     |
| logitech  | 2021Q2    | gross_margin          |             43.4 |             43.8 | pct    | 2021Q2       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2021Q3    | gross_margin          |             41.5 |             42   | pct    | 2021Q3       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.5 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2021Q4    | gross_margin          |             40.3 |             40.6 | pct    | 2021Q4       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2022Q1    | gross_margin          |             40.2 |             40.5 | pct    | 2022Q1       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2022Q2    | gross_margin          |             39.6 |             40   | pct    | 2022Q2       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2022Q3    | gross_margin          |             38.2 |             38.6 | pct    | 2022Q3       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2022Q4    | gross_margin          |             37.6 |             37.9 | pct    | 2022Q4       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2023Q1    | gross_margin          |             35.8 |             36.3 | pct    | 2023Q1       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.5 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2023Q2    | gross_margin          |             38.5 |             39   | pct    | 2023Q2       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.5 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2023Q3    | gross_margin          |             41.5 |             42   | pct    | 2023Q3       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.5 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2023Q4    | gross_margin          |             42   |             42.3 | pct    | 2023Q4       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2024Q1    | gross_margin          |             43.2 |             43.6 | pct    | 2024Q1       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2024Q2    | gross_margin          |             42.8 |             43.3 | pct    | 2024Q2       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.5 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2024Q3    | gross_margin          |             43.6 |             44.1 | pct    | 2024Q3       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.5 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2024Q4    | gross_margin          |             42.9 |             43.2 | pct    | 2024Q4       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2025Q1    | gross_margin          |             43.1 |             43.5 | pct    | 2025Q1       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2025Q2    | gross_margin          |             41.7 |             42.1 | pct    | 2025Q2       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2025Q3    | gross_margin          |             43.4 |             43.8 | pct    | 2025Q3       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.4 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2025Q4    | gross_margin          |             43.2 |             43.5 | pct    | 2025Q4       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2026Q1    | gross_margin          |             44.5 |             44.8 | pct    | 2026Q1       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |
| logitech  | 2026Q2    | gross_margin          |             49.5 |             49.8 | pct    | 2026Q2       | GAAP vs non-GAAP GM (share-based comp, amortisation)                     |       0.3 | hand CSV (8-K exhibit verified in Pipeline A) |

## What it means for the model

- Totals and Q4 balance sheets: use as audited. Segments: use restated values (the CSVs do) and carry the interval above for quarters before a taxonomy change.
- Margins: model the adjusted series, show reported beside it; Nordic and GN Q4 reports are the annual-report first draft, so Q4 one-offs are larger — widen Q4 ranges. The three forecast quarters are Q3, so unaffected.
- Verbal channel metrics stay grade C (Pipeline A, `verbal_metrics.csv`).