"""Step 6c — composite channel factor for Nordic's guidance miss, and the tests that it is not over-fit.

Target  beat_t = actual revenue_t / guidance midpoint_t - 1 (%): what the guide does NOT contain. Guidance already
        embeds Nordic's order book, so any factor has to explain the miss, not the level (step 6b shows lag models lose
        to guidance on the level).
Factors (config composite.factors; fixed before the run, each dated t-1 or earlier at the forecast date):
        x_k,t  -> z_k,t = (x_k,t - mean(x_k,<=t-1)) / sd(x_k,<=t-1)      expanding, point in time
        C_t    = mean_k( sign_k * z_k,t )                                equal weights, signs from economics
Model   beat_t = a + b * C_t + e_t, re-fit on quarters before t (walk-forward). Two parameters, whatever the number of factors.

Over-fitting has three sources, each tested:
  1 weights      -> equal weights vs estimated weights (OLS "kitchen sink", ridge) in the same walk-forward
  2 selection    -> placebo: the same pipeline on random AR(1) noise factors; p = share doing at least as well;
                    leave-one-factor-out: is the result carried by one factor?
  3 signs        -> all 2^(K-1) distinct sign combinations ranked (a global flip only flips b); where do the economic signs land?
plus coefficient stability (b at each origin), out-of-sample R^2 vs the benchmark (Campbell & Thompson 2008),
Diebold-Mariano (HLN) and the cumulative squared-error difference (Welch & Goyal 2008).
Benchmark: mean beat of the previous 4 quarters (the real-time step-7 method, decision B4).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from walkforward import _dm_hln


# ------------------------------------------------------------------ factors
def factor_frame(s: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Raw factors aligned to the target quarter (already lagged), before z-scoring and signing."""
    out = {}
    for name, f in cfg["composite"]["factors"].items():
        x = s[f["column"]]
        x = x.diff() if f["transform"] == "diff" else x
        out[name] = x.shift(f["lag"])
    return pd.DataFrame(out, index=s.index)


def expanding_z(x: pd.Series, min_hist: int) -> pd.Series:
    """z_t from the mean and sd of x up to t-1 (never t itself)."""
    past = x.shift(1)
    m, sd, n = past.expanding().mean(), past.expanding().std(ddof=1), past.expanding().count()
    return ((x - m) / sd).where((n >= min_hist) & (sd > 0))


def composite(Z: pd.DataFrame, signs: dict) -> pd.Series:
    return (Z * pd.Series(signs)).mean(axis=1, skipna=True).where(Z.notna().any(axis=1))


def factor_z(F: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Point-in-time z-score of every factor, UNSIGNED (the economic signs are applied in composite())."""
    mh = cfg["composite"]["min_z_history"]
    return pd.DataFrame({c: expanding_z(F[c], mh) for c in F}, index=F.index)


# ------------------------------------------------------------------ walk-forward engines
def _targets(y: pd.Series, first: str) -> list:
    return [t for t in y.dropna().index if t >= pd.Period(first, "Q")]


def benchmark(y: pd.Series, window: int = 4) -> pd.Series:
    return y.shift(1).rolling(window, min_periods=2).mean()


def wf_linear(y: pd.Series, X: pd.DataFrame, targets: list, train_start: str, min_train: int, ridge: float = 0.0) -> pd.Series:
    """Walk-forward linear forecast of y from the columns of X (already point in time); ridge on standardised X."""
    preds = {}
    start = pd.Period(train_start, "Q")
    for t in targets:
        tr = pd.concat([y.rename("y"), X], axis=1).loc[start:t - 1].dropna()
        xt = X.loc[t]
        if len(tr) < min_train or xt.isna().any():
            continue
        A = tr.drop(columns="y").values
        mu, sd = A.mean(0), A.std(0, ddof=1)
        sd[sd == 0] = 1.0
        Zt = np.column_stack([np.ones(len(A)), (A - mu) / sd])
        lam = np.eye(Zt.shape[1]) * ridge
        lam[0, 0] = 0.0
        b = np.linalg.solve(Zt.T @ Zt + lam, Zt.T @ tr["y"].values)
        preds[t] = float(b[0] + ((xt.values - mu) / sd) @ b[1:])
    return pd.Series(preds, dtype=float)


def coefficient_path(y: pd.Series, C: pd.Series, targets: list, train_start: str, min_train: int) -> pd.DataFrame:
    rows = []
    for t in targets:
        tr = pd.concat([y.rename("y"), C.rename("c")], axis=1).loc[pd.Period(train_start, "Q"):t - 1].dropna()
        if len(tr) < min_train:
            continue
        X = np.column_stack([np.ones(len(tr)), tr["c"].values])
        b = np.linalg.lstsq(X, tr["y"].values, rcond=None)[0]
        e = tr["y"].values - X @ b
        se = np.sqrt(np.diag(np.linalg.inv(X.T @ X)) * (e @ e) / max(len(e) - 2, 1))
        rows.append({"origin": str(t), "n_train": len(tr), "a": b[0], "b": b[1], "b_se": se[1]})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ scoring
def score(y: pd.Series, pred: pd.Series, bench: pd.Series, guide: pd.Series) -> dict:
    d = pd.concat([y.rename("y"), pred.rename("p"), bench.rename("b"), guide.rename("g")], axis=1).loc[pred.index].dropna()
    if d.empty:
        return {"n": 0}
    e, eb = d["p"] - d["y"], d["b"] - d["y"]
    sse, sse_b = float((e ** 2).sum()), float((eb ** 2).sum())
    dm, pv = _dm_hln(e.values, eb.values, 1)
    return {"n": len(d), "first": str(d.index[0]), "last": str(d.index[-1]),
            "rmse_beat_pts": np.sqrt(sse / len(d)), "bench_rmse_same_quarters": np.sqrt(sse_b / len(d)),
            "oos_r2_vs_bench": 1 - sse / sse_b if sse_b else np.nan,
            "rmse_usdm": float(np.sqrt(np.mean((e * d["g"] / 100) ** 2))),
            "direction_hit": float(np.mean(np.sign(d["p"]) == np.sign(d["y"]))), "dm_hln": dm, "dm_p": pv}


def _concentration(e_base: pd.Series, e_model: pd.Series) -> dict:
    """How concentrated the model's squared-error gain over a baseline is: top-3 share, quarters won, last-6 RMSE."""
    g = (e_base - e_model).dropna()
    total = float(g.sum())
    top3 = g.nlargest(3)
    last6 = pd.DataFrame({"m": e_model, "b": e_base}).dropna().tail(6)
    return {"top3_quarters": [str(q) for q in top3.index], "top3_share": float(top3.sum() / total) if total else np.nan,
            "quarters_won": int((g > 0).sum()), "n": int(len(g)), "oos_r2": 1 - float(e_model.loc[g.index].sum() / e_base.loc[g.index].sum()),
            "last6_rmse_model": float(np.sqrt(last6["m"].mean())), "last6_rmse_base": float(np.sqrt(last6["b"].mean()))}


def effective_n(x: pd.Series) -> dict:
    """Bartlett effective sample size n(1-rho)/(1+rho): how many independent observations an autocorrelated series holds."""
    x = x.dropna()
    rho = float(x.autocorr(1)) if len(x) > 3 else np.nan
    return {"n": int(len(x)), "rho1": rho, "n_eff": float(len(x) * (1 - rho) / (1 + rho)) if pd.notna(rho) else np.nan}


def interval_test(y: pd.Series, C: pd.Series, targets: list, train_start: str, min_train: int, cov: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Walk-forward 80% bands for beat = a + bC. Constant: +/- z s_t (s_t = training residual sd). Scaled: the same x
    (1+|C_t|)/(1+mean|C| in training). Scored by coverage, mean width and the Gneiting-Raftery (2007) interval score."""
    from scipy import stats
    z, alpha = stats.norm.ppf(0.5 + cov / 2), 1 - cov
    rows = []
    for t in targets:
        tr = pd.concat([y.rename("y"), C.rename("c")], axis=1).loc[pd.Period(train_start, "Q"):t - 1].dropna()
        if len(tr) < min_train or pd.isna(C.get(t)) or pd.isna(y.get(t)):
            continue
        X = np.column_stack([np.ones(len(tr)), tr["c"].values])
        b = np.linalg.lstsq(X, tr["y"].values, rcond=None)[0]
        s_t = float(np.sqrt(np.sum((tr["y"].values - X @ b) ** 2) / (len(tr) - 2)))
        mean_c = float(np.nanmean(np.abs(tr["c"].values)))
        yhat = float(b[0] + b[1] * C[t])
        for kind, half in (("constant", z * s_t), ("scaled by |C|", z * s_t * (1 + abs(C[t])) / (1 + mean_c))):
            lo, hi, a = yhat - half, yhat + half, float(y[t])
            score = (hi - lo) + (2 / alpha) * (max(lo - a, 0) + max(a - hi, 0))
            rows.append({"quarter": str(t), "band": kind, "abs_c": abs(float(C[t])), "forecast": yhat, "low": lo, "high": hi,
                         "actual": a, "covered": lo <= a <= hi, "width": hi - lo, "interval_score": score})
    d = pd.DataFrame(rows)
    summ = d.groupby("band").agg(n=("covered", "size"), coverage=("covered", "mean"), mean_width=("width", "mean"),
                                 interval_score=("interval_score", "mean")).reset_index()
    summ["target_coverage"] = cov
    return d, summ


# ------------------------------------------------------------------ the run
def run_composite(s: pd.DataFrame, cfg: dict) -> dict:
    cc, bt = cfg["composite"], cfg["backtest"]
    y = s[cc["target"]]
    guide = s["nordic_guide_mid"]
    targets = _targets(y, bt["first_target"])
    start, mt = cc["first_train_quarter"], bt["min_train_obs"]
    F = factor_frame(s, cfg)
    Z = factor_z(F, cfg)
    signs = {k: v["sign"] for k, v in cc["factors"].items()}
    C = composite(Z, signs)
    bench = benchmark(y, bt["beat_window_quarters"])
    SZ = Z * pd.Series(signs)

    preds = {"composite (equal weights)": wf_linear(y, C.to_frame("c"), targets, start, mt),
             "OLS on all factors (estimated weights)": wf_linear(y, SZ.fillna(0.0), targets, start, mt),
             "ridge on all factors": wf_linear(y, SZ.fillna(0.0), targets, start, mt, ridge=cfg["regression"]["ridge_alpha"] * 4),
             "zero beat (guide midpoint)": pd.Series(0.0, index=targets)}
    for k in signs:
        preds[f"single factor: {k}"] = wf_linear(y, SZ[[k]], targets, start, mt)
    for k in signs:
        rest = {j: signs[j] for j in signs if j != k}
        preds[f"leave out: {k}"] = wf_linear(y, composite(Z[list(rest)], rest).to_frame("c"), targets, start, mt)
    comp_idx = preds["composite (equal weights)"].index
    preds["benchmark: past-4-quarter beat"] = bench.reindex(comp_idx)

    table = pd.DataFrame([{"model": m, **score(y, p, bench, guide)} for m, p in preds.items()])

    # sign combinations. Flipping ALL signs only flips b, so the first factor's sign is held at its prior: 2^(K-1) distinct composites
    combos = []
    first = next(iter(signs))
    for sg in itertools.product([1, -1], repeat=len(signs) - 1):
        sd = {first: signs[first], **dict(zip(list(signs)[1:], sg))}
        r = score(y, wf_linear(y, composite(Z, sd).to_frame("c"), targets, start, mt), bench, guide)
        combos.append({"signs": " ".join(f"{'+' if v > 0 else '-'}{k}" for k, v in sd.items()),
                       "is_economic_prior": sd == signs, "rmse_beat_pts": r.get("rmse_beat_pts"), "oos_r2_vs_bench": r.get("oos_r2_vs_bench")})
    combos = pd.DataFrame(combos).sort_values("rmse_beat_pts").reset_index(drop=True)
    combos["rank"] = np.arange(1, len(combos) + 1)

    # placebo: AR(1) noise factors through the identical pipeline, on the same target quarters
    pl = cc["placebo"]
    rng = np.random.default_rng(pl["seed"])
    actual = table.set_index("model").loc["composite (equal weights)"]
    idx = s.index
    pl_rmse = []
    for _ in range(pl["draws"]):
        noise = np.zeros((len(idx), len(signs)))
        eps = rng.normal(size=noise.shape)
        for i in range(1, len(idx)):
            noise[i] = pl["ar1_phi"] * noise[i - 1] + eps[i]
        Fn = pd.DataFrame(noise, index=idx, columns=list(signs)).where(F.notna().values)    # same missing pattern as the real factors
        Zn = pd.DataFrame({c: expanding_z(Fn[c], cc["min_z_history"]) for c in Fn}, index=idx)
        pn = wf_linear(y, composite(Zn, {k: 1 for k in signs}).to_frame("c"), targets, start, mt).reindex(comp_idx)
        e = (pn - y.reindex(comp_idx)).dropna()
        pl_rmse.append(float(np.sqrt(np.mean(e ** 2))) if len(e) else np.nan)
    pl_rmse = np.array([v for v in pl_rmse if np.isfinite(v)])
    placebo_p = float(np.mean(pl_rmse <= actual["rmse_beat_pts"]))

    coef = coefficient_path(y, C, targets, start, mt)
    lo = table[table["model"].str.startswith("leave out")]
    ad = cc["adopt_if"]
    checks = {"oos_r2_vs_benchmark": (float(actual["oos_r2_vs_bench"]), actual["oos_r2_vs_bench"] > ad["oos_r2_vs_benchmark_min"]),
              "placebo_p": (placebo_p, placebo_p <= ad["placebo_p_max"]),
              "n_forecasts": (int(actual["n"]), actual["n"] >= ad["min_forecasts"]),
              "leave_one_out_share_beating_benchmark": (float((lo["oos_r2_vs_bench"] > 0).mean()), (lo["oos_r2_vs_bench"] > 0).mean() >= ad["leave_one_out_min_share"])}
    adopted = all(v[1] for v in checks.values())

    live_t = pd.Period("2026Q3", "Q")
    Cl = C.reindex(idx.union(pd.PeriodIndex([live_t])))
    live_pred = wf_linear(y.reindex(Cl.index), Cl.to_frame("c"), [live_t], start, mt).get(live_t, np.nan)
    live = {"quarter": str(live_t), "composite_C": float(Cl.get(live_t, np.nan)), "beat_hat_pct": float(live_pred),
            "benchmark_beat_pct": float(benchmark(y, bt["beat_window_quarters"]).reindex(Cl.index).get(live_t, np.nan)),
            "guide_mid": float(guide.get(live_t, np.nan)), "factor_z": {k: float(SZ.reindex(Cl.index).loc[live_t, k]) for k in signs}}
    live["revenue_hat_usdm"] = live["guide_mid"] * (1 + live["beat_hat_pct"] / 100)
    SZl = SZ.reindex(Cl.index).fillna(0.0)
    live["ridge_beat_hat_pct"] = float(wf_linear(y.reindex(Cl.index), SZl, [live_t], start, mt,
                                                 ridge=cfg["regression"]["ridge_alpha"] * 4).get(live_t, np.nan))
    series = pd.DataFrame({"actual_beat": y, "composite_C": C, "benchmark": bench,
                           **{m: p for m, p in preds.items() if not m.startswith(("single", "leave"))}}).loc[comp_idx.min():]
    # where does the gain come from? split the out-of-sample squared errors by regime (reported, not part of the gate)
    reg = s["regime"].reindex(comp_idx) if "regime" in s else pd.Series("all", index=comp_idx)
    e_c = (preds["composite (equal weights)"] - y.reindex(comp_idx)) ** 2
    e_b = (bench.reindex(comp_idx) - y.reindex(comp_idx)) ** 2
    by_regime = pd.DataFrame({"regime": reg, "sse_composite": e_c, "sse_benchmark": e_b}).groupby("regime").agg(
        n=("sse_composite", "size"), sse_composite=("sse_composite", "sum"), sse_benchmark=("sse_benchmark", "sum"))
    by_regime["rmse_composite"] = np.sqrt(by_regime["sse_composite"] / by_regime["n"])
    by_regime["rmse_benchmark"] = np.sqrt(by_regime["sse_benchmark"] / by_regime["n"])
    by_regime["share_of_total_gain"] = (by_regime["sse_benchmark"] - by_regime["sse_composite"]) / float((e_b - e_c).sum())
    # R1: where does the gain come from? Measured against TWO baselines, because the answer depends on which:
    #   bench   = mean beat of the previous 4 quarters (the gate's benchmark; slow to forget a finished destock)
    #   longrun = intercept only: mean of ALL past beats since first_train_quarter (no factors)
    lr = pd.Series({t: y.loc[pd.Period(start, "Q"):t - 1].dropna().mean() for t in comp_idx})
    e_l = (lr - y.reindex(comp_idx)) ** 2
    concentration = {"bench": _concentration(e_b, e_c), "longrun": _concentration(e_l, e_c)}
    gain_q = pd.DataFrame({"gain_vs_bench": e_b - e_c, "gain_vs_longrun": e_l - e_c, "regime": reg})
    neff = {"composite_C": effective_n(C.loc[pd.Period(start, "Q"):]), "beat": effective_n(y.loc[pd.Period(start, "Q"):])}
    band_rows, band_summary = interval_test(y, C, targets, start, mt, cc["interval"]["coverage"])
    bs = band_summary.set_index("band")["interval_score"]
    use_scaled = bool(cc["interval"]["use_scaled_if_interval_score_lower"] and bs.get("scaled by |C|", np.inf) < bs.get("constant", np.inf))
    oos_abs_c = C.reindex(comp_idx).abs().mean()      # the live band's base error is the OOS RMSE, so normalise by the |C| of those same quarters
    live_scale = float((1 + abs(live["composite_C"])) / (1 + oos_abs_c)) if use_scaled else 1.0
    return {"table": table.round(3), "combos": combos.round(3), "by_regime": by_regime.round(3).reset_index(),
            "effective_n": neff, "bands": band_rows.round(3), "band_summary": band_summary.round(3), "use_scaled_band": use_scaled,
            "live_band_scale": live_scale,
            "gain_by_quarter": gain_q.round(3), "concentration": concentration, "placebo_rmse": pl_rmse, "placebo_p": placebo_p,
            "coef": coef.round(3), "checks": checks, "adopted": adopted, "live": live, "series": series,
            "oos_rmse_pts": float(actual["rmse_beat_pts"]), "factors_z": SZ}


# ------------------------------------------------------------------ graph challenger (step 6c-g, B44)
def graph_demand(s: pd.DataFrame, cfg: dict) -> pd.Series:
    """Logitech sell-out proxy pushed through the step-5 graph kernel at h = 1: the graph known on each forecast date,
    lags below one quarter put on t-1 (Logitech t is not reported when Nordic's quarter t is forecast)."""
    from supply_graph import propagate          # steps/step5_supply_graph/src
    origin = lambda t: t.start_time + pd.Timedelta(days=20)    # noqa: E731  same origin as walk-forward model GR at h = 1
    return propagate(s["logi_sellthrough_yoy"], cfg, 1, origin).rename("graph_demand_h1")


def graph_challenger_cfg(cfg: dict) -> dict:
    """The composite spec with one factor swapped for graph demand (new dicts; cfg is not changed)."""
    gc = cfg["composite"]["graph_challenger"]
    factors = {(gc["name"] if k == gc["replaces"] else k): (gc["factor"] if k == gc["replaces"] else v)
               for k, v in cfg["composite"]["factors"].items()}
    return {**cfg, "composite": {**cfg["composite"], "factors": factors, "use_in_forecast": gc["use_in_forecast"]}}


def run_graph_challenger(s: pd.DataFrame, cfg: dict) -> tuple[dict, dict]:
    """(result, spec used) for the composite with the graph factor; the same walk-forward, placebo and gate as the primary."""
    g = graph_demand(s, cfg).reindex(s.index)
    cfg_g = graph_challenger_cfg(cfg)
    return run_composite(s.assign(graph_demand_h1=g), cfg_g), cfg_g
