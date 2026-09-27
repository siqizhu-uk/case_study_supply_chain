"""The figures of the analysis write-up (deliverables/my_analysis.md / .html, the dashboard's Analysis tab), written to
deliverables/figures/ on every run: the explanatory charts drawn here from the step outputs (channel recursion, channel
weeks, Nordic channel state, revenue build-ups, amplification by link, relationship breaks) and the story charts copied
from the steps (STORY). Nothing is recomputed here."""
from __future__ import annotations

import io
import json
import shutil

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import charts  # noqa: F401  shared style (rcParams, palette)
from charts import C, INK, MUTED
from core.config import OUTPUTS, ROOT

S3 = ROOT / "steps" / "step3_inventory_mechanism" / "outputs"
S7 = ROOT / "steps" / "step7_forecast" / "outputs"
FIG = ROOT / "deliverables" / "figures"


def _save(fig, name: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    (FIG / f"{name}.svg").write_text(buf.getvalue())


def _channel() -> pd.DataFrame:
    x = pd.read_csv(S3 / "channel_index_logitech.csv")
    return x.dropna(subset=["fill_exact", "excess_weeks"]).reset_index(drop=True)


def channel_fill() -> None:
    x = _channel()
    fig, ax = plt.subplots(figsize=(9.5, 3.6))
    i = np.arange(len(x))
    ax.bar(i - 0.2, x["fill_naive"], 0.38, color=C["band"], label="gap only: −gap × sell-in a year ago")
    ax.bar(i + 0.2, x["fill_exact"], 0.38, color=C["chain"], label="recursion: F(t−4)(1 + sell-through YoY) − gap × sell-in(t−4)")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(i, [q[2:] for q in x["quarter"]], fontsize=8)
    ax.set_ylabel("USD m")
    ax.set_title("Channel inventory added each quarter (USD m): gap-only reading vs recursion", loc="left", fontsize=10)
    k = x.index[x["quarter"] == "2024Q1"]
    if len(k):
        k = int(k[0])
        r = x.loc[k]
        top = float(max(x["fill_naive"].max(), x["fill_exact"].max()))
        ax.set_ylim(top=top + 45)
        ax.annotate(f"2024Q1: gap only {r['fill_naive']:+.1f}, recursion {r['fill_exact']:+.1f}\n(last year's destock lowered the base)",
                    xy=(k - 0.2, r["fill_naive"]), xytext=(k + 1.0, top + 18), fontsize=8, color=INK, va="center",
                    arrowprops={"arrowstyle": "-", "color": MUTED, "lw": 0.8})
    ax.legend(loc="lower left", fontsize=8)
    _save(fig, "channel_fill_gap_vs_recursion")


def channel_weeks() -> None:
    x = _channel()
    fig, ax = plt.subplots(figsize=(9.5, 3.2))
    i = np.arange(len(x))
    ax.axhspan(-0.7, 0.7, color="#eeeeea", zorder=0, label="target ± 0.7 wk (index error)")
    ax.plot(i, x["excess_weeks"], color=C["chain"], lw=2, marker="o", ms=3.5)
    ax.axhline(0, color=MUTED, lw=0.8)
    hi_, lo_ = float(x["excess_weeks"].max()), float(x["excess_weeks"].min())
    ax.set_ylim(lo_ - 0.6, hi_ + 1.0)
    first, last = x.loc[0], x.loc[len(x) - 1]
    ax.annotate(f"{first['excess_weeks']:+.1f} wk: channel above target", xy=(0, first["excess_weeks"]), xytext=(0.2, first["excess_weeks"] + 0.45),
                ha="left", va="center", fontsize=8, color=INK)
    ax.annotate(f"{last['excess_weeks']:+.1f} wk: lean now", xy=(len(x) - 1, last["excess_weeks"]), xytext=(len(x) - 1.3, last["excess_weeks"]),
                ha="right", va="center", fontsize=8, color=INK)
    ax.set_xticks(i, [q[2:] for q in x["quarter"]], fontsize=8)
    ax.set_ylabel("weeks vs target")
    ax.set_title("Logitech channel inventory vs target (weeks): cumulated F, level pinned by 'at target' quarters", loc="left", fontsize=10)
    ax.legend(loc="upper right", fontsize=8)
    _save(fig, "logitech_channel_weeks")


def gn_channel_weeks() -> None:
    """GN Enterprise channel from its disclosed sell-out vs sell-in gap: same recursion as Logitech, but GN never says the
    channel is 'at target', so the level is relative to the first quarter (direction only, grade D)."""
    x = pd.read_csv(S3 / "channel_index_gn.csv").dropna(subset=["excess_weeks"]).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.5, 3.0))
    i = np.arange(len(x))
    ax.plot(i, x["excess_weeks"], color=C["gn"], lw=2, marker="o", ms=3.5)
    ax.axhline(0, color=MUTED, lw=0.8)
    last = x.loc[len(x) - 1]
    ax.annotate(f"{last['excess_weeks']:+.1f} wk since {x.loc[0, 'quarter']} (DKK {last['excess_usd']:,.0f}m)", xy=(len(x) - 1, last["excess_weeks"]),
                xytext=(len(x) - 1.3, last["excess_weeks"]), ha="right", va="center", fontsize=8, color=INK)
    ax.set_ylim(float(x["excess_weeks"].min()) - 0.7, 0.8)
    ax.set_xticks(i, [q[2:] for q in x["quarter"]], fontsize=8)
    ax.set_ylabel("weeks of Enterprise sell-in")
    ax.set_title("GN Enterprise channel inventory (weeks, relative to 2024Q3): no 'at target' anchor, so direction only",
                 loc="left", fontsize=10)
    _save(fig, "gn_channel_weeks")


WORDING = {-1.0: ("destocking", "#d98a78"), -0.5: ("destocking, tapering", "#f2c2b4"), 0.0: ("healthy", "#e4e7ea"),
           0.5: ("some restocking", "#bcdcb4"), 1.0: ("adding stock", "#86bd84")}


def _strip(ax, y: float, colors: list[str | None]) -> None:
    for k, c in enumerate(colors):
        if c:
            ax.add_patch(plt.Rectangle((k - 0.5, y - 0.38), 1, 0.76, facecolor=c, edgecolor="white", lw=1.2))


def nordic_channel() -> None:
    """Nordic's channel as two state strips (P128, D25): Nordic's own words about its distributors' stock in each report
    (a flow: destocking / healthy / adding) and the state step 3b reads from Microchip's distributor days with Nordic's
    supply-shortage split (D24). The proxy is a state signal only: its levels move out of phase with Nordic's channel."""
    q = pd.read_csv(S3 / "nordic_wording_vs_microchip.csv")
    sh = pd.read_csv(S3 / "nordic_wording_vs_microchip_shifts.csv").set_index("mchp_shift_q")["corr_level_vs_mchp_days"]
    fig, ax = plt.subplots(figsize=(9.5, 2.9))
    _strip(ax, 1, [WORDING.get(w, (None, None))[1] for w in q["nordic_wording"]])
    _strip(ax, 0, [STATE_SHADE.get(s_, "#f7f7f7") for s_ in q["state_nordic"]])
    ax.set_xlim(-0.6, len(q) - 0.4)
    ax.set_ylim(-0.6, 1.9)
    ax.set_yticks([0, 1], ["Microchip distributor-days\nstate (step 3b, D24)", "Nordic's own words about\nits distributors' stock"], fontsize=8)
    ax.set_xticks(range(len(q)), [x[2:] for x in q["quarter"]], fontsize=7.5)
    ax.grid(False)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    k_n = int(q.index[q["nordic_wording"] < 0][0])
    k_m = int(q.index[q["mchp_state"] == "building"][0])
    ax.text(k_n - 0.45, 1.5, f"▼ Nordic destocking from {q.loc[k_n, 'quarter']}", fontsize=7.5, color=INK)
    ax.text(k_m - 0.45, -0.55, f"▲ Microchip building from {q.loc[k_m, 'quarter']}", fontsize=7.5, color=INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in WORDING.values()] + \
              [plt.Rectangle((0, 0), 1, 1, color=c) for c in STATE_SHADE.values()] + \
              [plt.Rectangle((0, 0), 1, 1, facecolor="#ffffff", edgecolor=MUTED, lw=0.6)]
    labels = [f"Nordic: {t}" for t, _ in WORDING.values()] + [f"Microchip: {s_}" for s_ in STATE_SHADE] + ["Microchip: normal"]
    ax.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=5, fontsize=7, frameon=False)
    lo, hi = float(sh.loc[-3:4].min()), float(sh.loc[-3:4].max())
    ax.set_title(f"Nordic's channel: the turns agree within a quarter; the levels do not (correlation {lo:+.2f} to {hi:+.2f} at shifts −3..+4)",
                 loc="left", fontsize=10)
    _save(fig, "nordic_channel_state")


def _bridge(steps: list[tuple[str, float, bool]], band: tuple[float, float], guide: tuple[float, float] | None, title: str,
            unit: str, name: str, digits: int) -> None:
    fig, ax = plt.subplots(figsize=(9.5, 0.55 * len(steps) + 1.3))
    run, lo_all = 0.0, []
    for k, (label, v, total) in enumerate(steps):
        y = len(steps) - 1 - k
        if total:
            ax.plot([v, v], [y - 0.3, y + 0.3], color=C["chain"], lw=3)
            txt, left, run = f"{v:,.{digits}f}", v, v
        else:
            a, b = run, run + v
            ax.barh(y, b - a, left=a, height=0.45, color=C["up"] if v >= 0 else C["down"])
            txt, left, run = f"{v:+,.{digits}f}", max(a, b), b
        ax.text(left + (band[1] - band[0]) * 0.01, y, txt, va="center", fontsize=8, color=INK)
        lo_all.append(v if total else run)
    ax.set_yticks(range(len(steps)), [s[0] for s in reversed(steps)], fontsize=8.5)
    y_b = -1
    ax.plot(band, [y_b, y_b], color=C["band"], lw=6, solid_capstyle="round")
    ax.plot([steps[-1][1]], [y_b], "o", color=C["chain"])
    ax.text(band[0], y_b - 0.45, f"{band[0]:,.{digits}f}", ha="center", fontsize=7.5, color=MUTED)
    ax.text(band[1], y_b - 0.45, f"{band[1]:,.{digits}f}", ha="center", fontsize=7.5, color=MUTED)
    ax.set_yticks(list(range(len(steps))) + [y_b], [s[0] for s in reversed(steps)] + ["≈80% range"], fontsize=8.5)
    if guide:
        ax.axvspan(*guide, color="#eeeeea", zorder=0)
        ax.text(sum(guide) / 2, len(steps) - 0.35, f"company guide {guide[0]:,.0f}–{guide[1]:,.0f}", ha="center", fontsize=7.5, color=MUTED)
    span = [band[0], band[1]] + [s[1] for s in steps if s[2]] + ([guide[0], guide[1]] if guide else [])
    pad = (max(span) - min(span)) * 0.08
    ax.set_xlim(min(span) - pad, max(span) + pad * 2)
    ax.set_ylim(y_b - 0.9, len(steps) - 0.1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel(unit)
    ax.set_title(title, loc="left", fontsize=10)
    _save(fig, name)


def nordic_bridge(d: dict) -> None:
    n = d["nordic"]
    mid, beat = float(n["guide_mid"]), float(n["hist_beat_pct"])
    adj = n.get("signal_adjustments", {})
    inc = float(adj.get("logitech_supplier_incident (graph)", 0.0))
    other = float(sum(v for k, v in adj.items() if k != "logitech_supplier_incident (graph)"))
    gd = n.get("guide")
    lo, hi = (float(gd[0]), float(gd[1])) if isinstance(gd, (list, tuple)) and len(gd) == 2 else (None, None)
    steps = [("guide midpoint", mid, True), (f"× expected guide error {beat:+.2f}% (own record, neither building nor shortage)", mid * beat / 100, False),
             ("supplier incident through the graph (net of the guide)", inc, False)]
    if abs(other) > 1e-9:
        steps.append(("other named lines", other, False))
    steps.append(("chain term (weight 0 in the guided quarter)", 0.0, False))
    steps.append(("point forecast", float(n["point"]), True))
    _bridge(steps, (float(n["low"]), float(n["high"])), (lo, hi) if lo is not None else None,
            "Nordic Q3 2026 revenue build-up (USD m)", "USD m", "nordic_revenue_bridge", 1)


def logitech_bridge(d: dict) -> None:
    lg = d["logitech"]
    mid, beat = float(lg["guide_mid"]), float(lg["hist_beat_pct"])
    chain = float(sum(v for k, v in lg.get("signal_adjustments", {}).items() if "chain" in k))
    gd = lg.get("guide")
    guide = (float(gd[0]), float(gd[1])) if isinstance(gd, (list, tuple)) and len(gd) == 2 else None
    steps = [("guide midpoint", mid, True), (f"× expected guide error {beat:+.2f}% (habit pooled with 12 peers + channel state)", mid * beat / 100, False),
             ("chain term (tier identity, weight 0: F29)", chain, False), ("point forecast", float(lg["point"]), True)]
    _bridge(steps, (float(lg["low"]), float(lg["high"])), guide, "Logitech Q2 FY27 net sales build-up (USD m)", "USD m", "logitech_revenue_bridge", 1)


def gn_bridge(d: dict) -> None:
    """GN's build-up for either method in config forecast.gn_2026Q3.method: the guide-error model (FY guide + own August
    miss -> H2 organic) or the division view (Enterprise and Gaming organic growth from config)."""
    g = d["gn"]
    b = g["base_q3_2025"]
    base = float(b["total"])
    fx = float(g["organic_assumptions"]["fx_pts"])
    if g.get("guidance_anchor"):
        h2 = float(g["guidance_anchor"]["h2_organic_pct"])
        organic = [(f"H2 organic {h2:+.2f}% (FY guide + own August miss, less H1)", base * h2 / 100, False)]
    else:
        oa = g["organic_assumptions"]
        e, gm = float(oa["enterprise"]["mid"]), float(oa["gaming"]["mid"])
        organic = [(f"Enterprise organic {e:+.1f}% (division view)", float(b["enterprise"]) * e / 100, False),
                   (f"Gaming organic {gm:+.1f}% (division view)", float(b["gaming"]) * gm / 100, False)]
    grown = base + sum(v for _, v, _ in organic)
    steps = [("Q3 2025 revenue (continuing ops)", base, True), *organic,
             (f"FX {fx:+.2f} pts (ECB rates since the guide, F27)", grown * fx / 100, False), ("point forecast", float(g["point"]), True)]
    _bridge(steps, (float(g["low"]), float(g["high"])), None, "GN Q3 2026 revenue build-up (DKK m)", "DKK m", "gn_revenue_bridge", 0)


S5 = ROOT / "steps" / "step5_supply_graph" / "outputs"
STATE_SHADE = {"shortage": "#f3e7c9", "building": "#f6d6d3", "drawdown": "#e3ecf5", "lean": "#eef3ea"}


def _break_tests() -> pd.DataFrame:
    """Every tested break (step 5c relationship_breaks + event_breaks rows with a p-value), one label each; `chain` marks the
    tests on the Nordic-on-Logitech link itself (the others test proxies)."""
    link = "Nordic consumer on Logitech sell-through (t-2)"
    r = pd.read_csv(S5 / "relationship_breaks.csv").dropna(subset=["p"])
    r = r.assign(label="chain link · " + r["dated_by"].str.replace("(step 3b, data-dated)", "(data-dated)", regex=False)
                 .str.replace("->", "→") + " @ " + r["break"], chain=r["relationship"].eq(link))
    e = pd.read_csv(S5 / "event_breaks.csv").dropna(subset=["p"])
    rel = e["relationship"].str.replace(link, "chain link", regex=False).str.replace(r" for .*", "", regex=True)
    e = e.assign(label=e["event"] + " · " + rel + " @ " + e["break"], chain=e["relationship"].str.startswith(link))
    cols = ["label", "break", "p", "verdict", "chain"]
    return pd.concat([r[cols], e[cols]], ignore_index=True)


def _link_panel(ax, tests: pd.DataFrame) -> None:
    lag = 2
    t = pd.read_csv(OUTPUTS / "tier_panel.csv").set_index("quarter")
    x = pd.DataFrame({"nordic": t["nordic_consumer_yoy"], "st": (t["logi_sales_yoy"] + t["logi_st_gap"]).shift(lag)}).dropna()
    st = pd.read_csv(S3 / "cycle_state.csv").set_index("quarter")["state_nordic"].reindex(x.index)
    i = np.arange(len(x))
    for k, s_ in enumerate(st):
        if s_ in STATE_SHADE:
            ax.axvspan(k - 0.5, k + 0.5, color=STATE_SHADE[s_], lw=0, zorder=0)
    ax.plot(i, x["nordic"], color=C["nordic"], lw=2, marker="o", ms=3, label="Nordic Consumer YoY % (left)")
    ax2 = ax.twinx()
    ax2.plot(i, x["st"], color=C["chain"], lw=1.6, ls="--", marker="o", ms=3, label=f"Logitech sell-through YoY % at t−{lag} (right)")
    ax2.grid(False)
    lo, hi = float(x["nordic"].min()) - 8, float(x["nordic"].max()) + 30
    ax.set_ylim(lo, hi)
    ax2.set_ylim(float(x["st"].min()) - 2, (float(x["st"].min()) - 2) * hi / lo)       # zero on both axes at the same height
    ax.axhline(0, color=MUTED, lw=0.6)
    on = tests[tests["chain"] & tests["break"].isin(x.index)].sort_values("break").reset_index(drop=True)
    for n, r in on.iterrows():
        k = list(x.index).index(r["break"]) - 0.5
        col = "#b0392e" if r["p"] < 0.05 else INK
        ax.axvline(k, color=col if r["p"] < 0.05 else C["dist"], lw=1.4 if r["p"] < 0.05 else 0.9, ls="-" if r["p"] < 0.05 else ":")
        left = n % 2 == 0                                                         # alternate sides so neighbours never overlap
        ax.text(k - 0.1 if left else k + 0.1, hi - 7 - 10 * (n % 2), f"{r['break'][2:]}: p {r['p']:.2f}", fontsize=7.5, color=col,
                ha="right" if left else "left")
    ax.set_xticks(i, [q[2:] for q in x.index], fontsize=7.5)
    ax.set_ylabel("Nordic Consumer YoY %")
    ax2.set_ylabel("Logitech sell-through YoY %")
    for s_, c in STATE_SHADE.items():
        ax.fill_between([], [], color=c, label=f"state: {s_}")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=7.5, ncol=3, frameon=False)
    ax.set_title(f"The tested relationship: Nordic Consumer on Logitech sell-through (t−{lag}); lines = tested break dates",
                 loc="left", fontsize=10)


def _p_panel(ax, tests: pd.DataFrame) -> None:
    t = tests.sort_values("p", ascending=False).reset_index(drop=True)
    for y, r in t.iterrows():
        hit = r["p"] < 0.05
        ax.plot([r["p"]], [y], "o", ms=7, color="#b0392e" if hit else C["dist"])
        ax.text(r["p"] + 0.015, y, f"p {r['p']:.3f} · {r['verdict']}", va="center", fontsize=7.5, color="#b0392e" if hit else INK)
    ax.axvline(0.05, color="#b0392e", ls="--", lw=1)
    ax.text(0.057, len(t) - 0.35, "p = 0.05", fontsize=7.5, color="#b0392e")
    ax.set_yticks(range(len(t)), t["label"], fontsize=8)
    ax.set_xlim(0, 1.3)
    ax.set_ylim(-0.6, len(t) - 0.1)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("p-value of the break test (Chow; Welch t for the distributor-dollar gap)")
    hits = t.loc[t["p"] < 0.05, "label"].tolist()
    head = f"{len(hits)} of {len(t)} tested breaks reject stability at 5%" + (f": {'; '.join(hits)}" if hits else "")
    ax.set_title(head, loc="left", fontsize=10)


def relationship_breaks() -> None:
    tests = _break_tests()
    fig = plt.figure(figsize=(9.5, 7.6), layout="constrained")
    top, bottom = fig.subfigures(2, 1, height_ratios=[1.2, 1], hspace=0.04)
    _link_panel(top.subplots(), tests)
    _p_panel(bottom.subplots(), tests)
    _save(fig, "relationship_breaks")


def bullwhip() -> None:
    b = pd.read_csv(S3 / "bullwhip_links.csv")
    b = b[(b["window"] == "all") & b["link"].isin(["A", "A'", "B"])].set_index("link").loc[["A", "A'", "B"]]
    labels = {"A": "A · Logitech sell-in / sell-through", "A'": "A′ · Logitech purchases / sell-in", "B": "B · Nordic consumer / Logitech sell-in"}
    fig, ax = plt.subplots(figsize=(9.5, 2.8))
    for k, (link, r) in enumerate(b.iterrows()):
        y = len(b) - 1 - k
        ax.plot([r["sd_ratio_p5"], r["sd_ratio_p95"]], [y, y], color=INK, lw=1.5)
        ax.plot([r["sd_ratio"]], [y], "o", color=C["chain"], ms=8)
        ax.text(r["sd_ratio_p95"] + 0.1, y, f"×{r['sd_ratio']:.2f}  ({r['sd_ratio_p5']:.2f}–{r['sd_ratio_p95']:.2f}, n {int(r['n'])})", va="center", fontsize=8)
    ax.axvline(1, color=C["dist"], ls="--", lw=1)
    ax.text(1.05, len(b) - 0.45, "×1 = no amplification", fontsize=7.5, color=C["dist"])
    ax.set_yticks(range(len(b)), [labels[l] for l in reversed(b.index)], fontsize=8.5)
    ax.set_xlim(0, max(7.5, float(b["sd_ratio_p95"].max()) + 2.2))
    ax.set_ylim(-0.6, len(b) - 0.2)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("ratio of YoY-growth standard deviations (dot = full sample; line = bootstrap 5–95%)")
    ax.set_title("Amplification by link: ratio of YoY-growth standard deviations (2021–26, 21 or 18 quarters)", loc="left", fontsize=10)
    _save(fig, "bullwhip_by_link")


STORY = {"attribution": OUTPUTS / "figures" / "story" / "attribution.svg", "backtest": OUTPUTS / "figures" / "story" / "backtest.svg",
         "lag": OUTPUTS / "figures" / "story" / "lag.svg", "inventory": OUTPUTS / "figures" / "story" / "inventory.svg",
         "bullwhip": OUTPUTS / "figures" / "story" / "bullwhip.svg", "chain_over_time": OUTPUTS / "figures" / "story" / "chain_over_time.svg",
         "forecast_bridges": OUTPUTS / "figures" / "story" / "forecast_bridges.svg",
         "supply_graph": ROOT / "steps" / "step5_supply_graph" / "outputs" / "supply_graph.svg",
         "event_study": ROOT / "steps" / "step5_supply_graph" / "outputs" / "event_study_supplier_incident.svg",
         "data_flow": ROOT / "docs" / "data_flow.svg"}


def copy_story() -> list[str]:
    """Charts drawn by the steps, copied so the write-up and the dashboard read one folder."""
    FIG.mkdir(parents=True, exist_ok=True)
    done = []
    for name, src in STORY.items():
        if src.exists():
            shutil.copyfile(src, FIG / f"{name}.svg")
            done.append(name)
    return done


def write_all() -> list[str]:
    story = copy_story()
    d = json.loads((OUTPUTS / "forecast_details.json").read_text())
    channel_fill()
    channel_weeks()
    gn_channel_weeks()
    nordic_channel()
    nordic_bridge(d)
    logitech_bridge(d)
    gn_bridge(d)
    bullwhip()
    relationship_breaks()
    return story + ["channel_fill_gap_vs_recursion", "logitech_channel_weeks", "gn_channel_weeks", "nordic_channel_state", "nordic_revenue_bridge",
                    "logitech_revenue_bridge", "gn_revenue_bridge", "bullwhip_by_link", "relationship_breaks"]
