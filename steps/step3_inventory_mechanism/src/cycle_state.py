"""Step 3b: which phase of the inventory cycle the channel is in, read from the mechanism data (decision D22).

The regime used to be a set of hand-typed date windows. Here it is classified every quarter from component-distributor
inventory: Microchip's distributor days (2007-2026), confirmed by Arrow / Avnet inventory days (2020-2026).
    building   days rising >= +3 over two quarters: distributors accumulate stock, sell-through slows, orders to chip
               makers are cut next (2022Q4-2024Q2 in the data; the hand-set 'destock')
    drawdown   days falling <= -3 from an above-normal level: excess stock worked down, orders below sell-through
    lean       level well below its own history (z <= -1), or falling from a normal / low level (tightening, as in the
               2020Q4-2021Q3 shortage): sell-in can run ahead of sell-through
    shortage   (Nordic only, column state_nordic, D24) a lean quarter with supply-side evidence of unmet demand: order
               backlog above two quarters of revenue, or a live lead time above 26 weeks
    normal     none of the above
The level is z-scored against the history known at that quarter (expanding median / IQR), so a state never uses later
data. What a state means for the forecast is measured, not assumed: guidance misses of the 12 peers and of Nordic,
grouped by the state of t-1, with standard errors clustered by quarter. Timing: Microchip files the days for t-1 in its
10-Q ~5-6 weeks after t-1 ends - after most guides for t are set, before the actual for t is reported - so t-1 is
point in time at the forecast date, not necessarily at the guide date (t-2 is; the finding holds with t-2, see D22).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT, step_outputs

MCHP = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "mchp_distributor_days_long.csv"
PEERS = [ROOT / "pipelines" / "D_peer_panel" / "data" / "raw" / f for f in ("peer_panel.csv", "peer_history_panel.csv")]
FACTORS = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "factors_quarterly.csv"
NORDIC_Q = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_quarterly.csv"
NORDIC_BACKLOG = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_backlog_history.csv"
SNAPSHOTS = ROOT / "pipelines" / "C_realtime_channel" / "data" / "raw" / "channel_snapshots.csv"


def load_signal(cfg: dict) -> pd.Series:
    m = pd.read_csv(MCHP).drop_duplicates("quarter", keep="last")
    s = pd.Series(m["disti_days"].values, index=pd.PeriodIndex(m["quarter"], freq="Q"), dtype=float).sort_index()
    return s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="Q"))


def classify(d: pd.Series, cfg: dict) -> pd.DataFrame:
    c = cfg["cycle_state"]
    out = pd.DataFrame({"days": d})
    med = d.expanding(min_periods=c["min_history"]).median()
    iqr = d.expanding(min_periods=c["min_history"]).quantile(0.75) - d.expanding(min_periods=c["min_history"]).quantile(0.25)
    out["z_point_in_time"] = (d - med) / (iqr / 1.349).clip(lower=c["min_scale_days"])
    out["change_days"] = d - d.shift(c["change_quarters"])
    falling = out["change_days"] <= c["drawdown_max_change_days"]
    excess_before = out["z_point_in_time"].shift(c["change_quarters"]) > c["drawdown_requires_prior_z_above"]
    rules = {"building": out["change_days"] >= c["building_min_change_days"],
             "drawdown": falling & excess_before,
             "lean": (out["z_point_in_time"] <= c["lean_max_z"]) | (falling & ~excess_before),
             "normal": pd.Series(True, index=out.index)}
    state = pd.Series(np.nan, index=out.index, dtype=object)
    for name in reversed(c["priority"]):                     # lowest priority first, overwritten by higher ones
        state[rules[name].fillna(False)] = name
    state[out["z_point_in_time"].isna() | out["change_days"].isna()] = np.nan
    out["state"] = state
    return out


def supply_evidence(index: pd.PeriodIndex) -> pd.DataFrame:
    """Nordic's supply-side evidence of unmet demand per quarter (D24): order backlog in quarters of revenue while it was
    disclosed (2020Q4-2023Q1; each figure published with that quarter's report, so point in time), and the latest
    authorized-distributor lead time, which is known at the forecast date and so stands for the latest classified quarter."""
    out = pd.DataFrame(index=index, columns=["backlog_x_rev", "lead_time_weeks"], dtype=float)
    frames = []
    for f in (NORDIC_BACKLOG, NORDIC_Q):
        if f.exists():
            d = pd.read_csv(f)
            rev = "revenue_usdm" if "revenue_usdm" in d else None
            if rev and "backlog_usdm" in d:
                d = d.dropna(subset=["backlog_usdm", rev])
                frames.append(pd.Series((d["backlog_usdm"] / d[rev]).values, index=pd.PeriodIndex(d["quarter"], freq="Q")))
    if frames:
        b = pd.concat(frames)
        b = b[~b.index.duplicated(keep="last")]
        out["backlog_x_rev"] = b.reindex(index)
    if SNAPSHOTS.exists() and len(index):
        c = pd.read_csv(SNAPSHOTS)
        c = c[c["authorized"].astype(str).str.lower().isin(["true", "1", "yes"])] if "authorized" in c else c
        lt = c.dropna(subset=["lead_time"])
        if len(lt):
            latest = lt[lt["snapshot_date"] == lt["snapshot_date"].max()]["lead_time"].astype(float).max()
            out.loc[index[-1], "lead_time_weeks"] = latest
    return out


def shortage_overlay(states: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """state_nordic = 'shortage' where the industry state is lean AND Nordic's supply evidence shows unmet demand (D24);
    otherwise the industry state. No evidence (no backlog disclosed, no lead-time reading) = no shortage."""
    c = cfg["cycle_state"]["shortage"]
    ev = supply_evidence(states.index)
    out = states.join(ev)
    short = (out["backlog_x_rev"] > c["backlog_min_quarters_of_revenue"]) | (out["lead_time_weeks"] > c["lead_time_min_weeks"])
    out["state_nordic"] = out["state"].where(~((out["state"] == "lean") & short.fillna(False)), "shortage")
    return out


def transitions(states: pd.DataFrame) -> pd.DataFrame:
    s = states["state"].dropna()
    pairs = pd.DataFrame({"from": s.values[:-1], "to": s.values[1:]})
    return pd.crosstab(pairs["from"], pairs["to"], normalize="index")


def _peer_beats() -> pd.DataFrame:
    frames = [pd.read_csv(f) for f in PEERS if f.exists()]
    d = pd.concat(frames, ignore_index=True)
    d = d[~d["excluded"].fillna(False).astype(bool)].dropna(subset=["beat_pct"])
    d = d.drop_duplicates(["company", "quarter"], keep="first")
    d["q"] = pd.PeriodIndex(d["quarter"], freq="Q")
    return d[["company", "q", "beat_pct"]]


def _clustered_mean(x: pd.Series, cluster: pd.Series) -> tuple[float, float]:
    e = x - x.mean()
    g = e.groupby(cluster.values).sum()
    return float(x.mean()), float(np.sqrt((g ** 2).sum()) / len(x)) if len(x) > 1 else float("nan")


def beat_by_state(states: pd.DataFrame, cfg: dict, nordic: pd.Series | None = None) -> pd.DataFrame:
    """Guidance miss (actual / guide mid - 1, %) grouped by the cycle state known at the forecast date (t - lag)."""
    lag = cfg["cycle_state"]["state_known_lag_quarters"]
    st = states["state"]
    rows = []
    peers = _peer_beats()
    peers["state"] = peers["q"].map(lambda q: st.get(q - lag, np.nan))
    samples = {"peers": peers.dropna(subset=["state"])}
    if nordic is not None:
        n = nordic.dropna()
        samples["nordic"] = pd.DataFrame({"q": n.index, "beat_pct": n.values, "state": [st.get(q - lag, np.nan) for q in n.index]}).dropna()
    for name, d in samples.items():
        for s_, g in d.groupby("state"):
            mean, se = _clustered_mean(g["beat_pct"], g["q"].astype(str))
            rows.append({"sample": name, "state": s_, "n": len(g), "quarters": g["q"].nunique(), "mean_beat_pct": mean,
                         "se_clustered": se, "t": mean / se if se and se == se and se > 0 else np.nan,
                         "sd_pct": float(g["beat_pct"].std(ddof=1)) if len(g) > 1 else np.nan,
                         "share_below_guide_mid": float((g["beat_pct"] < 0).mean())})
    return pd.DataFrame(rows)


def state_contrast(states: pd.DataFrame, cfg: dict, state: str = "building") -> dict:
    """Peers' beat in `state` minus in all other states: OLS on a dummy, standard error clustered by quarter (the cycle is
    common to all firms in a quarter, so firm-quarters in one quarter are not independent)."""
    lag = cfg["cycle_state"]["state_known_lag_quarters"]
    st = states["state"]
    d = _peer_beats()
    d["state"] = d["q"].map(lambda q: st.get(q - lag, np.nan))
    d = d.dropna(subset=["state"]).reset_index(drop=True)
    X = np.column_stack([np.ones(len(d)), (d["state"] == state).astype(float)])
    y = d["beat_pct"].to_numpy(float)
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    xtx = np.linalg.inv(X.T @ X)
    S = np.zeros((2, 2))
    for _, idx in d.groupby("q").indices.items():
        u = (X[idx] * e[idx, None]).sum(0)
        S += np.outer(u, u)
    g = d["q"].nunique()
    V = xtx @ S @ xtx * g / (g - 1)
    se = float(np.sqrt(V[1, 1]))
    return {"state": state, "diff_vs_other_pct": float(b[1]), "se_clustered": se, "t": float(b[1] / se), "n": len(d), "quarters": g}


def confirm_table(states: pd.DataFrame) -> pd.DataFrame:
    """Arrow / Avnet inventory days next to the Microchip-based state (2020 onwards) - do they move together?"""
    if not FACTORS.exists():
        return pd.DataFrame()
    f = pd.read_csv(FACTORS)
    f.index = pd.PeriodIndex(f["quarter"], freq="Q")
    cols = [c for c in ("arrow_dio", "avnet_dio", "comp_dist_dio_avg") if c in f]
    t = states.join(f[cols], how="inner")
    t["comp_change_days"] = t["comp_dist_dio_avg"] - t["comp_dist_dio_avg"].shift(2) if "comp_dist_dio_avg" in t else np.nan
    return t


def run_cycle_state(cfg: dict, nordic_beat: pd.Series | None = None, write: bool = True) -> dict:
    states = shortage_overlay(classify(load_signal(cfg), cfg), cfg)
    tr = transitions(states)
    bbs = beat_by_state(states, cfg, nordic_beat)
    conf = confirm_table(states)
    contrast = state_contrast(states, cfg)
    last = states["state"].dropna()
    now_q, now_s = last.index[-1], last.iloc[-1]
    nxt = tr.loc[now_s] if now_s in tr.index else pd.Series({now_s: 1.0})
    peers = bbs[bbs["sample"] == "peers"].set_index("state")["mean_beat_pct"]
    exp_beat = float(sum(p * peers.get(s_, np.nan) for s_, p in nxt.items() if s_ in peers.index))
    summary = {"latest_quarter": str(now_q), "latest_state": now_s, "next_state_probs": nxt.round(3).to_dict(),
               "expected_peer_beat_next_pct": round(exp_beat, 2),
               "building_vs_other_pct": round(contrast["diff_vs_other_pct"], 2), "building_vs_other_t": round(contrast["t"], 2)}
    if write:
        d = step_outputs("step3_inventory_mechanism")
        states.assign(quarter=states.index.astype(str)).round(3).to_csv(d / "cycle_state.csv", index=False)
        tr.round(3).to_csv(d / "cycle_transitions.csv")
        bbs.round(3).to_csv(d / "beat_by_cycle_state.csv", index=False)
        if len(conf):
            conf.assign(quarter=conf.index.astype(str)).round(2).to_csv(d / "cycle_state_confirm.csv", index=False)
        pd.DataFrame([summary]).to_csv(d / "cycle_state_now.csv", index=False)
    return {"states": states, "transitions": tr, "beat_by_state": bbs, "confirm": conf, "contrast": contrast, "summary": summary}
