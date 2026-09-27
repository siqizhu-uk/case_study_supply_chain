"""Step 3b — channel-inventory index from the disclosed sell-through minus sell-in gap.

Nobody publishes channel weeks-on-hand for Logitech or GN, but both say, most quarters, how much faster sell-through
grew than sell-in (percentage points of YoY growth). That is enough to rebuild the CHANGE in channel stock, exactly:

  flow identity        I_t - I_{t-1} = S_t - T_t = F_t          (channel stock, sell-in S, sell-through T, net fill F)
  YoY disclosure       S_t = S_{t-4}(1 + g_in),  T_t = T_{t-4}(1 + g_out),  gap_t = g_out - g_in
  =>                   F_t = F_{t-4}(1 + g_out) - gap_t * S_{t-4}                                   (exact)

The naive reading F_t = -gap_t * S_{t-4} drops the first term: it treats the year-ago quarter as balanced. When the
year-ago quarter was a drain (2023) the naive reading calls the lapping of that drain a 'build' (2024). Logitech's
CFO made exactly this point on the Q4 FY24 call ('2 points of that is simply comparing the channel inventory
year-over-year', data/manual/logitech_2024Q1.txt).

F is measured relative to the normal seasonal pattern (F = 0 before `start`: assumption A1, decision D5). The level
X_t = sum of F is known up to a constant, pinned by the quarters in which management said the channel was at target
(anchors, decision D7): the constant makes the mean excess at the anchors zero, and the spread of the anchor readings
(rms, in weeks) is the index's own error bar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WEEKS_Q = 13.0


def excess_fill(sell_in: pd.Series, gap_pts: pd.Series, start: str, g_in_pct: pd.Series | None = None,
                missing_gap_pts: float = 0.0) -> pd.DataFrame:
    """Exact recursion F_t = F_{t-4}(1+g_out) - gap*S_{t-4}; F = 0 for quarters before `start`.
    `g_in_pct` overrides the sell-in growth computed from `sell_in` (GN discloses ORGANIC growth, not reported)."""
    s = sell_in.astype(float)
    g_in = (g_in_pct if g_in_pct is not None else (s / s.shift(4) - 1) * 100) / 100
    st = pd.Period(start, "Q")
    gap = gap_pts.reindex(s.index)
    gap = gap.where(s.index < st, gap.fillna(missing_gap_pts)) / 100          # no disclosure after start -> no material gap (D6)
    g_out = g_in + gap
    fill = pd.Series(0.0, index=s.index)
    for i, q in enumerate(s.index):
        if q < st or i < 4 or pd.isna(gap.iloc[i]) or pd.isna(g_in.iloc[i]):
            continue
        fill.iloc[i] = fill.iloc[i - 4] * (1 + g_out.iloc[i]) - gap.iloc[i] * s.iloc[i - 4]
    out = pd.DataFrame({"sell_in": s, "g_in_pct": g_in * 100, "gap_pts": gap * 100, "g_out_pct": g_out * 100,
                        "fill_naive": -gap * s.shift(4), "fill_exact": fill})
    out.loc[out.index < st, ["fill_naive", "fill_exact"]] = np.nan
    out["level_raw"] = out["fill_exact"].cumsum()
    return out


def anchor_level(level: pd.Series, sell_in: pd.Series, anchors: list[str]) -> tuple[pd.DataFrame, dict]:
    """Shift the level so the anchors average zero; express it in weeks of sell-in (S_t / 13 per week)."""
    aq = [pd.Period(a, "Q") for a in anchors if pd.Period(a, "Q") in level.dropna().index]
    const = float(level.loc[aq].mean()) if aq else 0.0
    exc = level - const
    weeks = exc / (sell_in / WEEKS_Q)
    out = pd.DataFrame({"excess_usd": exc, "excess_weeks": weeks})
    at = weeks.loc[aq] if aq else pd.Series(dtype=float)
    disp = {"anchors_used": [str(q) for q in aq], "constant": const,
            "anchor_weeks": {str(q): round(float(v), 2) for q, v in at.items()},
            "rms_weeks": float(np.sqrt(np.mean(np.square(at)))) if len(at) else float("nan"),
            "max_abs_weeks": float(at.abs().max()) if len(at) else float("nan")}
    return out, disp


def logitech_index(p: pd.DataFrame, spec: dict, start: str | None = None) -> dict:
    st = start or spec["start"]
    f = excess_fill(p["logi_sales"], p["logi_st_gap"], st, missing_gap_pts=spec["missing_gap_pts"])
    lvl, disp = anchor_level(f["level_raw"], p["logi_sales"], spec["anchors"])
    return {"table": f.join(lvl), "anchor_fit": disp, "start": st, "currency": "USDm"}


def gn_index(p: pd.DataFrame, spec: dict) -> dict:
    f = excess_fill(p["gn_enterprise_dkk"], p["gn_st_gap"], spec["start"], g_in_pct=p["gn_enterprise_org"],
                    missing_gap_pts=spec["missing_gap_pts"])
    lvl, disp = anchor_level(f["level_raw"], p["gn_enterprise_dkk"], spec["anchors"])
    return {"table": f.join(lvl), "anchor_fit": disp, "start": spec["start"], "currency": "DKKm"}


def build_channel(p: pd.DataFrame, cfg: dict) -> dict:
    """Primary Logitech index = the start whose anchor readings agree best (smaller rms); the other is the sensitivity."""
    ci = cfg["inventory_mechanism"]["channel_index"]
    a = logitech_index(p, ci["logitech"])
    b = logitech_index(p, ci["logitech"], start=ci["logitech"]["alt_start"])
    primary, alt = (a, b) if a["anchor_fit"]["rms_weeks"] <= b["anchor_fit"]["rms_weeks"] else (b, a)
    primary["choice"] = (f"start {primary['start']} (anchor rms {primary['anchor_fit']['rms_weeks']:.2f} wk) preferred to "
                         f"start {alt['start']} (rms {alt['anchor_fit']['rms_weeks']:.2f} wk)")
    return {"logitech": primary, "logitech_alt": alt, "gn": gn_index(p, ci["gn"])}
