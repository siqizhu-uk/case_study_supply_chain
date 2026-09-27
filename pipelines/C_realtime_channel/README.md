# Pipeline C — real-time channel and design-win evidence

What the filings cannot give: live distributor stock on the Nordic parts inside peripherals (a dated snapshot series), which SoC sits inside Logitech / Jabra / SteelSeries products (teardowns, FCC internal photos), and the sell-out proxies the brief suggested (logged with the reason they are not scraped). `config/data_config.csv` lists every source with grade, retrieval method, validation method, status and reason; `config/parts.csv` and `config/distributors.csv` say what is watched and which distributors count as authorized.

```bash
python pipelines/C_realtime_channel/scripts/validate.py                 # today's snapshot + iFixit scan + FCC check (~2 min)
python pipelines/C_realtime_channel/scripts/validate.py --no-snapshot   # re-validate the stored series only
MOUSER_API_KEY=... python pipelines/C_realtime_channel/scripts/validate.py   # adds Mouser's official feed as the cross-check
```

Each run appends today's rows to `data/raw/channel_snapshots.csv` (idempotent per day) and rewrites `data/processed/channel_latest.csv`, `channel_series.csv`, `design_win_evidence.csv`, `ifixit_guides.csv`, `validation_report.md`. Run it weekly and the tier-3 channel indicator on the dashboard becomes a series.
