"""Step 5e — run, score and write the route-level propagation (decision G26).

Run by supply_graph_report.run_step5 (scripts/run_all.py, after steps 2 and 3 have written the share path and the slice
multiplier), or alone:  python steps/step5_supply_graph/src/route_propagation_report.py

Outputs (steps/step5_supply_graph/outputs/): route_demand.csv (the live vintage: route x quarter), route_propagation.csv
(walk-forward and live rows: route contributions, Nordic slice change, CH-route / CH-aggregate / GB totals),
route_propagation_scores.csv (walk-forward), route_propagation.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":                              # CLI: make core and the step folders importable
    _R = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(_R)] + [str(s) for s in sorted((_R / "steps").glob("step*/src"))]

from core.config import ROOT, step_outputs  # noqa: E402

SHARE_PATH = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"
MODELS = {"CH_route_total": "CH-route", "CH_agg_total": "CH-aggregate", "GB_total": "GB (guide-anchored)"}


def inputs(p: pd.DataFrame, cfg: dict, path: pd.DataFrame | None = None) -> dict:
    """Share path (step 2), slice multiplier (step 3), proxies, on the panel extended to the live targets."""
    from attribution_path import share_series       # steps/step2_attribution/src
    from chain_forecast import slice_multiplier     # steps/step7_forecast/src (read only)
    from route_demand import load_route_proxies
    from route_propagation import context, extend
    last = max(pd.Period(q, "Q") for q in cfg["route_propagation"]["live_targets"].values())
    pe = extend(p, last)
    path = pd.read_csv(SHARE_PATH) if path is None else path
    share = share_series(path, pe) / 100
    m, _ = slice_multiplier(cfg)
    return {"pe": pe, "ctx": context(pe, cfg, share, m, load_route_proxies(p, pe.index)), "m": m}


def _enc(model: pd.Series, bench: pd.Series, actual: pd.Series, t_min: float) -> dict:
    from chain_forecast import encompassing_weight
    return encompassing_weight(model - bench, actual, bench, t_min)


def score(wf: pd.DataFrame, col: str, label: str, idx: pd.Index, t_min: float) -> dict:
    """RMSE / MAE / bias (model - actual) and encompassing vs GB and vs CH-aggregate, on the common quarters idx."""
    d = wf.loc[idx]
    e = d[col] - d["actual_total"]
    gb, ch = _enc(d[col], d["GB_total"], d["actual_total"], t_min), _enc(d[col], d["CH_agg_total"], d["actual_total"], t_min)
    rm = lambda x: float(np.sqrt((x ** 2).mean()))           # noqa: E731
    return {"model": label, "n": len(d), "rmse_usdm": rm(e), "mae_usdm": float(e.abs().mean()), "bias_usdm": float(e.mean()),
            "rmse_ratio_vs_GB": rm(e) / rm(d["GB_total"] - d["actual_total"]),
            "rmse_ratio_vs_CH_agg": rm(e) / rm(d["CH_agg_total"] - d["actual_total"]),
            "enc_beta_vs_GB": gb["beta"], "enc_t_vs_GB": gb["t"], "enc_beta_vs_CH_agg": ch["beta"], "enc_t_vs_CH_agg": ch["t"],
            "max_abs_gap_vs_CH_agg_usdm": float((d[col] - d["CH_agg_total"]).abs().max())}


def scores(runs: dict, cfg: dict) -> pd.DataFrame:
    """One row per horizon x model; every variant on the same quarters as the main run."""
    t_min = cfg["chain_forecast"]["weight_t_min"]
    rows = []
    for h, byvar in runs.items():
        main = byvar["main"]
        idx = main.dropna(subset=["CH_route_total", "CH_agg_total", "GB_total", "actual_total"]).index
        for col, label in MODELS.items():
            rows.append({"horizon": h, **score(main, col, label, idx, t_min)})
        for lab, wf in byvar.items():
            if lab != "main":
                rows.append({"horizon": h, **score(wf, "CH_route_total", f"CH-route ({lab})", idx, t_min)})
            if lab.startswith("basis "):                    # the other lag basis has its own aggregate CH
                rows.append({"horizon": h, **score(wf, "CH_agg_total", f"CH-aggregate ({lab})", idx, t_min)})
    return pd.DataFrame(rows)


def other_bases(pe: pd.DataFrame, cfg: dict, ctx: dict) -> dict:
    """Sensitivity: the main run on every other lag basis supply_graph offers (G25: physical / signal); cfg is copied."""
    import supply_graph
    from route_propagation import context, walkforward
    own = cfg["supply_graph"].get("lag_basis", "physical")
    out = {}
    for basis in (b for b in getattr(supply_graph, "LAG_BASES", ()) if b != own):
        cb = {**cfg, "supply_graph": {**cfg["supply_graph"], "lag_basis": basis}}
        cx = context(pe, cb, ctx["share"], ctx["m"], ctx["proxies"])
        out[f"basis {basis}"] = {h: walkforward(pe, cb, cx, h) for h in cfg["route_propagation"]["horizons"]}
    return out


def divergence(runs: dict, cfg: dict) -> pd.DataFrame:
    """Quarters where CH-route and CH-aggregate differ most; which route drove the gap; did the route split help there."""
    n, rows = cfg["route_propagation"]["divergence_top_n"], []
    for h, byvar in runs.items():
        w = byvar["main"].dropna(subset=["CH_route_total", "CH_agg_total", "actual_total"])
        gap = (w["CH_route_total"] - w["CH_agg_total"])
        diff_cols = [c for c in w if c.startswith("diff_pts_")]
        for q in gap.abs().sort_values(ascending=False).index[:n]:
            r = w.loc[q]
            drv = max(diff_cols, key=lambda c: abs(r[c]))
            rows.append({"horizon": h, "quarter": q, "gap_route_minus_agg_usdm": gap[q], "err_route_usdm": r["CH_route_total"] - r["actual_total"],
                         "err_agg_usdm": r["CH_agg_total"] - r["actual_total"],
                         "route_split_helped": bool(abs(r["CH_route_total"] - r["actual_total"]) < abs(r["CH_agg_total"] - r["actual_total"])),
                         "driver_route": drv.replace("diff_pts_", ""), "driver_pts": r[drv]})
    return pd.DataFrame(rows)


def run_routes(p: pd.DataFrame, cfg: dict, path: pd.DataFrame | None = None) -> dict:
    """Walk-forward (main + sensitivity + shrink 0), live rows, the live route-demand vintage, scores."""
    from route_propagation import route_slice_demand, target_row, walkforward
    rc = cfg["route_propagation"]
    I = inputs(p, cfg, path)
    pe, ctx = I["pe"], I["ctx"]
    runs = {h: {"main": walkforward(pe, cfg, ctx, h)} for h in rc["horizons"]}
    for h in rc["horizons"]:
        for s in rc["sensitivity"]:
            runs[h][s["label"]] = walkforward(pe, cfg, ctx, h, s["shrink"], s["standardise"])
    for lab, byh in other_bases(pe, cfg, ctx).items():
        for h, wf in byh.items():
            runs[h][lab] = wf
    zero = {h: walkforward(pe, cfg, ctx, h, 0.0) for h in rc["horizons"]}
    live = pd.DataFrame([target_row(pe, cfg, pd.Period(q, "Q"), int(h), ctx) for h, q in rc["live_targets"].items()]).set_index("quarter")
    h0, q0 = next(iter(rc["live_targets"].items()))
    vint = route_slice_demand(ctx["total"], ctx["proxies"], cfg, pd.Period(q0, "Q"), int(h0), ctx["kc"])["long"]
    from route_demand import coverage, reconciliation_error
    checks = {"shrink0_max_gap_usdm": max(float((z["CH_route_total"] - z["CH_agg_total"]).abs().max()) for z in zero.values()),
              "reconciliation_max_pts": reconciliation_error(vint),
              "kernel_check_max": float(max(w["main"]["kernel_check"].max() for w in runs.values()))}
    from route_vs_gr import compare
    return {"runs": runs, "live": live, "vintage": vint, "scores": scores(runs, cfg), "divergence": divergence(runs, cfg),
            "vs_gr": compare(runs, p, cfg),
            "coverage": coverage(ctx["proxies"], cfg), "checks": checks, "m": I["m"], "kc": ctx["kc"]}


def kernel_table(res: dict, cfg: dict) -> pd.DataFrame:
    """Route masses, mean lags and kernels at the live origin."""
    from route_propagation import origin_date
    h, q = next(iter(cfg["route_propagation"]["live_targets"].items()))
    rk = res["kc"](origin_date(pd.Period(q, "Q"), int(h)))
    k = pd.DataFrame(rk["kernels"]).T
    k.columns = [f"lag {c}q" for c in k.columns]
    return pd.concat([rk["mass"].rename("kernel_mass"), rk["lag_weeks"].rename("mean_lag_weeks"), k], axis=1).rename_axis("route").reset_index()


def write(res: dict, cfg: dict) -> dict:
    from route_propagation_md import report_md
    d = step_outputs("step5_supply_graph")
    out = {"route_demand": d / "route_demand.csv", "route_propagation": d / "route_propagation.csv",
           "scores": d / "route_propagation_scores.csv", "md": d / "route_propagation.md"}
    res["vintage"].round(3).to_csv(out["route_demand"], index=False)
    wf = pd.concat([res["runs"][h]["main"].assign(kind="walkforward") for h in res["runs"]] + [res["live"].assign(kind="live")])
    wf.round(3).to_csv(out["route_propagation"])
    res["scores"].round(3).to_csv(out["scores"], index=False)
    res["vs_gr"].round(3).to_csv(step_outputs("step5_supply_graph") / "route_vs_gr.csv", index=False)
    out["md"].write_text(report_md(res, cfg, kernel_table(res, cfg)))
    return out


def run_route_propagation(p: pd.DataFrame, cfg: dict, path: pd.DataFrame | None = None, write_files: bool = True) -> dict:
    res = run_routes(p, cfg, path)
    if write_files:
        res["paths"] = write(res, cfg)
    return res


if __name__ == "__main__":
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    _cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    _res = run_route_propagation(build_panel(load_all(), _cfg), _cfg)
    print(_res["scores"].round(2).to_string(index=False))
    print(_res["checks"])
    print("\n".join(str(Path(v)) for v in _res["paths"].values()))
