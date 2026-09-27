"""Step 5g — the markdown report of the industry-cycle challenger (G29): reasoning, spec, availability, scores, live Q4."""
from __future__ import annotations

import numpy as np
import pandas as pd

SCORE_COLS = ["model", "vs", "n", "first", "last", "rmse", "bias", "rmse_bench_same_quarters", "rmse_ratio", "dm_t", "dm_p",
              "enc_beta", "enc_t", "gain_share_top3"]


def _f(x, fmt: str = "{:.1f}") -> str:
    return fmt.format(x) if isinstance(x, (int, float, np.floating)) and np.isfinite(x) else "n/a"


def spec_md(cfg: dict) -> list[str]:
    cc = cfg["cycle_challenger"]
    rows = [{"model": m, "role": s["role"], "regressors": ", ".join(s["regressors"]), "what": s["label"]} for m, s in cc["models"].items()]
    return ["## Specification (config `cycle_challenger`, fixed before any score; decision G29)\n",
            "Nordic consumer YoY at t (GR's target) = a + b x cycle YoY at t-2, OLS on an expanding window through step 6's "
            "`forecast_row` at h=2: the same targets, training rows, supply-constrained rule and guide rows as GR. Nordic total = the "
            "guide-anchored benchmark (Q3 guide x last year's Q3->Q4 step) + the model's consumer tilt.\n",
            pd.DataFrame(rows).to_markdown(index=False), "",
            "Why RSEAS and one slope: consumer end demand is the common driver P77 points at; WSTS world billings carry the AI / memory "
            "composition break from 2024 (G28, P110); distributor dollars carry memory ASPs and the merger mask; Microchip distributor days "
            "are a channel state already in the 6c composite and the anchor (F20). With 8-18 training rows and one cycle, a second "
            "regressor buys noise (P58). Prior before scoring: weak (US-only, nominal, appliances included, +-5% outside COVID).\n"]


def availability_md(av: pd.DataFrame) -> list[str]:
    return ["## What is known at the live origin\n",
            "A cycle quarter is published when its third month is (month end + release lag: RSEAS = route_nowcast.release_lag.rseas; "
            "WSTS from config). The regressor is quarter t-2; t-1 is filled by persistence (F24), no partial quarters.\n",
            av.round(2).to_markdown(index=False), ""]


def walkforward_md(wf: pd.DataFrame, cfg: dict) -> list[str]:
    cols = ["actual_total", "GB_total", "GR_total", "CH_total"] + [f"{m}_total" for m in cfg["cycle_challenger"]["models"]] + ["x_rseas", "x_wsts"]
    d = wf.dropna(subset=["actual_total"])[[c for c in cols if c in wf]]
    return ["## Walk-forward, h=2 (USD m; x = regressor as known at each origin, YoY %)\n", d.round(1).to_markdown(), ""]


def scores_md(sc: pd.DataFrame, adopt: dict, drop: dict, cfg: dict) -> list[str]:
    main = sc[sc["scope"] == "main"]
    level = main[main["vs"] == ""][["model", "n", "first", "last", "rmse", "bias"]]
    pairs = main[main["vs"] != ""][SCORE_COLS]
    sens = sc[sc["scope"].str.startswith("sensitivity") & (sc["vs"].isin(["", "GR"]))][SCORE_COLS]
    a = cfg["cycle_challenger"]["adoption"]
    return ["## Scores on identical quarters (h=2)\n", "Level (every model on the same quarters; COMBO = (GR + CYC) / 2, diagnostic only):\n",
            level.round(2).to_markdown(index=False), "",
            "Pairwise (model vs benchmark; encompassing = (actual - benchmark) on (model - benchmark): does the model add to it? "
            "top-3 = share of the squared-error gain from the best three quarters, n/a when there is no net gain):\n",
            pairs.round(2).to_markdown(index=False), "",
            f"**Adoption bar** (RMSE < GR AND (DM t <= -{a['t_min']} OR encompassing t >= {a['t_min']}) AND top-3 < {a['max_top3_gain_share']}): "
            f"RMSE below GR {adopt['rmse_below_gr']}, test {adopt['test_passed']}, gain not concentrated {adopt['gain_not_concentrated']} -> "
            f"**{'met' if adopt['bar_met'] else 'not met'}**. Either way CYC is a pre-registered challenger for this print only.\n",
            f"Diagnostic added after the first scores (not part of the bar): leaving one quarter out, the encompassing t of CYC over GR "
            f"ranges {_f(drop['t_min_drop_one'])} (without {drop['quarter_dropped']}) to {_f(drop['t_max_drop_one'])}.\n",
            "Step 6's own sensitivity flip (supply-constrained quarters out of training, both models):\n",
            sens.round(2).to_markdown(index=False), ""]


def live_md(lt: pd.DataFrame, lv: dict, res: dict) -> list[str]:
    cols = ["model", "total_ex_event", "event_usdm", "point", "low", "high", "wf_rmse", "minus_CH", "minus_GB"]
    return [f"## Live: Nordic {lv['quarter']} (origin {lv['origin']}, h=2)\n",
            "Every line carries Logitech's supplier-incident term for Q4 (step 5d / F21). Band = config band_z x the model's walk-forward "
            "RMSE on all its own quarters (GR and CH as in steps/step7_forecast/outputs/q4_prereg_log.csv; GR's lag-scenario widening is in "
            "outputs/forecast_next_quarter.csv). minus_CH = the model minus the chain as reasoned "
            "(the Logitech / GN slice only): for GR it is the cycle beyond the slice as GR sees it; for CYC the same quantity as the "
            "industry series sees it.\n", lt[cols].round(1).to_markdown(index=False), "",
            f"Pre-registered in `cycle_challenger_prereg_log.csv` (spec {res['hashes']['spec']}, data {res['hashes']['data']}); "
            f"check on {res['check_on']} (Nordic Q4 report). Nordic's Q3 report on 22 Oct adds one training row for later h=2 lines; "
            "the Q4 record is the last row logged before the print.\n"]


def sentences(res: dict, cfg: dict) -> list[str]:
    """3-5 computed sentences."""
    prim = cfg["cycle_challenger"]["primary"]
    s = res["scores"]
    m = s[(s["scope"] == "main") & (s["vs"] == "")].set_index("model")
    c, g = s[(s["scope"] == "main") & (s["model"] == prim) & (s["vs"] == "GR")].iloc[0], s[(s["scope"] == "main") & (s["model"] == "GR") & (s["vs"] == prim)].iloc[0]
    w = s[(s["scope"] == "main") & (s["model"] == "CYCw") & (s["vs"] == "GR")].iloc[0]
    lt, lv, a = res["live_table"].set_index("model"), res["live"], res["adoption"]
    wf = res["wf"].dropna(subset=[f"{prim}_total", "GR_total", "actual_total"])
    better = int(((wf[f"{prim}_total"] - wf["actual_total"]).abs() < (wf["GR_total"] - wf["actual_total"]).abs()).sum())
    xmax = float(wf["x_wsts"].max())
    return ["## Reading (computed)\n",
            f"- On the {int(c['n'])} common quarters ({c['first']}-{c['last']}) CYC's RMSE is {m.loc[prim, 'rmse']:.1f}m against GR {m.loc['GR', 'rmse']:.1f}, "
            f"CH {m.loc['CH', 'rmse']:.1f} and GB {m.loc['GB', 'rmse']:.1f} (bias {m.loc[prim, 'bias']:+.1f}m); it is closer than GR in {better} of {len(wf)} quarters. "
            f"The bar is {'met' if a['bar_met'] else 'not met'}.",
            f"- CYC adds to GR: beta {c['enc_beta']:+.2f} (t {c['enc_t']:+.1f}); GR adds to CYC: beta {g['enc_beta']:+.2f} (t {g['enc_t']:+.1f}); DM-HLN t {c['dm_t']:+.1f}. "
            f"The in-sample encompassing fit has its own intercept (it removes CYC's bias) and rests on few quarters (drop-one t down to "
            f"{res['enc_drop_one']['t_min_drop_one']:+.1f}); the average (GR + CYC) / 2 scores {m.loc['COMBO', 'rmse']:.1f}m, worse than GR.",
            f"- The WSTS variant scores {w['rmse']:.1f}m ({w['rmse_ratio']:.2f}x GR, DM t {w['dm_t']:+.1f}) but its live input "
            f"({lv['CYCw_x_wsts']:+.0f}% for {pd.Period(lv['quarter'], 'Q') - 2}) is {lv['CYCw_x_wsts'] / xmax:.1f}x the largest value it was scored on ({xmax:+.0f}%), "
            f"so its Q4 line is {lt.loc['CYCw', 'point']:.0f}m: the AI / memory composition break, not information about Nordic.",
            f"- Q4 2026: GR {lt.loc['GR', 'point']:.1f}m, CH {lt.loc['CH', 'point']:.1f}, CYC {lt.loc[prim, 'point']:.1f} ({lt.loc[prim, 'low']:.0f}-{lt.loc[prim, 'high']:.0f}), "
            f"GB {lt.loc['GB', 'point']:.1f}. Beyond the Logitech / GN slice GR sees {lt.loc['GR', 'minus_CH']:+.1f}m of cycle, CYC {lt.loc[prim, 'minus_CH']:+.1f}m: "
            f"US electronics-store sales ({lv[f'{prim}_x_rseas']:+.1f}% YoY) imply no extra cycle; with CYC's walk-forward bias of {m.loc[prim, 'bias']:+.1f}m its line more likely errs low.",
            ""]


def report_md(res: dict, cfg: dict) -> str:
    res = {**res, "check_on": cfg["cycle_challenger"]["check_on"]}
    head = ["# Step 5g — industry-cycle regression as a pre-registered Q4 challenger (G29)\n",
            "GR's h=2 slope is ~3x the attribution slice (P77): it partly times the common consumer-electronics / semiconductor cycle. "
            "CYC asks whether an industry-cycle series times that cycle better when Nordic is regressed on it directly. It is a "
            "challenger only: the Q4 forecast stays GR (F22 / F24).\n"]
    return "\n".join(head + sentences(res, cfg) + spec_md(cfg) + availability_md(res["availability"]) + walkforward_md(res["wf"], cfg)
                     + scores_md(res["scores"], res["adoption"], res["enc_drop_one"], cfg) + live_md(res["live_table"], res["live"], res))
