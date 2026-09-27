# Pipeline D — peer panel (guidance misses of 12 semiconductor companies, 2011–2026)

**Why.** The Nordic composite rests on about 2 independent observations: one cycle of one company. This panel holds several cycles (2011–12, 2015–16, 2019, 2022–24) across 12 companies (the original six plus six chosen by a pre-registered criterion, distribution share >= 35% — Nordic 42-55%; shares quote-checked in `config/peer_characteristics.csv`). It is used to test the same mechanism on data the Nordic model never saw (step 6d).

```bash
python pipelines/D_peer_panel/scripts/validate.py    # ~3 min first run (SEC downloads, cached in data/cache/), seconds after
```

| file | what |
|---|---|
| `config/peers.yaml` | companies, CIKs, one regex per guidance wording, **structural breaks** (M&A / divestitures), **verified outliers**, **actual overrides**, the unit-typo and plausibility rules — each with its reason |
| `config/data_config.csv` | one row per company per source, with retrieval method, validation method and status |
| `data/raw/peer_guidance.csv` | every earnings release: the guide it gave (low / mid / high) and the sentence it was read from |
| `data/raw/peer_panel.csv` | company × quarter: initial guide, first-reported actual, beat, flags, `excluded` + reason (model input) |
| `data/raw/peer_balance_xbrl.csv`, `peer_actuals_xbrl.csv` | first-reported inventory, cost of sales and revenue (SEC XBRL) |
| `data/raw/peer_channel_weeks.csv` | NXP's channel inventory, reported in months until 2024Q3 and in weeks from 2024Q4 (definition break, not bridged) |
| `data/processed/validation_report.md` | coverage, every check, exclusions, overrides |

**Checks** (`src/pipeline_d/validate.py`). All must pass:
- the guide is parsed from ≥ 80% of each company's releases, and the unparsed ones are listed;
- low ≤ mid ≤ high, and mid equals the average of low and high;
- **Microchip chain**: "the midpoint of our guidance provided on ⟨date⟩" equals the guide parsed from the ⟨date⟩ release (17/17);
- **NXP chain**: the prior-quarter channel-weeks column equals the previous release, checked within one definition only;
- every |beat| above 15% is either excluded as a structural break or confirmed by a manual read;
- every actual override's quote is found in that company's release.

**Traps found and handled** (details in `peers.yaml`):
1. A unit typo in a Microchip filing ("$1,240 billion").
2. NXP changed its channel-inventory definition (months → weeks, prior quarter restated).
3. Silicon Labs' 2021 divestiture restated its history → first-reported actuals, and the quarters with mixed bases are excluded.
4. Acquisitions not in the guide (Maxim, Linear, Microsemi, Atmel, SANYO) → excluded.
5. A GAAP one-off at onsemi 2017Q1 → the release's non-GAAP figure, quote-checked.
6. TI's mid-quarter outlook updates → the initial guide is used.
7. Sub-item sentences matched by broad patterns → plausibility band.
8. **The plausibility band itself**: 0.5–2× dropped a real destock guide (Silicon Labs $85m after $204m), so it is 0.25–4×.
9. Microchip's 10-Q misstated a prior-period distributor figure → `pipelines/A_company_financials/config/known_filing_issues.csv`.

## 2008-09 cycle (`src/pipeline_d/history.py`, config `history` in `peers.yaml`)
Releases that guide 2008Q3-2010Q4 (the Microchip distributor-days factor starts in 2008; 2001-02 has neither the factor nor
filed releases). Before XBRL the actual is the release's own figure, accepted only when the narrative sentence equals a
multi-column income-statement revenue row; XBRL first-reported wins where it exists. Releases without a numeric guide
(Microchip 2009Q1-Q2 withdrew guidance; Monolithic Power guided only on the call) are listed, not imputed. Outputs:
`data/raw/peer_history_releases.csv` (every release, both sources), `data/raw/peer_history_panel.csv` (75 guided firm-quarters).
Checks are the `history:` rows in `data/processed/validation_report.md`; used in step 6f.
