"""Step 5 report section and output tables: physical dwell vs order-signal lag (signal_lag.py, decision G25, P86, P100).
Every number and verdict below is computed from the run's tables; nothing is typed in."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

SC = ("low", "mid", "high")
SAMPLE = "ex supply-constrained"


def _r(lo: float, mid: float, hi: float) -> str:
    return f"{mid:.1f} ({lo:.1f}–{hi:.1f})"


def edges_df(t: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"edge": t["edge_id"] + " " + t["src"] + " → " + t["dst"], "brand": t["brand"],
                         "buyer's planning decision": t["info_delay_planner"].replace("", "none (sell-out)"),
                         **{f"{lab} wk mid (low–high)": [_r(*(r[f"{c}_{x}"] for x in SC)) for _, r in t.iterrows()]
                            for lab, c in (("physical", "physical_weeks"), ("info delay", "info_weeks"), ("signal", "signal_weeks"))}})


def routes_df(res: dict) -> pd.DataFrame:
    """One row per route: scenario low / mid / high and the Monte Carlo 90% band on each basis, the paired add-on."""
    rt, mc = res["routes"].set_index(["basis", "scenario"]), res["mc"].set_index(["basis", "route"])
    band = lambda b, k: f"{mc.loc[(b, k), 'p5']:.1f}–{mc.loc[(b, k), 'p95']:.1f}"    # noqa: E731
    rows = []
    for k in [c for c in rt.columns]:
        rows.append({"route": k, "physical wk mid (low–high)": _r(*(rt.loc[("physical", x), k] for x in SC)),
                     "physical MC 90%": band("physical", k),
                     "signal wk mid (low–high)": _r(*(rt.loc[("signal", x), k] for x in SC)), "signal MC 90%": band("signal", k),
                     "info delay add-on, MC p50 (90%)": f"{mc.loc[('info delay (signal - physical)', k), 'p50']:.1f} ({band('info delay (signal - physical)', k)})",
                     "signal, smoothing only (R/2 dropped)": round(float(rt.loc[("signal, smoothing only", "mid"), k]), 1)})
    return pd.DataFrame(rows)


def _inside(x: float, lo: float, hi: float) -> str:
    return "inside" if lo <= x <= hi else ("below" if x < lo else "above")


def consistency_df(res: dict, cfg: dict) -> pd.DataFrame:
    """Like with like: total vs step 4's reasoned lag and the sell-out-proxy driver's near-optimal set; upstream (Nordic ->
    brand) vs the sell-in driver's near-optimal set (P86). A check on consistency, not a fit."""
    st = res["stages"].set_index("basis")
    lw = cfg["lag_weeks"]
    s4 = {x: float(sum(v[x] for v in lw.values())) for x in SC}
    refs = [("total vs step 4 reasoned (config lag_weeks)", "total_weeks", s4["low"], s4["high"], f"{s4['mid']:.0f} ({s4['low']:.0f}–{s4['high']:.0f})")]
    c = res.get("continuous")
    if c is not None and len(c):
        for kind, col in (("sell-in", "upstream_weeks"), ("sell-out proxy", "total_weeks")):
            r = c[(c["kind"] == kind) & (c["sample"] == SAMPLE)]
            if len(r):
                r = r.iloc[0]
                what = "upstream (Nordic → brand)" if col == "upstream_weeks" else "total"
                refs.append((f"{what} vs data: {kind} driver's near-optimal set (n {int(r['n'])}, one cycle)", col,
                             float(r["near_optimal_lo_weeks"]), float(r["near_optimal_hi_weeks"]),
                             f"{r['near_optimal_lo_weeks']:.1f}–{r['near_optimal_hi_weeks']:.1f}"))
    return pd.DataFrame([{"comparison": name, "reference wk": txt, "physical wk": round(st.loc["physical", col], 1),
                          "physical is": _inside(st.loc["physical", col], lo, hi), "signal wk": round(st.loc["signal", col], 1),
                          "signal is": _inside(st.loc["signal", col], lo, hi)} for name, col, lo, hi, txt in refs])


def section_md(res: dict, cfg: dict) -> str:
    sg = cfg["supply_graph"]
    rt = res["routes"].set_index(["basis", "scenario"])
    all_ = rt.columns[-1]
    ph, si = rt.loc[("physical", "mid"), all_], rt.loc[("signal", "mid"), all_]
    cons = consistency_df(res, cfg)
    top = res["tornado"].iloc[0]
    return "\n".join([
        "## Physical dwell vs order-signal lag (decision G25; pitfalls P86, P100)\n",
        "The edge lags above are **physical dwell** times (how long a unit sits in each stock; Little's-law capped by inventory cover). "
        "A demand change travels upstream as an **order signal**: on every edge the buyer's planning decision adds a delay that holds "
        "no stock. Textbook periodic review with an exponentially smoothed forecast: delay = R/2 (wait for the next review) + "
        "(1 − α)/α × R (mean age of the smoothed forecast), R in weeks. Planners and which edge carries which: "
        "`config/model.yaml` → `supply_graph.info_delay`, `config/supply_graph.csv` → `info_delay_planner`. No company discloses its "
        "cadence: grade D, so each planner's range is ±100% of its mid (low end = no delay) and it is never capped by inventory cover.\n",
        res["planners"].drop(columns="source").round(2).to_markdown(index=False), "",
        "Per edge (effective ranges; E14 mixes the residual's distributor routes, G20):\n", edges_df(res["edges"]).to_markdown(index=False), "",
        f"**Per route** (scenario = every edge and planner at its low / mid / high; Monte Carlo {sg['mc_draws']} paired draws, each planner "
        "drawn once per draw so one S&OP moves all its edges together):\n", routes_df(res).to_markdown(index=False), "",
        f"Flow-weighted, the order signal takes **{si:.1f} weeks** against {ph:.1f} weeks of physical dwell. "
        "The smoothing-only column drops R/2 (the cycle stock of a periodic review may already sit in the cover, P100): the lower end of "
        "what the information delay adds.\n",
        "**Consistency check, not a fit** (like with like, P86: a sell-in driver measures the upstream segment only):\n",
        cons.to_markdown(index=False), "",
        "Which inputs move the signal lag most (flow-weighted; swing low → high, all else at mid; share swings in the table above):\n",
        res["tornado"].head(8).round(2).to_markdown(index=False), "",
        f"The largest single input is {top['input']} ({top['swing_weeks']:.1f} weeks of swing, grade {top['grade']}).\n",
        f"**Which basis where.** The lag answer (this section, step 4's edge priors) uses `supply_graph.lag_answer_basis = "
        f"{sg.get('lag_answer_basis', 'signal')}`. The forecasting path (propagate: step 6 GR / GRg, the 6c graph factor, step 7c and "
        f"the Q4 line) reads `supply_graph.lag_basis = {sg.get('lag_basis', 'physical')}`; switching it re-times a pre-registered "
        "challenger whose fingerprint does not cover the graph (P101), so the switch is the lead's call (decision G25 has the "
        "measured effect). The event study (5d) stays physical by construction: a supply shock moves goods already in the pipe; "
        "how fast orders are cut is modelled there by the frozen window and the lead time.\n"])


def write(res: dict, d: Path) -> None:
    res["planners"].round(3).to_csv(d / "graph_info_delay_planners.csv", index=False)
    res["edges"].round(3).to_csv(d / "graph_signal_lag_edges.csv", index=False)
    res["routes"].round(2).to_csv(d / "graph_signal_lag_routes.csv", index=False)
    res["mc"].round(2).to_csv(d / "graph_signal_lag_mc.csv", index=False)
    res["stages"].round(2).to_csv(d / "graph_signal_lag_stages.csv", index=False)
    res["tornado"].round(2).to_csv(d / "graph_signal_tornado.csv", index=False)
