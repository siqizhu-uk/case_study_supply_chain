"""Dashboard 'Charts' tab: the analysis as pictures, in the order of the brief's questions.

Every chart reads a step output (nothing is recomputed here) and carries a one-line takeaway that is computed from the
same data, so a re-run with other assumptions redraws both. Charts are inline SVG (matplotlib, text kept as text), written
to outputs/figures/story/*.svg and copied to deliverables/figures/ by mechanism_charts. Background shading is the
data-dated channel state (step 3b cycle_state.csv, P92); where a chart needs the hand-set config regimes it says so.
"""
from __future__ import annotations

import html
import io
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from core.config import OUTPUTS, ROOT, load_config  # noqa: E402

STORY = OUTPUTS / "figures" / "story"
S3 = ROOT / "steps" / "step3_inventory_mechanism" / "outputs"
S5 = ROOT / "steps" / "step5_supply_graph" / "outputs"
S4 = ROOT / "steps" / "step4_lag_structure" / "outputs"
S6 = ROOT / "steps" / "step6_backtest" / "outputs"
S7 = ROOT / "steps" / "step7_forecast" / "outputs"
ATTR = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"
ATTR_YEAR = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution.json"

INK, MUTED, GRID = "#1d1d1b", "#6b6b66", "#e6e5df"
C = {"guide": "#8a8a84", "chain": "#2f5d8a", "actual": "#1d1d1b", "up": "#2e8b57", "down": "#c0392b", "band": "#9fb8d3",
     "nordic": "#7b3fa0", "logi": "#2f5d8a", "dist": "#d99a00", "sellout": "#2e8b57", "gn": "#b5651d"}
STATE = {"shortage": "#f3e7c9", "building": "#f6d6d3", "drawdown": "#e3ecf5", "lean": "#eef3ea"}   # data-dated state; 'normal' unshaded
CONFIG_REGIME = "hand-set config regime (P92: data-dated state differs)"
CHAIN_TERM = "supply_chain_term (step 7c)"                              # key in forecast_details.json signal_adjustments
MIN_TERM = 0.05                                                         # smallest forecast term drawn as its own bar (m)
TITLE_PAD = 14                                                          # room for the state labels above the axes
SIGNAL_ALL, SIGNAL_AMAZON = "all routes (flow-weighted)", "Amazon direct"   # rows of step 5 graph_signal_lag_mc.csv (G25)

plt.rcParams.update({"svg.fonttype": "none", "font.family": "sans-serif", "font.size": 9, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "legend.frameon": False, "legend.fontsize": 8,
                     "svg.hashsalt": "case_study"})              # stable element ids: an unchanged chart gives an unchanged file


# ------------------------------------------------------------------ helpers
def _svg(fig, name: str) -> str:
    STORY.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", metadata={"Date": None})   # no timestamp: re-runs do not churn the file
    plt.close(fig)
    svg = buf.getvalue()
    (STORY / f"{name}.svg").write_text(svg)
    return svg[svg.find("<svg"):]


def _q(s) -> pd.PeriodIndex:
    return pd.PeriodIndex(pd.Index(s).astype(str), freq="Q")


def _x(idx: pd.PeriodIndex) -> np.ndarray:
    return idx.year + (idx.quarter - 1) / 4


def cycle_state() -> pd.Series:
    """Channel state per quarter, dated from the data (step 3b: Microchip distributor days, point in time; P92)."""
    c = pd.read_csv(S3 / "cycle_state.csv").dropna(subset=["state_nordic"])
    return pd.Series(c["state_nordic"].values, index=_q(c["quarter"]))


def _shade_states(ax, state: pd.Series, label: bool = True) -> None:
    """Background bands for the data-dated channel state (not the hand-set config regimes), labelled once per run."""
    r = state.dropna()
    x = _x(r.index)
    start = 0
    for i in range(1, len(r) + 1):
        if i == len(r) or r.iloc[i] != r.iloc[start]:
            col = STATE.get(r.iloc[start])
            if col:
                ax.axvspan(x[start] - 0.125, x[i - 1] + 0.125, color=col, zorder=0, lw=0)
            if col and label:
                ax.text((x[start] + x[i - 1]) / 2, 1.0, r.iloc[start], transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                        fontsize=7.5, color=MUTED)
            start = i


def _card(title: str, takeaway: str, svg: str, source: str) -> str:
    return (f"<div class=chart><h3>{html.escape(title)}</h3><p class=take>{html.escape(takeaway)}</p>{svg}"
            f"<p class=src>Source: {html.escape(source)}</p></div>")


# ------------------------------------------------------------------ 1. how each forecast is built
def forecast_bridges() -> tuple[str, str]:
    d = json.loads((OUTPUTS / "forecast_details.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), gridspec_kw={"width_ratios": [1.2, 1.0, 1.1]})
    takes = []
    for ax, key, title, unit in ((axes[0], "nordic", "Nordic Q3 2026", "USDm"), (axes[1], "logitech", "Logitech Q2 FY27", "USDm")):
        f = d[key]
        mid = f["guide_mid"]
        steps = [("guide\nmidpoint", mid, "base"), ("expected\nguide error", mid * f["hist_beat_pct"] / 100, "delta")]
        for k, v in f["signal_adjustments"].items():
            if abs(v) >= MIN_TERM:
                steps.append((SHORT.get(k, k.replace("_", " ")[:14]), v, "delta"))
        _waterfall(ax, steps, f["point"], (f["low"], f["high"]), f.get("guide"), unit)
        ax.set_title(title, fontsize=10, loc="left", color=INK)
        takes.append(f"{title}: {f['point']:,.0f} vs guide mid {mid:,.0f}")
    g = d["gn"]
    b, oa, an = g["base_q3_2025"], g["organic_assumptions"], g.get("guidance_anchor")
    if an:                                    # guide-error model: organic growth = H2 implied by the FY guide + GN's habit
        org = b["total"] * an["h2_organic_pct"] / 100
        steps = [("Q3 2025\nbase", b["total"], "base"), (f"H2 organic\n{an['h2_organic_pct']:+.2f}%", org, "delta")]
    else:                                     # division assumptions (config switch)
        org_e, org_g = (b[k] * oa[k]["mid"] / 100 for k in ("enterprise", "gaming"))
        steps = [("Q3 2025\nbase", b["total"], "base"), (f"Enterprise\n{oa['enterprise']['mid']:+.0f}% org.", org_e, "delta"),
                 (f"Gaming\n{oa['gaming']['mid']:+.0f}% org.", org_g, "delta")]
    fx = g["point"] - sum(v for _, v, _ in steps)
    steps.append((f"FX\n{oa['fx_pts']:+.1f} pts", fx, "delta"))
    _waterfall(axes[2], steps, g["point"], (g["low"], g["high"]), None, "DKKm")
    axes[2].set_title("GN continuing ops Q3 2026", fontsize=10, loc="left", color=INK)
    fig.tight_layout()
    take = ("Each bar is one named term; the last bar is the forecast with its 80% range (whisker) and the company guide (grey band). "
            + "; ".join(takes) + (f"; GN {g['point']:,.0f} DKKm: FY guide + GN's own August-guide habit -> H2 organic {an['h2_organic_pct']:+.2f}%, then FX." if an
               else f"; GN {g['point']:,.0f} DKKm, bottom-up from division organic growth."))
    return take, _svg(fig, "forecast_bridges")


SHORT = {"capacity_worry_pull_in": "pull-ins", "supply_chain_term (step 7c)": "supply chain\n(step 7c)",
         "logitech_supplier_incident (graph)": "supplier\nincident\n(graph)", "nrf54_ramp_mix": "nRF54 mix"}


def _waterfall(ax, steps, point, rng, guide, unit) -> None:
    run, xs = 0.0, []
    for i, (lab, v, kind) in enumerate(steps):
        if kind == "base":
            ax.bar(i, v, color=C["guide"], width=0.6)
            run = v
        else:
            ax.bar(i, v, bottom=run, color=C["up"] if v >= 0 else C["down"], width=0.6)
            ax.text(i, run + max(v, 0) + (abs(steps[0][1]) * 0.004), f"{v:+.1f}", ha="center", va="bottom", fontsize=7.5, color=INK)
            run += v
        xs.append(lab)
    n = len(steps)
    ax.bar(n, point, color=C["chain"], width=0.6)
    ax.errorbar(n, point, yerr=[[point - rng[0]], [rng[1] - point]], color=INK, capsize=4, lw=1)
    ax.text(n + 0.35, point, f"{point:,.0f}", va="center", fontsize=8.5, color=INK, fontweight="bold")
    if guide:
        ax.axhspan(guide[0], guide[1], color=C["guide"], alpha=0.15, lw=0)
        ax.text(-0.45, guide[1], "guide", fontsize=7, color=MUTED, va="bottom")
    xs.append("forecast")
    ax.set_xticks(range(n + 1), xs, fontsize=7)
    lo = min(steps[0][1], rng[0], guide[0] if guide else rng[0])
    hi = max(run, rng[1], guide[1] if guide else rng[1])
    pad = (hi - lo) * 0.6 + 1
    ax.set_ylim(lo - pad, hi + pad * 0.6)
    ax.set_ylabel(unit)
    ax.grid(axis="x", visible=False)


def _wrap(t: str, n: int) -> str:
    words, lines, cur = t.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return "\n".join(lines + [cur])


# ------------------------------------------------------------------ 3. the chain over time (bullwhip)
def chain_over_time(p: pd.DataFrame) -> tuple[str, str]:
    p = p.loc["2021Q3":"2026Q2"]          # 2021H1 is a COVID base effect (+117% YoY) that would flatten everything else
    x = _x(p.index)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(11.5, 5.4), sharex=True, gridspec_kw={"height_ratios": [1, 1.25]})
    st = cycle_state().reindex(p.index)
    for ax in (a1, a2):
        _shade_states(ax, st)
        ax.axhline(0, color=MUTED, lw=0.8)
    a1.plot(x, p["sellout_proxy_yoy"], color=C["sellout"], lw=2, label="end demand proxy (Logitech sell-through)")
    a1.plot(x, p["logi_sales_yoy"], color=C["logi"], lw=1.6, label="Logitech sell-in")
    a1.set_ylabel("YoY %")
    a1.set_title("Downstream: end demand, distributors, Logitech", fontsize=9.5, loc="left", pad=TITLE_PAD)
    a1.legend(ncol=4, loc="lower left", fontsize=7.5)
    a2.plot(x, p["logi_sales_yoy"], color=C["logi"], lw=1.2, alpha=0.6, label="Logitech sell-in (same line as above)")
    a2.plot(x, p["nordic_consumer_yoy"], color=C["nordic"], lw=2.2, label="Nordic Consumer")
    a2.plot(x, p["nordic_rev_yoy"], color=C["nordic"], lw=1.3, ls="--", label="Nordic total")
    a2.set_ylabel("YoY %")
    a2.set_title("Upstream: Nordic swings several times harder than the peripherals it feeds", fontsize=9.5, loc="left", pad=TITLE_PAD)
    a2.legend(ncol=3, loc="upper right", fontsize=7.5)
    a2.set_xticks(range(2022, 2027))
    fig.tight_layout()
    d = p[["logi_sales_yoy", "nordic_consumer_yoy"]].dropna()
    take = (f"Bullwhip in one picture: since mid-2021 Logitech sell-in moved between {d['logi_sales_yoy'].min():.0f}% and {d['logi_sales_yoy'].max():.0f}% YoY, "
            f"Nordic Consumer between {d['nordic_consumer_yoy'].min():.0f}% and {d['nordic_consumer_yoy'].max():.0f}%; Nordic turns after Logitech and overshoots both ways.")
    return take, _svg(fig, "chain_over_time")


def bullwhip_chart() -> tuple[str, str]:
    """Amplification by link over the whole sample (the hand-set destock / normal windows are not shown: P92, P04)."""
    b = pd.read_csv(S3 / "bullwhip_links.csv")
    a = b[b["window"] == "all"].drop_duplicates("label").set_index("label")
    fig, ax = plt.subplots(figsize=(11.5, 2.6))
    y = np.arange(len(a))[::-1]
    ax.barh(y, a["sd_ratio"], height=0.5, color=C["chain"])
    ax.errorbar(a["sd_ratio"], y, xerr=[a["sd_ratio"] - a["sd_ratio_p5"], a["sd_ratio_p95"] - a["sd_ratio"]], fmt="none",
                ecolor=INK, lw=0.8, capsize=3)
    for yi, (lab, r) in zip(y, a.iterrows()):
        ax.text(r["sd_ratio_p95"] * 1.05, yi, f"×{r['sd_ratio']:.2f} (n {int(r['n'])})", va="center", fontsize=8)
    ax.axvline(1, color=INK, lw=1)
    ax.text(1.03, len(a) - 0.55, "1 = no amplification", fontsize=7.5, color=MUTED)
    ax.set_yticks(y, a.index, fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("sd of YoY, upstream / downstream, whole sample (log scale; whisker = bootstrap 5–95%)")
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    r = b[b["window"] == "all"].set_index("link")["sd_ratio"]
    purchases = r.loc["A'"]
    take = (f"Logitech sell-in vs its own sell-through ×{r.loc['A']:.2f} (close to 1 by construction: the proxy is sell-in + the "
            f"disclosed gap); purchases ×{purchases:.2f}; Nordic Consumer ×{r.loc['B']:.1f} vs sell-in: the swing is created at the "
            "component tier. Ratios by hand-set window are left out: the windows are not the data-dated states (P92) and calm-window "
            "ratios are small-denominator artefacts (P04).")
    return take, _svg(fig, "bullwhip")


# ------------------------------------------------------------------ 4. lag: reasoned kernel vs data
def lag_chart() -> tuple[str, str]:
    k = pd.read_csv(S5 / "graph_kernel.csv")
    xc = pd.read_csv(S4 / "xcorr_all.csv")
    mc = pd.read_csv(S5 / "graph_mean_lag_mc.csv").iloc[0]                       # goods (physical) lag: the kernel's basis
    sig = pd.read_csv(S5 / "graph_signal_lag_mc.csv").query("basis == 'signal'").set_index("route")   # order signal (G25)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 3.1))
    lq = k["lag_quarters"]
    a1.bar(lq, k["mid"], color=C["chain"], width=0.55, label="graph kernel (mid)")
    a1.plot(lq, k["low"], "o", color=C["up"], ms=4, label="short lags (low)")
    a1.plot(lq, k["high"], "o", color=C["down"], ms=4, label="long lags (high)")
    a1.set_xlabel("quarters from end demand to Nordic revenue")
    a1.set_ylabel("weight")
    a1.set_title(f"Reasoned first: supply graph, goods lag {mc['p50']:.0f} weeks (90%: {mc['p5']:.0f}–{mc['p95']:.0f}), the kernel's basis",
                 fontsize=9.5, loc="left")
    a1.legend(fontsize=7.5)
    a1.grid(axis="x", visible=False)
    regimes = [r for r in ("all", "normal", "destock") if (xc["regime"] == r).any()]
    for reg, col in zip(regimes, (MUTED, C["chain"], C["down"])):
        g = xc[xc["regime"] == reg]
        a2.plot(g["lag_q"], g["corr"], "o-", color=col, lw=1.5, ms=4, label=f"{reg} (n ≈ {int(g['n'].median())})")
    a2.axhline(0, color=MUTED, lw=0.8)
    a2.set_xlabel("lag (quarters): Logitech radio categories lead Nordic Consumer")
    a2.set_xticks(range(int(xc["lag_q"].max()) + 1))
    a2.set_ylabel("correlation of YoY")
    a2.set_title("Then the data: cross-correlation by lag", fontsize=9.5, loc="left")
    a2.legend(fontsize=7.5, title=CONFIG_REGIME if regimes != ["all"] else None, title_fontsize=7)
    fig.tight_layout()
    ca = xc[xc["regime"] == "all"].set_index("lag_q")["corr"]
    kmax = int(k.loc[k["mid"].idxmax(), "lag_quarters"])
    kmean = float((k["mid"] * k["lag_quarters"]).sum() / k["mid"].sum())
    s_all, s_amz = sig.loc[SIGNAL_ALL], sig.loc[SIGNAL_AMAZON]
    corrs = ", ".join(f"lag {int(i)} ρ {v:.2f}" for i, v in ca.items() if i >= 1)
    take = (f"The graph puts most weight at lag {kmax} (kernel mean {kmean:.1f} quarters, built on the goods lag of {mc['p50']:.0f} weeks); "
            f"the order signal, which adds the planners' delays, arrives later: {s_all['p50']:.0f} weeks over all routes "
            f"(90% {s_all['p5']:.0f}–{s_all['p95']:.0f}), {s_amz['p50']:.0f} on the Amazon route (G25). The data: {corrs} "
            f"(n ≈ {int(xc['n'].median())}). A broad plateau, not a sharp peak: the correlation also carries the common industry cycle, "
            "so it cannot pick the lag, and the structure sets it.")
    return take, _svg(fig, "lag")


# ------------------------------------------------------------------ 5. where the inventory sits
def inventory_chart() -> tuple[str, str]:
    f = pd.read_csv(S3 / "factors_quarterly.csv")
    f.index = _q(f["quarter"])
    f = f.loc["2021Q1":"2026Q2"]
    st = cycle_state()
    x = _x(f.index)
    ci = pd.read_csv(S3 / "channel_index_logitech.csv")
    ci.index = _q(ci["quarter"])
    ci = ci.loc["2021Q1":"2026Q2"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 3.4), gridspec_kw={"width_ratios": [1.6, 1]})
    _shade_states(a1, st.reindex(f.index))
    for col, lab, c, ls in (("nordic_dio", "Nordic own DIO", C["nordic"], "-"), ("logi_dio", "Logitech own DIO", C["logi"], "-"),
                            ("it_dist_dio_avg", "IT distributors (Ingram, TD Synnex)", C["dist"], "--"),
                            ("comp_dist_dio_avg", "component distributors (Arrow, Avnet)", C["gn"], "--"),
                            ("mchp_disti_days", "Microchip: days at its distributors", C["down"], ":")):
        if col in f:
            a1.plot(x, f[col], color=c, ls=ls, lw=1.6, label=lab)
    a1.set_ylabel("days of inventory")
    a1.set_title("Balance-sheet inventory by tier (company filings)", fontsize=9.5, loc="left", pad=TITLE_PAD)
    a1.legend(fontsize=7, ncol=2, loc="upper left")
    xw = _x(ci.index)
    _shade_states(a2, st.reindex(ci.index), label=False)          # same states as the left panel; no room for labels
    a2.bar(xw, ci["excess_weeks"], width=0.18, color=[C["up"] if v >= 0 else C["down"] for v in ci["excess_weeks"].fillna(0)])
    a2.axhline(0, color=INK, lw=0.8)
    a2.set_ylabel("weeks vs target")
    a2.set_title("Logitech's channel (not its balance sheet): weeks above/below target", fontsize=9.5, loc="left", pad=TITLE_PAD)
    fig.tight_layout()
    last = f.dropna(subset=["nordic_dio"]).iloc[-1]
    w_all, w_anchor, state = _logitech_channel(ci)
    take = (f"Nordic's own inventory ({last['nordic_dio']:.0f} days) is not what moves its revenue; distributor and ODM stock is, but ODMs "
            "disclose nothing and distributors only all-vendor totals (Arrow / Avnet for chips, Ingram / TD Synnex for finished goods). "
            f"Logitech's channel: {w_all:+.1f} wk vs target ({w_anchor:+.1f} on the latest anchor; step 3: {state}).")
    return take, _svg(fig, "inventory")


def _logitech_channel(ci: pd.DataFrame) -> tuple[float, float, str]:
    """Logitech channel weeks vs target now: on all anchors, on the latest 'at target' anchor only, and step 3's state word.
    Weeks from the stored dollars (excess / weekly sell-in, step 3's own formula): the stored weeks are rounded to 0.01."""
    from channel_index import WEEKS_Q                                      # steps/step3_inventory_mechanism/src
    fit = json.loads((S3 / "step3_summary.json").read_text())["logitech_anchor_fit"]
    now = ci.dropna(subset=["excess_usd", "sell_in"])
    w_all = float(now["excess_usd"].iloc[-1] / (now["sell_in"].iloc[-1] / WEEKS_Q))
    w_anchor = w_all - float(fit["anchor_weeks"][fit["anchors_used"][-1]])
    call = pd.read_csv(S3 / "channel_call.csv").set_index("company")
    return w_all, w_anchor, str(call.loc["logitech", "state"]).split(":")[0]


# ------------------------------------------------------------------ 6. attribution
def attribution_chart(p: pd.DataFrame) -> tuple[str, str]:
    a = pd.read_csv(ATTR)
    a.index = _q(a["quarter"])
    x = _x(a.index)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 3.2))
    a1.fill_between(x, a["share_total_indirect_p10"], a["share_total_indirect_p90"], color=C["band"], alpha=0.5, lw=0, label="p10–p90")
    a1.plot(x, a["share_total_indirect_p50"], color=C["chain"], lw=2, label="p50 (Logitech buys via ODMs)")
    a1.plot(x, a["share_total_direct_p50"], color=MUTED, lw=1.2, ls="--", label="p50 if invoiced directly (IFRS cap binds)")
    a1.set_ylabel("% of Nordic revenue")
    a1.set_ylim(0, None)
    a1.set_title("Logitech + GN as a share of Nordic (step 2, five evidence legs)", fontsize=9.5, loc="left")
    a1.legend(fontsize=7.5, loc="lower left")
    rev = p["nordic_rev"].reindex(a.index)
    sl = rev * a["share_total_indirect_p50"] / 100
    a2.bar(x, sl, width=0.18, color=C["chain"], label="Logitech + GN slice (p50)")
    a2.bar(x, rev - sl, bottom=sl, width=0.18, color="#d8d6ce", label="rest of Nordic")
    a2.set_ylabel("USDm per quarter")
    a2.set_title("What the chain can speak for", fontsize=9.5, loc="left")
    a2.legend(fontsize=7.5, loc="upper left")
    fig.tight_layout()
    last = a.dropna(subset=["share_total_indirect_p50"]).iloc[-1]
    yr = json.loads(ATTR_YEAR.read_text())
    ys, qs = yr["combined_pct_of_nordic_total"], yr["logitech_ttm_sales_usdm"]["quarters"]     # the trailing four quarters
    t = pd.read_csv(S7 / "chain_weight_tests.csv").set_index(["horizon", "model"])
    beta = float(t.loc[(2, "CH"), "beta"])
    take = (f"About {last['share_total_indirect_p50']:.0f}% of Nordic in {last.name} ({last['share_total_indirect_p10']:.0f}–"
            f"{last['share_total_indirect_p90']:.0f}%; estimate over {qs[0]}–{qs[-1]} {ys['p50']:.0f}%, {ys['p10']:.0f}–{ys['p90']:.0f}%) runs "
            f"through Logitech and GN. The chain's direct evidence covers only that slice, but one quarter out Nordic moves ≈{beta:.1f}× what the slice "
            "implies (reasoned chain's back-test slope): its other consumer customers ride the same cycle.")
    return take, _svg(fig, "attribution")


# ------------------------------------------------------------------ 7. structural breaks
def breaks_chart() -> tuple[str, str]:
    """Every tested break (step 5c): the Nordic-on-Logitech link with its break dates, and every test's p-value."""
    from mechanism_charts import _break_tests, _link_panel, _p_panel       # lazy: mechanism_charts imports this module's style
    alpha = float(load_config()["relationship_breaks"]["alpha"])
    tests = _break_tests()
    fig = plt.figure(figsize=(9.5, 7.6), layout="constrained")
    top, bottom = fig.subfigures(2, 1, height_ratios=[1.2, 1], hspace=0.04)
    _link_panel(top.subplots(), tests)
    _p_panel(bottom.subplots(), tests)
    rb = pd.read_csv(S5 / "relationship_breaks.csv").dropna(subset=["p"])
    hand = rb[rb["dated_by"].str.contains("hand-set", regex=False)]
    hits = tests[tests["p"] < alpha]
    data_dated = len(hits) > 0 and hits["label"].str.contains("data-dated", regex=False).all()
    take = (f"{len(hits)} of {len(tests)} tested breaks reject stability at {alpha:.0%}" + (f": {'; '.join(hits['label'])}" if len(hits) else "")
            + f". The hand-set regime edges do not ({', '.join(f'{b} p {v:.2f}' for b, v in zip(hand['break'], hand['p']))})"
            + (": the break sits at a turn of the data-dated channel state, not at the config regime dates (P92)." if data_dated else "."))
    return take, _svg(fig, "relationship_breaks")


# ------------------------------------------------------------------ 8. back-test
def _h1_walkforward() -> pd.DataFrame:
    """Step 7c's h=1 walk-forward plus the rule used (step 7e): guide mid x (1 + expected guide error, known at each date)."""
    w1 = pd.read_csv(S7 / "chain_nordic_walkforward_h1.csv")
    w1.index = _q(w1["quarter"])
    g = pd.read_csv(S7 / "guide_error_walkforward_nordic.csv")
    g.index = _q(g["quarter"])
    return w1.assign(used_total=w1["guide_total"] * (1 + g["model"].reindex(w1.index) / 100))


def _rmse(w: pd.DataFrame, col: str) -> float:
    return float(np.sqrt(((w[col] - w["actual_total"]) ** 2).mean()))


def backtest_chart() -> tuple[str, str]:
    w1 = _h1_walkforward()
    w2 = pd.read_csv(S6 / "walkforward_h2.csv")
    w2.index = _q(w2["quarter"])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 3.5))
    x1 = _x(w1.index)
    a1.plot(x1, w1["actual_total"], color=C["actual"], lw=2.2, marker="o", ms=3.5, label="actual")
    a1.plot(x1, w1["guide_total"], color=C["guide"], lw=1.4, label="guide midpoint")
    a1.plot(x1, w1["used_total"], color=C["up"], lw=1.8, label="guide × own record by channel state (F20/F30, used)")
    a1.plot(x1, w1["GB_total"], color=C["dist"], lw=1.2, ls="--", label="guide × trailing beat (GB, benchmark)")
    a1.plot(x1, w1["CH_total"], color=C["chain"], lw=1.4, ls=":", label="chain as reasoned (CH)")
    a1.plot(x1, w1["GR_total"], color=C["nordic"], lw=1.2, ls="-.", label="graph, fitted slope (GR)")
    a1.set_ylabel("Nordic revenue, USDm")
    a1.set_title("Guided quarter (h = 1): the guide wins", fontsize=9.5, loc="left")
    a1.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    x2 = _x(w2.index)
    a2.plot(x2, w2["actual_total"], color=C["actual"], lw=2.2, marker="o", ms=3.5, label="actual")
    a2.plot(x2, w2["G_total"], color=C["guide"], lw=1.4, label="last guide × seasonal step")
    a2.plot(x2, w2["GR_total"], color=C["nordic"], lw=1.2, ls="-.", label="graph, sell-through (GR, challenger)")
    if "GRi_total" in w2:
        a2.plot(x2, w2["GRi_total"], color=C["chain"], lw=1.8, label="graph, Logitech sell-in (GRi, used)")
    a2.set_title("One quarter further (h = 2): the chain helps", fontsize=9.5, loc="left")
    a2.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=2)
    for ax in (a1, a2):
        ax.set_xticks(range(2023, 2027))
    fig.tight_layout()
    t = pd.read_csv(S7 / "chain_weight_tests.csv").set_index(["horizon", "model"])
    d1 = w1.dropna(subset=["used_total", "GB_total", "CH_total"])
    h1 = (f"Walk-forward RMSE, information of each forecast date. h=1 ({len(d1)} quarters): the rule used errs {_rmse(d1, 'used_total'):.1f}m "
          f"(F30 set after seeing these quarters), the GB benchmark {_rmse(d1, 'GB_total'):.1f}m, the reasoned chain "
          f"{_rmse(d1, 'CH_total'):.1f}m (weight {t.loc[(1, 'CH'), 'weight']:.0f}). ")
    return h1 + _h2_takeaway(w2), _svg(fig, "backtest")


def _h2_takeaway(w2: pd.DataFrame) -> str:
    """h=2 on the quarters every graph model covers: GRi (post hoc), GR vs the plain lag-2 model L3, the guide extrapolation."""
    pm = "GRi" if "GRi_total" in w2 else "GR"
    d2 = w2.dropna(subset=[f"{pm}_total", "GR_total", "L3_total"])
    gr, l3 = f"{_rmse(d2, 'GR_total'):.0f}", f"{_rmse(d2, 'L3_total'):.0f}"
    same = gr == l3                                                        # equal at the precision shown
    head = f"h=2 ({len(d2)} quarters): " + (f"GRi {_rmse(d2, 'GRi_total'):.0f}m (chosen after seeing these quarters, F26), " if pm == "GRi" else "")
    return (head + f"GR {gr}m {'= plain lag-2 L3' if same else 'vs plain lag-2 L3'} {l3}m, vs {_rmse(d2, 'G_total'):.0f}m for the guide "
            "extrapolation" + (": the gain is timing, not the graph (G5, P61)." if same else "."))


# ------------------------------------------------------------------ tab
CSS = """<style>.chart{margin:0 0 28px}.chart h3{margin:18px 0 2px;font-size:15px}.chart .take{margin:2px 0 8px;color:#333;
max-width:980px}.chart svg{max-width:100%;height:auto}.chapter{margin:30px 0 4px;padding-top:8px;border-top:2px solid #2f5d8a;
font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#2f5d8a}</style>"""


def _bridge_source() -> str:
    """Source line of the forecast bars; says the step 7c chain term is 0 only when it is 0 in every guided forecast."""
    d = json.loads((OUTPUTS / "forecast_details.json").read_text())
    chain = [d[k]["signal_adjustments"].get(CHAIN_TERM, 0.0) for k in ("nordic", "logitech")]
    return ("outputs/forecast_details.json (step 7e guide-error model, 5d incident; 7c chain term"
            + (" = 0)" if all(abs(v) < MIN_TERM for v in chain) else ")"))


SHADE = "; shading: step 3b cycle_state.csv (data-dated channel state)"


def charts_tab(p: pd.DataFrame) -> str:
    """HTML for the dashboard's Charts tab (also writes outputs/figures/story/*.svg)."""
    parts = [CSS, "<h2>The analysis in charts</h2><p class=note>The forecasts first, then the brief's questions in order: lag, "
                  "mechanism, attribution, structural breaks, limitations. Every takeaway line is computed from the same data as its "
                  "chart; SVGs in deliverables/figures/.</p>"]
    specs = [
        ("Forecasts", "How each forecast is built", forecast_bridges, _bridge_source),
        ("Lag structure", "Reasoned lag vs the data", lag_chart,
         "step 5 graph_kernel.csv, graph_mean_lag_mc.csv (goods lag), graph_signal_lag_mc.csv (order signal, G25); step 4 xcorr_all.csv"),
        ("Mechanism", "The chain over time", lambda: chain_over_time(p), "outputs/tier_panel.csv" + SHADE),
        ("Mechanism", "Where the swing is created", bullwhip_chart, "steps/step3_inventory_mechanism/outputs/bullwhip_links.csv"),
        ("Mechanism", "Where the inventory sits", inventory_chart,
         "step 3 factors_quarterly.csv, channel_index_logitech.csv, channel_call.csv, step3_summary.json" + SHADE),
        ("Attribution", "How much of Nordic the chain covers", lambda: attribution_chart(p),
         "steps/step2_attribution/outputs/attribution_path.csv, attribution.json"),
        ("Structural breaks", "Where the chain link breaks, and where it does not", breaks_chart,
         "step 5c relationship_breaks.csv, event_breaks.csv" + SHADE),
        ("Limitations", "Does it work? The back-test", backtest_chart,
         "step 6 walkforward_h2.csv; step 7c chain_nordic_walkforward_h1.csv; step 7e guide_error_walkforward_nordic.csv"),
    ]
    last = None
    for chapter, title, fn, src in specs:
        if chapter != last:
            parts.append(f"<div class=chapter>{chapter}</div>")
            last = chapter
        try:
            take, svg = fn()
            parts.append(_card(title, take, svg, src() if callable(src) else src))
        except (FileNotFoundError, KeyError, ValueError, IndexError) as e:     # a missing step output must not break the dashboard
            parts.append(f"<div class=chart><h3>{html.escape(title)}</h3><p class=src>not drawn: {html.escape(type(e).__name__)}: {html.escape(str(e))}</p></div>")
    return "".join(parts)
