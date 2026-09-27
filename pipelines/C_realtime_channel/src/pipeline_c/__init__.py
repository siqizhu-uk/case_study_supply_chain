"""Pipeline C — real-time channel and design-win evidence.

Three things the filings cannot give: (1) live distributor stock on the Nordic parts that sit in peripherals,
as a time series of snapshots; (2) which SoC is inside Logitech / Jabra products (design-win evidence from
teardowns and FCC internal photos); (3) the sell-out proxies that the brief suggested (Amazon rank, price
trackers) — logged with the reason they are not scraped.

Trustable tools are used directly where they exist and are keyless: the iFixit public API (teardown text),
findchips (Supplyframe's aggregator of distributor feeds, structured rows). Official distributor APIs (Mouser,
Digi-Key) need a free key; the Mouser provider runs when MOUSER_API_KEY is set and becomes the cross-check.
Everything is a dated snapshot appended to data/raw/channel_snapshots.csv so the series builds up over time.
"""
