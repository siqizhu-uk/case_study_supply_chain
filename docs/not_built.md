# What we chose not to build

One place for every build-or-buy decision. Per-source detail (URL, grade, validation, status) is in each pipeline's
`config/data_config.csv`; per-method decisions are in each step's `config/decisions.csv`.

## 1. Used existing APIs, datasets and libraries instead of writing our own

| Need | What we used | Instead of |
|---|---|---|
| US company financials (Logitech, TD Synnex, Ingram, Microchip, Arrow, Avnet, 12 semiconductor peers) | SEC EDGAR APIs: XBRL company facts (first-reported values), submissions, filing archives | parsing 10-Q HTML tables |
| Nordic and GN filings | Oslo Børs NewsWeb API; company quarterly-report PDFs read with `pdfplumber` | a PDF-table extractor |
| Macro and industry context (Pipeline B) | FRED, US Census, WSTS / SIA releases | building our own demand index |
| Component-channel stock | findchips.com (Supplyframe's distributor aggregator); Mouser's official Search API when a key is set | scraping Digi-Key / Mouser directly |
| Which SoC is inside a product | FCC internal photos (fccid.io exhibits), iFixit API | buying and tearing down devices |
| Statistics, figures, documents | pandas, numpy, scipy, matplotlib, python-docx | anything custom; no database, no scheduler, no ML framework |

## 2. Sell-out and discounting proxies the brief suggested — not built

| Proxy | Why not | What stands in for it |
|---|---|---|
| Amazon Best Sellers Rank (US / UK / DE basket) | free data only, so Keepa (paid) is excluded; the free route was tested: Internet Archive copies of product pages carry the rank in 2 of 14 monthly captures of the best-archived SKU, the US mouse best-seller list is archived in 9 of 22 quarters, UK / DE lists not usable | Logitech's own disclosed sell-through vs sell-in gap: sell-out YoY ≈ sell-in YoY + gap |
| Amazon price and promotion history | too noisy to process in the time available (list vs deal vs coupon prices, third-party sellers, regional variants) | promotion commentary in Logitech's and GN's calls (quote-checked) |
| Idealo / Geizhals street prices and merchant counts | 403 to scripts; no downloadable history, so it could never be back-tested | promotion commentary in Logitech's and GN's calls (quote-checked) |
| logitech.com / jabra.com promotion pages | reachable, but prices render client-side with no reliable "was" price; low value next to the call commentary | as above |
| Digi-Key / Mouser stock and lead times on nRF52 / nRF54 | direct fetch returns 403; there is no public history, so a snapshot cannot enter a regression | a dated snapshot series via findchips (Pipeline C), shown as a watch indicator only |
| GN sell-out (distributors' point-of-sale by vendor from Context / GfK / Circana; Amazon rank for SteelSeries) | paid data (free-only rule), and GN's channel is mostly invisible anyway: ~35% through IT distributors, which do not report by vendor, ~10% Amazon (capped at 17.5% by GN's filing), ~55% other resellers and retail (graph edges E19-E22). With 5 August guides the gain could not be back-tested. Expected value is modest: Logitech's own disclosed sell-through gap, the same kind of data, earns only an inverse-MSE weight of 0.23 against its guide (chain RMSE 23m vs guide 13m on the same 5 quarters, step 7c), shown as a diagnostic; the forecast uses the guide method (weight 0, F29), and on 12 peers the channel adds +1.7% out-of-sample R-squared beyond the guided quarter (K4). It would matter most for GN: the guide is annual (set in August), so Aug-Oct sell-out is news the guide does not hold, and it would show whether the 8-quarter Enterprise distributor drain has ended, which GN's 'positive H2 organic' needs | GN's own record on its August guides (F17); the Enterprise distributor-drain index (step 3, verbal) in the division-view scenario |

Deciding factor for all of them: none has public history, so none could be tested in the walk-forward back-test, and step 6
shows that even the channel signals we *can* test add little to a guided quarter. They are monitoring tools, not model
inputs. Digi-Key / Mouser is kept as a live gauge read on demand (dashboard tab 1), not as a series.

Also rejected: IPC supply-chain sentiment (report behind a form), Norwegian / Eurostat export statistics (Nordic is
fabless — its chips never cross Norwegian customs), sell-side research (paywalled; nothing citable in public).

## 3. Where we deliberately stopped

- **FCC photo census:** 38 of 81 public Logitech grants read, enough to bound Nordic's socket share (23 Nordic / 5 Telink / 2 other among legible peripherals); the rest would narrow a range that is dominated by the unknown invoicing route anyway.
- **Transcripts:** verbal data points are hand-quoted and quote-checked (41 of 41), not mined with NLP.
- **Factor search:** stopped after about a dozen candidates on Nordic's ~4 independent observations (step 6 decision B40); new factors should be tested on the peer panel first.
- **The peer panel went further than the case needed.** Twelve semiconductor peers' guidance back to 2008 (Pipeline D) was built to test whether Nordic's channel sensitivity generalises. It answered that (it does not) and gave the "beat = forecast error" finding, but it is a guidance-error study, not part of the Nordic ← Logitech / GN ← channel chain. It is supporting evidence for the limitations, and two forecast inputs are estimated on it: Logitech's pooled habit and the building-state effect (−1.64, t −4.4; F16). Nordic and GN use their own records (F20, F23).
- **ODM production lead:** one quick test (Taiwan ODMs' free monthly revenue vs Logitech; step 5c) and stopped: identity only from customs records, diluted proxies, Merry (acoustics) tracks Logitech specifically (0.74 at a 2-month lead) but ~20 quarters cannot pin the lead month; not a forecast input.
- **Data-driven regime call (built; now inside the forecast):** step 3b (`cycle_state.py`, D22) dates the channel cycle from Microchip's distributor days 2007–26, point in time; the guide-error model (F16) uses its *building* state as the channel term. In real time it flags building for the 2023Q1 guide, one quarter after Nordic's first miss (2022Q4). Not built: a finer state model (four states, or a Markov-switching model) - two turns in Nordic's own sample and one revision of the rule after seeing the data (disclosed in D22) are already the limit of what the history can support.
- **GN chip census:** not done. GN's FCC grantee code (BCE) is logged, but a census would only confirm whether Nordic is inside GN's products at all (the one teardown found, Jabra Evolve2 Buds, uses Qualcomm). GN is ~$8m a year of Nordic (p10-p90 $6-10m, ~1.8% of Nordic Consumer), so the result could move Nordic's attribution by at most ~1 pt and would not help the GN forecast: GN's orders are too small to be seen in Nordic's revenue (about $2m a quarter against Nordic's ~$9m guide-error sd), so the chain carries no information about GN in either direction.
- **State-dependent chain amplitude (considered, not built):** the reasoned chain (CH) scales end demand into Nordic's slice with one multiplier (1.09); at h = 2 its encompassing slope is ~3.2, i.e. Nordic swings ~3x what CH implies, so a multiplier that rises when distributors build or destock (step 3's destock amplitude ~2.6) and a doubled lag in the supply-constrained regime are the natural next step. Not built: there is one destock in the sample, so the state-dependent multiplier would be estimated on the episode it is scored on; CH carries no weight in any forecast (guided quarters weight 0, Q4 uses GRi, F26); the channel is lean now, where m stays ~1.1, so no live number would move. Route-level CH (step 5e, G26) was tested and adds nothing, so any gain would have to come from m and the regime lag.
- **Forecast horizon stops at h = 2, because there is no free end-demand pipeline.** The graph turns known demand into Nordic's timing: end demand reaches Nordic's revenue ~17 weeks later (goods) or ~24 weeks (order signal, G25). At h = 1 (Q3) every demand quarter the kernel needs is reported; at h = 2 (Q4) the latest one is not and is filled by our bias-corrected Logitech sell-in forecast (GRi, the point, F26), by persistence (GR, a challenger) or by Logitech's own guide (GRg, a sensitivity only); from h = 3 both are in the future, so the graph can only translate an end-demand forecast made elsewhere (seasonality, macro, product cycles). Weekly sell-out data (Amazon rank / price, retail point-of-sale) would observe the unreported quarter and reach ~24 weeks ahead: h = 2 on data and part of h = 3, not beyond. It is not free (Keepa and point-of-sale panels are paid; archived Amazon pages carry the rank in 2 of 14 captures, see section 2), and the free proxies tried as a nowcast of the unreported quarter did not beat persistence (step 5f, G27); Logitech's own disclosed sell-through, the same kind of signal, earns an inverse-MSE weight of only 0.23 against its guide and is not used (F29, step 7c). So the gain is timeliness, and its size is unproven on this sample.
- **Not modelled:** Nordic Industrial & Healthcare (~40% of revenue), GN Hearing (discontinued), daily or weekly scrapers.
