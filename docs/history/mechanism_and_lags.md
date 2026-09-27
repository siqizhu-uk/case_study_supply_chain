# Mechanism, lags, attribution, breaks — the decisions behind the model

This is the reasoning the code encodes. Every number quoted here is either in `data/raw/*.csv` (with its filing cited) or in `config/model.yaml` (an assumption you can change).

## 1. Mechanism: who holds the inventory, and how each company shows or hides it

| Tier | What "sales" means | Where inventory sits | Who bears it | What is disclosed | What is hidden |
|---|---|---|---|---|---|
| Amazon / retail | Sell-out to end users | Retailer shelves and Amazon FCs (1P) plus third-party sellers' FBA stock | Retailer (1P) / sellers (3P); Logitech/GN only via returns and price protection | Nothing directly. Logitech says whether sell-through ran above or below sell-in each call (we record the gap in points) | Weeks on hand at retail; promo funding |
| Ingram Micro / TD Synnex | Sell-through to resellers | Distributor balance sheet: INGM ≈ 35–42 inventory days, SNX ≈ 50–70 (inflated by Hyve ODM raw materials) | Distributor, but with vendor price protection and stock rotation rights, so the vendor economically bears part of it | Inventory $ and cash-conversion days quarterly; Endpoint vs Advanced billings growth verbally | Peripherals are ~1–2% of their sales (Logitech ≈ $4.8bn × 14% ÷ INGM $52bn). Their inventory says how willing the channel is to hold stock, not how mice are selling |
| Logitech | Sell-in to distributors/retailers (Ingram 14%, Amazon 18%, TD Synnex 12% of FY26 sales) | Own inventory ($492m, 66–75 days) + "weeks on hand" in the channel | Logitech owns its inventory; channel inventory is the customer's on paper but Logitech manages it to a target range (never quantified) and funds promotions to clear it | Inventory $, verbal sell-through vs sell-in gap, verbal "within targeted range" | Actual channel weeks; sell-through by region beyond growth rates |
| GN (Enterprise + SteelSeries) | Sell-in to distributors/resellers | Own inventory (DKK 1.8bn continuing ops); channel inventory at distributors | GN; Enterprise sell-out reported only when it diverges from sell-in (Q3'24 −3 vs −7, Q1'25 −5 vs −9, Q2'26 flat vs −7) — coded as `enterprise_sellout_minus_sellin_pts` with an estimate flag | Inventory $, divisional revenue/organic growth, occasional sell-out | Channel weeks; SteelSeries channel not discussed |
| Nordic | Sell-in to distributors (~40% of revenue, Arrow/Avnet/Future/Digi-Key/Mouser) and to OEM/ODM/EMS (~60%) | Own inventory ($217m, ~190 days, deliberate nRF54 wafer build); distributor inventory; ODM/EMS inventory of finished radios | Nordic owns its build; distributors own theirs (with ship-and-debit); ODMs hold component kits against OEM forecasts | Revenue by end market/technology; own inventory; verbal distributor-inventory state; top-10 customer share (~54–58%); no customer >10% | Backlog (dropped as an APM in Q2 2023 because it "has not been a good demand indicator"); distributor inventory in $ or weeks; ODM inventory entirely |

Two consequences drive the model:

1. **Nordic is three inventory buffers away from the end user** (retail → distributor/OEM channel → ODM kit). Each buffer adds delay and amplifies: a 5% sell-out miss becomes a 10–15% reorder cut once every tier trims its own weeks-on-hand. In 2022–24 Logitech BLE categories fell 17% at trough; Nordic Consumer fell 43% on YoY terms, and the broad-market (distribution) part of Nordic's Bluetooth revenue fell 46% in 2023 while its top-10 customers were flat.
2. **Nordic's own revenue is sell-in, and Nordic's distributors are the one tier that is disclosed only verbally.** The verbal state is therefore a variable in the model (`dist_inventory_state` = +1 restock / 0 normal / −1 destock), not decoration.

## 2. Lag structure — reasoning before regression

Weeks from a change in Amazon sell-out to a change in Nordic's revenue, normal channel (`config/model.yaml: lag_weeks`):

| Step | Low | Mid | High | Why |
|---|---|---|---|---|
| Sell-out → distributor/retailer reorder | 2 | 3 | 4 | Retailers replenish weekly against 2–6 week cover targets; Amazon's algorithmic reorder is faster than Best Buy's |
| Distributor → OEM sell-in | 3 | 4 | 6 | Logitech gets sell-through data weekly from retailers ("a majority of our retail sales"), manages weeks-on-hand, and adjusts shipments within the quarter |
| OEM sell-in → ODM/EMS build plan | 6 | 8 | 12 | Monthly S&OP; Logitech's own ~10 weeks of inventory cushions the ODM build before it is cut |
| ODM component order → Nordic revenue | 4 | 7 | 10 | Nordic standard lead time 12–16 weeks (Future/Avnet quote 16 weeks on nRF54L15 today), but ODMs draw much of it from distributor stock at 0–2 weeks; blended |
| **Total** | **15** | **22** | **32** | **≈ 1.2 / 1.7 / 2.5 quarters** |

Empirical checks (the model prints all of these):

- Cross-correlation of Nordic Consumer YoY with Logitech BLE-category YoY peaks at **lag 2–3 quarters (ρ = 0.86 / 0.85; ρ = 0.38 at lag 0)**. Inside the normal regime alone the contemporaneous correlation is *negative* (−0.68): when Logitech's growth is strong today, Nordic's growth was booked two quarters ago.
- Turning points: Logitech BLE categories returned to positive YoY in **2023Q4**; Nordic Consumer in **2024Q3** (3 quarters). Logitech sales turned negative in **2022Q1**; Nordic total revenue in **2023Q1** (4 quarters) — the long lag on the way down is the backlog regime (below).
- Ridge distributed-lag regression on lags 1–3 (n = 14): effects +1.2 / +0.7 / +1.8 pts of Nordic Consumer YoY per point of Logitech BLE YoY, **sum ≈ 3.7×** — the bullwhip in one number. In-sample R² 0.86, leave-one-out RMSE 18.7 points. That RMSE is the honest one: quarterly YoY at the component tier is too noisy to forecast a single quarter from the OEM tier alone. The regression is a check on the lag and the amplification, not the forecast engine.

## 3. Regimes and structural breaks (past four years)

| Break | Dates | What it does to the relationship | How the model handles it |
|---|---|---|---|
| Component shortage / backlog | 2021Q1–2022Q2 | Nordic revenue = supply, not demand ("capped by wafers"); backlog $1.7bn masked the demand turn for ~4 quarters; sell-in > sell-out at every tier | Regime flag `supply_constrained`; lag multiplier 2×; these quarters excluded from the guidance-bias anchor |
| Bullwhip unwind | 2022Q3–2024Q1 | Distributor and end-customer destock; Nordic broad-market −46%; Nordic *missed* its own midpoint by 4.7% on average (−13% in 2023Q3) | Regime `destock`; `dist_inventory_state = −1`; separate guidance-bias statistics |
| Nordic taxonomy changes | 2022Q1, 2025Q1 | End-market and technology buckets redefined; share bikes moved Industrial→Consumer | Restated comparatives used where published; both taxonomies kept in the raw file |
| Nordic one-offs | 2024Q2 (nRF9160 write-down), 2025Q4 (GM one-off) | Reported GM 42.0% / 54.9% vs 49.8% / 52.0% adjusted | Adjusted GM used (switchable) |
| Logitech taxonomy | FY24 (recast FY23) | Headsets, Video Collaboration, Other redefined | Two radio series from `config/model.yaml: radio_content`: **core** = Pointing + Keyboards + Gaming + Tablet (present in both taxonomies, weighted by radio content, YoY from 2021Q2 — the regression driver) and **all** = every line weighted (headsets 0.8, video collaboration 0.3, webcams 0.05, other 0.3; from 2022Q2) |
| Tariffs / price / pull-forward | 2025Q1–2026Q2 | Pre-tariff inventory build (Q4 FY25), ~10% US list price increase (Apr 2025), out-of-stocks during negotiations, IEEPA tariffs struck down Feb 2026, $61m refund in Q1 FY27 GM | Q1 FY27 GM adjusted −5.0pts; sell-through-gap series carries the unit signal |
| Logitech supplier incident | Late June 2026 | Unnamed semiconductor supplier facility; ≈$20m Q2 FY27 and up to $200m Q3 FY27 sales hit in gaming and mice/keyboards | Explicit negative adjustment to Nordic Q3 (attach loss on cancelled ODM builds) and included in Logitech's guide |
| GN: SteelSeries consolidated | 12 Jan 2022 | Audio revenue +30% inorganic | `gn_periph` = Enterprise + SteelSeries/Gaming (PC/office peripherals); `gn_radio_all` = every BLE-bearing division weighted (Enterprise 0.9, Gaming 0.8, Consumer 1.0 while it existed, Hearing 0.5 = Nordic content unknown) |
| GN: OneGN divisions, BlueParrott move, Consumer wind-down | 2024Q1, 2025Q1, Jun 2024–Dec 2024 | Restated Enterprise; Gaming division absorbs residual Consumer; organic growth quoted "ex wind-down" | Gaming division used from 2024 (it is the continuing series); Consumer excluded |
| TD Synnex + Tech Data merger | 2021Q4 (closed 1 Sep 2021) | Revenue ~3× from FQ4 FY21; pre-merger rows are SYNNEX standalone | YoY masked 2021Q4–2022Q3 (`tdsynnex_techdata_merger_2021`) |
| GN: Hearing discontinued | 2026Q1 | "GN Audio" no longer reported; continuing operations = Enterprise + Gaming with stranded costs | Forecast target defined as continuing operations (that is what GN now reports); Hearing revenue is still disclosed as discontinued ops and is kept as `gn_hearing_dkk`, with 2026 group revenue = continuing + Hearing. Hearing aids are BLE devices too; whether ReSound uses Nordic silicon is not public, so Hearing is in the data but not in the peripherals proxy |
| Distributor ASP inflation | 2026Q1– | Memory-driven ASPs add 2–3 pts to INGM/SNX dollar growth | Endpoint unit growth = dollar growth − 2.5 pts |

## 4. Attribution: how much of Nordic runs through Logitech and GN

Bottom-up chain (all inputs in `config/model.yaml: attribution`, Monte Carlo with triangular priors):

Logitech: BLE-relevant sales $4.0bn TTM ÷ sell-in ASP ~$38 → ~105m units × 70% wireless × 1.4 radios per wireless unit (device SoC plus a receiver dongle on roughly half) → ~100m radio sockets × Nordic share 30–60% × Nordic ASP $1.3–2.4 at volume → **$62–110m, median $83m**. GN: SteelSeries ~8m units × 50% wireless × 50% Nordic share × $2 plus a small Enterprise dongle/side-channel slice → **$6–10m**.

The cap: Nordic's audited 2025 annual report contains no IFRS 8.34 major-customer disclosure (required for any single customer ≥10% of revenue) and reports only the top-10 aggregate (57%). We read that as *no invoiced customer ≥10%* (≈ $76m TTM) — an implication from a required disclosure being absent, not a statement, so we treat the cap as soft. 65% of the Monte-Carlo draws breach it. Three readings are consistent with the disclosure and none has direct evidence, so we do not pick one: (i) Nordic's socket share at Logitech is nearer 30% than 60% (testable by FCC sampling); (ii) part of Logitech's purchases are invoiced to ODMs (Chicony, Primax, Sunrex) or distributors, so no single invoiced customer carries Logitech's full weight — but Logitech's 10-K says its own Suzhou plant builds ~35% of product by value, and an owned plant buys components in Logitech's name, so at least part of the flow is plausibly direct; the invoicing route is unknown; (iii) other Leg-A factors (wireless share, radios per unit, ASP) are too high. The honest output is conditional: **if Logitech is invoiced directly, IFRS 8 caps it at ≤10% (≤$76m); if via ODMs the cap does not apply and the uncapped range $62–110m (8–14%) stands.** Either way Logitech + GN are **9–15% of Nordic total (15–25% of Consumer)** — a minority, which is the conclusion that matters. The model reports both capped and uncapped figures.

Category-level view, which is what actually matters for reading Logitech as a signal: PC peripherals and gaming as a category are 20–40% of Nordic Consumer (median 30% ≈ 18% of total). Logitech has ~35–40% share of mice/keyboards, so Logitech's sell-through is a good proxy for the category even where Nordic's chip goes into a Logitech competitor. That is why the model uses Logitech's BLE categories as the driver, not an estimate of Logitech's own purchases.

## 5. What we chose not to build

- **Amazon / Idealo / Geizhals scraping.** Blocked for automated fetch (403/PerimeterX) and against Amazon's terms; a Keepa API subscription would give BSR/price history in an afternoon and is the first thing to add with a budget. Stub: `sellout_proxy_yoy` is Logitech's own disclosed sell-through gap.
- **Digi-Key / Mouser live scrape.** Both block bots; we use a findchips.com snapshot (aggregates their feeds) saved to `data/raw/nordic_channel_snapshot.csv`. A weekly cron of the same page would give the time series the case asks for.
- **SEC XBRL ingestion as the primary source.** Nordic and GN are not SEC filers; XBRL quarterly frames need fiscal-period de-duplication. We typed the numbers from filings with a citation per row and reconcile them against XBRL mechanically (`pipelines/A_company_financials/scripts/validate.py`).
- **VAR / state-space / Bayesian hierarchical model.** With 14–18 usable quarters and two regime breaks, anything beyond a 3-lag ridge regression would be fitting noise. The forecast engine is instead guidance × regime-conditioned beat + named adjustments, which a non-coder can audit line by line.
- **FX modelling for GN.** One fixed FX assumption (−1.5 pts, from the Q2 2026 reported-minus-organic gap).
- **Deliberate stop:** no attempt to estimate channel weeks-on-hand in numbers for Logitech or GN. Neither discloses it; any figure would be invented.

## 6. Where the model works and where it does not

Works: (a) the sign and timing of Nordic's cycle relative to Logitech — 2–3 quarter lag, ~3.7× amplification — is robust across the correlation, turning-point and regression checks; (b) the regime-conditioned guidance bias is a strong, simple anchor (Nordic has beaten its midpoint in 8 of the last 9 quarters by 3.5% on average, and missed by 4.7% on average during the destock); (c) inventory-days at each tier flag where the next surprise will come from.

Does not: (a) single-quarter Nordic revenue from the OEM tier alone (LOO RMSE ≈ 19 pts of YoY); (b) the ~40% of Nordic that is Industrial/Healthcare and the ~70% of Consumer that is not PC peripherals (wearables, trackers, toys, share bikes) are outside this chain; (c) Nordic's distributor inventory is known only verbally, so a Q3 beat borrowed from Q4 via pull-ins cannot be distinguished from real demand until Q4 guidance; (d) GN Enterprise is a B2B refresh cycle (Teams/Zoom rooms, headset fleets) with little BLE-SoC content, so the GN leg informs GN's own print but says little about Nordic; (e) distributor aggregates are PC-dominated and ASP-inflated in 2026 — useful for channel posture, useless for peripherals demand.
