# Manual verification — grade-C rows the validator cannot fetch

**Status 2026-09-23: all eight done.** The excerpts (speaker, date, source URL, verbatim sentences) are saved in
`pipelines/A_company_financials/data/manual/<company>_<quarter>.txt`; how each one was found (query, mirror, what failed) is in `pipelines/A_company_financials/data/manual/RETRIEVAL_LOG.md`; the verifier reads that folder first and marks the rows `found_manual_file`.
The table below is kept as the record of what was checked and where it was found.

Eight rows in `pipelines/A_company_financials/data/raw/verbal_metrics.csv` cite pages that return HTTP 403 to scripts (investing.com, Logitech's
q4cdn transcript host). They open normally in a browser. Budget: ~3 minutes per row, ~25 minutes total.

## The procedure (same for every row)

1. Open the `source_url` in a browser. If it is paywalled or gone, use the fallback in the table (Logitech and
   TD Synnex publish official transcripts on their IR sites; Nordic publishes the webcast replay).
2. Ctrl-F the **search phrase**. Read the sentence around it.
3. Check the **what to confirm** column: the sentence must support the number in `value` (sign and size).
4. In `pipelines/A_company_financials/data/raw/verbal_metrics.csv`, on that row:
   - write `confirmed` in `manual_check` if it does — optionally paste a longer exact sentence into `quote`;
   - write `rejected` if it does not, and fix `value` in **both** `verbal_metrics.csv` and the company CSV
     (`pipelines/A_company_financials/data/raw/<company>_quarterly.csv`, same quarter, same column) so the consistency check stays green.
5. Run `python pipelines/A_company_financials/scripts/validate.py --no-fetch-verbal`. The row becomes `found_manual`, the matching
   `config/data_config.csv` row becomes `validated = yes`, and the report's to-do table shrinks.

`manual_check` is never overwritten by the verifier; leave it blank for rows you did not look at.

## The eight rows

| # | company / quarter | metric → value | open this | fallback | search phrase | what to confirm |
|---|---|---|---|---|---|---|
| 1 | Logitech 2024Q1 (Q4 FY24 call, 30 Apr 2024) | `sellthrough_minus_sellin_pts` = **−5** | https://s1.q4cdn.com/104539020/files/doc_financials/2024/q4/LOGN-CH_Transcript_2024-04-30.pdf | ir.logitech.com → Financials → Quarterly Results → FY24 Q4 → Transcript | `sell-through` | Sell-through roughly flat while net sales (sell-in) grew ~+5% → gap ≈ −5. If the transcript gives different numbers, value = sell-through growth − net-sales growth. |
| 2 | Logitech 2025Q1 (Q4 FY25 call, 29 Apr 2025) | = **+2** | https://uk.investing.com/news/transcripts/earnings-call-transcript-logitechs-fiscal-2025-growth-and-strategic-focus-93CH-4054863 | ir.logitech.com → FY25 Q4 → Transcript; or fool.com "Logitech LOGI Q4 2025 earnings call transcript" | `outpaced` | "sell-through outpaced the sell-in by approximately two points" (or equivalent) → +2. |
| 3 | Logitech 2025Q2 (Q1 FY26 call, Jul 2025) | = **0** | https://s1.q4cdn.com/104539020/files/doc_financials/2026/q1/Transcript-Q1-FY-26-Earnings-Call.pdf | ir.logitech.com → FY26 Q1 → Transcript | `sell-in` | Sell-in described as in line with sell-through / channel weeks-on-hand unchanged → 0. |
| 4 | Logitech 2025Q4 (Q3 FY26 call, Jan 2026) | = **+4** | https://www.investing.com/news/transcripts/earnings-call-transcript-logitech-q3-2026-beats-forecasts-stock-dips-93CH-4468933 | ir.logitech.com → FY26 Q3 → Transcript; fool.com | `sell-through` | Sell-through growth (~+10% reported) minus net-sales growth (+6%) ≈ +4. |
| 5 | Logitech 2026Q1 (Q4 FY26 call, Apr 2026) | = **0** | https://www.investing.com/news/transcripts/earnings-call-transcript-logitech-q4-2026-beats-expectations-stock-rises-93CH-4677413 | ir.logitech.com → FY26 Q4 → Transcript; fool.com | `weeks on hand` | Channel weeks-on-hand in line with last year / sell-through ≈ sell-in → 0. |
| 6 | Nordic 2025Q3 (Q3 2025 call, Oct 2025) | `dist_inventory_state` = **0** | https://www.investing.com/news/transcripts/earnings-call-transcript-nordic-semiconductor-q3-2025-sees-strong-revenue-growth-93CH-4320415 | nordicsemi.com → Investor Relations → Reports & presentations → Q3 2025 webcast replay (Q&A, ~min 25–40) | `lighter` | Management says distributor/channel inventory is healthy, "a bit on the lighter side" → normal (0), not restocking (+1). |
| 7 | Nordic 2026Q2 (Q2 2026 call, Jul 2026) | = **+0.5** | https://www.investing.com/news/transcripts/earnings-call-transcript-nordic-semiconductor-posts-record-q2-2026-revenue-93CH-4840152 | nordicsemi.com → Q2 2026 webcast replay (Q&A) | `advancing` | CEO cannot rule out some customers advancing orders on capacity worries; distributor inventory unchanged/healthy → mild pull-in (+0.5). If he denies any pull-forward, set 0. |
| 8 | TD Synnex 2026Q2 (FQ2 FY26 call, 25 Jun 2026) | `endpoint_gb_yoy_pct` = **13** | https://www.investing.com/news/transcripts/earnings-call-transcript-td-synnex-tops-q2-2026-forecasts-as-ai-demand-surges-93CH-4760952 | ir.tdsynnex.com → Events & Presentations → FQ2 2026 → Transcript; fool.com | `Endpoint` | Endpoint Solutions gross billings +13% YoY (ASP-led, units mid-single-digit). |

## If you also want to clear the 31 "uncited" cells (optional, ~2 hours)

`pipelines/A_company_financials/data/processed/verbal_uncited.csv` lists grade-C cells with no evidence row. For each: find the call (fool.com
and ir sites hold the older Logitech and TD Synnex transcripts; Ingram's are on ir.ingrammicro.com), add a row
to `verbal_metrics.csv` with the sentence and URL, set `manual_check = confirmed`, and re-run the validator. The
TD Synnex 2022Q4–2023Q4 Endpoint values were coded from words ("modest decline", "trough"), so set
`is_estimate = 1` on those rows unless the call gives a number.
