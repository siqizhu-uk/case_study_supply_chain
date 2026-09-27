"""Step 6h: does the channel factor forecast REVENUE beyond the guided quarter (h=2) on the peer panel?

    g2_it   = actual_i,t+1 / guide_mid_it - 1                (growth from the guided quarter to the next, in %)
    s_it    = mean of g2_i over past years, same quarter of year  (firm seasonality, known at the origin)
    x_t     = sign * (Microchip distributor-days change at t-1) / sd   (lean channel > 0; known at the end of t)
    model   = s_it + b * x_t,  b from quarters whose target t+1 has already been reported (no look-ahead)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from guidance_optimism import peer_guides, _peer_actuals, PIPE_D


def design(cfg: dict, cfg_d: dict, x: pd.Series) -> pd.DataFrame:
    A = _peer_actuals()
    G = peer_guides(cfg_d)
    G["actual_next"] = [A.get((c, q + 1), np.nan) for c, q in zip(G["company"], G["quarter"])]
    G["g2"] = (G["actual_next"] / G["guide_mid_usdm"] - 1) * 100
    # a structural break (M&A / divestiture) in t+1 makes g2 an acquisition, not growth: drop those rows too
    brk = {(b["company"], b["quarter"]) for b in cfg_d.get("structural_breaks", []) + cfg_d.get("history", {}).get("structural_breaks", [])}
    h2b = {(b["company"], b["quarter"]) for b in cfg_d.get("h2_breaks", [])}
    G = G[[(c, str(q + 1)) not in brk and (c, str(q)) not in h2b for c, q in zip(G["company"], G["quarter"])]]
    G = G.dropna(subset=["g2"]).sort_values(["company", "quarter"])
    G["qoy"] = G["quarter"].map(lambda q: q.quarter)
    mn = cfg["revenue_h2"]["min_seasonal_years"]
    # seasonal mean from past years only: g2 of (t-4, t-8, ...) are all reported before the end of t
    G["s"] = G.groupby(["company", "qoy"])["g2"].transform(lambda v: v.shift(1).expanding(min_periods=mn).mean())
    G["x"] = G["quarter"].map(x)
    return G.assign(y=G["g2"] - G["s"]).reset_index(drop=True)


def unexplained_outliers(G: pd.DataFrame, cfg_d: dict, limit: float = 30.0) -> list[str]:
    """|g2 - seasonal| above `limit` pts must be listed in peers.yaml h2_verified (read by hand) or removed as h2_breaks."""
    ok = {(v["company"], v["quarter"]) for v in cfg_d.get("h2_verified", [])}
    big = G[G["y"].abs() > limit]
    return [f"{c} {q} {y:+.1f}" for c, q, y in zip(big["company"], big["quarter"].astype(str), big["y"]) if (c, q) not in ok]


def walk_forward(G: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """At origin T (end of quarter T): train on rows with quarter <= T-2 (their target T-1 is reported by the end of T)."""
    c = cfg["revenue_h2"]
    rows = []
    for T in sorted(q for q in G["quarter"].unique() if q >= pd.Period(c["first_target"], "Q")):
        tr = G[G["quarter"] <= T - 2].dropna(subset=["y", "x"])
        te = G[G["quarter"] == T].dropna(subset=["y", "x", "s"])
        if tr["quarter"].nunique() < c["min_train_quarters"] or te.empty:
            continue
        b = float(tr["x"] @ tr["y"] / (tr["x"] @ tr["x"]))
        rows.append(te.assign(pred=te["s"] + b * te["x"], b=b))
    return pd.concat(rows, ignore_index=True)


def score(w: pd.DataFrame) -> dict:
    e_m, e_s, e_0 = (w["pred"] - w["g2"]) ** 2, (w["s"] - w["g2"]) ** 2, w["g2"] ** 2
    by_q = w.assign(gain=e_s - e_m).groupby("quarter")["gain"].sum()
    top = by_q.sort_values(ascending=False).head(3)
    return {"firm_quarters": len(w), "quarters": w["quarter"].nunique(), "firms": w["company"].nunique(),
            "rmse_model": float(np.sqrt(e_m.mean())), "rmse_seasonal": float(np.sqrt(e_s.mean())), "rmse_flat": float(np.sqrt(e_0.mean())),
            "oos_r2_vs_seasonal": float(1 - e_m.sum() / e_s.sum()), "quarters_won_share": float((by_q > 0).mean()),
            "top3_gain_share": float(top.sum() / by_q.sum()) if by_q.sum() > 0 else np.nan,
            "top3_quarters": ", ".join(str(q) for q in top.index), "b_last": float(w["b"].iloc[-1])}


def run_revenue_h2(cfg: dict) -> dict:
    import yaml
    from cycle_test import industry_x
    cfg_d = yaml.safe_load((PIPE_D / "config" / "peers.yaml").read_text())
    G = design(cfg, cfg_d, industry_x(cfg))
    w = walk_forward(G, cfg)
    windows = {"all": (None, None), "2014-2019": ("2014Q1", "2019Q4"), "2020-2026": ("2020Q1", "2026Q4")}
    sc = []
    for lab, (lo, hi) in windows.items():
        ww = w if lo is None else w[(w["quarter"] >= pd.Period(lo, "Q")) & (w["quarter"] <= pd.Period(hi, "Q"))]
        sc.append({"window": lab, **score(ww)})
    ep = pd.PeriodIndex(cfg["guidance_optimism"]["episode_quarters"], freq="Q")
    we = w[~w["quarter"].isin(ep)]
    gain = w.assign(d=(w["s"] - w["g2"]) ** 2 - (w["pred"] - w["g2"]) ** 2).groupby("quarter")["d"].mean()
    return {"design": G, "walkforward": w, "scores": pd.DataFrame(sc), "unexplained": unexplained_outliers(G, cfg_d),
            "corr_full": float(G[["x", "y"]].corr().iloc[0, 1]),
            "oos_r2_wo_episode": float(1 - ((we["pred"] - we["g2"]) ** 2).sum() / ((we["s"] - we["g2"]) ** 2).sum()),
            "gain_t": float(gain.mean() / (gain.std(ddof=1) / np.sqrt(len(gain))))}
