"""Step 5 — physical dwell vs order-signal lag, per edge and per route (decision G25, pitfalls P86 / P100).

signal lag = physical dwell (edge table, Little's-law capped) + the buyer's information delay (info_delay.py). The Monte
Carlo draws both parts on the SAME draws of the shares and physical lags (paired), and each planner once per draw (one
planner, e.g. Logitech's S&OP, sits on several edges and moves them together). The comparison with step 4's reasoned
lag and the data's near-optimal set is a consistency check, not a fit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from info_delay import edge_info, planner_ranges, planner_table, planners_of
from step4_check import stage_lags
from supply_graph import _physical_ranges, edge_shares, effective_ranges, mix_lags, paths, load_edges

SC = ("low", "mid", "high")
ROUTES = ("Amazon direct", "via Ingram / TD Synnex", "other retail direct", "all routes (flow-weighted)")


def route_of(path: str) -> str:
    n = path.split(" > ")
    if "ingram" in n or "tdsynnex" in n:
        return "via Ingram / TD Synnex"
    return "Amazon direct" if "amazon" in n else "other retail direct"


def route_means(pt: pd.DataFrame) -> dict:
    """Flow-weighted mean path lag per route (weeks)."""
    r = pt["path"].map(route_of)
    out = {k: float(np.average(pt.loc[r == k, "lag_weeks"], weights=pt.loc[r == k, "weight"])) for k in ROUTES[:-1] if (r == k).any()}
    return {**out, ROUTES[-1]: float(np.average(pt["lag_weeks"], weights=pt["weight"]))}


def _mixed_info(unmixed: pd.DataFrame, weeks: dict, params: dict) -> np.ndarray:
    """Info delay per edge for planner weeks `weeks`, with the lag mix (Logitech's 10-K residual) at `params`."""
    i = edge_info(unmixed, weeks)
    tmp = unmixed[["edge_id", "lag_mix"]].assign(**{f"lag_weeks_{s}": i for s in SC})
    return pd.to_numeric(mix_lags(tmp, params)["lag_weeks_mid"], errors="coerce").fillna(0).values


def _route_lags(e: pd.DataFrame, cfg: dict, date, params: dict, lags: np.ndarray) -> dict:
    pt = paths(e.assign(lag_weeks_mid=lags), edge_shares(e, cfg, date, params=params), cfg)
    return route_means(pt)


def edge_table(cfg: dict) -> pd.DataFrame:
    """Per edge: planner(s), physical / info / signal low-mid-high (effective ranges; E14 mixed)."""
    s, _ = effective_ranges(load_edges(), cfg, "signal")
    cols = [f"{c}_{x}" for c in ("physical_weeks", "info_weeks", "lag_weeks") for x in SC]
    t = s[["edge_id", "src", "dst", "brand", "info_delay_planner"] + cols].copy()
    t[cols] = t[cols].apply(pd.to_numeric, errors="coerce")
    return t.rename(columns={f"lag_weeks_{x}": f"signal_weeks_{x}" for x in SC}).dropna(subset=["physical_weeks_mid"])


def route_table(cfg: dict, date) -> pd.DataFrame:
    """Per route: physical and signal mean lag at the low / mid / high scenario (every edge and planner at that end), plus
    the smoothing-only variant of the signal (R/2 dropped, P100)."""
    raw = load_edges()
    un, prm = _physical_ranges(raw, cfg)
    rows = {}
    for sc in SC:
        p = {k: v[sc] for k, v in prm.items()}
        phys = mix_lags(un, prm)
        L = pd.to_numeric(phys[f"lag_weeks_{sc}"], errors="coerce").fillna(0).values
        wk = {k: v[sc] for k, v in planner_ranges(cfg).items()}
        I = _mixed_info(un, wk, {k: {x: v[sc] for x in SC} for k, v in prm.items()})
        rows[("physical", sc)] = _route_lags(phys, cfg, date, p, L)
        rows[("signal", sc)] = _route_lags(phys, cfg, date, p, L + I)
    p = {k: v["mid"] for k, v in prm.items()}
    phys = mix_lags(un, prm)
    L = pd.to_numeric(phys["lag_weeks_mid"], errors="coerce").fillna(0).values
    I0 = _mixed_info(un, {k: v["mid"] for k, v in planner_ranges(cfg, False).items()}, prm)
    rows[("signal, smoothing only", "mid")] = _route_lags(phys, cfg, date, p, L + I0)
    t = pd.DataFrame(rows).T
    t.index.names = ["basis", "scenario"]
    return t.reset_index()


def _tri(rng, a: float, m: float, b: float) -> float:
    return float(rng.triangular(a, m, b)) if b > a else m


def monte_carlo(cfg: dict, date, seed: int = 0) -> pd.DataFrame:
    """Paired draws: shares (triangular), physical lag per edge (triangular on its effective range), each planner's delay
    once per draw. Returns one row per draw with the route means on both bases."""
    rng = np.random.default_rng(seed)
    un, prm = _physical_ranges(load_edges(), cfg)
    phys = mix_lags(un, prm)
    lo, md, hi = (pd.to_numeric(phys[f"lag_weeks_{k}"], errors="coerce").fillna(0).values for k in SC)
    pr = planner_ranges(cfg)
    rows = []
    for i in range(cfg["supply_graph"]["mc_draws"]):
        p = {k: _tri(rng, v["low"], v["mid"], v["high"]) for k, v in prm.items()}
        L = np.array([_tri(rng, a, m, b) for a, m, b in zip(lo, md, hi)])
        I = _mixed_info(un, {k: _tri(rng, v["low"], v["mid"], v["high"]) for k, v in pr.items()},
                        {k: {x: v for x in SC} for k, v in p.items()})
        a, b = _route_lags(phys, cfg, date, p, L), _route_lags(phys, cfg, date, p, L + I)
        rows += [{"draw": i, "basis": "physical", **a}, {"draw": i, "basis": "signal", **b}]
    return pd.DataFrame(rows)


def mc_bands(draws: pd.DataFrame) -> pd.DataFrame:
    """p5 / p50 / p95 per basis and route, and the paired information-delay add-on (signal - physical)."""
    long = draws.melt(id_vars=["draw", "basis"], var_name="route", value_name="weeks")
    w = long.pivot_table(index=["draw", "route"], columns="basis", values="weeks").reset_index()
    add = w.assign(basis="info delay (signal - physical)", weeks=w["signal"] - w["physical"])[["draw", "route", "basis", "weeks"]]
    q = pd.concat([long, add]).groupby(["basis", "route"])["weeks"].quantile([0.05, 0.5, 0.95]).unstack()
    return q.rename(columns={0.05: "p5", 0.5: "p50", 0.95: "p95"}).reset_index()


def tornado(cfg: dict, date) -> pd.DataFrame:
    """Signal basis, flow-weighted mean lag: swing each planner (all its edges together) and each edge's physical lag from
    low to high, everything else at mid. Share swings are in graph_tornado.csv (they move both bases alike)."""
    un, prm = _physical_ranges(load_edges(), cfg)
    phys = mix_lags(un, prm)
    p = {k: v["mid"] for k, v in prm.items()}
    pr = planner_ranges(cfg)
    mid_w = {k: v["mid"] for k, v in pr.items()}
    L = pd.to_numeric(phys["lag_weeks_mid"], errors="coerce").fillna(0).values
    I = _mixed_info(un, mid_w, prm)
    all_ = ROUTES[-1]
    base = _route_lags(phys, cfg, date, p, L + I)[all_]
    rows = []
    for k, v in pr.items():
        a, b = (_route_lags(phys, cfg, date, p, L + _mixed_info(un, {**mid_w, k: v[x]}, prm))[all_] for x in ("low", "high"))
        n = sum(k in pl for pl in planners_of(un).values())
        rows.append({"input": f"info delay: {k} ({n} edges)", "grade": v["grade"], "low_weeks": a, "high_weeks": b})
    for i, r in enumerate(phys.itertuples()):
        lo_, hi_ = pd.to_numeric(pd.Series([r.lag_weeks_low, r.lag_weeks_high]), errors="coerce")
        if pd.isna(lo_) or lo_ == hi_:
            continue
        a, b = (_route_lags(phys, cfg, date, p, np.where(np.arange(len(L)) == i, x, L) + I)[all_] for x in (lo_, hi_))
        rows.append({"input": f"physical lag: {r.edge_id} {r.src}→{r.dst}", "grade": r.lag_grade, "low_weeks": a, "high_weeks": b})
    t = pd.DataFrame(rows).assign(base_weeks=base)
    return t.assign(swing_weeks=(t["high_weeks"] - t["low_weeks"]).abs()).sort_values("swing_weeks", ascending=False).reset_index(drop=True)


def stage_means(cfg: dict, date) -> pd.DataFrame:
    """Flow-weighted upstream (Nordic -> brand), downstream (brand -> consumer) and total weeks per basis, mid lags: the
    upstream segment is what a sell-in driver's lag measures (like with like, P86)."""
    rows = []
    for basis in ("physical", "signal"):
        e, prm = effective_ranges(load_edges(), cfg, basis)
        st = stage_lags(e, paths(e, edge_shares(e, cfg, date, params={k: v["mid"] for k, v in prm.items()}), cfg))
        up, down = (float(np.average(st[c], weights=st["weight"])) for c in ("upstream", "downstream"))
        rows.append({"basis": basis, "upstream_weeks": up, "downstream_weeks": down, "total_weeks": up + down})
    return pd.DataFrame(rows)


def run(cfg: dict, date, continuous: pd.DataFrame | None = None) -> dict:
    """All signal-lag tables for step 5; `continuous` = step 5's continuous-lag table (the data's near-optimal sets)."""
    draws = monte_carlo(cfg, date)
    return {"planners": planner_table(cfg), "edges": edge_table(cfg), "routes": route_table(cfg, date), "draws": draws,
            "mc": mc_bands(draws), "tornado": tornado(cfg, date), "stages": stage_means(cfg, date), "continuous": continuous}
