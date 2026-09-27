"""Step 5g — run, score, pre-register and write the industry-cycle challenger for Nordic one quarter past the guide (G29).

Run by supply_graph_report.run_step5 after step 5f, or alone:
    python steps/step5_supply_graph/src/cycle_challenger_report.py
Outputs (steps/step5_supply_graph/outputs/): cycle_challenger.csv (walk-forward rows + live), cycle_challenger_scores.csv,
cycle_challenger.md, cycle_challenger_prereg_log.csv (append-only: one row per target x model x spec x data).
Spec hash: the config the model reads (cycle_challenger block, backtest, regimes, the origin and RSEAS release rule, band_z) and the
code that turns the regressors' source columns into the live number (this step's modules, step 6 walkforward, the panel builder).
Data hash: the point-in-time regressor values, the Nordic / guide columns the forecast reads and the incident term.
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

from core.config import ROOT, step_outputs  # noqa: E402

PREREG = "cycle_challenger_prereg_log.csv"
SRC = ROOT / "steps" / "step5_supply_graph" / "src"
SPEC_FILES = [SRC / "cycle_challenger.py", SRC / "cycle_challenger_report.py", SRC / "route_nowcast_data.py",
              ROOT / "steps" / "step6_backtest" / "src" / "walkforward.py", ROOT / "core" / "tiers.py"]
DATA_COLS = ["nordic_consumer_yoy", "nordic_rev", "nordic_consumer", "nordic_guide_mid", "nordic_beat_vs_guide_pct", "regime"]
KEY = ["target", "model", "spec_hash", "data_hash"]


def spec_hash(cfg: dict, files: list[Path] | None = None) -> str:
    rn = cfg["route_nowcast"]
    spec = {"cycle_challenger": {k: v for k, v in cfg["cycle_challenger"].items() if k != "check_on"},
            "backtest": cfg["backtest"], "regimes": cfg["regimes"], "band_z": cfg["forecast_next_quarter"]["band_z"],
            "origin_days": rn["origin_days_after_quarter_end"], "rseas_release": rn["release_lag"]["rseas"]}
    h = hashlib.sha1(json.dumps(spec, sort_keys=True, default=str).encode())
    for f in SPEC_FILES if files is None else files:
        h.update(f.read_bytes() if f.exists() else b"missing:" + f.name.encode())
    return h.hexdigest()[:10]


def data_hash(p: pd.DataFrame, cfg: dict, event_usdm: float) -> str:
    import cycle_challenger as cc
    t = pd.Period(cfg["cycle_challenger"]["live_target"], "Q")
    pe = p.reindex(p.index.union(pd.period_range(p.index.min(), t, freq="Q")))
    X = cc.designs(pe, cfg)[cfg["cycle_challenger"]["primary"]]
    parts = [X.round(6).to_csv(), p[[c for c in DATA_COLS if c in p]].round(6).to_csv(), f"{event_usdm:.4f}"]
    return hashlib.sha1("".join(parts).encode()).hexdigest()[:10]


def incident_q4(cfg: dict) -> float:
    """Logitech's supplier incident pushed to Nordic Q4 (step 5d / F21), the term every Q4 model carries."""
    from chain_forecast import supplier_incident        # steps/step7_forecast/src (read only)
    from route_nowcast_nordic import SHARE_PATH
    return float(supplier_incident(cfg, pd.read_csv(SHARE_PATH))["nordic_q4_usdm"])


def live_table(lv: dict, own: pd.DataFrame, cfg: dict, event: float) -> pd.DataFrame:
    """Q4 side by side: GB, GR, CH and each CYC model, ex and with the incident term, band = z x walk-forward RMSE (CYC)."""
    z, rows = float(cfg["forecast_next_quarter"]["band_z"]), []
    rm = own.set_index("model")["rmse"]
    for m in ["GB", "GR", "CH"] + list(cfg["cycle_challenger"]["models"]):
        pt = float(lv[f"{m}_total"])
        band = z * float(rm[m]) if m in rm else np.nan
        rows.append({"quarter": lv["quarter"], "model": m, "total_ex_event": pt, "event_usdm": event, "point": pt + event,
                     "low": pt + event - band, "high": pt + event + band, "wf_rmse": float(rm[m]) if m in rm else np.nan,
                     "minus_CH": pt - float(lv["CH_total"]), "minus_GB": pt - float(lv["GB_total"])})
    return pd.DataFrame(rows)


def run(p: pd.DataFrame, cfg: dict) -> dict:
    import cycle_challenger as cc
    import cycle_challenger_scores as sc
    wf = cc.walk_forward(p, cfg)
    flip = not cfg["backtest"]["exclude_supply_constrained_from_training"]
    wf_flip = cc.walk_forward(p, cfg, exclude_sc=flip)
    scores = pd.concat([sc.scores(wf, cfg), sc.scores(wf_flip, cfg, scope=f"sensitivity: exclude_supply_constrained={flip}"),
                        sc.own_quarters(wf, cfg)], ignore_index=True)
    lv, event = cc.live(p, cfg), incident_q4(cfg)
    prim = cfg["cycle_challenger"]["primary"]
    return {"wf": wf, "scores": scores, "adoption": sc.adoption(scores, cfg), "live": lv, "event": event,
            "availability": cc.availability(p, cfg), "enc_drop_one": sc.encompassing_drop_one(wf, cfg, prim, "GR"),
            "live_table": live_table(lv, sc.own_quarters(wf, cfg), cfg, event),
            "hashes": {"spec": spec_hash(cfg), "data": data_hash(p, cfg, event)}}


def prereg_row(res: dict, cfg: dict) -> dict:
    cc = cfg["cycle_challenger"]
    m, lv = cc["primary"], res["live"]
    t = res["live_table"].set_index("model")
    x = cc["models"][m]["regressors"][0]
    a, b = lv[f"{m}_coef"][:2]
    return {"target": lv["quarter"], "model": m, "role": "challenger (pre-registered; not in the Q4 forecast)", "origin": lv["origin"],
            "point": round(t.loc[m, "point"], 1), "low": round(t.loc[m, "low"], 1), "high": round(t.loc[m, "high"], 1),
            "event_usdm": round(res["event"], 2), "wf_rmse_usdm": round(t.loc[m, "wf_rmse"], 1), "regressor": x,
            "regressor_quarter": str(pd.Period(lv["quarter"], "Q") - int(cc["lag_quarters"])),
            "regressor_value": round(lv[f"{m}_x_{x}"], 2), "intercept": round(a, 3), "slope": round(b, 3), "ntrain": int(lv[f"{m}_ntrain"]),
            "gr_usdm": round(t.loc["GR", "point"], 1), "ch_usdm": round(t.loc["CH", "point"], 1), "gb_usdm": round(t.loc["GB", "point"], 1),
            "bar_met": bool(res["adoption"]["bar_met"]), "spec_hash": res["hashes"]["spec"], "data_hash": res["hashes"]["data"],
            "logged_on": date.today().isoformat(), "check_on": cc["check_on"], "actual_usdm": "", "scored_on": "",
            "abs_error_usdm": "", "gr_abs_error_usdm": ""}


def preregister(res: dict, cfg: dict, d: Path) -> pd.DataFrame:
    """Append the live row once per (target, model, spec, data); the last row logged before the print is the record."""
    f = d / PREREG
    new = pd.DataFrame([prereg_row(res, cfg)]).astype(str)
    log = pd.read_csv(f, dtype=str, keep_default_na=False) if f.exists() else pd.DataFrame(columns=new.columns)
    seen = set(map(tuple, log[KEY].values)) if len(log) else set()
    add = new[[tuple(r) not in seen for r in new[KEY].values]]
    out = pd.concat([log, add], ignore_index=True) if len(add) else log
    if len(add) or not f.exists():
        out.to_csv(f, index=False)
    return out


def write(res: dict, cfg: dict) -> dict:
    from cycle_challenger_md import report_md
    d = step_outputs("step5_supply_graph")
    out = {"wf": d / "cycle_challenger.csv", "scores": d / "cycle_challenger_scores.csv", "md": d / "cycle_challenger.md", "prereg": d / PREREG}
    live_row = pd.DataFrame([{k: v for k, v in res["live"].items() if not k.endswith("_coef")}]).set_index("quarter")
    pd.concat([res["wf"].assign(kind="walkforward"), live_row.assign(kind="live")]).round(3).to_csv(out["wf"])
    adopt = pd.DataFrame([{"scope": "adoption bar (primary vs GR)", **res["adoption"]}])
    pd.concat([res["scores"], adopt, res["live_table"].assign(scope="live")], ignore_index=True).round(3).to_csv(out["scores"], index=False)
    res["prereg"] = preregister(res, cfg, d)
    out["md"].write_text(report_md(res, cfg))
    return out


def run_cycle_challenger(p: pd.DataFrame, cfg: dict, write_files: bool = True) -> dict:
    res = run(p, cfg)
    if write_files:
        res["paths"] = write(res, cfg)
    return res


if __name__ == "__main__":
    from core.config import load_config
    from core.ingest import load_all
    from core.tiers import build_panel
    _args = [a for a in sys.argv[1:] if not a.startswith("--")]
    _cfg = load_config(_args[0] if _args else None)
    _res = run_cycle_challenger(build_panel(load_all(), _cfg), _cfg, write_files="--no-write" not in sys.argv)
    print(_res["scores"].round(2).to_string(index=False))
    print(_res["adoption"])
    print(_res["live_table"].round(1).to_string(index=False))
