"""Step 5e: route-level CH against step 6's GR on identical walk-forward quarters (analyst request 2026-09-27).

GR (graph-timed single-slope regression, step 6 walkforward.py) is re-run here from the same panel and config, so the
comparison never reads a stale step-6 output. Scores per horizon on the quarters where CH-route, CH-aggregate, GR, GB and
the actual all exist; pairwise encompassing both ways between CH-route and GR (does one add to the other?).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MODELS = {"CH_route_total": "CH-route", "CH_agg_total": "CH-aggregate", "GR_total": "GR (step 6)", "GB_total": "GB (guide-anchored)"}


def _q(idx) -> pd.Index:
    return pd.Index([str(q) for q in idx])


def gr_walkforward(p: pd.DataFrame, cfg: dict, h: int) -> pd.Series:
    """GR's Nordic total per target quarter, exactly as step 6 computes it (no time-varying driver: GR does not use one)."""
    from walkforward import walk_forward                    # steps/step6_backtest/src
    wf = walk_forward(p, cfg, None, h=h)
    q = wf["quarter"] if "quarter" in wf else wf.index
    return pd.Series(wf["GR_total"].values, index=_q(q), name="GR_total")


def _enc(model: pd.Series, bench: pd.Series, actual: pd.Series, t_min: float) -> dict:
    from chain_forecast import encompassing_weight         # steps/step7_forecast/src (read only)
    return encompassing_weight(model - bench, actual, bench, t_min)


def compare(runs: dict, p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """One row per horizon x model on common quarters, plus the CH-route <-> GR encompassing betas."""
    t_min = cfg["chain_forecast"]["weight_t_min"]
    rows = []
    for h, byvar in runs.items():
        m = byvar["main"].copy()
        m.index = _q(m.index)
        d = m.join(gr_walkforward(p, cfg, int(h)), how="inner").dropna(subset=list(MODELS) + ["actual_total"])
        if d.empty:
            continue
        a = d["actual_total"]
        ch_on_gr, gr_on_ch = _enc(d["CH_route_total"], d["GR_total"], a, t_min), _enc(d["GR_total"], d["CH_route_total"], a, t_min)
        for col, label in MODELS.items():
            e = d[col] - a
            rows.append({"horizon": int(h), "model": label, "n": len(d), "first": d.index.min(), "last": d.index.max(),
                         "rmse_usdm": float(np.sqrt((e ** 2).mean())), "bias_usdm": float(e.mean()),
                         "rmse_ratio_vs_GR": float(np.sqrt((e ** 2).mean()) / np.sqrt(((d["GR_total"] - a) ** 2).mean()))})
        rows.append({"horizon": int(h), "model": "encompassing: CH-route adds to GR", "n": len(d),
                     "beta": ch_on_gr["beta"], "t": ch_on_gr["t"]})
        rows.append({"horizon": int(h), "model": "encompassing: GR adds to CH-route", "n": len(d),
                     "beta": gr_on_ch["beta"], "t": gr_on_ch["t"]})
    return pd.DataFrame(rows)


def sentences(v: pd.DataFrame) -> list[str]:
    """Computed reading, one line per horizon."""
    out = []
    for h, g in v.groupby("horizon"):
        r = g.set_index("model")
        best = r.loc[list(MODELS.values()), "rmse_usdm"].idxmin()
        c, gr = r.loc["encompassing: CH-route adds to GR"], r.loc["encompassing: GR adds to CH-route"]
        out.append(f"- h={h} ({int(r.loc['GR (step 6)', 'n'])} quarters {r.loc['GR (step 6)', 'first']}–{r.loc['GR (step 6)', 'last']}): "
                   f"RMSE CH-route {r.loc['CH-route', 'rmse_usdm']:.1f}, GR {r.loc['GR (step 6)', 'rmse_usdm']:.1f}, "
                   f"GB {r.loc['GB (guide-anchored)', 'rmse_usdm']:.1f} USD m; lowest: {best}. CH-route adds to GR: beta "
                   f"{c['beta']:+.2f} (t {c['t']:+.1f}); GR adds to CH-route: beta {gr['beta']:+.2f} (t {gr['t']:+.1f}).")
    return out
