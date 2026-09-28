"""Write outputs: processed panel CSV, model_report.md, forecasts.csv, figures."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from core.config import DATA_PROC, OUTPUTS, step_outputs
from step4_report import step4_md   # steps/step4_lag_structure/src (decisions L1-L9)
from edge_lags import write as write_edge_lags   # steps/step4_lag_structure/src (L4-L9)


def _fig_tiers(p: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = p.index.to_timestamp()
    ax.plot(x, p["sellout_proxy_yoy"], label="Tier 0  sell-out proxy (Logitech sell-through)", color="#4C78A8", lw=1.6)
    ax.plot(x, p["logi_ble_yoy"], label="Tier 2  Logitech BLE categories (sell-in)", color="#F58518", lw=1.8)
    ax.plot(x, p["gn_periph_yoy"], label="Tier 2  GN Enterprise + SteelSeries (sell-in, DKK)", color="#72B7B2", lw=1.4, ls="--")
    ax.plot(x, p["nordic_consumer_yoy"], label="Tier 3  Nordic Consumer revenue", color="#E45756", lw=2.2)
    ax.axhline(0, color="#888", lw=0.8)
    for name, col in (("supply_constrained", "#f2f2f2"), ("destock", "#fde9e9")):
        w = p[p["regime"] == name]
        if len(w):
            ax.axvspan(w.index[0].to_timestamp(), w.index[-1].to_timestamp(how="end"), color=col, zorder=0)
    ax.set_ylabel("YoY %"); ax.set_title("Year-on-year growth by tier (shaded: supply-constrained / destock regimes)")
    ax.legend(fontsize=8, loc="lower left"); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _fig_inventory(p: pd.DataFrame, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.2))
    x = p.index.to_timestamp()
    ax.plot(x, p["nordic_inv_days"], label="Nordic own inventory days", color="#E45756", lw=2)
    ax.plot(x, p["logi_inv_days"], label="Logitech own inventory days", color="#F58518", lw=1.8)
    ax.plot(x, p["dist_inv_days_avg"], label="Distributor inventory days (INGM/SNX avg)", color="#4C78A8", lw=1.6)
    ax2 = ax.twinx()
    ax2.bar(x, p["logi_st_gap"], width=60, color="#54A24B", alpha=0.35, label="Logitech sell-through minus sell-in (pts, rhs)")
    ax2.set_ylim(-12, 12); ax2.set_ylabel("pts")
    ax.set_ylabel("days"); ax.set_title("Where the inventory sits: own-balance-sheet days by tier, and Logitech's channel gap")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, fontsize=8, loc="upper left"); ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _fig_xcorr(lag: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    xa = lag["xcorr_all"]
    ax.bar(xa["lag_q"] - 0.2, xa["corr"], width=0.4, label="all quarters", color="#4C78A8")
    xr = lag["xcorr_by_regime"]; xr = xr[xr["regime"] == "normal"]
    ax.bar(xr["lag_q"] + 0.2, xr["corr"], width=0.4, label="normal regime only", color="#F58518")
    ax.set_xlabel("Logitech BLE YoY lagged by k quarters"); ax.set_ylabel("corr with Nordic consumer YoY")
    ax.set_title("Cross-correlation by lag"); ax.legend(fontsize=8); ax.grid(alpha=0.25, axis="y")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _fig_guidance(p: pd.DataFrame, path: Path) -> None:
    """Every guided quarter from the raw series (2019Q1+, F32), not only the panel's 2020Q1+."""
    from guidance_record import nordic_quarters
    fig, ax = plt.subplots(figsize=(10, 3.6))
    s = nordic_quarters(p).dropna(subset=["revenue_usdm"])["error_pct"]
    colors = ["#E45756" if v < 0 else "#54A24B" for v in s]
    ax.bar(s.index.to_timestamp(), s.values, width=70, color=colors)
    ax.axhline(0, color="#888", lw=0.8)
    ax.set_title("Nordic: actual revenue vs guidance midpoint (%) — sign tracks channel regime")
    ax.set_ylabel("% vs midpoint"); ax.grid(alpha=0.25, axis="y")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _fig_regression(reg: dict, path: Path) -> None:
    if not reg.get("ok"):
        return
    fig, ax = plt.subplots(figsize=(10, 3.6))
    x = reg["actual"].index.to_timestamp()
    ax.plot(x, reg["actual"], label="Nordic consumer YoY (actual)", color="#E45756", lw=2)
    ax.plot(x, reg["fitted"], label="fitted (ridge distributed lag)", color="#4C78A8", lw=1.6, ls="--")
    ax.axhline(0, color="#888", lw=0.8); ax.legend(fontsize=8); ax.grid(alpha=0.25)
    ax.set_title(f"Distributed-lag fit  (n={reg['n']}, in-sample R²={reg['r2_in_sample']:.2f}, LOO RMSE={reg['rmse_loo']:.1f} pts)")
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def j(o) -> str:
    return json.dumps(o, indent=2, default=lambda x: x.to_dict() if hasattr(x, "to_dict") else str(x))


def write_outputs(p, lag, reg, gb, attr, fn, fl, fg, ftab, cfg) -> dict[str, Path]:
    OUTPUTS.mkdir(exist_ok=True, parents=True); DATA_PROC.mkdir(exist_ok=True, parents=True)
    figs = OUTPUTS / "figures"; figs.mkdir(exist_ok=True)
    p.to_csv(DATA_PROC / "tier_panel.csv")
    ftab.to_csv(OUTPUTS / "forecasts.csv", index=False)
    # per-step outputs (each step folder keeps its own evidence)
    s2, s3, s4, s6 = (step_outputs(n) for n in ("step2_attribution", "step3_inventory_mechanism", "step4_lag_structure", "step6_backtest"))
    with open(s2 / "attribution.json", "w") as f:
        f.write(j(attr))
    # step 3 writes its own tables and figures (inventory_by_tier.csv, inventory_days.png, ...) in steps/step3_inventory_mechanism
    lag["xcorr_all"].to_csv(s4 / "xcorr_all.csv", index=False)
    lag["xcorr_by_regime"].to_csv(s4 / "xcorr_by_regime.csv", index=False)
    with open(s4 / "lag_analysis.json", "w") as f:
        f.write(j({k: v for k, v in lag.items() if k not in ("xcorr_all", "xcorr_by_regime", "edge_lags")}))
    write_edge_lags(lag["edge_lags"], s4)                     # step 4 section 3: edge-by-edge lag (L4-L9)
    (s4 / "step4_report.md").write_text(step4_md(lag, cfg, attr))
    gb.to_csv(s6 / "guidance_bias.csv", index=False)
    with open(s6 / "regression.json", "w") as f:
        f.write(j({k: v for k, v in reg.items() if k not in ("fitted", "actual", "coef_std", "driver_series")}))
    _fig_tiers(p, figs / "tiers_yoy.png")
    if not (s3 / "inventory_days.png").exists():
        _fig_inventory(p, s3 / "inventory_days.png")
    _fig_xcorr(lag, s4 / "xcorr.png"); _fig_guidance(p, s6 / "nordic_guidance_beat.png"); _fig_regression(reg, s6 / "regression_fit.png")
    for src in (s3 / "inventory_days.png", s4 / "xcorr.png", s6 / "nordic_guidance_beat.png", s6 / "regression_fit.png"):
        (figs / src.name).write_bytes(src.read_bytes())          # the dashboard embeds from outputs/figures

    with open(OUTPUTS / "forecast_details.json", "w") as f:
        f.write(j({"nordic": fn, "logitech": fl, "gn": fg, "attribution": attr,
                   "lag": {k: v for k, v in lag.items() if k not in ("xcorr_all", "xcorr_by_regime")},
                   "regression": {k: v for k, v in reg.items() if k not in ("fitted", "actual", "coef_std", "driver_series")}}))

    md = []
    md.append(f"# Model report — generated {cfg['meta']['as_of']}\n")
    from risk_flags import load_flags, risk_box_md          # steps/step6_backtest/src
    from key_insights import load_insights, insight_box_md  # steps/step6_backtest/src
    md.append(insight_box_md(load_insights()))
    md.append(risk_box_md(load_flags()))
    md.append("## 1. Reasoned lag (before any regression)\n")
    r = lag["reasoned"]
    md.append(f"End-to-end sell-out → Nordic revenue: **{r['low']['weeks']} / {r['mid']['weeks']} / {r['high']['weeks']} weeks** "
              f"(≈ {r['low']['quarters']} / {r['mid']['quarters']} / {r['high']['quarters']} quarters) under a normal channel. "
              "Components (weeks): " + ", ".join(f"{k}={v['mid']}" for k, v in cfg["lag_weeks"].items()) + ".\n")
    md.append("## 2. Empirical checks\n")
    md.append("Timing of Nordic consumer YoY vs Logitech sell-in YoY lagged k quarters - the downstream / industry cycle, not the "
              "chain lag (step 4 decision L2; common-cycle controls give the same timing, step 5 G21):\n")
    md.append(lag["xcorr_all"].round(2).to_markdown(index=False) + "\n")
    md.append(lag["xcorr_by_regime"].round(2).to_markdown(index=False) + "\n")
    md.append("Turning points:\n```\n" + j(lag["turning_points"]) + "\n```\n")
    md.append(f"Amplitude ratio (Nordic consumer swing ÷ Logitech BLE swing): destock 2022-24 = {lag['amplitude']['destock_2022_2024']:.2f}x; "
              f"recovery 2024-26 = {lag['amplitude']['recovery_2024_2026']:.2f}x.\n")
    md.append("## 3. Distributed-lag regression (ridge)\n")
    if reg.get("ok"):
        md.append(f"n={reg['n']}, in-sample R²={reg['r2_in_sample']:.2f}, in-sample RMSE={reg['rmse_in_sample']:.1f} pts, leave-one-out RMSE={reg['rmse_loo']:.1f} pts.\n")
        md.append("Effect on Nordic consumer YoY (pts) of +1pt Logitech BLE YoY at lag k: " + ", ".join(f"L{k}: {v:+.2f}" for k, v in reg["lag_profile_pts"].items()) + f" (sum {reg['sum_lag_effect']:+.2f}; peak lag = {reg['best_lag']}).\n")
        md.append("Standardised coefficients:\n" + reg["coef_std"].round(2).to_frame().to_markdown() + "\n")
    else:
        md.append(f"Regression skipped: {reg.get('reason')}\n")
    md.append("## 4. Guidance-bias model\n" + gb.to_markdown(index=False) + "\n")
    md.append("## 5. Attribution (Monte Carlo, p10/p50/p90)\n```\n" + j(attr) + "\n```\n")
    md.append("## 6. Forecasts\n" + ftab.to_markdown(index=False) + "\n")
    cc = pd.DataFrame([{"company": k, **v["step3_channel_call"]} for k, v in (("Nordic", fn), ("Logitech", fl), ("GN", fg)) if "step3_channel_call" in v])
    if len(cc):
        md.append("### Step 3 channel cross-check (does not move the point; steps/step3_inventory_mechanism/outputs/step3_report.md)\n"
                  + cc[["company", "state", "adj_low", "adj_mid", "adj_high", "unit", "config_line", "config_value", "config_inside_range", "watch_flag"]].to_markdown(index=False) + "\n")
    md.append("### Nordic detail\n```\n" + j(fn) + "\n```\n### Logitech detail\n```\n" + j(fl) + "\n```\n### GN detail\n```\n" + j(fg) + "\n```\n")
    md.append("## 7. Tier panel (last 10 quarters)\n" + p.tail(10)[["sellout_proxy_yoy", "snx_endpoint_yoy", "logi_ble_yoy", "logi_st_gap", "gn_periph_yoy", "gn_st_gap", "nordic_consumer_yoy", "nordic_inv_days", "nordic_dist_state", "wsts_yoy", "regime"]].round(1).to_markdown() + "\n")
    md.append("`wsts_yoy` = WSTS worldwide semiconductor billings YoY (Pipeline B, context only — never a regressor).\n")
    (OUTPUTS / "model_report.md").write_text("\n".join(md))
    return {"report": OUTPUTS / "model_report.md", "forecasts": OUTPUTS / "forecasts.csv", "panel": DATA_PROC / "tier_panel.csv", "figures": figs}
