"""Step 6g: the beat is management's forecast error, so explain it with how the GUIDE was set, not only with the channel.

    guided growth       g_it   = guide_mid_it / actual_i,t-1 - 1                       (known when the guide is given)
    seasonal norm       n_it   = actual_i,t-4 / actual_i,t-5 - 1                        (same quarter last year)
    excess guided growth e_it  = g_it - n_it                                            (optimism vs own seasonality)
    relative optimism   rel_it = e_it - median_{j != i}(e_jt)                           (optimism vs peers, same quarter)

Every term uses first-reported actuals and guides released before the end of quarter t, i.e. before the firm reports t.
Raw versions (no seasonal norm) are kept as a robustness check.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT
from peer_panel import _q

PIPE_D = ROOT / "pipelines" / "D_peer_panel"
NORDIC_Q = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_quarterly.csv"


def _peer_actuals() -> pd.Series:
    """(company, quarter) -> first-reported revenue: XBRL, else the 2008-10 release figure (narrative = table)."""
    x = pd.read_csv(PIPE_D / "data" / "raw" / "peer_actuals_xbrl.csv")[["company", "quarter", "actual_usdm"]]
    h = pd.read_csv(PIPE_D / "data" / "raw" / "peer_history_releases.csv")
    h = h.loc[h["actual_table_usdm"].notna(), ["company", "reported_quarter", "actual_release_usdm"]]
    h.columns = ["company", "quarter", "actual_usdm"]
    a = pd.concat([x, h], ignore_index=True).drop_duplicates(["company", "quarter"], keep="first")
    a["quarter"] = _q(a["quarter"])
    return a.set_index(["company", "quarter"])["actual_usdm"]


def peer_guides(cfg_d: dict) -> pd.DataFrame:
    """Every parsed peer guide (main + 2008-10 history), structural breaks removed, released before its quarter ends."""
    g = pd.read_csv(PIPE_D / "data" / "raw" / "peer_guidance.csv")
    g = g.loc[g["parsed"], ["company", "guided_quarter", "release_date", "guide_mid_usdm"]]
    h = pd.read_csv(PIPE_D / "data" / "raw" / "peer_history_releases.csv")
    h = h.loc[h["parsed"], ["company", "guided_quarter", "release_date", "guide_mid_usdm"]]
    d = pd.concat([h, g], ignore_index=True)
    d["quarter"] = _q(d["guided_quarter"])
    d = d.sort_values("release_date").drop_duplicates(["company", "quarter"], keep="first")
    brk = {(b["company"], b["quarter"]) for b in cfg_d.get("structural_breaks", []) + cfg_d.get("history", {}).get("structural_breaks", [])}
    d = d[[(c, str(q)) not in brk for c, q in zip(d["company"], d["quarter"])]]
    d = d[pd.to_datetime(d["release_date"]) <= d["quarter"].map(lambda q: q.end_time)]
    return d[["company", "quarter", "release_date", "guide_mid_usdm"]].reset_index(drop=True)


def _growth_terms(d: pd.DataFrame, act) -> pd.DataFrame:
    """Adds guided growth g, seasonal norm n and excess e (in %) given act(company, quarter) -> revenue."""
    a1 = [act(c, q - 1) for c, q in zip(d["company"], d["quarter"])]
    a4 = [act(c, q - 4) for c, q in zip(d["company"], d["quarter"])]
    a5 = [act(c, q - 5) for c, q in zip(d["company"], d["quarter"])]
    d = d.assign(g=(d["guide_mid_usdm"] / np.array(a1, float) - 1) * 100,
                 n=(np.array(a4, float) / np.array(a5, float) - 1) * 100)
    return d.assign(e=d["g"] - d["n"])


def peer_terms(cfg_d: dict) -> pd.DataFrame:
    A = _peer_actuals()
    act = lambda c, q: A.get((c, q), np.nan)       # noqa: E731
    return _growth_terms(peer_guides(cfg_d), act)


def nordic_terms() -> pd.DataFrame:
    n = pd.read_csv(NORDIC_Q)
    n["quarter"] = _q(n["quarter"])
    n = n.set_index("quarter")
    d = pd.DataFrame({"company": "NORDIC", "quarter": n.index, "guide_mid_usdm": (n["guide_low_usdm"] + n["guide_high_usdm"]).values / 2,
                      "guide_width_pct": ((n["guide_high_usdm"] - n["guide_low_usdm"]) / ((n["guide_low_usdm"] + n["guide_high_usdm"]) / 2) * 100).values})
    d = d.dropna(subset=["guide_mid_usdm"]).reset_index(drop=True)
    rev = n["revenue_usdm"]
    d = _growth_terms(d, lambda c, q: rev.get(q, np.nan))
    bl = n["backlog_usdm"]
    d["backlog_cover"] = [bl.get(q - 1, np.nan) / m for q, m in zip(d["quarter"], d["guide_mid_usdm"])]
    return d


def relative(d: pd.DataFrame, peers: pd.DataFrame, col: str, min_peers: int) -> pd.Series:
    """col_it - median over OTHER peers of col_jt in the same quarter (NaN with fewer than min_peers)."""
    out = []
    for c, q, v in zip(d["company"], d["quarter"], d[col]):
        o = peers.loc[(peers["quarter"] == q) & (peers["company"] != c), col].dropna()
        out.append(v - o.median() if len(o) >= min_peers else np.nan)
    return pd.Series(out, index=d.index)


# ------------------------------------------------------------------ fits
def _ols(d: pd.DataFrame, y: str, xs: list[str]) -> dict:
    d = d[[y] + xs].dropna()
    A = np.column_stack([np.ones(len(d))] + [d[c].values for c in xs])
    b, *_ = np.linalg.lstsq(A, d[y].values, rcond=None)
    r = d[y].values - A @ b
    se = np.sqrt(np.diag((r @ r) / (len(d) - A.shape[1]) * np.linalg.inv(A.T @ A)))
    out = {"n": len(d), "r2": 1 - (r @ r) / ((d[y] - d[y].mean()) ** 2).sum()}
    for i, c in enumerate(xs):
        out[f"b_{c}"], out[f"t_{c}"] = float(b[i + 1]), float(b[i + 1] / se[i + 1])
    return out


def _clustered(d: pd.DataFrame, xs: list[str]) -> dict:
    """Pooled OLS of y on xs (no intercept: y is already net of the firm's past mean), SE clustered by quarter."""
    d = d.dropna(subset=["y"] + xs)
    A, y = d[xs].values, d["y"].values
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    e = y - A @ b
    inv = np.linalg.inv(A.T @ A)
    meat = sum(np.outer(v, v) for v in (A[m].T @ e[m] for m in (d["quarter"] == q for q in d["quarter"].unique())))
    G = d["quarter"].nunique()
    se = np.sqrt(np.diag(inv @ meat @ inv) * G / max(G - 1, 1))
    return {"firm_quarters": len(d), "quarters": G, **{f"b_{c}": float(b[i]) for i, c in enumerate(xs)},
            **{f"t_{c}": float(b[i] / se[i]) for i, c in enumerate(xs)}}


def peer_beats() -> pd.DataFrame:
    b = pd.concat([pd.read_csv(PIPE_D / "data" / "raw" / f) for f in ("peer_panel.csv", "peer_history_panel.csv")])
    b = b[~b["excluded"]].copy()
    b["quarter"] = _q(b["quarter"])
    return b.drop_duplicates(["company", "quarter"])[["company", "quarter", "beat_pct"]]


def panel_design(cfg: dict, cfg_d: dict, x: pd.Series) -> pd.DataFrame:
    go = cfg["guidance_optimism"]
    P = peer_terms(cfg_d)
    P["rel_raw"], P["rel_seasonal"] = relative(P, P, "g", go["min_peers"]), relative(P, P, "e", go["min_peers"])
    D = P.merge(peer_beats(), on=["company", "quarter"]).sort_values(["company", "quarter"])
    D["fe"] = D.groupby("company")["beat_pct"].transform(lambda s: s.shift(1).expanding().mean())     # past mean only
    return D.assign(y=D["beat_pct"] - D["fe"], x_channel=D["quarter"].map(x))


def panel_tests(D: pd.DataFrame, cfg: dict) -> dict:
    go = cfg["guidance_optimism"]
    fits = [{"spec": " + ".join(xs), **_clustered(D, xs)} for xs in (["rel_raw"], ["rel_seasonal"], ["g"], ["rel_raw", "x_channel"])]
    for lo, hi in (("2008Q3", "2010Q4"), ("2011Q1", "2019Q4"), ("2020Q1", "2026Q4")):
        w = D[(D["quarter"] >= pd.Period(lo, "Q")) & (D["quarter"] <= pd.Period(hi, "Q"))]
        fits.append({"spec": f"rel_raw, {lo}-{hi}", **_clustered(w, ["rel_raw"])})
    rows = []
    for T in sorted(q for q in D["quarter"].unique() if q >= pd.Period(go["first_target"], "Q")):
        tr = D[D["quarter"] < T].dropna(subset=["y", "rel_raw"])
        te = D[D["quarter"] == T].dropna(subset=["y", "rel_raw"])
        if tr["quarter"].nunique() < go["min_train_quarters"] or te.empty:
            continue
        b = float(tr["rel_raw"] @ tr["y"] / (tr["rel_raw"] @ tr["rel_raw"]))
        rows.append(te.assign(pred=te["fe"] + b * te["rel_raw"], b=b))
    w = pd.concat(rows)
    oos = 1 - ((w["pred"] - w["beat_pct"]) ** 2).sum() / ((w["fe"] - w["beat_pct"]) ** 2).sum()
    q = D.dropna(subset=["rel_raw", "y"]).assign(quintile=lambda d: pd.qcut(d["rel_raw"], 5, labels=[1, 2, 3, 4, 5]))
    quint = q.groupby("quintile", observed=True).agg(rel_optimism_pts=("rel_raw", "mean"), beat_vs_firm_mean=("y", "mean"),
                                                     miss_rate=("beat_pct", lambda s: (s < 0).mean()), n=("y", "size")).reset_index()
    return {"fits": pd.DataFrame(fits), "oos_r2": float(oos), "oos_n": len(w), "quintiles": quint,
            "corr_rel_channel": float(D[["rel_raw", "x_channel"]].corr().iloc[0, 1])}


def cycle_in_guide(cfg: dict) -> dict:
    """Peers: how much of the revenue cycle reaches the beat? sd of revenue YoY vs sd of beat; deep-decline quarters."""
    act = pd.read_csv(PIPE_D / "data" / "raw" / "peer_actuals_xbrl.csv").sort_values(["company", "quarter"])
    act["yoy"] = act.groupby("company")["actual_usdm"].pct_change(4, fill_method=None) * 100
    act["quarter"] = _q(act["quarter"])
    K = peer_beats().merge(act[["company", "quarter", "yoy"]], on=["company", "quarter"]).dropna(subset=["yoy"])
    deep = K[K["yoy"] <= cfg["guidance_optimism"]["deep_decline_yoy_pct"]]
    return {"n": len(K), "sd_yoy": float(K["yoy"].std()), "sd_beat": float(K["beat_pct"].std()),
            "corr_yoy_beat": float(K[["yoy", "beat_pct"]].corr().iloc[0, 1]), "deep_n": len(deep),
            "deep_mean_beat": float(deep["beat_pct"].mean()), "deep_within5": float((deep["beat_pct"].abs() < 5).mean()),
            "all_within5": float((K["beat_pct"].abs() < 5).mean())}


def nordic_table(cfg: dict, cfg_d: dict, x: pd.Series, Xc: pd.DataFrame) -> pd.DataFrame:
    """Nordic's guide-setting factors next to its channel factors (Xc: signed composite z-scores), one row per quarter."""
    go = cfg["guidance_optimism"]
    P = peer_terms(cfg_d)
    ch = pd.read_csv(ROOT / "pipelines" / "D_peer_panel" / "config" / "peer_characteristics.csv")
    heavy = ch.loc[ch["consumer_share"] >= go["consumer_heavy_min_share"], "company"].tolist()
    N = nordic_terms()
    N["rel_raw"], N["rel_seasonal"] = relative(N, P, "g", go["min_peers"]), relative(N, P, "e", go["min_peers"])
    N["rel_consumer_heavy"] = relative(N, P[P["company"].isin(heavy)], "g", 2)
    N["peer_median_g"] = [P.loc[P["quarter"] == q, "g"].median() for q in N["quarter"]]
    n = pd.read_csv(NORDIC_Q).assign(quarter=lambda d: _q(d["quarter"])).set_index("quarter")["revenue_usdm"]
    N["beat"] = [(n.get(q, np.nan) / m - 1) * 100 for q, m in zip(N["quarter"], N["guide_mid_usdm"])]
    N = N.set_index("quarter")
    N["last_beat"] = N["beat"].shift(1)
    N["x_channel"] = x.reindex(N.index)
    return N.join(Xc)


def nordic_fits(N: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    ep = pd.PeriodIndex(cfg["guidance_optimism"]["episode_quarters"], freq="Q")
    specs = [["x_channel"], ["rel_raw"], ["rel_seasonal"], ["rel_consumer_heavy"], ["g"], ["guide_width_pct"], ["last_beat"],
             ["x_channel", "rel_raw"], ["x_channel", "last_beat"]]
    rows = []
    for xs in specs:
        for lab, d in (("all", N), ("without episode", N.drop(ep, errors="ignore"))):
            f = _ols(d, "beat", xs)
            rows.append({"spec": " + ".join(xs), "sample": lab, "n": f["n"], "r2": f["r2"],
                         **{k: v for k, v in f.items() if k.startswith(("b_", "t_"))}})
    return pd.DataFrame(rows)


def run_guidance_optimism(s3: pd.DataFrame, cfg: dict) -> dict:
    import yaml
    from composite import factor_frame, factor_z
    from cycle_test import industry_x
    cfg_d = yaml.safe_load((PIPE_D / "config" / "peers.yaml").read_text())
    x = industry_x(cfg)
    sg = {k: v["sign"] for k, v in cfg["composite"]["factors"].items()}
    Z = factor_z(factor_frame(s3, cfg), cfg)
    Xc = pd.DataFrame({k: sg[k] * Z[k] for k in sg})
    Xc.index = pd.PeriodIndex(Xc.index, freq="Q")
    N = nordic_table(cfg, cfg_d, x, Xc)
    D = panel_design(cfg, cfg_d, x)
    cols = ["beat", "rel_raw", "rel_consumer_heavy", "g", "guide_width_pct", "last_beat", "x_channel"] + list(sg)
    peers_q = peer_beats().groupby("quarter")["beat_pct"].mean()
    same_q = pd.concat([N["beat"], peers_q.rename("peer_mean_beat")], axis=1).dropna()
    ep = pd.PeriodIndex(cfg["guidance_optimism"]["episode_quarters"], freq="Q")
    sq = same_q.drop(ep, errors="ignore")
    return {"nordic": N, "nordic_fits": nordic_fits(N, cfg), "corr": N[cols].corr().loc[cols, cols],
            "panel": panel_tests(D, cfg), "cycle_in_guide": cycle_in_guide(cfg),
            "same_quarter": {"corr": float(same_q.corr().iloc[0, 1]), "corr_wo_episode": float(sq.corr().iloc[0, 1]), "n": len(same_q)}}
