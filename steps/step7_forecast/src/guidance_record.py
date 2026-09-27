"""Guidance track record of Nordic, Logitech and GN: how accurate each company's guidance is and whether it guides
conservatively (actual above the midpoint) or aggressively (below). The forecasts anchor on these guides, so this is the
evidence behind each anchor's uplift and range width (step 7, decision F12; shown on the dashboard).

Guide types, each scored in its own units:
    Nordic    quarterly revenue range, given with the previous quarter's report          error = actual / midpoint - 1 (%)
              quarterly gross-margin floor ('above 50%')                                  error = actual - floor (pts)
    Logitech  annual outlook FY2019-FY2026 (cc growth to FY23, USD sales from FY24),       first statement vs outcome, and
              revised during the year; H1 FY24; quarterly ranges from Q1 FY26            each revision's direction
    GN        annual organic growth and EBITA margin, revised during the year              first statement vs outcome
Label rule, stated before the numbers: 'conservative' if the mean error is > 0 and >= 70% of outcomes land at or above the
midpoint; 'aggressive' if < 0 and >= 70% below; otherwise 'mixed'. With fewer than 4 outcomes the label is 'too few'.
"""
from __future__ import annotations

import html

import numpy as np
import pandas as pd

from core.config import ROOT

RAW = ROOT / "pipelines" / "A_company_financials" / "data" / "raw"
LOGI_HIST, GN_HIST = RAW / "logitech_guidance_history.csv", RAW / "gn_guidance_history.csv"
UNIT = {"sales_growth_cc_pct": "pts", "organic_growth_pct": "pts", "ebita_margin_pct": "pts", "ebit_margin_pct": "pts",
        "sales_usdm": "%", "op_income_usdm": "%"}


MIN_MONTHS_AHEAD = 6       # a 'first statement' counts as an initial guide only if made >= 6 months before the period ends


def period_end(period) -> pd.Timestamp:
    """Logitech FY2024 ends 31 Mar 2024, H1FY2024 on 30 Sep 2023; GN fiscal year 2024 (int) on 31 Dec 2024."""
    s = str(period)
    if s.startswith("H1FY"):
        return pd.Timestamp(f"{int(s[4:]) - 1}-09-30")
    if s.startswith("FY"):
        return pd.Timestamp(f"{int(s[2:])}-03-31")
    return pd.Timestamp(f"{int(float(s))}-12-31")


def _err(metric: str, actual: float, mid: float) -> float:
    return (actual / mid - 1) * 100 if UNIT.get(metric) == "%" else actual - mid


def label(errors: pd.Series) -> str:
    e = errors.dropna()
    if len(e) < 4:
        return "too few"
    up = float((e >= 0).mean())
    if e.mean() > 0 and up >= 0.7:
        return "conservative"
    if e.mean() < 0 and up <= 0.3:
        return "aggressive"
    return "mixed"


# ------------------------------------------------------------------ quarterly guides
def nordic_quarters(p: pd.DataFrame) -> pd.DataFrame:
    raw = pd.read_csv(RAW / "nordic_quarterly.csv")
    raw.index = pd.PeriodIndex(raw["quarter"], freq="Q")
    d = raw[["guide_low_usdm", "guide_high_usdm", "revenue_usdm", "guide_gm_pct", "gm_pct"]].dropna(subset=["guide_low_usdm"])
    d = d.assign(mid=(d["guide_low_usdm"] + d["guide_high_usdm"]) / 2)
    d["error_pct"] = (d["revenue_usdm"] / d["mid"] - 1) * 100
    d["in_range"] = d["revenue_usdm"].between(d["guide_low_usdm"], d["guide_high_usdm"])
    d["gm_vs_floor_pts"] = d["gm_pct"] - d["guide_gm_pct"]
    d["regime"] = p["regime"].reindex(d.index) if "regime" in p else ""
    return d


def logitech_quarters() -> pd.DataFrame:
    raw = pd.read_csv(RAW / "logitech_quarterly.csv")
    raw.index = pd.PeriodIndex(raw["quarter"], freq="Q")
    d = raw[["fiscal_label", "guide_low_usdm", "guide_high_usdm", "net_sales_usdm"]].dropna(subset=["guide_low_usdm"])
    d = d.assign(mid=(d["guide_low_usdm"] + d["guide_high_usdm"]) / 2)
    d["error_pct"] = (d["net_sales_usdm"] / d["mid"] - 1) * 100
    d["in_range"] = d["net_sales_usdm"].between(d["guide_low_usdm"], d["guide_high_usdm"])
    return d


# ------------------------------------------------------------------ annual guides with revisions
def annual(hist: pd.DataFrame, period_col: str, scope_col: str | None = None) -> pd.DataFrame:
    """Per (period, metric[, scope]): first statement, last statement, outcome, error of each vs the outcome, revisions."""
    keys = [period_col, "metric"] + ([scope_col] if scope_col else [])
    h = hist.sort_values("statement_date")
    rows = []
    for k, g in h.groupby(keys):
        k = k if isinstance(k, tuple) else (k,)
        act = g[g["action"] == "actual"]
        gd = g[(g["action"] != "actual") & g["low"].notna()]
        if gd.empty:
            continue
        first, last = gd.iloc[0], gd.iloc[-1]
        a = float(act["low"].iloc[-1]) if len(act) else np.nan
        fm, lm = (first["low"] + first["high"]) / 2, (last["low"] + last["high"]) / 2
        months = (period_end(k[0]) - pd.Timestamp(first["statement_date"])).days / 30.44
        rows.append({**dict(zip(keys, k)), "unit": UNIT.get(k[1], ""), "first_date": first["statement_date"],
                     "months_ahead": round(months, 1), "initial": months >= MIN_MONTHS_AHEAD, "first_low": first["low"],
                     "first_high": first["high"], "last_date": last["statement_date"], "last_low": last["low"], "last_high": last["high"],
                     "actual": a, "n_statements": len(gd), "raised": int((gd["action"] == "raised").sum()),
                     "lowered": int((gd["action"] == "lowered").sum()), "withdrawn": bool((g["action"] == "withdrawn").any()),
                     "first_error": _err(k[1], a, fm) if pd.notna(a) else np.nan,
                     "first_error_level_pct": (((1 + a / 100) / (1 + fm / 100) - 1) * 100 if k[1] == "sales_growth_cc_pct" else _err(k[1], a, fm))
                     if pd.notna(a) else np.nan,
                     "last_error": _err(k[1], a, lm) if pd.notna(a) else np.nan,
                     "first_in_range": bool(first["low"] <= a <= first["high"]) if pd.notna(a) else None})
    return pd.DataFrame(rows)


def logitech_annual() -> pd.DataFrame:
    if not LOGI_HIST.exists():
        return pd.DataFrame()
    h = pd.read_csv(LOGI_HIST)
    return annual(h[~h["period"].str.startswith("Q")], "period")


def gn_headline(h: pd.DataFrame) -> pd.DataFrame:
    """One scope per fiscal year and metric: the group guide where GN gives one, else the Audio division (headsets and
    speakerphones - the part of GN in this case; group guides start 2023 for organic growth, 2024 for the margin).
    Actual rows on a basis other than the guide's (GN's note says 'NOT the ... guide basis') are dropped. Open-ended
    guides ('at least 20%') have high = low."""
    h = h[~((h["action"] == "actual") & h["note"].fillna("").str.contains("NOT the", case=False))].copy()
    h["high"] = h["high"].where(h["high"].notna() | h["low"].isna(), h["low"])
    keep = []
    for (fy, m), g in h[h["metric"].isin(["organic_growth_pct", "ebita_margin_pct"])].groupby(["fiscal_year", "metric"]):
        scopes = set(g["scope"])
        use = {"group", "continuing_ops"} & scopes or ({"audio"} & scopes)
        keep.append(g[g["scope"].isin(use)])
    out = pd.concat(keep) if keep else h.iloc[0:0]
    out["scope"] = out["scope"].replace({"continuing_ops": "group"})   # 2026: guide moved to continuing ops mid-year (basis change, kept in note)
    return out


def gn_annual() -> pd.DataFrame:
    if not GN_HIST.exists():
        return pd.DataFrame()
    return annual(gn_headline(pd.read_csv(GN_HIST)), "fiscal_year", "scope")


# ------------------------------------------------------------------ summary
def summary(p: pd.DataFrame) -> pd.DataFrame:
    rows = []
    nq = nordic_quarters(p).dropna(subset=["revenue_usdm"])     # a guide not yet reported has no error: not a miss
    for reg, g in [("all", nq)] + list(nq.groupby("regime")):
        rows.append({"company": "Nordic", "guide": f"quarterly revenue range ({reg})", "unit": "%", "n": len(g),
                     "mean_error": g["error_pct"].mean(), "median_error": g["error_pct"].median(), "sd_error": g["error_pct"].std(ddof=1), "share_at_or_above_mid": (g["error_pct"] >= 0).mean(),
                     "share_in_range": g["in_range"].mean(), "label": label(g["error_pct"])})
    gm = nq["gm_vs_floor_pts"].dropna()
    rows.append({"company": "Nordic", "guide": "quarterly gross-margin floor", "unit": "pts", "n": len(gm), "mean_error": gm.mean(), "median_error": gm.median(),
                 "sd_error": gm.std(ddof=1), "share_at_or_above_mid": (gm >= 0).mean(), "share_in_range": (gm >= 0).mean(), "label": label(gm)})
    lq = logitech_quarters()
    lq = lq[lq["net_sales_usdm"].notna()]
    rows.append({"company": "Logitech", "guide": "quarterly sales range (from Q1 FY26)", "unit": "%", "n": len(lq), "mean_error": lq["error_pct"].mean(), "median_error": lq["error_pct"].median(),
                 "sd_error": lq["error_pct"].std(ddof=1), "share_at_or_above_mid": (lq["error_pct"] >= 0).mean(),
                 "share_in_range": lq["in_range"].mean(), "label": label(lq["error_pct"])})
    for name, a in (("Logitech", logitech_annual()), ("GN", gn_annual())):
        if a.empty:
            continue
        a = a[a["actual"].notna() & a["initial"]].copy()     # late first statements (e.g. one quarter left) are not initial guides
        if name == "Logitech":                                # cc growth guide (to FY23) and USD sales guide (from FY24): one sales series,
            a["metric"] = a["metric"].replace({"sales_growth_cc_pct": "sales", "sales_usdm": "sales"})   # error as % of the guided level
            a["first_error"], a["unit"] = a["first_error_level_pct"], "%"
        for metric, g in a.groupby("metric"):
            scope = f", {'/'.join(sorted(g['scope'].unique()))}" if "scope" in g else ""
            rows.append({"company": name, "guide": f"annual {metric}{scope}: initial guide (>= {MIN_MONTHS_AHEAD} months ahead)", "unit": g["unit"].iloc[0], "n": len(g),
                         "mean_error": g["first_error"].mean(), "median_error": g["first_error"].median(), "sd_error": g["first_error"].std(ddof=1),
                         "share_at_or_above_mid": (g["first_error"] >= 0).mean(), "share_in_range": g["first_in_range"].mean(),
                         "label": label(g["first_error"]), "revisions_up": int(g["raised"].sum()), "revisions_down": int(g["lowered"].sum())})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ html
def conclusions(s: pd.DataFrame) -> list[str]:
    """One computed sentence per company."""
    out = []
    for c, g in s.groupby("company", sort=False):
        best = g.sort_values("n", ascending=False)
        parts = [f"{r.guide}: {r.label} (median {r.median_error:+.1f} {r.unit}, mean {r.mean_error:+.1f}, sd {r.sd_error:.1f}, n={r.n}, in range {r.share_in_range:.0%})"
                 for r in best.itertuples() if pd.notna(r.mean_error)]
        out.append(f"<b>{c}</b> — " + "; ".join(parts[:3]))
    return out


def section_html(p: pd.DataFrame) -> str:
    from guidance_viz import charts_html          # guidance_viz imports this module
    s = summary(p)
    cols = ["company", "guide", "unit", "n", "mean_error", "median_error", "sd_error", "share_at_or_above_mid", "share_in_range", "label"]
    tab = s[cols].copy()
    for c in ("share_at_or_above_mid", "share_in_range"):
        tab[c] = tab[c].map(lambda v: f"{v:.0%}" if pd.notna(v) else "")
    for c in ("mean_error", "median_error", "sd_error"):
        tab[c] = tab[c].map(lambda v: f"{v:+.1f}" if pd.notna(v) else "")
    head = "".join(f"<th>{html.escape(c)}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in r) + "</tr>" for r in tab.values)
    rev = []
    for name, a in (("Logitech", logitech_annual()), ("GN", gn_annual())):
        for r in a.itertuples():
            scope = f" {r.scope}" if hasattr(r, "scope") else ""
            period = getattr(r, "period", getattr(r, "fiscal_year", ""))
            path = f"{r.first_low:g}–{r.first_high:g} → {r.last_low:g}–{r.last_high:g}"
            act = "" if pd.isna(r.actual) else f"{r.actual:g}"
            late = "" if r.initial else f" (first statement {r.months_ahead:g} months before period end: not an initial guide)"
            rev.append(f"<tr><td>{name}</td><td>{period}</td><td>{r.metric}{scope}{late}</td><td>{path}</td><td>{r.raised}↑ {r.lowered}↓{' withdrawn' if r.withdrawn else ''}</td>"
                       f"<td>{act}</td><td>{'' if pd.isna(r.first_error) else f'{r.first_error:+.1f} {r.unit}'}</td></tr>")
    from core.config import load_config
    cfg = load_config()
    at = anchor_table(p, cfg)
    reg_now = cfg["forecast"]["nordic_2026Q3"].get("regime", "normal")
    used = {"Nordic": at[(at["company"] == "Nordic") & at["window"].str.startswith(reg_now)], "Logitech": at[at["company"] == "Logitech"],
            "GN": at[at["company"] == "GN"]}
    fc = cfg["forecast"]
    gl = gn_headline(pd.read_csv(GN_HIST)) if GN_HIST.exists() else pd.DataFrame(columns=["metric", "action", "low", "statement_date", "high"])
    gl = gl[(gl["metric"] == "organic_growth_pct") & (gl["action"] != "actual") & gl["low"].notna()].sort_values("statement_date")
    guide = {"Nordic": f"Q3 2026 revenue USD {fc['nordic_2026Q3']['guide_low']:g}-{fc['nordic_2026Q3']['guide_high']:g}m",
             "Logitech": f"Q2 FY27 sales USD {fc['logitech_2026Q3']['guide_low']:,g}-{fc['logitech_2026Q3']['guide_high']:,g}m",
             "GN": (f"FY2026 organic growth {gl.iloc[-1]['low']:g}-{gl.iloc[-1]['high']:g}% ({gl.iloc[-1]['statement_date']})" if len(gl) else "")}
    gem_f = ROOT / "steps" / "step7_forecast" / "outputs" / "guide_error_model.csv"
    if gem_f.exists():                                                    # step 7e: the guide error each forecast applies
        anchor_html = _anchor_html_gem(pd.read_csv(gem_f).set_index("company"),
                                       pd.read_csv(gem_f.parent / "guide_error_state_effect.csv").iloc[0], guide)
    else:
        anchor_html = _anchor_html_f14(used, guide)
    return ("<h2>Guidance track record: how accurate, how conservative</h2>"
            "<p class=note>Each forecast anchors on the company's guide, so this is the evidence behind each uplift and range. Error = actual minus guide "
            "midpoint (% of the midpoint for USD guides, points for growth and margins). Label rule fixed before the numbers: conservative = mean error > 0 "
            "and ≥ 70% of outcomes at or above the midpoint; aggressive = the mirror; mixed otherwise; fewer than 4 outcomes = too few. Sources: company "
            "releases, every number quote-checked (Pipeline A: logitech_guidance_history.csv, gn_guidance_history.csv, nordic_quarterly.csv).</p>"
            f"<ul class=box>{''.join(f'<li>{c}</li>' for c in conclusions(s))}</ul>"
            + anchor_html
            + charts_html(p) +
            f"<table><tr>{head}</tr>{body}</table>"
            "<h3 style='font-size:14px'>Annual guides: first statement → last statement, revisions, outcome</h3>"
            "<table><tr><th>Company</th><th>Period</th><th>Metric</th><th>Guide path</th><th>Revisions</th><th>Actual</th><th>First guide error</th></tr>"
            + "".join(rev) + "</table>")


def _gem_sentences(gm: pd.DataFrame, se: pd.Series) -> dict[str, str]:
    """One sentence per company: how its expected guide error is built (step 7e)."""
    out = {}
    if "Nordic" in gm.index:
        r = gm.loc["Nordic"]
        out["Nordic"] = (f"own record by the data-dated channel state of t−1 (F20, F30): its mean miss when the channel was neither building "
                         f"nor in a supply shortage, {r['alpha']:+.2f}% on {int(r['n_not_building'])} of its {int(r['n'])} guides, plus its own "
                         f"building effect ({r['own_building_effect']:+.2f} pts, {int(r['n_building'])} quarters) or shortage effect "
                         f"({r['own_shortage_effect']:+.2f} pts, {int(r['n_shortage'])} quarters) when t−1 was in that state.")
    if "Logitech" in gm.index:
        r = gm.loc["Logitech"]
        out["Logitech"] = (f"habit pooled with {int(se['prior_n_peers'])} peers' quarterly guides (F16; peers' mean {se['prior_mu']:+.2f}%, spread "
                           f"{se['prior_tau']:.2f}; weight {r['weight_own']:.0%} on its own {int(r['n'])} guides), plus the peers' building effect "
                           f"{se['gamma_used']:+.2f} pts (t {se['t']:.1f}, {int(se['n'])} peer firm-quarters) when t−1 was building.")
    if "GN" in gm.index:
        r = gm.loc["GN"]
        out["GN"] = (f"plain mean of its own August full-year organic-guide misses (F17, F23), {r['alpha']:+.1f} pts on {int(r['n'])} years; "
                     "no state term (the peers' effect is a quarterly % revenue miss).")
    return out


def _anchor_html_gem(gm: pd.DataFrame, se: pd.Series, guide: dict) -> str:
    """The step-7e guide error each forecast applies: one sentence and one table row per company."""
    says = _gem_sentences(gm, se)
    source = {"Nordic": "own record, state split (F20, F30)", "Logitech": f"pooled with {int(se['prior_n_peers'])} peers (F16)",
              "GN": "own record (F17, F23)"}

    def n_used(c: str, r: pd.Series) -> str:
        return f"{int(r['n_not_building'])} of {int(r['n'])}" if c == "Nordic" and pd.notna(r.get("n_not_building")) else f"{int(r['n'])}"

    rows = "".join(
        f"<tr><td><b>{c}</b></td><td>{guide[c]}</td><td>{source[c]}</td><td>{n_used(c, r)}</td><td>{r['alpha']:+.2f}</td>"
        f"<td>{r['pred_state_nordic'] if c == 'Nordic' else r['pred_state']} ({r['pred_gamma_applied'] + 0.0:+.2f})</td><td><b>{r['pred_expected_error']:+.1f}</b></td><td>{r['pred_sd']:.1f}</td></tr>"
        for c, r in gm.reindex(["Nordic", "Logitech", "GN"]).dropna(subset=["n"]).iterrows())
    return ("<h3 style='font-size:14px'>The guide error each forecast applies (Logitech F16; Nordic F20/F30; GN F17/F23)</h3>"
            f"<ul class=src>{''.join(f'<li><b>{c}</b>: {s}</li>' for c, s in says.items())}</ul>"
            "<p class=src>Units: % of the guide midpoint (GN: pts of full-year organic growth). sd = predictive sd; the 80% range is ±1.28 sd.</p>"
            "<table><tr><th>Company</th><th>Guide</th><th>Habit from</th><th>n (habit)</th><th>Habit</th>"
            f"<th>State of t−1 (effect)</th><th>Expected error</th><th>sd</th></tr>{rows}</table>")


def _anchor_html_f14(used: dict, guide: dict) -> str:
    arow = "".join(f"<tr><td><b>{c}</b></td><td>{guide[c]}</td><td>{html.escape(r['rule'])}; {html.escape(r['window'])}</td><td>{int(r['n'])}</td>"
                   f"<td><b>{r['mean_beat_pct']:+.1f} {r['unit']}</b></td><td>{r['median_beat_pct']:+.1f}</td><td>{r['std_pct']:.1f}</td></tr>"
                   for c, d in used.items() for _, r in d.iterrows())
    return ("<h3 style='font-size:14px'>The bias each forecast applies (one rule, decision F14)</h3>"
                   "<p class=src>forecast = guide midpoint × (1 + mean bias) for Nordic and Logitech; GN: full-year organic = guide midpoint + mean bias, "
                   "H2 growth implied from the reported H1. Range from the bias's sd (80%).</p>"
                   "<table><tr><th>Company</th><th>Guide the forecast anchors on</th><th>Evidence</th><th>n</th><th>Mean bias (applied)</th><th>Median</th><th>sd</th></tr>"
                   f"{arow}</table>")


# ------------------------------------------------------------------ one anchor table for the forecasts (F14)
def gn_statement_errors(month: int = 8) -> pd.DataFrame:
    """Each year's last organic-growth statement made in `month`, scored against the full-year outcome (pts)."""
    if not GN_HIST.exists():
        return pd.DataFrame()
    h = gn_headline(pd.read_csv(GN_HIST))
    h = h[h["metric"] == "organic_growth_pct"]
    rows = []
    for fy, g in h.groupby("fiscal_year"):
        act = g[g["action"] == "actual"]["low"]
        st = g[(g["action"] != "actual") & g["low"].notna() & (pd.to_datetime(g["statement_date"]).dt.month == month)]
        if st.empty:
            continue
        r = st.iloc[-1]
        mid = (r["low"] + r["high"]) / 2
        rows.append({"fiscal_year": int(fy), "statement_date": r["statement_date"], "low": r["low"], "high": r["high"], "mid": mid,
                     "actual": float(act.iloc[-1]) if len(act) else np.nan,
                     "error_pts": float(act.iloc[-1]) - mid if len(act) else np.nan})
    return pd.DataFrame(rows)


def anchor_table(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Guidance bias per company and guide, in one format: company, window, n, mean / median / sd of the error, unit.
    Replaces step 6's guidance_bias() windows by the config regimes (one definition of the structural breaks)."""
    ga = cfg.get("guidance_anchor", {})
    rows = []

    def add(company, window, e, unit, rule):
        e = pd.Series(e, dtype=float).dropna()
        rows.append({"company": company, "window": window, "n": len(e), "mean_beat_pct": e.mean(), "median_beat_pct": e.median(),
                     "std_pct": e.std(ddof=1) if len(e) > 1 else np.nan, "min_pct": e.min(), "max_pct": e.max(), "unit": unit, "rule": rule})

    nq = nordic_quarters(p).dropna(subset=["revenue_usdm"])
    for reg in ("normal", "destock", "supply_constrained"):
        g = nq[nq["regime"] == reg]
        span = f"{g.index.min()}-{g.index.max()}" if len(g) else ""
        add("Nordic", f"{reg.replace('_', '-')} channel ({span})" if reg != "normal" else f"normal channel ({span})", g["error_pct"], "%",
            "quarterly revenue guide, quarters of that regime (config regimes)")
    add("Nordic", f"all quarters ({nq.index.min()}-{nq.index.max()})", nq["error_pct"], "%", "quarterly revenue guide, every quarter")
    lq = logitech_quarters().dropna(subset=["net_sales_usdm"])
    add("Logitech", f"quarterly guides ({lq.index.min()}-{lq.index.max()})", lq["error_pct"], "%", "explicit quarterly sales guide")
    ge = gn_statement_errors(ga.get("gn", {}).get("statement_month", 8)).dropna(subset=["error_pts"])
    if len(ge):
        want = cfg.get("forecast", {}).get("gn_2026Q3", {}).get("bias_regime")        # F15: same regime rule as Nordic
        reg = {int(y): {p["regime"].get(pd.Period(f"{int(y)}Q3", "Q")), p["regime"].get(pd.Period(f"{int(y)}Q4", "Q"))} for y in ge["fiscal_year"]}
        sub = ge[ge["fiscal_year"].map(lambda y: reg[int(y)] == {want})] if want else ge
        if want and len(sub) >= 2:                                                   # first GN row = the bias the forecast applies
            add("GN", f"august annual organic guides, H2 in {want} channel ({', '.join(str(int(y)) for y in sub['fiscal_year'])})", sub["error_pts"], "pts",
                "full-year organic growth outcome minus the August guide midpoint; years whose H2 was in the forecast's channel regime (F15); n < 4: too few to estimate a spread")
        add("GN", f"august annual organic guides, all years ({ge['fiscal_year'].min()}-{ge['fiscal_year'].max()})", ge["error_pts"], "pts",
            "full-year organic growth outcome minus the August guide midpoint; every year (F14; spread used for the range)")
    return pd.DataFrame(rows).round(2)
