"""Step 5e — route_propagation.md: reasoning first, then the tables and the computed sentences (decision G26)."""
from __future__ import annotations

import numpy as np
import pandas as pd

REASONING = """## Reasoning (decision G26, written before any score)

Step 7c's CH ("chain as reasoned") feeds one demand series, Logitech's sell-out proxy (sell-in YoY + disclosed sell-through
gap), through one flow-weighted kernel. The analyst's structural version goes route by route: route demand x route weight
(Logitech 10-K: Amazon, Ingram, TD Synnex, the residual 'other retail / resellers') -> each route's own lag -> attribution
share x slice multiplier -> Nordic slice revenue change.

- **The total stays Logitech's own number.** The route proxies are all-vendor and all-category (Amazon incl. AWS and ads;
  distributors incl. memory, servers and 2026 ASP inflation; CDW is B2B IT) and carry the common cycle. So they only
  ALLOCATE Logitech's sell-through across routes: D_r = total + shrink x sd(total) x (z_r - sum_r w_r z_r), z = each proxy
  standardised with its own mean and sd over the quarters known at the origin (min_obs quarters, else the route takes the
  total). sum_r w_r D_r = total exactly. Distributor dollars from 2026Q1 are cut by the configured ASP tailwind first.
- **Each route has its own kernel** (the graph's paths through that Logitech customer, lag basis from config, 10-K weights
  as filed by the origin). GN stays on the aggregate path: it discloses no routes beyond its annual-report caps.
- **Prior (what to expect).** With the total pinned, the split can only change CH through differences between the route
  kernels: sum_r M_r sum_k (K_r,k - K_k) dev_r(t-k). The routes' lags differ by a few weeks and all sit on lags 1-2, so at
  h=1 the split only re-weights t-1 against t-2, and at h=2 (every lag below h reads t-2) it cannot change anything. Any
  gain would have to come from mix divergence (e.g. 2026: distributors vs Amazon vs Best Buy) timed differently by route.
  Expected: small. The shrink is fixed at 1 before scoring; 0 (= CH-aggregate), 0.5 and 'demean' are reported, not selected.
"""

from route_vs_gr import sentences as vs_gr_sentences  # noqa: E402


def _f(x, fmt="{:+.1f}") -> str:
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else fmt.format(x)


def live_table(live: pd.DataFrame, ktab: pd.DataFrame) -> pd.DataFrame:
    """Route breakdown of each live target: kernel mass, lag, contribution (pts and USD m), re-allocation vs aggregate."""
    rows = []
    for q, r in live.iterrows():
        for route in ktab["route"]:
            k = ktab.set_index("route").loc[route]
            rows.append({"target": f"{q} (h={int(r['horizon'])})", "route": route, "kernel_mass": k["kernel_mass"],
                         "mean_lag_weeks": k["mean_lag_weeks"], "contribution_pts": r[f"pts_{route}"],
                         "vs_aggregate_pts": r[f"diff_pts_{route}"], "nordic_slice_usdm": r[f"usdm_{route}"]})
        rows.append({"target": f"{q} (h={int(r['horizon'])})", "route": "TOTAL slice (routes | aggregate)",
                     "contribution_pts": r["slice_demand_route"], "vs_aggregate_pts": r["slice_demand_route"] - r["slice_demand_agg"],
                     "nordic_slice_usdm": r["slice_usdm_change_route"]})
    return pd.DataFrame(rows)


def verdict(s: pd.DataFrame, h: int, t_min: float) -> str:
    r = s[(s["horizon"] == h) & (s["model"] == "CH-route")].iloc[0]
    if not np.isfinite(r["enc_t_vs_CH_agg"]):
        return "identical to CH-aggregate on every quarter (no route information can reach this horizon)"
    helps = r["enc_t_vs_CH_agg"] >= t_min and r["rmse_ratio_vs_CH_agg"] < 1
    return ("helps: " if helps else "no measurable help: ") + (
        f"encompassing of the route increment over CH-aggregate beta {_f(r['enc_beta_vs_CH_agg'], '{:+.2f}')} "
        f"(t {_f(r['enc_t_vs_CH_agg'])}, bar {t_min:.1f}), RMSE ratio {r['rmse_ratio_vs_CH_agg']:.3f}")


def sentences(res: dict, cfg: dict, ktab: pd.DataFrame) -> list[str]:
    s, t_min = res["scores"], cfg["chain_forecast"]["weight_t_min"]
    lag_cols = [c for c in ktab if c.startswith("lag ")]
    support = [c for c in lag_cols if (ktab[c] > 0).any()]
    out = [f"1. **Structure.** Route mean lags {ktab['mean_lag_weeks'].min():.1f}-{ktab['mean_lag_weeks'].max():.1f} weeks; "
           f"all route kernel weight sits on {', '.join(support)}. Largest walk-forward gap CH-route minus CH-aggregate: "
           + "; ".join(f"h={h} {s[(s['horizon'] == h) & (s['model'] == 'CH-route')]['max_abs_gap_vs_CH_agg_usdm'].iloc[0]:.2f}m"
                       for h in res["runs"]) + "."]
    for h in res["runs"]:
        g = s[s["horizon"] == h].set_index("model")
        out.append(f"{len(out) + 1}. **h={h}.** RMSE CH-route {g.loc['CH-route', 'rmse_usdm']:.1f}m, CH-aggregate "
                   f"{g.loc['CH-aggregate', 'rmse_usdm']:.1f}m, GB {g.loc['GB (guide-anchored)', 'rmse_usdm']:.1f}m "
                   f"({int(g.loc['CH-route', 'n'])} quarters); CH-route vs GB encompassing beta {_f(g.loc['CH-route', 'enc_beta_vs_GB'], '{:+.2f}')} "
                   f"(t {_f(g.loc['CH-route', 'enc_t_vs_GB'])}). Route split: {verdict(s, h, t_min)}.")
    for lab in sorted({m[len("CH-route ("):-1] for m in s["model"] if m.startswith("CH-route (basis ")}):
        parts = [f"h={h} max gap {r['max_abs_gap_vs_CH_agg_usdm']:.2f}m, route-increment t {_f(r['enc_t_vs_CH_agg'])}"
                 for h in res["runs"] for _, r in s[(s["horizon"] == h) & (s["model"] == f"CH-route ({lab})")].iterrows()]
        out.append(f"{len(out) + 1}. **Sensitivity, {lab} lags** (each basis against its own CH-aggregate): {'; '.join(parts)}.")
    d = res["divergence"]
    d1 = d[d["horizon"] == min(res["runs"])]
    out.append(f"{len(out) + 1}. **Where the routes diverged most** (h={min(res['runs'])}, top {len(d1)}): the split was closer to the actual in "
               f"{int(d1['route_split_helped'].sum())} of {len(d1)} quarters, by at most {d1['gap_route_minus_agg_usdm'].abs().max():.2f}m; "
               f"drivers: {', '.join(f'{k} {v}x' for k, v in d1['driver_route'].value_counts().items())}.")
    for q, r in res["live"].iterrows():
        diffs = {c.replace("diff_pts_", ""): r[c] for c in r.index if c.startswith("diff_pts_")}
        big = max(diffs, key=lambda k: abs(diffs[k]))
        out.append(f"{len(out) + 1}. **Live {q} (h={int(r['horizon'])}).** Slice demand {r['slice_demand_route']:+.2f}% by routes vs "
                   f"{r['slice_demand_agg']:+.2f}% aggregate -> Nordic slice {r['slice_usdm_change_route']:+.2f}m YoY; CH-route "
                   f"{r['CH_route_total']:.1f}m vs CH-aggregate {r['CH_agg_total']:.1f}m (GB {r['GB_total']:.1f}m). Largest re-allocation: "
                   f"{big} {diffs[big]:+.2f} pts of slice demand, offset by the other routes.")
    return out


def report_md(res: dict, cfg: dict, ktab: pd.DataFrame) -> str:
    c, v = res["checks"], res["vintage"]
    recent = v[v["quarter"] >= str(pd.Period(v["origin"].iloc[0], "Q") - 5)]
    dev = recent.pivot(index="quarter", columns="route", values="deviation")
    return "\n".join([
        "# Step 5e — Route-level propagation (CH by route)\n", REASONING,
        "## Route proxies (data already in the repo)\n", res["coverage"].to_markdown(index=False), "",
        "## Route kernels at the live origin\n", ktab.round(3).to_markdown(index=False), "",
        f"Checks: reconciliation max |sum_r w_r D_r - total| = {c['reconciliation_max_pts']:.1e} pts; shrink 0 vs CH-aggregate max gap "
        f"{c['shrink0_max_gap_usdm']:.1e} USD m; route kernels vs `kernel_asof` max gap {c['kernel_check_max']:.1e}.\n",
        "## Key results (computed)\n", "\n".join(sentences(res, cfg, ktab)), "",
        "## Live targets: route breakdown\n", live_table(res["live"], ktab).round(2).to_markdown(index=False), "",
        f"Route deviations in the live vintage (YoY pts of Logitech sell-through; origin {v['origin'].iloc[0]}):\n",
        dev.round(1).to_markdown(), "",
        "## Walk-forward scores (same quarters, same guide, same origin as step 6 / 7c)\n",
        res["scores"].round(3).to_markdown(index=False), "",
        "## Against GR (step 6), same quarters (`route_vs_gr.csv`)\n",
        res["vs_gr"].round(2).to_markdown(index=False), "", "\n".join(vs_gr_sentences(res["vs_gr"])), "",
        "## Quarters where the routes diverged most\n", res["divergence"].round(2).to_markdown(index=False), "",
        "## What this cannot tell\n",
        "- The proxies are all-vendor: a deviation says Amazon (or distributors) grew faster than retail overall, not that "
        "Logitech's units on that route did. Logitech discloses no sell-through by customer.\n"
        "- The 10-K route weights are annual and gross-sales based; the residual 'other retail' (~56%) mixes direct retail, "
        "resellers and smaller distributors (G20).\n"
        "- Not built: route-specific content or multipliers (no evidence Nordic content differs by route); route levels in "
        "place of Logitech's total (would import the all-vendor cycle).\n"])
