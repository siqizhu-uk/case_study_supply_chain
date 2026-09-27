"""Step 5 vs step 4 (decision G21): where the gap between the graph's flow-weighted lag and step 4's reasoned lag comes from.
A check only - nothing here changes an edge, a share or step 4's lag_weeks.

Every path's lag splits into upstream (Nordic -> finished device at the brand) and downstream (brand -> consumer), and
step 4 gives one number for each stage (config lag_weeks mid). So the total gap is exactly

    sum over paths  w x (upstream - step 4 upstream)  +  w x (downstream - step 4 downstream)

grouped by route. Logitech's unnamed 10-K residual (edge with a lag_mix, G20) is split in two:
    w x (distributor-route lag - step 4 downstream)          -> 'distributor route' (as if all of it went via a distributor)
    w x (1 - p) x (own direct lag - distributor-route lag)   -> 'direct-retail part of the residual' (moves with p)
which adds up to w x (mixed lag - step 4 downstream) because mixed = (1 - p) x own + p x distributor route.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from step4_check import DOWNSTREAM, UPSTREAM, stage_lags
from supply_graph import effective_ranges

DISTRIBUTORS = ("ingram", "tdsynnex")
AMAZON = "Logitech -> Amazon direct"
SUZHOU = "Logitech in-house (Suzhou) routes: Nordic -> Logitech without an ODM"
ODM = "Logitech ODM routes (upstream)"
DIST = "distributor route itself (Ingram / TD Synnex + distributor part of the 10-K residual)"
DIRECT = "direct-retail part of Logitech's 10-K residual"
GN = "GN routes"
GROUPS = {   # group -> (nature: why the graph differs from step 4, what it is compared with)
    AMAZON: ("structure: Amazon buys from Logitech directly (10-K customer share, A)", "step 4 downstream mid"),
    SUZHOU: ("structure: ~35% built in-house (10-K, A)", "step 4 upstream mid"),
    ODM: ("agrees with step 4", "step 4 upstream mid"),
    DIST: ("data bound: reseller inventory cover caps the distributor -> retail edges (P69)", "step 4 downstream mid"),
    DIRECT: ("judgment: p = share of the residual via distributors (G20, grade D)", "graph distributor route (as at p = 1)"),
    GN: ("GN (upstream + downstream)", "step 4 total mid"),
}


def residual_mix(raw: pd.DataFrame, cfg: dict) -> dict:
    """The mixed edge (Logitech's 10-K residual): its own direct lag, the distributor-route lag it is mixed with, and p (mid)."""
    plain, params = effective_ranges(raw.assign(lag_mix=""), cfg)
    lag = dict(zip(plain["edge_id"], pd.to_numeric(plain["lag_weeks_mid"], errors="coerce")))
    row = raw.loc[raw["lag_mix"].astype(str).str.len() > 0].iloc[0]
    name, routes = row["lag_mix"].split(":")
    via = float(np.mean([sum(lag[e] for e in rt.split("+")) for rt in routes.split("|")]))
    return {"src": row["src"], "dst": row["dst"], "own": float(lag[row["edge_id"]]), "via": via, "p": float(params[name]["mid"])}


def _first_customer(path: str, brand: str) -> str:
    nodes = path.split(" > ")
    return nodes[nodes.index(brand) + 1]


def _pieces(st: pd.DataFrame, mix: dict, up4: float, down4: float) -> pd.DataFrame:
    """One row per (path, piece): group, flow, graph weeks, reference weeks; contribution = flow x (graph - reference)."""
    rows = []
    for r in st.itertuples():
        if r.brand != "logitech":
            rows.append((GN, r.weight, r.upstream + r.downstream, up4 + down4))
            continue
        suzhou = " > odm > " not in r.path
        rows.append((SUZHOU if suzhou else ODM, r.weight, r.upstream, up4))
        first = _first_customer(r.path, "logitech")
        if first == "amazon":
            rows.append((AMAZON, r.weight, r.downstream, down4))
        elif first in DISTRIBUTORS:
            rows.append((DIST, r.weight, r.downstream, down4))
        elif first == mix["dst"]:
            rest = r.downstream - ((1 - mix["p"]) * mix["own"] + mix["p"] * mix["via"])
            rows.append((DIST, r.weight, mix["via"] + rest, down4))
            rows.append((DIRECT, r.weight * (1 - mix["p"]), mix["own"], mix["via"]))
        else:
            raise ValueError(f"unclassified Logitech route: {r.path}")
    return pd.DataFrame(rows, columns=["group", "flow", "graph", "ref"])


def decompose(raw: pd.DataFrame, eff: pd.DataFrame, pt: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Gap (graph - step 4 mid, weeks) by route group; the rows sum to the total gap. raw: edges as in the CSV;
    eff: effective edges (with the residual's lag mix) the paths were built from."""
    lw = cfg["lag_weeks"]
    up4, down4 = (float(sum(lw[k]["mid"] for k in ks)) for ks in (UPSTREAM, DOWNSTREAM))
    st = stage_lags(eff, pt)
    st = st.assign(weight=st["weight"] / st["weight"].sum())
    mix = residual_mix(raw, cfg)
    pc = _pieces(st, mix, up4, down4)
    pc = pc.assign(contrib=pc["flow"] * (pc["graph"] - pc["ref"]))
    g = pc.groupby("group", sort=False).apply(lambda d: pd.Series({
        "flow_share": d["flow"].sum(), "graph_weeks": np.average(d["graph"], weights=d["flow"]),
        "reference_weeks": np.average(d["ref"], weights=d["flow"]), "contribution_weeks": d["contrib"].sum()}), include_groups=False)
    g = g.reindex([k for k in GROUPS if k in g.index]).reset_index()
    g = g.assign(nature=g["group"].map(lambda k: GROUPS[k][0]), reference=g["group"].map(lambda k: GROUPS[k][1]))
    total = float(np.average(st["upstream"] + st["downstream"], weights=st["weight"])) - (up4 + down4)
    tot = pd.DataFrame([{"group": "total (graph - step 4 mid)", "flow_share": 1.0, "graph_weeks": total + up4 + down4,
                         "reference_weeks": up4 + down4, "contribution_weeks": g["contribution_weeks"].sum(),
                         "nature": f"check: graph total - step 4 mid = {total:+.2f}", "reference": "step 4 total mid"}])
    cols = ["group", "nature", "flow_share", "graph_weeks", "reference_weeks", "reference", "contribution_weeks"]
    return pd.concat([g, tot], ignore_index=True)[cols].assign(p_residual_via_dist=mix["p"])
