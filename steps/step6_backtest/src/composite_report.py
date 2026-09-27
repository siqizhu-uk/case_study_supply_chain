"""Step 6c outputs: composite tables, the pre-registration log, a 2x3 figure and the markdown section for step6_report.md."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

PRIMARY = "composite (equal weights)"
CHALLENGER = "ridge on all factors"


MODEL_KEYS = ("target", "factors", "min_z_history", "first_train_quarter")    # what defines the forecast; thresholds and display settings do not


def spec_hash(cfg: dict) -> str:
    spec = {k: cfg["composite"][k] for k in MODEL_KEYS}
    return hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:10]


def data_hash(r: dict) -> str:
    """Fingerprint of the inputs the live forecast used (target + signed factor z-scores up to the live quarter)."""
    frame = pd.concat([r["series"]["actual_beat"], r["factors_z"]], axis=1).round(6)
    return hashlib.sha1(frame.to_csv().encode()).hexdigest()[:10]


def preregister(r: dict, cfg: dict, d: Path, fname: str = "composite_prereg_log.csv") -> pd.DataFrame:
    """Append the live forecast once per (target, model spec, input data): any change to the model OR to the data that
    moves the forecast adds a visible row. Scoring rule: the LAST row logged before the print date is the forecast of record."""
    f = d / fname
    log = pd.read_csv(f, dtype=str) if f.exists() else pd.DataFrame(columns=["target", "spec_hash", "data_hash"])
    lv, h, dh = r["live"], spec_hash(cfg), data_hash(r)
    if not ((log["target"] == lv["quarter"]) & (log["spec_hash"] == h) & (log["data_hash"] == dh)).any():
        row = {"target": lv["quarter"], "spec_hash": h, "data_hash": dh, "logged_on": date.today().isoformat(), "guide_mid_usdm": round(lv["guide_mid"], 1),
               "beat_hat_pct": round(lv["beat_hat_pct"], 2), "revenue_hat_usdm": round(lv["revenue_hat_usdm"], 1),
               "benchmark_beat_pct": round(lv["benchmark_beat_pct"], 2), "ridge_challenger_beat_pct": round(lv["ridge_beat_hat_pct"], 2),
               "adopted": r["adopted"], "actual_usdm": "", "scored_on": ""}
        log = pd.concat([log, pd.DataFrame([row])], ignore_index=True)
        log.to_csv(f, index=False)
    return log


def prereg_view(log: pd.DataFrame, used: bool, reason: str) -> pd.DataFrame:
    """The pre-registration log as displayed: its 'adopted' column records the adoption GATE, not use in the forecast
    (the analyst can keep a gate-passing model out, e.g. B26), so it is shown as one status in words."""
    if "adopted" not in log:
        return log
    status = lambda v: (f"gate passed; {'used' if used else f'not used ({reason})'}"   # noqa: E731
                        if str(v).lower() == "true" else "gate failed; not used")
    return log.assign(adopted=log["adopted"].map(status)).rename(columns={"adopted": "status"})


def figure(r: dict, d: Path) -> Path:
    s = r["series"]
    x = s.index.to_timestamp()
    fig, ax = plt.subplots(2, 3, figsize=(15, 7.5))
    a = ax[0, 0]
    a.bar(x, s["actual_beat"], width=50, color="#bbbbbb", label="actual beat vs guide midpoint")
    a.plot(x, s[PRIMARY], "o-", color="#E45756", label="composite (walk-forward)")
    a.plot(x, s["benchmark"], "s--", color="#4C78A8", label="past-4-quarter beat (benchmark)")
    a.axhline(0, color="k", lw=.6); a.set_ylabel("% vs guide"); a.set_title("Forecast of Nordic's guidance miss", fontsize=10); a.legend(fontsize=7)
    t = r["table"].set_index("model").dropna(subset=["rmse_beat_pts"])
    keep = [m for m in t.index if not m.startswith("single")]
    col = ["#E45756" if m == PRIMARY else "#4C78A8" if m.startswith("benchmark") else "#F58518" if m.startswith("leave") else "#999" for m in keep]
    a = ax[0, 1]
    a.barh(range(len(keep)), t.loc[keep, "rmse_beat_pts"], color=col)
    a.set_yticks(range(len(keep))); a.set_yticklabels([k.replace("leave out: ", "drop ") for k in keep], fontsize=7); a.invert_yaxis()
    a.set_xlabel("walk-forward RMSE (pts)"); a.set_title("Weights and leave-one-factor-out", fontsize=10)
    a = ax[0, 2]
    e_c = (s[PRIMARY] - s["actual_beat"]) ** 2
    e_b = (s["benchmark"] - s["actual_beat"]) ** 2
    e_r = (s[CHALLENGER] - s["actual_beat"]) ** 2
    a.plot(x, (e_b - e_c).fillna(0).cumsum(), "o-", color="#E45756", label="composite")
    a.plot(x, (e_b - e_r).fillna(0).cumsum(), "d--", color="#F58518", label="ridge (challenger)")
    a.axhline(0, color="k", lw=.6); a.set_title("Cumulative squared-error gain vs benchmark\n(rising = beating it; Welch-Goyal)", fontsize=10); a.legend(fontsize=7)
    a = ax[1, 0]
    a.hist(r["placebo_rmse"], bins=40, color="#cccccc")
    a.axvline(r["oos_rmse_pts"], color="#E45756", lw=2, label=f"composite {r['oos_rmse_pts']:.2f}")
    a.axvline(float(t.loc["benchmark: past-4-quarter beat", "rmse_beat_pts"]), color="#4C78A8", ls="--", label="benchmark")
    a.set_title(f"Placebo: {len(r['placebo_rmse'])} noise composites, p = {r['placebo_p']:.3f}", fontsize=10); a.legend(fontsize=7); a.set_xlabel("RMSE (pts)")
    a = ax[1, 1]
    c = r["coef"]
    xo = pd.PeriodIndex(c["origin"], freq="Q").to_timestamp()
    a.errorbar(xo, c["b"], yerr=1.645 * c["b_se"], fmt="o-", color="#E45756", capsize=3)
    a.axhline(0, color="k", lw=.6); a.set_title("Slope b at each forecast origin (±90%)", fontsize=10); a.set_ylabel("pts of beat per unit of C")
    a = ax[1, 2]
    cb = r["combos"]
    a.bar(range(len(cb)), cb["rmse_beat_pts"], color=["#E45756" if v else "#bbbbbb" for v in cb["is_economic_prior"]])
    a.axhline(float(t.loc["benchmark: past-4-quarter beat", "rmse_beat_pts"]), color="#4C78A8", ls="--", label="benchmark")
    a.set_xticks(range(len(cb))); a.set_xticklabels(cb["rank"], fontsize=7); a.set_xlabel("sign combinations, best to worst (red = economic prior)")
    a.set_title("Sign choice", fontsize=10); a.legend(fontsize=7)
    for a in ax.flat:
        a.grid(alpha=.3)
    for a in (ax[0, 0], ax[0, 2], ax[1, 1]):
        a.xaxis.set_major_locator(mdates.MonthLocator(bymonth=(1, 7)))
        a.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        a.tick_params(axis="x", labelsize=7, rotation=45)
    fig.tight_layout()
    f = d / "composite.png"
    fig.savefig(f, dpi=120); plt.close(fig)
    return f


def _gain_sentence(c: dict) -> str:
    """Same content as risk R1: the gain's concentration against both baselines."""
    from risk_flags import _r1_evidence
    cb = c["bench"]
    return "Where the gain comes from — " + _r1_evidence(cb, c["longrun"], cb["last6_rmse_model"] > cb["last6_rmse_base"])


def _band_caveat(r: dict) -> str:
    """How much evidence the band comparison really holds (data trap check)."""
    bd = r["bands"]
    cov = bd.groupby("band")["covered"].sum()
    n = int(bd.groupby("band").size().iloc[0])
    diff = int(abs(cov.get("constant", 0) - cov.get("scaled by |C|", 0)))
    train_mean = bd.loc[bd["band"] == "constant", "abs_c"].mean()
    return (f"**Caveat.** Coverage differs by {diff} of {n} quarters ({int(cov.get('constant', 0))} vs {int(cov.get('scaled by |C|', 0))} covered). "
            f"The scaled band is narrower here partly because |C| in these test quarters (mean {train_mean:.2f}) is small next to the destock "
            "quarters that dominate the training mean — the same one-cycle composition behind R1 and R4.")


def section(r: dict, cfg: dict, log: pd.DataFrame) -> str:
    t = r["table"].set_index("model")
    p, ch, lv = t.loc[PRIMARY], r["checks"], r["live"]
    cb = r["combos"]
    prior_rank = int(cb.loc[cb["is_economic_prior"], "rank"].iloc[0])
    lo = t[t.index.str.startswith("leave out")]
    fac = pd.DataFrame([{"factor": k, "column": v["column"], "transform": v["transform"], "lag": v["lag"], "sign": v["sign"], "reason": v["reason"]}
                        for k, v in cfg["composite"]["factors"].items()])
    gate = pd.DataFrame([{"check": k, "value": round(v[0], 3), "passed": v[1]} for k, v in ch.items()])
    key = lo["oos_r2_vs_bench"].sort_values().index[:2].str.replace("leave out: ", "")
    best = cb.iloc[0]["signs"].split()
    prior = cb.loc[cb["is_economic_prior"], "signs"].iloc[0].split()
    flipped = [b[1:] for b, q in zip(best, prior) if b != q]
    sz = r["factors_z"]
    corr = sz.corrwith(r["series"]["actual_beat"].reindex(sz.index))
    wrong = [k for k, v in corr.items() if pd.notna(v) and v < 0]
    md = ["## 7. Composite channel factor → Nordic's guidance miss (step 6c)\n",
          "**Why this target.** Guidance already contains Nordic's order book, so a factor can only add what the guide does not know: the miss "
          "beat_t = actual / guide midpoint − 1. **Model.** C_t = mean_k(sign_k × z_k,t), each z from data up to t−1 only; beat_t = a + b·C_t, re-fit each quarter. "
          "Two parameters regardless of how many factors (B12–B18).\n",
          "Factors, signs and lags (fixed in `config/model.yaml` → `composite` before the run):\n", fac.to_markdown(index=False), "",
          f"**Result.** Walk-forward RMSE {p['rmse_beat_pts']:.2f} pts vs {p['bench_rmse_same_quarters']:.2f} for the past-beat benchmark on the same "
          f"{int(p['n'])} quarters (out-of-sample R² {p['oos_r2_vs_bench']:+.2f}; in revenue USD {p['rmse_usdm']:.1f}m vs "
          f"{t.loc['benchmark: past-4-quarter beat', 'rmse_usdm']:.1f}m); beat direction right {p['direction_hit']:.0%}. "
          f"Diebold-Mariano p = {p['dm_p']:.2f} — not significant on its own with {int(p['n'])} points.\n",
          "**Where the gain comes from** (walk-forward squared errors split by regime; reported, not part of the gate):\n",
          r["by_regime"].to_markdown(index=False), "",
          f"{_gain_sentence(r['concentration'])}\n",
          "### Is it over-fit?\n",
          f"1. **Chance (placebo).** {len(r['placebo_rmse'])} composites of random AR(1) noise through the identical pipeline: only "
          f"{r['placebo_p']:.1%} do as well. The pipeline does not manufacture this result.",
          f"2. **One factor carrying it (leave-one-out).** Dropping any single factor, {int((lo['oos_r2_vs_bench'] > 0).sum())} of {len(lo)} composites still beat the "
          f"benchmark (OOS R² {lo['oos_r2_vs_bench'].min():+.2f} to {lo['oos_r2_vs_bench'].max():+.2f}); dropping {key[0]} or {key[1]} hurts most.",
          f"3. **Weights.** Estimated weights did *not* over-fit here: OLS {t.loc['OLS on all factors (estimated weights)', 'rmse_beat_pts']:.2f}, ridge "
          f"{t.loc[CHALLENGER, 'rmse_beat_pts']:.2f} vs equal {p['rmse_beat_pts']:.2f} pts. Equal weights stay primary because they were fixed before the run; "
          f"switching now, after seeing the result on {int(p['n'])} points, would be the look-ahead the test exists to prevent. Ridge is logged as the challenger.",
          f"4. **Signs.** Of the {len(cb)} distinct sign combinations the economic prior ranks {prior_rank}; the best one flips "
          f"{', '.join(flipped) if flipped else 'nothing'} relative to the prior. The prior signs are kept — choosing the back-test's best would be data-mining.",
          f"5. **Stability.** The slope b stays between {r['coef']['b'].min():.1f} and {r['coef']['b'].max():.1f} across origins; its standard error falls from "
          f"{r['coef']['b_se'].iloc[0]:.1f} to {r['coef']['b_se'].iloc[-1]:.1f}.",
          "6. **What no test can remove.** The four factors were chosen after step 3 had shown the data (researcher degrees of freedom). None was dropped after "
          f"seeing the back-test ({', '.join(wrong) + ' stays although its signed correlation with the miss is negative' if wrong else 'every signed factor correlates positively with the miss'}). "
          "The honest test is the pre-registered forecast below, scored after 22 Oct.\n",
          "### Uncertainty band: does |C| predict the size of the error?\n",
          "|C| says how extreme the channel is, not which way the miss goes (the sign is C's job). A band scaled by (1+|C_t|)/(1+mean|C|) "
          "adds no fitted parameter; it keeps the average width over the window its base error is measured on and moves width towards extreme "
          "channel states. Walk-forward 80% bands:\n",
          r["band_summary"].to_markdown(index=False), "",
          _band_caveat(r), "",
          f"Step 7 uses the **{'scaled' if r['use_scaled_band'] else 'constant'}** band (rule in config: scaled only if its interval score is lower). "
          f"Live scale factor for {lv['quarter']}: {r['live_band_scale']:.2f}.\n",
          "### Adoption gate (stated in config before the run)\n", gate.to_markdown(index=False), "",
          (f"**Gate {'passed' if r['adopted'] else 'failed'}; used in the forecast: {'YES' if r['adopted'] and cfg['composite'].get('use_in_forecast', True) else 'NO'}.** "
           + ("Analyst decision B26: the peer panel (section 8, risk R5) shows the mechanism does not generalise, so the composite stays a "
              "pre-registered challenger and step 7 keeps the regime-conditioned historical beat.\n"
              if not cfg["composite"].get("use_in_forecast", True) else
              ("Step 7 uses the composite beat and its out-of-sample error.\n" if r["adopted"] else "Step 7 keeps the regime-conditioned historical beat.\n"))),
          "### Live forecast, pre-registered (`outputs/composite_prereg_log.csv`)\n",
          f"Q3 2026: C = {lv['composite_C']:+.2f} → beat {lv['beat_hat_pct']:+.2f}% (benchmark {lv['benchmark_beat_pct']:+.2f}%) → revenue USD {lv['revenue_hat_usdm']:.1f}m on the "
          f"USD {lv['guide_mid']:.0f}m midpoint. Factor contributions (signed z): " + ", ".join(f"{k} {v:+.2f}" for k, v in lv["factor_z"].items()) + ".\n",
          prereg_view(log, cfg["composite"].get("use_in_forecast", True), "B26").to_markdown(index=False), "",
          "![composite](composite.png)\n",
          "### All models in the composite test\n", r["table"].to_markdown(index=False), "", "Sign combinations:\n", cb.to_markdown(index=False), ""]
    return "\n".join(md)


def write_composite(r: dict, cfg: dict, d: Path) -> str:
    r["table"].to_csv(d / "composite_models.csv", index=False)
    r["combos"].to_csv(d / "composite_sign_combos.csv", index=False)
    r["coef"].to_csv(d / "composite_coefficient_path.csv", index=False)
    r["by_regime"].to_csv(d / "composite_gain_by_regime.csv", index=False)
    r["gain_by_quarter"].round(3).to_csv(d / "composite_gain_by_quarter.csv")
    r["bands"].to_csv(d / "composite_bands.csv", index=False)
    r["band_summary"].to_csv(d / "composite_band_summary.csv", index=False)
    pd.DataFrame([{"series": k, **v} for k, v in r["effective_n"].items()]).round(3).to_csv(d / "composite_effective_n.csv", index=False)
    r["series"].round(3).to_csv(d / "composite_walkforward.csv")
    pd.DataFrame({"placebo_rmse": np.round(r["placebo_rmse"], 4)}).to_csv(d / "composite_placebo.csv", index=False)
    pd.DataFrame([{"check": k, "value": v[0], "passed": v[1]} for k, v in r["checks"].items()]
                 + [{"check": "GATE PASSED", "value": None, "passed": r["adopted"]},
                    {"check": "USED IN FORECAST (analyst: config composite.use_in_forecast, B26)", "value": None,
                     "passed": bool(r["adopted"] and cfg["composite"].get("use_in_forecast", True))}]).to_csv(d / "composite_gate.csv", index=False)
    log = preregister(r, cfg, d)
    figure(r, d)
    return section(r, cfg, log)


def graph_section(rg: dict, r: dict, cfg_g: dict, log: pd.DataFrame) -> str:
    """Step 6c-g: the composite with the graph factor next to the primary, same quarters, same tests."""
    gc = cfg_g["composite"]["graph_challenger"]
    tg, t = rg["table"].set_index("model"), r["table"].set_index("model")
    rows = []
    for label, tab, res in (("primary: " + gc["replaces"], t, r), ("graph challenger: " + gc["name"], tg, rg)):
        p = tab.loc[PRIMARY]
        lo = tab[tab.index.str.startswith("leave out")]
        rows.append({"composite": label, "n": int(p["n"]), "rmse_beat_pts": p["rmse_beat_pts"], "benchmark_rmse": p["bench_rmse_same_quarters"],
                     "oos_r2_vs_bench": p["oos_r2_vs_bench"], "rmse_usdm": p["rmse_usdm"], "placebo_p": res["placebo_p"],
                     "leave_one_out_beating_bench": f"{int((lo['oos_r2_vs_bench'] > 0).sum())}/{len(lo)}",
                     "gate_passed": res["adopted"], "q3_2026_beat_pct": res["live"]["beat_hat_pct"], "q3_2026_revenue_usdm": res["live"]["revenue_hat_usdm"]})
    cmp = pd.DataFrame(rows).round(3)
    single = [f"single factor: {gc['replaces']}", f"single factor: {gc['name']}"]
    sf = pd.concat([t.loc[[single[0]]], tg.loc[[single[1]]]])[["n", "rmse_beat_pts", "bench_rmse_same_quarters", "oos_r2_vs_bench"]].round(3)
    lv = rg["live"]
    return "\n".join([
        "### Graph challenger (step 6c-g, decision B44)\n",
        f"One factor swapped: **{gc['replaces']}** (Logitech sell-through acceleration, one path, fixed lag 1) → **{gc['name']}** "
        "(the same sell-out proxy pushed through the step-5 supply-graph lag kernel: every route's weight and lag, graph as known on the "
        "forecast date, lags below one quarter put on t−1). Other factors, signs, z-scores and gate unchanged. The graph supplies the "
        "*timing* (a weighted lag), not separate demand per route: there is one sell-out proxy.\n",
        cmp.to_markdown(index=False), "",
        "The swapped factor on its own:\n", sf.to_markdown(), "",
        f"**Q3 2026, pre-registered** (`outputs/composite_graph_prereg_log.csv`): beat {lv['beat_hat_pct']:+.2f}% → revenue USD "
        f"{lv['revenue_hat_usdm']:.1f}m on the USD {lv['guide_mid']:.0f}m midpoint. Signed z: " + ", ".join(f"{k} {v:+.2f}" for k, v in lv["factor_z"].items()) + ".\n",
        prereg_view(log, gc.get("use_in_forecast", False), "challenger only, B44").to_markdown(index=False), "",
        "**Status.** Challenger only (config `composite.graph_challenger.use_in_forecast: false`): it was added after the factor search was "
        "stopped (B40), so its back-test is not a clean test and the peer panel cannot test it (the graph is Nordic's). "
        "It is scored on the 22 Oct print next to the primary composite and the benchmark.\n"])


def write_graph_challenger(rg: dict, r: dict, cfg_g: dict, d: Path) -> str:
    rg["table"].to_csv(d / "composite_graph_models.csv", index=False)
    rg["series"].round(3).to_csv(d / "composite_graph_walkforward.csv")
    log = preregister(rg, cfg_g, d, "composite_graph_prereg_log.csv")
    return graph_section(rg, r, cfg_g, log)
