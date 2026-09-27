"""Step 3c — bullwhip measured link by link, and the Logitech / GN slice multiplier.

Measure (Lee, Padmanabhan & Whang 1997; Cachon, Randall & Schmidt 2007): variance ratio
    VR = Var(orders placed upstream) / Var(demand received)
on YoY growth rates (the YoY transform removes seasonality, which is how Cachon et al. avoid calling a Christmas
build 'bullwhip'). Reported with its square root (the amplitude ratio in standard-deviation terms) and a moving-block
bootstrap 90% interval: n is 7-21 quarters, so the interval is the point.

Links (each denominator is the demand the numerator's tier actually sees):
    A  Logitech sell-in        / Logitech sell-through     retail + distributor channel (the gap)
    A' Logitech purchases      / Logitech sell-in          Logitech's own stock (purchases = COGS + dInventory)
    B  Nordic consumer revenue / Logitech sell-in          ODM stock + component distribution + Nordic customer mix
    C  Nordic consumer revenue / Logitech sell-through     end to end

Slice multiplier: Nordic's Q4 2023 report splits Bluetooth revenue into top-10 customers (-3% in 2023) and the broad
market (-46%). The whole-company amplitude (2.5x destock / 5.5x recovery peak-to-trough) is a broad-market number; the
Logitech slice is bounded by (i) the top-10 behaviour and (ii) Logitech's own purchases.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def variance_ratio(num, den) -> float:
    num, den = np.asarray(num, float), np.asarray(den, float)
    return float(np.var(num, ddof=1) / np.var(den, ddof=1))


def block_bootstrap_ci(stat, arrays: list, reps: int, block: int, seed: int, q=(5, 95)) -> tuple[float, float]:
    """Moving-block bootstrap: resample overlapping blocks of `block` consecutive quarters (keeps autocorrelation)."""
    n = len(arrays[0])
    rng = np.random.default_rng(seed)
    starts = np.arange(max(n - block + 1, 1))
    vals = []
    for _ in range(reps):
        idx = np.concatenate([np.arange(s, min(s + block, n)) for s in rng.choice(starts, size=int(np.ceil(n / block)))])[:n]
        try:
            v = stat(*[np.asarray(a)[idx] for a in arrays])
        except (ZeroDivisionError, FloatingPointError, np.linalg.LinAlgError):
            continue
        if np.isfinite(v):
            vals.append(v)
    return (float(np.percentile(vals, q[0])), float(np.percentile(vals, q[1]))) if vals else (np.nan, np.nan)


LINKS = [
    ("A", "Logitech sell-in / Logitech sell-through", "logi_sales_yoy", "logi_sellthrough_yoy"),
    ("A'", "Logitech purchases / Logitech sell-in", "logi_purchases_yoy", "logi_sales_yoy"),
    ("B", "Nordic consumer / Logitech sell-in", "nordic_consumer_yoy", "logi_sales_yoy"),
    ("C", "Nordic consumer / Logitech sell-through", "nordic_consumer_yoy", "logi_sellthrough_yoy"),
]


def link_table(s: pd.DataFrame, windows: dict[str, tuple[str, str]], boot: dict) -> pd.DataFrame:
    rows = []
    for wname, (lo, hi) in windows.items():
        w = s.loc[pd.Period(lo, "Q"):pd.Period(hi, "Q")]
        for lid, label, num, den in LINKS:
            d = w[[num, den]].dropna()
            if len(d) < 5:
                rows.append({"window": wname, "link": lid, "label": label, "n": len(d)})
                continue
            vr = variance_ratio(d[num], d[den])
            lo_ci, hi_ci = block_bootstrap_ci(variance_ratio, [d[num].values, d[den].values], boot["reps"], boot["block"], boot["seed"])
            rows.append({"window": wname, "link": lid, "label": label, "n": len(d), "variance_ratio": vr,
                         "vr_p5": lo_ci, "vr_p95": hi_ci, "sd_ratio": np.sqrt(vr),
                         "sd_ratio_p5": np.sqrt(lo_ci), "sd_ratio_p95": np.sqrt(hi_ci)})
    return pd.DataFrame(rows).round(2)


def concentration_table(conc: pd.DataFrame, p: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """Annual Nordic Bluetooth revenue split top-10 / broad market, against Logitech's calendar-year sell-in,
    sell-through and purchases. Dollar figures where Nordic gives them, share x Bluetooth revenue otherwise."""
    yr = p.index.year
    full = p["nordic_rev"].groupby(yr).count() == 4
    bt_rev = p["nordic_short_range"].groupby(yr).sum(min_count=4)
    c = conc.pivot_table(index="year", columns="metric", values="value")
    usd = c["top10_bt_revenue_usdm"] if "top10_bt_revenue_usdm" in c else pd.Series(dtype=float)
    share = c["top10_share_of_bt_pct"] if "top10_share_of_bt_pct" in c else pd.Series(dtype=float)
    rows = []
    for y in sorted(c.index):
        if not full.get(y, False):
            continue
        total = float(bt_rev[y])
        if pd.notna(usd.get(y, np.nan)):
            top, basis = float(usd[y]), "USD disclosed"
        elif pd.notna(share.get(y, np.nan)):
            top, basis = total * float(share[y]) / 100, f"{share[y]:.0f}% x Bluetooth revenue"
        else:
            continue
        rows.append({"year": y, "bt_revenue_usdm": total, "top10_usdm": top, "broad_usdm": total - top, "top10_basis": basis})
    t = pd.DataFrame(rows).set_index("year")
    t["top10_yoy_pct"] = t["top10_usdm"].pct_change(fill_method=None) * 100
    t["broad_yoy_pct"] = t["broad_usdm"].pct_change(fill_method=None) * 100
    sales_y = p["logi_sales"].groupby(yr).sum(min_count=4)
    st_level = (p["logi_sales"].shift(4) * (1 + p["logi_sellthrough_yoy"] / 100)).groupby(yr).sum(min_count=4)
    t["logi_sellin_yoy_pct"] = (sales_y.pct_change(fill_method=None) * 100).reindex(t.index)
    t["logi_sellthrough_yoy_pct"] = ((st_level / sales_y.shift(1) - 1) * 100).reindex(t.index)
    t["logi_purchases_yoy_pct"] = (f["logi_purchases_usdm"].groupby(yr).sum(min_count=4).pct_change(fill_method=None) * 100).reindex(t.index)
    return t.round(1)


def slice_multiplier(conc_t: pd.DataFrame, links: pd.DataFrame, attribution_path: pd.DataFrame | None, top10_avg: float) -> pd.DataFrame:
    """Amplitude of the Nordic revenue that comes from Logitech (and GN), relative to their own sell-in.
    Lower bound: Nordic's top-10 customers in the 2023 destock (their YoY / Logitech sell-in YoY).
    Upper bound: Logitech's purchases amplitude (link A'), i.e. what Logitech's supply chain actually bought.
    Whole company (link B) shown for contrast - it is the broad-market number and does not apply to the slice."""
    y23 = conc_t.loc[2023] if 2023 in conc_t.index else None
    top_beta = float(y23["top10_yoy_pct"] / y23["logi_sellin_yoy_pct"]) if y23 is not None else np.nan
    broad_beta = float(y23["broad_yoy_pct"] / y23["logi_sellin_yoy_pct"]) if y23 is not None else np.nan
    a_ = links[(links["link"] == "A'") & (links["window"] == "all")].iloc[0]
    b_ = links[(links["link"] == "B") & (links["window"] == "all")].iloc[0]
    logi_p10 = gn_p50 = np.nan
    if attribution_path is not None and len(attribution_path):
        r = attribution_path.set_index("quarter").loc["2023Q4"]
        logi_p10, gn_p50 = float(r["logitech_usdm_p10"]), float(r["gn_usdm_p50"])
    logi_top10 = bool(logi_p10 > top10_avg)
    rows = [
        {"slice": "logitech", "in_top10_evidence": f"step-2 attribution p10 USD {logi_p10:.0f}m/yr > top-10 average USD {top10_avg:.1f}m -> top-10 customer" if logi_top10
         else f"step-2 p10 USD {logi_p10:.0f}m/yr <= top-10 average -> membership unknown",
         "mult_low": round(max(top_beta, 0.0), 2), "mult_mid": 1.0, "mult_high": round(float(a_["sd_ratio"]), 2),
         "basis": "low = top-10 Bluetooth YoY / Logitech sell-in YoY (2023); mid = pass-through of Logitech builds; high = Logitech purchases sd ratio (link A')"},
        {"slice": "gn", "in_top10_evidence": f"step-2 p50 USD {gn_p50:.0f}m/yr < top-10 average USD {top10_avg:.1f}m -> likely broad market or a small key account",
         "mult_low": 1.0, "mult_mid": round(0.5 * 1.0 + 0.5 * broad_beta, 2), "mult_high": round(broad_beta, 2),
         "basis": "low = pass-through (key account); high = broad-market Bluetooth YoY / Logitech sell-in YoY (2023); mid = equal odds of the two"},
        {"slice": "nordic_whole_company", "in_top10_evidence": "n/a", "mult_low": round(float(b_["sd_ratio_p5"]), 2), "mult_mid": round(float(b_["sd_ratio"]), 2),
         "mult_high": round(float(b_["sd_ratio_p95"]), 2), "basis": "link B sd ratio, all quarters: the number the regime amplitude_multiplier describes"},
    ]
    return pd.DataFrame(rows)
