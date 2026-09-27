# Step 1 — 10-Q / interim-report confidence level

**Question.** Quarterly reports are unaudited. How far can each company's quarterly figures be trusted, per kind of figure?

**Method — three separate tests, because three different things go wrong** (`src/filing_confidence.py`):

1. `test1_sum4q_vs_fy.csv` — Σ of the four quarterly revenues (hand CSV, original reports) vs the audited full-year figure. SEC filers: the 10-K XBRL annual fact. Nordic: typed in `config/annual_audited.csv` and verified in the annual-report text. GN: the Σ4Q figure is located in the annual-report text. Measures audit true-ups.
2. `test2_restatements.csv` — original segment value vs the same quarter restated in a later report (`config/restatements.csv`); both numbers verified in the cited filings, and whether the model's CSV uses the restated value. Measures taxonomy risk.
3. `test3_adjusted_vs_reported.csv` — reported vs adjusted margins (`config/adjusted_vs_reported.csv` + Logitech GAAP vs non-GAAP GM for every quarter). Measures management-definition room.

**Fold.** `outputs/confidence.csv`: one interval per company × metric class, a grade, and the rule the model follows; `final_confidence.json` and `step1_report.md` carry the final grade per company. Grade of the step itself: **A** — arithmetic on filings, every number verified in the cited filing text.

**Result (2026-09-23).** Totals ≤ 0.02% everywhere — by construction, Q4 absorbs audit true-ups (Nordic and GN Q4 reports are the annual report's first draft; Logitech Q4 = 10-K − 9M). Segment restatements are the real risk: Nordic Industrial & Healthcare ±15%, Consumer ±7% (2025 taxonomy); Logitech Video Collaboration ±26%, Gaming ±8% (FY24 recast); GN Enterprise ±4% (BlueParrott move). Adjusted-vs-reported gaps up to 7.8 pts (Nordic GM, Q2 2024) and 19.3 pts (GN EBITA, Q1 2026); Logitech ≤ 0.5 pt. Final grades: Logitech B, Ingram B, TD Synnex B, Nordic C, GN C — the C is the margin definition room, not the revenue lines.

**Consequence applied to the data.** The test found the Nordic CSV mixing the 2024 original taxonomy with the 2025 one; the 2024 Consumer / Industrial & Healthcare / Other cells were replaced with the restated comparatives from the 2025 reports, so 2025 YoY is like-for-like.

```bash
python steps/step1_filing_confidence/scripts/run.py
```
