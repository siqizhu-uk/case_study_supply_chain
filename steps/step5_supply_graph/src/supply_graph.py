"""Step 5 — the supply chain as a time-versioned graph, and the propagation of end demand back to Nordic.

Edges (config/supply_graph.csv) carry goods downstream; demand travels back up them. For one brand b, a path p from
Nordic to end demand has
    weight   w_p = brand_share_b x prod(edge shares along p)          (shares of each node's outflow sum to 1)
    lag      L_p = sum(edge reorder lags along p), weeks   (physical dwell, or + the buyers' information delay: basis
                                                           'signal', G25, info_delay.py; config supply_graph.lag_basis)
and Nordic's response to an end-demand series D (YoY, quarterly) is the kernel-weighted sum
    R(t) = sum_p w_p D(t - L_p / 13)          fractional quarters split linearly between floor and ceil.
Only the edge shares that change over time are time-stamped (Logitech's customer shares, one row per 10-K, usable from
its filing date): graph_asof(date) is the graph an analyst could have known on that date, so a back-test never uses a
10-K published after its forecast origin.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from core.config import ROOT

CFG_DIR = ROOT / "config"
BOUNDS = ROOT / "steps" / "step5_supply_graph" / "outputs" / "graph_lag_bounds.csv"   # written by step 5 from data
EDGES, NODES, WEIGHTS = CFG_DIR / "supply_graph.csv", CFG_DIR / "supply_graph_nodes.csv", CFG_DIR / "supply_graph_weights.csv"
LOGI_10K = ROOT / "pipelines" / "A_company_financials" / "data" / "cache" / "filings" / "logitech"
CUSTOMER_RE = {
    "amazon": r"Amazon Inc\. and its affiliated entities together accounted for (\d+)\s?%",
    "ingram": r"Ingram Micro Inc\. and its affiliated entities together accounted for (\d+)\s?%",
    "tdsynnex": r"TD Synnex(?:,| and its affiliated? entities together)? accounted for (\d+)\s?%",
}


# ------------------------------------------------------------------ time-stamped weights (Logitech's 10-K)
def extract_logitech_weights(filed: dict[int, str]) -> pd.DataFrame:
    """Current-year customer shares from each cached Logitech 10-K, with the sentence they come from."""
    import sys
    sys.path.insert(0, str(ROOT / "pipelines" / "A_company_financials" / "src"))
    from pipeline_a.filings import extract_text
    rows = []
    for f in sorted(LOGI_10K.glob("10KFY??.htm")):
        fy = 2000 + int(f.stem[-2:])
        t = re.sub(r"\s+", " ", extract_text(f))
        row = {"fiscal_year": fy, "source_key": f.stem, "published": filed.get(fy, "")}
        for k, rx in CUSTOMER_RE.items():
            m = re.search(rx, t)
            row[k] = int(m.group(1)) / 100 if m else np.nan
            row[f"quote_{k}"] = m.group(0) if m else ""
        rows.append(row)
    return pd.DataFrame(rows)


def load_weights() -> pd.DataFrame:
    w = pd.read_csv(WEIGHTS, dtype={"published": str})
    return w.sort_values("published").reset_index(drop=True)


def weights_asof(date: str | pd.Timestamp) -> dict:
    """Latest 10-K published on or before `date` (the earliest one if none was yet)."""
    w = load_weights()
    known = w[pd.to_datetime(w["published"]) <= pd.Timestamp(date)]
    r = (known if len(known) else w).iloc[-1]
    return {"amazon": float(r["amazon"]), "ingram": float(r["ingram"]), "tdsynnex": float(r["tdsynnex"]),
            "fiscal_year": int(r["fiscal_year"]), "published": r["published"]}


# ------------------------------------------------------------------ graph, paths, kernel
def load_edges() -> pd.DataFrame:
    return pd.read_csv(EDGES, dtype=str).fillna("")


LAG_BASES = ("physical", "signal")


def effective_ranges(edges: pd.DataFrame, cfg: dict, basis: str = "physical") -> tuple[pd.DataFrame, dict]:
    """Ranges that follow the evidence grade. Data support is NOT the level: a grade sets how wide the range must at least
    be around the mid (config min_halfwidth_by_grade); data bounds then cut it (an anchored lag keeps the cover-based high
    from the edge table; a named share keeps its filing floor / cap). Returns (edges with effective lag low/high,
    {param: {low, mid, high}}).
    basis 'physical' = dwell time only (the edge table). basis 'signal' = physical + the buyer's information delay (G25,
    info_delay.py): lag_weeks_* is the sum, physical_weeks_* / info_weeks_* keep the parts. The Little's-law cap acts on
    the physical part only; the info delay is grade-widened on its own. Lag mixes apply to each part (they are linear)."""
    if basis not in LAG_BASES:
        raise ValueError(f"lag basis must be one of {LAG_BASES}, got {basis!r}")
    e, params = _physical_ranges(edges, cfg)
    if basis == "signal":
        e = add_info_delay(e, cfg)
    return mix_lags(e, params), params


def add_info_delay(e: pd.DataFrame, cfg: dict, count_review_half: bool | None = None) -> pd.DataFrame:
    """Physical effective ranges -> signal: keep the parts, lag_weeks_* = physical + info (new frame; `e` untouched)."""
    from info_delay import info_frame
    info = info_frame(e, cfg, count_review_half)
    out = e.copy()
    for sc in ("low", "mid", "high"):
        phys = pd.to_numeric(e[f"lag_weeks_{sc}"], errors="coerce")
        out[f"physical_weeks_{sc}"] = phys
        out[f"info_weeks_{sc}"] = info[f"info_weeks_{sc}"]
        out[f"lag_weeks_{sc}"] = np.where(phys.notna(), (phys + info[f"info_weeks_{sc}"].fillna(0)).round(2), e[f"lag_weeks_{sc}"])
    return out


def _physical_ranges(edges: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Grade-widened, cover-capped physical lags (not yet mixed) and the named shares' ranges."""
    sg = cfg["supply_graph"]
    hw = sg["min_halfwidth_by_grade"]
    e = edges.copy()
    lo, md, hi = (pd.to_numeric(e[f"lag_weeks_{k}"], errors="coerce") for k in ("low", "mid", "high"))
    w = e["lag_grade"].map(hw).fillna(1.0)
    new_lo = np.minimum(lo, md * (1 - w)).clip(lower=0)
    new_hi = np.maximum(hi, md * (1 + w))
    bound = e["lag_anchor"].map(_bounds(sg.get("little_law_tolerance", 1.0)))       # data bound (inventory cover), weeks
    bound = bound.where(bound.notna(), np.where(e["lag_anchor"].astype(str).str.len() > 0, hi, np.nan))
    new_hi = np.where(bound.notna(), np.minimum(new_hi, bound), new_hi)
    new_lo = np.minimum(new_lo, new_hi)
    e["lag_weeks_low"] = np.where(md.notna(), new_lo.round(2), e["lag_weeks_low"])
    e["lag_weeks_high"] = np.where(md.notna(), pd.Series(new_hi).round(2), e["lag_weeks_high"])
    params = {}
    for k, v in sg["params"].items():
        m, g = float(v["mid"]), hw.get(v.get("grade", "D"), 1.0)
        a = max(float(v.get("floor", 0.0)), min(float(v["low"]), m * (1 - g)), 0.0)
        b = min(float(v.get("cap", 1.0)), max(float(v["high"]), m * (1 + g)), 1.0)
        params[k] = {"low": a, "mid": m, "high": b}
    return e, params


def mix_lags(e: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Edges whose flow is split between two routes the graph has no entity for (column lag_mix = 'param:A+B|C+D'):
    lag = (1 - p) x own lag + p x mean over routes of the summed route lags, per scenario (low p with low lags, ...).
    Used for Logitech's unnamed 10-K residual: part direct to retail, part through smaller distributors (G20)."""
    if "lag_mix" not in e or not e["lag_mix"].astype(str).str.len().any():
        return e
    out = e.copy()
    for col in ("lag_weeks", "physical_weeks", "info_weeks"):          # the signal basis mixes each part (linear)
        if f"{col}_mid" not in e:
            continue
        lag = {sc: dict(zip(e["edge_id"], pd.to_numeric(e[f"{col}_{sc}"], errors="coerce"))) for sc in ("low", "mid", "high")}
        for i, r in e[e["lag_mix"].astype(str).str.len() > 0].iterrows():
            name, routes = r["lag_mix"].split(":")
            for sc in ("low", "mid", "high"):
                via = float(np.mean([sum(lag[sc][x] for x in rt.split("+")) for rt in routes.split("|")]))
                p = params[name][sc]
                out.loc[i, f"{col}_{sc}"] = round((1 - p) * lag[sc][r["edge_id"]] + p * via, 2)
    return out


def _bounds(tol: float) -> dict:
    """anchor -> upper bound on the lag in weeks (inventory cover x tolerance), from the latest step-5 run."""
    if not BOUNDS.exists():
        return {}
    b = pd.read_csv(BOUNDS).dropna(subset=["weeks"])
    return dict(zip(b["anchor"], b["weeks"] * tol))


def edge_shares(edges: pd.DataFrame, cfg: dict, date, scenario: str = "mid", params: dict | None = None) -> pd.Series:
    """Evaluate each edge's share formula with the named parameters (a scenario, or `params` drawn by the Monte Carlo)
    and the 10-K weights known at `date`."""
    sg = cfg["supply_graph"]
    ns = dict(params) if params is not None else {k: float(v[scenario]) for k, v in sg["params"].items()}
    ns.update({k: v for k, v in weights_asof(date).items() if k in CUSTOMER_RE})
    out = {}
    for r in edges.itertuples():
        if not r.share:
            out[r.edge_id] = np.nan
            continue
        if not re.fullmatch(r"[\w\s\.\*\+\-/()]+", r.share):
            raise ValueError(f"{r.edge_id}: share formula '{r.share}' has characters outside names, numbers and + - * / ( )")
        out[r.edge_id] = float(eval(r.share, {"__builtins__": {}}, ns))          # noqa: S307  names/numbers/operators only
    return pd.Series(out)


def paths(edges: pd.DataFrame, shares: pd.Series, cfg: dict, lag_col: str = "lag_weeks_mid", stop_at: str | None = None) -> pd.DataFrame:
    """Every path from Nordic to end demand, per brand, with weight and summed lag. `stop_at` (e.g. 'logitech') ends each path
    at that node: the segment from the node's own sell-in back to Nordic, used when the driver is that node's sell-in (GRi)."""
    sg = cfg["supply_graph"]
    rows = []
    for brand, bshare in ((b, v) for b, v in sg["brand_share"].items() if b != "source"):
        e = edges[edges["brand"].isin([brand, "all"]) & shares.reindex(edges["edge_id"]).notna().values]
        out_edges = {s: g for s, g in e.groupby("src")}

        def walk(node, w, lag, trail):
            if node == (stop_at or "consumers"):
                rows.append({"brand": brand, "path": " > ".join(trail), "weight": bshare * w, "lag_weeks": lag})
                return
            for r in out_edges.get(node, pd.DataFrame()).itertuples():
                walk(r.dst, w * shares[r.edge_id], lag + float(getattr(r, lag_col)), trail + [r.dst])

        walk("nordic", 1.0, 0.0, ["nordic"])
    return pd.DataFrame(rows)


def kernel(pt: pd.DataFrame, cfg: dict, max_q: int = 4) -> pd.Series:
    """Weights on quarterly lags 0..max_q: each path's lag in quarters split linearly between floor and ceil."""
    wq = cfg["supply_graph"]["weeks_per_quarter"]
    k = np.zeros(max_q + 1)
    for w, L in zip(pt["weight"], pt["lag_weeks"] / wq):
        lo = int(np.floor(L))
        frac = L - lo
        k[min(lo, max_q)] += w * (1 - frac)
        k[min(lo + 1, max_q)] += w * frac
    return pd.Series(k / k.sum(), index=range(max_q + 1), name="weight")


def lag_basis(cfg: dict, basis: str | None = None) -> str:
    """The basis a kernel uses: explicit, else config supply_graph.lag_basis (default physical)."""
    return basis or cfg["supply_graph"].get("lag_basis", "physical")


def kernel_asof(date, cfg: dict, scenario: str = "mid", basis: str | None = None, stop_at: str | None = None) -> pd.Series:
    """Lag kernel of the graph known at `date`; `scenario` sets both the shares and the edge lags (low / mid / high),
    using the grade-based effective ranges; `basis` physical / signal (default: config supply_graph.lag_basis)."""
    e, prm = effective_ranges(load_edges(), cfg, lag_basis(cfg, basis))
    params = {k: v[scenario] for k, v in prm.items()}
    return kernel(paths(e, edge_shares(e, cfg, date, params=params), cfg, lag_col=f"lag_weeks_{scenario}", stop_at=stop_at), cfg)


def _known(D: pd.Series, ahead: pd.Series | None, t: pd.Period, j: int, h: int) -> float:
    """D(t-j) as known at the origin of a horizon-h forecast of t: reported (j >= h), else a point-in-time forecast of
    that quarter (`ahead`, e.g. the downstream company's own guide), else the latest known value (persistence)."""
    for jj in range(j, j + 8):
        if jj >= h:
            return D.get(t - jj, np.nan)
        if ahead is not None and t - jj in ahead.index and pd.notna(ahead[t - jj]):
            return float(ahead[t - jj])
    return np.nan


def propagate(D: pd.Series, cfg: dict, h: int = 0, origin_of=None, scenario: str = "mid", ahead: pd.Series | None = None,
              basis: str | None = None, stop_at: str | None = None) -> pd.Series:
    """R(t) = sum_k kernel_k D(t-k), with the graph known at the forecast origin of t. At horizon h, lags below h are not
    yet observed: they read `ahead` (a forecast of that quarter known at the origin) where given, else the latest known
    value (persistence). Without `ahead`, all weight below h lands on D(t-h), so edge lags that only move weight between
    lags 0..h cannot change the result."""
    out = {}
    for t in D.index:
        date = origin_of(t) if origin_of else t.end_time
        k = kernel_asof(date, cfg, scenario, basis, stop_at)
        k = k[k > 0]                                                     # zero-weight lags need no data
        vals = [_known(D, ahead, t, j, h) for j in k.index]
        out[t] = float(np.dot(k.values, vals)) if not np.isnan(vals).any() else np.nan
    return pd.Series(out, name=f"graph_demand_h{h}")
