"""Draw docs/data_flow.svg: where every number comes from.

sources -> pipelines -> core -> analysis steps -> forecast components -> deliverables (static, self-contained SVG).
The few numbers on the boxes are read from the model outputs when they exist, so a re-run re-labels the diagram.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
W, BH, GAP, BW = 1420, 46, 9, 196


def _num(path: str, fn, default: str) -> str:
    try:
        return fn(pd.read_csv(ROOT / path))
    except (FileNotFoundError, KeyError, IndexError, ValueError):
        return default


def labels() -> dict:
    share = _num("steps/step2_attribution/outputs/attribution_path.csv",
                 lambda d: f"Logitech + GN ≈ {d.dropna(subset=['share_total_indirect_p50']).iloc[-1]['share_total_indirect_p50']:.0f}% of Nordic", "Logitech + GN share of Nordic")
    lag = _num("steps/step4_lag_structure/outputs/edge_lags_total.csv",
               lambda d: f"Amazon route ≈ {d.set_index('route').loc['Amazon -> Logitech -> Nordic', 'total_weeks']:.0f} wk (signal)", "edge by edge, reasoned")
    state = _num("steps/step3_inventory_mechanism/outputs/cycle_state_now.csv",
                 lambda d: f"now '{d.iloc[0]['latest_state']}'; building {d.iloc[0]['building_vs_other_pct']:+.2f} pts", "state from distributor days")
    q4 = _num("outputs/forecast_next_quarter.csv", lambda d: (lambda r: f"{r['model']} {r['point']:.0f}; GR, CH = challengers")(
        d[d["is_point"].astype(str).str.lower() == "true"].iloc[0]), "graph-timed, h = 2")
    fx = "ECB rates; Nordic 0 (USD)"
    try:
        g = json.loads((ROOT / "outputs" / "forecast_details.json").read_text())["gn"]["fx_update"]
        fx = f"GN {g['term_pts']:+.1f} pts; Nordic 0 (USD)"
    except (FileNotFoundError, KeyError, ValueError):
        pass
    checks = _num("steps/step7_forecast/outputs/cross_checks_summary.csv",
                  lambda d: f"{int(d['inside_band'].sum())} of {int(d['compared'].sum())} inside the bands", "beside each forecast")
    return {"share": share, "lag": lag, "state": state, "q4": q4, "fx": fx, "checks": checks}


def columns() -> dict:
    lb = labels()
    return {
        "Sources": (14, "#F1EFE8", "#5F5E5A", [
            ("SEC EDGAR", "XBRL facts, 8-K / 10-Q / 10-K"), ("Company reports", "Oslo Børs, IR PDFs, releases"),
            ("Earnings calls", "verbal metrics, quote-checked"), ("FRED / Census / WSTS", "break and lag checks only"),
            ("findchips", "Digi-Key / Mouser stock, live"), ("FCC photos / iFixit", "which chip is inside"),
            ("12 semiconductor peers", "guides vs actuals 2008-26"), ("ECB reference rates", "FX since each guide (F27)"),
            ("Taiwan ODM revenue", "Merry / Chicony, monthly")]),
        "Pipelines (data)": (248, "#E6F1FB", "#185FA5", [
            ("A · Company financials", "5 names, distributors, retailers, ODMs"), ("B · Macro / industry", "ECB FX; break and lag checks"),
            ("C · Real-time channel", "live gauge, FCC census"), ("D · Peer panel", "guidance misses, history")]),
        "Assumptions + panel": (482, "#FAEEDA", "#854F0B", [
            ("config/model.yaml", "every assumption, editable"), ("config/supply_graph.csv", "edges: share, lag, grade"),
            ("Tier panel (core/)", "sell-out → distributor → OEM → Nordic"), ("Fiscal calendars", "one quarter rule for all (P124)"),
            ("audit/ + decisions.csv", "every trap, check and call logged")]),
        "Analysis steps": (716, "#EEEDFE", "#534AB7", [
            ("1 · Filing confidence", "grades A-D per source"), ("2 · Attribution", lb["share"]),
            ("3 · Mechanism", "who holds, bears, discloses"), ("3b · Channel cycle", lb["state"]),
            ("4 · Lag, edge by edge", lb["lag"]), ("5 · Supply graph", "routes, kernel, breaks, events, cycle"),
            ("6 · Back-test", "walk-forward h=1 / h=2, peers")]),
        "Forecast components": (950, "#FCEBEB", "#A32D2D", [
            ("7e · Guide-error model", "habit + channel state"), ("7c · Chain terms", "shown; weight 0 in guided quarters"),
            ("5d · Dated events", "supplier incident, forward"), ("F27 · FX rule", lb["fx"]),
            ("F18 · Margin rule", "guide + own error, or best rule"), ("7b · Nordic Q4", lb["q4"]),
            ("7d · Scenarios", "one input at a time"), ("Cross-checks", lb["checks"]),
            ("Pre-registration", "Q3, Q4, CYC, ODM: hashed, scored")]),
        "Deliverables": (1184, "#E1F5EE", "#0F6E56", [
            ("outputs/forecasts.csv", "point + 80% range"), ("Investment note", "deliverables/, 2 pages"),
            ("Analysis", "deliverables/my_analysis, the brief answered"), ("Dashboard", "deliverables/dashboard.html"),
            ("Results page", "one tab per step + Assumptions"), ("Pitfall register", "audit/pitfalls.csv")]),
    }


def svg() -> str:
    cols = columns()
    nmax = max(len(v[3]) for v in cols.values())
    H = 70 + nmax * (BH + GAP) + 54
    b = {}
    for title, (x, fill, stroke, items) in cols.items():
        h = len(items) * (BH + GAP) - GAP
        y0 = 70 + (nmax * (BH + GAP) - GAP - h) / 2
        b[title] = [(x, y0 + i * (BH + GAP), name, sub, fill, stroke) for i, (name, sub) in enumerate(items)]
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" font-family="-apple-system,Segoe UI,Helvetica,Arial">',
         '<defs><marker id="dfa" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M1 1L9 5L1 9" fill="none" stroke="#888" stroke-width="1.5"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    for title, (x, *_rest) in cols.items():
        p.append(f'<text x="{x + BW / 2}" y="44" text-anchor="middle" font-size="14" font-weight="600" fill="#333">{title}</text>')
    names = list(cols)
    for a, c in zip(names, names[1:]):                         # column-to-column bundle arrows
        xa, xc = cols[a][0] + BW, cols[c][0]
        ya = [y + BH / 2 for (_, y, *_r) in b[a]]
        yc = [y + BH / 2 for (_, y, *_r) in b[c]]
        mid = (xa + xc) / 2
        for y in ya:
            p.append(f'<path d="M{xa} {y} H{mid - 6}" stroke="#bbb" fill="none"/>')
        p.append(f'<path d="M{mid - 6} {min(ya)} V{max(ya)}" stroke="#bbb" fill="none"/>')
        p.append(f'<path d="M{mid - 6} {(min(ya) + max(ya)) / 2} H{mid + 6}" stroke="#bbb" fill="none"/>')
        p.append(f'<path d="M{mid + 6} {min(yc)} V{max(yc)}" stroke="#bbb" fill="none"/>')
        for y in yc:
            p.append(f'<path d="M{mid + 6} {y} H{xc - 2}" stroke="#bbb" fill="none" marker-end="url(#dfa)"/>')
    for items in b.values():
        for x, y, name, sub, fill, stroke in items:
            p.append(f'<rect x="{x}" y="{y}" width="{BW}" height="{BH}" rx="6" fill="{fill}" stroke="{stroke}" stroke-width="0.8"/>'
                     f'<text x="{x + BW / 2}" y="{y + 19}" text-anchor="middle" font-size="12" font-weight="600" fill="#222">{name}</text>'
                     f'<text x="{x + BW / 2}" y="{y + 35}" text-anchor="middle" font-size="10.5" fill="#555">{sub}</text>')
    p.append(f'<text x="14" y="{H - 30}" font-size="11" fill="#666">Every source is a row in its pipeline\'s data_config.csv (retrieval, validation, grade); '
             'every judgment call a row in its step\'s decisions.csv; every trap a row in audit/pitfalls.csv.</text>')
    p.append(f'<text x="14" y="{H - 13}" font-size="11" fill="#666">Each guided forecast = guide × (1 + expected guide error) + chain terms + dated events + FX; '
             'one quarter past the guide, the graph model. Numbers on the boxes are read from the outputs at each run.</text></svg>')
    return "".join(p)


if __name__ == "__main__":
    out = ROOT / "docs" / "data_flow.svg"
    out.write_text(svg())
    print(out)
