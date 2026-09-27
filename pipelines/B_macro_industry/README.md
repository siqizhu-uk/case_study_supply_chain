# Pipeline B — macro / industry context

Context and sanity checks, plus two inputs: the ECB reference rates behind the FX rule (`src/pipeline_b/fx.py` → `data/raw/fx_quarterly_ecb.csv`, F27) and US electronics-store sales, the regressor of challengers only (CYC, G29; route nowcast, G27). `data/processed/macro_monthly.csv` and `macro_quarterly.csv` are committed so a fresh clone runs (P118). `config/data_config.csv` lists the ten sources from the data-source note with grade, retrieval method, validation method, status and reason (fetched + cross-checked, quote-checked, manual, not_fetched, rejected). `src/pipeline_b/` fetches FRED RSEAS (validated against Census MARTS) and WSTS billings (validated against the SIA press release), quote-checks the grade-C documents, and builds `data/processed/macro_monthly.csv` / `macro_quarterly.csv` plus `validation_report.md` with the industry-cycle dating used to sanity-check the model's regimes.

```bash
python pipelines/B_macro_industry/scripts/validate.py [--refresh]
```
