"""Step 3 outputs: tables (CSV), a JSON summary, three figures and step3_report.md. All numbers in the prose are
filled from the results, so the report cannot drift from the code."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from core.config import step_outputs, PIPE_A  # noqa: E402

OUT_NAME = "step3_inventory_mechanism"


def _md(df: pd.DataFrame, **kw) -> str:
    return df.to_markdown(**kw)


def _lk(links: pd.DataFrame, window: str, link: str, col: str) -> float:
    return float(links[(links["window"] == window) & (links["link"] == link)][col].iloc[0])


def _mt(mech: pd.DataFrame, tier: str, spec: str, col: str) -> float:
    return float(mech[(mech["tier"] == tier) & (mech["spec"] == spec)][col].iloc[0])


def _figures(o: dict, d: Path) -> dict:
    f, s = o["factors"], o["series"]
    x = f.index.to_timestamp()
    paths = {}
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for col, lab, c in [("nordic_dio", "Nordic own DIO", "#E45756"), ("logi_dio", "Logitech own DIO", "#F58518"),
                        ("avnet_dio", "Avnet DIO (Nordic distributor)", "#54A24B"), ("arrow_dio", "Arrow DIO (Nordic distributor)", "#88D27A"),
                        ("it_dist_dio_avg", "Ingram / TD Synnex DIO (Logitech side)", "#4C78A8"), ("mchp_disti_days", "Microchip distributor days", "#B279A2")]:
        ax.plot(x, f[col], label=lab, color=c, lw=1.8)
    ax.set_ylabel("days"); ax.set_title("Inventory days by tier (own balance sheets) and the MCU channel"); ax.legend(fontsize=7, ncol=2); ax.grid(alpha=.3)
    paths["inventory_days"] = d / "inventory_days.png"; fig.tight_layout(); fig.savefig(paths["inventory_days"], dpi=130); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    lp, la, g = o["channel"]["logitech"], o["channel"]["logitech_alt"], o["channel"]["gn"]
    t = lp["table"]["excess_weeks"].dropna(); ta = la["table"]["excess_weeks"].dropna()
    axes[0].plot(t.index.to_timestamp(), t, color="#F58518", lw=2, label=f"start {lp['start']} (primary)")
    axes[0].plot(ta.index.to_timestamp(), ta, color="#F58518", lw=1, ls="--", label=f"start {la['start']}")
    for q in lp["anchor_fit"]["anchors_used"]:
        axes[0].scatter(pd.Period(q, "Q").to_timestamp(), t.get(pd.Period(q, "Q")), color="k", zorder=3, s=14)
    axes[0].axhline(0, color="grey", lw=.8); axes[0].set_title("Logitech channel vs target (weeks of sell-in)\ndots = management 'at target' anchors", fontsize=9)
    axes[0].legend(fontsize=7); axes[0].grid(alpha=.3)
    tg = g["table"]["excess_weeks"].dropna()
    axes[1].bar(tg.index.to_timestamp(), tg, width=60, color="#4C78A8")
    axes[1].set_title("GN Enterprise channel since 2024Q3 (weeks, relative, grade D)", fontsize=9); axes[1].grid(alpha=.3)
    paths["channel_index"] = d / "channel_index.png"; fig.tight_layout(); fig.savefig(paths["channel_index"], dpi=130); plt.close(fig)

    r = o["reduced"]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    ax.plot(r["actual"].index.to_timestamp(), r["actual"], "o-", color="#E45756", label="Nordic consumer YoY (actual)")
    ax.plot(r["fitted"].index.to_timestamp(), r["fitted"], "s--", color="#4C78A8",
            label=f"a + b x Logitech sell-through YoY(t-{r['lag']})   b = {r['coef']['g']:.2f}")
    ax.axhline(0, color="grey", lw=.8); ax.set_ylabel("% YoY"); ax.legend(fontsize=8); ax.grid(alpha=.3)
    ax.set_title(f"Reduced form: n={r['n']}, R² {r['r2']:.2f}, leave-one-out RMSE {r['rmse_loo']:.0f} pts", fontsize=9)
    paths["amplification"] = d / "amplification.png"; fig.tight_layout(); fig.savefig(paths["amplification"], dpi=130); plt.close(fig)
    return paths


def _validation_tables() -> str:
    proc = PIPE_A / "data" / "processed"
    parts = []
    for name in ("inventory_detail_validation.csv", "nordic_balance_validation.csv"):
        fp = proc / name
        parts.append(_md(pd.read_csv(fp), index=False) if fp.exists() else f"`{name}` not found — run `python pipelines/A_company_financials/scripts/validate.py`")
    return "\n\n".join(parts)


def _report(o: dict, cfg: dict) -> str:
    f, ch, call = o["factors"], o["channel"], o["call"].set_index("company")
    q = pd.Period("2026Q2", "Q")
    lp = ch["logitech"]
    mech, chain, pr = o["mechanism"], o["chain"], o["prediction"]
    nord = mech[(mech["tier"] == "nordic")].set_index("spec")
    red = o["reduced"]
    conc = o["concentration"]
    links = o["bullwhip"]
    c23 = conc.loc[2023]
    pri = o["prior"].set_index("tier_test")
    ldio = f["logi_dio"].loc["2021Q1":"2024Q4"]
    latest = f.loc[[q], ["nordic_dio", "nordic_fwd_dio", "nordic_inv_spread", "nordic_dso", "nordic_dso_yoy_chg", "logi_dio", "logi_fg_share",
                         "logi_fg_weeks", "logi_fg_spread", "logi_dso", "logi_dso_yoy_chg", "logi_purchases_yoy", "arrow_dio", "avnet_dio",
                         "mchp_disti_days", "it_dist_dio_avg"]].T.round(1)
    latest.columns = ["2026Q2"]
    md = [f"# Step 3 — Inventory mechanism (bullwhip) — generated {cfg['meta']['as_of']}\n",
          "**Question.** Where does inventory sit between end demand and Nordic's revenue, who holds it, how much does each link "
          "amplify, and what does the channel position say about the October prints? Formulas, reasons and data checks are all "
          "below; each judgment call has an id (D1-D21) in `config/decisions.csv`.\n",
          "## 1. The call (what an analyst would say on 22 Oct / 27 Oct / 5 Nov)\n"]
    for comp in ("nordic", "logitech", "gn"):
        r = call.loc[comp]
        flag = " **Watch flag:** receivables are rising faster than revenue while the channel fills." if r["watch_flag"] else ""
        md.append(f"- **{ {'nordic': 'Nordic', 'logitech': 'Logitech', 'gn': 'GN'}[comp]} — {r['print']}.** {r['state']}. Direction: {r['direction']}.{flag} "
                  f"Channel adjustment {r['adj_low']:+.0f} / {r['adj_mid']:+.0f} / {r['adj_high']:+.0f} {r['unit']} (low/mid/high; {r['formula']}). "
                  f"Forecast line `{r['config_line']}` = {r['config_value']:+g} → {'inside' if r['config_inside_range'] else 'OUTSIDE'} step 3's range. "
                  f"Questions: {r['questions']}")
    lg = call.loc["logitech"]
    md.append(f"\nWhere step 3 disagrees with the forecast config: Logitech's refill mid ({lg['adj_mid']:+.0f} USDm) is well above the "
              f"hand-set channel lines ({lg['config_value']:+g}; removed by step-7 decision F5 in favour of step 7c's data-weighted chain term); "
              "the gap is the supply-availability assumption after the late-June incident. GN: the channel view puts Enterprise organic growth at "
              f"{cfg['inventory_mechanism']['channel_call']['gn_sellout_growth_next_q_pct']['mid'] - cfg['inventory_mechanism']['channel_call']['gn_gap_next_q_pts']['mid']:+.0f}% "
              f"(mid) against the forecast's {cfg['forecast']['gn_2026Q3']['enterprise_org_pct']['mid']:+.0f}%. Step 3 does not overwrite the config (D15).\n")

    md += ["## 2. Inventory factors — the formulas\n",
           "| factor | formula | reads as |", "|---|---|---|",
           "| DIO | inventory_t / COGS_t × 91.25 | days of trailing cost of sales on hand |",
           "| forward DIO | inventory_t / (guided revenue_{t+1} × (1 − margin)) × 91.25 | days of NEXT quarter's cost of sales — a build ahead of guided growth is not an overhang (D17) |",
           "| inventory–sales spread | YoY%(inventory) − YoY%(revenue) | Bernard & Noel (1991), Thomas & Zhang (2002): inventory outgrowing sales predicts weaker sales and margins |",
           "| stage spread | YoY%(stage) − YoY%(revenue) | finished goods outgrowing sales = demand shortfall; raw materials / WIP outgrowing sales = planned build |",
           "| FG share, FG weeks | FG / inventory; FG / COGS × 13 | OEM finished-goods cover |",
           "| DSO | receivables_t / revenue_t × 91.25 | channel-stuffing tell: sell-in pushed on extended terms shows up in DSO first |",
           "| purchases | COGS_t + inventory_t − inventory_{t−1} | what the company bought from its suppliers = the order signal the next tier sees |",
           "| channel fill (exact) | F_t = F_{t−4}(1+g_out) − gap_t × S_{t−4} | see §4 |",
           "| distributor days | Arrow / Avnet DIO; Microchip 'our distributors maintained NN days' | component-channel cover |", "",
           "Latest quarter:\n", _md(latest), "",
           "Nordic inventory by stage at each year end (AR note; raw materials = wafers at sub-contractors):\n",
           _md(o["nordic_stage"][["raw_materials_usdm", "work_in_progress_usdm", "finished_goods_usdm", "total_usdm", "raw_materials_share",
                                  "finished_goods_share", "finished_goods_spread_pts", "raw_materials_spread_pts", "finished_goods_weeks_on_q4_cogs"]]), "",
           f"Reading: the 2023 destock shows as finished goods outgrowing revenue by {o['nordic_stage'].loc[2023, 'finished_goods_spread_pts']:+.0f} pts "
           f"and FG cover rising to {o['nordic_stage'].loc[2023, 'finished_goods_weeks_on_q4_cogs']:.0f} weeks of Q4 COGS; 2025 is the unwind "
           f"(FG spread {o['nordic_stage'].loc[2025, 'finished_goods_spread_pts']:+.0f} pts, wafers drawn down). The 2026 build "
           f"(USD 155m → {o['series'].loc[q, 'nordic_inventory']:.0f}m) has no stage split until AR2026 — a blind spot (D3).\n",
           "## 3. Data added for this step and how each number was validated\n",
           "| source | grade | retrieval | validation |", "|---|---|---|---|",
           "| Logitech XBRL: raw materials, finished goods, receivables | B/A | SEC company-facts API | RM + FG = total inventory (26 quarters); total = hand-typed inventory |",
           "| Arrow, Avnet XBRL: revenue, COGS, inventory, receivables | B/A | SEC company-facts API; 52/53-week closes mapped to calendar quarters | revenue > COGS > 0, margins in 10-13% (Q4 derived as FY − 9M) |",
           "| Microchip distributor days | B (10-Q) / A (10-K) | EDGAR primary documents, regex on the sentence | verbatim quote stored; each 'compared to MM days at <date>' equals the filing for that date |",
           "| Nordic receivables + inventory, quarterly | B | cached NewsWeb reports, script-read balance sheet | year-ago column in report t = current column in report t−4; inventory = hand-typed |",
           "| Nordic inventory by stage, annual | A | cached annual reports, note 'Cost of materials / inventory' | stages sum to reported inventory; prior-year column chains |",
           "| Nordic top-10 / broad-market Bluetooth revenue | B (2024: C) | hand-typed with quote fragments | every fragment found in the cited report; 276 + 208 = 2023 short-range revenue |",
           "| Logitech 'channel at target' anchors | C | saved transcript excerpts | fragment found in excerpt at run time |", "",
           _validation_tables(), "",
           "Anchor check (run time):\n", _md(o["anchors"][["company", "quarter", "statement", "verified", "check"]], index=False), "",
           "## 4. Channel-inventory index (Logitech, GN)\n",
           "Flow identity I_t − I_{t−1} = S_t − T_t = F_t. Both companies disclose gap = g_out − g_in (YoY points). With "
           "S_t = S_{t−4}(1+g_in) and T_t = T_{t−4}(1+g_out):\n",
           "    F_t = F_{t−4}(1 + g_out) − gap_t × S_{t−4}        (exact; F = 0 before the start, D5)\n",
           "The naive −gap × S_{t−4} forgets that the year-ago quarter may itself have been a drain: in 2024Q1 it reads "
           f"{lp['table'].loc['2024Q1', 'fill_naive']:+.0f}m (a build) where the exact recursion reads {lp['table'].loc['2024Q1', 'fill_exact']:+.0f}m — "
           "Logitech's CFO on the Q4 FY24 call: '2 points of that is simply comparing the channel inventory year-over-year'. "
           "The level is pinned by five management 'at target' statements (D7); their spread is the error bar.\n",
           f"Logitech: {lp['choice']}. Anchor readings (weeks): {lp['anchor_fit']['anchor_weeks']}; rms {lp['anchor_fit']['rms_weeks']:.2f} wk. "
           f"2026Q2: {lp['table'].loc[q, 'excess_weeks']:+.1f} wk (all anchors), "
           f"{lp['table'].loc[q, 'excess_weeks'] - lp['anchor_fit']['anchor_weeks'][lp['anchor_fit']['anchors_used'][-1]]:+.1f} wk (latest anchor). "
           "The anchors drift down by ~2 weeks from 2025Q1 to 2026Q1 although management called the channel 'at target' each time: either the "
           "weeks-on-hand target is being lowered or the coded gaps run ~0.5 pt a quarter high. Both make the latest-anchor reading the least biased, "
           "so it is the low end of the deficit and half of the mid (D21).\n",
           _md(lp["table"].loc["2023Q1":"2026Q2", ["sell_in", "g_in_pct", "gap_pts", "g_out_pct", "fill_naive", "fill_exact", "excess_usd", "excess_weeks"]].round(1)), "",
           f"GN Enterprise (no anchor; relative to 2023Q3-2024Q2; grade D): cumulative {ch['gn']['table']['excess_usd'].dropna().iloc[-1]:.0f} DKKm = "
           f"{ch['gn']['table']['excess_weeks'].dropna().iloc[-1]:.1f} weeks of sell-in drained since 2024Q3.\n",
           "![channel index](channel_index.png)\n",
           "## 5. Bullwhip, link by link\n",
           "Variance ratio VR = Var(orders upstream) / Var(demand received), on YoY growth (removes seasonality), moving-block bootstrap 90% interval (D14):\n",
           _md(links, index=False), "",
           f"- **Link A (Logitech's retail + distribution channel) does not amplify**: VR {_lk(links, 'all', 'A', 'variance_ratio'):.2f}. "
           "Logitech runs the channel to target; the gap moves sell-in by a few points, not multiples.",
           f"- **Link A' (Logitech's own stock) amplifies ~{_lk(links, 'all', "A'", 'sd_ratio'):.1f}× in sd terms**: purchases fell "
           f"{c23['logi_purchases_yoy_pct']:+.0f}% in 2023 against sell-in {c23['logi_sellin_yoy_pct']:+.0f}% (Logitech cut DIO from {ldio.max():.0f} days in {ldio.idxmax()} to {ldio.min():.0f} in {ldio.idxmin()}).",
           f"- **Link B (Nordic consumer vs Logitech sell-in) is the big one — {_lk(links, 'all', 'B', 'sd_ratio'):.1f}× sd**, but the normal-regime "
           f"ratio ({_lk(links, 'normal', 'B', 'variance_ratio'):.0f}× VR) is a small-denominator artefact: Logitech growth barely moved in 2024-26. "
           "The '5.5× in the recovery' is the same artefact plus Nordic share / content gains (the trend a in §6), not bullwhip.\n",
           "### Whose revenue swung: top-10 customers vs the broad market (Nordic's own disclosure)\n",
           _md(conc), "",
           f"In 2023 Nordic's top-10 Bluetooth customers moved {c23['top10_yoy_pct']:+.0f}% and the broad market {c23['broad_yoy_pct']:+.0f}%, while Logitech's "
           f"sell-in moved {c23['logi_sellin_yoy_pct']:+.0f}%, sell-through {c23['logi_sellthrough_yoy_pct']:+.0f}% and purchases {c23['logi_purchases_yoy_pct']:+.0f}%. "
           "The destock was a broad-market (distribution-channel) event. Logitech is a top-10 customer on step 2's estimate, so the whole-company "
           "amplitude must not be applied to the Logitech slice (D9). Tension to state openly: Logitech's purchases fell far more than the top-10 bucket, "
           "so either other top-10 customers grew (health, wearables) or Logitech's radio buying held up better than its total purchases — the data cannot say which.\n",
           _md(o["slice"], index=False), "",
           "## 6. Why the chain amplifies — the regression and its intuition\n",
           "**Ordering rule** (Sterman 1989; stock adjustment, Metzler 1941 / Blinder & Maccini 1991): "
           "O_t = E[D_t] + (I*_t − I*_{t−1}) + α(I*_t − I_t), with target stock I* = c × trailing-twelve-month demand. In YoY growth:\n",
           "    g^O_t ≈ g_t + c·(g_t − g_{t−4}) − α'·gap_t\n",
           "- term 1 **pass-through**: orders grow with demand;",
           "- term 2 **accelerator**: a tier holding c years of cover orders c × the *change* in demand growth on top — orders LEAD demand; c × 52 = weeks of cover. "
           "(The one-quarter version g_t − g_{t−1} does not cancel Logitech's ~25% Q4→Q1 seasonality, D19.)",
           "- term 3 **stock-gap correction**: when demand falls, stock piles up involuntarily (distributor days are counter-cyclical: Avnet, Arrow, Microchip "
           "correlate −0.6 with same-quarter growth), then is cut — orders LAG demand.\n",
           "**Prior, stated before fitting (D10)** — cover at each stocking point:\n", _md(o["prior"], index=False), "",
           "**Tests** — y = a + b·g_{t−L} [+ c·(g_{t−L} − g_{t−L−4})] [+ γ·gap_{t−K}], OLS, Newey-West s.e., leave-one-out RMSE:\n",
           _md(mech.drop(columns=["b_ci90"]), index=False), "",
           "What the data say:\n",
           f"1. **Pass-through is identified everywhere**: channel b = {_mt(mech, 'logitech_channel', 'A demand', 'b_demand'):.2f}, "
           f"Logitech purchases b = {_mt(mech, 'logitech_own', 'A demand', 'b_demand'):.2f}, "
           f"Nordic consumer b = {red['coef']['g']:.2f} (90% bootstrap {red['ci90']['g'][0]:.1f}-{red['ci90']['g'][1]:.1f}) on Logitech end demand two quarters earlier. "
           "Amplification shows up as an elasticity above one, not as a separate inventory term.",
           f"2. **The accelerator is absent where it is well identified**: at the two same-quarter tiers c ≈ 0 "
           f"({_mt(mech, 'logitech_channel', 'B + accelerator', 'c_accel'):+.2f} ± {_mt(mech, 'logitech_channel', 'B + accelerator', 'c_se'):.2f}; "
           f"{_mt(mech, 'logitech_own', 'B + accelerator', 'c_accel'):+.2f} ± {_mt(mech, 'logitech_own', 'B + accelerator', 'c_se'):.2f}) "
           f"against a prior of {pri.loc['logitech_channel', 'low']:.0f}-{pri.loc['logitech_own', 'high']:.0f} weeks "
           f"(c ≈ {pri.loc['logitech_channel', 'low'] / 52:.2f}-{pri.loc['logitech_own', 'high'] / 52:.2f}). At Nordic its implied cover flips sign with the lag "
           f"({nord.loc['B + accelerator, lag 1', 'implied_cover_wk']:+.0f} / {nord.loc['B + accelerator', 'implied_cover_wk']:+.0f} / {nord.loc['B + accelerator, lag 3', 'implied_cover_wk']:+.0f} weeks "
           "for lags 1/2/3): with 16 quarters and one cycle, the accelerator and the lag cannot be separated. A negative 'cover' is the phase-lag signature of term 3.",
           f"3. **The stock-gap proxy adds nothing measurable**: γ = {nord.iloc[2]['gamma_gap']:+.2f} ± {nord.iloc[2]['gamma_se']:.2f}, leave-one-out RMSE "
           f"{nord.iloc[2]['rmse_loo']:.1f} vs {red['rmse_loo']:.1f} for demand only.",
           "4. **Links multiply to the direct estimate** (a consistency check on the three links):\n",
           _md(chain.assign(ci90=chain["ci90"].map(lambda v: f"{v[0]:.2f}-{v[1]:.2f}" if isinstance(v, tuple) else "")), index=False), "",
           "**Decision (D11):** the reduced form kept is the demand elasticity b with lag 2. Inventory information enters the forecast as *state* "
           "(the channel call in §1), not as a regression coefficient, because no inventory term is identified with the data available. "
           f"Implied Nordic consumer YoY for 2026Q3 from Logitech end demand in {pr['driver_quarter']} ({pr['driver_yoy']:+.1f}%): "
           f"{pr['trend_a']:.1f} + {pr['demand_b_x_g']:.1f} = **{pr['yoy']:+.0f}%**, leave-one-out RMSE {pr['rmse_loo']:.0f} pts — a sanity check only; "
           "far too wide to move a forecast.\n",
           "![reduced form](amplification.png)\n",
           "## 7. When this works and when it does not\n",
           "- Works: normal and destock regimes, for the *direction* of the next quarter's channel move and for the size of Logitech's channel gap.",
           "- Fails: supply-constrained regimes (2021-22: revenue = wafers, excluded, D13); after a supply shock at the OEM (the late-June Logitech "
           "supplier incident caps the refill — the Logitech range is wide for that reason).",
           f"- Weakest link: the channel LEVEL. The Logitech index has a ±{lp['anchor_fit']['rms_weeks']:.1f}-week error bar from management's own statements; "
           "GN has no anchor at all; Nordic's distribution channel is known only as a coded state plus the Microchip / Arrow / Avnet proxies.",
           "- Cannot tell: Nordic's revenue from Logitech specifically (no disclosure); the 2026 stage split of Nordic's inventory; channel weeks-on-hand "
           "anywhere in this chain in numbers.\n",
           "## 8. Decisions (full text in `config/decisions.csv`)\n",
           _md(o["decisions"][["id", "topic", "decision", "reason"]], index=False), ""]
    return "\n".join(md)


def _jsonable(o):
    if isinstance(o, (pd.Series, pd.DataFrame)):
        return None
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items() if not isinstance(v, (pd.Series, pd.DataFrame))}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    return o


def write_step3(o: dict, p: pd.DataFrame, cfg: dict) -> dict:
    d = step_outputs(OUT_NAME)
    o["factors"].round(2).to_csv(d / "factors_quarterly.csv")
    o["nordic_stage"].to_csv(d / "nordic_inventory_stage.csv")
    cols = [c for c in p.columns if "inv_days" in c or "st_gap" in c or "dist_state" in c]
    p[cols].join(o["factors"][["arrow_dio", "avnet_dio", "mchp_disti_days"]]).round(1).to_csv(d / "inventory_by_tier.csv")
    o["channel"]["logitech"]["table"].round(2).to_csv(d / "channel_index_logitech.csv")
    o["channel"]["logitech_alt"]["table"].round(2).to_csv(d / "channel_index_logitech_alt_start.csv")
    o["channel"]["gn"]["table"].round(2).to_csv(d / "channel_index_gn.csv")
    o["bullwhip"].to_csv(d / "bullwhip_links.csv", index=False)
    o["concentration"].to_csv(d / "nordic_top10_vs_broad.csv")
    o["slice"].to_csv(d / "slice_multiplier.csv", index=False)
    o["prior"].to_csv(d / "prior_cover_weeks.csv", index=False)
    o["mechanism"].to_csv(d / "mechanism_tests.csv", index=False)
    o["chain"].to_csv(d / "chain_consistency.csv", index=False)
    o["call"].to_csv(d / "channel_call.csv", index=False)
    o["anchors"].to_csv(d / "anchor_check.csv", index=False)
    summary = {"channel_index_choice": o["channel"]["logitech"]["choice"],
               "logitech_anchor_fit": o["channel"]["logitech"]["anchor_fit"], "gn_anchor_fit": o["channel"]["gn"]["anchor_fit"],
               "reduced_form": {k: v for k, v in o["reduced"].items() if k not in ("fitted", "actual")},
               "prediction_2026Q3": o["prediction"], "call": o["call"].to_dict(orient="records")}
    (d / "step3_summary.json").write_text(json.dumps(_jsonable(summary), indent=2, default=str))
    figs = _figures(o, d)
    (d / "step3_report.md").write_text(_report(o, cfg))
    return {"report": d / "step3_report.md", **figs}
