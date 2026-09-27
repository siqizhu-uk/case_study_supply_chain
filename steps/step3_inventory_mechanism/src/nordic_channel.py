"""Nordic's own channel (D25, P128). Nordic discloses no channel weeks; two Nordic-specific readings stand in for them,
and the Microchip distributor-days proxy is compared with them.

1. Annual size, from the stock-flow identity (channel change = sell-in - sell-through): Nordic's top-10 customers,
   served mostly direct, stand in for sell-through growth; the broad market's (mostly distribution) growth beyond
   theirs is the distribution route's channel change = gap x last year's broad-market revenue, and in weeks of last
   year's broad-market sales. Arrow / Avnet's all-vendor cover over the same years shows how much of it distributors
   could have held.
2. Quarterly direction: Nordic's own words about its distributors' stock in each report (coded -1 destocking to +1
   adding; a flow), cumulated into a level index and correlated with Microchip's distributor days (a stock) at
   shifts of -4..+4 quarters."""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import step_outputs

OUT_NAME = "step3_inventory_mechanism"
WEEKS_PER_YEAR = 52
SHIFTS = range(-4, 5)


def _by_str(x: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    return x.set_axis([str(i) for i in x.index])


def annual_size(conc: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """Implied change in the distribution route's channel stock per year, with the distributors' own cover beside it."""
    c = conc.reset_index() if "year" not in conc.columns else conc.copy()
    c = c.sort_values("year").reset_index(drop=True)
    prev_broad = c["broad_usdm"].shift(1)
    gap = c["broad_yoy_pct"] - c["top10_yoy_pct"]
    change = gap / 100 * prev_broad
    q = _by_str(f[["arrow_dio", "avnet_dio"]]) / 7
    year_end = q[q.index.str.endswith("Q4")].set_axis([int(i[:4]) for i in q.index if i.endswith("Q4")])
    out = pd.DataFrame({
        "year": c["year"], "top10_basis": c["top10_basis"],
        "top10_estimated": ~c["top10_basis"].astype(str).str.contains("disclosed"),
        "top10_yoy_pct": c["top10_yoy_pct"], "broad_yoy_pct": c["broad_yoy_pct"],
        "gap_pts": gap.round(1), "channel_change_usdm": change.round(1),
        "weeks_of_prior_year_broad_sales": (change / (prev_broad / WEEKS_PER_YEAR)).round(1),
    })
    out["cum_change_usdm"] = out["channel_change_usdm"].fillna(0).cumsum().where(out["channel_change_usdm"].notna()).round(1)
    out["arrow_weeks_q4"] = out["year"].map(year_end["arrow_dio"]).round(1)
    out["avnet_weeks_q4"] = out["year"].map(year_end["avnet_dio"]).round(1)
    return out


def wording_vs_microchip(p: pd.DataFrame, states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Nordic's coded wording (flow), its cumulated level, and Microchip's days and state, quarter by quarter; and the
    correlation of the level with Microchip's days when Microchip is moved k quarters (k > 0: Microchip earlier)."""
    word = _by_str(p["nordic_dist_state"]).dropna()
    st = _by_str(states)
    q = pd.DataFrame({"nordic_wording": word, "nordic_level_index": word.cumsum()})
    q = q.join(st[["days", "state", "state_nordic"]].rename(columns={"days": "mchp_days", "state": "mchp_state"}))
    days = st["days"]
    rows = []
    for k in SHIFTS:
        x = pd.concat([q["nordic_level_index"], days.shift(k).reindex(q.index)], axis=1).dropna()
        rows.append({"mchp_shift_q": k, "n": len(x), "corr_level_vs_mchp_days": round(float(x.corr().iloc[0, 1]), 2)})
    return q, pd.DataFrame(rows)


def run_nordic_channel(conc: pd.DataFrame, f: pd.DataFrame, p: pd.DataFrame, states: pd.DataFrame, write: bool = True) -> dict:
    size = annual_size(conc, f)
    q, shifts = wording_vs_microchip(p, states)
    if write:
        d = step_outputs(OUT_NAME)
        size.to_csv(d / "nordic_channel_size.csv", index=False)
        q.to_csv(d / "nordic_wording_vs_microchip.csv", index_label="quarter")
        shifts.to_csv(d / "nordic_wording_vs_microchip_shifts.csv", index=False)
    return {"size": size, "quarterly": q, "shifts": shifts}
