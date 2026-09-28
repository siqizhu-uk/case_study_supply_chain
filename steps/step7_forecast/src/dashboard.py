"""Single-file HTML monitoring view (deliverables/dashboard.html). No external assets:
figures are embedded as base64 PNG so the file can be emailed or opened offline."""
from __future__ import annotations

import base64
import html
import re
from datetime import date
from pathlib import Path

import pandas as pd

from core.config import OUTPUTS, ROOT, load_config, step_outputs
from risk_flags import load_flags  # steps/step6_backtest/src
from composite_report import prereg_view  # steps/step6_backtest/src: 'adopted' shown as gate status (B26)
from key_insights import load_insights  # steps/step6_backtest/src
import pitfalls  # noqa: E402   the pitfall register
from metric_catalogue import catalogue, write_catalogue, tab_html as data_tab  # noqa: E402
from supply_graph_timeline import tab_html as timeline_tab  # noqa: E402   steps/step5_supply_graph/src
from edge_lags_report import dashboard_section as edge_lags_section  # noqa: E402   steps/step4_lag_structure/src (L4-L9)
from live_gauge import gauge_html, latest_lead  # noqa: E402
from monitoring import plan_html  # noqa: E402
from forecast_display import basis_cell, beat_footnote, method_line, gn_enterprise_level, next_quarter_section, nordic_dist_level, regime_html, status_html  # noqa: E402


from disclosure import section_html as disclosure_html  # step 3: who holds inventory, who discloses it (D23)
from fiscal_calendar import section_html as fiscal_calendar_html  # fiscal vs calendar quarter of every company (Data tab)
from brief_audit import section_html as brief_audit_html  # brief checklist: data / chart / prior per answer
from guidance_record import section_html as guidance_section_html  # guidance track record (F12)
from charts import charts_tab  # noqa: E402   the analysis in charts (tab 'Charts')
from cross_checks_view import html_section as cross_checks_html  # noqa: E402   every check beside each forecast
from event_study_svg import dashboard_section as event_study_section  # noqa: E402   steps/step5 (5d, G23)
from analysis_tab import analysis_tab_html  # noqa: E402   the analyst's write-up (deliverables/my_analysis.html)
from mechanism_charts import write_all as write_figures  # noqa: E402   deliverables/figures/

def _img(path: Path) -> str:
    if not path.exists():
        return ""
    b = base64.b64encode(path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b}" style="max-width:100%;height:auto;border:1px solid #e5e5e5;border-radius:6px">'


def _status(level: str) -> str:
    return status_html(level)          # forecast_display.py: green / amber / red, and a hollow grey dot for 'judgment'


def _run_len(s: pd.Series) -> int:
    """Consecutive latest quarters with s > 0."""
    n = 0
    for v in s.dropna()[::-1]:
        if v > 0:
            n += 1
        else:
            break
    return n


def _pct_in_history(s: pd.Series) -> float:
    s = s.dropna()
    return float((s <= s.iloc[-1]).mean()) if len(s) else float("nan")


NORDIC_Q = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_quarterly.csv"
GEM = ROOT / "steps" / "step7_forecast" / "outputs" / "guide_error_model.csv"


def _incident_row(cfg: dict) -> dict:
    """Logitech's supplier incident pushed back to Nordic through the graph (step 5d event study, F21)."""
    sb = cfg["structural_breaks"]["logitech_supplier_incident_2026"]
    es = pd.read_csv(step_outputs("step5_supply_graph") / "event_study_supplier_incident.csv").set_index("row")
    tot, net = es.loc["Nordic shipments to the Logitech slice: total"], es.loc["Nordic: not yet in any guide (total - already in guide)"]
    return {"tier": "2 OEM", "indicator": "Logitech supplier incident (gaming, mice/keyboards)",
            "latest": f"≈${sb['q2fy27_sales_hit_usdm']:.0f}m Q2 FY27, up to ${sb['q3fy27_sales_hit_usdm']:.0f}m Q3 FY27",
            "read": (f"Unnamed semiconductor supplier facility incident; lost Logitech builds cut its ODMs' Nordic chip orders. Through the graph: "
                     f"Nordic {net['2026Q3']:+.1f}m net in Q3 (gross {tot['2026Q3']:+.1f}, range 0 to {tot['2026Q3']:+.1f}) and "
                     f"{tot['2026Q4']:+.1f}m in Q4 (F21)."),
            "level": "judgment", "source": "Logitech Q1 FY27 release (8-K), 28 Jul 2026; step 5d event study"}


def _distributor_days_row(p: pd.DataFrame, cfg: dict) -> dict:
    """Ingram and TD Synnex inventory days: the larger quarter-on-quarter move against one threshold (shared with W12)."""
    th = float(cfg["dashboard_rules"]["distributor_inv_days_amber_change"])
    ser = {"Ingram": p["ingm_inv_days"].dropna(), "TD Synnex": p["snx_inv_days"].dropna()}
    chg = {k: float(s.iloc[-1] - s.iloc[-2]) for k, s in ser.items() if len(s) > 1}
    who, d = max(chg.items(), key=lambda kv: abs(kv[1]))
    read = ("Rising: a channel willing to hold stock is a tailwind to sell-in now and a risk if end demand stalls." if d >= th
            else "Falling: distributors are drawing stock down." if d <= -th else f"Flat (within ±{th:g} days of the prior quarter).")
    return {"tier": "1 Distributor", "indicator": "Distributor inventory days (Ingram / TD Synnex)",
            "latest": ", ".join(f"{k} {s.iloc[-1]:.0f} ({s.index[-1]}; {chg.get(k, float('nan')):+.1f} on the quarter)" for k, s in ser.items()),
            "read": f"Larger move: {who} {d:+.1f} days. {read}", "level": "amber" if max(chg.values()) >= th else "green",
            "source": f"Ingram / TD Synnex balance sheets; rule: either up {th:g} days or more on the quarter -> amber (W12)"}


def _gn_enterprise_row(p: pd.DataFrame, cfg: dict) -> dict:
    """GN Enterprise: management's words as saved in docs/source_notes/gn_raw.md, and the step-3 distributor drain."""
    gi = pd.read_csv(step_outputs("step3_inventory_mechanism") / "channel_index_gn.csv").set_index("quarter")["excess_weeks"].dropna()
    gap, org = p["gn_st_gap"].dropna(), p["gn_enterprise_org"].dropna()
    return {"tier": "2 OEM", "indicator": "GN Enterprise sell-out minus sell-in (pts)",
            "latest": f"{gap.iloc[-1]:+.0f} ({gap.index[-1]}); Enterprise org {org.iloc[-1]:+.0f}%",
            "read": ("Management (Q2 call): Evolve3 ships from September; Q3 the 'turning point' to positive group organic growth; EMEA channel "
                     f"reductions smaller in H2. The H2 guide needs the {len(gi)}-quarter distributor drain (step 3: {gi.iloc[-1]:+.1f} wk of "
                     f"Enterprise sell-in since {gi.index[0]}) to end."),
            "level": gn_enterprise_level(float(org.iloc[-1]), cfg),
            "source": (f"GN Q2 2026 report / call, 19 Aug 2026 (verbal; docs/source_notes/gn_raw.md); rule: Enterprise organic < "
                       f"{cfg['dashboard_rules']['gn_enterprise_org_amber_below']:g}% -> amber")}


def _nordic_state_row(p: pd.DataFrame, cfg: dict) -> dict:
    """Nordic's coded distributor state with the note recorded beside it in nordic_quarterly.csv (source column)."""
    st = p["nordic_dist_state"].dropna()
    q = pd.read_csv(NORDIC_Q, dtype={"quarter": str}).dropna(subset=["dist_inventory_state"]).iloc[-1]
    m = re.search(r"\((.*)\)\s*$", str(q["source"]))
    return {"tier": "3 Component", "indicator": "Nordic distributor-inventory state (verbal)",
            "latest": f"{st.iloc[-1]:+.1f} coded ({st.index[-1]}): {m.group(1) if m else q['source']}",
            "read": ("CEO: the smallest customers may carry 'some safety stockings for some additional weeks'. If Q3 beats and distributor "
                     "inventory rises, the beat is borrowed from Q4/Q1."),
            "level": nordic_dist_level(float(st.iloc[-1]), cfg),
            "source": f"Nordic Q2 2026 call (verbal); rule: |coded state| >= {cfg['dashboard_rules']['nordic_dist_state_amber_abs']:g} -> amber"}


def _nordic_days_row(p: pd.DataFrame, cfg: dict) -> dict:
    th = float(cfg["dashboard_rules"]["nordic_inv_days_amber_above"])
    d = p["nordic_inv_days"].dropna()
    return {"tier": "3 Component", "indicator": "Nordic own inventory days", "latest": f"{d.iloc[-1]:.0f} ({d.index[-1]})",
            "read": f"Deliberate nRF54 wafer build. Above {th:g} with flat revenue would signal demand slipping below the build plan (W3).",
            "level": "amber" if d.iloc[-1] > th else "green", "source": f"Nordic balance sheet; rule: above {th:g} days -> amber"}


def _nordic_lead_row(cfg: dict) -> dict:
    """The live gauge as one row: the longest factory lead time on Nordic's Bluetooth LE SoCs (findchips), the one live
    reading that enters the model (D24: above the shortage threshold Nordic's state turns to shortage)."""
    amber, red = float(cfg["dashboard_rules"]["nordic_lead_time_amber_weeks"]), float(cfg["cycle_state"]["shortage"]["lead_time_min_weeks"])
    lt = latest_lead()
    latest = f"{lt[0]:.0f} wk ({lt[1]}, read {lt[2]})" if lt else "not quoted"
    level = "judgment" if lt is None else ("red" if lt[0] > red else "amber" if lt[0] > amber else "green")
    return {"tier": "3 Component", "indicator": "Nordic factory lead time (live, authorized distributors)", "latest": latest,
            "read": (f"The one live reading that enters the model: above {red:g} weeks Nordic's state turns to shortage (D24), which "
                     f"lowers its expected guide error. "
                     + (f"Quoted only for {', '.join(lt[3])}; {', '.join(lt[4])} had no lead time quoted. " if lt and lt[4] else "")
                     + "Stock and price per part: Audit tab (live gauge); ./run.sh --live takes a new reading."),
            "level": level, "source": f"findchips (Digi-Key, Mouser); rule: above {amber:g} wk -> amber, above {red:g} wk -> red (W4)"}


def _nordic_beat_row(p: pd.DataFrame) -> dict:
    """Nordic's beat: the habit the forecast applies (F20/F30) and the last quarter it guided above the outcome."""
    b = p["nordic_beat_vs_guide_pct"].dropna()
    neg = b[b < 0]
    r = pd.read_csv(GEM).set_index("company").loc["Nordic"]
    miss = f"Last quarter below the midpoint: {neg.index[-1]} ({neg.iloc[-1]:+.2f}%)." if len(neg) else "No quarter below the midpoint on record."
    return {"tier": "3 Component", "indicator": "Nordic beat vs guidance midpoint, last 4 quarters", "latest": ", ".join(f"{v:+.1f}%" for v in b.tail(4)),
            "read": (f"Nordic's own record when the channel was neither building nor short of supply: {r['alpha']:+.2f}% (n {int(r['n_not_building'])}; "
                     f"F20/F30; record from 2019Q1, F32, limits R7-R8); the forecast anchors on it. {miss}"),
            "level": "green" if (b.tail(4) > 0).all() else "amber", "source": "computed from quarterly reports; steps/step7_forecast/outputs/guide_error_model.csv"}


def indicators(p: pd.DataFrame, data: dict, fn: dict, cfg: dict) -> list[dict]:
    """Watch list. Every 'latest' and every reading is computed from the data at run time; verbal items carry the call date."""
    last = p.dropna(subset=["nordic_rev"]).index[-1]
    s3 = step_outputs("step3_inventory_mechanism")
    li = pd.read_csv(s3 / "channel_index_logitech.csv").set_index("quarter")["excess_weeks"].dropna()
    ch_w = float(li.iloc[-1]) if len(li) else float("nan")
    gap = p["logi_st_gap"].dropna()
    run = _run_len(gap)
    snx = p[["snx_sales", "snx_sales_yoy", "snx_inv_days"]].dropna(subset=["snx_sales"])
    sq = snx.index[-1]
    tg = data["tdsynnex"]
    tg = tg.set_index("quarter") if "quarter" in tg.columns else tg
    snx_guide = tg[["guide_low_usdm", "guide_high_usdm"]].apply(pd.to_numeric, errors="coerce")
    snx_guide.index = snx_guide.index.astype(str)
    g_mid = snx_guide.loc[str(sq)].mean() if str(sq) in snx_guide.index else float("nan")
    snx_beat = (snx.loc[sq, "snx_sales"] / g_mid - 1) * 100 if pd.notna(g_mid) else float("nan")
    li_days = p["logi_inv_days"].dropna()
    li_pct = _pct_in_history(li_days)
    rows = [
        {"tier": "0 Sell-out", "indicator": "Logitech sell-through minus sell-in (pts)", "latest": f"{gap.iloc[-1]:+.0f} ({gap.index[-1]})",
         "read": (f"Sell-through ahead of sell-in for {run} quarter(s) in a row; channel {ch_w:+.1f} weeks vs target (step 3 index) "
                  + ("⇒ sell-in must catch up: supportive beyond the guided quarter and for ODM builds; the Q2 FY27 point is the guide "
                     "method only (F29)." if run and ch_w < 0 else
                     "⇒ channel filling: good for sell-in now, payback risk later." if ch_w > 0 else "⇒ no catch-up signal.")),
         "level": "green" if gap.iloc[-1] >= 0 else "red", "source": "Logitech call, each quarter; step 3 channel index"},
        {"tier": "1 Distributor", "indicator": f"TD Synnex revenue YoY and vs its own guide ({sq})",
         "latest": f"{snx.loc[sq, 'snx_sales_yoy']:+.0f}% YoY; {snx_beat:+.0f}% vs guide mid",
         "read": ("Driven by PC prices and the commercial refresh (CEO, FQ2 call: 'positioned on B2B where the refresh is not over'): "
                  "read as channel posture, not peripherals demand."),
         # context, not a peripherals-demand light: 2026 distributor dollars carry memory-driven ASPs (+31-38% vs Logitech +7%;
         # structural_breaks.distributor_asp_inflation_2026), so a positive YoY says little about mice and headsets
         "level": "context", "source": "TD Synnex 8-K releases (latest FQ3 FY26, 24 Sep 2026); dollars inflated by memory ASPs, context only"},
        _distributor_days_row(p, cfg),
        {"tier": "2 OEM", "indicator": "Logitech own inventory days", "latest": f"{li_days.iloc[-1]:.0f} ({li_days.index[-1]})",
         "read": f"At the {li_pct:.0%} point of its own 2021-26 history" + (": high - pre-build or demand below plan." if li_pct > 0.8 else
                  ": low - lean, little pre-build." if li_pct < 0.2 else ": no pre-build signal either way."),
         "level": "amber" if li_pct > 0.8 else "green", "source": "Logitech balance sheet"},
        _incident_row(cfg),
        _gn_enterprise_row(p, cfg),
        _nordic_state_row(p, cfg),
        _nordic_lead_row(cfg),
        _nordic_days_row(p, cfg),
        _nordic_beat_row(p),
    ]
    return rows


def _insights_compact(k: pd.DataFrame | None) -> str:
    """Headline + so-what visible; the computed evidence one click away."""
    if k is None or k.empty:
        return ""
    items = "".join(f"<li><b>{r.insight}.</b> {r.implication}<details><summary class=src>evidence</summary>{r.evidence}</details></li>"
                    for r in k.itertuples())
    return f'<h2>Key insights (computed from the data)</h2><ol class=box style="border-left-color:#2b7bb9">{items}</ol>'


def _risks_compact(f: pd.DataFrame | None) -> str:
    if f is None or f.empty:
        return ""
    items = "".join(f"<li>{'<b style=\"color:#c0392b\">●</b> ' if bool(r.triggered) else '○ '}<b>{r.id}. {r.risk}.</b>"
                    f"<details><summary class=src>evidence</summary>{r.evidence}</details></li>" for r in f.itertuples())
    return ('<h2>Risks the tests cannot rule out: the composite channel factor (a pre-registered challenger, not in the forecast; B26) and Nordic&#39;s own guide-error record (F32)</h2>'
            f'<ul class=box style="border-left-color:#c0392b;list-style:none">{items}</ul>'
            '<p class=src>R1-R4 concern the composite; R5-R6 concern the channel mechanism in general, so they also bound how much weight any '
            'channel signal in the forecasts can carry; R7-R8 are what Nordic&#39;s own record extended to 2019Q1 shows about the guide-error rule in '
            'force (F32; rule kept, F33). ● triggered by the current data · full text: steps/step6_backtest/outputs/step6_report.md, '
            'steps/step7_forecast/outputs/guide_error_record_extension.csv</p>')


def graph_lags(d: Path | None = None) -> dict:
    """Step 5 lags in weeks: the goods (physical) lag and the order-signal lag incl. planning delays (G25), all routes
    flow-weighted and the Amazon route, each with its 90% band (graph Monte Carlo)."""
    d = d or step_outputs("step5_supply_graph")
    f = d / "graph_signal_lag_mc.csv"
    if not f.exists():
        return {}
    t = pd.read_csv(f).set_index(["basis", "route"])
    pick = lambda b, r: t.loc[(b, r), ["p5", "p50", "p95"]].to_dict()  # noqa: E731
    mc = d / "graph_mean_lag_mc.csv"                               # the goods lag as the Reliability line reads it (one source per page)
    phys = pd.read_csv(mc).iloc[0][["p5", "p50", "p95"]].to_dict() if mc.exists() else pick("physical", "all routes (flow-weighted)")
    return {"physical": phys, "signal": pick("signal", "all routes (flow-weighted)"), "signal_amazon": pick("signal", "Amazon direct")}


def _wk(x: dict) -> str:
    return f"{x['p50']:.0f} weeks (90% {x['p5']:.0f}–{x['p95']:.0f})"


def _graph_lag_line(d: Path) -> str:
    """The kernel's goods lag (what the forecasts use) and the order-signal lag beside it."""
    k = d / "graph_kernel.csv"
    if not k.exists():
        return ""
    kern = pd.read_csv(k).set_index("lag_quarters")
    mean = {c: float((kern[c] * kern.index).sum()) for c in kern.columns}
    g = graph_lags(d)
    sig = (f" Order signal incl. planning delays (G25): {_wk(g['signal'])} flow-weighted, Amazon route {_wk(g['signal_amazon'])}; "
           "the forecasts use the goods lag." if g else "")
    return (f"Goods (physical) lag end demand → Nordic, the basis of the forecast kernel: {mean['mid'] * 13:.0f} weeks ({mean['mid']:.1f} quarters; "
            f"{mean['low'] * 13:.0f}–{mean['high'] * 13:.0f} weeks across the low / high edge lags).{sig} ")


def _mixed_lag(d: Path) -> str | None:
    """E14's lag mixed over p = the residual's share through distributors (G20), from graph_residual_lag_by_p.csv."""
    f = d / "graph_residual_lag_by_p.csv"
    if not f.exists():
        return None
    t = pd.read_csv(f)
    at = {k: t[t["p"].str.startswith(k)].iloc[0] for k in ("low", "mid", "high")}
    return (f"{at['mid']['E14_lag_weeks']:.1f} mixed (p " + "/".join(f"{float(at[k]['p'].split()[-1]):g}" for k in at)
            + ": " + "/".join(f"{at[k]['E14_lag_weeks']:.1f}" for k in at) + ")")


def _edges_table(d: Path) -> str:
    edges = d / "graph_edges_today.csv"
    if not edges.exists():
        return ""
    e = pd.read_csv(edges).fillna("")
    e["share_value"] = e["share_value"].map(lambda v: f"{v:.3f}" if v != "" else "")
    e["flow"] = e["flow"].map(lambda v: f"{v:.1%}" if v != "" else "")
    e["lag (wk)"] = e["lag_weeks_low"].astype(str) + "–" + e["lag_weeks_high"].astype(str)
    mix = _mixed_lag(d)
    if mix:                                                        # E14: direct range shown, the mixed lag is what the graph uses
        has = e["lag_mix"].astype(str) != ""
        e.loc[has, "lag (wk)"] = mix + "; direct " + e.loc[has, "lag (wk)"]
    cols = ["edge_id", "src", "dst", "brand", "share", "share_value", "share_grade", "flow", "lag (wk)", "lag_grade", "inventory_holder",
            "inventory_disclosed", "evidence", "lag_evidence"]
    return f"<details><summary><b>All edges</b> — share, lag, inventory holder, disclosure, evidence</summary>{e[cols].to_html(index=False, border=0)}</details>"


def _grade_mix(r: pd.Series, what: str) -> str:
    """'share 100% A/B' or 'lag 0% A/B (100% C)': the share of flow at each grade."""
    ab = r[f"{what}_A"] + r[f"{what}_B"]
    rest = ", ".join(f"{r[f'{what}_{g}']:.0%} {g}" for g in ("C", "D") if r[f"{what}_{g}"] > 0)
    return f"{what} {ab:.0%} A/B" + (f" ({rest})" if rest else "")


def _info_delay_line(d: Path) -> str:
    f = d / "graph_signal_tornado.csv"
    if not f.exists():
        return ""
    t = pd.read_csv(f)
    info = t[t["input"].str.startswith("info delay")].sort_values("swing_weeks", ascending=False)
    if info.empty:
        return ""
    grades = sorted(set(info["grade"]))
    top = info.iloc[0]
    return (f" Planning (information) delays: {'all grade ' + grades[0] if len(grades) == 1 else 'grades ' + '/'.join(grades)}; "
            f"largest input {top['input']} ±{top['swing_weeks'] / 2:.1f} wk (G25).")


def _reliability(d: Path) -> str:
    tg, mc, gaps, tor = (d / f for f in ("graph_tier_grades.csv", "graph_mean_lag_mc.csv", "graph_data_gaps.csv", "graph_tornado.csv"))
    if not (tg.exists() and mc.exists()):
        return ""
    m = pd.read_csv(mc).iloc[0]
    t = pd.read_csv(tg).set_index("tier")
    g = pd.read_csv(gaps)
    top = pd.read_csv(tor).head(4)
    counts = {"not public": int((g["availability"] == "not_public").sum()), "public but not yet collected": int((g["availability"] == "not_collected").sum())}
    g = g.assign(flow=g["flow"].map(lambda v: f"{v:.1%}" if pd.notna(v) else ""))
    return (f"<p class=note><b>Reliability.</b> Monte Carlo over every share and lag: goods (physical) mean lag {m['p5']:.0f}–{m['p95']:.0f} weeks (90%). "
            "Support is graded separately for the share and for the lag (grade = data support, not the level): "
            + "; ".join(f"{i}: {_grade_mix(r, 'share')} · {_grade_mix(r, 'lag')}" for i, r in t.iterrows()) + ". "
            f"{len(g)} D-graded inputs: " + ", ".join(f"{v} {k}" for k, v in counts.items() if v) + " (list: Data gaps). "
            "Inputs that move the goods lag most: " + ", ".join(f"{r['input']} (grade {r['grade']}, ±{r['swing_weeks'] / 2:.1f} wk)" for _, r in top.iterrows())
            + "." + _info_delay_line(d) + "</p>"
            f"<details><summary><b>Data gaps</b> — every D-graded share or lag</summary>{g.round(3).to_html(index=False, border=0)}</details>")


def _graph_section() -> str:
    """The supply chain as a graph (step 5): blue = edge share from a filing, grey dashed = assumption; width = flow."""
    d = step_outputs("step5_supply_graph")
    svg = d / "supply_graph.svg"
    if not svg.exists():
        return ""
    return (f"<h2>Supply graph (step 5): who buys from whom, with shares and lags</h2><div id=sg-wrap style=position:relative>{svg.read_text()}"
            "<div id=sg-tip style='position:absolute;display:none;pointer-events:none;background:#fff;border:1px solid #999;border-radius:6px;"
            "padding:6px 9px;font-size:12px;white-space:pre-line;max-width:420px;box-shadow:0 2px 6px rgba(0,0,0,.12);z-index:5'></div></div>"
            "<div id=sg-pin class=note style='white-space:pre-line;display:none'></div>"
            f"<p class=src>{_graph_lag_line(d)}Hover an edge for its share, lag, inventory holder and evidence; click to pin it. Edges and weights: "
            "config/supply_graph.csv, config/supply_graph_weights.csv (Logitech's customer shares per 10-K, point in time).</p>"
            + _reliability(d) + _residual_box(d) + _edges_table(d) + _GRAPH_JS)


def _residual_box(d: Path) -> str:
    """Logitech's unnamed 10-K residual: evidence, range reasoning and lag effect of p (step 5, G20)."""
    ev, lp = d / "graph_residual_evidence.csv", d / "graph_residual_lag_by_p.csv"
    if not (ev.exists() and lp.exists()):
        return ""
    from residual_evidence import PARAM, html_box                     # steps/step5_supply_graph/src
    from core.config import load_config
    o = {"evidence": pd.read_csv(ev, dtype=str).fillna(""), "lag_by_p": pd.read_csv(lp),
         "param": load_config()["supply_graph"]["params"][PARAM]}
    return f"<details><summary><b>Logitech's unnamed 56% of sales: how much goes through distributors</b> — evidence and range (G20)</summary>{html_box(o)}</details>"


_GRAPH_JS = """<script>
(function(){
  var wrap=document.getElementById('sg-wrap'), tip=document.getElementById('sg-tip'), pin=document.getElementById('sg-pin');
  if(!wrap) return;
  wrap.querySelectorAll('.sg-hit').forEach(function(h){
    var t=h.querySelector('title'); if(t) t.remove();                 // our tooltip replaces the slow native one
    var line=h.previousElementSibling;
    h.addEventListener('mousemove',function(ev){
      var r=wrap.getBoundingClientRect(); tip.textContent=h.dataset.tip; tip.style.display='block';
      var x=ev.clientX-r.left+14, y=ev.clientY-r.top+14;
      if(x+430>r.width) x=Math.max(0,ev.clientX-r.left-430);
      tip.style.left=x+'px'; tip.style.top=y+'px';
      if(line) line.setAttribute('stroke-opacity','1');
    });
    h.addEventListener('mouseleave',function(){ tip.style.display='none'; if(line) line.setAttribute('stroke-opacity','0.85'); });
    h.addEventListener('click',function(){ pin.textContent=h.dataset.tip; pin.style.display='block'; });
  });
})();
</script>"""


EDGE1_SEGMENTS = ("sell_out_to_distributor", "distributor_to_oem")     # sell-out -> brand sell-in (step 4 edge 1); the rest is edge 2


def _decision_range() -> str:
    """'F1–F31': the first and last step-7 decision ids, read from the register."""
    ids = pd.read_csv(ROOT / "steps" / "step7_forecast" / "config" / "decisions.csv")["id"]
    return f"{ids.iloc[0]}–{ids.iloc[-1]}"


def _route_shares() -> str:
    """Logitech's named customers in its latest 10-K (config/supply_graph_weights.csv)."""
    w = pd.read_csv(ROOT / "config" / "supply_graph_weights.csv").iloc[-1]
    return (f"Amazon direct {w['amazon']:.0%}, Ingram / TD Synnex {w['ingram'] + w['tdsynnex']:.0%} of Logitech's gross sales, "
            f"{w['source_key']}")


def _backlog_regime_note(p: pd.DataFrame, cfg: dict) -> str:
    """The supply-constrained regime's lag stretch as config documents it (edge 2 x lag_multiplier); not applied (D13)."""
    rg, lw = cfg["regimes"]["supply_constrained"], cfg["lag_weeks"]
    edge1 = sum(lw[k]["mid"] for k in EDGE1_SEGMENTS)
    edge2 = sum(lw[k]["mid"] for k in lw if k not in EDGE1_SEGMENTS)
    wk = edge1 + edge2 * rg["lag_multiplier"]
    bl = p["nordic_backlog"].dropna() if "nordic_backlog" in p else pd.Series(dtype=float)
    peak = (f" (Nordic's backlog peaked at {bl.max() / p.loc[bl.idxmax(), 'nordic_rev']:.1f}x quarterly revenue in {bl.idxmax()})" if len(bl) else "")
    turn = _first_negative_gap(p, "logi_sales_yoy", "nordic_consumer_yoy", rg["quarters"][0])
    seen = (f" Observed: Nordic Consumer turned negative YoY {turn[2]} quarters after Logitech ({turn[0]} → {turn[1]}), one turning point."
            if turn else "")
    return (f"In the {rg['quarters'][0]}–{rg['quarters'][1]} supply-constrained regime{peak}, config stretches edge 2 x{rg['lag_multiplier']:g}: "
            f"{wk:.0f} weeks (≈{wk / 13:.1f} quarters) at the mid. Documented, not applied: those quarters are excluded from the fits (D13).{seen}")


def _first_negative_gap(p: pd.DataFrame, lead: str, lag: str, start: str) -> tuple[str, str, int] | None:
    """First quarter from `start` where each series turns negative YoY, and the gap in quarters."""
    firsts = []
    for c in (lead, lag):
        s = p[c].dropna() if c in p else pd.Series(dtype=float)
        neg = s[(s < 0) & (s.index.astype(str) >= start)]
        if neg.empty:
            return None
        firsts.append(pd.Period(str(neg.index[0]), "Q"))
    return str(firsts[0]), str(firsts[1]), (firsts[1] - firsts[0]).n


ROLE_COLOUR = {"FORECAST": "#2e8b57", "IN THE": "#2e8b57", "benchmark": "#4C78A8", "retired": "#c0392b", "challenger": "#d99a00",
               "outlook": "#d99a00", "cross-check": "#777", "diagnostic": "#777"}


def _chain_section() -> str:
    """Step 7c: every forecast as terms, each tied to one of the brief's decisions (chain_terms.csv)."""
    f = ROOT / "steps" / "step7_forecast" / "outputs" / "chain_terms.csv"
    if not f.exists():
        return ""
    t = pd.read_csv(f).fillna("")
    rows = "".join(f"<tr><td>{html.escape(str(r.print))}</td><td><b>{html.escape(str(r.decision))}</b></td><td>{html.escape(str(r.term))}</td>"
                   f"<td>{html.escape(str(r.value))}</td><td class=src>{html.escape(str(r.evidence))}</td></tr>" for r in t.itertuples())
    return ("<h2>How the supply chain enters each forecast (step 7c)</h2>"
            "<p class=src>final = guide-anchored + weight × (chain − guide-anchored) + events pushed through the graph. The chain is built "
            "from the brief's decisions (lag kernel, inventory mechanism, attribution share, regime). Weights: Nordic h=1 from the walk-forward "
            "encompassing test (config/model.yaml chain_forecast); Logitech 0 by F29 (guide method only); the Nordic Q4 point is GRi by F26 "
            f"(chosen after seeing the back-test). Decisions {_decision_range()}: steps/step7_forecast/config/decisions.csv.</p>"
            f"<table><tr><th>Print</th><th>Decision</th><th>Term</th><th>Value</th><th>Evidence</th></tr>{rows}</table>")






def _role(role: str) -> str:
    col = next((c for k, c in ROLE_COLOUR.items() if str(role).startswith(k) or k in str(role)), "#777")
    return f'<span style="color:{col};font-weight:600">{role}</span>'


def _csv_table(path: Path, cols: list[str] | None = None, view=None) -> str:
    if not path.exists():
        return "<p class=meta>not generated yet</p>"
    t = pd.read_csv(path)
    t = view(t) if view else t
    return (t[cols] if cols else t).to_html(index=False, border=0, na_rep="", float_format=lambda v: f"{v:.2f}")


def _models_section(inv: pd.DataFrame | None, fn: dict) -> str:
    if inv is None:
        return ""
    s6 = step_outputs("step6_backtest")
    used = bool(load_config().get("composite", {}).get("use_in_forecast", False))      # B26: a gate pass is not use
    rows = "".join(f"<tr><td>{r['id']}</td><td>{r['step']}</td><td><b>{r['model']}</b><br><span class=src>{r['question']}</span></td>"
                   f"<td><code>{r['formula']}</code></td><td>{_role(r['role'])}</td><td>{r['walk_forward_performance'] if isinstance(r['walk_forward_performance'], str) else ''}</td></tr>"
                   for _, r in inv.iterrows())
    gate = s6 / "composite_gate.csv"
    ratio = {}
    for h in (1, 2):
        f = s6 / f"walkforward_metrics_h{h}.csv"
        if f.exists():
            m = pd.read_csv(f).set_index("model").reindex(["L6", "L6tv", "L3"])["rmse_ratio_vs_GB"].dropna()
            ratio[h] = f"{m.min():.2f}–{m.max():.2f}×" if len(m) else "n/a"
    return f"""
<h2>All models (what each one answers, and whether it earns its place)</h2>
<table><tr><th>#</th><th>Step</th><th>Model</th><th>Formula</th><th>Role</th><th>Walk-forward performance (point in time)</th></tr>{rows}</table>
<p class=note>h1 = the guided quarter (the October prints); h2 = the quarter after. Performance is from forecasts made with only the data public on each forecast date; ratios compare with guidance + real-time beat on the same quarters.</p>

<h2>Back-test: lag models vs guidance</h2>
<p class=note>Lag-model error relative to guidance + real-time beat on the same quarters — next quarter (guided): {ratio.get(1, 'n/a')}; the quarter after: {ratio.get(2, 'n/a')} (below 1 = better than the carried guide). Nordic guides from its own order book, so a lagged Logitech signal adds nothing for the guided quarter. Full report: steps/step6_backtest/outputs/step6_report.md.</p>
{_img(s6 / 'walkforward.png')}

<h2>Composite channel factor → Nordic's guidance miss (step 6c; pre-registered challenger, not in the forecast: B26)</h2>
<p class=note>beat<sub>t</sub> = a + b·C<sub>t</sub>, C<sub>t</sub> = mean of four signed, point-in-time z-scores (Logitech sell-through acceleration, Nordic distributor state, change in Microchip distributor days, Nordic forward DIO). Two parameters whatever the number of factors. Panels: forecast vs actual miss · weights and leave-one-factor-out · cumulative squared-error gain vs the benchmark · placebo of 1000 noise composites · slope stability · sign choice.</p>
{_img(s6 / 'composite.png')}
<div class=grid><div><h3 style="font-size:14px">Adoption gate (thresholds fixed in config before the run)</h3>{_csv_table(gate)}</div>
<div><h3 style="font-size:14px">Pre-registered live forecasts (scored after the print)</h3>{_csv_table(s6 / 'composite_prereg_log.csv', view=lambda t: prereg_view(t, used, 'B26'))}
<h3 style="font-size:14px">Graph challenger: Logitech factor replaced by supply-graph demand (B44)</h3>{_csv_table(s6 / 'composite_graph_prereg_log.csv', view=lambda t: prereg_view(t, False, 'challenger only, B44'))}</div></div>
<h3 style="font-size:14px">Every model in the composite test</h3>
{_csv_table(s6 / 'composite_models.csv', ['model', 'n', 'rmse_beat_pts', 'bench_rmse_same_quarters', 'oos_r2_vs_bench', 'rmse_usdm', 'direction_hit', 'dm_p'])}
"""


SANDBOX = """<h2>Change an assumption and re-run the forecasts</h2>
<p class=note>Every value in config/model.yaml and every edge lag in config/supply_graph.csv can be edited; <b>Run scenario</b> re-runs the
whole model in a sandbox copy of the repository (runs/scenarios/&lt;id&gt;/repo), about 2–3 minutes, and shows the six forecasts beside the committed ones.
<b>Run scenario</b> never writes the committed config or outputs; only <b>Save to config</b> writes config/model.yaml / config/supply_graph.csv.</p>
<div id=sandbox><p class=meta>The sandbox needs the local results server: run <code>python scripts/serve.py</code> and open
<code>http://127.0.0.1:8765/dashboard</code>, tab Predict. Opened as a file, this page shows the committed run only.</p></div>
<script>(function(){ var box=document.getElementById('sandbox'); if(!/^https?:$/.test(location.protocol)) return;
  fetch('/api/assumptions',{cache:'no-store'}).then(function(r){ if(!r.ok) throw 0;
    box.innerHTML='<iframe src="/#assumptions" title="Assumptions sandbox" style="width:100%;height:calc(100vh - 150px);min-height:640px;border:1px solid #e3e3e3;border-radius:6px"></iframe>';
  }).catch(function(){}); })();</script>"""


def _fold(section: str) -> str:
    """A section as one closed box, its own heading as the summary (the Audit tab)."""
    if not section or not section.strip():
        return ""
    if section.lstrip().startswith("<details"):                  # already a box: keep it, closed
        return re.sub(r"^\s*<details( open)?", "<details class=fold", section, count=1)
    m = re.search(r"<h([23])[^>]*>(.*?)</h\1>", section, flags=re.S)
    if not m:
        return f"<details>{section}</details>"
    body = section[:m.start()] + section[m.end():]
    return f"<details class=fold><summary><b>{m.group(2)}</b></summary>{body}</details>"


def build_dashboard(p, data, lag, reg, gb, attr, fn, fl, fg, ftab, cfg, inv: pd.DataFrame | None = None) -> Path:
    figs = OUTPUTS / "figures"
    ind = indicators(p, data, fn, cfg)
    rows = "".join(
        f"<tr><td>{r['tier']}</td><td><b>{r['indicator']}</b><br><span class=src>{r['source']}</span></td><td>{r['latest']}</td><td>{_status(r['level'])}</td><td>{r['read']}</td></tr>"
        for r in ind)
    ft = ftab.copy(); ft["yoy_pct"] = ft["yoy_pct"].map(lambda v: "" if pd.isna(v) else f"{v:+.1f}%")
    fo = "".join(f"<tr><td>{r['print']}</td><td>{r['metric']}</td><td><b>{r['point']}</b></td><td>{r['low']} – {r['high']}</td><td>{r['guide']}</td><td>{r['yoy_pct']}</td>"
                 f"<td>{basis_cell(r, cfg)}</td></tr>" for r in ft.to_dict("records"))
    gb_now = gb                         # guidance_bias table (steps 6 / 7)
    summ = p.tail(8)[["sellout_proxy_yoy", "logi_ble_yoy", "logi_st_gap", "gn_periph_yoy", "nordic_consumer_yoy", "nordic_inv_days", "regime"]].round(1)
    summ = summ[summ.drop(columns="regime").notna().any(axis=1)]           # the unreported quarter has no data yet
    summ.columns = ["Sell-out proxy YoY", "Logitech BLE YoY", "Logi ST−SI gap", "GN periph YoY", "Nordic consumer YoY", "Nordic inv days", "Regime"]
    attr_line = (f"Logitech + GN ≈ {attr['combined_pct_of_nordic_total']['p50']:.0f}% of Nordic revenue "
                 f"(p10–p90 {attr['combined_pct_of_nordic_total']['p10']:.0f}–{attr['combined_pct_of_nordic_total']['p90']:.0f}%; "
                 f"≤ {attr['by_route']['direct']['combined_pct_of_nordic_total']['p90']:.0f}% if invoiced direct — route unknown; grade {attr['grade']}); "
                 f"PC-peripherals category ≈ {attr['pc_peripherals_category_pct_of_total']['p50']:.0f}% of total.")
    r = lag["reasoned"]
    cutoff = "; ".join(f"{n} {p[c].dropna().index[-1]}" for n, c in (("Nordic", "nordic_rev"), ("Logitech", "logi_sales"), ("GN", "gn_group_rev"),
                                                                    ("Ingram", "ingm_sales"), ("TD Synnex", "snx_sales")) if c in p and p[c].notna().any())
    gl = graph_lags()
    graph_lag = (f" Drawn as a graph (step 5: {_route_shares()}): goods (physical) dwell {_wk(gl['physical'])}; order signal incl. planning "
                 f"delays {_wk(gl['signal'])} flow-weighted, Amazon route {_wk(gl['signal_amazon'])} (G25)." if gl else "")
    cat = catalogue(p)
    write_catalogue(cat, OUTPUTS / "metric_catalogue.csv")
    data_html, time_html = data_tab(cat) + fiscal_calendar_html(), timeline_tab(p, cfg)
    charts_html = charts_tab(p)                     # writes outputs/figures/story/*.svg
    write_figures()                                 # deliverables/figures/: the story charts + the write-up's charts, before embedding
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Supply Chain Signal — Nordic / Logitech / GN</title>
<style>
body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:24px;color:#222;max-width:1200px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:26px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{border:1px solid #e3e3e3;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#f6f6f6}} .src{{color:#777;font-size:11px}} .meta{{color:#666;font-size:12px}} .grid{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.note{{background:#f8f9fb;border-left:4px solid #4C78A8;padding:8px 12px;font-size:13px}}
.box{{border-left:4px solid;background:#fafafa;padding:8px 12px 8px 28px;font-size:13px;margin:0}} .box li{{margin:6px 0}}
details{{margin:8px 0}} summary{{cursor:pointer}} details.fold{{border-bottom:1px solid #eee;padding:4px 0}} details.fold>summary{{font-size:15px;padding:4px 0}}
nav.tabs{{margin:14px 0 4px;border-bottom:1px solid #ccc}} nav.tabs button{{border:1px solid #ccc;border-bottom:none;background:#f6f6f6;padding:6px 14px;margin-right:4px;cursor:pointer;border-radius:6px 6px 0 0;font-size:13px}}
nav.tabs button.on{{background:#fff;font-weight:600;position:relative;top:1px}}
</style></head><body>
<h1 style="margin-bottom:2px">Supply Chain Signal Monitor — Nordic Semiconductor ← Logitech / GN ← Distributors / Amazon</h1>
<div class=meta>Generated {date.today().isoformat()} from public data only (filings, call transcripts, distributor listings, ECB rates) · latest data: {cutoff} · all assumptions in config/model.yaml · re-run <code>python scripts/run_all.py</code> · investment note: <code>deliverables/investment_note.md</code> · the analysis, question by question: tab Analysis</div>
<nav class=tabs><button data-tab=charts class=on>Charts</button><button data-tab=analysis>Analysis</button><button data-tab=time>Chain over time</button><button data-tab=predict>Predict</button><button data-tab=monitor>Monitor</button><button data-tab=data>Data &amp; time series</button><button data-tab=audit>Audit</button></nav>
<section id=tab-charts class=tab>{_graph_section()}
{charts_html}</section>
<section id=tab-analysis class=tab style="display:none">{analysis_tab_html()}</section>
<section id=tab-predict class=tab style="display:none">
<h2>Forecasts for the next prints</h2>
<table><tr><th>Print</th><th>Metric</th><th>Point</th><th>Range</th><th>Company guide</th><th>YoY</th><th>What the range is</th></tr>{fo}</table>
<p class=src>{method_line(fn)}.</p>
<p class=src>{beat_footnote(fn, fl, gb_now, cfg)}.</p>
{regime_html(fn, gb_now)}
{SANDBOX}
</section>
<section id=tab-monitor class=tab style="display:none">
<h2>Indicators to watch (traffic light = read-through for Nordic Q3/Q4)</h2>
<table><tr><th>Tier</th><th>Indicator</th><th>Latest</th><th>Status</th><th>Why it matters</th></tr>{rows}</table>
{plan_html(p)}
{_risks_compact(load_flags())}
</section>
<section id=tab-data class=tab style="display:none">{data_html}</section>
<section id=tab-time class=tab style="display:none">{time_html}</section>
<section id=tab-audit class=tab style="display:none">
<p class=meta>The evidence behind every number, for a reviewer. Each box is rebuilt every run; hand-written labels come from the CSVs named in each box.</p>
{_fold(cross_checks_html())}
{_fold(next_quarter_section())}
{_fold(_chain_section())}
{_fold(_insights_compact(load_insights()))}
{_fold(brief_audit_html())}
{_fold(disclosure_html())}
{_fold(guidance_section_html(p))}
{_fold(edge_lags_section(lag.get("edge_lags"), cfg))}
{_fold(event_study_section())}
{_fold(gauge_html())}
<details><summary><b>Lag and mechanism</b> — charts and the reasoned lag</summary>
<p class=note>Reasoned end-to-end lag sell-out → Nordic revenue: {r['low']['weeks']}/{r['mid']['weeks']}/{r['high']['weeks']} weeks (≈{r['mid']['quarters']} quarters) in a normal channel (single-chain reasoning);{graph_lag} {_backlog_regime_note(p, cfg)} Correlation with Logitech sell-in peaks at lag {lag['best_lag_all']} quarter(s): the industry cycle's timing at Nordic, not the chain lag (semiconductor billings and US electronics sales give the same timing; one cycle cannot pin the lag - step 4 L2, P86); amplitude ratio Nordic/Logitech = {lag['amplitude']['destock_2022_2024']:.1f}x in the destock, {lag['amplitude']['recovery_2024_2026']:.1f}x in the recovery. {attr_line}</p>
<div class=grid>
<div>{_img(figs / 'tiers_yoy.png')}</div><div>{_img(figs / 'inventory_days.png')}</div>
<div>{_img(figs / 'xcorr.png')}</div><div>{_img(figs / 'nordic_guidance_beat.png')}</div>
</div>
<div style="margin-top:14px">{_img(figs / 'regression_fit.png')}</div>
</details>
<details><summary><b>Tier panel</b> — last 8 quarters</summary>
{summ.to_html(border=0, na_rep="–")}
<p class=meta>Sell-out proxy = Logitech net sales YoY + disclosed sell-through-minus-sell-in gap. GN periph = Enterprise + SteelSeries (DKK). Nordic inventory days = inventory ÷ quarterly COGS × 91.</p>
</details>
<details><summary><b>All models, back-test and the composite challenger</b></summary>
{_models_section(inv, fn)}
</details>
{_fold(pitfalls.html_section(pitfalls.load(), inner_fold=False))}
</section>
<script>
document.querySelectorAll('nav.tabs button').forEach(function(b){{ b.addEventListener('click',function(){{
  document.querySelectorAll('nav.tabs button').forEach(function(x){{ x.classList.toggle('on', x===b); }});
  document.querySelectorAll('section.tab').forEach(function(t){{ t.style.display = t.id==='tab-'+b.dataset.tab ? '' : 'none'; }});
  try {{ localStorage.setItem('dash-tab', b.dataset.tab); history.replaceState(null, '', '#' + b.dataset.tab); }} catch(e) {{}}
}}); }});
try {{ var t=location.hash.slice(1) || localStorage.getItem('dash-tab');            // #predict opens that tab (deep link)
      var btn=t && document.querySelector('nav.tabs button[data-tab='+t+']'); if(btn) btn.click(); }} catch(e) {{}}
</script>
</body></html>"""
    out = ROOT / "deliverables" / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out
