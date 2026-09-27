"""Live gauge of Nordic channel tightness (dashboard: one lead-time row in Monitor, the per-part table in Audit): authorized-distributor stock, factory lead time and 1k
price on the Nordic parts inside peripherals, from the latest on-demand snapshot (Pipeline C; `./run.sh --live` takes a
new one). Readings, not a time series: there is no public history to back-test. One reading enters the model: a latest
lead time above config cycle_state.shortage.lead_time_min_weeks turns Nordic's state to shortage (D24, step 3b);
stock and price enter nothing."""
from __future__ import annotations

import pandas as pd

from core.config import ROOT, load_config

SNAP = ROOT / "pipelines" / "C_realtime_channel" / "data" / "raw" / "channel_snapshots.csv"


def _groups() -> pd.DataFrame:
    """Authorized, exact-MPN readings: one stock number per (date, part, distributor group)."""
    s = pd.read_csv(SNAP, dtype={"snapshot_date": str})
    s = s[(s["authorized"] == 1) & s["qty_in_stock"].notna()]
    s = s[s["listed_mpn"].fillna("").str.upper().str.replace("-", "") == s["part"].str.upper().str.replace("-", "")]
    return s.groupby(["snapshot_date", "part", "distributor_group"]).agg(stock=("qty_in_stock", "max"), lead=("lead_time", "max"),
                                                                        p1k=("price_1000", "median")).reset_index()


def readings() -> pd.DataFrame:
    g = _groups()
    return g.groupby(["snapshot_date", "part"]).agg(stock=("stock", "sum"), groups=("distributor_group", "nunique"),
                                                    lead_weeks=("lead", "max"), price_1k=("p1k", "median")).reset_index()


def _listings() -> pd.DataFrame:
    """One stock number per (date, part, exact distributor listing, e.g. 'Avnet Silica' vs 'Avnet Americas')."""
    s = pd.read_csv(SNAP, dtype={"snapshot_date": str})
    s = s[(s["authorized"] == 1) & s["qty_in_stock"].notna()]
    s = s[s["listed_mpn"].fillna("").str.upper().str.replace("-", "") == s["part"].str.upper().str.replace("-", "")]
    return s.groupby(["snapshot_date", "part", "distributor"])["qty_in_stock"].max().rename("stock").reset_index()


def like_for_like(g: pd.DataFrame, part: str, last: str, prev: str) -> tuple[float, int, int] | None:
    """Stock change on the exact distributor listings present in BOTH readings. findchips shows a different regional set
    per fetch (Avnet Silica / Asia / Americas are separate listings), so totals and even distributor groups swing with the
    listing, not the stock. Returns (change, listings compared, listings seen before) or None."""
    a = g[(g["part"] == part) & (g["snapshot_date"] == last)].set_index("distributor")["stock"]
    b = g[(g["part"] == part) & (g["snapshot_date"] == prev)].set_index("distributor")["stock"]
    common = a.index.intersection(b.index)
    if not len(common) or b[common].sum() <= 0:
        return None
    return float(a[common].sum() / b[common].sum() - 1), len(common), len(b)


def _shortage_weeks() -> float:
    """D24: the live lead time above which a lean quarter is a supply shortage for Nordic."""
    return float(load_config()["cycle_state"]["shortage"]["lead_time_min_weeks"])


def latest_lead() -> tuple[float, str, str, list[str], list[str]] | None:
    """The longest factory lead time in each part's latest quote: (weeks, part, read date, parts quoted with a lead time,
    parts never quoted with one); None without a quote."""
    all_parts = sorted(_groups()["part"].unique())
    g = _groups().dropna(subset=["lead"])
    if g.empty:
        return None
    last = g.sort_values("snapshot_date").groupby("part").tail(1)
    top = last.sort_values("lead").iloc[-1]
    quoted = sorted(last["part"])
    return float(top["lead"]), str(top["part"]), str(top["snapshot_date"]), quoted, [p for p in all_parts if p not in quoted]


def gauge_html() -> str:
    if not SNAP.exists():
        return ""
    g, r, lst = _groups(), readings(), _listings()
    dates = sorted(r["snapshot_date"].unique())
    last, prev = dates[-1], (dates[-2] if len(dates) > 1 else None)
    cur = r[r["snapshot_date"] == last].set_index("part")
    lead = g.dropna(subset=["lead"]).sort_values("snapshot_date").groupby("part").tail(1).set_index("part")
    rows = ""
    for part, x in cur.iterrows():
        ch = like_for_like(lst, part, last, prev) if prev else None
        chs = f"{ch[0] * 100:+.0f}% on {ch[1]} of {ch[2]} listings seen before" if ch else "no listing in common"
        lt = f"{lead.loc[part, 'lead']:.0f} wk (read {lead.loc[part, 'snapshot_date']})" if part in lead.index else "not quoted"
        p = "" if pd.isna(x["price_1k"]) else f"${x['price_1k']:.2f}"
        rows += f"<tr><td>{part}</td><td>{x['stock']:,.0f}</td><td>{int(x['groups'])}</td><td>{chs}</td><td>{lt}</td><td>{p}</td></tr>"
    return (f"<h2>Live gauge: Nordic's Bluetooth LE SoCs at authorized distributors ({last})</h2>"
            "<p class=src>nRF is Nordic's part-number prefix: the nRF52, nRF53 and nRF54 families are its Bluetooth Low Energy SoCs, "
            "the chips inside wireless mice, keyboards and headsets; the brief names nRF52 and nRF54 parts as the gauge of Nordic's "
            "channel tightness.</p>"
            f"<table><tr><th>Part</th><th>Authorized stock (units)</th><th>Distributor groups</th><th>Change vs {prev} (like for like)</th>"
            "<th>Factory lead time</th><th>1k price (median)</th></tr>"
            f"{rows}</table><p class=src>Readings on demand (<code>./run.sh --live</code> takes a new one), not a series: listings vary by "
            "region and fetch (e.g. Avnet Silica on one day, Avnet Americas on another), so the change compares only the exact listings present "
            "in both readings, and there is no public history to back-test. "
            f"One reading enters the model: a latest lead time above {_shortage_weeks():.0f} weeks turns Nordic's state to shortage "
            "(D24, config cycle_state.shortage.lead_time_min_weeks); stock and price enter nothing. Lead time also bounds the Nordic "
            "direct-order lag (step 5); stock reads channel tightness; the 1k price reads pricing. Source: findchips (Digi-Key / Mouser block scripts; Mouser API used when MOUSER_API_KEY is set).</p>")
