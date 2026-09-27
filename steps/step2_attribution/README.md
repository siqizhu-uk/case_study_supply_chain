# Step 2 — Nordic ← Logitech / GN attribution

**Question.** What share of Nordic's revenue is reached through Logitech and GN — and is the OEM tier therefore a *level* driver or a *timing* signal for Nordic?

**Method — five legs, reconciled, never averaged** (`src/attribution.py`; priors in `config/model.yaml` `attribution:`; typed evidence in `config/constraints.csv`, each row quote-checked in the cached filing):

- **A** bottom-up Monte Carlo: units × radios per unit × Nordic socket share × Nordic ASP. Socket share is the widest prior and the only factor public evidence can close: once ≥ 15 FCC grants in Pipeline C's `fcc_logitech_grants_2023_2026.csv` have a SoC marking read, the census (with a Wilson 90% interval) replaces the prior and the grade moves D → B.
- **B** IFRS 8.34: Nordic's AR 2025 discloses that its only ≥ 10% customers are two *distributors* (30% and 12%; three in 2024: 35%, 13%, 10%). So no OEM is ≥ 10% — a hard cap on Logitech if invoiced direct, not binding if Logitech's ODMs or its Suzhou plant buy through ODMs / distributors (≈ 42% of Nordic's revenue flows through two distributors). Logitech's 10-K says Suzhou builds ~35% of output by value, which anchors the direct-share prior (0.15 / 0.35 / 0.5); the output is reported per route: direct / indirect / mixed.
- **C** category view: PC peripherals as a share of Nordic's Consumer end-market (prior).
- **D** proprietary-2.4 GHz floor: Nordic's Proprietary technology line — almost purely PC-peripheral receivers — peaked at $96m TTM (14% of Nordic) in 2022Q2 and halved from 2022Q3, one quarter after Logitech turned negative. A floor for peripherals exposure before the BLE/Bolt migration folded it into Short-range.
- **E** natural experiment: in the 2022–24 destock Nordic consumer fell 41% TTM ($203m) while Logitech's BLE-core categories fell 14% ($399m); with Nordic content ≈ 2% of Logitech's sell-in value, Logitech alone explains ≈ 4% of Nordic's drop.

**FCC census (2026-09-23).** 21 of 101 Logitech grants read from the internal-photo exhibits (evidence PNGs in `pipelines/C_realtime_channel/data/manual/fcc_photos/`, readings in the grant CSV): 16 legible. Peripherals (mice, keyboards, receivers): **11 of 13 Nordic** — nRF52832 / 52833 / 52820 / 52810, including a proprietary-2.4 GHz-only mouse — and 2 Telink TLSR8208 in entry-level SKUs. Audio (headsets, dongles): **0 of 3 Nordic** — Airoha AB1571DN ×2, Realtek RTL8763BFW; consistent with the Jabra teardown (Qualcomm). The census replaces the socket-share prior for peripherals (Wilson 90%: 0.63 / 0.85 / 0.95) and sets headsets to ≈ 0.

**Result.** With the census, Logitech + GN ≈ 17% of Nordic revenue at p50 (13–22%) if invoiced indirectly, capped at 11% if direct; 23–37% of Consumer. Leg A now exceeds the IFRS 8.34 ceiling in 99% of draws: either the radios are invoiced to ODMs / distributors (two distributors take 42% of Nordic's revenue), or the unit / ASP priors are high — the census is a count of designs, not units, and the Telink designs are the high-volume entry SKUs, so the unit-weighted share is likely nearer the Wilson low end (~63%). GN ≈ $8m. **Grade B** (A inputs, observed socket share). **Use in the model:** the OEM tier is a timing / direction signal for Nordic's consumer line, not a level input.

Evidence found online and logged in `config/constraints.csv` (quote-checked; web sources cached, or saved as excerpts under `config/evidence/` where the site blocks scripts): Nordic's own 2005 press release naming Logitech design wins (V200 / V500 on nRF24xx) — Nordic stopped naming customers later, so the absence of recent releases is policy, not absence of the relationship; the Jabra Evolve2 Buds teardown showing Qualcomm QCC5141 in the buds and QCC5126 in the Link 380 dongle, no Nordic part; GN's FCC grantee code BCE, the route to a GN census.

Outputs: `outputs/attribution.json` (all legs, by route), `constraints_used.csv` (evidence + verification), `step2_report.md`, and
**`outputs/attribution_path.csv`** — the attribution as a time path (step 2b, `src/attribution_path.py`).

## Step 2b — the share is time-varying, and the back-test must use the share of *that* quarter

One row per quarter (2022Q1–2026Q2: the first quarter with four quarters of Logitech category sales and Nordic segment data; there is no
earlier public data for either). Three inputs move it, each observed per quarter: Nordic's own TTM revenue (denominator — in the 2022-24
destock Nordic fell ~45% while Logitech's peripherals fell ~15%, so Logitech's share of Nordic *rose* to ~21% at the trough), Logitech's
category mix (pointing / keyboards / gaming carry different wireless weights, `config/model.yaml: radio_content`), and the Nordic socket
share of the design cohort in the market (FCC grants of the last three years, Wilson 90% interval; cohorts before 2023 are extrapolated
from the 2023-24 grants with the prior's low end as the floor — `socket_evidence` says so on every row). The IFRS 8.34 cap is applied with
the year it is evidenced for (`cap_status` found / assumed). The 2022Q3 break (Nordic's proprietary-2.4GHz line halving one quarter after
Logitech turned negative) is the `break_2022Q3` column, with the proprietary line's share of revenue beside it.

Consumers of the path: step 4 (`lags.level_check`: Logitech-implied Nordic dollars at the path's content ratio vs Nordic consumer, by lag),
step 6 (`distributed_lag_regression(driver=time_varying_driver(...))`: Logitech YoY re-weighted by its share of Nordic in that quarter; the
orchestrator keeps whichever of constant / time-varying has the lower leave-one-out RMSE and records both in `regression.json: alternatives`),
step 7 (the regression cross-check uses the regression's own driver). Result on the current data: the time-varying driver lowers the
leave-one-out RMSE from 16.3 to 13.5 pts of Nordic consumer YoY (R² 0.88 → 0.92). Full reasoning and every source: the note "Nordic ← Logitech percentage".

```bash
python steps/step2_attribution/scripts/run.py
```
