"""Step 6d — peer panel: do inventory / channel factors predict guidance misses across six companies and several cycles?

Why a panel: the Nordic composite holds ~2 independent observations (one cycle). Six peers x 2011-2026 hold several
cycles (2011-12, 2015-16, 2019, 2022-24) and firm-specific timing. Caveat stated up front: pooling adds independent
information only for factors that DIFFER across firms (own forward DIO). A common factor (Microchip distributor days)
is the same number for every firm in a quarter, so it is still identified from time variation alone -> standard errors
clustered by quarter, and the Diebold-Mariano test runs on the cross-sectional average loss per quarter.

Model (config peer_panel, fixed before the run; every regressor dated t-1 at the forecast date):
    beat_it = FE_it + b1 * sign1 * z(own_fwd_dio)_it + b2 * sign2 * z(d Microchip distributor days)_t + e_it
    FE_it   = firm i's mean beat up to t-1 (its guidance conservatism)
    own_fwd_dio_it = inventory_i,t-1 / (guide_mid_it x COGS/revenue_i,t-1) x 91.25       (days of next quarter's guided cost)
Walk-forward by quarter: pooled fit on all firm-quarters before t, forecast every firm at t.
External test: the peers-only b applied to Nordic (never used in estimation).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from core.config import ROOT
from walkforward import _dm_hln

PIPE_D = ROOT / "pipelines" / "D_peer_panel" / "data" / "raw"
PIPE_A = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"
DAYS_Q = 91.25


def _q(s: pd.Series) -> pd.PeriodIndex:
    return pd.PeriodIndex(s.astype(str), freq="Q")


def load_panel() -> pd.DataFrame:
    p = pd.read_csv(PIPE_D / "peer_panel.csv")
    p = p[~p["excluded"]].copy()
    bal = pd.read_csv(PIPE_D / "peer_balance_xbrl.csv")
    act = pd.read_csv(PIPE_D / "peer_actuals_xbrl.csv")[["company", "quarter", "actual_usdm"]].rename(columns={"actual_usdm": "rev"})
    for d in (p, bal, act):
        d["quarter"] = _q(d["quarter"])
    b = bal.merge(act, on=["company", "quarter"], how="left")
    b["cogs_ratio"] = b["cogs_usdm"] / b["rev"]
    lag = b[["company", "quarter", "inventory_usdm", "cogs_ratio"]].assign(quarter=lambda d: d["quarter"] + 1)   # t-1 values aligned to t
    p = p.merge(lag, on=["company", "quarter"], how="left")
    p["own_fwd_dio"] = p["inventory_usdm"] / (p["guide_mid_usdm"] * p["cogs_ratio"]) * DAYS_Q
    return p[["company", "quarter", "beat_pct", "guide_mid_usdm", "own_fwd_dio"]]


def industry_factor() -> pd.Series:
    m = pd.read_csv(PIPE_A / "mchp_distributor_days.csv")
    s = pd.Series(m["disti_days"].values, index=_q(m["quarter"])).sort_index()
    s = s[~s.index.duplicated(keep="last")].asfreq("Q")
    return s.diff().shift(1).rename("industry_mchp_days")          # change in t-1, known at t


def _expanding_z(x: pd.Series, min_hist: int) -> pd.Series:
    past = x.shift(1)
    m, sd, n = past.expanding().mean(), past.expanding().std(ddof=1), past.expanding().count()
    return ((x - m) / sd).where((n >= min_hist) & (sd > 0))


def build_design(p: pd.DataFrame, ind: pd.Series, cfg: dict) -> pd.DataFrame:
    """Signed, point-in-time z-scores; firm FE = expanding mean beat; past-4 benchmark."""
    pc = cfg["peer_panel"]
    mh = pc["min_z_history"]
    out = []
    for c, g in p.groupby("company"):
        g = g.set_index("quarter").sort_index().asfreq("Q")
        g["company"] = c
        g["fe"] = g["beat_pct"].shift(1).expanding().mean()
        g["past4"] = g["beat_pct"].shift(1).rolling(4, min_periods=2).mean()
        g["z_own_fwd_dio"] = pc["factors"]["own_fwd_dio"]["sign"] * _expanding_z(g["own_fwd_dio"], mh)
        out.append(g.reset_index())
    d = pd.concat(out, ignore_index=True).dropna(subset=["beat_pct"])
    zi = pc["factors"]["industry_mchp_days"]["sign"] * _expanding_z(ind, mh)
    d["z_industry"] = d["quarter"].map(zi)
    return d


def _fit(tr: pd.DataFrame, cols: list[str]) -> np.ndarray:
    X = tr[cols].values
    return np.linalg.lstsq(X, (tr["beat_pct"] - tr["fe"]).values, rcond=None)[0]


def clustered_se(tr: pd.DataFrame, cols: list[str], b: np.ndarray) -> np.ndarray:
    """Sandwich with clusters = quarters (common shocks hit every firm at once)."""
    X = tr[cols].values
    e = (tr["beat_pct"] - tr["fe"]).values - X @ b
    xtx = np.linalg.inv(X.T @ X)
    meat = sum(np.outer(X[idx].T @ e[idx], X[idx].T @ e[idx]) for idx in tr.groupby("quarter").indices.values())
    g = tr["quarter"].nunique()
    return np.sqrt(np.diag(xtx @ meat @ xtx) * g / max(g - 1, 1))


SPECS = {"FE + own forward DIO": ["z_own_fwd_dio"], "FE + industry channel": ["z_industry"],
         "FE + both": ["z_own_fwd_dio", "z_industry"]}


def walk_forward(d: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    pc = cfg["peer_panel"]
    qs = sorted(d["quarter"].unique())
    first = pd.Period(pc["first_target"], "Q")
    rows = []
    for T in [q for q in qs if q >= first]:
        test = d[d["quarter"] == T].dropna(subset=["fe"])
        base = {"fe": test["fe"], "past4": test["past4"]}
        pred = {}
        for name, cols in SPECS.items():
            tr = d[(d["quarter"] < T)].dropna(subset=["fe"] + cols)
            if tr["quarter"].nunique() < pc["min_train_quarters"]:
                continue
            b = _fit(tr, cols)
            pred[name] = test["fe"] + test[cols].fillna(0.0).values @ b          # a missing z -> neutral (0)
        for i in test.index:
            rows.append({"quarter": T, "company": test.at[i, "company"], "actual": test.at[i, "beat_pct"],
                         "benchmark_firm_mean": base["fe"][i], "benchmark_past4": base["past4"][i],
                         **{k: v[i] for k, v in pred.items()}})
    return pd.DataFrame(rows)


def score(wf: pd.DataFrame, bench: str = "benchmark_firm_mean") -> pd.DataFrame:
    rows = []
    models = [c for c in wf.columns if c not in ("quarter", "company", "actual")]
    for m in models:
        d = wf[list(dict.fromkeys(["quarter", "company", "actual", m, bench, "benchmark_past4"]))].dropna()
        if d.empty:
            continue
        e2, b2, p2 = (d[m] - d["actual"]) ** 2, (d[bench] - d["actual"]) ** 2, (d["benchmark_past4"] - d["actual"]) ** 2
        lq = pd.DataFrame({"q": d["quarter"], "m": e2, "b": b2}).groupby("q").mean()       # cross-sectional average loss per quarter
        dm, pv = _dm_hln(np.sqrt(lq["m"].values), np.sqrt(lq["b"].values), 1) if m != bench else (np.nan, np.nan)
        gain = (lq["b"] - lq["m"])
        top3 = gain.nlargest(3)
        rows.append({"model": m, "firm_quarters": len(d), "quarters": d["quarter"].nunique(), "firms": d["company"].nunique(),
                     "rmse_pts": float(np.sqrt(e2.mean())), "oos_r2_vs_firm_mean": 1 - float(e2.sum() / b2.sum()),
                     "oos_r2_vs_past4": 1 - float(e2.sum() / p2.sum()), "dm_p_by_quarter": pv,
                     "quarters_won_share": float((gain > 0).mean()),
                     "top3_quarters_gain_share": float(top3.sum() / gain.sum()) if gain.sum() > 0 else np.nan,
                     "top3_quarters": ", ".join(str(q) for q in top3.index)})
    return pd.DataFrame(rows)


def full_sample(d: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, cols in SPECS.items():
        tr = d.dropna(subset=["fe"] + cols)
        b = _fit(tr, cols)
        se = clustered_se(tr, cols, b)
        for c, bb, s in zip(cols, b, se):
            rows.append({"spec": name, "factor": c, "b_pts_per_sd": bb, "se_clustered_by_quarter": s, "t": bb / s,
                         "p": 2 * stats.t.sf(abs(bb / s), df=max(tr["quarter"].nunique() - 1, 1)),
                         "firm_quarters": len(tr), "quarters": tr["quarter"].nunique()})
    return pd.DataFrame(rows)


def by_firm(wf: pd.DataFrame, model: str) -> pd.DataFrame:
    d = wf.dropna(subset=[model, "benchmark_firm_mean"])
    g = d.groupby("company").apply(lambda x: pd.Series({
        "n": len(x), "rmse_model": np.sqrt(((x[model] - x["actual"]) ** 2).mean()),
        "rmse_firm_mean": np.sqrt(((x["benchmark_firm_mean"] - x["actual"]) ** 2).mean())}))
    g["oos_r2"] = 1 - g["rmse_model"] ** 2 / g["rmse_firm_mean"] ** 2
    return g.round(3).reset_index()


def nordic_external(d_peers: pd.DataFrame, s3: pd.DataFrame, ind: pd.Series, cfg: dict, first: str) -> pd.DataFrame:
    """Peers-only coefficients (trained on quarters < T) applied to Nordic at T, with Nordic's own firm FE (mean past beat)
    and Nordic's own point-in-time z of forward DIO. Nordic never enters estimation: an external test."""
    pc = cfg["peer_panel"]
    n = pd.DataFrame({"beat_pct": s3["nordic_beat_vs_guide_pct"], "own_fwd_dio": s3["nordic_fwd_dio"].shift(1)})
    n = n.asfreq("Q") if not isinstance(n.index, pd.PeriodIndex) else n
    n["fe"] = n["beat_pct"].shift(1).expanding().mean()
    n["past4"] = n["beat_pct"].shift(1).rolling(4, min_periods=2).mean()
    n["z_own_fwd_dio"] = pc["factors"]["own_fwd_dio"]["sign"] * _expanding_z(n["own_fwd_dio"], pc["min_z_history"])
    n["z_industry"] = pc["factors"]["industry_mchp_days"]["sign"] * _expanding_z(ind, pc["min_z_history"]).reindex(n.index)
    rows = []
    for T in [q for q in n.dropna(subset=["beat_pct", "fe"]).index if q >= pd.Period(first, "Q")]:
        r = {"quarter": T, "actual": n.at[T, "beat_pct"], "benchmark_firm_mean": n.at[T, "fe"], "benchmark_past4": n.at[T, "past4"]}
        for name, cols in SPECS.items():
            tr = d_peers[d_peers["quarter"] < T].dropna(subset=["fe"] + cols)
            b = _fit(tr, cols)
            r[name] = n.at[T, "fe"] + n.loc[T, cols].fillna(0.0).values @ b
        rows.append(r)
    return pd.DataFrame(rows)


def hierarchical(d: pd.DataFrame, nordic_rows: pd.DataFrame, factor: str = "z_industry", peers: list[str] | None = None) -> dict:
    """Partial pooling (DerSimonian-Laird random effects): each firm's slope = peer mean + firm deviation. Nordic's own slope
    is shrunk towards the peer mean with weight tau^2 / (tau^2 + se^2); se is also shown inflated for Nordic's effective n.
    `peers` restricts the pool (e.g. to the pre-registered Nordic-like peers)."""
    rows = []
    dd = d if peers is None else d[d["company"].isin(peers)]
    for c, g in pd.concat([dd, nordic_rows]).dropna(subset=["beat_pct", "fe", factor]).groupby("company"):
        y, x = (g["beat_pct"] - g["fe"]).values, g[factor].values
        b = float(x @ y / (x @ x))
        e = y - b * x
        se = float(np.sqrt((e @ e) / (len(y) - 1) / (x @ x)))
        rho = float(pd.Series(x).autocorr(1))
        rows.append({"company": c, "n": len(y), "b": b, "se": se, "x_rho1": rho, "n_eff_x": len(y) * (1 - rho) / (1 + rho)})
    t = pd.DataFrame(rows).set_index("company")
    peers = t.drop("NORDIC")
    w = 1 / peers["se"] ** 2
    bf = float((w * peers["b"]).sum() / w.sum())
    q = float((w * (peers["b"] - bf) ** 2).sum())
    tau2 = max(0.0, (q - (len(peers) - 1)) / float(w.sum() - (w ** 2).sum() / w.sum()))
    wr = 1 / (peers["se"] ** 2 + tau2)
    b_re, se_re = float((wr * peers["b"]).sum() / wr.sum()), float(np.sqrt(1 / wr.sum()))
    n = t.loc["NORDIC"]
    se_eff = float(n["se"] * np.sqrt(n["n"] / max(n["n_eff_x"], 1)))
    shrink = {lab: {"se": s, "weight_on_nordic": tau2 / (tau2 + s ** 2) if tau2 + s ** 2 else 0.0}
              for lab, s in (("naive", float(n["se"])), ("effective_n", se_eff))}
    for v in shrink.values():
        v["shrunk_slope"] = v["weight_on_nordic"] * float(n["b"]) + (1 - v["weight_on_nordic"]) * b_re
    return {"per_firm": t.reset_index(), "peer_mean": b_re, "peer_mean_se": se_re, "tau": float(np.sqrt(tau2)), "Q": q,
            "df": len(peers) - 1, "nordic_b": float(n["b"]), "shrink": shrink}


def phase_test(d: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per-cycle modelling on the panel. Phase = sign of the firm's OWN revenue YoY at t-1 (known at t, no ex-post labels).
    Pooled vs phase intercept vs phase-specific slopes, walk-forward, OOS R^2 vs the firm mean, overall and by phase."""
    act = pd.read_csv(PIPE_D / "peer_actuals_xbrl.csv")
    act["quarter"] = _q(act["quarter"])
    act = act.sort_values(["company", "quarter"])
    act["yoy"] = act.groupby("company")["actual_usdm"].pct_change(4, fill_method=None) * 100
    x = d.merge(act[["company", "quarter", "yoy"]].assign(quarter=lambda a: a["quarter"] + 1), on=["company", "quarter"], how="left")
    x["down"] = (x["yoy"] <= 0).astype(float)
    x["up"] = 1 - x["down"]
    for f, s in (("z_industry", "zi"), ("z_own_fwd_dio", "zo")):
        x[f"{s}_up"], x[f"{s}_dn"] = x[f] * x["up"], x[f] * x["down"]
    specs = {"pooled (no phase)": ["z_industry", "z_own_fwd_dio"], "phase intercept": ["z_industry", "z_own_fwd_dio", "down"],
             "phase-specific slopes": ["zi_up", "zi_dn", "zo_up", "zo_dn"], "phase intercept + slopes": ["zi_up", "zi_dn", "zo_up", "zo_dn", "down"]}
    rows = []
    for T in sorted(q for q in x["quarter"].unique() if q >= pd.Period(cfg["peer_panel"]["first_target"], "Q")):
        test = x[x["quarter"] == T].dropna(subset=["fe", "yoy"])
        preds = {}
        for name, cols in specs.items():
            tr = x[x["quarter"] < T].dropna(subset=["fe", "yoy"] + cols)
            if tr["quarter"].nunique() < cfg["peer_panel"]["min_train_quarters"]:
                continue
            b = np.linalg.lstsq(tr[cols].values, (tr["beat_pct"] - tr["fe"]).values, rcond=None)[0]
            preds[name] = test["fe"] + np.nan_to_num(test[cols].values.astype(float)) @ b
        for i in test.index:
            rows.append({"actual": test.at[i, "beat_pct"], "fe": test.at[i, "fe"], "down": test.at[i, "down"], "quarter": T,
                         **{k: v[i] for k, v in preds.items()}})
    w = pd.DataFrame(rows).dropna()
    out = []
    for name in specs:
        e, eb, dn = (w[name] - w["actual"]) ** 2, (w["fe"] - w["actual"]) ** 2, w["down"] == 1
        out.append({"model": name, "firm_quarters": len(w), "downturn_quarters": int(w.loc[dn, "quarter"].nunique()),
                    "oos_r2_vs_firm_mean": 1 - e.sum() / eb.sum(), "oos_r2_in_downturns": 1 - e[dn].sum() / eb[dn].sum(),
                    "oos_r2_in_upturns": 1 - e[~dn].sum() / eb[~dn].sum()})
    return pd.DataFrame(out)


def _dl_tau2_reg(b: np.ndarray, se: np.ndarray, X: np.ndarray) -> float:
    """Method-of-moments (DerSimonian-Laird) residual between-firm variance for a meta-regression:
    tau^2 = (Q_E - (k - p)) / (sum w - tr((X'WX)^-1 X'W^2X)), floored at 0."""
    w = 1 / se ** 2
    xtwx = np.linalg.inv(X.T @ (X * w[:, None]))
    g = xtwx @ X.T @ (w * b)
    qe = float(w @ (b - X @ g) ** 2)
    c = float(w.sum() - np.trace(xtwx @ (X.T @ (X * (w ** 2)[:, None]))))
    return max(0.0, (qe - (len(b) - X.shape[1])) / c) if c > 0 else 0.0


def _wls_meta(sub: pd.DataFrame, cov_col: str, x_nordic: dict) -> dict:
    """WLS of slope on one characteristic, weights 1/(se^2 + residual tau^2); Nordic's slope predicted at x_nordic values,
    90% prediction interval = pred +- 1.645 sqrt(se_pred^2 + tau^2)."""
    X = np.column_stack([np.ones(len(sub)), sub[cov_col]])
    b, se = sub["b"].values, sub["se"].values
    tau2 = _dl_tau2_reg(b, se, X)
    w = 1 / (se ** 2 + tau2)
    cov = np.linalg.inv(X.T @ (X * w[:, None]))
    g = cov @ X.T @ (w * b)
    preds = {}
    for k, v in x_nordic.items():
        x = np.array([1.0, v])
        pred, sp = float(x @ g), float(np.sqrt(x @ cov @ x))
        pi = float(np.sqrt(sp ** 2 + tau2))
        preds[k] = {"x": v, "pred": pred, "pi90": (pred - 1.645 * pi, pred + 1.645 * pi)}
    lo, hi = float(sub[cov_col].min()), float(sub[cov_col].max())
    return {"n": len(sub), "covariate": cov_col, "gamma0": float(g[0]), "gamma1": float(g[1]), "gamma1_se": float(np.sqrt(cov[1, 1])),
            "gamma1_t": float(g[1] / np.sqrt(cov[1, 1])), "tau_resid": float(np.sqrt(tau2)), "x_range": (lo, hi),
            "nordic_extrapolated": any(not lo <= v <= hi for v in x_nordic.values()), "nordic_pred": preds}


def meta_regression(h: dict, cfg: dict) -> dict:
    """Step 6e: does a firm's slope depend on how Nordic-like it is? Each peer's slope is regressed on its distribution share
    (WLS, weights 1 / (se^2 + residual tau^2)) for all peers with a disclosed share and for the pre-registered Nordic-like
    peers only; Nordic's slope is then PREDICTED from its own characteristics (never fitted), with a prediction interval
    that includes the residual tau. Consumer share is an exploratory sensitivity only (B30: definitions differ, not all disclose)."""
    ps = cfg["peer_similarity"]
    ch = pd.read_csv(ROOT / "pipelines" / "D_peer_panel" / "config" / "peer_characteristics.csv").set_index("company")
    t = h["per_firm"].set_index("company").drop("NORDIC").join(ch[["distribution_share", "distribution_basis", "consumer_share"]])
    t["meets_criterion"] = t["distribution_share"] >= ps["criteria"]["min_distribution_share"]
    out = {"table": t.reset_index(), "fits": []}
    specs = (("all peers", "distribution_share", t.dropna(subset=["distribution_share"]), ps["nordic"]["distribution_share"]),
             ("Nordic-like peers", "distribution_share", t[t["meets_criterion"]], ps["nordic"]["distribution_share"]),
             ("Nordic-like peers (exploratory)", "consumer_share", t[t["meets_criterion"]].dropna(subset=["consumer_share"]),
              {"nordic": ps["nordic"]["consumer_share"]}))
    for label, col, sub, xn in specs:
        if len(sub) >= 3:
            out["fits"].append({"sample": label, **_wls_meta(sub, col, xn)})
    return out


def meta_table(m: dict) -> pd.DataFrame:
    """One row per (fit, Nordic scenario) for peer_panel_meta_regression.csv."""
    rows = [{"sample": f["sample"], "covariate": f["covariate"], "n_firms": f["n"], "gamma0": f["gamma0"], "gamma1": f["gamma1"],
             "gamma1_se": f["gamma1_se"], "gamma1_t": f["gamma1_t"], "tau_resid": f["tau_resid"],
             "peer_range": f"{f['x_range'][0]:.2f}-{f['x_range'][1]:.2f}", "nordic_scenario": k, "nordic_x": p["x"],
             "nordic_slope_pred": p["pred"], "pi90_low": p["pi90"][0], "pi90_high": p["pi90"][1],
             "extrapolated": not f["x_range"][0] <= p["x"] <= f["x_range"][1]}
            for f in m["fits"] for k, p in f["nordic_pred"].items()]
    return pd.DataFrame(rows)
