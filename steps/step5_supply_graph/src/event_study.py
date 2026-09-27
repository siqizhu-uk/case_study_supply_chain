"""Step 5d — the 2026 supplier incident as an event study through this chain (decision G23).

A SHOCK leaves every relationship as it is, so the graph carries it. Logitech's late-June 2026 semiconductor-supplier
incident (lost Logitech sales: Q2 FY27 = 2026Q3 $20m, Q3 FY27 = 2026Q4 up to $200m, 'largely resolved by Q4') is pushed
back to Nordic node by node, in weeks, and summed into calendar quarters by overlap (no single quarter shift):

    customers  Amazon / Ingram / TD Synnex sell-in from Logitech = lost sales x their 10-K shares (the same invoice)
    Logitech   lost sales, spread evenly over the weeks in which a sale CAN be lost: after the finished goods built before
               the incident have sold (incident + flow-weighted build -> sale lag)
    build      lost builds / component call-offs, per graph path: sale week - build -> sale lag (ODM E08, in-house E05)
    Nordic     lost Nordic shipments, per path: build week - (path lead - build -> sale lag), x Nordic content per
               Logitech $ (step 2 attribution path)

Buffers:
    stock      chips Nordic shipped BEFORE the incident for builds that were then lost, and deliveries inside the frozen
               window after it, are not lost shipments: they sit at the holder (Nordic's distributors, the ODM kit,
               Logitech's Suzhou raw materials). When builds restart they are used first, so Nordic's orders restart one
               stock-depletion later and the loss re-appears then. Checked against each holder's inventory cover.
    orders     every later cut is a push-out or a cancellation of an order already booked inside the 12-16 week lead
               time (the on-order share is computed); for revenue the two are the same unless lost sales come back.
    guide      Nordic's 6 Aug guide came from orders after Logitech's 28 Jul disclosure: share_in_nordic_guide (grade D,
               config chain_forecast.supplier_incident) of the Q3 effect is already in it.
Conservation: with no restock, Nordic's total change = - content x total lost Logitech sales.
"""
from __future__ import annotations

from typing import NamedTuple

import numpy as np
import pandas as pd

from core.config import ROOT
from supply_graph import edge_shares, effective_ranges, load_edges, weights_asof

S2_PATH = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"
BOUNDS = ROOT / "steps" / "step5_supply_graph" / "outputs" / "graph_lag_bounds.csv"
CHIP_NODES = ("nordic_distributors", "odm", "logitech")


class Block(NamedTuple):
    """USD m spread evenly over weeks [start, end); start == end puts it all at that week. Week 0 = window start."""
    start: float
    end: float
    usd: float


# ------------------------------------------------------------------ block arithmetic (pure)
def shift(b: Block, lag: float) -> Block:
    return Block(b.start - lag, b.end - lag, b.usd)


def scale(b: Block, k: float) -> Block:
    return Block(b.start, b.end, b.usd * k)


def frac_before(b: Block, t: float) -> float:
    if b.end == b.start:
        return float(b.start < t)
    return float(np.clip((t - b.start) / (b.end - b.start), 0.0, 1.0))


def split(b: Block, t: float) -> tuple[Block, Block]:
    """(part before week t, part from t on)."""
    f = frac_before(b, t)
    return (Block(b.start, min(b.end, max(b.start, t)), b.usd * f),
            Block(max(b.start, min(b.end, t)), b.end, b.usd * (1 - f)))


def clamp(b: Block, t: float) -> list[Block]:
    """Mass before week t moved to t (a build cannot be lost before the incident: the pipeline was already full)."""
    pre, post = split(b, t)
    return [Block(t, t, pre.usd), post]


def total(blocks: list[Block]) -> float:
    return float(sum(b.usd for b in blocks))


def by_quarter(blocks: list[Block], q0: pd.Period, quarters: list[pd.Period], wq: float) -> pd.Series:
    out = {str(q): sum(b.usd * (frac_before(b, ((q - q0).n + 1) * wq) - frac_before(b, (q - q0).n * wq)) for b in blocks)
           for q in quarters}
    return pd.Series(out, dtype=float)


def centroid(blocks: list[Block]) -> float:
    m = total(blocks)
    return float(sum(b.usd * (b.start + b.end) / 2 for b in blocks) / m) if m else np.nan


def week_of(date, q0: pd.Period, wq: float) -> float:
    d = pd.Timestamp(date)
    q = d.to_period("Q")
    return ((q - q0).n + (d - q.start_time) / (q.end_time - q.start_time)) * wq


def date_of(week: float, q0: pd.Period, wq: float) -> pd.Timestamp:
    k = int(np.floor(week / wq))
    q = q0 + k
    return (q.start_time + (week / wq - k) * (q.end_time - q.start_time)).normalize()


# ------------------------------------------------------------------ the graph segment Nordic -> Logitech
def _walk(e: pd.DataFrame, sh: pd.Series, node: str, trail: tuple, w: float) -> list[tuple[tuple, float]]:
    if node == "logitech":
        return [(trail, w)]
    nxt = e[(e["src"] == node) & e["dst"].isin(CHIP_NODES)]
    return [p for r in nxt.itertuples() if pd.notna(sh.get(r.edge_id))
            for p in _walk(e, sh, r.dst, trail + (r.edge_id,), w * sh[r.edge_id])]


def lead_paths(cfg: dict, date, lags: str = "mid") -> pd.DataFrame:
    """Nordic -> Logitech paths known at `date`: weight (sums to 1), lead (Nordic shipment -> Logitech sale, weeks),
    build -> sale lag, and the first holder of the chip. Shares at mid; edge lags at `lags` (grade-widened ranges)."""
    e, prm = effective_ranges(load_edges(), cfg)
    sh = edge_shares(e, cfg, date, params={k: v["mid"] for k, v in prm.items()})
    e = e[e["brand"].isin(["logitech", "all"])]
    lag = dict(zip(e["edge_id"], pd.to_numeric(e[f"lag_weeks_{lags}"], errors="coerce")))
    src, dst = dict(zip(e["edge_id"], e["src"])), dict(zip(e["edge_id"], e["dst"]))
    inhouse = cfg["event_study"]["inhouse_build_edge"]
    walks = _walk(e, sh, "nordic", (), 1.0)
    W = sum(w for _, w in walks)
    return pd.DataFrame([{"path": " > ".join(t), "weight": w / W, "lead_weeks": sum(lag[x] for x in t),
                          "build_weeks": lag[t[-1]] if src[t[-1]] != "nordic" else lag[inhouse], "holder": dst[t[0]]}
                         for t, w in walks])


# ------------------------------------------------------------------ inputs read from config and earlier steps
def inputs(cfg: dict) -> dict:
    """Everything the event study takes from elsewhere, read once (config is not modified)."""
    es, inc = cfg["event_study"], cfg["chain_forecast"]["supplier_incident"]
    wq = float(cfg["supply_graph"]["weeks_per_quarter"])
    q0 = pd.Period(es["window"][0], "Q")
    ap = pd.read_csv(S2_PATH).dropna(subset=["nordic_content_pct_of_logi_sales_p50"]).iloc[-1]
    c50 = float(ap["nordic_content_pct_of_logi_sales_p50"]) / 100
    content = {"p10": c50 * ap["logitech_usdm_p10"] / ap["logitech_usdm_p50"], "p50": c50,
               "p90": c50 * ap["logitech_usdm_p90"] / ap["logitech_usdm_p50"]}
    bounds = pd.read_csv(BOUNDS).set_index("anchor")["weeks"].to_dict() if BOUNDS.exists() else {}
    w10k = weights_asof(inc["as_of"])
    shares = {**{k: w10k[k] for k in ("amazon", "ingram", "tdsynnex")}}
    shares_other = 1 - sum(shares.values())
    cov = es["customer_cover_anchor"]
    cover = sum(s * bounds.get(cov[k], np.nan) for k, s in {**shares, "other": shares_other}.items())
    g = cfg["forecast"]["logitech_2026Q3"]
    return {"wq": wq, "q0": q0, "quarters": list(pd.period_range(es["window"][0], es["window"][1], freq="Q")),
            "w0": week_of(es["incident_date"], q0, wq), "content": content, "bounds": bounds, "shares_10k": shares,
            "named_share": sum(shares.values()), "customer_cover_weeks": float(cover),
            "weekly_sales": (g["guide_low"] + g["guide_high"]) / 2 / wq, "as_of": inc["as_of"],
            "share_in_guide": float(inc["share_in_nordic_guide"]), "guide_date": inc["as_of"]}


def loss_blocks(cfg: dict, sc: dict, w0: float, d_bar: float, x: dict) -> list[Block]:
    """Lost Logitech sales (negative), each fiscal quarter spread over the weeks a sale can be lost in that quarter."""
    sb, f2c = cfg["structural_breaks"]["logitech_supplier_incident_2026"], cfg["event_study"]["fiscal_to_calendar"]
    loss = {f2c["q2fy27_sales_hit_usdm"]: sb["q2fy27_sales_hit_usdm"],
            f2c["q3fy27_sales_hit_usdm"]: sb["q3fy27_sales_hit_usdm"] * sc["q3fy27_loss_scale"],
            f2c["q4fy27"]: sc["q4fy27_loss_usdm"]} if sb.get("apply") else {}
    out = []
    for q, usd in loss.items():
        a, z = (pd.Period(q, "Q") - x["q0"]).n * x["wq"], ((pd.Period(q, "Q") - x["q0"]).n + 1) * x["wq"]
        start = min(max(a, w0 + d_bar), z)
        out += [Block(start, z, -float(usd))] if usd else []
    return out


# ------------------------------------------------------------------ one run
def _path_run(loss: list[Block], p, content: float, w0: float, frozen: float) -> dict:
    build = [c for b in loss for c in clamp(shift(scale(b, p.weight), p.build_weeks), w0)]
    ship = [scale(shift(b, p.lead_weeks - p.build_weeks), content) for b in build]
    pre, rest = zip(*[split(b, w0) for b in ship]) if ship else ((), ())
    frz, cut = zip(*[split(b, w0 + frozen) for b in rest]) if rest else ((), ())
    return {"build": build, "pre": list(pre), "frozen": list(frz), "cut": list(cut), "ship": ship}


def _restock(loss: list[Block], sc: dict, wR: float, x: dict) -> tuple[list[Block], float]:
    """The channel refills (share of) the cover it drew during the outage: drawn = min(lost sell-in, cover x peak rate)."""
    if not loss or not sc["restock_share"]:
        return [], 0.0
    peak = max(-b.usd / (b.end - b.start) for b in loss if b.end > b.start)
    cover = x["customer_cover_weeks"]
    drawn = min(-total(loss), cover * peak)
    return [Block(wR, wR + cover, sc["restock_share"] * drawn)], drawn


def run(cfg: dict, x: dict, sc_name: str = "mid", lags: str = "mid", frozen: str = "mid", content: str = "p50") -> dict:
    """Blocks per node for one scenario / lag / frozen-window / content setting."""
    es = cfg["event_study"]
    sc = es["scenarios"][sc_name]
    pt = lead_paths(cfg, pd.Timestamp(x["as_of"]), lags)
    c, fz, w0 = x["content"][content], float(es["frozen_weeks"][frozen]), x["w0"]
    wR = (pd.Period(sc["resolved_quarter"], "Q") - x["q0"]).n * x["wq"]
    d_bar = float(np.dot(pt["weight"], pt["build_weeks"]))
    loss = loss_blocks(cfg, sc, w0, d_bar, x)
    rs, drawn = _restock(loss, sc, wR, x)
    per = {r.holder + "|" + r.path: (r, _path_run(loss, r, c, w0, fz)) for r in pt.itertuples()}
    stock, release = {}, []
    for key, (r, pr) in per.items():
        s = total(pr["pre"]) + total(pr["frozen"])
        usage = r.weight * c * x["weekly_sales"]
        stock[key] = {"holder": r.holder, "usd": s, "weeks": -s / usage if usage else np.nan}
        release.append(Block(wR - r.lead_weeks, wR - r.lead_weeks - s / usage, s))
    rs_build = [shift(scale(b, r.weight), r.build_weeks) for r in pt.itertuples() for b in rs]
    rs_nordic = [scale(shift(scale(b, r.weight), r.lead_weeks), c) for r in pt.itertuples() for b in rs]
    cut = [b for _, pr in per.values() for b in pr["cut"]]
    return {"paths": pt, "d_bar": d_bar, "wR": wR, "w0": w0, "frozen": fz, "content": c, "drawn": drawn,
            "customers": [scale(b, x["named_share"]) for b in loss + rs], "logitech": loss + rs,
            "build": [b for _, pr in per.values() for b in pr["build"]] + rs_build,
            "nordic_cut": cut, "nordic_stock": release, "nordic_restock": rs_nordic,
            "nordic": cut + release + rs_nordic, "gross_ship": [b for _, pr in per.values() for b in pr["ship"]],
            "stock": stock}
