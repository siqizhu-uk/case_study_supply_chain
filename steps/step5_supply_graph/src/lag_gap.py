"""Step 5 vs step 4 (decision G21, check only): why step 4's measured lag (~2 quarters) is longer than both reasoned lags.
Builds the continuous-lag table (continuous_lag.py) for step 4's driver, the graph's driver and drivers outside the chain,
and renders the report subsection together with the gap decomposition (gap_decomposition.py).

Like with like: step 4's driver (Logitech radio-core revenue) is Logitech SELL-IN, so its lag to Nordic is the UPSTREAM part
of the chain (graph ~14 weeks, step 4 15); only the sell-out proxy (sell-in + disclosed sell-through gap) compares with
the total (graph ~19, step 4 22).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from continuous_lag import block_indices, common_axis, estimate, tau_grid

STEP4 = "step 4 driver"


def drivers(p: pd.DataFrame, cfg: dict) -> list[tuple[str, str, pd.Series]]:
    """(name, kind, series): the two chain drivers, then the controls from config."""
    d = cfg["regression"]["driver"]
    out = [(f"{STEP4} ({d}): Logitech radio-core revenue", "sell-in", p[d]),
           ("graph driver: Logitech sell-in + sell-through gap", "sell-out proxy", p["logi_sales_yoy"] + p["logi_st_gap"])]
    return out + [(f"control: {label}", "control", p[col]) for col, label in cfg["supply_graph"]["lag_check"]["controls"].items()]


def references(s4: pd.DataFrame) -> dict:
    """Weeks the CIs are checked against, read from the step 4 comparison table (graph_vs_step4.csv)."""
    tot, up = s4.iloc[0], s4.iloc[1]
    return {"graph_upstream": float(up["graph_mid"]), "graph_total": float(tot["graph_mid"]),
            "step4_upstream": float(up["step4_mid"]), "step4_total": float(tot["step4_mid"])}


def _ci(draws: np.ndarray, lc: dict, wq: float) -> tuple[float, float]:
    ok = draws[~np.isnan(draws)]
    lo, hi = np.quantile(ok, lc["ci"]) if len(ok) else (np.nan, np.nan)
    return float(lo * wq), float(hi * wq)


def _paired_diff(y: pd.Series, x: pd.Series, x4: pd.Series, keep: pd.Index, lc: dict, wq: float) -> dict:
    """tau(control) - tau(step 4 driver) on the quarters both have, with the same bootstrap draws for both."""
    axis = common_axis(y, [x, x4], keep, tau_grid(lc))
    idx = block_indices(len(axis), lc["block_len"], lc["boot_draws"], lc["seed"])
    a, b = estimate(y, x, axis, lc, idx), estimate(y, x4, axis, lc, idx)
    lo, hi = _ci(a["boot"] - b["boot"], lc, wq)
    return {"diff_vs_step4_driver_weeks": (a["tau_q"] - b["tau_q"]) * wq, "diff_ci_lo_weeks": lo, "diff_ci_hi_weeks": hi,
            "diff_n": len(axis), "step4_driver_tau_weeks_same_quarters": b["tau_q"] * wq}


def _row(name: str, kind: str, x: pd.Series, y: pd.Series, keep: pd.Index, lc: dict, wq: float, ref: dict) -> dict:
    axis = common_axis(y, [x], keep, tau_grid(lc))
    e = estimate(y, x, axis, lc, block_indices(len(axis), lc["block_len"], lc["boot_draws"], lc["seed"]))
    lo, hi = _ci(e["boot"], lc, wq)
    like = {"sell-in": ("graph_upstream", "step4_upstream"), "sell-out proxy": ("graph_total", "step4_total")}.get(kind)
    inside = lambda w: bool(lo <= w <= hi)   # noqa: E731
    return {"driver": name, "kind": kind, "first_quarter": str(axis[0]) if len(axis) else "", "n": len(axis),
            "tau_q": e["tau_q"], "tau_weeks": e["tau_q"] * wq, "corr": e["corr"], "ci_lo_weeks": lo, "ci_hi_weeks": hi,
            "near_optimal_lo_weeks": e["near_lo_q"] * wq, "near_optimal_hi_weeks": e["near_hi_q"] * wq,
            "near_optimal_contiguous": e["near_contiguous"],
            "like_graph_weeks": ref[like[0]] if like else np.nan, "like_step4_weeks": ref[like[1]] if like else np.nan,
            "like_graph_in_ci": inside(ref[like[0]]) if like else None, "like_step4_in_ci": inside(ref[like[1]]) if like else None,
            "graph_upstream_in_ci": inside(ref["graph_upstream"]), "graph_total_in_ci": inside(ref["graph_total"]),
            "step4_total_in_ci": inside(ref["step4_total"])}


def continuous_lag_table(p: pd.DataFrame, cfg: dict, s4: pd.DataFrame) -> pd.DataFrame:
    """One row per driver x sample: continuous tau, bootstrap CI (weeks), which reference lags the CI contains, and for
    controls the paired difference to step 4's driver."""
    lc, wq, ref = cfg["supply_graph"]["lag_check"], cfg["supply_graph"]["weeks_per_quarter"], references(s4)
    y = p["nordic_consumer_yoy"]
    samples = {"all quarters": p.index, "ex supply-constrained": p.index[p["regime"] != "supply_constrained"]}
    dv = drivers(p, cfg)
    x4 = dv[0][2]
    rows = []
    for sn, keep in samples.items():
        for name, kind, x in dv:
            r = {"sample": sn, **_row(name, kind, x, y, keep, lc, wq, ref)}
            rows.append({**r, **(_paired_diff(y, x, x4, keep, lc, wq) if kind == "control" else {})})
    return pd.DataFrame(rows)


def _yes(b) -> str:
    return "yes" if b is True else "no" if b is False else ""


def _table_md(cl: pd.DataFrame) -> str:
    t = pd.DataFrame({
        "driver": cl["driver"], "sample": cl["sample"], "n (from)": cl["n"].astype(str) + " (" + cl["first_quarter"] + ")",
        "tau, weeks": cl["tau_weeks"].round(1), "corr": cl["corr"].round(2),
        "90% CI, weeks": cl["ci_lo_weeks"].round(1).astype(str) + "-" + cl["ci_hi_weeks"].round(1).astype(str),
        "near-optimal tau, weeks": cl["near_optimal_lo_weeks"].round(1).astype(str) + "-" + cl["near_optimal_hi_weeks"].round(1).astype(str)
        + cl["near_optimal_contiguous"].map({False: " (gaps)"}).fillna(""),
        "like-with-like graph lag in CI": [f"{w:.1f}: {_yes(b)}" if pd.notna(w) else "" for w, b in zip(cl["like_graph_weeks"], cl["like_graph_in_ci"])],
        "graph upstream in CI": cl["graph_upstream_in_ci"].map(_yes), "graph total in CI": cl["graph_total_in_ci"].map(_yes),
        "step 4 total in CI": cl["step4_total_in_ci"].map(_yes)})
    if "diff_vs_step4_driver_weeks" in cl:
        d = cl["diff_vs_step4_driver_weeks"]
        t["minus step 4 driver, weeks (90% CI; n)"] = [
            "" if pd.isna(v) else f"{v:+.1f} ({lo:+.1f} to {hi:+.1f}; {int(n)})"
            for v, lo, hi, n in zip(d, cl["diff_ci_lo_weeks"], cl["diff_ci_hi_weeks"], cl["diff_n"])]
    return t.to_markdown(index=False)


def _dec_text(dec: pd.DataFrame) -> str:
    c = dec.set_index("group")["contribution_weeks"]
    nature = dec.set_index("group")["nature"].str.split(":").str[0]
    by = {k: float(c[nature == k].sum()) for k in ("structure", "data bound", "judgment", "GN (upstream + downstream)")}
    tot = dec.iloc[-1]
    return (f"The {tot['contribution_weeks']:+.2f}-week gap: structure read from A-graded 10-K facts (Amazon bought direct, "
            f"in-house Suzhou builds skip the ODM) {by['structure']:+.2f}; the inventory-cover bound on the distributor route "
            f"{by['data bound']:+.2f}; the judgment p = {dec['p_residual_via_dist'].iloc[0]:.2f} on Logitech's 10-K residual "
            f"{by['judgment']:+.2f} (zero at p = 1); GN {by['GN (upstream + downstream)']:+.2f}. Upstream and downstream rows "
            "cover the same flow, so the flow shares do not add to 1; the contributions add to the gap.\n")


def _where(flags: pd.Series) -> str:
    k, m = int(flags.astype(bool).sum()), len(flags)
    return "inside the 90% CI in every sample" if k == m else "outside the 90% CI in every sample" if k == 0 else f"inside the 90% CI in {k} of {m} samples"


def _span(s: pd.Series, fmt: str = ".0f") -> str:
    lo, hi = s.min(), s.max()
    return f"{lo:{fmt}}" if abs(hi - lo) < 0.5 else f"{lo:{fmt}}-{hi:{fmt}}"


def _cis(rows: pd.DataFrame) -> str:
    return ", ".join(f"{r.ci_lo_weeks:.0f}-{r.ci_hi_weeks:.0f} ({r.sample})" for r in rows.itertuples())


def _controls(ct: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Per control: a sentence, and the names whose tau cannot be told from the step 4 driver's in every sample."""
    lines, same = [], []
    for name, g in ct.groupby("driver", sort=False):
        zero = (g["diff_ci_lo_weeks"] <= 0) & (g["diff_ci_hi_weeks"] >= 0)
        label = name.removeprefix("control: ").split(" (")[0]
        same += [label] if zero.all() else []
        lines.append(f"  - {label} (n {_span(g['n'].astype(float))} from {g['first_quarter'].min()}): Nordic lags it by "
                     f"{_span(g['tau_weeks'])} weeks (CI {_cis(g)}); minus the step 4 driver's tau on the "
                     f"same {_span(g['diff_n'].astype(float))} quarters: {_span(g['diff_vs_step4_driver_weeks'], '+.0f')} weeks, "
                     f"zero inside the 90% CI in {int(zero.sum())} of {len(g)} samples.")
    return lines, same


def _flat(si: pd.DataFrame, lc: dict) -> str:
    """The near-optimal set of the sell-in driver and why its point estimate is not a lag (P86)."""
    sets = ", ".join(f"{r.near_optimal_lo_weeks:.0f}-{r.near_optimal_hi_weeks:.0f} ({r.sample})" for r in si.itertuples())
    return (f"- **Flat surface: the data do not pin the lag.** Every tau whose correlation is within {lc['near_optimal_corr_gap']} of the "
            f"maximum (the near-optimal set, column above): sell-in {sets} weeks, on {_span(si['n'].astype(float))} quarters of one "
            "down-up cycle. The point estimate must not be quoted as a lag: between two integer lags the interpolated driver is a "
            "2-tap moving average, and a smoother regressor correlates more with a smooth YoY target, so fractional taus are "
            "favoured (interpolation smoothing bias). Step 4's integer '2 quarters' had no band at all; the set and the CI are the "
            "honest reading.")


def _cover_state(p: pd.DataFrame) -> str:
    inv = p["logi_inv_days"].dropna()
    turn = inv[p.loc[inv.index, "regime"] != "normal"]
    if turn.empty:
        return ""
    q, last = turn.idxmax(), inv.index[-1]
    if turn.max() <= inv.iloc[-1]:
        return f"- **The cover.** Logitech's inventory cover in the cycle turn never exceeded its {last} level ({inv.iloc[-1]:.0f} days)."
    return (f"- **The cover itself moved.** Logitech's inventory cover, which caps the ODM -> Logitech edge (E08), was {turn.max():.0f} days "
            f"({turn.max() / 7:.0f} weeks) in {q} against {inv.iloc[-1]:.0f} days ({inv.iloc[-1] / 7:.1f} weeks) in {last}, the level the graph "
            "uses: in the cycle turn that carries the correlation the physical dwell time was itself longer than the graph's.")


def _conclusion(si: pd.DataFrame, same: list[str], n: str) -> str:
    excess = not si["like_graph_in_ci"].astype(bool).any()
    if excess and same:
        return (f"- **Reading.** The sell-in peak is longer than the physical chain it measures, and Nordic lags {' and '.join(same)} - "
                "which carry no or almost no Logitech orders - by a lag that cannot be told from it. So the ~2-quarter peak cannot be read "
                "as the Logitech -> Nordic order lag: it is consistent with the timing of the consumer-electronics / semiconductor cycle "
                "at Nordic (Logitech + GN are a small slice of Nordic, step 2), plus order-signal delay (below). It is not evidence "
                f"against the graph's edge lags, and {n} quarters cannot test those edge lags either.")
    if excess:
        return ("- **Reading.** The sell-in peak is longer than the physical chain and no control shows the same lag: the excess looks "
                "chain-specific, and order-signal delay (below) is the leading candidate.")
    return ("- **Reading.** The graph's upstream lag lies inside the sell-in driver's CI in at least one sample: the measured peak is "
            "within sampling noise of the physical chain.")


def gap_section(s4: dict, p: pd.DataFrame, cfg: dict) -> str:
    """Report subsection; s4 = step4_check.compare() output plus 'decomposition' and 'continuous'."""
    dec, cl = s4["decomposition"], s4["continuous"]
    lc, ref = cfg["supply_graph"]["lag_check"], references(s4["table"])
    peak = float(s4["data"].iloc[0]["best_lag_weeks"])
    si, so, ct = (cl[cl["kind"] == k] for k in ("sell-in", "sell-out proxy", "control"))
    ctl, same = _controls(ct)
    return "\n".join([
        "### Why the measured lag is longer: gap by route, like with like, continuous lag (check only, decision G21)\n",
        "**The gap by route group** (`graph_vs_step4_decomposition.csv`). Each row is flow x (graph weeks - reference weeks):\n",
        dec.drop(columns="p_residual_via_dist").round(3).to_markdown(index=False), "", _dec_text(dec),
        f"**Like with like.** Step 4's driver (`{cfg['regression']['driver']}`) is Logitech's reported revenue, i.e. sell-in. A chip order "
        "that follows Logitech's sell-in crosses only the upstream part of the chain, so its lag compares with the graph's upstream "
        f"{ref['graph_upstream']:.1f} weeks (step 4's own upstream {ref['step4_upstream']:.0f}), not with the totals "
        f"{ref['graph_total']:.1f} / {ref['step4_total']:.0f}. Against that, step 4's integer peak ({peak:.0f} weeks) is "
        f"{peak - ref['graph_upstream']:.0f} weeks longer than the chain it measures, not {peak - ref['graph_total']:.0f}. Only the graph's driver "
        "(sell-in + disclosed sell-through gap, a sell-out proxy) compares with the total.\n",
        f"**Continuous lag** (`graph_vs_step4_continuous_lag.csv`). Integer quarters of YoY growth cannot resolve weeks. tau runs 0-"
        f"{lc['tau_max_q']:.0f} quarters in steps of {lc['tau_step_q']}, the driver interpolated linearly between neighbouring quarters; "
        "tau maximises the correlation with Nordic consumer YoY on one fixed sample per driver (the quarters where every tau is defined, "
        f"so the peak cannot come from quarters entering the sample); 90% CI from a moving-block bootstrap ({lc['boot_draws']} draws, "
        f"blocks of {lc['block_len']} quarters, seed {lc['seed']}). Controls are differenced from the step 4 driver on the quarters both "
        "have, with the same draws.\n",
        _table_md(cl), "",
        f"- **Sell-in (step 4's driver):** tau {_span(si['tau_weeks'])} weeks, CI {_cis(si)}. The graph's upstream "
        f"{ref['graph_upstream']:.1f} weeks is {_where(si['like_graph_in_ci'])}; step 4's upstream {ref['step4_upstream']:.0f} is "
        f"{_where(si['like_step4_in_ci'])}.",
        f"- **Sell-out proxy (the graph's driver):** tau {_span(so['tau_weeks'])} weeks, CI {_cis(so)}: the graph's total "
        f"{ref['graph_total']:.1f} is {_where(so['like_graph_in_ci'])} and step 4's {ref['step4_total']:.0f} "
        f"{_where(so['step4_total_in_ci'])} - this driver cannot tell the lags apart.",
        _flat(si, lc), "- **Common cycle** (drivers outside the Logitech -> Nordic chain):", *ctl, _cover_state(p), _conclusion(si, same, _span(cl["n"].astype(float))), "",
        "**Physical dwell time vs order signal (known limitation, not fixed).** The graph's edge lags are capped by inventory cover "
        "(Little's law: the mean time a unit sits in stock). The order signal that moves Nordic's revenue travels with delays that hold "
        "no stock: demand forecasts smoothed over several periods, monthly S&OP and quarterly build plans, order batching, and the chip "
        "lead time between order and shipment. Under order-up-to replenishment with exponentially smoothed forecasts (the bullwhip "
        "literature: Lee, Padmanabhan & Whang 1997; Chen, Drezner, Ryan & Simchi-Levi 2000) orders respond to demand late by about the "
        "forecast's mean age, and amplified. A lag measured on revenue correlations should therefore exceed the dwell-time lag. "
        "Nothing is changed (G21): the graph's edge lags stay physical, step 4's `lag_weeks` stays the documented prior, and the "
        "2-quarter correlation peak is read as an envelope that mixes order delay, cover that was higher at the turn, and the common "
        "cycle - not as the chain's lag.\n"])
