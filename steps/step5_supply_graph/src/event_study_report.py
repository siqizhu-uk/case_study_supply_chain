"""Step 5d outputs: the supplier-incident propagation table (node x calendar quarter, USD m), its uncertainty band, the
Nordic Q3 waterfall (chain_forecast gross -> re-timed by stock and orders -> already in the guide -> net), the report
section and the run hook (decision G23). The mechanics are in event_study.py."""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from core.config import step_outputs
from event_study import S2_PATH, by_quarter, centroid, date_of, inputs, run, split, total

ROWS = [("customers", "customers", "Amazon + Ingram + TD Synnex sell-in from Logitech", "A share (10-K) x C loss (verbal)"),
        ("logitech", "logitech", "Logitech sales lost", "C (Logitech, verbal; Q3 FY27 'up to')"),
        ("build", "build", "Logitech builds / component call-offs lost (at Logitech sales value)", "C (edge lags E05 / E08)"),
        ("nordic", "nordic_cut", "Nordic shipments: orders pushed out / cancelled", "B/C content x C lead"),
        ("nordic", "nordic_stock", "Nordic shipments: chips already at the holder used first at restart", "D frozen window, C restart date"),
        ("nordic", "nordic_restock", "Nordic shipments: channel restock (scenario only)", "D"),
        ("nordic", "nordic", "Nordic shipments to the Logitech slice: total", "C")]


def _q(blocks, x) -> pd.Series:
    return by_quarter(blocks, x["q0"], x["quarters"], x["wq"])


def band(cfg: dict, x: dict) -> pd.DataFrame:
    """Nordic total by quarter over every edge-lag range (low / mid / high), frozen window and content (p10 / p50 / p90),
    at the mid recovery; plus the downside / upside recovery scenarios at mid inputs."""
    grid = [_q(run(cfg, x, "mid", lg, fz, ct)["nordic"], x) for lg, fz, ct in
            itertools.product(("low", "mid", "high"), ("low", "mid", "high"), ("p10", "p50", "p90"))]
    g = pd.DataFrame(grid)
    return pd.DataFrame({"band_low": g.min(), "band_high": g.max(),
                         **{s: _q(run(cfg, x, s)["nordic"], x) for s in ("downside", "upside")}})


def on_order_share(r: dict, x: dict, lead_w: float) -> float:
    """Share of Nordic's cut shipments in the guided quarter that were already on order at the incident (delivery
    within the order lead time of it): those cuts are push-outs / cancellations of booked orders."""
    q = pd.Timestamp(x["as_of"]).to_period("Q")
    a, z = (q - x["q0"]).n * x["wq"], ((q - x["q0"]).n + 1) * x["wq"]
    inq = [split(split(b, a)[1], z)[0] for b in r["nordic_cut"]]
    booked = total([split(b, r["w0"] + lead_w)[0] for b in inq])
    return booked / total(inq) if total(inq) else np.nan


def propagation_table(cfg: dict, x: dict, r: dict, bd: pd.DataFrame) -> pd.DataFrame:
    shown = [str(q) for q in x["quarters"] if q >= pd.Period(cfg["event_study"]["window"][0], "Q") + 1]
    rows = [{"node": n, "row": lab, "grade": g, **_q(r[k], x)[shown].to_dict(), "total": total(r[k])} for n, k, lab, g in ROWS]
    tq = str(pd.Timestamp(x["as_of"]).to_period("Q"))
    nq = _q(r["nordic"], x)
    guide = {q: (x["share_in_guide"] * nq[q] if q == tq else 0.0) for q in shown}
    rows += [{"node": "nordic", "row": f"band {s.split('_')[1]} (edge lags x frozen window x content)" if "band" in s else f"scenario: {s}",
              "grade": "", **bd[s][shown].to_dict(), "total": np.nan} for s in ("band_low", "band_high", "downside", "upside")]
    rows += [{"node": "nordic", "row": "already in Nordic's 6 Aug guide (guided quarter only)", "grade": "D",
              **guide, "total": sum(guide.values())},
             {"node": "nordic", "row": "Nordic: not yet in any guide (total - already in guide)", "grade": "D",
              **{q: nq[q] - guide[q] for q in shown}, "total": total(r["nordic"]) - sum(guide.values())}]
    return pd.DataFrame(rows)


def _nordic_guide_mid(cfg: dict) -> float:
    g = cfg["forecast"]["nordic_2026Q3"]
    return (g["guide_low"] + g["guide_high"]) / 2


def summary(cfg: dict, x: dict, r: dict, bd: pd.DataFrame) -> dict:
    from chain_forecast import supplier_incident                         # step 7c's term, read (not edited) for the waterfall
    cf = supplier_incident(cfg, pd.read_csv(S2_PATH))
    pt = r["paths"]
    tq, nq = str(pd.Timestamp(x["as_of"]).to_period("Q")), _q(r["nordic"], x)
    tq1 = str(pd.Period(tq, "Q") + 1)
    stock = pd.DataFrame(r["stock"].values()).groupby("holder").agg(usd=("usd", "sum"), weeks=("weeks", "max"))
    cov = cfg["event_study"]["holder_cover_anchor"]
    stock = stock.assign(cover_weeks=[x["bounds"].get(cov.get(h, ""), np.nan) for h in stock.index])
    lead = float(np.dot(pt["weight"], pt["lead_weeks"]))
    return {"lead_weeks": lead, "build_weeks": r["d_bar"], "ship_to_build_weeks": lead - r["d_bar"], "content_pct": r["content"] * 100,
            "incident": date_of(r["w0"], x["q0"], x["wq"]).date(), "loss_start": date_of(r["w0"] + r["d_bar"], x["q0"], x["wq"]).date(),
            "restart_sales": date_of(r["wR"], x["q0"], x["wq"]).date(), "restart_ship": date_of(r["wR"] - lead, x["q0"], x["wq"]).date(),
            "gross_total": total(r["nordic"]), "logitech_total": total(r["logitech"]),
            "chain_gross_q": cf["nordic_gross_usdm"], "chain_net_q": cf["nordic_net_usdm"], "chain_pre_incident": _q(r["gross_ship"], x)[:tq].iloc[:-1].sum(),
            "event_q": nq[tq], "event_q1": nq[tq1], "in_guide": x["share_in_guide"] * nq[tq], "net_q": nq[tq] * (1 - x["share_in_guide"]),
            "share_in_guide": x["share_in_guide"], "tq": tq, "tq1": tq1, "nordic_guide_mid": _nordic_guide_mid(cfg),
            "band_q": (bd.loc[tq, "band_low"], bd.loc[tq, "band_high"]), "band_q1": (bd.loc[tq1, "band_low"], bd.loc[tq1, "band_high"]),
            "scen_q": bd.loc[tq, ["downside", "upside"]].to_dict(), "scen_q1": bd.loc[tq1, ["downside", "upside"]].to_dict(),
            "stock": stock, "stock_total": stock["usd"].sum(), "frozen_weeks": r["frozen"],
            "on_order": {w: on_order_share(r, x, w) for w in (cfg["event_study"]["order_lead_weeks_low"], x["bounds"].get("nrf54_leadtime_weeks", np.nan))},
            "customer_cover_weeks": x["customer_cover_weeks"], "named_share": x["named_share"],
            "centroids": {k: centroid(r[k]) for k in ("logitech", "build", "nordic")}}


def event_md(res: dict) -> str:
    s, t = res["summary"], res["table"]
    st = s["stock"]
    over = [h for h, v in st.iterrows() if pd.notna(v["cover_weeks"]) and v["weeks"] > v["cover_weeks"]]
    oo = ", ".join(f"{v:.0%} at a {w:.0f}-week lead" for w, v in s["on_order"].items())
    lines = [
        "", "## 5d. Structural breaks through the chain: shocks vs breaks, and the 2026 supplier incident as a worked event study (G23)", "",
        "A **shock** is a dated change in flow with every edge unchanged: the graph carries it (lead, shares, content). A **break** changes an "
        "edge itself (its lag, share or amplitude) or the reporting basis of a node; then the graph's normal-regime numbers are wrong for that "
        "period and the model must condition on it, exclude it or restate the series. Logitech's 2026 supplier incident is the shock; the same "
        "template (which element changes, which buffer absorbs it, what it does to Nordic's revenue, how the model handles it) is applied to "
        "every event in `config/model.yaml` structural_breaks and regimes below.", "",
        "![supplier incident through the chain](event_study_supplier_incident.svg)", "",
        "Propagation, USD m (`outputs/event_study_supplier_incident.csv`):", "",
        t.round(2).fillna("").to_markdown(index=False), "",
        f"- **Timing.** Lost Logitech sales can only start once the goods built before the incident ({s['incident']}) have sold: "
        f"from {s['loss_start']} (build -> sale {s['build_weeks']:.1f} wk, flow-weighted over E05 / E08). Nordic ships "
        f"{s['lead_weeks']:.1f} weeks before the Logitech sale ({s['ship_to_build_weeks']:.1f} wk to the build), so lost Q3 FY27 sales "
        f"are lost Nordic shipments in {s['tq']}; builds for sales from {s['restart_sales']} need Nordic chips from {s['restart_ship']}.",
        f"- **Stock.** Mapping the lead back puts {-s['chain_pre_incident']:.1f}m of Nordic's effect before the incident (step 7c books only "
        f"the {s['tq']} part, {s['chain_gross_q']:+.1f}m). Those chips, plus deliveries in the {s['frozen_weeks']:.0f}-week frozen window, "
        f"sit at the holder ({-s['stock_total']:.1f}m; up to {st['weeks'].max():.1f} weeks of normal use) and are used first at restart: "
        f"Nordic's gross becomes {s['event_q']:+.1f}m in {s['tq']} and {s['event_q1']:+.1f}m in {s['tq1']}; total {s['gross_total']:+.1f}m "
        f"= {s['content_pct']:.2f}% x {s['logitech_total']:+.0f}m lost Logitech sales (conserved). "
        + ("Stock is within every holder's cover (Logitech raw materials, distributor weeks)." if not over else
           f"Stock exceeds the cover of {', '.join(over)}: that holder would have pushed out more."),
        f"- **Orders.** {oo} of the {s['tq']} cut was already on Nordic's books at the incident: a push-out or a cancellation, "
        f"known when Nordic guided on {res['as_of']} - consistent with the grade-D {s['share_in_guide']:.0%} already in the guide.",
        f"- **Net.** {s['tq']}: {s['event_q']:+.1f}m gross, {s['in_guide']:+.1f}m already in the guide, **{s['net_q']:+.1f}m net** (step 7c: "
        f"{s['chain_net_q']:+.1f}m); band {s['band_q'][0]:+.1f} to {s['band_q'][1]:+.1f}m over edge lags, frozen window and content. "
        f"{s['tq1']}: {s['event_q1']:+.1f}m (band {s['band_q1'][0]:+.1f} to {s['band_q1'][1]:+.1f}; downside {s['scen_q1']['downside']:+.1f}, "
        f"upside {s['scen_q1']['upside']:+.1f} with the channel refilling its ~{s['customer_cover_weeks']:.0f}-week cover) - not in any guide, "
        "and outside the h=2 forecast (GR reads end demand, not dated events).",
        f"- **Size.** The whole incident is {-s['gross_total'] / s['nordic_guide_mid']:.1%} of one quarter of Nordic revenue (guide midpoint "
        f"{s['nordic_guide_mid']:.0f}m): the answer to 'what changed the relationships' is the breaks table below, not this shock.", ""]
    return "\n".join(lines)


def run_event_study(p: pd.DataFrame, cfg: dict, write: bool = True) -> dict:
    """Step 5d: event-study table + band + SVG, then the structural-breaks-through-the-chain table."""
    from event_study_svg import render
    from structural_breaks_chain import breaks_chain, breaks_chain_md
    x = inputs(cfg)
    r = run(cfg, x)
    bd = band(cfg, x)
    res = {"table": propagation_table(cfg, x, r, bd), "summary": summary(cfg, x, r, bd), "run": r, "inputs": x, "band": bd, "as_of": x["as_of"]}
    res = {**res, "svg": render(res)}
    res = {**res, "breaks": breaks_chain(p, cfg, res["summary"])}
    if write:
        d = step_outputs("step5_supply_graph")
        res["table"].round(3).to_csv(d / "event_study_supplier_incident.csv", index=False)
        (d / "event_study_supplier_incident.svg").write_text(res["svg"])
        res["breaks"].to_csv(d / "structural_breaks_chain.csv", index=False)
    res = {**res, "md": event_md(res) + breaks_chain_md(res["breaks"])}
    return res
