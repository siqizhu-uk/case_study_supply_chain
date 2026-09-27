"""Step 5c: which breaks of the last four years changed the supply-chain relationships, tested one relationship at a time
(decision G22).

For each edge or link the table says what moved, the evidence, a verdict and how the model handles it:
    link    Nordic consumer YoY on Logitech sell-through YoY two quarters earlier (the graph's lag): Chow tests at the
            hand-set regime edges and at the transitions dated by step 3b's cycle state; a HAC Wald test of the same
            break (overlapping YoY data are autocorrelated). Chow's predictive test when a segment has fewer
            observations than parameters (Chow 1960).
    shares  Logitech's 10-K customer shares; the graph's lag kernel re-computed at each 10-K; Logitech + GN share of
            Nordic (step 2 path); Nordic's socket share at Logitech (FCC cohorts, Wilson intervals); Nordic's top-10 vs
            broad-market revenue in the 2023 destock; the bullwhip ratio by regime (step 3).
    events  node changes that are facts in filings (GN restructuring, SYNNEX-Tech Data, the 2026 supplier incident,
            memory-driven distributor ASPs): not tested, handled by definition.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from core.config import ROOT, step_outputs

VERDICTS = ("stable", "changed", "not distinguishable", "not testable", "event (in filings)", "input moved, relationship stable",
            "shock (timing)", "risk (not testable)")
S2 = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"
S3 = ROOT / "steps" / "step3_inventory_mechanism" / "outputs"
S5 = ROOT / "steps" / "step5_supply_graph" / "outputs"
WEIGHTS = ROOT / "config" / "supply_graph_weights.csv"


# ---------------------------------------------------------------------------------------------------- tests
def _ssr(y: np.ndarray, X: np.ndarray) -> float:
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    return float(e @ e)


def _design(x: np.ndarray) -> np.ndarray:
    return np.column_stack([np.ones(len(x)), x])


def chow(y, x, split: int) -> dict:
    """Break after the first `split` observations. Standard Chow F when both segments can be fitted, else Chow's
    predictive test (fit on the long segment, test whether the short one fits it)."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    n, k = len(y), 2
    X = _design(x)
    n1, n2 = split, n - split
    s_pool = _ssr(y, X)
    if min(n1, n2) > k:
        s1, s2 = _ssr(y[:split], X[:split]), _ssr(y[split:], X[split:])
        F = ((s_pool - s1 - s2) / k) / ((s1 + s2) / (n - 2 * k))
        return {"test": "Chow", "F": F, "df1": k, "df2": n - 2 * k, "p": float(stats.f.sf(F, k, n - 2 * k)), "n_pre": n1, "n_post": n2}
    long_ = slice(split, n) if n2 >= n1 else slice(0, split)
    n_long, n_short = (n2, n1) if n2 >= n1 else (n1, n2)
    s_long = _ssr(y[long_], X[long_])
    F = ((s_pool - s_long) / n_short) / (s_long / (n_long - k))
    return {"test": "Chow predictive", "F": F, "df1": n_short, "df2": n_long - k, "p": float(stats.f.sf(F, n_short, n_long - k)),
            "n_pre": n1, "n_post": n2}


def hac_break(y, x, split: int, lags: int = 1) -> dict:
    """y = a + b x + c D + d D x; Newey-West Wald test of c = d = 0 (F form). Not computed when a segment has fewer than
    4 observations: with 2-3 points a segment's own line fits almost exactly and the HAC variance collapses."""
    y, x = np.asarray(y, float), np.asarray(x, float)
    D = (np.arange(len(y)) >= split).astype(float)
    X = np.column_stack([np.ones(len(y)), x, D, D * x])
    n, k = X.shape
    if min(split, len(y) - split) < 4 or n - k < 2:                  # each segment needs residual variation of its own
        return {"F_hac": np.nan, "p": np.nan}
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    xtx = np.linalg.pinv(X.T @ X)
    u = X * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        g = u[L:].T @ u[:-L]
        S += (1 - L / (lags + 1)) * (g + g.T)
    V = xtx @ S @ xtx * n / (n - k)
    R = np.array([[0, 0, 1, 0], [0, 0, 0, 1]], float)
    rb = R @ b
    W = float(rb @ np.linalg.pinv(R @ V @ R.T) @ rb)
    F = W / 2
    return {"F_hac": F, "p": float(stats.f.sf(F, 2, n - k)), "slope_pre": b[1], "slope_post": b[1] + b[3]}


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return np.nan, np.nan
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return c - h, c + h


# ---------------------------------------------------------------------------------------------------- the table
def _link_rows(p: pd.DataFrame, cfg: dict) -> list[dict]:
    c = cfg["relationship_breaks"]
    x = (p["logi_sales_yoy"] + p["logi_st_gap"]).shift(c["link_lag_quarters"])
    d = pd.concat([p["nordic_consumer_yoy"].rename("y"), x.rename("x")], axis=1).dropna()
    dates = [(q, "hand-set regime edge") for q in c["event_dates"]]
    cyc = S3 / "cycle_state.csv"
    if cyc.exists():
        st = pd.read_csv(cyc).dropna(subset=["state"]).set_index("quarter")["state"]
        st = st[st.index >= str(d.index.min())]
        for q, prev, cur in zip(st.index[1:], st.values[:-1], st.values[1:]):
            if prev != cur and "building" in (prev, cur):
                dates.append((q, f"cycle state {prev} -> {cur} (step 3b, data-dated)"))
    rows = []
    for q, how in dates:
        split = int((d.index < pd.Period(q, "Q")).sum())
        if split == 0 or split >= len(d):
            continue
        ch = chow(d["y"].values, d["x"].values, split)
        hac = hac_break(d["y"].values, d["x"].values, split, c["hac_lags"])
        sig = ch["p"] < c["alpha"] and (np.isnan(hac.get("p", np.nan)) or hac["p"] < c["alpha"])
        slopes = (f"; slope {hac['slope_pre']:+.2f} before, {hac['slope_post']:+.2f} after" if "slope_pre" in hac else "")
        rows.append({"relationship": "Nordic consumer on Logitech sell-through (t-2)", "edge": "Logitech -> Nordic (E02-E08 chain)",
                     "break": q, "dated_by": how, "test": ch["test"], "stat": round(ch["F"], 2), "p": round(ch["p"], 3),
                     "p_hac": round(hac.get("p", np.nan), 3), "n_pre": ch["n_pre"], "n_post": ch["n_post"],
                     "evidence": f"{ch['test']} F {ch['F']:.2f} (p {ch['p']:.3f}); HAC Wald p {hac.get('p', np.nan):.3f}{slopes}; n {ch['n_pre']} / {ch['n_post']}",
                     "verdict": "changed" if sig else "not distinguishable",
                     "treatment": "Lag models trained on all quarters, the link carries no weight in the guided quarter (step 7c weight 0); "
                                  "sample too short to estimate a slope per regime"})
    return rows


def _stability_rows(cfg: dict) -> list[dict]:
    c = cfg["relationship_breaks"]
    rows = []
    w = pd.read_csv(WEIGHTS)
    rng = {k: (w[k].max() - w[k].min()) * 100 for k in ("amazon", "ingram", "tdsynnex")}
    rows.append({"relationship": "Logitech 10-K customer shares", "edge": "Logitech -> Amazon / Ingram / TD Synnex (E11-E13)", "break": "FY22-FY26",
                 "dated_by": "each 10-K", "evidence": "; ".join(f"{k} {w[k].min()*100:.0f}-{w[k].max()*100:.0f}%" for k in rng),
                 "verdict": "stable" if max(rng.values()) <= c["stable_share_range_pts"] else "changed",
                 "treatment": "graph uses the share of the 10-K known at each date (point in time)"})
    kh = S5 / "graph_kernel_history.csv"
    if kh.exists():
        k = pd.read_csv(kh, index_col=0)
        r = float(k["1"].max() - k["1"].min())
        rows.append({"relationship": "Graph lag kernel re-computed at each 10-K", "edge": "all paths end demand -> Nordic", "break": "FY22-FY26",
                     "dated_by": "each 10-K", "evidence": f"weight on lag 1 quarter {k['1'].min():.2f}-{k['1'].max():.2f}",
                     "verdict": "stable" if r <= c["stable_kernel_range"] else "changed",
                     "treatment": "kernel recomputed point in time; no break handling needed"})
    if S2.exists():
        ap = pd.read_csv(S2)
        s = ap.set_index("quarter")["share_total_indirect_p50"]
        rows.append({"relationship": "Logitech + GN share of Nordic revenue", "edge": "Nordic node (attribution, step 2)", "break": "2022-2024",
                     "dated_by": "step 2 path", "evidence": f"{s.iloc[0]:.1f}% ({s.index[0]}) -> {s.max():.1f}% ({s.idxmax()}) -> {s.iloc[-1]:.1f}% ({s.index[-1]}): "
                     "Nordic's broad market fell, the key accounts did not",
                     "verdict": "changed", "treatment": "time-varying share path read point in time by steps 4, 6, 7"})
        coh = ap.drop_duplicates("socket_cohort")[["socket_cohort", "socket_n", "socket_k_nordic"]].dropna()
        coh = coh[~coh["socket_cohort"].str.contains("extrapolated|widened")]
        if len(coh) >= 2:
            ci = [(r.socket_cohort, int(r.socket_k_nordic), int(r.socket_n), *_wilson(int(r.socket_k_nordic), int(r.socket_n))) for r in coh.itertuples()]
            overlap = ci[0][4] >= ci[-1][3]
            rows.append({"relationship": "Nordic socket share at Logitech (FCC photos)", "edge": "Nordic -> Logitech content (E02, E03)", "break": "2022-2026",
                         "dated_by": "FCC grant cohorts", "evidence": "; ".join(f"{a}: {k}/{n} ({lo:.2f}-{hi:.2f})" for a, k, n, lo, hi in ci),
                         "verdict": "not distinguishable" if overlap else "changed",
                         "treatment": "share path uses the cohort of each date; the rise is within sampling error"})
    tb = S3 / "nordic_top10_vs_broad.csv"
    if tb.exists():
        t = pd.read_csv(tb).set_index("year")
        rows.append({"relationship": "Nordic top-10 customers vs broad market", "edge": "Nordic direct vs distributor route (E01 vs E02/E03)", "break": "2023",
                     "dated_by": "Nordic annual reports", "evidence": f"2023 YoY: top-10 {t.loc[2023, 'top10_yoy_pct']:+.1f}%, broad market {t.loc[2023, 'broad_yoy_pct']:+.1f}%",
                     "verdict": "changed", "treatment": "amplitude split by route: Logitech slice multiplier 1.0 (key account), broad market higher (step 3)"})
    bw = S3 / "bullwhip_links.csv"
    if bw.exists():
        b = pd.read_csv(bw).set_index(["window", "link"])
        if ("destock", "B") in b.index and ("normal", "B") in b.index:
            de, no = b.loc[("destock", "B")], b.loc[("normal", "B")]
            overlap = de["sd_ratio_p95"] >= no["sd_ratio_p5"] and no["sd_ratio_p95"] >= de["sd_ratio_p5"]
            rows.append({"relationship": "Amplification Nordic consumer / Logitech sell-in", "edge": "whole chain (bullwhip, step 3)", "break": "2022Q3 / 2024Q2",
                         "dated_by": "hand-set regimes", "evidence": f"sd ratio destock {de['sd_ratio']:.2f} ({de['sd_ratio_p5']:.2f}-{de['sd_ratio_p95']:.2f}), "
                         f"normal {no['sd_ratio']:.2f} ({no['sd_ratio_p5']:.2f}-{no['sd_ratio_p95']:.2f}); normal is high because Logitech barely moves (small denominator)",
                         "verdict": "not distinguishable" if overlap else "changed",
                         "treatment": "no regime-specific multiplier in any model; amplitude_multiplier is documentation only"})
    return rows


def _event_rows(cfg: dict) -> list[dict]:
    sb = cfg["structural_breaks"]
    picks = {"gn_steelseries_consolidation_2022": ("GN node composition", "GN node"),
             "gn_hearing_discontinued_2026": ("GN node composition", "GN node"),
             "tdsynnex_techdata_merger_2021": ("Distributor node (SYNNEX + Tech Data)", "TD Synnex node"),
             "logitech_supplier_incident_2026": ("Supplier incident 2026", "a Logitech supply edge"),
             "distributor_asp_inflation_2026": ("Distributor dollars vs units 2026", "Ingram / TD Synnex flows")}
    return [{"relationship": name, "edge": edge, "break": key.split("_")[-1] if key.split("_")[-1].isdigit() else "",
             "dated_by": "filings", "evidence": sb[key].get("note", key), "verdict": "event (in filings)",
             "treatment": f"config structural_breaks.{key} (a switch)"} for key, (name, edge) in picks.items() if key in sb]


def relationship_breaks(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    return pd.DataFrame(_stability_rows(cfg) + _link_rows(p, cfg) + _event_rows(cfg))


def breaks_md(t: pd.DataFrame) -> str:
    out = ["", "## 5c. Which breaks changed the relationships (decision G22)", "",
           "Downstream structure (10-K shares, lag kernel) is the reference; each row is one relationship, its evidence and how the model handles it. "
           "Full table: outputs/relationship_breaks.csv.", "",
           t[["relationship", "break", "evidence", "verdict", "treatment"]].to_markdown(index=False), ""]
    ev = S5 / "event_breaks.csv"
    if ev.exists():
        e = pd.read_csv(ev)
        out += ["### Events of 2021-26, one by one (decision G28)", "",
                "Each event at a date fixed in config (relationship_breaks.event_breaks): does it change a relationship, only move its input, or is it "
                "a shock, a proxy break or a forward risk? Full table: outputs/event_breaks.csv; decomposition of the 2022-24 fall: "
                "outputs/normalisation_decomposition.csv.", "",
                e[["event", "relationship", "break", "evidence", "verdict", "treatment"]].to_markdown(index=False), ""]
    return "\n".join(out)


def run_relationship_breaks(p: pd.DataFrame, cfg: dict, write: bool = True) -> pd.DataFrame:
    t = relationship_breaks(p, cfg)
    if write:
        t.to_csv(step_outputs("step5_supply_graph") / "relationship_breaks.csv", index=False)
        run_event_breaks(p, cfg)                          # G28: events of 2021-26, one by one
    return t


# ---------------------------------------------------------------------------------------------------- events 2021-26
# Decision G28: the brief asks which events changed the relationships. Each event below is tested at a date fixed in
# config (relationship_breaks.event_breaks) and typed: relationship break, input moved (relationship stable), shock,
# proxy break (a context series stops describing Nordic's market) or forward risk.

def tariff_price_effect(p: pd.DataFrame, cfg: dict) -> pd.Series:
    """Points of Logitech's dollar sales YoY that are price, not units, after the April 2025 US price step. Size from the
    quoted gross-margin lift of the price actions: GM rises by c*x/(1+x) for a price step x when cost/revenue = c."""
    t = cfg["relationship_breaks"]["event_breaks"]["tariff_2025"]
    c = 1 - t["gm_rate"]
    r = t["gm_lift_from_price_pts"] / 100 / c
    x = r / (1 - r) * 100                                   # price step, % of total sales
    w = {pd.Period(k, "Q"): float(v) for k, v in t["price_effect_weight"].items()}
    return pd.Series({q: x * w.get(q, 0.0) for q in p.index}, name="price_effect_pts")


def normalisation_decomposition(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Nordic consumer YoY = Logitech+GN slice (share of Nordic consumer a year earlier x Logitech sell-through YoY two
    quarters earlier, key-account multiplier 1) + the rest of Nordic (broad market via distributors)."""
    lo, hi = cfg["relationship_breaks"]["event_breaks"]["normalisation_window"]
    lag = cfg["relationship_breaks"]["link_lag_quarters"]
    ap = pd.read_csv(S2)
    share = pd.Series(ap["share_consumer_indirect_p50"].values, index=pd.PeriodIndex(ap["quarter"], freq="Q")) / 100
    share = share.reindex(p.index).bfill().ffill()
    st = (p["logi_sales_yoy"] + p["logi_st_gap"]).shift(lag)
    d = pd.DataFrame({"nordic_consumer_yoy": p["nordic_consumer_yoy"], "share_a_year_before": share.shift(4).fillna(share),
                      "logitech_sellthrough_yoy_t_minus_2": st}).loc[lo:hi].dropna()
    d["slice_contribution"] = d["share_a_year_before"] * d["logitech_sellthrough_yoy_t_minus_2"]
    d["rest_of_nordic"] = d["nordic_consumer_yoy"] - d["slice_contribution"]
    return d


def _split_corr(x: pd.Series, y: pd.Series, q: str) -> tuple[float, float, int, int]:
    d = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    pre, post = d[d.index < pd.Period(q, "Q")], d[d.index >= pd.Period(q, "Q")]
    c = lambda z: float(z["x"].corr(z["y"])) if len(z) > 2 else np.nan  # noqa: E731
    return c(pre), c(post), len(pre), len(post)


def _fisher_p(r1: float, r2: float, n1: int, n2: int) -> float:
    """Two-sided p for equal correlations in two independent samples (Fisher z)."""
    if min(n1, n2) <= 3 or np.isnan(r1) or np.isnan(r2):
        return np.nan
    z = (np.arctanh(r1) - np.arctanh(r2)) / np.sqrt(1 / (n1 - 3) + 1 / (n2 - 3))
    return float(2 * stats.norm.sf(abs(z)))


def _welch(a: pd.Series, b: pd.Series) -> tuple[float, float]:
    if len(a) < 2 or len(b) < 2:
        return np.nan, np.nan
    r = stats.ttest_ind(a, b, equal_var=False)
    return float(r.statistic), float(r.pvalue)


def event_rows(p: pd.DataFrame, cfg: dict) -> list[dict]:
    c = cfg["relationship_breaks"]
    ev = c["event_breaks"]
    rows = []
    # 1. 2025 US tariffs ------------------------------------------------------------------------------------------
    pe = tariff_price_effect(p, cfg)
    x_raw = (p["logi_sales_yoy"] + p["logi_st_gap"]).shift(c["link_lag_quarters"])
    x_adj = (p["logi_sales_yoy"] + p["logi_st_gap"] - pe).shift(c["link_lag_quarters"])
    first_affected = (pd.Period(ev["tariff_2025"]["event_quarter"], "Q") + c["link_lag_quarters"])
    tests = {}
    for name, x in (("dollars", x_raw), ("units", x_adj)):
        d = pd.concat([p["nordic_consumer_yoy"].rename("y"), x.rename("x")], axis=1).dropna()
        split = int((d.index < first_affected).sum())
        tests[name] = chow(d["y"].values, d["x"].values, split) if 0 < split < len(d) else {"p": np.nan, "n_pre": split, "n_post": 0, "test": "n/a", "F": np.nan}
    step = float(pe.max())
    am = p["logi_americas_yoy"]
    rows.append({"event": "tariff 2025", "relationship": "Logitech dollar sales as the unit driver of Nordic's chips", "edge": "Logitech -> Nordic (driver)",
                 "break": ev["tariff_2025"]["event_quarter"], "dated_by": "US price step, April 2025 (Logitech calls)",
                 "evidence": (f"price lifted Logitech's gross margin 1.5 pts (Q2 FY26 call) = a price step of {step:.1f}% of sales, in YoY from 2025Q2 to "
                              f"early 2026Q2; Americas sell-in {am.get(pd.Period('2025Q2','Q'), np.nan):+.1f}% / {am.get(pd.Period('2025Q3','Q'), np.nan):+.1f}% "
                              f"(2025Q2/Q3) while group sales grew and sell-through ran ahead ('lower demand early in the quarter as a result of the pricing actions')"),
                 "verdict": "changed", "type": "relationship break (price vs units)",
                 "treatment": (f"new: the unit driver removes the price step ({step:.1f} pts at most). Logitech's own dollar forecast needs no change; "
                               "Nordic's chain term (weight 0 at h=1) moves by well under 1m")})
    rows.append({"event": "tariff 2025", "relationship": "Nordic consumer on Logitech sell-through (t-2), across the price step", "edge": "Logitech -> Nordic",
                 "break": str(first_affected), "dated_by": "first Nordic quarter whose t-2 driver carries the step",
                 "test": tests["units"]["test"], "p": round(tests["units"]["p"], 3), "n_pre": tests["units"]["n_pre"], "n_post": tests["units"]["n_post"],
                 "evidence": (f"{tests['dollars']['test']}: p {tests['dollars']['p']:.3f} on the dollar driver, {tests['units']['p']:.3f} on the unit driver; "
                              f"n {tests['units']['n_pre']} / {tests['units']['n_post']} (too few quarters after the step to have power)"),
                 "verdict": "changed" if min(tests["dollars"]["p"], tests["units"]["p"]) < c["alpha"] else "not distinguishable",
                 "type": "relationship break test", "treatment": "reported; no slope re-estimated on three quarters"})
    inv = p["logi_inv_days"]
    rows.append({"event": "tariff 2025", "relationship": "timing of Logitech's purchases (chip orders to ODMs)", "edge": "ODM -> Logitech",
                 "break": "2025Q1", "dated_by": "purchases pulled in ahead of new tariffs (Q2 FY26 call)",
                 "evidence": (f"Logitech inventory {inv.get(pd.Period('2025Q1','Q'), np.nan):.0f} days in 2025Q1 vs {inv.loc['2024Q1':'2024Q3'].mean():.0f} "
                              f"a year earlier; back to {inv.get(pd.Period('2025Q2','Q'), np.nan):.0f} in 2025Q2"),
                 "verdict": "shock (timing)", "type": "shock",
                 "treatment": "no change to the lags; a one-quarter pull-forward, reversed in 2025Q2. Production moved out of China for US (<10% by Dec 2025): lag change not measurable"})
    # 2. post-COVID normalisation --------------------------------------------------------------------------------
    dec = normalisation_decomposition(p, cfg)
    yr = dec.loc["2023Q1":"2023Q4"]
    link24 = [r for r in _link_rows(p, cfg) if r["break"] == "2024Q2"]
    rows.append({"event": "post-COVID normalisation", "relationship": "end demand vs the channel in Nordic's 2022-24 fall", "edge": "end demand -> Nordic",
                 "break": "/".join(ev["normalisation_window"]), "dated_by": "Logitech sell-through YoY negative",
                 "evidence": (f"2023: Nordic consumer {yr['nordic_consumer_yoy'].mean():+.0f}% YoY, of which the Logitech+GN slice {yr['slice_contribution'].mean():+.1f} pts "
                              f"and the rest of Nordic {yr['rest_of_nordic'].mean():+.0f} pts; top-10 customers -3% vs broad market -46% (2023). "
                              + (f"Link at 2024Q2: {link24[0]['evidence']}" if link24 else "")),
                 "verdict": "input moved, relationship stable", "type": "input moved",
                 "treatment": "end demand enters through the driver; the fall of 2023 is the channel (building / destock state), not a new relationship"})
    # 3. AI / memory cycle -----------------------------------------------------------------------------------------
    pre, post, n1, n2 = _split_corr(p["wsts_yoy"], p["nordic_rev_yoy"], ev["ai_cycle_quarter"])
    pz = _fisher_p(pre, post, n1, n2)
    dw = pd.concat([p["nordic_rev_yoy"].rename("y"), p["wsts_yoy"].rename("x")], axis=1).dropna()
    cw = chow(dw["y"].values, dw["x"].values, int((dw.index < pd.Period(ev["ai_cycle_quarter"], "Q")).sum()))
    w_last = p["wsts_yoy"].dropna()
    rows.append({"event": "AI / memory cycle", "relationship": "industry sales (WSTS) as a proxy for Nordic's market", "edge": "context series",
                 "break": ev["ai_cycle_quarter"], "dated_by": "AI data-centre spending (May 2023 guidance shock); dated with the data in view",
                 "test": cw["test"], "p": round(cw["p"], 3), "n_pre": cw["n_pre"], "n_post": cw["n_post"],
                 "evidence": (f"corr(WSTS YoY, Nordic YoY) {pre:+.2f} before (n {n1}) vs {post:+.2f} after (n {n2}), Fisher-z p {pz:.2f}; "
                              f"{cw['test']} p {cw['p']:.3f}; WSTS {w_last.iloc[-1]:+.0f}% in {w_last.index[-1]} vs Nordic "
                              f"{p['nordic_rev_yoy'].dropna().iloc[-1]:+.0f}%"),
                 "verdict": "changed" if min(pz, cw["p"]) < c["alpha"] else "not distinguishable", "type": "proxy break",
                 "treatment": "WSTS / SIA are context only, never a regressor (Pipeline B)"})
    gap = (p["snx_sales_yoy"] - p["logi_sales_yoy"]).dropna()
    mq = pd.Period(ev["memory_cycle_quarter"], "Q")
    g0, g1 = gap[(gap.index < mq) & (gap.index >= pd.Period(ev["gap_compare_from"], "Q"))], gap[gap.index >= mq]
    tg, pg = _welch(g1, g0)
    rows.append({"event": "AI / memory cycle", "relationship": "distributor dollars as a proxy for peripherals demand", "edge": "Ingram / TD Synnex flows",
                 "break": ev["memory_cycle_quarter"], "dated_by": "memory price surge; dated with the data in view",
                 "test": "Welch t on the gap", "p": round(pg, 3), "n_pre": len(g0), "n_post": len(g1),
                 "evidence": (f"TD Synnex minus Logitech sales YoY: {g0.mean():+.1f} pts on average from {ev['gap_compare_from']} (n {len(g0)}, sd {g0.std(ddof=1):.1f}), "
                              f"{g1.mean():+.1f} after (n {len(g1)}: " + ", ".join(f"{v:+.0f}" for v in g1) + f"), Welch t {tg:.1f} (p {pg:.2f}); rising each quarter; "
                              f"TD Synnex {p['snx_sales_yoy'].dropna().iloc[-1]:+.0f}% in {p['snx_sales_yoy'].dropna().index[-1]};"),
                 "verdict": "changed" if pg < c["alpha"] else "not distinguishable", "type": "proxy break",
                 "treatment": "distributor dollars are not a driver; ASP tailwind removed (config structural_breaks); the TD Synnex light is context only"})
    cyc = S3 / "cycle_state.csv"
    md = (pd.read_csv(cyc).set_index("quarter")["days"].rename(index=lambda q: pd.Period(q, "Q")) if cyc.exists() else pd.Series(dtype=float))
    rows.append({"event": "AI / memory cycle", "relationship": "the channel-cycle signal (Microchip MCU distributor days)", "edge": "cycle state (step 3b)",
                 "break": ev["memory_cycle_quarter"], "dated_by": "as above",
                 "evidence": ("Microchip distributor days " + ", ".join(f"{v:.0f}" for v in md.loc[ev['memory_cycle_quarter']:].dropna())
                              + " since then: no memory or AI inflation in the MCU channel") if len(md.dropna()) else "MCU channel, no memory content",
                 "verdict": "stable", "type": "not affected", "treatment": "the cycle state keeps its signal"})
    # 4. forward risk ---------------------------------------------------------------------------------------------
    rows.append({"event": "Nordic capacity", "relationship": "Nordic revenue = demand (vs = supply, as in 2021-22)", "edge": "Nordic node",
                 "break": "2026", "dated_by": "Nordic Q2 2026 call",
                 "evidence": "CEO: 'It hasn't limited us yet, but it's very tight. It's running at its almost maximum pace.' nRF54 / nRF5340 lead time 16 weeks",
                 "verdict": "risk (not testable)", "type": "forward risk",
                 "treatment": "watched: lead time above 20 weeks or stock down 50% (monitoring plan W4); if it binds, the 2021-22 treatment applies"})
    return rows


def run_event_breaks(p: pd.DataFrame, cfg: dict, write: bool = True) -> pd.DataFrame:
    t = pd.DataFrame(event_rows(p, cfg))
    if write:
        d = step_outputs("step5_supply_graph")
        t.to_csv(d / "event_breaks.csv", index=False)
        normalisation_decomposition(p, cfg).round(2).assign(quarter=lambda x: x.index.astype(str)).to_csv(d / "normalisation_decomposition.csv", index=False)
    return t
