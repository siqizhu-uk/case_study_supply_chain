"""Step 4 report section and dashboard snippet for the edge-by-edge lag (edge_lags.py, decisions L4-L9).

Order = order of the reasoning: chain, priors with their evidence, the two regressions, prior + data -> posterior, route
totals, then the plain-English reading. Every number and every verdict is computed from the run's tables.
"""
from __future__ import annotations

import html
import re

import numpy as np
import pandas as pd

from core.config import step_outputs

GRAPH_MC = ("signal", "Amazon direct")      # step 5's order-signal Monte Carlo row that matches the Amazon route total
CHAIN = ("    Amazon / Ingram Micro / TD Synnex --edge 1--> Logitech / GN --edge 2--> Nordic\n"
         "    edge 1 = customers' sell-out -> their orders to the brand (= brand sell-in)\n"
         "    edge 2 = brand sell-in -> build / component orders -> Nordic revenue (ODM / EMS and Nordic's distributors folded in)")


def _rng(lo, mid, hi) -> str:
    f = lambda v: "∞" if np.isinf(v) else f"{v:.1f}"                  # noqa: E731
    return f"{f(mid)} ({f(lo)}–{f(hi)})" if pd.notna(lo) and pd.notna(hi) else f(mid)


def prior_df(pri: pd.DataFrame) -> pd.DataFrame:
    t = pri.assign(prior=[_rng(r.prior_low, r.prior_mid, r.prior_high) for r in pri.itertuples()],
                   phys=[_rng(r.prior_phys_low, r.prior_phys_mid, r.prior_phys_high) if "prior_phys_mid" in pri else "–"
                         for r in pri.itertuples()])
    t = t[["edge", "brand", "route", "flow_share", "prior", "phys", "grade", "edges", "evidence"]]
    return t.rename(columns={"prior": "prior wk mid (low–high), order signal", "phys": "physical dwell only",
                             "flow_share": "share of brand flow"})


def prior_table(pri: pd.DataFrame) -> str:
    return prior_df(pri).to_markdown(index=False)


def edge1_table(r1: pd.DataFrame) -> str:
    return edge1_df(r1).to_markdown(index=False)


def edge1_df(r1: pd.DataFrame) -> pd.DataFrame:
    t = r1.assign(lag=[_rng(r.lag_lo_weeks, r.lag_weeks, r.lag_hi_weeks) for r in r1.itertuples()],
                  rho_ci=[f"{r.rho:.2f} ({r.rho_lo:.2f}–{r.rho_hi:.2f})" if pd.notna(r.rho_lo) else f"{r.rho:.2f}" for r in r1.itertuples()])
    return t[["brand", "spec", "n", "rho_ci", "lag", "koyck_weeks", "interval"]].rename(columns={
        "rho_ci": "rho (90%)", "lag": "mean lag wk, continuous (90%)", "koyck_weeks": "Koyck wk"}).round(1)


def edge2_table(r2: pd.DataFrame) -> str:
    return edge2_df(r2).to_markdown(index=False)


def edge2_df(r2: pd.DataFrame) -> pd.DataFrame:
    t = r2.assign(tau=[_rng(r.ci_lo_weeks, r.tau_weeks, r.ci_hi_weeks) for r in r2.itertuples()],
                  set=[f"{r.set_lo_weeks:.0f}–{r.set_hi_weeks:.0f}" for r in r2.itertuples()])
    cols = ["brand", "fit", "n", "first_quarter", "slope", "slope_kind", "kappa_weeks", "tau", "set", "coverage"]
    return t[cols].rename(columns={"tau": "tau wk (bootstrap 90%)", "set": "90% profile / near-optimal set, wk",
                                   "kappa_weeks": "control lag wk", "coverage": "share of 0-52 wk covered"}).round(2)


def combined_table(post: pd.DataFrame) -> str:
    return combined_df(post).to_markdown(index=False)


def combined_df(post: pd.DataFrame) -> pd.DataFrame:
    t = post.assign(prior=[_rng(r.prior_low, r.prior_mid, r.prior_high) for r in post.itertuples()],
                    estimate=[_rng(r.estimate_lo_weeks, r.estimate_weeks, r.estimate_hi_weeks) if pd.notna(r.estimate_weeks) else "–"
                              for r in post.itertuples()],
                    posterior=[_rng(r.post_low, r.post_mid, r.post_high) for r in post.itertuples()])
    return t[["edge", "brand", "route", "prior", "estimate", "posterior", "moved_by_weeks", "reading"]].rename(
        columns={"moved_by_weeks": "moved by wk"}).round(1)


def totals_table(tot: pd.DataFrame) -> str:
    return totals_df(tot).to_markdown(index=False)


def totals_df(tot: pd.DataFrame) -> pd.DataFrame:
    t = tot.assign(sim=[f"{r.sim_p5_weeks:.0f}–{r.sim_p95_weeks:.0f}" for r in tot.itertuples()],
                   co=[f"{r.comonotone_low_weeks:.0f}–{r.comonotone_high_weeks:.0f}" for r in tot.itertuples()])
    t = t if "physical_weeks" in t else t.assign(physical_weeks=np.nan)
    return t[["route", "edge1_weeks", "edge2_weeks", "total_weeks", "total_quarters", "sim", "co", "physical_weeks"]].rename(columns={
        "edge1_weeks": "edge 1 wk", "edge2_weeks": "edge 2 wk", "total_weeks": "total wk", "total_quarters": "quarters",
        "physical_weeks": "physical dwell only, wk",
        "sim": "90% range, edges independent", "co": "range if edges move together"}).round(1)


def _cell(post: pd.DataFrame, edge: str, brand: str) -> pd.Series:
    return post[(post["edge"] == edge) & (post["brand"] == brand) & (post["route"] == "all routes (flow-weighted)")].iloc[0]


def bullet_edge1(post: pd.DataFrame, r1: pd.DataFrame) -> str:
    c = _cell(post, "edge 1", "logitech")
    if c["informative"]:
        return (f"- **Edge 1 is short and the data support it.** Prior {_rng(c.prior_low, c.prior_mid, c.prior_high)} wk; the channel "
                f"index's partial adjustment gives {_rng(c.estimate_lo_weeks, c.estimate_weeks, c.estimate_hi_weeks)} wk; posterior "
                f"{c.post_mid:.1f} wk ({c.reading}).")
    mu = r1[r1["primary"] & (r1["brand"] == "logitech")].iloc[0]
    ols = r1[r1["spec"].str.startswith("AR(1) + trend, OLS")].iloc[0]
    return (f"- **Edge 1 is short by structure; the quarterly data cannot confirm it.** The prior {_rng(c.prior_low, c.prior_mid, c.prior_high)} wk "
            f"comes from the customers' inventory cover (evidence above). The channel index's reversion gives a median-unbiased mean lag of "
            f"{_rng(mu.lag_lo_weeks, mu.lag_weeks, mu.lag_hi_weeks)} wk (rho {mu.rho:.2f}, 90% {mu.rho_lo:.2f}–{mu.rho_hi:.2f}, n {mu.n}); "
            f"{'the interval runs from full correction within the quarter to no reversion' if np.isinf(mu.lag_hi_weeks) else 'the interval is too wide to place the lag'}"
            f", so the posterior is the prior. The plain OLS reading, {ols.lag_weeks:.0f} wk (bootstrap {ols.lag_lo_weeks:.0f}–{ols.lag_hi_weeks:.0f}), would look "
            "like a confirmation only because OLS rho on ~13 quarters is biased towards zero (P90). A lag under one quarter is below what "
            "quarterly data resolve, except through this reversion speed.")


def _pct_span(v: pd.Series) -> str:
    lo, hi = f"{v.min():.0%}", f"{v.max():.0%}"
    return lo if lo == hi else f"{lo}–{hi}"


def bullet_edge2(post: pd.DataFrame, r2: pd.DataFrame, s: dict, m: dict) -> str:
    c = _cell(post, "edge 2", "logitech")
    pr = r2[(r2["fit"] == "primary") & (r2["brand"] == "logitech")].iloc[0]
    sens = r2[(r2["slope_kind"] == "fixed s x m") & (r2["brand"] == "logitech")]
    u = r2[r2["fit"].str.startswith("unconstrained")].iloc[0]
    inside = pr.set_lo_weeks <= c.prior_mid <= pr.set_hi_weeks
    return (f"- **Edge 2 is sized by attribution and timed by structure.** With Logitech's slice fixed at s × m = {pr.slope:.2f} "
            f"(share of Nordic consumer {s['logitech']['mid']:.0%} × slice multiplier {m['logitech']['mid']:.2f}), every lag from "
            f"{pr.set_lo_weeks:.0f} to {pr.set_hi_weeks:.0f} wk is inside the 90% profile set; across the {len(sens)} constrained fits the "
            f"90% interval covers {_pct_span(sens['coverage'])} of 0–52 wk. The data "
            f"{'fail to contradict the prior and cannot confirm it' if inside else 'put the prior outside their set'}: posterior "
            f"{_rng(c.post_low, c.post_mid, c.post_high)} wk ({'= the prior' if not c.informative else c.reading}). Left free, the slope is {u.slope:.2f}, "
            f"{u.slope / pr.slope:.1f}× the slice: what a free fit times is the common cycle, not Logitech's orders (P77, P91).")


def bullet_totals(tot: pd.DataFrame) -> str:
    t = tot.set_index("route")
    a, i, f, g = (t.loc[k] for k in ("Amazon -> Logitech -> Nordic", "Ingram / TD Synnex -> Logitech -> Nordic",
                                      "all Logitech routes (flow-weighted)", "all GN routes (flow-weighted)"))
    return (f"- **Amazon sell-out → Nordic revenue ≈ {a.total_weeks:.0f} weeks ({a.total_quarters:.1f} quarters)**: edge 1 {a.edge1_weeks:.1f} + "
            f"edge 2 {a.edge2_weeks:.1f} wk; 90% range {a.sim_p5_weeks:.0f}–{a.sim_p95_weeks:.0f} wk with the edges independent, "
            f"{a.comonotone_low_weeks:.0f}–{a.comonotone_high_weeks:.0f} if they stretch together. Through Ingram / TD Synnex "
            f"{i.total_weeks:.0f} wk; flow-weighted over Logitech's routes {f.total_weeks:.0f} wk (GN {g.total_weeks:.0f} wk). "
            f"These are order-signal lags; the physical dwell alone is {a.physical_weeks:.0f} / {i.physical_weeks:.0f} / "
            f"{f.physical_weeks:.0f} wk: the rest is the buyers' planning (review period + forecast smoothing, grade D, G25).")


def bullet_regime(r1: pd.DataFrame, r2: pd.DataFrame, cfg: dict, index: pd.Series, post: pd.DataFrame) -> str:
    share = cfg["edge_lags"]["uninformative_share"]
    sc = cfg["regimes"]["supply_constrained"]
    nm = r2[r2["fit"] == "regime: normal only"].iloc[0]
    dm = r2[r2["fit"] == "regime: destock intercept"].iloc[0]
    mu = r1[r1["primary"] & (r1["brand"] == "logitech")].iloc[0]
    ix = index.dropna()
    turn = cfg["regimes"]["normal"]["quarters"][0]
    return (f"- **Regime dependence.** The fits use the destock and normal quarters only: in {sc['quarters'][0]}–{sc['quarters'][1]} "
            f"Nordic revenue was wafer supply, and config stretches the lag ×{sc['lag_multiplier']:.0f} there. Normal quarters alone (n {nm.n}) "
            f"cover {nm.coverage:.0%} of the range; a destock intercept gives tau {dm.tau_weeks:.0f} wk with {dm.coverage:.0%} covered - "
            f"{'no regime pins edge 2' if min(nm.coverage, dm.coverage) >= share else 'one regime narrows edge 2: read it with its n'}. Edge 1's persistence (median-unbiased {mu.lag_weeks:.0f} wk) comes from a sample that starts in the "
            f"destock (channel {ix.iloc[0]:+.1f} wk vs target in {ix.index[0]}, {ix.get(turn, np.nan):+.1f} wk by {turn}): if real, it is "
            "a drain of the channel target, not the reorder lag of a normal channel"
            + (", so the normal-channel prior stands." if not _cell(post, "edge 1", "logitech").informative else
               "; the posterior mixes it into the prior - read it as a destock-weighted lag."))


def section_md(res: dict, cfg: dict) -> str:
    """Step 4 section 3: the lag of this chain, edge by edge (reasoning first)."""
    el, pri, post = cfg["edge_lags"], res["priors"], res["combined"]
    r1, r2, s, m = res["edge1"], res["edge2"], res["shares"], res["multipliers"]
    gn_n = res.get("gn_index_n", 0)
    return "\n".join([
        "## 3. Lag, edge by edge: Amazon / Ingram / TD Synnex -> Logitech / GN -> Nordic\n", "```", CHAIN, "```\n",
        "### 3a. Reasoning first: the prior per edge (decisions L4, L5)\n",
        f"- Edge 1: {el['mechanism']['edge1']}.", f"- Edge 2: {el['mechanism']['edge2']}.",
        "- Numbers: step 5's graph (`config/supply_graph.csv`), flow-weighted over paths and cut at the brand node; low / high = every "
        "edge at its grade-widened low / high lag (grade C = at least ±50%), read as a 90% range.",
        f"- Basis ({pri['basis'].iloc[0] if 'basis' in pri else 'physical'}, G25): the brief asks when a demand change reaches Nordic's revenue, "
        "which is an order-signal lag = physical dwell (inventory cover, Little's-law capped) + the information delay of each buyer's "
        "planning decision (review period / 2 + mean age of the smoothed forecast; config `supply_graph.info_delay`, grade D, so its "
        "low end is zero). The physical dwell alone is the next column.\n", prior_table(pri), "",
        "### 3b. Edge 1 regression: channel-inventory partial adjustment (decision L6)\n",
        "d_t = a + c·t + rho·d_(t-1) + e_t on step 3's Logitech channel index (weeks vs target); mean lag T = -13 / ln(rho) weeks "
        "(continuous replenishment sampled at quarter ends; Koyck rho / (1 - rho) quarters shown). Andrews (1993) median-unbiased rho "
        "is the estimate; OLS with a block bootstrap and the no-trend fit are shown for comparison.\n", edge1_table(r1), "",
        f"GN: {gn_n} quarters of channel index (no anchor, grade D), below the {el['edge1']['min_obs']} needed: prior only.\n",
        "### 3c. Edge 2 regression: attribution-constrained, common cycle controlled (decision L7)\n",
        "y_t = alpha + s·m·x(t - tau) + beta·w(t - kappa) + e_t; y = Nordic consumer YoY, x = the brand's sell-in YoY, w = "
        f"{el['edge2']['control']} at its own peak kappa; s (step 2) and m (step 3) fixed: Logitech s = {s['logitech']['mid']:.3f} "
        f"({s['logitech']['low']:.3f}–{s['logitech']['high']:.3f}), m = {m['logitech']['mid']:.2f} ({m['logitech']['low']:.2f}–"
        f"{m['logitech']['high']:.2f}); GN s = {s['gn']['mid']:.3f}, m = {m['gn']['mid']:.2f}. Sample: {', '.join(el['edge2']['regimes'])} "
        "quarters on one fixed axis; tau on a 0.05-quarter grid.\n", edge2_table(r2), "",
        "### 3d. Prior + data -> posterior (decision L8)\n", combined_table(post), "",
        "### 3e. Totals along each route (decision L9)\n", totals_table(res["totals"]), "",
        "### 3f. What it says\n", bullet_edge1(post, r1), bullet_edge2(post, r2, s, m), bullet_totals(res["totals"]),
        bullet_regime(r1, r2, cfg, res["index"], post), "",
        "Outputs: `edge_lags.csv`, `edge_lags_total.csv`, `edge_lags_edge1_fits.csv`, `edge_lags_edge2_fits.csv`. Decisions L4–L10 (L10: signal basis); "
        "pitfalls P90, P91.\n"])


def _md_to_html(line: str) -> str:
    """One markdown bullet -> html: escape, then **bold** -> <b>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(line.removeprefix("- ")))


def _tbl(df: pd.DataFrame) -> str:
    return df.to_html(index=False, border=0, escape=True, na_rep="–")


def graph_mc_band(basis: str = GRAPH_MC[0], route: str = GRAPH_MC[1]) -> tuple[float, float] | None:
    """Step 5's Monte Carlo 90% band for one route (paired triangular draws of shares, lags and planners), or None."""
    f = step_outputs("step5_supply_graph") / "graph_signal_lag_mc.csv"
    if not f.exists():
        return None
    m = pd.read_csv(f).set_index(["basis", "route"])
    return (float(m.loc[(basis, route), "p5"]), float(m.loc[(basis, route), "p95"])) if (basis, route) in m.index else None


def _range_text(a) -> str:
    """The Amazon route's 90% range, each labelled for what it is."""
    indep = f"{a.sim_p5_weeks:.0f}–{a.sim_p95_weeks:.0f} if each edge sits anywhere in its prior independently"
    band = graph_mc_band()
    return f"90% {band[0]:.0f}–{band[1]:.0f} wk (graph Monte Carlo, step 5); {indep}" if band else f"90% range {indep} (wk)"


def dashboard_section(res: dict | None, cfg: dict) -> str:
    """The brief's lag question answered on the dashboard: chain, priors (reasoning first), both regressions, posterior,
    route totals and the plain-English reading - the same tables and computed sentences as step 4 section 3."""
    if not res:
        return ""
    post, tot, r1, r2 = res["combined"], res["totals"], res["edge1"], res["edge2"]
    a = tot.set_index("route").loc["Amazon -> Logitech -> Nordic"]
    reading = [bullet_edge1(post, r1), bullet_edge2(post, r2, res["shares"], res["multipliers"]), bullet_totals(tot),
               bullet_regime(r1, r2, cfg, res["index"], post)]
    return (
        "<h2>Lag: Amazon sell-out → Nordic revenue, edge by edge</h2>"
        f"<p class=note style='font-size:15px'><b>≈{a.total_weeks:.0f} weeks ({a.total_quarters:.1f} quarters)</b> order-signal lag "
        f"(physical dwell alone {a.physical_weeks:.0f} wk + the buyers' planning delay, G25) = edge 1 "
        f"{a.edge1_weeks:.0f} wk (Amazon cuts orders to Logitech) + edge 2 {a.edge2_weeks:.0f} wk (Logitech's build and chip orders reach "
        f"Nordic); {_range_text(a)}. Set by the chain's structure; the edge-by-edge regressions "
        "could not narrow it.</p>"
        f"<pre style='font-size:12px;background:#f6f8fa;padding:8px;border-radius:6px'>{html.escape(CHAIN)}</pre>"
        "<h3 style='font-size:14px'>1 · Reasoning first: prior per edge (from the supply graph, before any fit; L4, L5)</h3>"
        + _tbl(prior_df(res["priors"])) +
        "<h3 style='font-size:14px'>2 · Route totals (edges add; L9)</h3>" + _tbl(totals_df(tot)) +
        "<h3 style='font-size:14px'>3 · Prior + data → posterior (L8)</h3>" + _tbl(combined_df(post)) +
        "<h3 style='font-size:14px'>What it says</h3><ul>" + "".join(f"<li>{_md_to_html(b)}</li>" for b in reading) + "</ul>"
        "<details><summary><b>The regressions</b> — edge 1 channel reversion (L6), edge 2 attribution-constrained with a cycle control (L7)</summary>"
        "<p class=note>Edge 1: d_t = a + c·t + rho·d_(t−1) on step 3's Logitech channel index (weeks vs target); mean lag = −13 / ln(rho) weeks.</p>"
        + _tbl(edge1_df(r1)) +
        "<p class=note>Edge 2: Nordic consumer YoY = α + s·m·Logitech sell-in YoY(t − τ) + β·WSTS(t − κ); s (attribution, step 2) and "
        "m (slice multiplier, step 3) fixed, supply-constrained quarters excluded.</p>" + _tbl(edge2_df(r2)) +
        "<p class=src>Step 4 report section 3; outputs steps/step4_lag_structure/outputs/edge_lags*.csv; pitfalls P90, P91.</p></details>")
