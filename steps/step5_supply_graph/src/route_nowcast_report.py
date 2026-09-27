"""Step 5f — run, score, pre-register and write the route-proxy nowcast of Logitech's unreported quarter (decision G27).

Run by supply_graph_report.run_step5 after step 5e, or alone:
    python steps/step5_supply_graph/src/route_nowcast_report.py
Outputs (steps/step5_supply_graph/outputs/): route_nowcast.csv (quarter x model nowcasts vs actual, walk-forward +
live), route_nowcast_nordic.csv (Nordic h=2 GR / CH per model), route_nowcast_scores.csv, route_nowcast_availability.csv,
route_nowcast.md, route_nowcast_prereg_log.csv (append-only: one row per model x spec x data).
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

if __name__ == "__main__":                              # CLI: make core and the step folders importable
    _R = Path(__file__).resolve().parents[3]
    sys.path[:0] = [str(_R)] + [str(s) for s in sorted((_R / "steps").glob("step*/src"))]

from core.config import step_outputs  # noqa: E402

PANEL_COLS = ["nordic_consumer_yoy", "nordic_rev", "nordic_consumer", "nordic_guide_mid", "nordic_beat_vs_guide_pct",
              "logi_sales_yoy", "logi_st_gap", "logi_sales", "logi_guide_mid"]
SPEC_KEYS = ("route_nowcast", "supply_graph", "backtest")      # everything that moves a live number (P101)
PREREG = "route_nowcast_prereg_log.csv"


def checks(p: pd.DataFrame, cfg: dict, nordic: dict) -> dict:
    """Replication: N0 / N1 graph demand vs step 6's own GR / GRg designs (propagate), max |diff| on common quarters."""
    from walkforward import design                   # steps/step6_backtest/src
    wf = nordic["wf"]
    out = {}
    for m, model in (("N0", "GR"), ("N1", "GRg")):
        mine = wf[wf["model"] == m].set_index("quarter")["graph_demand"]
        mine.index = pd.PeriodIndex(mine.index, freq="Q")
        ref = design(p, model, cfg, None, int(cfg["route_nowcast"]["nordic_horizon"]))["graph_demand"].reindex(mine.index)
        out[f"graph_demand_{m}_vs_step6_{model}_max_abs"] = float((mine - ref).abs().max())
    return out


def run(p: pd.DataFrame, cfg: dict) -> dict:
    import route_nowcast as rn
    import route_nowcast_nordic as rnn
    import route_nowcast_scores as sc
    from route_nowcast_availability import availability
    from route_nowcast_md import logitech_share
    rc = cfg["route_nowcast"]
    S = rn.sources(p, cfg)
    live_q = pd.Period(rc["live_quarter"], "Q")
    y = rn.series(S["logitech"])
    quarters = list(pd.period_range(y.index.min() + 1, live_q, freq="Q"))
    wf = rn.walk_forward(S, cfg, quarters)
    nordic = rnn.walk_forward(p, cfg, wf)
    ns, nd = sc.nowcast_scores(wf, cfg), sc.nordic_scores(nordic["wf"], cfg)
    return {"S": S, "wf": wf, "nordic": nordic, "nowcast_scores": ns, "nordic_scores": nd, "adoption": sc.adoption(ns, nd, cfg),
            "availability": availability(p, cfg, S, live_q), "checks": checks(p, cfg, nordic), "live_q": live_q,
            "snx_share": logitech_share(p, cfg),
            "hashes": {"spec": spec_hash(cfg), "data": data_hash(p, cfg, S, live_q)}}


def spec_hash(cfg: dict) -> str:
    spec = {k: cfg[k] for k in SPEC_KEYS}
    spec["route_nowcast"] = {k: v for k, v in spec["route_nowcast"].items() if k != "check_on"}
    spec["asp"] = cfg["structural_breaks"]["distributor_asp_inflation_2026"]
    return hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:10]


def data_hash(p: pd.DataFrame, cfg: dict, S: dict, q: pd.Period) -> str:
    """Fingerprint of every input of the live numbers: the vintage at origin(q), the panel columns GR / CH read, the share path."""
    import route_nowcast as rn
    import route_nowcast_data as rnd
    from route_nowcast_nordic import SHARE_PATH
    V = rn.vintage(S, rnd.origin(q, cfg))
    parts = [V[k].round(6).to_csv() for k in sorted(V)] + [p[[c for c in PANEL_COLS if c in p]].round(6).to_csv(), SHARE_PATH.read_text()]
    return hashlib.sha1("".join(parts).encode()).hexdigest()[:10]


def prereg_rows(res: dict, cfg: dict) -> list[dict]:
    """Live rows to log: the default and every candidate with a live value (never a comparison-only model: user rule)."""
    rc, wf, live = cfg["route_nowcast"], res["wf"], res["nordic"]["live"].set_index("model")
    q, verdict = str(res["live_q"]), res["adoption"]["verdict"].iloc[0]
    keep = [rc["adoption"]["default"]] + [m for m in rc["adoption"]["candidates"] if bool(wf.loc[q, f"{m}_fitted"])]
    return [{"logitech_quarter": q, "nordic_target": str(live.loc[m, "quarter"]), "model": m, "role": "default" if m == rc["adoption"]["default"] else "candidate",
             "adopted": m == verdict, "spec_hash": res["hashes"]["spec"], "data_hash": res["hashes"]["data"], "logged_on": date.today().isoformat(),
             "logitech_st_yoy_nowcast": round(float(wf.loc[q, m]), 2), "nordic_gr_usdm": round(float(live.loc[m, "GR_total"]), 1),
             "nordic_ch_usdm": round(float(live.loc[m, "CH_total"]), 1), "check_on": rc["check_on"],
             "logitech_st_yoy_actual": "", "nordic_actual_usdm": "", "scored_on": ""} for m in keep]


def preregister(res: dict, cfg: dict, d: Path) -> pd.DataFrame:
    """Append each live row once per (model, spec, data); the last row logged before the print is the record."""
    f = d / PREREG
    new = pd.DataFrame(prereg_rows(res, cfg))
    log = pd.read_csv(f, dtype=str) if f.exists() else pd.DataFrame(columns=new.columns)
    key = ["logitech_quarter", "model", "spec_hash", "data_hash"]
    seen = set(map(tuple, log[key].astype(str).values))
    add = new[[tuple(map(str, r)) not in seen for r in new[key].values]]
    out = pd.concat([log, add.astype(str)], ignore_index=True) if len(add) else log
    if len(add) or not f.exists():
        out.to_csv(f, index=False)
    return out


def write(res: dict, cfg: dict) -> dict:
    from route_nowcast_md import report_md
    d = step_outputs("step5_supply_graph")
    out = {k: d / f"route_nowcast{s}" for k, s in (("nowcast", ".csv"), ("nordic", "_nordic.csv"), ("scores", "_scores.csv"),
                                                   ("availability", "_availability.csv"), ("md", ".md"))}
    res["wf"].assign(kind=np.where(res["wf"]["actual"].notna(), "walkforward", "live")).round(3).to_csv(out["nowcast"])
    pd.concat([res["nordic"]["wf"], res["nordic"]["live"]]).round(3).to_csv(out["nordic"], index=False)
    pd.concat([res["nowcast_scores"].assign(table="nowcast vs N0"), res["nordic_scores"].assign(table="Nordic h=2 vs N0 version"),
               res["adoption"].assign(table="adoption")], ignore_index=True).round(3).to_csv(out["scores"], index=False)
    res["availability"].round(2).to_csv(out["availability"], index=False)
    res["prereg"] = preregister(res, cfg, d)
    out["md"].write_text(report_md(res, cfg))
    out["prereg"] = d / PREREG
    return out


def run_route_nowcast(p: pd.DataFrame, cfg: dict, write_files: bool = True) -> dict:
    res = run(p, cfg)
    if write_files:
        res["paths"] = write(res, cfg)
    return res


if __name__ == "__main__":
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    _cfg = load_config(sys.argv[1] if len(sys.argv) > 1 else None)
    _res = run_route_nowcast(build_panel(load_all(), _cfg), _cfg)
    print(_res["nowcast_scores"].round(2).to_string(index=False))
    print(_res["nordic_scores"].round(2).to_string(index=False))
    print(_res["adoption"].round(2).to_string(index=False))
    print(_res["checks"])
