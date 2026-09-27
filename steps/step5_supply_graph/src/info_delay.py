"""Step 5 — information delay per edge: the part of the order-signal lag that holds no stock (decision G25, pitfall P86).

A demand change travels upstream as an ORDER SIGNAL. On an edge src -> dst the buyer (dst) places the order; its planning
decision adds, on top of the physical dwell (edge table lag_weeks_*, Little's-law capped), the textbook delay of a
periodic-review order-up-to policy with an exponentially smoothed forecast:

    delay = R / 2  +  (1 - alpha) / alpha x R          weeks, R = review period in weeks, alpha per review period
            (wait for the next review) (mean age of the smoothed forecast; Brown 1959)

Planners and their R / alpha are in config/model.yaml supply_graph.info_delay (grade D: nobody discloses a cadence); which
planner(s) an edge carries is config/supply_graph.csv info_delay_planner ('a+b' = two decisions on one edge). A planner's
range is widened around its mid by min_halfwidth_by_grade like any lag, and is never capped by inventory cover.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SCENARIOS = ("low", "mid", "high")


def planner_delay(p: dict, count_review_half: bool = True) -> dict:
    """{low, mid, high} weeks for one planner from its review period and smoothing constant (keys = delay scenarios)."""
    out = {}
    for sc in SCENARIOS:
        r, a = float(p["review_weeks"][sc]), float(p["alpha"][sc])
        if r < 0 or not 0 < a <= 1:
            raise ValueError(f"info_delay planner: review_weeks must be >= 0 and 0 < alpha <= 1 (got {r}, {a})")
        out[sc] = (r / 2 if count_review_half else 0.0) + (1 - a) / a * r
    return out


def planner_ranges(cfg: dict, count_review_half: bool | None = None) -> dict:
    """{planner: {low, mid, high, grade}} with the grade's minimum half-width around the mid (no data cap)."""
    sg = cfg["supply_graph"]
    idc = sg["info_delay"]
    half = idc.get("count_review_half", True) if count_review_half is None else count_review_half
    hw = sg["min_halfwidth_by_grade"]
    out = {}
    for name, p in idc["planners"].items():
        d, g = planner_delay(p, half), p.get("grade", "D")
        w = hw.get(g, 1.0)
        out[name] = {"low": max(min(d["low"], d["mid"] * (1 - w)), 0.0), "mid": d["mid"],
                     "high": max(d["high"], d["mid"] * (1 + w)), "grade": g}
    return out


def planners_of(edges: pd.DataFrame) -> dict[str, list[str]]:
    """edge_id -> list of planner names (empty when the edge carries no order decision)."""
    col = edges["info_delay_planner"] if "info_delay_planner" in edges else pd.Series("", index=edges.index)
    return {e: [x.strip() for x in str(p).split("+") if x.strip()] for e, p in zip(edges["edge_id"], col.fillna(""))}


def edge_info(edges: pd.DataFrame, weeks: dict[str, float]) -> pd.Series:
    """Information delay per edge (weeks) for given planner delays: the sum over the edge's planners. Edges without a lag
    (lag_weeks_mid blank) get NaN, like their physical lag."""
    has_lag = pd.to_numeric(edges["lag_weeks_mid"], errors="coerce").notna().values
    pl = planners_of(edges)
    unknown = {x for v in pl.values() for x in v} - set(weeks)
    if unknown:
        raise ValueError(f"info_delay_planner names not in config supply_graph.info_delay.planners: {sorted(unknown)}")
    vals = [sum(weeks[x] for x in pl[e]) if ok else np.nan for e, ok in zip(edges["edge_id"], has_lag)]
    return pd.Series(vals, index=edges.index, dtype=float)


def info_frame(edges: pd.DataFrame, cfg: dict, count_review_half: bool | None = None) -> pd.DataFrame:
    """info_weeks_low / mid / high per edge (index aligned with `edges`); the scenarios move every planner together."""
    pr = planner_ranges(cfg, count_review_half)
    return pd.DataFrame({f"info_weeks_{sc}": edge_info(edges, {k: v[sc] for k, v in pr.items()}) for sc in SCENARIOS},
                        index=edges.index)


def planner_table(cfg: dict) -> pd.DataFrame:
    """One row per planner: review period, alpha, the formula's low / mid / high and the grade-widened range."""
    idc = cfg["supply_graph"]["info_delay"]
    pr = planner_ranges(cfg)
    rows = []
    for k, p in idc["planners"].items():
        raw = planner_delay(p, idc.get("count_review_half", True))
        rows.append({"planner": k, "review_weeks_mid": p["review_weeks"]["mid"], "alpha_mid": p["alpha"]["mid"],
                     "formula_low": raw["low"], "formula_mid": raw["mid"], "formula_high": raw["high"],
                     "range_low": pr[k]["low"], "range_high": pr[k]["high"], "grade": pr[k]["grade"],
                     "smoothing_only_mid": planner_delay(p, False)["mid"], "source": p.get("source", "")})
    return pd.DataFrame(rows)
