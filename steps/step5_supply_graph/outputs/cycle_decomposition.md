# Cycle beyond the slice: point model vs the industry-cycle challenger (step 5g addendum)

Step 5g addendum: does the Q4 point model agree with the industry-cycle challenger about the cycle beyond the slice?

CH (step 7c) is the chain as reasoned: it speaks only for the Logitech / GN slice of Nordic. Any model minus CH is therefore
the part of Nordic it sees beyond the slice. Compared per quarter (step 6 h=2 walk-forward) and live (Q4 2026):
    GRi - CH   the point model since F26 (Logitech sell-in, Nordic -> ODM -> Logitech segment, forecast fill)
    GR  - CH   the previous point model, now a challenger
    CYC - CH   the industry-cycle challenger (G29: US electronics-store sales)
    actual - CH  what the slice missed in fact
Levels differ by each model's own bias, so the live gap is also read against the model's own historical mean gap
("anomaly"): two models agree on THIS quarter only if their anomalies agree, not just their levels. Kept outside the
pre-registered CYC files so their spec hash does not move.

- Live Q4 gap to CH: GRi -3.3, GR +10.2, CYC -3.9 USD m. In level, GRi is closer to CYC than GR was.
- Against each model's own history (9 quarters): mean gaps GRi +13.2, GR +8.3, CYC -15.6; the actual was +15.1 above CH on average. Live anomalies: GRi -16.5, CYC +11.7 - opposite directions: the level agreement is a coincidence of two biases, not a shared reading of this quarter.
- Which gap tracks what CH missed (correlation with actual - CH): GRi 0.73, GR 0.69, CYC 0.78; RMSE GRi 25.4, GR 28.0, CYC 38.8.

| model   |   n |   hist_mean_gap |   corr_with_actual_gap |   rmse_usdm |   live_gap |   live_anomaly |
|:--------|----:|----------------:|-----------------------:|------------:|-----------:|---------------:|
| GRi     |   9 |           13.15 |                   0.73 |       25.42 |      -3.32 |         -16.48 |
| GR      |   9 |            8.29 |                   0.69 |       28.03 |      10.19 |           1.9  |
| CYC     |   9 |          -15.6  |                   0.78 |       38.79 |      -3.93 |          11.67 |
| actual  |   9 |           15.14 |                 nan    |      nan    |     nan    |         nan    |

| quarter   |   CYC_total |   CH_total |   actual_total |   GRi_total |   GR_total |   GRi_minus_CH |   GR_minus_CH |   CYC_minus_CH |   actual_minus_CH |
|:----------|------------:|-----------:|---------------:|------------:|-----------:|---------------:|--------------:|---------------:|------------------:|
| 2024Q2    |       111   |       94.1 |          127.9 |       135   |      124   |           40.9 |          29.9 |           16.9 |              33.8 |
| 2024Q3    |       107.8 |      114.8 |          158.8 |       146.3 |      130.8 |           31.4 |          15.9 |           -7   |              44   |
| 2024Q4    |       107.9 |      126.3 |          150.2 |       140.1 |      130.6 |           13.8 |           4.3 |          -18.5 |              23.9 |
| 2025Q1    |        73.1 |       92.8 |          155.1 |        95.9 |       91.2 |            3.1 |          -1.6 |          -19.7 |              62.3 |
| 2025Q2    |       166.4 |      236.5 |          164.1 |       196.4 |      198.6 |          -40.1 |         -37.9 |          -70.1 |             -72.4 |
| 2025Q3    |       165.1 |      187.1 |          179   |       200.6 |      196.6 |           13.5 |           9.6 |          -21.9 |              -8.1 |
| 2025Q4    |       154.2 |      164.4 |          169.5 |       188.2 |      183.8 |           23.8 |          19.3 |          -10.3 |               5.1 |
| 2026Q1    |       168.7 |      169.9 |          192.4 |       187.6 |      188.8 |           17.7 |          18.9 |           -1.2 |              22.5 |
| 2026Q2    |       184.8 |      193.5 |          218.6 |       207.8 |      209.6 |           14.3 |          16.2 |           -8.7 |              25.1 |
