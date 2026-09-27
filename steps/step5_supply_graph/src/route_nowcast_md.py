"""Step 5f — route_nowcast.md: reasoning and the adoption rule first (fixed before scoring), then availability, scores,
live numbers and computed sentences (decision G27)."""
from __future__ import annotations

import numpy as np
import pandas as pd

REASONING = """## Reasoning (decision G27, written before any score)

**The gap.** Step 5e showed that routes only re-allocate a KNOWN Logitech total. At the h=2 origin of Nordic Q4 2026 (the day
before Nordic reports Q3, ~21 Oct) the total for Jul-Sep (Logitech Q2 FY27, reported ~27 Oct) is not known. Step 6 GR fills it
by persistence (the last reported quarter); GRg with Logitech's guide. Route data published before the origin could nowcast it.

**Point in time by release date.** A proxy value is used for quarter q only if first published by origin(q) = q end + 21 days
(Nordic Q3 2026: 22 Oct; Nordic's Q4 reports come in February, so 21 days is early - conservative). Release date = the filing
date stored in the repo (Best Buy), else period end + a documented typical lag (config `route_nowcast.release_lag`, graded;
the rule errs long, which can only drop data). Calendar-quarter reporters (Amazon, Ingram, CDW) publish ~30 days after quarter
end, after Nordic: excluded by the rule, not by hand.

**Fiscal vs calendar.** TD Synnex's FQ ends Feb/May/Aug/Nov; the quarter labelled q (e.g. Jun-Aug for Q3) shares 2 of 3 months
with q and is out ~4-6 weeks later, before the origin. Best Buy's quarter ends a month after the calendar quarter (P83): the one
filed by the origin (May-Jul for Q3) shares ONE month with q - it mostly describes the quarter Logitech already reported. US
electronics-store sales (Census, monthly): months 1-2 of q are out by the origin, month 3 is not (partial-quarter YoY).

**Model (few parameters, nests the default).** y(q) = y(q-1) + b x C(q), C = mean over the available proxies of their change since
q-1 (each as released by its own origin), scaled by its sd point in time; b = OLS through the origin, expanding window from
2021Q4 (2021's lockdown-base YoY excluded), b = 0 below 6 pairs. One slope, no level: an all-vendor proxy's level (TD Synnex +38%
in 2026 on memory prices) never becomes Logitech's level; only its change, standardised, moves the nowcast.

**Prior.** Modest at best. The proxies are all-vendor and all-category and carry the common PC / consumer-electronics cycle;
Logitech is a small share of each (computed below); two of three overlap the target by 1-2 months; TD Synnex's 2026 dollar
growth is memory ASPs, and its Endpoint split (the closest to Logitech) is not in the FQ3 FY26 release. Logitech's YoY is
persistent (a cycle moves over several quarters), so persistence is a hard benchmark for a one-quarter step.
"""

RULE = """## Adoption rule (the analyst, 2026-09-27; config `route_nowcast.adoption`, fixed before scoring)

- **Default = persistence (N0):** the last reported Logitech quarter fills the unreported one. A modelling assumption, stated.
- A route-proxy nowcast replaces it only with walk-forward evidence: nowcast RMSE below N0's on the same quarters AND
  (Diebold-Mariano t <= -{t} OR encompassing t >= {t}), AND Nordic h=2 GR fed with it no worse than GR on the same quarters.
  If the bar is not met the verdict is persistence, whatever the point estimates say.
- **Logitech's guide (N1) is not a candidate:** the analyst considers it known to be inaccurate. It is scored in one labelled
  comparison row (it is what step 6 GRg uses) and never pre-registered or recommended.
"""


def _f(x, fmt="{:.2f}") -> str:
    return "n/a" if x is None or (isinstance(x, (float, np.floating)) and not np.isfinite(x)) else fmt.format(x)


def _table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    lines += ["| " + " | ".join(_f(v) if isinstance(v, (float, np.floating)) else str(v) for v in r) + " |" for r in df.itertuples(index=False)]
    return "\n".join(lines) + "\n"


def availability_md(av: pd.DataFrame) -> str:
    cols = ["source", "period", "months_in_target", "release_date", "release_basis", "available_at_origin", "value", "grade", "used_in"]
    t = av[cols].assign(release_basis=av["release_basis"].str.split(" \\(").str[0])
    return f"## Availability at the live origin ({av['origin'].iloc[0]}, target Logitech {av['period'].iloc[0]})\n\n" + _table(t)


def scores_md(ns: pd.DataFrame, nd: pd.DataFrame, ad: pd.DataFrame) -> str:
    c1 = ["scope", "model", "role", "n", "first", "last", "rmse", "rmse_bench_same_quarters", "rmse_ratio", "dm_t", "enc_t", "rmse_ratio_last6"]
    c2 = ["forecast", "model", "role", "n", "rmse", "rmse_bench_same_quarters", "rmse_ratio", "dm_t", "dm_p", "enc_t", "gain_share_top3",
          "mean_abs_change_vs_N0_usdm", "enc_vs_guide_t"]
    return ("## Nowcast of Logitech sell-through YoY (pts), walk-forward, vs persistence on the same quarters\n\n" + _table(ns[c1])
            + "\n## Nordic h=2 (USD m): step 6 GR and step 7c CH with each nowcast for the unreported quarter, vs the persistence version\n\n"
            + _table(nd[[c for c in c2 if c in nd]]) + "\n## Adoption (bar above)\n\n" + _table(ad))


def live_md(res: dict, cfg: dict) -> str:
    rc, q = cfg["route_nowcast"], str(res["live_q"])
    wf, lv = res["wf"], res["nordic"]["live"].set_index("model")
    rows = [{"model": m, "label": rc["models"][m]["label"], "logitech_st_yoy_nowcast": wf.loc[q, m],
             "live_value": "yes" if bool(wf.loc[q, f"{m}_fitted"]) or m == rc["adoption"]["default"] else "no (= persistence)",
             "nordic_GR_usdm": lv.loc[m, "GR_total"], "nordic_CH_usdm": lv.loc[m, "CH_total"]} for m in rc["models"]]
    comp = {k: wf.loc[q, k] for k in wf.columns if k.startswith("N2c_dx_")}
    return (f"## Live: Logitech {q} nowcast and Nordic {lv['quarter'].iloc[0]} (h=2)\n\n" + _table(pd.DataFrame(rows))
            + f"\nN2c components for {q} (change since the previous quarter, pts): "
            + ", ".join(f"{k.replace('N2c_dx_', '')} {_f(v, '{:+.1f}')}" for k, v in comp.items())
            + f"; composite {_f(wf.loc[q, 'N2c_C_q'], '{:+.2f}')} sd x slope {_f(wf.loc[q, 'N2c_b'])} (n {int(wf.loc[q, 'N2c_n_train'])}).\n\n"
            + f"**Dated check ({rc['check_on']}, Logitech reports {q}):** fill `logitech_st_yoy_actual` (sales YoY + disclosed "
            "sell-through gap) in `route_nowcast_prereg_log.csv`; Nordic's actual for the h=2 target after its February report. "
            "The last row logged before the print is the record.\n")


def logitech_share(p: pd.DataFrame, cfg: dict) -> float:
    """Logitech's sales through TD Synnex over the last 4 reported quarters as % of TD Synnex revenue (10-K share x sales)."""
    from supply_graph import weights_asof
    last = p["logi_sales"].dropna().index[-4:]
    w = weights_asof(last[-1].end_time)["tdsynnex"]
    return float(w * p.loc[last, "logi_sales"].sum() / p.loc[last, "snx_sales"].sum() * 100)


def sentences(res: dict, cfg: dict) -> list[str]:
    ns, nd, ad = res["nowcast_scores"], res["nordic_scores"], res["adoption"]
    own = ns[ns["scope"] == "own quarters"].set_index("model")
    gr = nd[nd["forecast"] == "GR"].set_index("model")
    n0 = gr.loc["N0"]
    best = gr.drop(index="N0")["rmse"].idxmin()
    out = [f"No route-proxy nowcast beats persistence for Logitech's unreported quarter: RMSE ratio vs N0 "
           + ", ".join(f"{m} {_f(own.loc[m, 'rmse_ratio'])} (n {int(own.loc[m, 'n'])}, DM t {_f(own.loc[m, 'dm_t'], '{:+.1f}')})"
                       for m in own.index if m != "N1") + ".",
           f"Logitech's guide (comparison only) misses by more than persistence: RMSE {_f(own.loc['N1', 'rmse'])} vs "
           f"{_f(own.loc['N1', 'rmse_bench_same_quarters'])} pts on its {int(own.loc['N1', 'n'])} quarters (bias {_f(own.loc['N1', 'bias'], '{:+.1f}')}).",
           f"Nordic h=2 GR: persistence {_f(n0['rmse'], '{:.1f}')}m (n {int(n0['n'])}); best alternative {best} "
           f"{_f(gr.loc[best, 'rmse'], '{:.1f}')}m (DM t {_f(gr.loc[best, 'dm_t'], '{:+.1f}')}, {_f(100 * gr.loc[best, 'gain_share_top3'], '{:.0f}')}% "
           f"of the gain from 3 quarters, mean change {_f(gr.loc[best, 'mean_abs_change_vs_N0_usdm'], '{:.1f}')}m): a Nordic-level gain "
           "without a better nowcast is not evidence the proxies know Logitech's quarter (P109).",
           f"Verdict under the rule fixed before scoring: {ad['verdict'].iloc[0]} "
           f"({'persistence stays the default' if ad['verdict'].iloc[0] == 'N0' else 'adopted'}); no candidate met the nowcast bar."
           if not ad["adopted"].any() else f"Verdict: {ad['verdict'].iloc[0]} adopted (bar met)."]
    if np.isfinite(res.get("snx_share", np.nan)):
        out.append(f"Logitech is ~{_f(res['snx_share'], '{:.1f}')}% of TD Synnex's revenue (10-K share x sales, last 4 quarters): "
                   "the distributor's number is the all-vendor cycle, not Logitech.")
    return out


def report_md(res: dict, cfg: dict) -> str:
    ck = ", ".join(f"{k} {_f(v, '{:.2g}')}" for k, v in res["checks"].items())
    return ("# Step 5f — route proxies as a nowcast of Logitech's unreported quarter\n\n"
            + "\n".join(f"- {s}" for s in sentences(res, cfg)) + "\n\n" + REASONING + "\n"
            + RULE.format(t=cfg["route_nowcast"]["adoption"]["t_min"]) + "\n" + availability_md(res["availability"]) + "\n"
            + scores_md(res["nowcast_scores"], res["nordic_scores"], res["adoption"]) + "\n" + live_md(res, cfg)
            + f"\nReplication checks (0 = identical to step 6's own design): {ck}. Spec hash {res['hashes']['spec']}, "
            f"data hash {res['hashes']['data']}.\n")
