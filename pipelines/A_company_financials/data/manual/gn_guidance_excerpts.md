# GN Store Nord - financial guidance history FY2021-FY2026: quote evidence

Every row of `data/raw/gn_guidance_history.csv` with the source URL, retrieval date (2026-09-26), the local text copy
(under `data/cache/verbal/`, gitignored) and the exact excerpt. `check` = the excerpt was found word for word in the
saved copy (whitespace collapsed, curly quotes/apostrophes straightened, case-insensitive; for PDFs a line-end
hyphen join is also tried). Company announcements are the gn.com Newsroom pages (GN's company announcements, also
distributed via Nasdaq Copenhagen / GlobeNewswire - those copies were not fetched: globenewswire.com timed out); PDFs are from the gn.com Financial Download Center, extracted three ways per page
(two-column halves, three-column thirds, full width) because GN's layouts interleave columns; table rows are quoted
as their cells in reading order.

Action convention: `raised` / `lowered` follow the MIDPOINT (or the open bound) of the range, not GN's wording; when
GN calls a change 'narrowed' but the midpoint moved, the row says so in `note`. `narrowed` = midpoint unchanged.
Qualitative ranges are converted: 'upper/lower half of A-B' -> that half; 'middle of A-B' -> low=high=midpoint;
'more than X' / '>X' / 'better than X' -> low=X, high blank; 'around X' / '~X' -> low=high=X.

## 2021-02-11 - https://www.gn.com/Newsroom/Announcement?id=2173690&lang=en&date=20210211&title=annual-report-2020-navigating-safely-through-rough-waters-gn-hearing-24-gn-audio-42-gn-store-nord-9-organic-revenue-growth-gn-store-nord-ebita-of-dkk-1-866-million-and-free-cash-fl

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/_hearing_24_gn_audio_42_gn_store_nord_9_organic_revenue_growth_gn_store_nord_ebita_of_dkk_1_866_million_and_free_cash_fl.htm.txt`

- FY2021 hearing organic_growth_pct (initial): check found
  > For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.
- FY2021 hearing ebita_margin_pct (initial): check found
- FY2021 audio organic_growth_pct (initial): check found
  > For full year 2021, GN Audio expects organic revenue growth to be more than 20% and an EBITA margin of more than 21%.
- FY2021 audio ebita_margin_pct (initial): check found
- FY2021 group other (initial): check found
  > GN Store Nord expects a growth in EPS of more than 50% for full year 2021.

## 2021-04-14 - https://www.gn.com/Newsroom/Announcement?id=2209636&lang=en&date=20210414&title=gn-store-nord-upgrades-financial-guidance-for-2021

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/w_gn_com_Newsroom_Announcement_id_2209636_lang_en_date_20210414_title_gn_store_nord_upgrades_financial_guidance_for_2021.htm.txt`

- FY2021 audio organic_growth_pct (raised): check found
  > GN Audio upgrades the financial guidance communicated on February 11, 2021 from an organic revenue growth of more than 20% to more than 25% and confirms an EBITA margin of more than 21%.
- FY2021 audio ebita_margin_pct (reiterated): check found
- FY2021 hearing organic_growth_pct (reiterated): check found
  > For full year 2021, GN Hearing confirms an expected organic revenue growth of more than 25% and an EBITA margin of more than 16%.
- FY2021 hearing ebita_margin_pct (reiterated): check found
- FY2021 group other (raised): check found
  > GN Store Nord upgrades the financial guidance communicated on February 11, 2021 on growth in EPS from more than 50% to more than 60%.

## 2021-05-06 - https://www.gn.com/-/media/Files/Financial-Download-Center/2021/Q1/GNSN---Interim-Report-Q1-2021.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2021_Q1_GNSN_Interim_Report_Q1_2021_pdf.pdf.txt`

- FY2021 hearing organic_growth_pct (reiterated): check found
  > For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.
- FY2021 hearing ebita_margin_pct (reiterated): check found
- FY2021 audio organic_growth_pct (reiterated): check found
  > For full year 2021, GN Audio expects organic revenue growth to be more than 25% and an EBITA margin of more than 21%.
- FY2021 audio ebita_margin_pct (reiterated): check found
- FY2021 group other (reiterated): check found
  > GN Store Nord expects a growth in EPS of more than 60% for full year 2021.

## 2021-08-19 - https://www.gn.com/-/media/Files/Financial-Download-Center/2021/Q2/GNSN---Interim-Report-Q2-2021.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2021_Q2_GNSN_Interim_Report_Q2_2021_pdf.pdf.txt`

- FY2021 hearing organic_growth_pct (reiterated): check found
  > For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.
- FY2021 hearing ebita_margin_pct (reiterated): check found
- FY2021 audio organic_growth_pct (reiterated): check found
  > For full year 2021, GN Audio expects organic revenue growth to be more than 25% and an EBITA margin of more than 21%.
- FY2021 audio ebita_margin_pct (reiterated): check found
- FY2021 group other (reiterated): check found
  > GN Store Nord expects a growth in EPS of more than 60% for full year 2021.

## 2021-10-05 - https://www.gn.com/Newsroom/Announcement?id=2308394&lang=en&date=20211005&title=gn-store-nord-revises-financial-guidance-for-2021

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/ww_gn_com_Newsroom_Announcement_id_2308394_lang_en_date_20211005_title_gn_store_nord_revises_financial_guidance_for_2021.htm.txt`

- FY2021 hearing organic_growth_pct (lowered): check found
  > The GN Hearing organic revenue growth guidance for 2021 is revised from more than 25% to around 16%
- FY2021 hearing ebita_margin_pct (lowered): check found
  > the GN Hearing EBITA margin guidance for 2021 is revised from more than 16% to more than 12%
- FY2021 group other (lowered): check found
  > GN Store Nord revises the financial guidance on growth in EPS from more than 60% to more than 50%
- FY2021 audio organic_growth_pct (reiterated): check found
  > The 2021 financial guidance for GN Audio is unchanged and confirmed.
- FY2021 audio ebita_margin_pct (reiterated): check found

## 2021-10-06 - https://www.gn.com/Newsroom/Announcement?id=2309255&lang=en&date=20211006&title=gn-store-nord-to-acquire-steelseries-a-global-pioneer-in-premium-software-enabled-gaming-gear

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/ang_en_date_20211006_title_gn_store_nord_to_acquire_steelseries_a_global_pioneer_in_premium_software_enabled_gaming_gear.htm.txt`

- FY2021 group other (basis_change): check found
  > Transaction-related costs including integration costs, insurance costs, fees, consultant costs, etc. are expected to be around DKK 150 million in 2021.

## 2021-10-29 - https://www.gn.com/Newsroom/Announcement?id=2323342&lang=en&date=20211029&title=interim-report-q3-2021-in-q3-2021-gn-store-nord-delivered-2-organic-revenue-growth-and-announced-the-acquisition-of-steelseries-revision-of-gn-audio-s-organic-revenue-growth-guidan

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/organic_revenue_growth_and_announced_the_acquisition_of_steelseries_revision_of_gn_audio_s_organic_revenue_growth_guidan.htm.txt`

- FY2021 audio organic_growth_pct (lowered): check found
  > GN Audio today revises its organic revenue growth guidance for 2021 from more than 25% to 22-25%
- FY2021 audio ebita_margin_pct (reiterated): check found
  > The EBITA margin guidance of more than 21% excluding transaction related costs is confirmed
- FY2021 group other (lowered): check found
  > GN Store Nord now expects a growth in EPS of more than 40% for 2021 excluding transaction related costs

## 2021-10-29 - https://www.gn.com/-/media/Files/Financial-Download-Center/2021/Q3/GNSN---Interim-Report-Q3-2021.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2021_Q3_GNSN_Interim_Report_Q3_2021_pdf.pdf.txt`

- FY2021 hearing organic_growth_pct (reiterated): check found
  > For full year 2021, GN Hearing expects an organic revenue growth of around 16% and an EBITA margin of more than 12%.
- FY2021 hearing ebita_margin_pct (reiterated): check found

## 2022-02-10 - https://www.gn.com/Newsroom/Announcement?id=2382398&lang=en&date=20220210&title=annual-report-2021-navigating-rough-waters-part-ii-gn-hearing-16-gn-audio-22-gn-store-nord-20-organic-revenue-growth

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/tle_annual_report_2021_navigating_rough_waters_part_ii_gn_hearing_16_gn_audio_22_gn_store_nord_20_organic_revenue_growth.htm.txt`

- FY2021 hearing organic_growth_pct (actual): check found
  > GN Hearing’s organic revenue growth in 2021 was 16%, with an EBITA margin of 12.1%.
- FY2021 hearing ebita_margin_pct (actual): check found
- FY2021 audio organic_growth_pct (actual): check found
  > 2021 organic revenue growth was 22%, with an EBITA-margin of 21.2% excluding transaction related costs of DKK 45 million.
- FY2021 audio ebita_margin_pct (actual): check found
- FY2021 group other (actual): check found
  > EBITA of DKK 2.7 billion and EPS was DKK 13.90 (excluding transaction related costs)
- FY2022 hearing_core organic_growth_pct (initial): check found
  > In 2022, GN Hearing expects to grow faster than the projected market growth of 4-6% volume growth and -1% to -2% ASP decline, with an organic revenue growth between 5-10%.
- FY2022 hearing_core ebita_margin_pct (initial): check found
  > For the core hearing aid business, the EBITA margin is expected to be ~14% for 2022 excluding non-recurring items.
- FY2022 audio organic_growth_pct (initial): check found
  > GN Audio’s organic revenue growth for 2022 is expected to be >5%, while the organic revenue growth for SteelSeries is expected to be >10%
- FY2022 steelseries organic_growth_pct (initial): check found
- FY2022 audio ebita_margin_pct (initial): check found
  > For GN Audio, the EBITA margin is expected to be ~20% for 2022 excluding non-recurring items.
- FY2022 group other (initial): check found
  > adjusted EPS (excluding non-recurring items and amortization and impairment of acquired intangible assets) is expected to grow >10% compared to adjusted EPS of DKK 15.29 in 2021.

## 2022-05-05 - https://www.gn.com/-/media/Files/Financial-Download-Center/2022/Q1/GN-Interim-Report-Q1-2022.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2022_Q1_GN_Interim_Report_Q1_2022_pdf.pdf.txt`

- FY2022 hearing_core organic_growth_pct (reiterated): check found
  > - Core business organic 5-10% ~14% ~ -150
- FY2022 hearing_core ebita_margin_pct (reiterated): check found
- FY2022 audio organic_growth_pct (reiterated): check found
  > - GN Audio organic >5%
- FY2022 steelseries organic_growth_pct (reiterated): check found
  > - SteelSeries >10%
- FY2022 audio ebita_margin_pct (reiterated): check found
  > GN Audio2) 3) ~20% ~ -400
- FY2022 group other (reiterated): check found
  > GN Store Nord >10%

## 2022-08-17 - https://www.gn.com/Newsroom/Announcement?id=2500341&lang=en&date=20220817&title=gn-interim-report-q2-2022

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_Newsroom_Announcement_id_2500341_lang_en_date_20220817_title_gn_interim_report_q2_2022.htm.txt`

- FY2022 hearing_core organic_growth_pct (lowered): check found
  > GN Hearing - Core business organic 5-8% ~14% ~ -150
- FY2022 hearing_core ebita_margin_pct (reiterated): check found
- FY2022 audio organic_growth_pct (lowered): check found
  > - GN Audio organic 6) 0-5% - SteelSeries 7) >-25%
- FY2022 steelseries organic_growth_pct (lowered): check found
- FY2022 audio ebita_margin_pct (lowered): check found
  > GN Audio 2) 8) 17-18% ~ -400
- FY2022 group other (lowered): check found
  > GN Store Nord now expects growth in adj. EPS between -10% to 0%

## 2022-11-02 - https://www.gn.com/Newsroom/Announcement?id=2547164&lang=en&date=20221102&title=gn-store-nord-s-audio-division-revises-financial-guidance-for-2022

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/m_Announcement_id_2547164_lang_en_date_20221102_title_gn_store_nord_s_audio_division_revises_financial_guidance_for_2022.htm.txt`

- FY2022 audio organic_growth_pct (lowered): check found
  > GN Audio organic revenue growth guidance is revised from “0-5%” to now “-7% to -5%”
- FY2022 audio ebita_margin_pct (lowered): check found
  > GN Audio’s adj. EBITA margin guidance is revised from “17-18%” to now “14-15%”
- FY2022 group other (lowered): check found
  > GN Store Nord revises the financial guidance on growth in adj. EPS from between -10% to 0% to now “around -30%”
- FY2022 hearing_core organic_growth_pct (reiterated): check found
  > All other guidance parameters are confirmed
- FY2022 hearing_core ebita_margin_pct (reiterated): check found
- FY2022 steelseries organic_growth_pct (reiterated): check found

## 2022-11-11 - https://www.gn.com/-/media/Files/Financial-Download-Center/2022/Q3/GN-Interim-Report-Q3-2022.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2022_Q3_GN_Interim_Report_Q3_2022_pdf.pdf.txt`

- FY2022 hearing_core organic_growth_pct (reiterated): check found
  > - Core business organic 5-8% ~14% ~ -150
- FY2022 hearing_core ebita_margin_pct (reiterated): check found
- FY2022 audio organic_growth_pct (reiterated): check found
  > - GN Audio organic -7% to -5%
- FY2022 steelseries organic_growth_pct (reiterated): check found
  > - SteelSeries better than -25%
- FY2022 audio ebita_margin_pct (reiterated): check found
  > GN Audio2) 6) 14-15% ~ -500

## 2022-11-11 - https://www.gn.com/Newsroom/Announcement?id=2553961&lang=en&date=20221111&title=gn-store-nord-in-q3-2022-delivered-24-revenue-growth-while-organic-growth-was-1-supported-by-solid-enterprise-performance-strong-initial-uptake-of-resound-omnia

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/venue_growth_while_organic_growth_was_1_supported_by_solid_enterprise_performance_strong_initial_uptake_of_resound_omnia.htm.txt`

- FY2022 group other (reiterated): check found
  > The financial guidance, which was revised on November 2, 2022, is confirmed.

## 2023-02-09 - https://www.gn.com/-/media/Files/Financial-Download-Center/2023/Q1/GN-Annual-Report-2022.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2023_Q1_GN_Annual_Report_2022_pdf.pdf.txt`

- FY2022 hearing_core organic_growth_pct (actual): check found
  > Organic growth 5% 5% 73% -7% -7% -19%
- FY2022 hearing_core ebita_margin_pct (actual): check found
  > delivering adj. EBITA of DKK 786 million corresponding to an adj. EBITA margin of 13.1%, which was in line with the financial guidance.
- FY2022 steelseries organic_growth_pct (actual): check found
  > SteelSeries delivered organic revenue growth of -19% while gaining
- FY2022 audio ebita_margin_pct (actual): check found
  > translating into an adj. EBITA margin of 14.1%, compared to 21.2% in 2021
- FY2022 group other (actual): check found
  > Adj. earnings per share (adj. EPS) was DKK 10.54 in 2022 compared to DKK 15.29 in 2021, translating into a growth of -31%

## 2023-02-09 - https://www.gn.com/Newsroom/Announcement?id=2604596&lang=en&date=20230209&title=q4-2022-strong-organic-revenue-growth-of-14-in-gn-hearing-and-3-in-gn-audio-primarily-driven-by-9-in-enterprise

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/09_title_q4_2022_strong_organic_revenue_growth_of_14_in_gn_hearing_and_3_in_gn_audio_primarily_driven_by_9_in_enterprise.htm.txt`

- FY2022 audio organic_growth_pct (actual): check found
  > GN Audio delivered -7% organic revenue growth in 2022, in line with the updated financial guidance.
- FY2023 hearing organic_growth_pct (initial): check found
  > an organic revenue growth between 2% to 8% driven by market share gains is expected for 2023.
- FY2023 hearing_core ebita_margin_pct (initial): check found
  > For the core hearing aid business, the EBITA margin is expected to be between 13% to 16% for 2023 excluding non-recurring items.
- FY2023 audio organic_growth_pct (initial): check found
  > GN Audio is expecting organic revenue growth between -10% to +5%.
- FY2023 audio ebita_margin_pct (initial): check found
  > The EBITA margin is expected to be 10% to 15% for 2023 excluding non-recurring items.
- FY2023 group organic_growth_pct (initial): check found
  > For full year 2023, GN Store Nord consequently expects organic revenue growth of -6% to +6% in 2023

## 2023-04-26 - https://www.gn.com/Newsroom/Announcement?id=2655572&lang=en&date=20230426&title=gn-store-nord-delivered-7-organic-revenue-growth-driven-by-strong-market-share-gains-full-year-guidance-upgraded

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/6_title_gn_store_nord_delivered_7_organic_revenue_growth_driven_by_strong_market_share_gains_full_year_guidance_upgraded.htm.txt`

- FY2023 group organic_growth_pct (raised): check found
  > The financial guidance on organic revenue growth is upgraded from “-6% to +6%” to “-5% to +7%”
- FY2023 hearing organic_growth_pct (raised): check found
  > GN Hearing is upgrading its organic revenue growth guidance from “2% to 8%” to “5% to 10%”.
- FY2023 hearing_core ebita_margin_pct (raised): check found
  > the adj. EBITA margin in the core business is upgraded from “13% to 16%” to “14% to 16%”
- FY2023 audio organic_growth_pct (reiterated): check found
  > GN Audio -10% to +5% 10% to 15% ~ -150
- FY2023 audio ebita_margin_pct (reiterated): check found

## 2023-08-16 - https://www.gn.com/Newsroom/Announcement?id=2726719&lang=en&date=20230816&title=update-of-financial-guidance-for-2023

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_Newsroom_Announcement_id_2726719_lang_en_date_20230816_title_update_of_financial_guidance_for_2023.htm.txt`

- FY2023 hearing organic_growth_pct (raised): check found
  > GN Hearing is upgrading its organic revenue growth guidance from “5% to 10%” to “9% to 13%”.
- FY2023 hearing_core ebita_margin_pct (reiterated): check found
  > The EBITA margin in the core business of “14% to 16%” is confirmed
- FY2023 audio organic_growth_pct (lowered): check found
  > GN Audio’s organic revenue guidance is narrowed from “-10% to +5%” to “-10% to -4%”.
- FY2023 audio ebita_margin_pct (lowered): check found
  > GN Audio’s adj. EBITA margin is narrowed from “10% to 15%” to “10% to 12%”.
- FY2023 group organic_growth_pct (lowered): check found
  > GN Store Nord’s organic revenue growth guidance is narrowed from “-5% to +7%” to “-4% to +2%”.

## 2023-11-10 - https://www.gn.com/Newsroom/Announcement?id=2778042&lang=en&date=20231110&title=one-gn-transformation-well-on-track-hearing-continued-strong-organic-growth-while-enterprise-executed-well-in-stabilizing-markets-and-steelseries-outperformed-the-market-sequential

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/_organic_growth_while_enterprise_executed_well_in_stabilizing_markets_and_steelseries_outperformed_the_market_sequential.htm.txt`

- FY2023 group organic_growth_pct (narrowed): check found
  > GN Store Nord’s organic revenue growth guidance is narrowed from “-4% to +2%” to “-2% to 0%”.
- FY2023 hearing organic_growth_pct (raised): check found
  > GN Hearing is narrowing its organic revenue growth guidance from “9% to 13%” to “11% to 13%”.
- FY2023 hearing_core ebita_margin_pct (reiterated): check found
  > The EBITA margin in the core business of “14% to 16%” is confirmed
- FY2023 audio organic_growth_pct (lowered): check found
  > GN Audio’s organic revenue guidance is narrowed from “-10% to -4%” to “-9% to -7%”.
- FY2023 audio ebita_margin_pct (reiterated): check found
  > GN Audio’s adj. EBITA margin is confirmed at “10% to 12%”

## 2024-02-08 - https://www.gn.com/Newsroom/Announcement?id=2825677&lang=en&date=20240208&title=annual-report-2023-strong-execution-across-the-company-led-to-13-organic-revenue-growth-in-gn-hearing-and-8-organic-revenue-growth-in-gn-audio-while-generating-dkk-1-1-billion-in-f

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/o_13_organic_revenue_growth_in_gn_hearing_and_8_organic_revenue_growth_in_gn_audio_while_generating_dkk_1_1_billion_in_f.htm.txt`

- FY2023 group organic_growth_pct (actual): check found
  > GN delivered DKK 18.1 billion revenue with organic revenue growth of -1%, as a result of 13% organic revenue growth in GN Hearing and -8% organic revenue growth in GN Audio
- FY2023 hearing organic_growth_pct (actual): check found
- FY2023 audio organic_growth_pct (actual): check found
- FY2024 group organic_growth_pct (initial): check found
  > Organic revenue growth EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 8% 12% to 14% >700
- FY2024 group ebita_margin_pct (initial): check found
- FY2024 hearing organic_growth_pct (initial): check found
  > the Hearing division assumes to contribute with organic revenue growth of 8% to 12%.
- FY2024 hearing_core ebita_margin_pct (initial): check found
  > the underlying assumptions include an EBITA margin in the core hearing aid business of 18% to 20%.
- FY2024 enterprise organic_growth_pct (initial): check found
  > the Enterprise division assumes to contribute with organic revenue growth of -3% to 5%.
- FY2024 gaming_consumer organic_growth_pct (initial): check found
  > the Gaming & Consumer division assumes to contribute with organic revenue growth of 2% to 10%.

## 2024-02-08 - https://www.gn.com/-/media/Files/Financial-Download-Center/2024/Q1/GN-Annual-Report-2023.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2024_Q1_GN_Annual_Report_2023_pdf.pdf.txt`

- FY2023 hearing_core ebita_margin_pct (actual): check found
  > delivering adj. EBITA of DKK 960 million, equal to an EBITA margin of 14.7% compared to 13.1% in 2022, in line with the financial guidance.
- FY2023 audio ebita_margin_pct (actual): check found
  > GN Audio’s adj. EBITA ended at DKK 1,197 million, translating into an adj. EBITA margin of 10.6%, compared to 14.1% in 2022

## 2024-05-02 - https://www.gn.com/Newsroom/Announcement?id=2873806&lang=en&date=20240502&title=interim-report-q1-2024-gn-store-nord-delivered-organic-revenue-growth-of-5-reaching-an-ebita-margin-of-12-5

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/240502_title_interim_report_q1_2024_gn_store_nord_delivered_organic_revenue_growth_of_5_reaching_an_ebita_margin_of_12_5.htm.txt`

- FY2024 group organic_growth_pct (reiterated): check found
  > The full year guidance is confirmed Financial guidance for 2024 Organic revenue growth EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 8% 12% to 14% >700
- FY2024 group ebita_margin_pct (reiterated): check found

## 2024-05-02 - https://www.gn.com/-/media/Files/Financial-Download-Center/2024/Q2/Interim-Report-Q1-2024.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2024_Q2_Interim_Report_Q1_2024_pdf.pdf.txt`

- FY2024 hearing organic_growth_pct (reiterated): check found
  > Hearing division assumes to contribute with organic revenue growth of 8% to 12%
- FY2024 hearing_core ebita_margin_pct (reiterated): check found
  > core hearing aid business of 18% to 20%
- FY2024 enterprise organic_growth_pct (reiterated): check found
  > contribute with organic revenue growth of -3% to 5%.
- FY2024 gaming_consumer organic_growth_pct (reiterated): check found
  > contribute with organic revenue growth of 2% to 10%.

## 2024-06-11 - https://www.gn.com/Newsroom/Announcement?id=2896501&lang=en&date=20240611&title=gn-to-gradually-wind-down-its-elite-and-talk-product-lines-strong-performance-in-the-hearing-division-to-partly-off-set-the-extraordinary-impact-from-the-gradual-wind-down

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/t_lines_strong_performance_in_the_hearing_division_to_partly_off_set_the_extraordinary_impact_from_the_gradual_wind_down.htm.txt`

- FY2024 group organic_growth_pct (lowered): check found
  > the group organic revenue growth guidance is narrowed from “2% to 8%” to now “2% to 6%”.
- FY2024 group ebita_margin_pct (lowered): check found
  > GN is narrowing the EBITA margin guidance from “12% to 14%” to now “12% to 13%”.

## 2024-08-22 - https://www.gn.com/Newsroom/Announcement?id=2933940&lang=en&date=20240822&title=interim-report-q2-2024-strong-execution-leading-to-5-organic-growth-and-margin-expansion

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/940_lang_en_date_20240822_title_interim_report_q2_2024_strong_execution_leading_to_5_organic_growth_and_margin_expansion.htm.txt`

- FY2024 group organic_growth_pct (reiterated): check found
  > The full year guidance, which was adjusted on June 11, is confirmed
- FY2024 group ebita_margin_pct (reiterated): check found
  > Organic revenue growth Reported EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 6% 12% to 13% >900

## 2024-08-22 - https://www.gn.com/-/media/Files/Financial-Download-Center/2024/Q3/GN-Interim-Report-Q2-2024.pdf

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_media_Files_Financial_Download_Center_2024_Q3_GN_Interim_Report_Q2_2024_pdf.pdf.txt`

- FY2024 hearing organic_growth_pct (raised): check found
  > the Hearing division is trending towards the upper half of the overall organic growth assumption of 8% to 12%.
- FY2024 hearing_core ebita_margin_pct (reiterated): check found
  > GN is also well underway to deliver an EBITA margin of 18% to 20% in the core hearing aid business.
- FY2024 enterprise organic_growth_pct (lowered): check found
  > the Enterprise division is trending towards the lower half of the overall organic growth assumption of -3% to +5%.
- FY2024 gaming_consumer organic_growth_pct (lowered): check found
  > division is assumed to deliver organic revenue growth of -10% to -2%

## 2024-11-06 - https://www.gn.com/Newsroom/Announcement?id=2975901&lang=en&date=20241106&title=update-of-financial-guidance-for-2024

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/https_www_gn_com_Newsroom_Announcement_id_2975901_lang_en_date_20241106_title_update_of_financial_guidance_for_2024.htm.txt`

- FY2024 group organic_growth_pct (lowered): check found
  > Following a somewhat softer market development than earlier anticipated for Enterprise and Gaming, GN adjusts its organic revenue growth guidance to “1% to 2%”
- FY2024 group ebita_margin_pct (reiterated): check found
  > a confirmation of the EBITA margin guidance of “12 to 13%”

## 2024-11-06 - https://www.gn.com/Newsroom/Announcement?id=2975902&lang=en&date=20241106&title=interim-report-q3-2024-further-margin-expansion-and-strong-cash-flow-despite-mixed-growth-across-divisions

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/0241106_title_interim_report_q3_2024_further_margin_expansion_and_strong_cash_flow_despite_mixed_growth_across_divisions.htm.txt`

- FY2024 hearing organic_growth_pct (reiterated): check found
  > GN expects the Hearing division to trend towards the upper half of the original organic growth assumption of 8% to 12%.
- FY2024 hearing_core ebita_margin_pct (raised): check found
  > the Hearing division is projecting an EBITA margin in the core hearing aid business of around 20% for 2024.
- FY2024 enterprise organic_growth_pct (lowered): check found
  > the Enterprise division is currently assuming an overall organic revenue growth of around -3% for 2024 compared to the original assumption of -3% to +5%.
- FY2024 gaming_consumer organic_growth_pct (reiterated): check found
  > the Gaming & Consumer division is assumed to deliver organic revenue growth of -10% to -2% reflecting the announcement on June 11, 2024.

## 2025-02-06 - https://www.gn.com/Newsroom/Announcement?id=3021706&lang=en&date=20250206&title=gn-annual-report-2024-strong-growth-in-hearing-and-gaming-offset-by-slight-decline-in-enterprise-leading-to-1-group-organic-revenue-growth-12-reported-ebita-margin-and-free-cash-fl

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/fset_by_slight_decline_in_enterprise_leading_to_1_group_organic_revenue_growth_12_reported_ebita_margin_and_free_cash_fl.htm.txt`

- FY2024 group organic_growth_pct (actual): check found
  > translating into organic revenue growth excluding the wind-down of 4%, while the reported organic revenue growth was 1%.
- FY2024 group organic_growth_pct (actual): check found
- FY2024 group ebita_margin_pct (actual): check found
  > The EBITA-margin increased by 5.4 percentage points compared to 2023 and ended at 12.0% in line with revised financial guidance following the wind-down.
- FY2024 hearing organic_growth_pct (actual): check found
  > as a result of 10% organic revenue growth in Hearing, -3% organic revenue growth in Enterprise, 7% organic revenue growth in Gaming, and -31% organic revenue growth in Consumer due to the wind-down
- FY2024 enterprise organic_growth_pct (actual): check found
- FY2024 gaming_consumer organic_growth_pct (actual): check found
  > translating into total organic revenue growth of -5% for the Gaming & Consumer division.
- FY2025 group organic_growth_pct (initial): check found
  > Organic revenue growth excl. wind-down EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 3% to 7% 12% to 14% ~800
- FY2025 group ebita_margin_pct (initial): check found
- FY2025 hearing organic_growth_pct (initial): check found
  > the Hearing division assumes to contribute with organic revenue growth of 5% to 9%.
- FY2025 enterprise organic_growth_pct (initial): check found
  > the Enterprise division assumes to contribute with organic revenue growth of 0% to 4%.
- FY2025 gaming organic_growth_pct (initial): check found
  > Gaming assumes to contribute with organic revenue growth of 7% to 12% (excluding the impact from the wind-down).

## 2025-04-30 - https://www.gn.com/Newsroom/Announcement?id=3071633&lang=en&date=20250430&title=interim-report-q1-2025-growth-challenged-by-market-uncertainty-proactive-cost-mitigation-initiated-to-support-long-term-margins

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/_report_q1_2025_growth_challenged_by_market_uncertainty_proactive_cost_mitigation_initiated_to_support_long_term_margins.htm.txt`

- FY2025 group organic_growth_pct (lowered): check found
  > GN now expects group organic revenue growth of -3% to +3%, an EBITA margin of 11% to 13%, and an unchanged free cash flow excl. M&A guidance of DKK ~800 million.
- FY2025 group ebita_margin_pct (lowered): check found

## 2025-04-30 - https://www.gn.com/Newsroom/Announcement?id=3071577&lang=en&date=20250430&title=guidance-updated-impact-from-and-mitigation-to-navigate-the-global-trade-environment

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/3071577_lang_en_date_20250430_title_guidance_updated_impact_from_and_mitigation_to_navigate_the_global_trade_environment.htm.txt`

- FY2025 hearing organic_growth_pct (reiterated): check found
  > Consequently, the Hearing division assumes to contribute with organic revenue growth of 5% to 9%.
- FY2025 enterprise organic_growth_pct (lowered): check found
  > Consequently, the Enterprise division assumes to contribute with organic revenue growth of -8% to 0%.
- FY2025 gaming organic_growth_pct (lowered): check found
  > Consequently, the Gaming division assumes to contribute with organic revenue growth of -6% to +2% (excluding the impact from the wind-down).

## 2025-08-21 - https://www.gn.com/Newsroom/Announcement?id=3136821&lang=en&date=20250821&title=interim-report-q2-2025-commercial-and-operational-agility-drove-market-share-gains-and-46-ebita-growth

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/te_20250821_title_interim_report_q2_2025_commercial_and_operational_agility_drove_market_share_gains_and_46_ebita_growth.htm.txt`

- FY2025 group organic_growth_pct (narrowed): check found
  > The organic revenue growth guidance of -3% to +3% (excluding wind-down effects) is narrowed to -2% to +2%.
- FY2025 group ebita_margin_pct (reiterated): check found
  > The guidance on EBITA-margin and free cash flow excl. M&A is confirmed
- FY2025 hearing organic_growth_pct (lowered): check found
  > In the beginning of 2025, we assumed the Hearing division to contribute with organic revenue growth of 5% to 9%. Due to the lower market growth assumption, it is currently assumed that the Hearing division will grow at the lower half of that range.
- FY2025 enterprise organic_growth_pct (narrowed): check found
  > In April 2025, we assumed the Enterprise division would contribute with organic revenue growth of -8% to 0%, and we are continuing to assume a contribution in the middle of this range.
- FY2025 gaming organic_growth_pct (raised): check found
  > Driven by the strong execution in the first half of the year, the Gaming division is now assuming to contribute with organic revenue growth in the upper half of that range.

## 2025-11-06 - https://www.gn.com/Newsroom/Announcement?id=3182179&lang=en&date=20251106&title=interim-report-q3-2025-solid-quarter-with-1-organic-growth-11-ebita-margin-and-dkk-410-million-cash-flow

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/_20251106_title_interim_report_q3_2025_solid_quarter_with_1_organic_growth_11_ebita_margin_and_dkk_410_million_cash_flow.htm.txt`

- FY2025 group organic_growth_pct (reiterated): check found
  > Following a successful execution in the first nine months of the year, GN’s financial guidance for 2025 is confirmed
- FY2025 group ebita_margin_pct (reiterated): check found
  > Confirmed Confirmed Confirmed -2% to +2% 11% to 13% ~800
- FY2025 hearing organic_growth_pct (reiterated): check found
  > it is still assumed that the Hearing division will grow at the lower half of that range.
- FY2025 enterprise organic_growth_pct (reiterated): check found
  > we are continuing to assume a contribution in the middle of this range.
- FY2025 gaming organic_growth_pct (reiterated): check found
  > the Gaming division is still assuming to contribute with organic revenue growth in the upper half of that range.

## 2026-02-05 - https://www.gn.com/Newsroom/Announcement?id=3232627&lang=en&date=20260205&title=gn-annual-report-2025-solid-execution-leading-to-market-share-gains-dkk-1-1-billion-free-cash-flow-and-a-strong-foundation-for-profitable-growth-in-the-years-ahead

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/ng_to_market_share_gains_dkk_1_1_billion_free_cash_flow_and_a_strong_foundation_for_profitable_growth_in_the_years_ahead.htm.txt`

- FY2025 group organic_growth_pct (actual): check found
  > translating into organic revenue growth excluding the wind-down of -1%, while the reported organic revenue growth was -4%.
- FY2025 group organic_growth_pct (actual): check found
- FY2025 group ebita_margin_pct (actual): check found
  > Group EBITA ended at DKK 1,908 million compared to DKK 2,153 million in 2024, equivalent to a margin of 11.4%.
- FY2025 hearing organic_growth_pct (actual): check found
  > In the Hearing division, GN delivered another strong year with 5% organic growth
- FY2025 enterprise organic_growth_pct (actual): check found
  > Organic growth was -6% in 2025
- FY2025 gaming organic_growth_pct (actual): check found
  > resulting in organic revenue growth of -2% (excluding the wind-down effect)
- FY2026 group organic_growth_pct (initial): check found
  > Financial guidance for 2026 Organic revenue growth EBITA margin GN Store Nord 3% to 7% 11.5% to 13.5%
- FY2026 group ebita_margin_pct (initial): check found
- FY2026 hearing organic_growth_pct (initial): check found
  > Consequently, the Hearing division assumes to contribute with organic revenue growth of 3% to 7%.
- FY2026 enterprise organic_growth_pct (initial): check found
  > it is assumed that the Enterprise division will contribute with organic revenue growth of 0% to 6%.
- FY2026 gaming organic_growth_pct (initial): check found
  > Consequently, Gaming assumes to contribute with organic revenue growth of 7% to 13%.

## 2026-03-16 - https://www.gn.com/Newsroom/Announcement?id=3256006&lang=en&date=20260316&title=gn-store-nord-a-s-enters-into-agreement-to-sell-its-hearing-business-to-amplifon-s-p-a-for-dkk-17-0-billion

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/260316_title_gn_store_nord_a_s_enters_into_agreement_to_sell_its_hearing_business_to_amplifon_s_p_a_for_dkk_17_0_billion.htm.txt`

- FY2026 continuing_ops organic_growth_pct (basis_change): check found
  > Consequently, the organic revenue guidance is now expected to be 2-8%, based on unchanged divisional assumptions of 0-6% organic revenue growth in Enterprise, and 7-13% organic revenue growth in Gaming.
- FY2026 group ebita_margin_pct (withdrawn): check found
  > Following the establishment of a standalone operating system structure, the company is expected to re-introduce a profitability guidance.
- FY2026 hearing organic_growth_pct (withdrawn): check found
  > GN’s financial guidance for 2026 now excludes discontinued operations and therefore only reflects Enterprise and Gaming.
- FY2026 enterprise organic_growth_pct (reiterated): check found
  > based on unchanged divisional assumptions of 0-6% organic revenue growth in Enterprise, and 7-13% organic revenue growth in Gaming.
- FY2026 gaming organic_growth_pct (reiterated): check found

## 2026-05-06 - https://www.gn.com/Newsroom/Announcement?id=3289173&lang=en&date=20260506&title=guidance-updated-to-reflect-hearing-business-being-treated-as-discontinued-operations

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/289173_lang_en_date_20260506_title_guidance_updated_to_reflect_hearing_business_being_treated_as_discontinued_operations.htm.txt`

- FY2026 continuing_ops organic_growth_pct (lowered): check found
  > GN Store Nord (continuing operations) is adjusting its organic revenue growth guidance from 2% to 8% to now 0% to 6%
- FY2026 continuing_ops ebita_margin_pct (initial): check found
  > The adj. EBITA margin (excluding one-off costs) for the continuing operations is expected to be 8-9% in 2026 (compared to 7.6% in 2025)
- FY2026 enterprise organic_growth_pct (lowered): check found
  > Consequently, it is assumed that Enterprise will contribute with organic revenue growth of -3% to +3% in a modestly declining market.
- FY2026 gaming organic_growth_pct (reiterated): check found
  > it is still assumed that Gaming will contribute with organic revenue growth of 7% to 13% for 2026.

## 2026-08-19 - https://www.gn.com/Newsroom/Announcement?id=3350848&lang=en&date=20260819&title=financial-guidance-2026-upgrading-adjusted-ebita-margin-while-narrowing-organic-revenue-growth-guidance

- retrieved: 2026-09-26
- local copy: `data/cache/verbal/e_20260819_title_financial_guidance_2026_upgrading_adjusted_ebita_margin_while_narrowing_organic_revenue_growth_guidance.htm.txt`

- FY2026 continuing_ops organic_growth_pct (lowered): check found
  > GN Store Nord (continuing operations) is narrowing its organic revenue growth guidance from 0% to 6% to now 0% to 3%.
- FY2026 continuing_ops ebita_margin_pct (raised): check found
  > which is expected to lead to an adjusted EBITA margin of 9-10% in 2026.
- FY2026 enterprise organic_growth_pct (lowered): check found
  > it is assumed that Enterprise will contribute with organic revenue growth in the lower half of the earlier assumed range of -3% to +3%
- FY2026 gaming organic_growth_pct (lowered): check found
  > it is assumed that Gaming will contribute with organic revenue growth in the lower half of the earlier assumed range of 7% to 13%

## Basis changes and traps (read before comparing guide with actual)

1. **Per-division, not group, until 2023.** FY2021-22 guided GN Hearing and GN Audio separately (plus EPS growth for the
   group); FY2023 added a group organic range but margins stayed per division; FY2024 onward guides the group, with
   divisional numbers only as 'assumptions'. Rows keep the scope as stated (`hearing`, `hearing_core`, `audio`,
   `steelseries`, `enterprise`, `gaming_consumer`, `gaming`, `group`, `continuing_ops`).
2. **SteelSeries (closed 12 Jan 2022).** FY2022 'GN Audio organic' EXCLUDES SteelSeries (reported as M&A growth; SteelSeries
   guided separately, `steelseries`), but the GN Audio adj. EBITA margin INCLUDES it. From FY2023 Audio organic includes
   SteelSeries. From 6 Oct 2021 the FY2021 guides exclude ~DKK 150m SteelSeries transaction costs (FY2021 Audio actual
   21.2% is also excl. DKK 45m transaction costs).
3. **Adjusted vs reported EBITA.** FY2021: reported. FY2022-23: adjusted (excl. non-recurring items), and for Hearing only the
   core business (Emerging Business guided in DKK, not recorded). FY2024-25 and Feb 2026: group REPORTED EBITA margin -
   the June 2024 cut to 12-13% absorbs ~DKK -200m extraordinary wind-down costs. From 6 May 2026: ADJUSTED margin for
   continuing operations, excl. ~DKK 750m one-off carve-out/right-sizing costs. Never EBIT: GN guides EBITA throughout;
   consensus sources quoting EBIT (e.g. MarketScreener) differ by amortisation of acquired intangibles (~DKK 0.4bn/yr).
4. **Reported vs organic vs 'organic excl. wind-down'.** All growth guides are organic. FY2025 group (and Gaming) organic
   EXCLUDES the Elite/Talk wind-down (-3 to -4pp group); FY2024 guides were on reported organic (incl. wind-down after
   June 2024). Both actuals are recorded (2024: 1% reported / 4% ex wind-down; 2025: -1% ex / -4% reported), with the
   guide basis flagged in `note`.
5. **Division perimeter changes.** Gaming & Consumer (FY2024) -> Gaming (FY2025+, Consumer wound down); BlueParrott moved
   from Consumer to Enterprise from 2025 (2024 Enterprise 7,205 as guided vs 7,474 restated in AR2025).
6. **Hearing sold (16 Mar 2026).** Group guide -> continuing operations (Enterprise + Gaming): organic 3-7% (group) became
   2-8% (cont. ops) with unchanged divisional assumptions = `basis_change`, not a revision; EBITA-margin guide
   `withdrawn` 16 Mar - 6 May 2026, then re-introduced as adjusted cont.-ops margin 8-9% (FY2025 cont.-ops base 7.6%).
   The FY2026 actual (AR2026, ~Feb 2027) must be read on the cont.-ops adjusted basis; not yet available.
7. **One-offs inside a raise.** The 19 Aug 2026 margin raise to 9-10% includes DKK 100-150m expected US IEEPA tariff
   refunds (not in the prior guide) - worth ~1.0-1.6pp on ~DKK 9.5bn revenue, i.e. most of the 1pp raise.
8. **'Narrowed' that is a cut.** GN's 'narrowed' often moved the midpoint down (Aug 2023 group and Audio, Nov 2023 Audio,
   Jun 2024 group organic and margin, Aug 2026 cont.-ops organic). The `action` column follows the midpoint.
9. **Source typo.** The 26 Apr 2023 announcement's guidance TABLE prints group organic '-5% to +10%'; its text, the Q1 2023
   report and the 16 Aug 2023 update say '-5% to +7%'. Recorded -5 to +7.
10. **Timing.** Guidance announcements are released the evening before the download-center report date (e.g. 19 vs 20 Aug
   2026, 6 vs 7 May 2026, 30 Apr vs 1 May 2025, 6 vs 7 Nov 2024); `statement_date` is the announcement date.
11. **Gaps.** No FY2024 core-hearing EBITA-margin actual is reported (divisional profit margin instead) - no actual row.
   FY2021 EPS-growth actual is derived (13.90 / 9.72 - 1). DKK-denominated guides (Other EBITA, Emerging Business,
   non-recurring items, free cash flow) are not recorded. No IFRS change affecting the guided metrics in 2021-2026
   (IFRS 16 adopted 2019).
