# Model report — generated 2026-09-22

> ### 💡 Key insights (computed from the data)
>
> **K1. The beat is management's forecast error, not demand.** Across 632 peer quarters revenue YoY has sd 29% but the beat only 3.9% (correlation 0.23). In the 20 quarters where a peer's revenue fell 30% or more YoY the mean beat was -0.2% and 95% stayed within +/-5%: management writes the cycle into the guide. *So what:* A factor can predict the beat only if management ignored public information; channel signals can at most help the revenue forecast beyond the guided quarter (K4).
>
> **K2. Nordic's 2023Q3 miss was not set up by a guide more optimistic than the peers'.** For 2023Q3 Nordic guided +0.5% q/q against a peer median of +0.4% (relative optimism +0.1 pts), then missed by 12.9%: the shortfall arose inside the quarter. Against the consumer-heavy peers only (exploratory, chosen after seeing the data) the gap was +18.8 pts. *So what:* Which comparator is 'the market' decides the reading; the pre-registered peer median does not flag the episode.
>
> **K3. No guide-setting factor predicts misses.** Relative guidance optimism on 671 peer firm-quarters (70 quarters): +0.005 per pt (t 0.3); walk-forward OOS R2 -0.005 vs each firm's mean; the most optimistic fifth of guides misses in 15% of quarters, the least optimistic in 24%. On Nordic without 2023Q3, 2023Q4: last_beat keep |t| >= 2; the channel factor keeps +0.86 (t 0.7, naive). *So what:* The large Nordic misses are rare intra-quarter surprises; about a dozen candidate factors have now been tried on 21 quarters, so any one that 'works' on Nordic alone is expected by chance.
>
> **K4. Beyond the guided quarter the channel factor adds little to revenue forecasts.** Forecasting revenue one quarter past the guide (g2 = actual t+1 / guide t) on 479 peer firm-quarters: seasonal benchmark + channel factor gives OOS R2 +1.6% vs the seasonal benchmark alone (t 1.4; RMSE 10.55 with the channel vs 10.64 seasonal vs 11.54 flat, pts); 102% of the gain comes from 2023Q3, 2023Q4, 2025Q4; without 2023Q3, 2023Q4 +0.3%. *So what:* Where the channel belongs (revenue beyond the guide, not the beat) is consistent with (not confirmed by) the data: its value there is small and turn-dependent: seasonality does more than the channel.


> ### ⚠ Risks the tests cannot rule out (R1-R6 the composite channel factor, a pre-registered challenger; R7-R8 Nordic's own guide-error record, F32)
>
> **R1. Against the 4-quarter benchmark the gain comes from one cycle turn.** (a) vs the past-4-quarter beat (the gate's benchmark): the three best quarters (2024Q4, 2024Q2, 2024Q3) carry 111% of the gain — above 100% because the other quarters together lose; the composite wins 7 of 11 quarters; over the last six quarters the composite is WORSE (RMSE 1.71 vs 1.67 pts). (b) vs the intercept-only model (mean of all past beats, no factors): the three best quarters (2023Q4, 2024Q4, 2025Q2) carry 106% of the gain — above 100% because the other quarters together lose; the composite wins 7 of 11 quarters (out-of-sample R² +0.46; last six quarters 1.71 vs 3.98). Reading: the composite wins more quarters against the intercept-only model (7 vs 7 of 11) and its top-3 share is lower (106% vs 111%), but against both baselines three quarters still carry most of the gain — the concentration is only partly an artefact of the slow 4-quarter benchmark. Either way the sample holds one cycle.
>
> **R2. Factors chosen after seeing the data.** The four factors were chosen after step 3 had already shown the 2021-2026 data (researcher degrees of freedom). No back-test removes this. The only clean test: Nordic Q3 2026 print, 22 Oct 2026 (pre-registered in steps/step6_backtest/outputs/composite_prereg_log.csv; the last row logged before the print is the forecast of record) — none scored yet.
>
> **R3. The composite and its ridge variant disagree on this quarter.** 2026Q3: composite (equal weights) beat +3.39% vs ridge challenger +1.69% (+1.71 pts = USD 3.9m on the USD 230m midpoint). Which specification is right is unknown until the print.
>
> **R4. Very few independent observations.** The composite has 20 quarterly values but lag-1 autocorrelation 0.75, so it holds about 2.8 independent observations (Bartlett n(1-ρ)/(1+ρ)); the beat itself holds about 8.0 of 19. Every cycle-dependent conclusion rests on roughly one downturn and one upturn; each extra fitted parameter (absolute value, separate +/- slopes, regime switches) would be fitted to those. More independent evidence has to come from more cycles or more companies (peer panel), not from the model's form.
>
> **R5. The channel mechanism itself fails external validation on 12 peers.** Pooled over 442 peer firm-quarters and several cycles, the same channel factors do not beat each firm's own mean beat out of sample (OOS R² -0.009, better in 52% of quarters). On the industry factor Nordic's slope is +2.99 pts per sd vs +0.39 for the peers. A Nordic-like peer set (11 firms, distribution share >= 35%) predicts Nordic's slope from its distribution share at +0.16 (90% PI -0.28 to +0.61); distribution share itself explains nothing (t = 0.2). The composite's Nordic result is most likely specific to one cycle of one company.
>
> **R6. The channel mechanism rests on one cycle turn, for Nordic and for the peers.** Peers' slope by window: 2008-10 -0.22, 2011-19 +0.19, Nordic's window +0.59 (se 0.92). Three quarters carry 92% of the peers' and 82% of Nordic's slope; 2023Q3, 2023Q4 are in both. Nordic vs peers in the same window: t = 0.9 after autocorrelation.
>
> **R7. The channel state cannot see an end-demand shock.** Nordic's record runs 2019Q1-2026Q2 (30 guides, F32). Of the 15 quarters that set the habit (channel neither building nor short), 2020Q2, 2020Q3 had the guide raised before the print: errors +10.6, +19.4 against the guide the model scores, +1.7, +3.8 against the last guide, with the state reading 'lean, normal'. The state variable is a channel stock (distributor days); it explains misses when distributors build (2023) and is blind to a demand shock (2020). Habit +5.23% with those quarters, +3.72% without (n 13); before 2021 +6.10% (n 8), from 2021 +4.24% (n 7). The rule is kept as pre-stated (F33); the shock sits in the range, not in a new term.
>
> **R8. The state split has no walk-forward edge on the longer record.** Walk-forward over 14 quarters from 2023Q1: rule in force 5.54 pts, guide midpoint (zero error) 5.55, past-4-quarter beat 5.41, pooled with the peers 5.06 (F16 challenger). The habit's sign replicates out of sample (Nordic guided below the outcome in 8 of the 9 quarters 2019Q1-2021Q1), the claim that splitting it by channel state improves the forecast does not; the split is kept for its mechanism (F20, F30), and every challenger is scored at the print.

## 1. Reasoned lag (before any regression)

End-to-end sell-out → Nordic revenue: **15 / 22 / 32 weeks** (≈ 1.15 / 1.69 / 2.46 quarters) under a normal channel. Components (weeks): sell_out_to_distributor=3, distributor_to_oem=4, oem_to_odm_build=8, odm_to_component=7.

## 2. Empirical checks

Timing of Nordic consumer YoY vs Logitech sell-in YoY lagged k quarters - the downstream / industry cycle, not the chain lag (step 4 decision L2; common-cycle controls give the same timing, step 5 G21):

|   lag_q |   corr |   n | regime   |
|--------:|-------:|----:|:---------|
|       0 |   0.41 |  17 | all      |
|       1 |   0.78 |  16 | all      |
|       2 |   0.9  |  15 | all      |
|       3 |   0.84 |  14 | all      |
|       4 |   0.59 |  13 | all      |

|   lag_q |   corr |   n | regime             |
|--------:|-------:|----:|:-------------------|
|       0 | nan    |   1 | supply_constrained |
|       1 | nan    |   0 | supply_constrained |
|       2 | nan    |   0 | supply_constrained |
|       3 | nan    |   0 | supply_constrained |
|       4 | nan    |   0 | supply_constrained |
|       0 |  -0.22 |   7 | destock            |
|       1 |   0.36 |   7 | destock            |
|       2 |   0.63 |   6 | destock            |
|       3 | nan    |   5 | destock            |
|       4 | nan    |   4 | destock            |
|       0 |  -0.56 |   9 | normal             |
|       1 |   0.52 |   9 | normal             |
|       2 |   0.66 |   9 | normal             |
|       3 |   0.48 |   9 | normal             |
|       4 |  -0.07 |   9 | normal             |

Turning points:
```
{
  "sellout_proxy": {
    "peak": "2021Q1",
    "peak_val": 116.6,
    "trough": "2022Q4",
    "trough_val": -24.2,
    "sign_changes": [
      "2021Q4",
      "2024Q1"
    ]
  },
  "logitech_ble": {
    "peak": "2024Q2",
    "peak_val": 14.3,
    "trough": "2022Q4",
    "trough_val": -16.0,
    "sign_changes": [
      "2023Q4"
    ]
  },
  "gn_periph": {
    "peak": "2024Q2",
    "peak_val": 12.6,
    "trough": "2023Q2",
    "trough_val": -18.1,
    "sign_changes": [
      "2024Q1",
      "2024Q3",
      "2024Q4",
      "2025Q1"
    ]
  },
  "nordic_consumer": {
    "peak": "2025Q1",
    "peak_val": 63.3,
    "trough": "2023Q1",
    "trough_val": -42.9,
    "sign_changes": [
      "2022Q4",
      "2024Q2"
    ]
  },
  "nordic_total": {
    "peak": "2025Q1",
    "peak_val": 108.2,
    "trough": "2024Q1",
    "trough_val": -48.8,
    "sign_changes": [
      "2023Q1",
      "2024Q3"
    ]
  }
}
```

Amplitude ratio (Nordic consumer swing ÷ Logitech BLE swing): destock 2022-24 = 2.56x; recovery 2024-26 = 5.09x.

## 3. Distributed-lag regression (ridge)

n=14, in-sample R²=0.92, in-sample RMSE=9.1 pts, leave-one-out RMSE=13.5 pts.

Effect on Nordic consumer YoY (pts) of +1pt Logitech BLE YoY at lag k: L1: +1.53, L2: +1.22, L3: +1.38 (sum +4.13; peak lag = 1).

Standardised coefficients:
|                   |   beta_std |
|:------------------|-----------:|
| logi_ble_yoy_L1   |      13.58 |
| logi_ble_yoy_L2   |      11.17 |
| logi_ble_yoy_L3   |      12.57 |
| nordic_dist_state |      -2.98 |

## 4. Guidance-bias model
| company   | window                                              |   n |   mean_beat_pct |   median_beat_pct |   std_pct |   min_pct |   max_pct | unit   | rule                                                                                                          |
|:----------|:----------------------------------------------------|----:|----------------:|------------------:|----------:|----------:|----------:|:-------|:--------------------------------------------------------------------------------------------------------------|
| Nordic    | normal channel (2020Q1-2026Q2)                      |  11 |            4.17 |              4    |      2.97 |     -0.75 |     10.62 | %      | quarterly revenue guide, quarters of that regime (config regimes)                                             |
| Nordic    | destock channel (2022Q3-2024Q1)                     |   7 |           -3.85 |             -3.07 |      5.73 |    -12.9  |      2.8  | %      | quarterly revenue guide, quarters of that regime (config regimes)                                             |
| Nordic    | supply-constrained channel (2020Q3-2022Q2)          |   8 |            6.01 |              5.99 |      5.99 |      0.1  |     19.4  | %      | quarterly revenue guide, quarters of that regime (config regimes)                                             |
| Nordic    | all quarters (2019Q1-2026Q2)                        |  30 |            2.53 |              2.52 |      5.87 |    -12.9  |     19.4  | %      | quarterly revenue guide, every quarter                                                                        |
| Logitech  | quarterly guides (2025Q2-2026Q2)                    |   5 |            1.61 |              1.9  |      0.64 |      0.51 |      2.05 | %      | explicit quarterly sales guide                                                                                |
| GN        | august annual organic guides, all years (2021-2025) |   5 |           -3.3  |             -3    |      3.7  |     -9.5  |      0    | pts    | full-year organic growth outcome minus the August guide midpoint; every year (F14; spread used for the range) |

## 5. Attribution (Monte Carlo, p10/p50/p90)
```
{
  "headline_route": "mixed",
  "logitech_usdm": {
    "p10": 76.0,
    "p50": 76.0,
    "p90": 76.0
  },
  "logitech_uncapped_usdm": {
    "p10": 89.46200635577819,
    "p50": 114.6955142917163,
    "p90": 146.37058453330638
  },
  "gn_usdm": {
    "p10": 6.110289132131125,
    "p50": 7.994806656102842,
    "p90": 10.192556901406459
  },
  "by_route": {
    "direct": {
      "logitech_usdm": {
        "p10": 76.0,
        "p50": 76.0,
        "p90": 76.0
      },
      "combined_pct_of_nordic_total": {
        "p10": 10.79553538087213,
        "p50": 11.047631637454497,
        "p90": 11.340040144344576
      },
      "combined_pct_of_nordic_consumer": {
        "p10": 18.151785153678798,
        "p50": 18.575663815188975,
        "p90": 19.067324136508574
      }
    },
    "indirect": {
      "logitech_usdm": {
        "p10": 89.46200635577819,
        "p50": 114.6955142917163,
        "p90": 146.37058453330638
      },
      "combined_pct_of_nordic_total": {
        "p10": 12.80998425214404,
        "p50": 16.162877554504057,
        "p90": 20.32113032656519
      },
      "combined_pct_of_nordic_consumer": {
        "p10": 21.538911574401485,
        "p50": 27.176519781909477,
        "p90": 34.16827223050784
      }
    },
    "mixed": {
      "logitech_usdm": {
        "p10": 89.46200635577819,
        "p50": 114.69551429171628,
        "p90": 146.37058453330638
      },
      "combined_pct_of_nordic_total": {
        "p10": 12.80998425214404,
        "p50": 16.162877554504057,
        "p90": 20.32113032656519
      },
      "combined_pct_of_nordic_consumer": {
        "p10": 21.538911574401485,
        "p50": 27.176519781909477,
        "p90": 34.16827223050784
      }
    }
  },
  "combined_usdm": {
    "p10": 97.35588031629472,
    "p50": 122.83786941423082,
    "p90": 154.4405904818954
  },
  "combined_pct_of_nordic_total": {
    "p10": 12.80998425214404,
    "p50": 16.162877554504057,
    "p90": 20.32113032656519
  },
  "combined_pct_of_nordic_consumer": {
    "p10": 21.538911574401485,
    "p50": 27.176519781909477,
    "p90": 34.16827223050784
  },
  "pc_peripherals_category_pct_of_consumer": {
    "p10": 24.419347387696025,
    "p50": 29.96914878659161,
    "p90": 35.603233418322155
  },
  "pc_peripherals_category_pct_of_total": {
    "p10": 14.523085551629741,
    "p50": 17.823756909920277,
    "p90": 21.174554611949493
  },
  "share_of_draws_hitting_10pct_cap": 0.9856,
  "implied_logitech_radio_units_m": {
    "p10": 74.58284142431387,
    "p50": 87.86688389329163,
    "p90": 103.61072036671386
  },
  "socket_share_used": {
    "source": "FCC census (peripheral grants)",
    "low": 0.6209599324121905,
    "mid": 0.7666666666666667,
    "high": 0.8682465670019085
  },
  "headset_share_used": {
    "low": 0.0,
    "mid": 0.0,
    "high": 0.3
  },
  "logitech_ttm_sales_usdm": {
    "quarters": [
      "2025Q3",
      "2025Q4",
      "2026Q1",
      "2026Q2"
    ],
    "peripherals": 3285.8999999999996,
    "headsets": 178.4
  },
  "fcc_census": {
    "grants": 101,
    "read": 38,
    "readable": 33,
    "unreadable": 5,
    "nordic": 23,
    "vendors": {
      "Nordic": 23,
      "Telink": 5,
      "Airoha": 2,
      "other (unidentified marking)": 2,
      "Realtek": 1
    },
    "by_family": {
      "peripheral": {
        "readable": 30,
        "nordic": 23,
        "vendors": {
          "Nordic": 23,
          "Telink": 5,
          "other (unidentified marking)": 2
        },
        "share": {
          "low": 0.6209599324121905,
          "mid": 0.7666666666666667,
          "high": 0.8682465670019085
        }
      },
      "audio": {
        "readable": 3,
        "nordic": 0,
        "vendors": {
          "Airoha": 2,
          "Realtek": 1
        },
        "share": {
          "low": 0.0,
          "mid": 0.0,
          "high": 0.4742399481250082
        }
      }
    },
    "used": true,
    "share": {
      "low": 0.6209599324121905,
      "mid": 0.7666666666666667,
      "high": 0.8682465670019085
    }
  },
  "leg_d_proprietary_floor": {
    "available": true,
    "line": "proprietary_usdm (Nordic technology split; discontinued in the 2025 taxonomy)",
    "peak_ttm_quarter": "2022Q2",
    "peak_ttm_usdm": 96.10000000000001,
    "peak_share_of_nordic_pct": 13.669985775248936,
    "trough_ttm_quarter": "2024Q1",
    "trough_ttm_usdm": 32.6,
    "peak_to_trough_pct": -66.07700312174818,
    "first_quarter_below_half_peak": "2022Q3",
    "reading": "floor for PC-peripheral exposure before the BLE/Bolt migration folded it into Short-range; a lower bound, not Logitech alone"
  },
  "leg_e_natural_experiment": {
    "available": true,
    "nordic_consumer_peak": "2022Q3",
    "nordic_consumer_trough": "2024Q1",
    "nordic_consumer_drop_usdm": 202.8,
    "nordic_consumer_drop_pct": -41.40465496120866,
    "logitech_ble_core_peak": "2022Q1",
    "logitech_ble_core_trough": "2023Q3",
    "logitech_drop_usdm": 399.3699999999999,
    "logitech_drop_pct": -14.405104565686289,
    "nordic_content_needed_if_logitech_alone_pct_of_logitech_sales": 50.779978466084096,
    "nordic_content_on_leg_a_priors_pct_of_logitech_sales": 3.5589473684210526,
    "reading": "on the Leg-A priors Nordic content is \u22483.6% of Logitech's sell-in value, so Logitech alone explains \u22487% of Nordic's drop: the OEM tier is a timing/direction signal, the level is broad-market"
  },
  "grade": "B",
  "use_in_model": "timing / direction signal for Nordic's consumer line, not a level input",
  "path": {
    "quarter": {
      "0": "2022Q1",
      "1": "2022Q2",
      "2": "2022Q3",
      "3": "2022Q4",
      "4": "2023Q1",
      "5": "2023Q2",
      "6": "2023Q3",
      "7": "2023Q4",
      "8": "2024Q1",
      "9": "2024Q2",
      "10": "2024Q3",
      "11": "2024Q4",
      "12": "2025Q1",
      "13": "2025Q2",
      "14": "2025Q3",
      "15": "2025Q4",
      "16": "2026Q1",
      "17": "2026Q2"
    },
    "regime": {
      "0": "supply_constrained",
      "1": "supply_constrained",
      "2": "destock",
      "3": "destock",
      "4": "destock",
      "5": "destock",
      "6": "destock",
      "7": "destock",
      "8": "destock",
      "9": "normal",
      "10": "normal",
      "11": "normal",
      "12": "normal",
      "13": "normal",
      "14": "normal",
      "15": "normal",
      "16": "normal",
      "17": "normal"
    },
    "break_2022Q3": {
      "0": "pre",
      "1": "pre",
      "2": "post",
      "3": "post",
      "4": "post",
      "5": "post",
      "6": "post",
      "7": "post",
      "8": "post",
      "9": "post",
      "10": "post",
      "11": "post",
      "12": "post",
      "13": "post",
      "14": "post",
      "15": "post",
      "16": "post",
      "17": "post"
    },
    "nordic_rev_ttm_usdm": {
      "0": 650.4,
      "1": 703.0,
      "2": 756.6,
      "3": 776.8,
      "4": 739.1,
      "5": 693.1,
      "6": 626.0,
      "7": 542.8,
      "8": 471.9,
      "9": 445.6,
      "10": 469.4,
      "11": 511.4,
      "12": 592.0,
      "13": 628.2,
      "14": 648.4,
      "15": 667.7,
      "16": 705.0,
      "17": 759.5
    },
    "nordic_consumer_ttm_usdm": {
      "0": 435.1,
      "1": 467.7,
      "2": 489.8,
      "3": 483.7,
      "4": 431.3,
      "5": 389.3,
      "6": 344.1,
      "7": 302.6,
      "8": 287.0,
      "9": 290.1,
      "10": 320.4,
      "11": 349.6,
      "12": 383.9,
      "13": 396.7,
      "14": 397.0,
      "15": 400.4,
      "16": 427.0,
      "17": 451.9
    },
    "nordic_proprietary_pct_of_rev": {
      "0": 13.5,
      "1": 13.7,
      "2": 12.0,
      "3": 9.8,
      "4": 7.9,
      "5": 5.7,
      "6": 5.9,
      "7": 6.3,
      "8": 6.9,
      "9": 8.4,
      "10": 8.3,
      "11": 7.3,
      "12": NaN,
      "13": NaN,
      "14": NaN,
      "15": NaN,
      "16": NaN,
      "17": NaN
    },
    "nordic_proprietary_q_usdm": {
      "0": 25.1,
      "1": 25.7,
      "2": 12.9,
      "3": 12.1,
      "4": 7.9,
      "5": 6.4,
      "6": 10.3,
      "7": 9.8,
      "8": 6.1,
      "9": 11.1,
      "10": 12.0,
      "11": 8.3,
      "12": NaN,
      "13": NaN,
      "14": NaN,
      "15": NaN,
      "16": NaN,
      "17": NaN
    },
    "logi_periph_ttm_usdm": {
      "0": 3200.4,
      "1": 3172.6,
      "2": 3124.6,
      "3": 2973.7,
      "4": 2853.1,
      "5": 2766.0,
      "6": 2726.6,
      "7": 2740.1,
      "8": 2795.5,
      "9": 2888.4,
      "10": 2926.0,
      "11": 3001.8,
      "12": 3009.7,
      "13": 3029.2,
      "14": 3103.2,
      "15": 3161.3,
      "16": 3210.8,
      "17": 3285.9
    },
    "mix_pointing": {
      "0": 0.244,
      "1": 0.246,
      "2": 0.249,
      "3": 0.251,
      "4": 0.255,
      "5": 0.26,
      "6": 0.266,
      "7": 0.268,
      "8": 0.266,
      "9": 0.263,
      "10": 0.261,
      "11": 0.258,
      "12": 0.262,
      "13": 0.262,
      "14": 0.264,
      "15": 0.267,
      "16": 0.268,
      "17": 0.271
    },
    "mix_keyboards": {
      "0": 0.302,
      "1": 0.308,
      "2": 0.301,
      "3": 0.296,
      "4": 0.293,
      "5": 0.286,
      "6": 0.287,
      "7": 0.289,
      "8": 0.294,
      "9": 0.296,
      "10": 0.298,
      "11": 0.293,
      "12": 0.293,
      "13": 0.294,
      "14": 0.295,
      "15": 0.295,
      "16": 0.292,
      "17": 0.287
    },
    "mix_gaming": {
      "0": 0.454,
      "1": 0.446,
      "2": 0.45,
      "3": 0.453,
      "4": 0.452,
      "5": 0.454,
      "6": 0.446,
      "7": 0.443,
      "8": 0.44,
      "9": 0.441,
      "10": 0.442,
      "11": 0.45,
      "12": 0.445,
      "13": 0.444,
      "14": 0.441,
      "15": 0.438,
      "16": 0.44,
      "17": 0.442
    },
    "wireless_share_mix_weighted": {
      "0": 0.697,
      "1": 0.697,
      "2": 0.697,
      "3": 0.697,
      "4": 0.698,
      "5": 0.698,
      "6": 0.699,
      "7": 0.7,
      "8": 0.7,
      "9": 0.699,
      "10": 0.699,
      "11": 0.698,
      "12": 0.699,
      "13": 0.699,
      "14": 0.7,
      "15": 0.7,
      "16": 0.7,
      "17": 0.7
    },
    "socket_cohort": {
      "0": "2023-2024 (extrapolated back)",
      "1": "2023-2024 (extrapolated back)",
      "2": "2023-2024 (extrapolated back)",
      "3": "2023-2024 (extrapolated back)",
      "4": "2021-2023 (widened to 2021-2024)",
      "5": "2021-2023 (widened to 2021-2024)",
      "6": "2021-2023 (widened to 2021-2024)",
      "7": "2021-2023 (widened to 2021-2024)",
      "8": "2022-2024",
      "9": "2022-2024",
      "10": "2022-2024",
      "11": "2022-2024",
      "12": "2023-2025",
      "13": "2023-2025",
      "14": "2023-2025",
      "15": "2023-2025",
      "16": "2024-2026",
      "17": "2024-2026"
    },
    "socket_n": {
      "0": 18,
      "1": 18,
      "2": 18,
      "3": 18,
      "4": 18,
      "5": 18,
      "6": 18,
      "7": 18,
      "8": 18,
      "9": 18,
      "10": 18,
      "11": 18,
      "12": 29,
      "13": 29,
      "14": 29,
      "15": 29,
      "16": 26,
      "17": 26
    },
    "socket_k_nordic": {
      "0": 12,
      "1": 12,
      "2": 12,
      "3": 12,
      "4": 12,
      "5": 12,
      "6": 12,
      "7": 12,
      "8": 12,
      "9": 12,
      "10": 12,
      "11": 12,
      "12": 22,
      "13": 22,
      "14": 22,
      "15": 22,
      "16": 21,
      "17": 21
    },
    "socket_low": {
      "0": 0.3,
      "1": 0.3,
      "2": 0.3,
      "3": 0.3,
      "4": 0.473,
      "5": 0.473,
      "6": 0.473,
      "7": 0.473,
      "8": 0.473,
      "9": 0.473,
      "10": 0.473,
      "11": 0.473,
      "12": 0.61,
      "13": 0.61,
      "14": 0.61,
      "15": 0.61,
      "16": 0.654,
      "17": 0.654
    },
    "socket_mid": {
      "0": 0.667,
      "1": 0.667,
      "2": 0.667,
      "3": 0.667,
      "4": 0.667,
      "5": 0.667,
      "6": 0.667,
      "7": 0.667,
      "8": 0.667,
      "9": 0.667,
      "10": 0.667,
      "11": 0.667,
      "12": 0.759,
      "13": 0.759,
      "14": 0.759,
      "15": 0.759,
      "16": 0.808,
      "17": 0.808
    },
    "socket_high": {
      "0": 0.817,
      "1": 0.817,
      "2": 0.817,
      "3": 0.817,
      "4": 0.817,
      "5": 0.817,
      "6": 0.817,
      "7": 0.817,
      "8": 0.817,
      "9": 0.817,
      "10": 0.817,
      "11": 0.817,
      "12": 0.863,
      "13": 0.863,
      "14": 0.863,
      "15": 0.863,
      "16": 0.903,
      "17": 0.903
    },
    "socket_evidence": {
      "0": "extrapolated: 12/18 Nordic in the 2023-2024 grants; lower bound widened to the prior",
      "1": "extrapolated: 12/18 Nordic in the 2023-2024 grants; lower bound widened to the prior",
      "2": "extrapolated: 12/18 Nordic in the 2023-2024 grants; lower bound widened to the prior",
      "3": "extrapolated: 12/18 Nordic in the 2023-2024 grants; lower bound widened to the prior",
      "4": "widened: too few readable grants in 2021-2023; 12/18 Nordic among grants 2021-2024 (Wilson 90%)",
      "5": "widened: too few readable grants in 2021-2023; 12/18 Nordic among grants 2021-2024 (Wilson 90%)",
      "6": "widened: too few readable grants in 2021-2023; 12/18 Nordic among grants 2021-2024 (Wilson 90%)",
      "7": "widened: too few readable grants in 2021-2023; 12/18 Nordic among grants 2021-2024 (Wilson 90%)",
      "8": "census: 12/18 Nordic among readable peripheral grants 2022-2024 (Wilson 90%)",
      "9": "census: 12/18 Nordic among readable peripheral grants 2022-2024 (Wilson 90%)",
      "10": "census: 12/18 Nordic among readable peripheral grants 2022-2024 (Wilson 90%)",
      "11": "census: 12/18 Nordic among readable peripheral grants 2022-2024 (Wilson 90%)",
      "12": "census: 22/29 Nordic among readable peripheral grants 2023-2025 (Wilson 90%)",
      "13": "census: 22/29 Nordic among readable peripheral grants 2023-2025 (Wilson 90%)",
      "14": "census: 22/29 Nordic among readable peripheral grants 2023-2025 (Wilson 90%)",
      "15": "census: 22/29 Nordic among readable peripheral grants 2023-2025 (Wilson 90%)",
      "16": "census: 21/26 Nordic among readable peripheral grants 2024-2026 (Wilson 90%)",
      "17": "census: 21/26 Nordic among readable peripheral grants 2024-2026 (Wilson 90%)"
    },
    "nordic_content_pct_of_logi_sales_p50": {
      "0": 2.73,
      "1": 2.73,
      "2": 2.72,
      "3": 2.73,
      "4": 2.99,
      "5": 2.98,
      "6": 3.0,
      "7": 3.0,
      "8": 3.0,
      "9": 2.99,
      "10": 3.0,
      "11": 2.99,
      "12": 3.43,
      "13": 3.42,
      "14": 3.43,
      "15": 3.43,
      "16": 3.63,
      "17": 3.63
    },
    "logitech_usdm_p10": {
      "0": 60.1,
      "1": 59.8,
      "2": 58.5,
      "3": 55.8,
      "4": 64.7,
      "5": 62.9,
      "6": 62.0,
      "7": 62.3,
      "8": 63.7,
      "9": 65.6,
      "10": 66.6,
      "11": 68.4,
      "12": 80.1,
      "13": 80.9,
      "14": 82.9,
      "15": 84.5,
      "16": 91.1,
      "17": 93.4
    },
    "logitech_usdm_p50": {
      "0": 87.2,
      "1": 86.6,
      "2": 85.1,
      "3": 81.2,
      "4": 85.3,
      "5": 82.5,
      "6": 81.7,
      "7": 82.1,
      "8": 83.8,
      "9": 86.4,
      "10": 87.7,
      "11": 89.8,
      "12": 103.1,
      "13": 103.6,
      "14": 106.4,
      "15": 108.5,
      "16": 116.7,
      "17": 119.4
    },
    "logitech_usdm_p90": {
      "0": 119.2,
      "1": 118.2,
      "2": 116.3,
      "3": 110.5,
      "4": 110.9,
      "5": 107.5,
      "6": 106.7,
      "7": 106.9,
      "8": 109.2,
      "9": 112.7,
      "10": 114.1,
      "11": 116.8,
      "12": 131.7,
      "13": 132.3,
      "14": 135.4,
      "15": 138.4,
      "16": 149.0,
      "17": 152.0
    },
    "ifrs834_cap_usdm": {
      "0": 65.0,
      "1": 70.3,
      "2": 75.7,
      "3": 77.7,
      "4": 73.9,
      "5": 69.3,
      "6": 62.6,
      "7": 54.3,
      "8": 47.2,
      "9": 44.6,
      "10": 46.9,
      "11": 51.1,
      "12": 59.2,
      "13": 62.8,
      "14": 64.8,
      "15": 66.8,
      "16": 70.5,
      "17": 76.0
    },
    "cap_source": {
      "0": "assumed: no OEM >=10% (not verified for this year)",
      "1": "assumed: no OEM >=10% (not verified for this year)",
      "2": "assumed: no OEM >=10% (not verified for this year)",
      "3": "assumed: no OEM >=10% (not verified for this year)",
      "4": "assumed: no OEM >=10% (not verified for this year)",
      "5": "assumed: no OEM >=10% (not verified for this year)",
      "6": "assumed: no OEM >=10% (not verified for this year)",
      "7": "assumed: no OEM >=10% (not verified for this year)",
      "8": "AR2025 comparatives: three distributors (35%, 13%, 10%)",
      "9": "AR2025 comparatives: three distributors (35%, 13%, 10%)",
      "10": "AR2025 comparatives: three distributors (35%, 13%, 10%)",
      "11": "AR2025 comparatives: three distributors (35%, 13%, 10%)",
      "12": "AR2025: only >=10% customers are two distributors (30%, 12%)",
      "13": "AR2025: only >=10% customers are two distributors (30%, 12%)",
      "14": "AR2025: only >=10% customers are two distributors (30%, 12%)",
      "15": "AR2025: only >=10% customers are two distributors (30%, 12%)",
      "16": "AR2025: only >=10% customers are two distributors (30%, 12%)",
      "17": "AR2025: only >=10% customers are two distributors (30%, 12%)"
    },
    "cap_status": {
      "0": "assumed",
      "1": "assumed",
      "2": "assumed",
      "3": "assumed",
      "4": "assumed",
      "5": "assumed",
      "6": "assumed",
      "7": "assumed",
      "8": "found",
      "9": "found",
      "10": "found",
      "11": "found",
      "12": "found",
      "13": "found",
      "14": "found",
      "15": "found",
      "16": "found",
      "17": "found"
    },
    "share_of_draws_over_cap": {
      "0": 0.848,
      "1": 0.766,
      "2": 0.667,
      "3": 0.566,
      "4": 0.747,
      "5": 0.795,
      "6": 0.892,
      "7": 0.975,
      "8": 0.997,
      "9": 0.999,
      "10": 0.999,
      "11": 0.996,
      "12": 0.998,
      "13": 0.996,
      "14": 0.996,
      "15": 0.995,
      "16": 0.997,
      "17": 0.992
    },
    "gn_usdm_p50": {
      "0": 8.0,
      "1": 8.0,
      "2": 8.0,
      "3": 8.0,
      "4": 9.6,
      "5": 9.1,
      "6": 8.8,
      "7": 8.7,
      "8": 8.9,
      "9": 9.2,
      "10": 9.2,
      "11": 9.4,
      "12": 9.2,
      "13": 8.8,
      "14": 8.6,
      "15": 8.3,
      "16": 8.1,
      "17": 8.0
    },
    "share_total_indirect_p10": {
      "0": 10.46,
      "1": 9.64,
      "2": 8.82,
      "3": 8.2,
      "4": 10.03,
      "5": 10.38,
      "6": 11.29,
      "7": 13.09,
      "8": 15.36,
      "9": 16.77,
      "10": 16.11,
      "11": 15.21,
      "12": 15.1,
      "13": 14.28,
      "14": 14.12,
      "15": 13.9,
      "16": 14.07,
      "17": 13.35
    },
    "share_total_indirect_p50": {
      "0": 14.67,
      "1": 13.46,
      "2": 12.32,
      "3": 11.5,
      "4": 12.85,
      "5": 13.25,
      "6": 14.47,
      "7": 16.75,
      "8": 19.68,
      "9": 21.49,
      "10": 20.67,
      "11": 19.42,
      "12": 18.99,
      "13": 17.91,
      "14": 17.74,
      "15": 17.5,
      "16": 17.71,
      "17": 16.79
    },
    "share_total_indirect_p90": {
      "0": 19.58,
      "1": 17.95,
      "2": 16.48,
      "3": 15.25,
      "4": 16.35,
      "5": 16.85,
      "6": 18.47,
      "7": 21.32,
      "8": 25.09,
      "9": 27.38,
      "10": 26.32,
      "11": 24.73,
      "12": 23.82,
      "13": 22.5,
      "14": 22.25,
      "15": 21.98,
      "16": 22.31,
      "17": 21.08
    },
    "share_total_direct_p50": {
      "0": 11.18,
      "1": 11.06,
      "2": 10.94,
      "3": 10.84,
      "4": 11.2,
      "5": 11.24,
      "6": 11.37,
      "7": 11.6,
      "8": 11.89,
      "9": 12.06,
      "10": 11.96,
      "11": 11.84,
      "12": 11.55,
      "13": 11.4,
      "14": 11.33,
      "15": 11.24,
      "16": 11.15,
      "17": 11.05
    },
    "share_total_mixed_p50": {
      "0": 14.67,
      "1": 13.46,
      "2": 12.32,
      "3": 11.5,
      "4": 12.85,
      "5": 13.25,
      "6": 14.47,
      "7": 16.75,
      "8": 19.68,
      "9": 21.49,
      "10": 20.67,
      "11": 19.42,
      "12": 18.99,
      "13": 17.91,
      "14": 17.74,
      "15": 17.5,
      "16": 17.71,
      "17": 16.79
    },
    "share_consumer_indirect_p50": {
      "0": 21.93,
      "1": 20.23,
      "2": 19.04,
      "3": 18.46,
      "4": 22.03,
      "5": 23.6,
      "6": 26.32,
      "7": 30.05,
      "8": 32.36,
      "9": 33.01,
      "10": 30.28,
      "11": 28.41,
      "12": 29.29,
      "13": 28.36,
      "14": 28.97,
      "15": 29.18,
      "16": 29.24,
      "17": 28.22
    }
  }
}
```

## 6. Forecasts
| print                | metric                    |   point |    low |   high | guide        |   yoy_pct |
|:---------------------|:--------------------------|--------:|-------:|-------:|:-------------|----------:|
| Nordic Q3 2026       | Revenue (USDm)            |   240.2 |  225.2 |  255.3 | 220-240      |      34.2 |
| Nordic Q3 2026       | Gross margin (%)          |    53.1 |   52   |   54.2 | >50          |     nan   |
| Logitech Q2 FY27     | Net sales (USDm)          |  1226.3 | 1172.9 | 1279.6 | 1185-1220    |       3.4 |
| Logitech Q2 FY27     | Gross margin non-GAAP (%) |    45.3 |   44.1 |   46.5 | ~44          |     nan   |
| GN cont. ops Q3 2026 | Revenue (DKKm)            |  2247   | 2023   | 2471   | FY org 0-3%  |       1.6 |
| GN cont. ops Q3 2026 | Adj. EBITA margin (%)     |    13.5 |    9.3 |   17.8 | FY adj 9-10% |     nan   |

### Step 3 channel cross-check (does not move the point; steps/step3_inventory_mechanism/outputs/step3_report.md)
| company   | state                                                                                                                                                                                 |   adj_low |   adj_mid |   adj_high | unit   | config_line                                                              |   config_value | config_inside_range   | watch_flag   |
|:----------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------:|----------:|-----------:|:-------|:-------------------------------------------------------------------------|---------------:|:----------------------|:-------------|
| Nordic    | distribution restocking from a lean base (coded state +0.5); component distributors lean: Avnet 75 d, Arrow 61 d, Microchip distributor days 25 (31% of the way up its 10-year range) |       0   |       4.2 |       14.6 | USDm   | forecast.nordic_2026Q3.signal_adjustments_usdm.capacity_worry_pull_in    |              0 | True                  | True         |
| Logitech  | lean: channel -2.1 wk vs target (all anchors) / -1.1 wk (latest anchor 2026Q1); sell-through ran +4 pts above sell-in in 2026Q2                                                       |       5.1 |      36.5 |      161.9 | USDm   | forecast.logitech_2026Q3.signal_adjustments_usdm (sum of hand-set lines) |              0 | False                 | False        |
| GN        | distributors draining for 8 quarters: cumulative -481 DKKm = -4.0 wk of Enterprise sell-in since 2024Q3 (no anchor: relative, grade D)                                                |    -113.7 |     -48.7 |       16.2 | DKKm   | forecast.gn_2026Q3.enterprise_org_pct.mid                                |              2 | True                  | False        |

### Nordic detail
```
{
  "name": "Nordic Semiconductor Q3 2026 (reports 22 Oct 2026)",
  "metric": "Revenue USDm",
  "guide": [
    220,
    240
  ],
  "guide_mid": 230.0,
  "hist_beat_pct": 5.23,
  "hist_beat_sd_pct": 5.11,
  "signal_adjustments": {
    "capacity_worry_pull_in": 0.0,
    "nrf54_ramp_mix": 0.0,
    "supply_chain_term (step 7c)": -0.0,
    "logitech_supplier_incident (graph)": -1.78
  },
  "beat_source": "own record by channel state (F20, F30): +5.23% when neither building nor short of supply (n 15), -8.39 pts when building (n 7), -2.79 pts in a supply shortage (n 8); state now 'lean' (+0.00); the shortage split was adopted after seeing the data and its walk-forward does not beat the rule before it; record from 2019Q1 (F32): the state cannot see a demand shock and the split has no walk-forward edge (R7-R8), rule kept (F33)",
  "point": 240.2,
  "low": 225.2,
  "high": 255.3,
  "yoy_pct": 34.2,
  "gm_point": 53.1,
  "gm_range": [
    52.0,
    54.2
  ],
  "gm_rule": "F18 branch: Nordic guides only a floor ('>50%'), so the walk-forward winner is used: last quarter (RMSE 2.36 pts; 4-quarter mean 2.90, same quarter last year 4.15, guide + mean past error (last 4) 2.45, guide + mean past error (all) 2.37; one-off-adjusted GM) + channel-excess term +0.0 (F25 not adopted: peer delta -0.25 pts, t -1.18; state 1q before = not excess)",
  "gm_model": {
    "rule": "F18 branch: Nordic guides only a floor ('>50%'), so the walk-forward winner is used: last quarter (RMSE 2.36 pts; 4-quarter mean 2.90, same quarter last year 4.15, guide + mean past error (last 4) 2.45, guide + mean past error (all) 2.37; one-off-adjusted GM) + channel-excess term +0.0 (F25 not adopted: peer delta -0.25 pts, t -1.18; state 1q before = not excess)",
    "point": 53.1,
    "low": 52.0,
    "high": 54.2,
    "sd_pts": 0.87,
    "n_regime": 10,
    "scores": {
      "last quarter": 2.36,
      "4-quarter mean": 2.9,
      "same quarter last year": 4.15,
      "guide + mean past error (last 4)": 2.45,
      "guide + mean past error (all)": 2.37
    },
    "rule_points": {
      "last quarter": 53.1,
      "4-quarter mean": 52.27,
      "same quarter last year": 51.9,
      "guide + mean past error (last 4)": 52.27,
      "guide + mean past error (all)": 51.4
    },
    "floor_met_share": 0.81,
    "guide": ">50%",
    "series": "one-off adjusted",
    "excess": {
      "delta": -0.252,
      "se": 0.214,
      "t": -1.18,
      "n": 672,
      "n_quarters": 63,
      "adopted": false,
      "why": "not adopted: peer delta -0.25 pts, t -1.18 (needs < 0 with |t| >= 2); Nordic walk-forward RMSE 2.27 with the term vs 2.27 without",
      "wf_rmse_last_quarter": 2.27,
      "wf_rmse_with_term": 2.27,
      "wf_n": 25,
      "wf_n_excess": 10,
      "state_t_minus_1": "not excess",
      "applied_pts": 0.0,
      "gm_if_excess": 52.8
    }
  },
  "regression_crosscheck": {
    "implied_consumer_yoy_pct": 22.7,
    "implied_consumer_usdm": 137.0,
    "implied_total_usdm_at_avg_mix": 229.8,
    "inputs": {
      "driver": "logi_ble_yoy_tv",
      "L1": 8.8,
      "L2": 8.3,
      "L3": 8.3
    },
    "note": "regression-only view; ignores I&H and guidance, shown as a sanity check not the forecast"
  },
  "step3_channel_call": {
    "state": "distribution restocking from a lean base (coded state +0.5); component distributors lean: Avnet 75 d, Arrow 61 d, Microchip distributor days 25 (31% of the way up its 10-year range)",
    "direction": "small Q3 upside (mostly in the guide); the same amount is a payback risk in H1 2027",
    "adj_low": 0.0,
    "adj_mid": 4.2,
    "adj_high": 14.6,
    "unit": "USDm",
    "config_line": "forecast.nordic_2026Q3.signal_adjustments_usdm.capacity_worry_pull_in",
    "config_value": 0.0,
    "config_inside_range": true,
    "watch_flag": true
  }
}
```
### Logitech detail
```
{
  "name": "Logitech Q2 FY2027 (Jul-Sep 2026; reports ~27 Oct 2026)",
  "metric": "Net sales USDm",
  "guide": [
    1185,
    1220
  ],
  "guide_mid": 1202.5,
  "hist_beat_pct": 1.98,
  "hist_beat_sd_pct": 3.46,
  "signal_adjustments": {
    "supply_chain_term (step 7c)": 0.0
  },
  "beat_source": "guide-error model (F16): habit +1.98% (pooled with 12 peers, own record 11%) + channel state 'lean' (+0.00)",
  "point": 1226.3,
  "low": 1172.9,
  "high": 1279.6,
  "yoy_pct": 3.4,
  "gm_point": 45.3,
  "gm_range": [
    44.1,
    46.5
  ],
  "gm_rule": "F18 branch: point guide (44% on the call) -> guide + mean past error +1.3 pts (n 4: +0.6, +2.3, +1.0, +1.3); walk-forward race on the 4 guided quarters: guide + mean past error 0.93, last quarter 1.29, 4-quarter mean 1.11 pts -> guide + mean past error",
  "gm_model": {
    "rule": "F18 branch: point guide (44% on the call) -> guide + mean past error +1.3 pts (n 4: +0.6, +2.3, +1.0, +1.3); walk-forward race on the 4 guided quarters: guide + mean past error 0.93, last quarter 1.29, 4-quarter mean 1.11 pts -> guide + mean past error",
    "point": 45.3,
    "low": 44.1,
    "high": 46.5,
    "sd_pts": 0.93,
    "n": 4,
    "walk_forward_rmse": 0.93,
    "scores": {
      "guide + mean past error": 0.93,
      "last quarter": 1.29,
      "4-quarter mean": 1.11
    },
    "chosen": "guide + mean past error",
    "guide": "~44%",
    "rule_points": {
      "guide + mean past error": 45.3,
      "last quarter": 44.8,
      "4-quarter mean": 44.22
    }
  },
  "gm_note": "non-GAAP; GAAP \u2248 0.3pt lower; excludes any further tariff refunds",
  "fx_check": {
    "term_pts": 0.12,
    "term_usdm": 1.4,
    "guide_assumed_pts": 0.0,
    "calibration_slope": 0.67,
    "calibration_r2": 0.89,
    "wf_rmse_guide": 23.3,
    "wf_rmse_guide_fx": 28.0,
    "wf_n": 4,
    "applied": false
  },
  "step3_channel_call": {
    "state": "lean: channel -2.1 wk vs target (all anchors) / -1.1 wk (latest anchor 2026Q1); sell-through ran +4 pts above sell-in in 2026Q2",
    "direction": "refill tailwind to sell-in, capped by the late-June supplier incident",
    "adj_low": 5.1,
    "adj_mid": 36.5,
    "adj_high": 161.9,
    "unit": "USDm",
    "config_line": "forecast.logitech_2026Q3.signal_adjustments_usdm (sum of hand-set lines)",
    "config_value": 0.0,
    "config_inside_range": false,
    "watch_flag": false
  }
}
```
### GN detail
```
{
  "name": "GN Store Nord \u2014 GN Audio successor = continuing ops (Enterprise + Gaming), Q3 2026 (reports 5 Nov 2026)",
  "metric": "Revenue DKKm",
  "base_q3_2025": {
    "enterprise": 1624.0,
    "gaming": 587.0,
    "total": 2211.0
  },
  "organic_assumptions": {
    "enterprise": {
      "low": -1.0,
      "mid": 2.0,
      "high": 4.0
    },
    "gaming": {
      "low": 8.0,
      "mid": 12.0,
      "high": 16.0
    },
    "fx_pts": 1.47
  },
  "fx_update": {
    "term_pts": 1.4704578897876242,
    "usd_yoy_pct": 1.628082036354539,
    "apac_yoy_pct": 3.8903282280887646,
    "usd_share": 0.4252809310028481,
    "rates_days": 63,
    "fit": {
      "usd_share": 0.4252809310028481,
      "apac_share": 0.2,
      "prior_usd_share": 0.4,
      "n": 5,
      "fit": {
        "2023Q1": [
          1.0,
          1.11
        ],
        "2024Q2": [
          -1.0,
          -0.31
        ],
        "2024Q3": [
          -1.0,
          -0.49
        ],
        "2025Q1": [
          1.0,
          1.46
        ],
        "2026Q2": [
          -2.0,
          -0.97
        ]
      },
      "rmse_pts": 0.6341813949745307,
      "north_america_check": {
        "2023Q3": [
          -7.0,
          -7.319564890877672
        ]
      }
    }
  },
  "method": "guide_error_model",
  "guidance_anchor": {
    "fy_guide": [
      0.0,
      3.0,
      "2026-08-19"
    ],
    "fy_guide_mid": 1.5,
    "august_bias_pts": -3.3,
    "august_bias_n": 5,
    "bias_source": "guide-error model: plain mean of its own August-guide misses (F17, F23), -3.30 pts (n 5)",
    "august_bias_all_years_pts": -3.3,
    "august_bias_by_year": {
      "2021": -3.0,
      "2022": -9.5,
      "2023": 0.0,
      "2024": -3.0,
      "2025": -1.0
    },
    "fy_expected_pct": -1.8,
    "h2_if": {
      "no bias (guide as given)": 6.491069636765001,
      "pooled with the semiconductor peers' habit": 10.375161149331573
    },
    "h1_2026_organic_pct": -3.92,
    "h2_organic_pct": 0.15,
    "h2_sd_pts": 7.79,
    "q3_if": {
      "no bias (guide as given)": 2389.0,
      "pooled with the semiconductor peers' habit": 2476.0
    }
  },
  "division_view": {
    "point": 2348.0,
    "low": 2275.0,
    "high": 2405.0
  },
  "point": 2247.0,
  "low": 2023.0,
  "high": 2471.0,
  "yoy_pct": 1.6,
  "ebita_bridge_dkkm": {
    "q2_2026_adj_ebita": 111.0,
    "drop_through_on_incremental_rev": 40.0,
    "cost_savings": 50,
    "tariff_refund": 60
  },
  "ebita_bridge_point_dkkm": 261.0,
  "ebita_adj_margin_point": 13.5,
  "ebita_adj_margin_range": [
    9.3,
    17.8
  ],
  "ebita_margin_rule": "F18 branch: annual point guide -> guide + mean past error (no walk-forward race: quarterly continuing-ops EBITA exists from 2025 only). FY guide 9-10% (2026-08-19) + mean August error -0.94 pts (all 5 years) = 8.56% of FY revenue 9,331; H1 EBITA 117 reported; Q3 = 45% of H2 (2025 split)",
  "ebita_margin_model": {
    "rule": "F18 branch: annual point guide -> guide + mean past error (no walk-forward race: quarterly continuing-ops EBITA exists from 2025 only). FY guide 9-10% (2026-08-19) + mean August error -0.94 pts (all 5 years) = 8.56% of FY revenue 9,331; H1 EBITA 117 reported; Q3 = 45% of H2 (2025 split)",
    "point": 13.5,
    "low": 9.3,
    "high": 17.8,
    "sd_pts": 3.3,
    "q3_share_by_year": {
      "2021": 0.507,
      "2022": 0.58,
      "2023": 0.435,
      "2025": 0.447
    },
    "q3_share_sd": 0.066,
    "sd_from_fy_error_pts": 2.61,
    "sd_from_share_pts": 2.02,
    "point_if_share_mean": 14.9,
    "q3_share_mean": 0.492,
    "fy_margin_expected": 8.56,
    "q3_ebita_dkkm": 304.0,
    "h2_ebita_dkkm": 682.0,
    "august_errors": [
      {
        "fiscal_year": 2021,
        "statement_date": "2021-08-19",
        "mid": 21.0,
        "actual": 21.2,
        "error_pts": 0.2
      },
      {
        "fiscal_year": 2022,
        "statement_date": "2022-08-17",
        "mid": 17.5,
        "actual": 14.1,
        "error_pts": -3.4
      },
      {
        "fiscal_year": 2023,
        "statement_date": "2023-08-16",
        "mid": 11.0,
        "actual": 10.6,
        "error_pts": -0.4
      },
      {
        "fiscal_year": 2024,
        "statement_date": "2024-08-22",
        "mid": 12.5,
        "actual": 12.0,
        "error_pts": -0.5
      },
      {
        "fiscal_year": 2025,
        "statement_date": "2025-08-21",
        "mid": 12.0,
        "actual": 11.4,
        "error_pts": -0.6
      }
    ],
    "guide": "FY 9-10%"
  },
  "ebita_adj_point_dkkm": 304.0,
  "ebita_margin_ex_tariff_refund": 10.9,
  "ebita_bridge_margin_pct": 11.6,
  "ebita_bridge_margin_ex_tariff_refund": 8.9,
  "step3_channel_call": {
    "state": "distributors draining for 8 quarters: cumulative -481 DKKm = -4.0 wk of Enterprise sell-in since 2024Q3 (no anchor: relative, grade D)",
    "direction": "H2 'positive organic' needs the drain to END more than sell-out to accelerate",
    "adj_low": -113.7,
    "adj_mid": -48.7,
    "adj_high": 16.2,
    "unit": "DKKm",
    "config_line": "forecast.gn_2026Q3.enterprise_org_pct.mid",
    "config_value": 2.0,
    "config_inside_range": true,
    "watch_flag": false
  }
}
```

## 7. Tier panel (last 10 quarters)
| quarter   |   sellout_proxy_yoy |   snx_endpoint_yoy |   logi_ble_yoy |   logi_st_gap |   gn_periph_yoy |   gn_st_gap |   nordic_consumer_yoy |   nordic_inv_days |   nordic_dist_state |   wsts_yoy | regime   |
|:----------|--------------------:|-------------------:|---------------:|--------------:|----------------:|------------:|----------------------:|------------------:|--------------------:|-----------:|:---------|
| 2024Q2    |                 8.7 |                  1 |           14.3 |            -3 |            12.6 |         nan |                   3.7 |             242.2 |                -0.5 |       18.6 | normal   |
| 2024Q3    |                 3.6 |                  5 |            8.3 |            -2 |            -0.9 |           4 |                  37.4 |             206.5 |                -0.5 |       23.7 | normal   |
| 2024Q4    |                 8.8 |                  3 |            9.5 |             2 |             9.5 |         nan |                  43.3 |             205.2 |                -0.5 |       18.2 | normal   |
| 2025Q1    |                 1.9 |                  8 |            1.9 |             2 |           -11   |           4 |                  63.3 |             167.9 |                 0   |       18.1 | normal   |
| 2025Q2    |                 5.5 |                 13 |            4.3 |             0 |           -15   |           2 |                  14.6 |             153.3 |                 0   |       20   | normal   |
| 2025Q3    |                 7.3 |                 10 |            9.3 |             1 |            -9.3 |           2 |                   0.3 |             141.4 |                 0   |       26   | normal   |
| 2025Q4    |                10.1 |                 12 |            7.9 |             4 |           -12.5 |         nan |                   3.5 |             173.8 |                 0   |       38.4 | normal   |
| 2026Q1    |                 7.4 |                 14 |            7.9 |             0 |            -8.2 |           2 |                  30.1 |             181.9 |                 0   |       83   | normal   |
| 2026Q2    |                10.9 |                 13 |            8.8 |             4 |            -5.7 |           3 |                  24.8 |             193.4 |                 0.5 |      129.4 | normal   |
| 2026Q3    |               nan   |                nan |          nan   |           nan |           nan   |         nan |                 nan   |             nan   |               nan   |      nan   | normal   |

`wsts_yoy` = WSTS worldwide semiconductor billings YoY (Pipeline B, context only — never a regressor).

## How the supply chain enters each forecast (step 7c)

Each forecast = guide-anchored benchmark + weight x (chain forecast − benchmark) + events propagated through the graph. The chain forecast is built from the brief's decisions (lag kernel, inventory mechanism, attribution share, channel state); the weight comes from the walk-forward back-test by a rule fixed in `config/model.yaml` (chain_forecast) before the live numbers.

- **Nordic, guided quarter (h=1):** the chain as reasoned (CH, nothing fitted) has walk-forward RMSE 12.7m vs 7.4m for the guide-anchored benchmark on the same quarters; encompassing beta -0.66 (t -2.0) - a negative sign: when the Logitech/GN slice lags the guided total, Nordic beats anyway, because the rest drives the quarter. Weight 0. Why, mechanically: Nordic guides from orders in hand, and the lag kernel says the end demand that sets Q3 was reported before the guide, so it is already in the orders. The chain describes only the Logitech/GN slice; its disagreement with the guide is about the mix, which the guide total already absorbs.
- **Nordic, quarter after (h=2):** CH beta +3.16 (t +2.6), GR beta +1.31 (t +3.6): the chain carries information where no guide exists. CH gets the direction right but a slope of 3.2 says Nordic moves about 3x what the attribution slice alone implies: its other consumer customers ride the same end-demand cycle (step 3's whole-company multiplier 2.1–6.5). Encompassing picks GR (lower RMSE), weight 1.00; the Q4 point and its pre-registered challengers are the 'Nordic Q4 2026 (h=2)' row below (F26, F22).
- **Logitech (h=1):** tier identity sell-in = sell-through + Δchannel inventory. On the same 5 guided quarters: walk-forward RMSE 23m vs 13m for the guide (all 14 quarters: 51m); weight used 0.00 (guide only at h1 (F29); inverse-MSE weight shown as a diagnostic: 0.23), contribution +0.0m. The three hand-set channel lines were removed (F5).
- **GN (h=1):** same-quarter read-across fails (table below); GN's segments move with its own product cycle and share shifts. The channel enters only through the Enterprise distributor-drain assumption.
- **Logitech supplier incident:** -7.1m of Nordic Q3 shipments by the graph (lead 14 weeks, content 3.63%), of which 75% is assumed already in the 6 Aug guide: -1.8m.

| print                | decision          | term                                                                            | value                      | evidence                                                                                                                                                                                                                | source                                                                            |
|:---------------------|:------------------|:--------------------------------------------------------------------------------|:---------------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:----------------------------------------------------------------------------------|
| Nordic Q3 2026       | Lag               | graph kernel (share of the demand signal by quarters back)                      | 1 q back 54%, 2 q back 46% | mean 1.46 q; the demand that sets Q3 is mostly already reported                                                                                                                                                         | config/supply_graph.csv                                                           |
| Nordic Q3 2026       | Lag               | end demand fed through the kernel (Logitech sell-out proxy, YoY %)              | 9.3                        | Logitech sell-in YoY + disclosed sell-through gap; unreported quarter by persistence                                                                                                                                    | step 5 / step 6 GR                                                                |
| Nordic Q3 2026       | Mechanism         | slice multiplier m (end demand -> Nordic slice)                                 | 1.09                       | step 3 slice_multiplier.csv mid: Logitech 1.00, GN 2.46                                                                                                                                                                 | steps/step3_inventory_mechanism                                                   |
| Nordic Q3 2026       | Attribution       | Logitech + GN share of Nordic revenue s                                         | 16.8                       | step 2 share path p50 (%); p10-p90 in attribution_path.csv                                                                                                                                                              | steps/step2_attribution                                                           |
| Nordic Q3 2026       | Structural breaks | channel state of t−1 (step 3b, data-dated) and its term (pts)                   | lean: +0.00                | Nordic's own record by the state of t−1 (F20, F30): habit +5.23% on 15 quarters neither building nor short; building -8.39 pts (7 q), supply shortage -2.79 pts (8 q). Config regimes only for GR training and lag fits | steps/step7_forecast/outputs/guide_error_model.csv                                |
| Nordic Q3 2026       | Chain             | CH (as reasoned, nothing fitted): guide + s x [rev(t-4)(1+m x demand) - guide]  | 224.5                      | tilt -5.5; GR (fitted slope) 233.6                                                                                                                                                                                      | chain_forecast.py                                                                 |
| Nordic Q3 2026       | Limitations       | weight on the chain (encompassing test, h=1)                                    | 0.0                        | CH beta -0.66 (t -2.0), GR beta -0.05 (t -0.8): no information beyond the guide                                                                                                                                         | chain_weight_tests.csv                                                            |
| Nordic Q3 2026       | Chain             | chain contribution to the forecast (USDm)                                       | 0.0                        | weight x (chain - guide-anchored)                                                                                                                                                                                       |                                                                                   |
| Nordic Q3 2026       | Lag + Attribution | Logitech supplier incident through the graph (USDm)                             | -1.8                       | step 5d event study (forward from 25 Jun; lead 14 wk, content 3.63%): gross -7.1, 75% assumed already in the 6 Aug guide (grade D): range 0 to -7.1; Q4 -0.9                                                            | steps/step5_supply_graph/outputs/event_study_supplier_incident.csv                |
| Nordic Q4 2026 (h=2) | Chain             | GRi / GR / CH forecast (USDm)                                                   | 212.0 / 222.4 / 212.2      | point GRi (F26); GR and CH pre-registered (F22); each includes the incident's Q4 term -0.9. Encompassing: CH beta +3.16 t +2.6; GR beta +1.31 t +3.6                                                                    | outputs/forecast_next_quarter.csv; steps/step7_forecast/outputs/q4_prereg_log.csv |
| Logitech Q2 FY27     | Mechanism         | tier identity: sell-in = sell-through + d(channel inventory); channel at target | 10.9                       | Q1 FY27 sell-through YoY (%) carried to Q2                                                                                                                                                                              | logitech_quarterly.csv sellthrough gap                                            |
| Logitech Q2 FY27     | Chain             | chain forecast (USDm)                                                           | 1315.7                     | vs guide-anchored 1221.9                                                                                                                                                                                                | chain_forecast.py                                                                 |
| Logitech Q2 FY27     | Limitations       | weight on the chain (F29: guide only at h1; inverse-MSE 0.23 is a diagnostic)   | 0.0                        | same 5 guided quarters: chain RMSE 23m vs guide 13m (chain over all 14 quarters incl. the 2023-24 turn: 51m)                                                                                                            | chain_logitech_walkforward.csv                                                    |
| Logitech Q2 FY27     | Chain             | chain contribution to the forecast (USDm)                                       | 0.0                        | 0 (F29); the three hand-set lines were removed (F5)                                                                                                                                                                     |                                                                                   |
| GN Q3 2026           | Chain             | Gaming organic vs Logitech Gaming YoY (same quarter; Logitech reports first)    | -0.17                      | n 17; below the 0.5 bar: not used                                                                                                                                                                                       | chain_gn_readacross.csv                                                           |
| GN Q3 2026           | Chain             | Enterprise organic vs TD Synnex Endpoint billings YoY (same quarter)            | 0.21                       | n 15; below the 0.5 bar: not used                                                                                                                                                                                       | chain_gn_readacross.csv                                                           |
| GN Q3 2026           | Mechanism         | Enterprise distributor drain (step 3 channel call)                              | in the organic assumption  | H2 'positive organic' needs the drain to end; kept in the bottom-up, not a separate term                                                                                                                                | steps/step3_inventory_mechanism/outputs/channel_call.csv                          |

## Next quarter: Nordic 2026Q4 revenue (h = 2, graph-driven)

Point **USD 212m** (179–245, +25% y/y) from GRi. No guide exists for this quarter; the benchmark carries the Q3 guide by last year's seasonal step. The graph models read the step-5 lag kernel, so an edited edge lag moves them: GR only when a path's lag crosses two quarters (the unreported quarter is filled by persistence, P74), GRg whenever weight shifts between lags 1 and 2 (it reads Logitech's own Q3 guide). `lag_low_point` / `lag_high_point` = the graph's low / high scenario. Caveat: GR / GRg regress all Nordic consumer revenue on Logitech's sell-out proxy, so they carry the common consumer cycle, not the Logitech / GN slice; they fail when Logitech diverges from the rest of consumer electronics (e.g. the 2026 supplier incident; step 6 section 5, P86).

| model   | role                                                                                                                                  |   point |    low |   high |   yoy_pct |   lag_low_point |   lag_high_point |   wf_rmse_usdm |   wf_n |   rmse_ratio_vs_GB |
|:--------|:--------------------------------------------------------------------------------------------------------------------------------------|--------:|-------:|-------:|----------:|----------------:|-----------------:|---------------:|-------:|-------------------:|
| G       | benchmark: Q3 guide x last year's Q3->Q4 step                                                                                         |  216.93 | 162.27 | 271.59 |     27.98 |          nan    |           nan    |          42.65 |     14 |               0.97 |
| GB      | benchmark + real-time beat                                                                                                            |  221.14 | 164.63 | 277.64 |     30.46 |          nan    |           nan    |          44.09 |     14 |               1    |
| GR      | challenger (was the point until F26): sell-through proxy through the whole graph, unreported quarter by persistence (F24)             |  222.41 | 186.46 | 258.36 |     31.22 |          222.41 |           219.78 |          28.03 |      9 |               0.59 |
| GRg     | sensitivity only: GR with Logitech's raw guide for the unreported quarter (F24; GRi uses guide x (1+past beat), F26)                  |  216.27 | 179.59 | 252.94 |     27.59 |          211.54 |           219.67 |          28.44 |      9 |               0.6  |
| GRi     | point (F26): Logitech sell-in through the Nordic -> ODM -> Logitech segment; unreported quarter = our bias-corrected sell-in forecast |  211.97 | 179.34 | 244.6  |     25.06 |          211.43 |           215.11 |          25.42 |      9 |               0.54 |

## Risk scenarios (step 7d, outputs/scenarios.csv)

| print                                      | scenario                                                                              |   point |    low |   high |   vs_base | decision          | what_moves                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | source                                                                                                                    |
|:-------------------------------------------|:--------------------------------------------------------------------------------------|--------:|-------:|-------:|----------:|:------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------|
| Nordic Q3 2026                             | base                                                                                  |   240.2 |  225.2 |  255.3 |       0   | all               | guide x (1 + 5.23%) + chain terms (7c) + incident (5d); expected error = own record by channel state (F20, F30): +5.23% when neither building nor short of supply (n 15), -8.39 pts when building (n 7), -2.79 pts in a supply shortage (n 8); state now 'lean' (+0.00); the shortage split was adopted after seeing the data and its walk-forward does not beat the rule before it; record from 2019Q1 (F32): the state cannot see a demand shock and the split has no walk-forward edge (R7-R8), rule kept (F33) | outputs/forecasts.csv                                                                                                     |
| Nordic Q3 2026                             | distributors turn to building (channel state)                                         |   220.9 |        |        |     -19.3 | Mechanism         | Nordic's own building effect -8.39 pts (n 7); peers' -1.64 (t -4.4)                                                                                                                                                                                                                                                                                                                                                                                                                                                | steps/step7_forecast/outputs/guide_error_model.csv                                                                        |
| Nordic Q3 2026                             | supply shortage (D24: lead time > 26 weeks)                                           |   233.8 |        |        |      -6.4 | Mechanism         | Nordic's own shortage effect -2.79 pts (n 8) on its base habit +5.23%; same incident term                                                                                                                                                                                                                                                                                                                                                                                                                          | steps/step7_forecast/outputs/guide_error_model.csv                                                                        |
| Nordic Q3 2026                             | F16 pooled with peers (pre-registered challenger)                                     |   233.3 |        |        |      -6.9 | Limitations       | expected error +2.24% (habit pooled, own weight 25%) instead of +5.23%                                                                                                                                                                                                                                                                                                                                                                                                                                             | steps/step7_forecast/outputs/challenger_prereg_log.csv                                                                    |
| Nordic Q3 2026                             | rule before F30: supply-shortage quarters counted as lean (pre-registered challenger) |   238   |        |        |      -2.2 | Structural breaks | expected error +4.26% (14 not-building quarters incl. the 2020Q4-22Q3 shortage) instead of +5.23%                                                                                                                                                                                                                                                                                                                                                                                                                  | steps/step7_forecast/outputs/challenger_prereg_log.csv                                                                    |
| Nordic Q3 2026                             | state from Nordic's own words (F31, pre-registered)                                   |   236.9 |        |        |      -3.3 | Structural breaks | expected error +3.80% (state 'base' from Nordic's words) instead of +5.23%                                                                                                                                                                                                                                                                                                                                                                                                                                         | steps/step7_forecast/outputs/challenger_prereg_log.csv                                                                    |
| Nordic Q3 2026                             | rule before F20 (F14): Nordic's own normal-regime beat, unpooled                      |   237.8 |        |        |      -2.4 | Structural breaks | beat +4.17% (regime dated after the fact, F14) instead of +5.23%                                                                                                                                                                                                                                                                                                                                                                                                                                                   | steps/step6_backtest/outputs/guidance_bias.csv                                                                            |
| Nordic Q3 2026                             | small customers pull in beyond the guide (+1.0; F19 keeps the line at 0)              |   241.2 |        |        |       1   | Mechanism         | sign grade C (CEO, Q2 2026 call: 'some safety stockings for some additional weeks'); size grade D (F19)                                                                                                                                                                                                                                                                                                                                                                                                            | pipelines/A_company_financials/data/manual/nordic_2026Q2.txt                                                              |
| Nordic Q3 2026                             | supplier incident not in Nordic's guide (net -> gross)                                |   234.9 |        |        |      -5.3 | Lag + Attribution | share of the incident already in the 6 Aug guide 75% -> 0% (gross -7.1)                                                                                                                                                                                                                                                                                                                                                                                                                                            | steps/step7_forecast/outputs/chain_terms.csv                                                                              |
| Nordic Q3 2026                             | supplier incident all in Nordic's guide (net -> 0)                                    |   242   |        |        |       1.8 | Lag + Attribution | share in the 6 Aug guide 75% -> 100% (grade D judgment); range of the line 0 to -7.1                                                                                                                                                                                                                                                                                                                                                                                                                               | steps/step7_forecast/outputs/chain_terms.csv                                                                              |
| Nordic Q3 2026                             | distributors restock at step 3's high                                                 |   254.8 |        |        |      14.6 | Mechanism         | channel refill +14.6 instead of the +0.0 line (extra distributor weeks (0.0, 0.5, 1.5) x USD 17.7m/wk x distribution share (0.42, 0.47, 0.55))                                                                                                                                                                                                                                                                                                                                                                     | steps/step3_inventory_mechanism/outputs/channel_call.csv                                                                  |
| Nordic Q4 2026                             | base: supply graph (GRi, h=2)                                                         |   212   |  179.3 |  244.6 |       0   | Lag               | point (F26): Logitech sell-in through the Nordic -> ODM -> Logitech segment; unreported quarter = our bias-corrected sell-in forecast; walk-forward error 0.54x the guide-based extrapolation (n 9)                                                                                                                                                                                                                                                                                                                | outputs/forecast_next_quarter.csv                                                                                         |
| Nordic Q4 2026                             | graph lags and shares at their low end (GRi)                                          |   211.4 |        |        |      -0.5 | Lag + Attribution | every edge lag and share at the end of its grade-based range                                                                                                                                                                                                                                                                                                                                                                                                                                                       | outputs/forecast_next_quarter.csv                                                                                         |
| Nordic Q4 2026                             | graph lags and shares at their high end (GRi)                                         |   215.1 |        |        |       3.1 | Lag + Attribution | every edge lag and share at the end of its grade-based range                                                                                                                                                                                                                                                                                                                                                                                                                                                       | outputs/forecast_next_quarter.csv                                                                                         |
| Nordic Q4 2026                             | previous rule: GR (sell-through proxy, whole graph, persistence fill; F24)            |   222.4 |  186.5 |  258.4 |      10.4 | Limitations       | pre-registered challenger since F26; walk-forward error 0.59x (n 9); its gap to GRi is the sell-through vs sell-in driver and the fill                                                                                                                                                                                                                                                                                                                                                                             | outputs/forecast_next_quarter.csv; steps/step7_forecast/outputs/q4_prereg_log.csv                                         |
| Nordic Q4 2026                             | Q3 restock (step 3 high) pays back in Q4                                              |   197.4 |        |        |     -14.6 | Mechanism         | the 14.6 refill reverses one quarter later (step 3 dates the payback to H1 2027; Q4 is the earliest case)                                                                                                                                                                                                                                                                                                                                                                                                          | steps/step3_inventory_mechanism/outputs/channel_call.csv                                                                  |
| Logitech Q2 FY27                           | base                                                                                  |  1226.3 | 1172.9 | 1279.6 |       0   | all               | guide x beat + 0.00 x (chain - guide-anchored); guide only at h1 (F29); inverse-MSE weight shown as a diagnostic (5 explicitly guided quarters)                                                                                                                                                                                                                                                                                                                                                                    | outputs/forecasts.csv                                                                                                     |
| Logitech Q2 FY27                           | chain at its inverse-MSE weight (diagnostic since F29)                                |  1248.2 |        |        |      21.9 | Limitations       | weight 0.23 instead of 0.00 (n 5)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | steps/step7_forecast/outputs/chain_terms.csv; pipelines/A_company_financials/data/raw/logitech_implied_quarter_guides.csv |
| Logitech Q2 FY27                           | chain weight incl. implied guides at the 2023-25 turns                                |  1271.2 |        |        |      44.9 | Limitations       | weight 0.48 instead of 0.00 (n 8)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | steps/step7_forecast/outputs/chain_terms.csv; pipelines/A_company_financials/data/raw/logitech_implied_quarter_guides.csv |
| GN cont. ops Q3 2026                       | base                                                                                  |  2247   | 2023   | 2471   |       0   | all               | FY guide mid +1.5% + expected guide error -3.3 pts (plain mean of its own August-guide misses, n 5; F17, F23) + FX +1.5 pts at ECB rates (F27)                                                                                                                                                                                                                                                                                                                                                                     | outputs/forecast_details.json (gn.guidance_anchor)                                                                        |
| GN cont. ops Q3 2026                       | bias: no bias (guide as given)                                                        |  2389   |        |        |     142   | Limitations       | H2 organic +6.5% instead of +0.1%                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | outputs/forecast_details.json                                                                                             |
| GN cont. ops Q3 2026                       | bias: pooled with the semiconductor peers' habit                                      |  2476   |        |        |     229   | Limitations       | H2 organic +10.4% instead of +0.1%                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | outputs/forecast_details.json                                                                                             |
| GN cont. ops Q3 2026                       | division view (Enterprise / Gaming organic, config)                                   |  2348   |        |        |     101   | Mechanism         | management's divisional H2 language; Enterprise distributor drain ends                                                                                                                                                                                                                                                                                                                                                                                                                                             | config/model.yaml forecast.gn_2026Q3                                                                                      |
| GN cont. ops Q3 2026 adj. EBITA margin (%) | point: Q3 share of H2 EBITA as in 2025                                                |    13.5 |    9.3 |   17.8 |       0   | all               | Q3 share 45% (the one continuing-ops year)                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | outputs/forecast_details.json (gn.ebita_margin_model)                                                                     |
| GN cont. ops Q3 2026 adj. EBITA margin (%) | Q3 share at its 2021-25 mean                                                          |    14.9 |        |        |       1.4 | Limitations       | Q3 share 49% (2021-23 GN Audio incl. Consumer: a different perimeter; F23)                                                                                                                                                                                                                                                                                                                                                                                                                                         | pipelines/A_company_financials/data/raw/gn_quarterly.csv                                                                  |
