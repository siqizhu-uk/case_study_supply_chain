"""Step 5e — route-level end demand (decision G26): Logitech's own sell-through allocated across its 10-K routes.

For one forecast origin o (the last quarter known at the origin, t - h) and the routes r of config route_propagation.routes
(Logitech's first customers in the graph: amazon, ingram, tdsynnex, other_retail):

    z_r,q   = route proxy standardised with ITS OWN mean and sd over the quarters <= o   (point in time; one vintage per origin)
    dev_r,q = z_r,q - sum_(r available) w_r z_r,q / sum_(r available) w_r              (deviation from the weighted mean)
    D_r,q   = total_q + shrink x scale_o x dev_r,q                                     (route demand, YoY %)

total_q = Logitech sell-in YoY + disclosed sell-through gap (the same series as step 6 GR / step 7c CH); scale_o = sd of the
total over the quarters <= o (z units -> Logitech YoY points; 1 for 'demean' / 'none'). Because the deviations have a
w-weighted mean of zero, sum_r w_r D_r,q = total_q exactly (reconciliation): the proxies only ALLOCATE Logitech's number
across routes, they never replace it. A route whose proxy is missing in a quarter (or has fewer than min_obs quarters of
history at the origin) takes the total (deviation 0). Distributor dollars from asp_adjust_from are cut by
structural_breaks.distributor_asp_inflation_2026 before standardising (dollar growth overstates units).
Nothing after o is read: every input is sliced to <= o first.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"
XBRL = RAW / "inventory_detail_xbrl.csv"            # Amazon / CDW revenue (SEC XBRL, Pipeline A inventory_detail.py)
BESTBUY = RAW / "bestbuy_category_comps.csv"        # Best Buy Domestic Computing & Mobile comps (8-K Ex 99, Pipeline A)
XBRL_REVENUE = {"amazon_revenue_yoy": "amazon", "cdw_revenue_yoy": "cdw"}   # proxy name -> company in the XBRL file
BESTBUY_COLS = {"bestbuy_computing_comp": "computing_mobile_comp_pct"}


def _yoy(s: pd.Series) -> pd.Series:
    full = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq="Q"))
    return (full / full.shift(4) - 1) * 100


def load_route_proxies(p: pd.DataFrame, index: pd.PeriodIndex | None = None) -> pd.DataFrame:
    """Every route proxy on one quarterly index: panel columns (distributors, US electronics stores) plus Amazon / CDW
    revenue YoY (XBRL) and Best Buy's Computing & Mobile comps. Data already in the repo; nothing fetched."""
    idx = p.index if index is None else index
    x = pd.read_csv(XBRL)
    rev = x[x["metric"] == "revenue"].pivot(index="quarter", columns="company", values="value_usdm")
    rev.index = pd.PeriodIndex(rev.index, freq="Q")
    b = pd.read_csv(BESTBUY)
    b.index = pd.PeriodIndex(b["quarter"], freq="Q")
    cols = {name: _yoy(rev[co]).reindex(idx) for name, co in XBRL_REVENUE.items()}
    cols.update({name: b[c].reindex(idx) for name, c in BESTBUY_COLS.items()})
    panel_cols = [c for c in ("ingm_ces_yoy", "ingm_sales_yoy", "snx_endpoint_yoy", "rseas_yoy") if c in p]
    cols.update({c: p[c].reindex(idx) for c in panel_cols})
    return pd.DataFrame(cols, index=idx)


def total_demand(p: pd.DataFrame, cfg: dict) -> pd.Series:
    """Logitech's own sell-through YoY: the sum of the config columns (sell-in YoY + disclosed gap), as step 6 GR uses."""
    cols = cfg["route_propagation"]["total_demand"]
    return p[cols].sum(axis=1, min_count=len(cols)).rename("total")


def asp_adjusted(px: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Distributor dollar proxies minus the 2026 ASP tailwind (config structural_breaks), from asp_adjust_from on. New frame."""
    rc, sb = cfg["route_propagation"], cfg["structural_breaks"]["distributor_asp_inflation_2026"]
    if not sb.get("apply"):
        return px.copy()
    cols = [c for spec in rc["routes"].values() if spec.get("asp_adjust") for c in spec["proxies"] if c in px]
    mask = px.index >= pd.Period(rc["asp_adjust_from"], "Q")
    adj = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    adj.loc[mask, cols] = float(sb["asp_tailwind_pts"])
    return px - adj


def standardise(x: pd.Series, method: str, min_obs: int) -> pd.Series | None:
    """One component, on the quarters known at the origin; None if it has fewer than min_obs observations."""
    s = x.dropna()
    if len(s) < min_obs:
        return None
    if method == "zscore":
        sd = float(s.std(ddof=1))
        return (x - s.mean()) / sd if sd > 0 else None
    if method == "demean":
        return x - s.mean()
    if method == "none":
        return x.copy()
    raise ValueError(f"route_propagation.standardise must be zscore / demean / none, got {method!r}")


def route_signal(px: pd.DataFrame, spec: dict, method: str, min_obs: int) -> tuple[pd.Series, pd.Series]:
    """(standardised route signal, raw proxy) from the route's components: 'first' available or 'mean' of available."""
    comps = {c: standardise(px[c], method, min_obs) for c in spec["proxies"] if c in px}
    comps = {c: s for c, s in comps.items() if s is not None}
    if not comps:
        empty = pd.Series(np.nan, index=px.index)
        return empty, empty
    z, raw = pd.DataFrame(comps), px[list(comps)]
    if spec["combine"] == "first":
        return z.bfill(axis=1).iloc[:, 0], raw.bfill(axis=1).iloc[:, 0]
    if spec["combine"] == "mean":
        return z.mean(axis=1), raw.mean(axis=1)
    raise ValueError(f"route combine must be first / mean, got {spec['combine']!r}")


def route_demand_asof(total: pd.Series, proxies: pd.DataFrame, cfg: dict, origin: pd.Period, weights: dict,
                      shrink: float | None = None, method: str | None = None) -> pd.DataFrame:
    """Route demand for every quarter <= origin, as known at the origin (long frame: quarter x route)."""
    rc = cfg["route_propagation"]
    shrink = float(rc["deviation_shrink"] if shrink is None else shrink)
    method = method or rc["standardise"]
    tot = total.loc[:origin]
    px = asp_adjusted(proxies.loc[:origin], cfg)
    sig = {r: route_signal(px, spec, method, int(rc["min_obs"])) for r, spec in rc["routes"].items()}
    S = pd.DataFrame({r: s[0] for r, s in sig.items()}).reindex(tot.index)
    raw = pd.DataFrame({r: s[1] for r, s in sig.items()}).reindex(tot.index)
    w = pd.Series(weights, dtype=float).reindex(S.columns)
    avail = S.notna().astype(float)
    wmean = (S.fillna(0.0) * w).sum(axis=1) / (avail * w).sum(axis=1).replace(0.0, np.nan)
    scale = float(tot.std(ddof=1)) if method == "zscore" else 1.0
    dev = S.sub(wmean, axis=0).fillna(0.0) * scale * shrink
    D = dev.add(tot, axis=0)
    long = [pd.DataFrame({"quarter": S.index.astype(str), "route": r, "proxy": raw[r].values, "proxy_std": S[r].values,
                          "deviation": dev[r].values, "demand": D[r].values, "weight": w[r], "total": tot.values})
            for r in S.columns]
    return pd.concat(long, ignore_index=True).assign(origin=str(origin))


def demand_wide(long: pd.DataFrame) -> pd.DataFrame:
    """quarter x route demand (PeriodIndex) from route_demand_asof's long frame."""
    w = long.pivot(index="quarter", columns="route", values="demand")
    w.index = pd.PeriodIndex(w.index, freq="Q")
    return w


def reconciliation_error(long: pd.DataFrame) -> float:
    """max over quarters of |sum_r w_r D_r - total| (0 up to rounding when the total is known)."""
    d = long.dropna(subset=["total"]).assign(wd=lambda x: x["weight"] * x["demand"])
    g = d.groupby("quarter").agg(wd=("wd", "sum"), w=("weight", "sum"), total=("total", "first"))
    return float((g["wd"] / g["w"] - g["total"]).abs().max()) if len(g) else 0.0


def coverage(proxies: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Which proxy covers which route, from when to when."""
    rows = []
    for r, spec in cfg["route_propagation"]["routes"].items():
        for c in spec["proxies"]:
            s = proxies[c].dropna() if c in proxies else pd.Series(dtype=float)
            rows.append({"route": r, "proxy": c, "first": str(s.index.min()) if len(s) else "", "last": str(s.index.max()) if len(s) else "",
                         "n_quarters": int(len(s)), "combine": spec["combine"], "asp_adjusted": bool(spec.get("asp_adjust")),
                         "what_it_measures": spec.get("note", "")})
    return pd.DataFrame(rows)
