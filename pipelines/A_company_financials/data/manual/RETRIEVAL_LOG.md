# Retrieval log — grade-C transcript excerpts (data/manual/)

Why this folder exists: `pipelines/A_company_financials/scripts/validate.py` fetches every `source_url` in `data/raw/verbal_metrics.csv`. Eight
sources returned HTTP 403 to scripts (investing.com, Logitech's q4cdn CDN when addressed directly) on 2026-09-23. For
those, the transcript was located by hand, the relevant sentences were copied verbatim into
`<company>_<quarter>.txt` (header = call date, source URL, retrieval date), and the verifier searches this folder
first. Nothing here comes from a paid terminal or an employer system: every source is a public web page.

Method (repeatable by anyone): web search for `<company> <fiscal quarter> earnings call transcript` plus a
distinctive phrase (`sell-through`, `weeks on hand`, `distributor inventory`, `Endpoint Solutions`); open the
first mirror that renders the full Q&A without login; Ctrl-F the phrase; copy the sentence and speaker.
Mirrors that worked without login on 2026-09-23: roic.ai, gloom.sh, stockinsights.ai, investing.com regional
mirrors (ca./ng.), Logitech's own transcript PDFs when reached via a web-fetch proxy. Mirrors that did NOT work:
seekingalpha.com (paywalled after the first paragraphs), insidermonkey.com (headings only), finance.yahoo.com
transcript pages (404), fool.com (no Logitech/Nordic coverage for these quarters), www.investing.com (403).

| company / quarter | metric | value | original source_url (403) | working source used | search query that found it | sentence relied on |
|---|---|---|---|---|---|---|
| logitech 2024Q1 (Q4 FY24 call, 30 Apr 2024) | sellthrough_minus_sellin_pts | −5 | s1.q4cdn.com …/2024/q4/LOGN-CH_Transcript_2024-04-30.pdf (403 to curl; OK via web-fetch proxy) | same PDF | direct URL | CFO Boynton: "sell-through was flat year-over-year. Sell-in was up 5%." |
| logitech 2025Q1 (Q4 FY25 call, 29 Apr 2025) | sellthrough_minus_sellin_pts | +2 | uk.investing.com …-93CH-4054863 | https://www.stockinsights.ai/us/LOGI/earnings-transcript/fy25-q4-6254 | `"Transcript: Logitech International Q4 2025 Earnings Conference Call"` | CFO Anversa: "sell through outpaced the sell in by approximately two points" |
| logitech 2025Q2 (Q1 FY26 call, Jul 2025) | sellthrough_minus_sellin_pts | 0 | s1.q4cdn.com …/2026/q1/Transcript-Q1-FY-26-Earnings-Call.pdf (403 to curl; OK via web-fetch proxy) | same PDF | direct URL | CFO Anversa: "started with sell-in in line with sell-through" |
| logitech 2025Q4 (Q3 FY26 call, 27 Jan 2026) | sellthrough_minus_sellin_pts | +4 | www.investing.com …-93CH-4468933 | https://gloom.sh/stocks/logi/transcripts/q3-2026 | `Logitech Q3 fiscal 2026 earnings call transcript January 2026 "sell-through"` | CFO Anversa: "Sell-through was up 10% year-over-year in the third quarter" (8% cc); net sales +6% reported (8-K) → +4 |
| logitech 2026Q1 (Q4 FY26 call, 5 May 2026) | sellthrough_minus_sellin_pts | 0 | www.investing.com …-93CH-4677413 | https://www.roic.ai/quote/LOGI/transcripts/2026-year/4-quarter | `Logitech Q4 fiscal 2026 earnings call transcript "weeks on hand"` | CFO Anversa: weeks on hand "pretty much in line where they were last year" |
| nordic 2025Q3 (Q3 2025 call, Oct 2025) | dist_inventory_state | 0 | www.investing.com …-93CH-4320415 | https://ca.investing.com/news/transcripts/earnings-call-transcript-nordic-semiconductor-q3-2025-sees-strong-revenue-growth-93CH-4277749 | `Nordic Semiconductor Q3 2025 earnings call transcript distributor inventory "lighter"` | CEO Wollan: "healthy levels relatively. Probably a bit on the lighter side" |
| nordic 2026Q2 (Q2 2026 call, Jul 2026) | dist_inventory_state | +0.5 | www.investing.com …-93CH-4840152 | https://ng.investing.com/news/transcripts/earnings-call-transcript-nordic-semiconductor-posts-strong-q2-2026-growth-93CH-2646899 | `"Nordic Semiconductor" Q2 2026 earnings call transcript investing.com` | UBS: management "not ruling out … inventory pull forward"; CEO Wollan: "might be an element of some safety stockings for some additional weeks" (smallest customers). Quote changed from our paraphrase "advancing orders" to the verbatim wording; value unchanged. |
| tdsynnex 2026Q2 (FQ2 FY26 call, 25 Jun 2026) | endpoint_gb_yoy_pct | 13 | www.investing.com …-93CH-4760952 | https://www.roic.ai/quote/SNX/transcripts/2026-year/2-quarter | `TD SYNNEX fiscal second quarter 2026 earnings call transcript Endpoint Solutions gross billings` | CFO Jordan: "Endpoint Solutions gross billings increased 13% year-over-year … mid-single-digit growth in units" |

Outcome: all eight values as previously coded were confirmed; one quote string was corrected to the verbatim
wording. To re-verify: open the "working source used", Ctrl-F the sentence; or delete the `.txt` and re-run
`python pipelines/A_company_financials/scripts/validate.py` — the row falls back to `fetch_failed` and reappears in the manual to-do list.
