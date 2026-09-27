"""Step 6f: is the channel slope a property of Nordic or of the cycle? Same factor, same scale, estimated per cycle window
on the peers (2008-10 from the release history, 2011+ from the main panel) and on Nordic inside its own window.

    y_it = beat_it - mean_i(beat within the window)         (firm fixed effect, window by window)
    x_t  = sign * (Microchip distributor days change at t-1) / sd(full 2008-2026 series)
    y_it = b * x_t + e_it                                    b: pts of beat per 1 sd of the (lagged) channel change

x is common to all firms, so each window holds as many independent observations as QUARTERS, not firm-quarters. Two
estimates are shown: pooled with SE clustered by quarter, and the quarter-level regression of the cross-firm mean y on x
(n = quarters) - the honest one when clusters are few.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT
from peer_panel import _q

PIPE_D = ROOT / "pipelines" / "D_peer_panel" / "data" / "raw"
PIPE_A = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"


def industry_x(cfg: dict) -> pd.Series:
    """Lagged change in Microchip distributor days on one fixed scale (long history from 2007)."""
    m = pd.read_csv(PIPE_A / "mchp_distributor_days_long.csv")
    s = pd.Series(m["disti_days"].values, index=_q(m["quarter"])).sort_index()
    ch = s.asfreq("Q").diff()
    return (cfg["cycle_test"]["sign"] * ch / ch.std(ddof=1)).shift(1).rename("x")


def peer_beats() -> pd.DataFrame:
    """Main panel (2011+) and the 2008-10 history window, structural breaks removed; one row per firm-quarter."""
    frames = []
    for f in ("peer_panel.csv", "peer_history_panel.csv"):
        p = pd.read_csv(PIPE_D / f)
        frames.append(p.loc[~p["excluded"], ["company", "quarter", "beat_pct"]].assign(source=f))
    d = pd.concat(frames, ignore_index=True)
    d["quarter"] = _q(d["quarter"])
    return d.drop_duplicates(["company", "quarter"], keep="first")


def _slopes(d: pd.DataFrame, min_firms: int) -> dict:
    """d: company, quarter, y (demeaned within firm), x. Pooled OLS through the origin with quarter-clustered SE, and the
    quarter-level regression (mean y per quarter on x, with intercept)."""
    d = d.dropna(subset=["y", "x"])
    x, y = d["x"].values, d["y"].values
    b = float(x @ y / (x @ x))
    e = y - b * x
    g = d.assign(s=x * e).groupby("quarter")["s"].sum().values
    G = len(g)
    se = float(np.sqrt((g @ g) / (x @ x) ** 2 * G / max(G - 1, 1)))
    qm = d.groupby("quarter").agg(y=("y", "mean"), x=("x", "first"), n=("y", "size"))
    qm = qm[qm["n"] >= min_firms]
    out = {"firm_quarters": len(d), "firms": d["company"].nunique(), "quarters": G, "b_pooled": b, "se_clustered": se}
    if len(qm) >= 4:
        X = np.column_stack([np.ones(len(qm)), qm["x"]])
        c, *_ = np.linalg.lstsq(X, qm["y"].values, rcond=None)
        r = qm["y"].values - X @ c
        cov = (r @ r) / (len(qm) - 2) * np.linalg.inv(X.T @ X)
        rho = float(qm["x"].autocorr(1)) if len(qm) > 3 else 0.0
        n_eff = len(qm) * (1 - rho) / (1 + rho) if rho > 0 else float(len(qm))
        se_q = float(np.sqrt(cov[1, 1]))
        contrib = (qm["x"] - qm["x"].mean()) * (qm["y"] - qm["y"].mean())          # each quarter's share of the slope's numerator
        top = contrib.sort_values(ascending=False).head(3)
        out.update({"quarters_q_level": len(qm), "b_quarter_level": float(c[1]), "se_quarter_level": se_q,
                    "x_rho1": rho, "n_eff": n_eff, "se_q_level_neff": se_q * float(np.sqrt(len(qm) / max(n_eff, 2))),
                    "top3_share": float(top.sum() / contrib.sum()) if contrib.sum() > 0 else np.nan,
                    "top3_quarters": ", ".join(str(q) for q in top.index), "x_sd_in_window": float(qm["x"].std(ddof=1))})
    return out


def cycle_stability(s3: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    ct = cfg["cycle_test"]
    x = industry_x(cfg)
    peers = peer_beats()
    peers["x"] = peers["quarter"].map(x)
    nord = pd.DataFrame({"beat_pct": s3["nordic_beat_vs_guide_pct"]}).dropna()
    nord.index = pd.PeriodIndex(nord.index, freq="Q")
    nord = nord.assign(company="NORDIC", quarter=nord.index, x=nord.index.map(x)).reset_index(drop=True).dropna(subset=["x"])
    windows = dict(ct["windows"])
    windows["nordic_window"] = {"from": str(nord["quarter"].min()), "to": str(nord["quarter"].max()),
                                "reason": "the quarters Nordic's own slope is estimated on"}
    rows = []
    for name, w in windows.items():
        lo, hi = pd.Period(w["from"], "Q"), pd.Period(w["to"], "Q")
        for who, d in (("peers", peers), ("NORDIC", nord)):
            if who == "NORDIC" and name != "nordic_window":
                continue
            sub = d[(d["quarter"] >= lo) & (d["quarter"] <= hi)].copy()
            if sub.empty:
                continue
            sub["y"] = sub["beat_pct"] - sub.groupby("company")["beat_pct"].transform("mean")
            rows.append({"window": name, "from": w["from"], "to": w["to"], "who": who, "reason": w["reason"],
                         **_slopes(sub, 1 if who == "NORDIC" else ct["min_firms_per_quarter"])})
    t = pd.DataFrame(rows)
    nw = t[t["window"] == "nordic_window"].set_index("who")
    if {"peers", "NORDIC"} <= set(nw.index):
        d = nw.loc["NORDIC", "b_quarter_level"] - nw.loc["peers", "b_quarter_level"]
        for lab, col in (("naive", "se_quarter_level"), ("n_eff", "se_q_level_neff")):
            se = float(np.hypot(nw.loc["NORDIC", col], nw.loc["peers", col]))
            t.attrs[f"gap_{lab}"] = {"gap": float(d), "se": se, "t": float(d / se)}
        t.attrs["cycle_share_of_nordic"] = float(nw.loc["peers", "b_quarter_level"] / nw.loc["NORDIC", "b_quarter_level"])
    return t
