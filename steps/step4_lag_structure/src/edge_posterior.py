"""Step 4 — prior + estimate -> posterior per edge (decision L8), and route totals (decision L9). Pure functions.

Posterior (normal approximation on weeks):
    informative estimate:  mean = (m_p / sd_p^2 + m_e / sd_e^2) / (1 / sd_p^2 + 1 / sd_e^2),  sd = (1 / sd_p^2 + 1 / sd_e^2)^-1/2
                           sd_e = (90% interval width) / (2 x 1.645)
    uninformative:         posterior = prior ("data did not move it"): the 90% interval is unbounded, or covers at least
                           edge_lags.uninformative_share of the searched range
Totals along a route: edge 1 (route) + edge 2 (brand). Means add; the range is simulated with the edges drawn
independently (normal, clipped at 0), and the comonotone range (low + low, high + high) is shown for edges that move
together (one inventory cycle stretching both).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

Z90 = 1.6449


def posterior(prior: dict, est: dict | None, share_max: float) -> dict:
    """prior {mid, sd, low, high}; est {mid, lo, hi, coverage} in weeks or None. Returns the posterior and how far it moved."""
    base = {"post_mid": prior["mid"], "post_sd": prior["sd"], "post_low": prior["low"], "post_high": prior["high"], "moved_by_weeks": 0.0}
    if est is None:
        return {**base, "informative": False, "reading": "prior only: no estimate for this edge"}
    if not np.isfinite(est["hi"]) or not np.isfinite(est["lo"]):
        return {**base, "informative": False, "reading": "data did not move it: the 90% interval is unbounded"}
    if est.get("coverage", 0.0) >= share_max:
        return {**base, "informative": False,
                "reading": f"data did not move it: the 90% interval covers {est['coverage']:.0%} of the searched range"}
    sd_e = max((est["hi"] - est["lo"]) / (2 * Z90), 1e-6)
    w_p, w_e = 1 / prior["sd"] ** 2, 1 / sd_e ** 2
    mid = (prior["mid"] * w_p + est["mid"] * w_e) / (w_p + w_e)
    sd = (w_p + w_e) ** -0.5
    return {"post_mid": mid, "post_sd": sd, "post_low": max(mid - Z90 * sd, 0.0), "post_high": mid + Z90 * sd,
            "moved_by_weeks": mid - prior["mid"], "informative": True,
            "reading": f"moved {mid - prior['mid']:+.1f} wk ({(mid - prior['mid']) / (est['mid'] - prior['mid']):.0%} of the way to the estimate)"
            if abs(est["mid"] - prior["mid"]) > 1e-9 else "estimate equals the prior"}


def route_total(e1: dict, e2: dict, draws: int, seed: int) -> dict:
    """Sum of two edges {post_mid, post_sd, post_low, post_high}: mean, simulated 5-95%, comonotone low / high."""
    rng = np.random.default_rng(seed)
    a = np.clip(rng.normal(e1["post_mid"], e1["post_sd"], draws), 0, None)
    b = np.clip(rng.normal(e2["post_mid"], e2["post_sd"], draws), 0, None)
    tot = a + b
    return {"edge1_weeks": e1["post_mid"], "edge2_weeks": e2["post_mid"], "total_weeks": e1["post_mid"] + e2["post_mid"],
            "sim_p5_weeks": float(np.quantile(tot, 0.05)), "sim_p95_weeks": float(np.quantile(tot, 0.95)),
            "comonotone_low_weeks": e1["post_low"] + e2["post_low"], "comonotone_high_weeks": e1["post_high"] + e2["post_high"]}


def combine(pri: pd.DataFrame, est: dict, share_max: float) -> pd.DataFrame:
    """Posterior per prior row. `est` maps (edge, brand) -> estimate dict for the flow-weighted cell; route rows of edge 1
    move by the same weeks as their cell (the data are aggregate sell-in: they cannot split the routes)."""
    rows = []
    for r in pri.to_dict("records"):
        pr = {"mid": r["prior_mid"], "sd": r["prior_sd"], "low": r["prior_low"], "high": r["prior_high"]}
        e = est.get((r["edge"], r["brand"]))
        cell = posterior(pr, e, share_max)
        if r["route"] != "all routes (flow-weighted)":
            shift = cell["moved_by_weeks"]
            cell = {**cell, "post_mid": r["prior_mid"] + shift, "post_sd": r["prior_sd"] if not cell["informative"] else cell["post_sd"],
                    "post_low": max(r["prior_low"] + shift, 0.0), "post_high": r["prior_high"] + shift,
                    "reading": cell["reading"] + " (route: shifted with its cell; the data cannot split routes)"}
        rows.append({**r, "estimate_weeks": e["mid"] if e else np.nan, "estimate_lo_weeks": e["lo"] if e else np.nan,
                     "estimate_hi_weeks": e["hi"] if e else np.nan, "estimate_method": e["method"] if e else "", **cell})
    return pd.DataFrame(rows)


TOTAL_ROUTES = (("Amazon -> Logitech -> Nordic", "logitech", "Amazon direct"),
                ("Ingram / TD Synnex -> Logitech -> Nordic", "logitech", "via Ingram / TD Synnex"),
                ("all Logitech routes (flow-weighted)", "logitech", "all routes (flow-weighted)"),
                ("Amazon -> GN -> Nordic", "gn", "Amazon direct"),
                ("Ingram / TD Synnex -> GN -> Nordic", "gn", "via Ingram / TD Synnex"),
                ("all GN routes (flow-weighted)", "gn", "all routes (flow-weighted)"))


def totals(post: pd.DataFrame, draws: int, seed: int) -> pd.DataFrame:
    """Route totals edge 1 (route) + edge 2 (brand)."""
    ix = post.set_index(["edge", "brand", "route"])
    rows = []
    for i, (name, brand, route) in enumerate(TOTAL_ROUTES):
        e1 = ix.loc[("edge 1", brand, route)].to_dict()
        e2 = ix.loc[("edge 2", brand, "all routes (flow-weighted)")].to_dict()
        phys = e1.get("prior_phys_mid", np.nan) + e2.get("prior_phys_mid", np.nan)     # dwell only (G25), shown alongside
        rows.append({"route": name, "brand": brand, **route_total(e1, e2, draws, seed + i), "physical_weeks": phys})
    out = pd.DataFrame(rows)
    return out.assign(total_quarters=out["total_weeks"] / 13.0)
