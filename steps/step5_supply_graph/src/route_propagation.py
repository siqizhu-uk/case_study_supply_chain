"""Step 5e — route-level propagation through the graph: step 7c's CH ("chain as reasoned") by route (decision G26).

CH today (steps/step7_forecast/src/chain_forecast.py) feeds ONE demand series D (Logitech sell-out proxy) through ONE
flow-weighted kernel:
    slice YoY_t = m x sum_k kernel_k D_(t-k);   tilt_t = s_t x [rev_(t-4) x (1 + slice YoY_t) - guide_t]
CH-route splits the kernel by Logitech's first customer (the graph's paths through logitech > amazon / ingram / tdsynnex /
other_retail) and feeds each route its own demand D_r (route_demand.py); GN's paths stay on the aggregate D (GN discloses
no routes beyond its annual-report caps):
    slice YoY_t = m x [ sum_r M_r sum_k K_r,k D_r,(t-k)  +  M_gn sum_k K_gn,k D_(t-k) ]
M = each route's share of the kernel mass (brand share x 10-K share), K_r = the route's own kernel. Since
sum_r M_r K_r + M_gn K_gn = kernel (linear in the paths), D_r = D for every route gives CH exactly (shrink 0 test).
At horizon h a lag k < h reads D(t-h) (persistence), as supply_graph.propagate does without `ahead`; the graph (shares and
10-K weights, lag basis from config) is the one known at step 6's origin date. Everything is point in time.
"""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

from route_demand import demand_wide, route_demand_asof, total_demand
from supply_graph import edge_shares, effective_ranges, kernel, kernel_asof, load_edges, paths, propagate


def origin_date(t: pd.Period, h: int) -> pd.Timestamp:
    """Step 6's origin date for target t at horizon h (walkforward.design: the day before Nordic reports t-h+1)."""
    return (t - h + 1).start_time + pd.Timedelta(days=20)


def _ranges(cfg: dict):
    """effective_ranges on the config's lag basis where supply_graph supports one (physical when it does not)."""
    if "basis" in inspect.signature(effective_ranges).parameters:
        return effective_ranges(load_edges(), cfg, cfg["supply_graph"].get("lag_basis", "physical"))
    return effective_ranges(load_edges(), cfg)


def route_kernels(date, cfg: dict, scenario: str = "mid") -> dict:
    """{'kernels': {route: Series}, 'mass': Series route -> share of kernel mass, 'lag_weeks': Series, 'check': float}.
    Routes: Logitech's first customer on the path; GN paths are one route 'gn'. `check` = max |sum_r M_r K_r - kernel_asof|."""
    e, prm = _ranges(cfg)
    params = {k: v[scenario] for k, v in prm.items()}
    pt = paths(e, edge_shares(e, cfg, date, params=params), cfg, lag_col=f"lag_weeks_{scenario}")
    route = pt["path"].str.extract(r"logitech > (\w+)")[0].where(pt["brand"] == "logitech", pt["brand"])
    groups = dict(tuple(pt.assign(route=route).groupby("route")))
    kern = {r: kernel(g, cfg) for r, g in groups.items()}
    w = pd.Series({r: g["weight"].sum() for r, g in groups.items()})
    mass = w / w.sum()
    lag = pd.Series({r: float(np.average(g["lag_weeks"], weights=g["weight"])) for r, g in groups.items()})
    combined = sum(mass[r] * kern[r] for r in kern)
    check = float((combined - kernel_asof(date, cfg, scenario)).abs().max())
    return {"kernels": kern, "mass": mass, "lag_weeks": lag, "check": check}


def logitech_weights(rk: dict, cfg: dict) -> dict:
    """Deviation weights w_r = the Logitech routes' kernel masses, renormalised (= the 10-K shares known at the origin)."""
    m = rk["mass"].reindex(list(cfg["route_propagation"]["routes"]))
    return (m / m.sum()).to_dict()


def route_contributions(Dw: pd.DataFrame, total: pd.Series, rk: dict, t: pd.Period, h: int) -> dict:
    """Each route's contribution M_r sum_k K_r,k D_r(t - max(k, h)) in YoY points; 'gn' reads the total."""
    out = {}
    for r, K in rk["kernels"].items():
        K = K[K > 0]
        D = total if r not in Dw else Dw[r]
        vals = np.array([D.get(t - max(int(k), h), np.nan) for k in K.index], dtype=float)
        out[r] = float(rk["mass"][r] * np.dot(K.values, vals)) if not np.isnan(vals).any() else np.nan
    return out


class _KernelCache:
    """route_kernels per origin date (the graph changes only at 10-K dates; the file reads are the cost)."""

    def __init__(self, cfg: dict):
        self.cfg, self.store = cfg, {}

    def __call__(self, date) -> dict:
        key = pd.Timestamp(date)
        if key not in self.store:
            self.store[key] = route_kernels(key, self.cfg)
        return self.store[key]


def route_slice_demand(total: pd.Series, proxies: pd.DataFrame, cfg: dict, t: pd.Period, h: int, kc=None,
                       shrink: float | None = None, method: str | None = None) -> dict:
    """Slice demand for target t at horizon h from the routes (reads nothing after t - h)."""
    kc = kc or _KernelCache(cfg)
    rk = kc(origin_date(t, h))
    long = route_demand_asof(total, proxies, cfg, t - h, logitech_weights(rk, cfg), shrink, method)
    contrib = route_contributions(demand_wide(long), total.loc[:t - h], rk, t, h)
    vals = list(contrib.values())
    g = float(np.sum(vals)) if not np.isnan(vals).any() else np.nan
    return {"slice_demand": g, "contrib": contrib, "long": long, "kernel_check": rk["check"]}


def aggregate_slice_demand(total: pd.Series, cfg: dict, h: int) -> pd.Series:
    """CH-aggregate's demand: supply_graph.propagate on the same total and origin (what step 6 GR / step 7c CH read)."""
    return propagate(total, cfg, h, lambda t: origin_date(t, h))


def ch_total(guide: float, share: float, rev_t4: float, m: float, g: float) -> float:
    """CH: guide + s x [rev(t-4) x (1 + m x g / 100) - guide] (step 7c)."""
    return guide + share * (rev_t4 * (1 + m * g / 100) - guide)


def targets(p: pd.DataFrame, cfg: dict, h: int) -> list[pd.Period]:
    """Step 6's walk-forward targets: from first_target, reported, with a guide for t (h=1) or t-1 (h=2)."""
    first = pd.Period(cfg["backtest"]["first_target"], "Q")
    return [q for q in p.index if q >= first and pd.notna(p["nordic_consumer_yoy"].get(q))
            and pd.notna(p["nordic_guide_mid"].get(q if h == 1 else q - 1, np.nan))]


def guide_rows(p: pd.DataFrame, cfg: dict, t: pd.Period, h: int) -> dict:
    """guide_total and GB_total (the guide-anchored benchmark) exactly as step 6's walk-forward computes them."""
    from walkforward import forecast_row            # steps/step6_backtest/src
    r = forecast_row(p, cfg, {}, t, h, cfg["backtest"]["exclude_supply_constrained_from_training"])
    gb_cons = r["cons_t4"] * (1 + r["GB_yoy"] / 100)
    return {"guide_total": float(r["guide_total"]), "GB_total": float(r["guide_total"] + gb_cons - r["guide_cons"])}


def target_row(p: pd.DataFrame, cfg: dict, t: pd.Period, h: int, ctx: dict, shrink=None, method=None) -> dict:
    """One target: route and aggregate slice demand, CH-route / CH-aggregate / GB totals, route contributions in pts and USD m."""
    rs = route_slice_demand(ctx["total"], ctx["proxies"], cfg, t, h, ctx["kc"], shrink, method)
    s, m, rev4 = float(ctx["share"][t]), ctx["m"], float(p.loc[t - 4, "nordic_rev"])
    gr = guide_rows(p, cfg, t, h)
    g_agg = float(ctx["agg"][h].get(t, np.nan))
    row = {"quarter": str(t), "horizon": h, "share": s, "rev_t4": rev4, **gr,
           "slice_demand_agg": g_agg, "slice_demand_route": rs["slice_demand"],
           "CH_agg_total": ch_total(gr["guide_total"], s, rev4, m, g_agg),
           "CH_route_total": ch_total(gr["guide_total"], s, rev4, m, rs["slice_demand"]),
           "slice_usdm_change_agg": s * rev4 * m * g_agg / 100, "slice_usdm_change_route": s * rev4 * m * rs["slice_demand"] / 100,
           "actual_total": float(p["nordic_rev"].get(t, np.nan)), "kernel_check": rs["kernel_check"]}
    same = route_contributions(pd.DataFrame(), ctx["total"].loc[:t - h], ctx["kc"](origin_date(t, h)), t, h)   # every route reads the total
    for r, v in rs["contrib"].items():
        row[f"pts_{r}"], row[f"usdm_{r}"], row[f"diff_pts_{r}"] = v, s * rev4 * m * v / 100, v - same[r]
    return row


def context(p: pd.DataFrame, cfg: dict, share: pd.Series, m: float, proxies: pd.DataFrame) -> dict:
    """Inputs shared by every target: total demand, proxies, kernel cache, share path, multiplier, aggregate demand by h."""
    total = total_demand(p, cfg)
    return {"total": total, "proxies": proxies, "kc": _KernelCache(cfg), "share": share, "m": m,
            "agg": {h: aggregate_slice_demand(total, cfg, h) for h in cfg["route_propagation"]["horizons"]}}


def walkforward(p: pd.DataFrame, cfg: dict, ctx: dict, h: int, shrink=None, method=None) -> pd.DataFrame:
    return pd.DataFrame([target_row(p, cfg, t, h, ctx, shrink, method) for t in targets(p, cfg, h)]).set_index("quarter")


def extend(p: pd.DataFrame, last: pd.Period) -> pd.DataFrame:
    """The panel with empty rows up to `last` (the live targets are not reported yet)."""
    return p.reindex(p.index.union(pd.period_range(p.index.min(), last, freq="Q")))
