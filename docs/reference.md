# Reference — full detail behind `README.md`

*The short entry point is `README.md`. This file keeps the long-form description of every pipeline and step; the per-folder READMEs are the authority where they differ.*

# Supply Chain Signal Model — Nordic Semiconductor ← Logitech / GN ← Ingram / TD Synnex / Amazon

A runnable, config-driven model of the peripherals supply chain: it ingests public quarterly data for five companies, builds tier-by-tier series (sell-out proxy → distributor → OEM sell-in → component), encodes the lag and mechanism assumptions in one YAML file, tests them against the data, and produces point forecasts with ranges for the three October/November prints.

Public data only (company filings, presentations, call transcripts, findchips.com distributor stock snapshot). Nothing from any employer system.

## Run it in under ten minutes

```bash
git clone <this repo> && cd case_study
python3 -m venv .venv && source .venv/bin/activate      # optional
pip install -r requirements.txt                          # pandas, numpy, pyyaml, matplotlib, tabulate, pytest, python-docx
python scripts/run_all.py                                # ~10 seconds: steps 1-7 → outputs/ and steps/*/outputs/
open deliverables/dashboard.html                              # monitoring view (single self-contained file)
python scripts/serve.py                                  # results page, one tab per step: http://127.0.0.1:8765 (updates itself after each re-run)
pytest -q                                                # 301 tests, ~2 min
```

`./run.sh` does all three. Python ≥ 3.10; the model itself needs no network (it reads `pipelines/A_company_financials/data/raw/*.csv`).

## Company financial data pipeline (Pipeline A)

```bash
python pipelines/A_company_financials/scripts/fetch.py      # download: SEC XBRL + 8-K exhibits + Nordic (Oslo Børs) + GN PDFs (~2 min first run)
python pipelines/A_company_financials/scripts/validate.py   # check every hand-typed figure; writes its data/processed/validation_report.md
```

**All sources are listed in one file, `pipelines/A_company_financials/config/data_config.csv`** — one row per document (company, quarter key, source type, URL, which CSV columns it backs) with `validated` / `validated_on` / `validation_detail` columns that `validate.py` fills in. To add a new quarter: add the row(s) there and the new line in `pipelines/A_company_financials/data/raw/<company>_quarterly.csv`, then run the two commands. Current status: 150 rows — 150 validated, 0 with discrepancies, 12 qualitative sources marked `manual`.

**Is the data correct?** Three mechanical checks, no reading required: (1) coverage — every company has the 16 quarters 2022Q3–2026Q2 needed for the regime study, and Logitech / TD Synnex reach back to 2020Q1 via XBRL headline lines so the 2020–21 supply-constrained regime is covered at the distributor tier too (Ingram was private before its 2024 IPO: no public quarterlies before 2022); (2) 151 headline cells for the US filers agree with the SEC XBRL API within 0.5% (max 0.37%); (3) 467 hand-typed cells across all five companies are found verbatim in the cited filing (PDF or 8-K exhibit), 39 of them as restated comparatives in later filings. (4) **Grade-C verbal metrics** (Logitech sell-through minus sell-in, Nordic distributor-inventory state, GN Enterprise sell-out gap, distributor segment growth) live in `pipelines/A_company_financials/data/raw/verbal_metrics.csv` — one row per data point with the phrase it rests on, the source URL and an `is_estimate` flag when the call gave direction but not magnitude. The validator searches the phrase in the cited page or, when the site blocks bots, in the quarter's cached report, and checks the value equals the company-CSV cell it feeds: 41 of 41 quotes verified and 41/41 values consistent — 33 against the cited page or the quarter's cached report, 8 against transcript excerpts saved by hand in `pipelines/A_company_financials/data/manual/<company>_<quarter>.txt` (with speaker, date and source URL) because investing.com / q4cdn return 403 to scripts; the procedure is in `docs/history/manual_verification_2026-09-23.md`, and a human result in the `manual_check` column is also honoured by the verifier. Grade-C cells with no evidence row (31: Logitech 2021–22, TD Synnex, Ingram segment growth, three carried-forward Nordic states) are listed as effectively grade D in `pipelines/A_company_financials/data/processed/verbal_uncited.csv`. What cannot be machine-checked at all (chosen adjusted margins, Logitech regions from 10-Q notes, Ingram's pre-IPO quarters) is in section 5 of the report with a two-minute spot-check recipe.

Data grades used throughout: **A** audited annual report / 10-K; **B** unaudited quarterly report / 8-K exhibit (reconciled to XBRL and to the later audited figures); **C** verbal — call or report commentary coded to a number; **D** our estimate, interpolation or a scrape.

| Step | Source | Trust | Output |
|---|---|---|---|
| 1 | **SEC XBRL company-facts API** (`data.sec.gov`) for Logitech, Ingram Micro, TD Synnex, Amazon. Free, no key — SEC only asks for a descriptive `User-Agent` and ≤10 requests/s. Q4 is derived as FY − (Q1+Q2+Q3). Cached in `data/cache/sec/`. | Legally liable filings | `data/processed/sec_quarterly.csv` |
| 2 | Reconcile every hand-typed revenue / inventory / gross-profit figure in `data/raw/` against XBRL | — | `data/processed/sec_reconciliation.csv` — **151 checks, 0 differences > 0.5%** |
| 1b | Extend `data/raw/` backwards from XBRL for pre-2022 quarters (headline lines only, source-stamped) — TD Synnex and Logitech now start 2020Q1; the Tech Data merger (Sep 2021) is a flagged break with YoY masked 2021Q4–2022Q3 | SEC | rows appended in `data/raw/` |
| — | Steps below are what `scripts/fetch.py` runs; `scripts/validate.py` then scores each row of `config/data_config.csv` (paths relative to `pipelines/A_company_financials/`) |  |  |
| 3a | **Oslo Børs NewsWeb API** (`api3.oslo.oslobors.no/v1/newsreader`, keyless) — every Nordic quarterly and annual report is attached to its stock-exchange announcement; 45 filings 2017Q2–2026Q2 (from the Q2 2017 report, the first with a guidance statement the model records; decision F32), each cited by NewsWeb message id; the list endpoint caps at 50 messages per call, so windows are split on `overflow` (P131). Announcement bodies without an attachment (guidance updates, pre-announcements) are cached as `newsweb_<id>.txt`. (nordicsemi.com itself returns 403 to non-browser clients.) | Regulated exchange announcements | `data/cache/filings/nordic/`, `data/processed/newsweb_nordic_index.csv` |
| 3b | GN interim and annual report PDFs from `gn.com` URLs in `manifest.py` | Company IR | `data/cache/filings/gn/`, `data/processed/filing_downloads.csv` |
| 4 | Verify every hand-typed Nordic / GN figure appears in the filing text (pdfplumber; handles Nordic's USD-thousands tables; restated figures are searched in the next four quarterly reports and two annual reports) | — | `data/processed/filing_verification.csv` — **Nordic 89/89, GN 75/75 found** (18 of them as restated comparatives in later filings) |

Why no API keys and no AI: the two APIs that matter (SEC XBRL, company IR PDFs) are keyless; the only places an LLM could add value — reading segment tables and call commentary out of PDFs — are exactly where reproducibility matters most, so those numbers are typed by hand with a citation per row and then *verified* mechanically by steps 2 and 4. Segment lines (Logitech categories, Nordic end-markets, GN divisions) are not in XBRL company-facts, which is why the model's inputs stay in `data/raw/` rather than being pulled from the API.

What the run produces:

| Output | What it is |
|---|---|
| `outputs/forecasts.csv` | The six numbers: Nordic Q3'26 revenue & GM, Logitech Q2 FY27 net sales & GM, GN continuing-ops Q3'26 revenue & adj. EBITA margin — point, ≈80% range, company guide |
| `outputs/model_report.md` | Reasoned lag, cross-correlations by regime, turning points, amplitude ratio, regression, guidance-bias table, attribution Monte Carlo, forecast detail |
| `deliverables/dashboard.html` | Forecasts, a traffic-light indicator table (what to watch and why), four charts, last-8-quarter tier panel |
| `outputs/forecast_details.json` | Every intermediate number behind the forecasts |
| `outputs/tier_panel.csv` | The constructed quarterly panel, 2020Q1–2026Q3, ~60 columns (+ Pipeline B context columns `wsts_yoy`, `rseas_yoy`) |
| `outputs/figures/*.png` | Tier YoY growth, inventory days by tier, cross-correlation, Nordic guidance beats, regression fit |

The 2-page investment note is `deliverables/investment_note.md` (render it to `.docx` with `python scripts/build_note.py`; not committed). The brief answered question by question is `deliverables/my_analysis.html` (the dashboard's Analysis tab; the analyst's hand-written reading of one run, its headline numbers checked against the outputs by `tests/test_analysis_page.py`; `my_analysis.md` is the working draft); every decision with its reason is a row in a step's `config/decisions.csv`. `docs/history/mechanism_and_lags.md` is the original mechanism write-up (historical).

## Macro / industry context pipeline (Pipeline B)

```bash
python pipelines/B_macro_industry/scripts/validate.py       # ~20 s; keyless
```

Used sparingly: none of these observe peripherals or Nordic directly, so they are regime context and sanity checks, never model inputs that could dominate a 14-quarter panel. Two series are fetched and each is cross-checked against a second primary source; the grade-C documents are quote-checked; everything else on the data-source note's list is logged in `pipelines/B_macro_industry/config/data_config.csv` with its retrieval method, validation method and status (`yes` / `manual` / `not_fetched` / `rejected`) and the reason.

| Source | Grade | Retrieval | Validation | Result (2026-09-23) |
|---|---|---|---|---|
| FRED `RSEAS` — US electronics & appliance store sales, SA, monthly | A (Census) | `fredgraph.csv`, keyless | every month vs Census MARTS `adv44300.txt` (the primary publisher), tol 0.5% | 416 months, 0 flagged, max diff 0.000% |
| WSTS Historical Billings Report — global semiconductor billings, monthly + 3MMA | B | page scraped for the current `.xlsx`, keyless | latest SIA press-release headline (worldwide 3MMA) vs the WSTS 3MMA sheet, tol 0.5% | Jul-2026: SIA $146.8bn vs WSTS $146.8bn (−0.00%) |
| Bluetooth SIG 2025 market update (ABI) | C | page download | quoted sentence must occur in the page | found |
| Nordic Credit Rating report, Sep 2025 | C | PDF download | quoted sentence must occur in the PDF | found |
| Consensus aggregators | C | manual (client-rendered) | none possible; dated in the note | manual |
| IPC electronics supply-chain sentiment | C | not fetched (404 / form) | none | not_fetched |
| SSB / Eurostat exports; sell-side research | — | not fetched | — | rejected (Nordic is fabless, chips never cross Norwegian customs; sell-side paywalled) |

What it feeds: `wsts_yoy` and `rseas_yoy` context columns in the tier panel and section 7 of the model report, and one sanity check — WSTS worldwide YoY was negative 2022Q3–2023Q3, the model's `destock` regime is 2022Q3–2024Q1: same start, and Nordic's distributor adjustment ran two quarters longer (its Q1 2024 report is the first to call it "predominately behind us").

## Real-time channel pipeline (Pipeline C)

```bash
python pipelines/C_realtime_channel/scripts/validate.py       # ~2 min; keyless (Mouser API optional)
```

Trustable tools used directly where they exist and are keyless: the **iFixit public API** (teardown step text and photos) and **findchips** (Supplyframe's aggregator, which serves the distributors' own feeds as structured rows — Digi-Key and Mouser return 403 to scripts). The official **Mouser Search API** runs when `MOUSER_API_KEY` is set and becomes the cross-check. Every run appends a dated snapshot to `channel_snapshots.csv`, so the channel indicator becomes a series over time.

| Source | Grade | Retrieval | Validation | Result (2026-09-23) |
|---|---|---|---|---|
| findchips distributor rows, 5 Nordic parts | D (snapshot → series) | page per part, `data-…` attributes parsed | Farnell/Newark/element14 report one pool → agree within 15%; every authorized row parses; exact MPN present; Mouser API when keyed | 16 authorized rows per part; checks 17/20 (three pool disagreements are feed timing) |
| Hand snapshot 22 Sep (browser) | D | manual | overlap with first scripted snapshot within 25% | 4/6 cells agree; the two misses are region-dependent listings |
| iFixit teardown/repair guides for Logitech, Jabra, SteelSeries | C | API search + guide text | sentence verbatim from the guide; photo check flagged | 156 guides; 4 sentences name a chip (Spotlight: "Nordic Semis are quite common on Logitech peripherals"; Revue: nRF24); 24 teardowns listed for photo reading |
| FCC OET grants, JNZ | D → B once photos read | manual export (apps.fcc.gov 403 outside US) | ids unique, JNZ-prefixed, dates parse; reading progress counted | 101 grants, 81 with public photos, 0 read yet |
| Amazon BSR; Amazon price / promotion; Idealo; brand promo pages | D | rejected / skipped | — | reasons in docs/not_built.md and the dashboard checklist |

Which distributors findchips lists varies with the requesting region, so the series is built on distributor *groups* and each row records which groups were counted. The dashboard's tier-3 indicator reads the latest snapshot; nothing here enters the regression or the forecast.

## Step 1 — filing confidence (how far the quarterly numbers can be trusted)

```bash
python steps/step1_filing_confidence/scripts/run.py
```

Three separate tests, every row logged in `steps/step1_filing_confidence/outputs/`: (1) Σ4Q of the original quarterly revenues vs the audited full-year figure (10-K XBRL annual fact for the SEC filers; Nordic's annual report, typed and verified in its text; GN's annual report, located in its text) — ≤ 0.02% for all five companies, by construction, because Q4 absorbs the audit true-ups; (2) original vs restated segment values, both verified in the cited filings — Nordic Industrial & Healthcare ±15% and Consumer ±7% (2025 taxonomy), Logitech Video Collaboration ±26% and Gaming ±8% (FY24 recast), GN Enterprise ±4% (BlueParrott); (3) reported vs adjusted margins — up to 7.8 pts (Nordic GM) and 19.3 pts (GN EBITA), Logitech ≤ 0.5 pt. Folded into `confidence.csv` (interval per company × metric class, the rule the model follows) and a **final grade per company: Logitech B, Ingram B, TD Synnex B, Nordic C, GN C** — the C is margin-definition room, not the revenue lines. The step itself is grade A (arithmetic on filings). One data fix came out of it: the Nordic 2024 segment cells were replaced with the restated 2025-taxonomy comparatives so that 2025 YoY is like-for-like.

## Change an assumption

Everything is in `config/model.yaml`; the Python contains no numbers.

```yaml
lag_weeks:                       # the reasoned lag, in weeks, per tier
  sell_out_to_distributor: {low: 2, mid: 3, high: 4}
radio_content:                   # which product lines carry a wireless SoC, and what share of units
  logitech:
    tablet_usdm: {weight: 0.9, core: true}
  gn:
    hearing_rev_dkkm: {weight: 0.5}
regression:
  lags_used: [1, 2, 3]           # which quarterly lags enter the regression
attribution:
  logitech:
    nordic_socket_share: {low: 0.30, mid: 0.45, high: 0.60}
forecast:
  nordic_2026Q3:
    guide_low: 220
    guide_high: 240
    signal_adjustments_usdm:      # named, arguable line items
      capacity_worry_pull_in: 0.0     # F19: was +1.0; a risk scenario only
```

Edit, re-run `python scripts/run_all.py`, and every table, chart and forecast regenerates. To keep a variant: `python scripts/run_all.py --config my_variant.yaml`.

When a new quarter prints, add one row to the relevant `pipelines/A_company_financials/data/raw/*.csv` (each row cites its filing) and re-run.

## How the forecast is built

1. **Expected guide error** (step 7e, `steps/step7_forecast/src/guide_error_model.py`, F16/F17): guide midpoint × (1 + expected error). Expected error = the company's habit (its own record on its guides, partially pooled with 12 semiconductor peers' quarterly guides) + the channel state of the quarter before (step 3b `cycle_state`: distributors *building* stock lowers the error; effect estimated on the peers, `steps/step7_forecast/outputs/guide_error_state_effect.csv`). Nordic uses its own record split by channel state (+3.08% not building, n 14; −6.24 pts building, n 7; F20), the pooled model logged as a pre-registered challenger. GN has only a full-year guide, so its habit is the plain mean of its own August misses (−3.3 pts, F23).
2. **The supply chain as terms** (step 7c, `chain_forecast.py`): a chain forecast from the six decisions enters as weight × (chain − anchor), the weight set by the walk-forward back-test; Nordic Q3 and Logitech (F29, guide method only) both carry weight 0; events (Logitech's supplier incident, the step 5d event study, F21) are pushed through the graph. Terms and evidence: `steps/step7_forecast/outputs/chain_terms.csv`.
3. **Range** = the guide-error model's predictive sd, ≈ 80% band. **Margins** (F18): guide + the company's own past error on that guide; where only a floor is given (Nordic GM > 50%), the simple rule with the lowest walk-forward error.
4. **Cross-checks** printed beside the forecast, not used as it (`cross_checks.py` → `steps/step7_forecast/outputs/cross_checks.csv`): every other method, one-input scenario, margin rule and pre-registered challenger (6c, 6c-g, F16 pooled, F25, F27 Logitech FX, F28 ODM nowcast), with whether it lands inside the band; the formula behind each number (`formulas.py`) sits above them.
5. **GN** revenue and adj. EBITA from its full-year guides and their August errors (F23), plus the FX term from ECB rates (F27); the division view (Enterprise / Gaming organic × FX, EBITA bridged from Q2) is kept as a scenario.

6. **Nordic Q4** (h = 2, not one of the three prints): GRi (F26; Logitech sell-in through the Nordic → ODM → Logitech segment), with GR, CH and CYC as pre-registered challengers (`q4_prereg_log.csv`).

Current numbers: `outputs/forecasts.csv`; the method's history: `steps/step7_forecast/config/decisions.csv`.

## Repository layout

Four data pipelines feed seven analysis steps. Every pipeline and every step is its own folder with the same shape — `README.md` (what it decides, on what evidence), `config/` (hand-typed inputs with sources), `src/` (only that unit's code), `outputs/` or `data/processed/` (every table it logs). The only shared code is the small core in `core/` (config, ingest, tier panel).

```
deliverables/                            investment_note.md, dashboard.html, my_analysis.md / .html, figures/ (.pdf / .docx renders are local only)
config/                                  the assumptions: model.yaml (lags, regimes, attribution priors, breaks, forecast rules), supply_graph*.csv, fiscal_calendar.csv
pipelines/                               DATA — fetched, validated, logged in each pipeline's config/data_config.csv
  A_company_financials/                  company filings: hand CSVs + XBRL reconciliation + filing-text verification + grade-C quote checks; ODM monthly revenue
  B_macro_industry/                      ECB FX rates (GN's FX term, F27); FRED / Census and WSTS (break and lag checks, Q4 challengers; never in the six forecasts)
  C_realtime_channel/                    distributor stock snapshots (findchips; Mouser API optional), iFixit teardown scan, FCC grant list
  D_peer_panel/                          12 semiconductor peers' guides vs actuals, 2008-2026
steps/                                   ANALYSIS — one folder per step of the plan (steps/README.md has the map)
  step1_filing_confidence/               Σ4Q vs audited FY · original vs restated segments · reported vs adjusted margins → confidence.csv, final grade per company
  step2_attribution/                     Nordic ← Logitech / GN share: five evidence legs A–E + the share as a time path → attribution.json, attribution_path.csv
  step3_inventory_mechanism/             inventory factors, channel index, bullwhip by link, ordering-rule regression, channel call, cycle state → step3_report.md
  step4_lag_structure/                   reasoned lag edge by edge, cross-correlation, turning points, amplitude → edge_lags*.csv, xcorr_*.csv
  step5_supply_graph/                    supply graph (lags, shares, kernel), structural breaks and the incident event study, route nowcast, industry-cycle challenger
  step6_backtest/                        walk-forward point-in-time back-test (h=1 / h=2; GR, GRg, GRi), composite challenger, 12-peer panel, guidance bias
  step7_forecast/                        guide-error model, chain terms, margins, FX, the three forecasts + Nordic Q4, scenarios, cross-checks, dashboard
core/                            core: config.py (paths), ingest.py (Pipeline A CSVs + Pipeline C series), tiers.py (the tier-by-tier panel), verify_ledger.py
outputs/                                 every table and figure the run writes: forecasts.csv, scenarios.csv, model_report.md, tier_panel.csv, pitfalls.md, figures/
audit/                                   pitfalls.csv, verification_ledger.csv, monitoring_plan.csv, brief_audit.csv, brief_data_checklist.csv, metric_catalogue.csv
docs/                                    reference.md (this file), not_built.md, data_flow.svg, source_notes/ (raw research notes with URLs), history/ (superseded write-ups)
scripts/                                 run_all.py (steps 1 → 7, then the deliverables), serve.py, build_note.py, draw_data_flow.py
webapp/                                  results page and the ⚙ Assumptions sandbox
tests/                                   offline tests: core, steps, Pipelines A-D (count in README.md)
```

## Data provenance

Nordic: quarterly reports 2017–2026 (nordicsemi.com IR; machine-fetched copies via Oslo Børs NewsWeb, message ids in `pipelines/A_company_financials/data/processed/newsweb_nordic_index.csv`; the typed series runs 2019Q1–2026Q2 with quarterly guides from 2019Q1 and the 2017–18 half-year guides in `data/raw/nordic_guidance_history.csv`, F32) and Q2 2026 call. Logitech: SEC 8-K Ex 99.1 per quarter, 10-K FY22–FY26, 10-Q Jun-26, call transcripts. GN: annual reports 2022–2025, interim reports Q1 2022–Q2 2026, 19 Aug 2026 guidance release, Q2 2026 call. Ingram Micro: S-1/A (Oct 2024), 10-K FY24/FY25, quarterly releases; 2022–H1 2023 quarterlies from XBRL-derived aggregator data (flagged `is_estimate`). TD Synnex: 8-K Ex 99.1 FQ1'22–FQ2'26, transcripts. Distributor stock: findchips.com snapshot 22 Sep 2026 (Digi-Key/Mouser block automated fetches). Full URLs in `docs/source_notes/*.md`; every document is a row in the pipeline's `config/data_config.csv`.
