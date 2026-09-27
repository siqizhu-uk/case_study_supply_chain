# Step 3 — Inventory mechanism (bullwhip)

**Question.** Where does inventory sit between end demand and Nordic's revenue, who holds it, how much does each link
amplify, and what does the channel position say about the next three prints (Nordic 22 Oct, Logitech ~27 Oct, GN 5 Nov)?

**Answer in one paragraph** (numbers regenerate in `outputs/step3_report.md`). Logitech's retail/distribution channel
does not amplify (variance ratio ≈ 1). Logitech's own purchases amplify ~1.5× its sell-in. Nordic's consumer revenue
moves ~1.9× Logitech's end demand two quarters later. That elasticity is the only amplification term the data identify.
The textbook inventory terms (accelerator, stock-gap correction) are tested at every tier and are either zero or not
identified with 16 quarters, so inventory enters the forecast as **state**, not as a coefficient. The 2023 destock was a
broad-market event: Nordic's top-10 Bluetooth customers were −3% while the broad market was −46%. So the whole-company
amplitude must not be applied to the Logitech slice. Going into Q3 2026:
- **Logitech's channel is lean**, 1–2 weeks below target.
- **GN's distributors have drained for eight quarters.**
- **Nordic's component distribution channel is lean but restocking**, with receivables growing twice as fast as revenue (watch flag).

## Run

```bash
python steps/step3_inventory_mechanism/scripts/run.py      # this step only (~3 s); also runs inside scripts/run_all.py
python pipelines/A_company_financials/scripts/validate.py  # re-validates every input this step reads (check 5 + section 7 of the report)
pytest -q tests/test_step3.py                              # 13 tests: formulas on toy data with known answers, parsers, full step
```

## Folder

| path | what |
|---|---|
| `config/decisions.csv` | **every judgment call (D1–D21)**: decision, alternatives considered, reason, evidence, effect |
| `config/anchors.csv` | the five Logitech "channel at target" statements that pin the channel level; quotes checked at run time |
| `config/model.yaml` → `inventory_mechanism` | every numeric assumption (priors, ranges, bootstrap settings), with the decision id |
| `src/inventory_factors.py` | 3a: DIO, forward DIO, inventory–sales and stage spreads, FG share / weeks, DSO, purchases, distributor days |
| `src/channel_index.py` | 3b: channel-inventory index from the sell-through minus sell-in gap (exact recursion + anchors) |
| `src/bullwhip.py` | 3c: variance ratios link by link (block bootstrap); top-10 vs broad market; Logitech / GN slice multiplier |
| `src/amplification.py` | 3d: the ordering-rule regression (pass-through / accelerator / stock gap) and the reduced form kept |
| `src/channel_call.py` | 3e: state, direction, adjustment range and questions for each print |
| `src/step3.py`, `src/step3_report.py` | orchestrator; writes `outputs/` |
| `outputs/step3_report.md` | the write-up: the call, formulas, data checks, results, decisions |
| `outputs/*.csv, *.png, step3_summary.json` | every table and figure the report cites |

## Inputs and how each was validated

Everything is read by script from a primary filing, or hand-typed with a verbatim fragment that is searched in the
cited document. Sources are rows in `pipelines/A_company_financials/config/data_config.csv`, all `validated = yes`
except Silicon Labs, which is logged as `rejected` with the reason.

| input (Pipeline A `data/raw/`) | source | check |
|---|---|---|
| `inventory_detail_xbrl.csv`: Logitech raw materials / finished goods / receivables; Arrow and Avnet revenue, COGS, inventory, receivables | SEC XBRL company facts | RM + FG = total inventory; Logitech total = hand-typed; Arrow / Avnet margins 10–13% every quarter |
| `mchp_distributor_days.csv`: Microchip "our distributors maintained NN days" + 10-year range | 25 Microchip 10-Q/10-K | verbatim quote per row; 21/21 "compared to MM days at <date>" equal the filing for that date |
| `nordic_balance_extract.csv`: Nordic receivables and inventory per quarter | 23 cached NewsWeb reports | 28/28 year-ago columns equal the report four quarters earlier; inventory = hand-typed (max 0.08%) |
| `nordic_inventory_stage.csv`: Nordic raw materials (wafers) / WIP / finished goods | AR2021–AR2025 notes | stages sum to reported inventory; prior-year columns chain |
| `nordic_customer_concentration.csv`: top-10 vs broad-market Bluetooth revenue | Q4 2022 / 2023 / 2024 reports | 7/7 rows' fragments found in the cited report; 276 + 208 = 2023 short-range revenue |
| `verbal_metrics.csv` (existing): Logitech / GN gaps, Nordic distributor state | calls and reports | Pipeline A grade-C check (41/41) |

## Formulas

**Inventory factors**

- DIO = inventory / quarterly COGS × 91.25.
- Forward DIO = inventory / guided next-quarter COGS × 91.25.
- Spread = YoY%(inventory or stage) − YoY%(revenue) (Bernard & Noel 1991; Thomas & Zhang 2002). Finished goods outgrowing sales signals a demand shortfall; raw materials / WIP outgrowing sales signals a planned build.
- DSO = receivables / revenue × 91.25.
- Purchases = COGS + Δinventory. This is the order signal the next tier sees.

**Channel index.** The flow identity is I_t − I_{t−1} = S_t − T_t = F_t (channel stock, sell-in, sell-through, net fill). The companies disclose gap = g_out − g_in, which gives exactly

    F_t = F_{t−4}·(1 + g_out) − gap_t · S_{t−4}

The naive −gap·S_{t−4} books the lapping of last year's drain as a build (D5). The level is pinned by management's "at target" statements, and their spread is the error bar (D7, D21).

**Bullwhip.** VR = Var(orders upstream) / Var(demand received), on YoY growth, with a moving-block bootstrap 90% interval, link by link (D14).

**Regression intuition** (Sterman 1989 anchoring-and-adjustment; Metzler 1941 / Blinder & Maccini 1991 stock adjustment). A tier orders

    O_t = E[D_t] + (I*_t − I*_{t−1}) + α·(I*_t − I_t),   I* = c × trailing-12-month demand

In YoY growth this becomes

    g^O_t ≈ g_t + c·(g_t − g_{t−4}) − α'·gap_t

- **Pass-through:** orders grow with demand.
- **Accelerator:** orders lead demand, and c × 52 = weeks of cover. The prior is measured from the balance sheets before fitting (D10).
- **Stock-gap correction:** orders lag demand, with distributor days as the proxy.

Each tier is estimated as y = a + b·g_{t−L} [+ c·(g_{t−L} − g_{t−L−4})] [+ γ·gap], using OLS, Newey–West standard errors, a block bootstrap and leave-one-out RMSE. A term is kept only if it is identified and lowers the leave-one-out error (D11).

**Channel call.**
- Logitech refill = deficit weeks × guided weekly sell-in × refill share × supply availability.
- Nordic safety stock = extra distributor weeks × guided weekly revenue × distribution share.
- GN Enterprise organic = sell-out growth − gap.

Each input is a {low, mid, high} in config. The results are cross-checks next to the forecast lines and do not overwrite them (D15).

## Known gaps (stated, not hidden)

- **Channel weeks-on-hand are never disclosed in numbers** for Logitech, GN or Nordic. The level rests on management's statements (Logitech) or is only relative (GN, grade D). Microchip is the only company in reach that publishes distributor days.
- **Nordic's 2026 inventory build ($155m → $217m) has no stage split** until the 2026 annual report (D3).
- **Logitech's slice of Nordic revenue is bounded, not measured.** The multiplier range is 0.27–1.24×; within that the data cannot distinguish "other top-10 customers grew" from "Logitech's radio buying held up".
- **Sixteen quarters and one cycle.** The lag and the accelerator cannot be separated at the Nordic tier. The reduced form's leave-one-out RMSE is ~27 pts, so it is a sanity check, not a forecast.
