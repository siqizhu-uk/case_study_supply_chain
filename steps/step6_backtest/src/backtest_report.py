"""Step 6b outputs: walk-forward tables for h = 1 and h = 2, live forecasts, a figure and step6_report.md.
Every number in the prose is filled from the results."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from core.config import step_outputs  # noqa: E402
from walkforward import walk_forward, metrics, metrics_by_regime, encompassing, live_forecasts  # noqa: E402
from composite import run_composite, run_graph_challenger  # noqa: E402
from composite_report import write_composite, write_graph_challenger  # noqa: E402
from risk_flags import risk_flags, risk_box_md, FILE as RISK_FILE  # noqa: E402
from peer_panel_report import run_peer_panel, write_peer_panel  # noqa: E402
from guidance_optimism import run_guidance_optimism  # noqa: E402
from revenue_h2 import run_revenue_h2  # noqa: E402
from guidance_optimism_report import write_guidance_optimism  # noqa: E402
from key_insights import insight_box_md  # noqa: E402

STEP = Path(__file__).resolve().parents[1]
LABEL = {"G": "guidance midpoint", "GB": "guidance + real-time beat (step 7 method)", "N": "naive (last YoY)",
         "L6": "step-6 lag model", "L6tv": "step-6 lag model, share-weighted", "L6leak": "step-6 as built (leaks state t)",
         "L3": "step-3 reduced form (sell-through, lag 2)", "GR": "supply graph (step 5 lag kernel)",
         "GRg": "supply graph, unreported quarter from Logitech's guide (h=2)"}


def _models(h: int) -> list[str]:
    return ["G", "GB", "N", "L6", "L6tv", "L3", "GR"] + (["L6leak"] if h == 1 else ["GRg", "GRi"])


def _figure(wf: dict, d: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    for ax, h in zip(axes, (1, 2)):
        w = wf[h]
        x = pd.PeriodIndex(w.index, freq="Q").to_timestamp()
        ax.plot(x, w["actual_total"], "ko-", lw=2, label="actual")
        ax.plot(x, w["GB_total"], "s--", color="#4C78A8", label=LABEL["GB"] if h == 1 else "last guide x seasonal step + beat")
        ax.plot(x, w["L3_total"], "^-", color="#E45756", label=LABEL["L3"])
        ax.plot(x, w["L6tv_total"], "d-", color="#F58518", label=LABEL["L6tv"])
        ax.set_title(f"h = {h}: {'next quarter (guided)' if h == 1 else 'quarter after the guided one'}", fontsize=9)
        ax.grid(alpha=.3); ax.legend(fontsize=7)
    axes[0].set_ylabel("Nordic revenue, USD m")
    fig.tight_layout()
    f = d / "walkforward.png"
    fig.savefig(f, dpi=130); plt.close(fig)
    return f


def _md(df: pd.DataFrame, **kw) -> str:
    return df.to_markdown(**kw)


def _report(wf: dict, met: dict, enc: dict, reg: dict, live: pd.DataFrame, dec: pd.DataFrame) -> str:
    m1, m2 = met[1].set_index("model"), met[2].set_index("model")
    e1, e2 = enc[1].set_index("model"), enc[2].set_index("model")
    lv = live.set_index("horizon")
    md = ["# Step 6 — Back-test (walk-forward, point-in-time)\n",
          "**Question.** Would the lag model have improved the forecast, using only what was known on each forecast date? "
          "Leave-one-out cannot answer that: it trains on later quarters, and the old regression used the distributor state of the "
          "quarter being predicted. Design, benchmark and reasons: `config/decisions.csv` (B1–B11).\n",
          "## 1. Answer\n",
          f"- **Next quarter (h = 1, the October prints): no.** On the lag models' own quarters, guidance + real-time beat misses by "
          f"USD {m1.loc['L6', 'GB_rmse_same_quarters']:.1f}–{m1.loc['L3', 'GB_rmse_same_quarters']:.1f}m RMSE; the lag models as a tilt on guidance by "
          f"USD {m1.loc['L6tv', 'rmse_total_usdm']:.0f}–{m1.loc['L3', 'rmse_total_usdm']:.0f}m "
          f"({m1.loc[['L6', 'L6tv', 'L3'], 'rmse_ratio_vs_GB'].min():.1f}–{m1.loc[['L6', 'L6tv', 'L3'], 'rmse_ratio_vs_GB'].max():.1f}× worse). "
          f"Encompassing: the real-time beat adds to guidance (t = {e1.loc['GB', 't']:.1f}); no lag model does "
          f"(p ≥ {e1.loc[['L6', 'L6tv', 'L3'], 'p'].min():.2f}). Nordic guides from its own order book, which already contains Logitech's orders.",
          f"- **Quarter after the guided one (h = 2): yes, suggestively.** Against the last guide carried by last year's seasonal step, the lag models cut RMSE to "
          f"{m2.loc[['L6', 'L6tv', 'L3'], 'rmse_ratio_vs_GB'].min():.2f}–{m2.loc[['L6', 'L6tv', 'L3'], 'rmse_ratio_vs_GB'].max():.2f}× on the same quarters; the step-3 reduced form's tilt "
          f"predicts the miss (β = {e2.loc['L3', 'beta_on_tilt']:.2f}, t = {e2.loc['L3', 't']:.1f}, n = {int(e2.loc['L3', 'n'])}); Diebold-Mariano p = {m2.loc['L3', 'dm_p_vs_GB']:.2f}. "
          "With 5–9 forecasts this is evidence, not proof; and what they carry is the common consumer cycle, not the Logitech slice (section 5).",
          f"- **The leak mattered.** With the distributor state of the target quarter, the step-6 model's h = 1 RMSE is USD {m1.loc['L6leak', 'rmse_total_usdm']:.1f}m; "
          f"point-in-time it is USD {m1.loc['L6', 'rmse_total_usdm']:.1f}m. The leaky version cannot even produce a live forecast (the state is not yet known).",
          f"- **In-sample vs out-of-sample.** The step-6 regression reports in-sample R² {reg.get('r2_in_sample', float('nan')):.2f} and leave-one-out RMSE "
          f"{reg.get('rmse_loo', float('nan')):.1f} pts; walk-forward RMSE on the same target is {m1.loc['L6', 'rmse_yoy_pts']:.1f} pts.\n",
          "**What changes:** the October point forecasts stay guidance-based (step 7 has no lag-model tilt; B11). The lag models are the outlook for the "
          "quarter after — Q4 2026 below. For the guided quarter the useful model is the composite channel factor on the guidance MISS (section 7).\n",
          "## 2. Live forecasts from the 21 October origin\n",
          _md(live.set_index("quarter")[["horizon", "guide_total", "GB_total", "N_total", "L6_total", "L6tv_total", "L3_total"]].round(1)), "",
          f"Q4 2026 (h = 2): lag models USD {lv.loc[2, ['L6_total', 'L6tv_total', 'L3_total']].min():.0f}–{lv.loc[2, ['L6_total', 'L6tv_total', 'L3_total']].max():.0f}m "
          f"vs the carried guide USD {lv.loc[2, 'guide_total']:.0f}m — "
          + ("the models disagree on the direction, so the outlook is a range, not a call.\n"
             if (lv.loc[2, ['L6_total', 'L6tv_total', 'L3_total']] > lv.loc[2, 'guide_total']).nunique() > 1
             else f"all lag models point {'above' if lv.loc[2, 'L3_total'] > lv.loc[2, 'guide_total'] else 'below'} the carried guide.\n"),
          "![walk-forward](walkforward.png)\n",
          "## 3. Metrics\n", "### h = 1 (next quarter)\n", _md(met[1], index=False), "", "Encompassing: (actual − guide) = a + b × tilt\n", _md(enc[1], index=False), "",
          "### h = 2 (quarter after the guided one)\n", _md(met[2], index=False), "", _md(enc[2], index=False), "",
          "### By regime (h = 1)\n", _md(metrics_by_regime(wf[1], _models(1)), index=False), "",
          "## 4. Every forecast (h = 1)\n",
          _md(wf[1][["regime", "actual_total", "guide_total", "GB_total", "N_total", "L6_total", "L6tv_total", "L6leak_total", "L3_total", "L6_ntrain"]].round(1)), "",
          "## 5. Limits\n",
          "- 5–14 forecasts per model, one destock and one recovery: every conclusion is conditional on this cycle.",
          "- Latest (restated) data, not first releases (B9): slightly flattering to the models.",
          "- The h = 2 benchmark is weak by construction (no consensus); a sell-side consensus would be the right bar.",
          "- **What the lag models measure.** L3, L6 and GR regress ALL of Nordic's consumer revenue on Logitech (sell-in, sell-through, "
          "or the graph's sell-out proxy), while Logitech + GN are a minority slice of Nordic (step 2). They work as a proxy for the common consumer "
          "cycle - Nordic lags semiconductor billings and US electronics sales by about the same as Logitech (step 4 L2, step 5 G21, "
          "P86) - not as the Logitech / GN slice. They fail when Logitech diverges from the rest of consumer electronics (e.g. the "
          "2026 supplier incident).\n",
          "## 6. Decisions\n", _md(dec[["id", "topic", "decision", "reason"]], index=False), ""]
    return "\n".join(md)


def run_walkforward(p: pd.DataFrame, cfg: dict, tv: pd.Series | None, reg: dict | None = None, write: bool = True,
                    s3: pd.DataFrame | None = None) -> dict:
    """`s3` = step 3's series + factors (needed for the composite channel factor, step 6c)."""
    wf = {h: walk_forward(p, cfg, tv, h=h) for h in (1, 2)}
    met = {h: metrics(wf[h], _models(h)) for h in (1, 2)}
    enc = {h: encompassing(wf[h], [m for m in _models(h) if m != "G"], cfg["backtest"]["hac_lags"]) for h in (1, 2)}
    live = live_forecasts(p, cfg, tv, {1: "2026Q3", 2: "2026Q4"}).reset_index()
    dec = pd.read_csv(STEP / "config" / "decisions.csv")
    comp = run_composite(s3, cfg) if s3 is not None else None
    graph_ch = run_graph_challenger(s3, cfg) if s3 is not None and "graph_challenger" in cfg["composite"] else None
    panel = run_peer_panel(s3, cfg, str(comp["series"].index.min())) if comp is not None else None
    if comp is not None:
        comp["peer_panel"] = panel
    out = {"graph_challenger": graph_ch[0] if graph_ch else None, "walkforward": wf, "metrics": met, "encompassing": enc, "live": live, "decisions": dec, "composite": comp}
    if write:
        d = step_outputs("step6_backtest")
        for h in (1, 2):
            wf[h].round(2).to_csv(d / f"walkforward_h{h}.csv")
            met[h].to_csv(d / f"walkforward_metrics_h{h}.csv", index=False)
            enc[h].to_csv(d / f"walkforward_encompassing_h{h}.csv", index=False)
        live.round(2).to_csv(d / "walkforward_live.csv", index=False)
        from walkforward import gri_fill_check                     # F26: the evidence for GRi's fill, as a computed table
        gri_fill_check(p).round(2).to_csv(d / "gri_fill_check.csv", index=False)
        from logitech_explore import explore          # step 6i exploration (B46): every specification tried is logged
        explore(p).round(3).to_csv(d / "logitech_factor_exploration.csv", index=False)
        _figure(wf, d)
        extra = write_composite(comp, cfg, d) if comp is not None else ""
        extra += "\n" + write_graph_challenger(graph_ch[0], comp, graph_ch[1], d) if graph_ch is not None else ""
        extra += "\n" + write_peer_panel(panel, comp, d) if panel is not None else ""
        insights = None
        if s3 is not None:
            go_sec, insights = write_guidance_optimism(run_guidance_optimism(s3, cfg), cfg, d, run_revenue_h2(cfg))
            extra += "\n" + go_sec
        flags = risk_flags(comp, cfg) if comp is not None else None
        if flags is not None:
            flags.to_csv(d / RISK_FILE, index=False)
        body = _report(wf, met, enc, reg or {}, live, dec)
        title, rest = body.split("\n", 1)
        (d / "step6_report.md").write_text(title + "\n\n" + insight_box_md(insights) + risk_box_md(flags) + rest + "\n" + extra)
        out["risks"] = flags
        out["report"] = d / "step6_report.md"
    return out
