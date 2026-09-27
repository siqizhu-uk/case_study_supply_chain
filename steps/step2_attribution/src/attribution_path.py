"""Step 2b — the attribution as a TIME PATH, not a single number.

The share of Nordic's revenue that Logitech (+ GN) accounts for moves every quarter, for three reasons that are each
observable:

  1. the denominator — Nordic's own revenue swings far more than Logitech's (bullwhip): in the 2022-24 destock Nordic's
     TTM revenue fell ~45% while Logitech's peripheral sales fell ~15%, so Logitech's share of Nordic ROSE in the trough;
  2. Logitech's category mix — pointing / keyboards / gaming carry different wireless shares (config radio_content), so
     the radio count per dollar of Logitech sales drifts with the mix;
  3. Nordic's socket share by design cohort — the FCC census is dated per grant, so the share of Logitech designs that
     carry Nordic can be computed for the designs in the market at each quarter (grants of the last three years).

The path is what the back-test (step 6) and the forecast (step 7) must use: validating 2023 quarters with the 2026
share would be a look-ahead. Every row carries the evidence flags for the socket cohort and for the IFRS 8.34 cap, and
the 2022Q3 break (Nordic's proprietary-2.4GHz line halving one quarter after Logitech turned negative) is a column.

Output: steps/step2_attribution/outputs/attribution_path.csv (one row per quarter, 2021Q2-2026Q2 — the first quarter with
Logitech category sales and Nordic segment data; there is no earlier public data for either).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from attribution import FCC, LOGITECH, NORDIC, OUT, PERIPHERAL_CODES, _draw, _wilson

MIN_COHORT_READ = 5          # readable peripheral grants in the cohort window before the cohort share is used on its own
COHORT_YEARS = 3             # a design certified in year Y is assumed in the market for Y..Y+2
BREAK_QUARTER = "2022Q3"     # Nordic proprietary line -50% QoQ; first quarter after Logitech's sales turned negative YoY


def _readable_peripheral_grants() -> pd.DataFrame:
    if not FCC.exists():
        return pd.DataFrame(columns=["fcc_id", "grant_date", "chip_vendor", "year"])
    d = pd.read_csv(FCC, dtype=str).fillna("")
    d = d[d["fcc_id"].str[3:5].isin(PERIPHERAL_CODES) & (d["soc_marking_observed"].str.strip() != "")
          & ~d["chip_vendor"].str.contains("unreadable", case=False)].copy()
    d["year"] = pd.to_datetime(d["grant_date"]).dt.year
    d["nordic"] = d["chip_vendor"].str.contains("Nordic", case=False)
    return d[["fcc_id", "grant_date", "chip_vendor", "year", "nordic"]]


def socket_share_for_quarter(q: pd.Period, grants: pd.DataFrame, prior: dict) -> dict:
    """Nordic share of readable Logitech peripheral designs in the market at quarter q: grants dated in
    [q.year - COHORT_YEARS + 1, q.year]. Before the census starts (2023) the earliest cohort is used with the
    prior's low end as the lower bound — flagged 'extrapolated'."""
    if grants.empty:
        return {"cohort": "prior", "n": 0, "k": 0, "low": prior["low"], "mid": prior["mid"], "high": prior["high"], "evidence": "prior (no census)"}
    first = int(grants["year"].min())
    y_hi, y_lo = q.year, q.year - COHORT_YEARS + 1
    if q.year < first:
        w = grants[grants["year"] <= first + 1]
        n, k = len(w), int(w["nordic"].sum())
        s = _wilson(k, n) if n else prior
        return {"cohort": f"{first}-{first + 1} (extrapolated back)", "n": n, "k": k, "low": min(prior["low"], s["low"]), "mid": s["mid"], "high": s["high"],
                "evidence": f"extrapolated: {k}/{n} Nordic in the {first}-{first + 1} grants; lower bound widened to the prior"}
    w = grants[(grants["year"] >= y_lo) & (grants["year"] <= y_hi)]
    n, k = len(w), int(w["nordic"].sum())
    if n >= MIN_COHORT_READ:
        s = _wilson(k, n)
        return {"cohort": f"{y_lo}-{y_hi}", "n": n, "k": k, **s, "evidence": f"census: {k}/{n} Nordic among readable peripheral grants {y_lo}-{y_hi} (Wilson 90%)"}
    # thin window: widen one year at a time (forward first — the next cohort is the closest technology) until it holds enough reads
    lo_w, hi_w, step = y_lo, y_hi, 0
    while n < MIN_COHORT_READ and (lo_w > int(grants["year"].min()) or hi_w < int(grants["year"].max())):
        if step % 2 == 0 and hi_w < int(grants["year"].max()):
            hi_w += 1
        elif lo_w > int(grants["year"].min()):
            lo_w -= 1
        else:
            hi_w += 1
        step += 1
        w = grants[(grants["year"] >= lo_w) & (grants["year"] <= hi_w)]
        n, k = len(w), int(w["nordic"].sum())
    s = _wilson(k, n) if n else prior
    return {"cohort": f"{y_lo}-{y_hi} (widened to {lo_w}-{hi_w})", "n": n, "k": k, **s,
            "evidence": f"widened: too few readable grants in {y_lo}-{y_hi}; {k}/{n} Nordic among grants {lo_w}-{hi_w} (Wilson 90%)"}


def _cap_evidence(q: pd.Period) -> tuple[str, str]:
    """IFRS 8.34 major-customer disclosure that bounds a DIRECT customer: Nordic AR2025 (2025: two distributors 30/12%;
    2024: three distributors 35/13/10%). Earlier years are not in the repo's evidence — the cap is assumed, and flagged."""
    if q.year >= 2025:
        return "AR2025: only >=10% customers are two distributors (30%, 12%)", "found"
    if q.year == 2024:
        return "AR2025 comparatives: three distributors (35%, 13%, 10%)", "found"
    return "assumed: no OEM >=10% (not verified for this year)", "assumed"


def build_path(cfg: dict, panel: pd.DataFrame | None = None, n: int = 20000, seed: int = 7) -> pd.DataFrame:
    a = cfg["attribution"]
    L, G = a["logitech"], a["gn"]
    rc = cfg["radio_content"]["logitech"]
    rng = np.random.default_rng(seed)
    grants = _readable_peripheral_grants()

    lo = pd.read_csv(LOGITECH).set_index("quarter")
    nd = pd.read_csv(NORDIC, dtype={"quarter": str}).set_index("quarter")
    cats = ["pointing_usdm", "keyboards_usdm", "gaming_usdm"]
    lo_ttm = lo[cats].rolling(4).sum()
    nd_ttm = nd[["revenue_usdm", "consumer_usdm", "proprietary_usdm"]].rolling(4, min_periods=4).sum()
    prop_q = nd["proprietary_usdm"]

    # draws shared across quarters so the path is smooth in the sampling noise, not just in the inputs
    asp = _draw(rng, L["avg_sell_in_asp_usd"], n)
    wl_scale = _draw(rng, L["wireless_share"], n) / L["wireless_share"]["mid"]      # scales the category wireless weights
    rpu = _draw(rng, L["radios_per_wireless_unit"], n)
    nasp = _draw(rng, L["nordic_asp_usd"], n)
    direct = _draw(rng, a.get("route_direct_share", {"low": 0.15, "mid": 0.35, "high": 0.5}), n)
    gn_ss = _draw(rng, G["steelseries_units_m"], n) * _draw(rng, G["steelseries_wireless_share"], n) * _draw(rng, G["nordic_socket_share_gaming"], n) * _draw(rng, G["nordic_asp_usd"], n)
    gn_ent = _draw(rng, G["enterprise_units_m"], n) * _draw(rng, G["enterprise_nordic_share"], n) * _draw(rng, G["nordic_asp_usd"], n)
    gn_now = gn_ss + gn_ent
    gn_index = None
    if panel is not None and "gn_periph_dkk" in panel:
        g = panel["gn_periph_dkk"].rolling(4).sum()
        gn_index = (g / g.dropna().iloc[-1]) if g.notna().any() else None

    # category-mix effect only: the mix-weighted wireless share is scaled so that the LAST quarter equals the headline
    # prior (config wireless_share.mid) — the path then differs from the headline only through observed drift in the mix
    valid = lo_ttm.dropna().index
    last_mix = lo_ttm.loc[valid[-1]] / lo_ttm.loc[valid[-1]].sum()
    wl_norm = L["wireless_share"]["mid"] / sum(rc[c]["weight"] * last_mix[c] for c in cats)

    rows = []
    for q in lo_ttm.index:
        if pd.isna(lo_ttm.loc[q]).any() or q not in nd_ttm.index or pd.isna(nd_ttm.loc[q, "revenue_usdm"]):
            continue
        per = pd.Period(q, "Q")
        sales = lo_ttm.loc[q]
        tot_l = float(sales.sum())
        mix = {c: float(sales[c] / tot_l) for c in cats}
        wl_mix = wl_norm * sum(rc[c]["weight"] * mix[c] for c in cats)            # mix-weighted wireless share (weights in config), anchored to the headline prior
        ss = socket_share_for_quarter(per, grants, L["nordic_socket_share"])
        socket = rng.triangular(ss["low"], ss["mid"], ss["high"], n) if ss["high"] > ss["low"] else np.full(n, ss["mid"])
        radios = tot_l / asp * np.clip(wl_mix * wl_scale, 0, 1) * rpu
        logi = radios * socket * nasp                                               # uncapped (indirect route)
        nordic_tot, nordic_cons = float(nd_ttm.loc[q, "revenue_usdm"]), float(nd_ttm.loc[q, "consumer_usdm"])
        cap = a["nordic_no_customer_over_pct"] / 100 * nordic_tot
        cap_src, cap_status = _cap_evidence(per)
        logi_direct = np.minimum(logi, cap)
        logi_mixed = np.minimum(logi * direct, cap) + logi * (1 - direct)
        gn = gn_now * (float(gn_index.get(per, np.nan)) if gn_index is not None and not np.isnan(gn_index.get(per, np.nan)) else 1.0)
        pct = lambda x: (x + gn) / nordic_tot * 100
        prop_ttm = nd_ttm.loc[q, "proprietary_usdm"]
        rows.append({
            "quarter": q, "regime": (panel["regime"].get(per) if panel is not None and "regime" in panel else None),
            "break_2022Q3": "post" if per >= pd.Period(BREAK_QUARTER, "Q") else "pre",
            "nordic_rev_ttm_usdm": round(nordic_tot, 1), "nordic_consumer_ttm_usdm": round(nordic_cons, 1),
            "nordic_proprietary_pct_of_rev": round(float(prop_ttm / nordic_tot * 100), 1) if not pd.isna(prop_ttm) else np.nan,
            "nordic_proprietary_q_usdm": float(prop_q.get(q, np.nan)),
            "logi_periph_ttm_usdm": round(tot_l, 1), "mix_pointing": round(mix["pointing_usdm"], 3), "mix_keyboards": round(mix["keyboards_usdm"], 3),
            "mix_gaming": round(mix["gaming_usdm"], 3), "wireless_share_mix_weighted": round(wl_mix, 3),
            "socket_cohort": ss["cohort"], "socket_n": ss["n"], "socket_k_nordic": ss["k"],
            "socket_low": round(ss["low"], 3), "socket_mid": round(ss["mid"], 3), "socket_high": round(ss["high"], 3), "socket_evidence": ss["evidence"],
            "nordic_content_pct_of_logi_sales_p50": round(float(np.median(logi) / tot_l * 100), 2),
            "logitech_usdm_p10": round(float(np.percentile(logi, 10)), 1), "logitech_usdm_p50": round(float(np.percentile(logi, 50)), 1), "logitech_usdm_p90": round(float(np.percentile(logi, 90)), 1),
            "ifrs834_cap_usdm": round(cap, 1), "cap_source": cap_src, "cap_status": cap_status, "share_of_draws_over_cap": round(float((logi > cap).mean()), 3),
            "gn_usdm_p50": round(float(np.median(gn)), 1),
            "share_total_indirect_p10": round(float(np.percentile(pct(logi), 10)), 2), "share_total_indirect_p50": round(float(np.percentile(pct(logi), 50)), 2), "share_total_indirect_p90": round(float(np.percentile(pct(logi), 90)), 2),
            "share_total_direct_p50": round(float(np.percentile(pct(logi_direct), 50)), 2),
            "share_total_mixed_p50": round(float(np.percentile(pct(logi_mixed), 50)), 2),
            "share_consumer_indirect_p50": round(float(np.percentile((logi + gn) / nordic_cons * 100, 50)), 2),
        })
    path = pd.DataFrame(rows)
    return path


def write_path(path: pd.DataFrame) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "attribution_path.csv"
    path.to_csv(f, index=False)
    return f


def path_summary_md(path: pd.DataFrame) -> list[str]:
    if path.empty:
        return ["## Attribution path\n", "no quarters with both Logitech category sales and Nordic segment data", ""]
    pre = path[path["break_2022Q3"] == "pre"]; post = path[path["break_2022Q3"] == "post"]
    peak = path.loc[path["share_total_indirect_p50"].idxmax()]
    last = path.iloc[-1]
    md = ["## Attribution path (time-varying; `outputs/attribution_path.csv`)\n",
          "The share is not a constant: the back-test and the forecast read this path, not the headline number. Three drivers are observed per quarter — "
          "Nordic's own TTM revenue (denominator), Logitech's category mix (wireless weight), and the Nordic socket share of the design cohort in the market "
          "(FCC grants of the last three years). The IFRS 8.34 cap is applied with the year it is evidenced for.\n",
          "| quarter | regime | Nordic TTM $m | Logitech periph TTM $m | socket cohort (k/n) | Logitech $m p50 | cap $m (status) | share of Nordic total, indirect p10/p50/p90 | direct p50 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for _, r in path.iterrows():
        md.append(f"| {r['quarter']} | {r['regime']} | {r['nordic_rev_ttm_usdm']:.0f} | {r['logi_periph_ttm_usdm']:.0f} | {r['socket_cohort']} ({r['socket_k_nordic']}/{r['socket_n']}) | "
                  f"{r['logitech_usdm_p50']:.0f} | {r['ifrs834_cap_usdm']:.0f} ({r['cap_status']}) | {r['share_total_indirect_p10']:.1f} / {r['share_total_indirect_p50']:.1f} / {r['share_total_indirect_p90']:.1f} | {r['share_total_direct_p50']:.1f} |")
    md += ["", f"Reading: the indirect-route share peaks at {peak['share_total_indirect_p50']:.0f}% in {peak['quarter']} — the destock trough, when Nordic's broad-market revenue "
           f"collapsed faster than Logitech's sell-in — and is {last['share_total_indirect_p50']:.0f}% in {last['quarter']}. Pre-break ({pre['quarter'].iloc[0] if len(pre) else '—'}–{pre['quarter'].iloc[-1] if len(pre) else '—'}) the median share was "
           f"{pre['share_total_indirect_p50'].median():.0f}%, post-break {post['share_total_indirect_p50'].median():.0f}%; Nordic's proprietary-2.4GHz line was "
           f"{path['nordic_proprietary_pct_of_rev'].dropna().iloc[0]:.0f}% of revenue at the start of the path and {path['nordic_proprietary_pct_of_rev'].dropna().iloc[-1]:.0f}% at its last disclosure. "
           "Socket cohorts before 2023 are extrapolated from the 2023-24 grants with the prior's low end as the floor (flagged in `socket_evidence`); "
           "the cap is evidenced from AR2025 for 2024-25 only and assumed earlier (`cap_status`).", ""]
    return md


# ----------------------------------------------------------------------------- consumers of the path (steps 4, 6, 7)
def share_series(path: pd.DataFrame, p: pd.DataFrame, col: str = "share_total_indirect_p50") -> pd.Series:
    """The time-varying share as a Series on the panel's PeriodIndex; quarters before the path start take the first value,
    quarters after the last take the last (forecast horizon). The path CSV is the record of what is observed vs carried."""
    s = pd.Series(path[col].values, index=pd.PeriodIndex(path["quarter"], freq="Q"))
    return s.reindex(p.index).ffill().bfill()


def time_varying_driver(p: pd.DataFrame, path: pd.DataFrame, driver_col: str) -> pd.Series:
    """Logitech YoY re-weighted by Logitech's share of Nordic at that quarter relative to the latest quarter: 1pt of Logitech
    YoY in 2024Q2 (share ~21%) should move Nordic more than 1pt in 2026Q2 (share ~17%). Used as the regression driver in
    step 6 and step 7 next to the constant-share driver; the leave-one-out RMSE says which one the data prefers."""
    s = share_series(path, p)
    return (p[driver_col] * s / float(s.iloc[-1])).rename(f"{driver_col}_tv")


def implied_content_series(p: pd.DataFrame, path: pd.DataFrame) -> pd.Series:
    """Quarterly Nordic dollars implied by Logitech's radio-core sales at the path's content ratio (USD m) — a LEVEL series
    to compare with Nordic consumer revenue at lags (step 4)."""
    c = share_series(path, p, "nordic_content_pct_of_logi_sales_p50") / 100
    return (p["logi_radio_core"] * c).rename("logi_implied_nordic_usdm")
