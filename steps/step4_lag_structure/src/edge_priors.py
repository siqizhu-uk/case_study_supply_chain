"""Step 4 — edge-by-edge lag PRIORS, computed from the step 5 supply graph before any fit (decision L4).

The chain has two edges, cut at the brand node exactly as step 5's stage_lags cuts each path:

    Amazon / Ingram Micro / TD Synnex --edge 1--> Logitech / GN --edge 2--> Nordic
    edge 1 (downstream) = customers' sell-out -> their orders to the brand (= brand sell-in)
    edge 2 (upstream)   = brand sell-in -> build / component orders -> Nordic revenue
                          (ODM / EMS and Nordic's distributors are folded in, decision L5)

Per cell (edge x brand) the prior is the flow-weighted mean of the path segment lags, under the graph's low / mid / high
edge lags (grade-widened, supply_graph.effective_ranges); route cells (edge 1 via Amazon direct, via Ingram / TD Synnex)
use the same weights restricted to those paths. Evidence = the edges' lag anchors (inventory cover, lead times).

Basis (G25): the prior answers the brief's lag question, so it is on the ORDER-SIGNAL basis (config
supply_graph.lag_answer_basis = signal: physical dwell + the buyers' information delay); the physical dwell alone is kept
next to it (prior_phys_low / mid / high), so the information delay each edge adds is visible.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from edge_posterior import Z90
from step4_check import BRANDS, stage_lags
from supply_graph import edge_shares, effective_ranges, load_edges, paths

SCENARIOS = ("low", "mid", "high")
ROUTES = {"all routes (flow-weighted)": lambda st: st["weight"] > 0,
          "Amazon direct": lambda st: st["path"].str.contains(r"> (?:logitech|gn) > amazon >", regex=True),
          "via Ingram / TD Synnex": lambda st: ~st["direct_to_retail"]}


def answer_basis(cfg: dict) -> str:
    return cfg["supply_graph"].get("lag_answer_basis", "signal")


def graph_paths(cfg: dict, basis: str = "physical") -> tuple[pd.DataFrame, pd.DataFrame]:
    """(edges with effective low / mid / high lags, paths at mid shares) for the graph known at meta.as_of."""
    e, prm = effective_ranges(load_edges(), cfg, basis)
    shares = edge_shares(e, cfg, cfg["meta"]["as_of"], params={k: v["mid"] for k, v in prm.items()})
    return e, paths(e, shares, cfg)


def stage_by_scenario(e: pd.DataFrame, pt: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-path upstream / downstream weeks with every edge at its low, mid or high lag (weights fixed at mid shares)."""
    return {sc: stage_lags(e.assign(lag_weeks_mid=e[f"lag_weeks_{sc}"]), pt) for sc in SCENARIOS}


def _wavg(st: pd.DataFrame, col: str) -> float:
    return float(np.average(st[col], weights=st["weight"])) if st["weight"].sum() > 0 else np.nan


def cell_edges(e: pd.DataFrame, pt: pd.DataFrame, brand: str, upstream: bool) -> list[str]:
    """Edge ids on the brand's paths before (edge 2) or after (edge 1) the brand node; identity sell-out edges dropped."""
    key = {(r.src, r.dst, r.brand): r.edge_id for r in e.itertuples()}
    ids: list[str] = []
    for path in pt.loc[pt["brand"] == brand, "path"]:
        n = path.split(" > ")
        cut = next(i for i, x in enumerate(n) if x in BRANDS)
        pairs = list(zip(n, n[1:]))
        for a, b in (pairs[:cut] if upstream else pairs[cut:]):
            eid = key.get((a, b, brand), key.get((a, b, "all")))
            ids += [eid] if eid and b != "consumers" and eid not in ids else []
    return ids


def _why(e: pd.DataFrame, ids: list[str]) -> tuple[str, str]:
    """(evidence line from the edges' lag anchors, worst lag grade among them)."""
    sub = e.set_index("edge_id").loc[ids]
    first = sub[sub["lag_anchor"].astype(bool)].reset_index().drop_duplicates("lag_anchor")
    ev = "; ".join(f"{r.edge_id} {r.lag_anchor}: {str(r.lag_evidence).split(';')[0].split('(')[0].strip()}" for r in first.itertuples())
    return ev, max(sub["lag_grade"])


def priors(cfg: dict) -> pd.DataFrame:
    """One row per (edge, brand, route): prior low / mid / high / sd in weeks on the answer basis (signal), the physical
    dwell alone next to it (prior_phys_*), grade, the edges and their evidence."""
    basis = answer_basis(cfg)
    pri = _priors_on(cfg, basis)
    phys = _priors_on(cfg, "physical")[["prior_low", "prior_mid", "prior_high"]]
    return pri.assign(basis=basis, **{f"prior_phys_{k}": phys[f"prior_{k}"].values for k in SCENARIOS})


def _priors_on(cfg: dict, basis: str) -> pd.DataFrame:
    e, pt = graph_paths(cfg, basis)
    by_sc = stage_by_scenario(e, pt)
    rows = []
    for brand in BRANDS:
        for edge, col, routes in (("edge 1", "downstream", ROUTES), ("edge 2", "upstream", {"all routes (flow-weighted)": ROUTES["all routes (flow-weighted)"]})):
            for route, pick in routes.items():
                ids = cell_edges(e, pt[pick(by_sc["mid"]).to_numpy()], brand, upstream=(edge == "edge 2"))
                ev, grade = _why(e, ids)
                vals = {sc: _wavg(st[(st["brand"] == brand) & pick(st)], col) for sc, st in by_sc.items()}
                share = float(pt.loc[(pt["brand"] == brand) & pick(by_sc["mid"]).to_numpy(), "weight"].sum() / pt.loc[pt["brand"] == brand, "weight"].sum())
                rows.append({"edge": edge, "brand": brand, "route": route, "flow_share": round(share, 3),
                             "prior_low": vals["low"], "prior_mid": vals["mid"], "prior_high": vals["high"],
                             "prior_sd": (vals["high"] - vals["low"]) / (2 * Z90), "grade": grade,
                             "edges": " ".join(ids), "evidence": ev})
    return pd.DataFrame(rows)
