# Pipeline A — company financials

Inputs of the model. Everything under this folder: `config/data_config.csv` (every source with URL, retrieval method, validation method and status), `src/pipeline_a/` (fetch + verify code), `data/raw/` (hand-typed quarterly CSVs, one citation per row; `verbal_metrics.csv` for grade-C data points), `data/manual/` (hand-saved transcript excerpts + retrieval log), `data/processed/` and `data/cache/` (generated, git-ignored).

```bash
python pipelines/A_company_financials/scripts/fetch.py       # download SEC XBRL, 8-K exhibits, Nordic (Oslo Børs NewsWeb), GN PDFs
python pipelines/A_company_financials/scripts/validate.py    # coverage, XBRL reconciliation, filing-text verification, grade-C checks
```

Full description, current counts and the four checks: `docs/reference.md`, section "Company financial data pipeline (Pipeline A)". Builders run by hand, not by `validate.py`: `src/pipeline_a/{bestbuy_comps,fx_disclosed,guidance_history,odm_monthly}.py` and `scripts/build_gn_guidance.py` (their committed CSVs are what the model reads). `src/pipeline_a/nordic_guidance.py` (Nordic's guidance statements Q2 2017–Q4 2020: half-year guides, the first quarterly guides, the Dec 2018 cut and the two 2020 pre-announcement raises, each excerpt checked against the cached report or announcement; decision F32) runs inside `validate.py` and writes `data/raw/nordic_guidance_history.csv`.
