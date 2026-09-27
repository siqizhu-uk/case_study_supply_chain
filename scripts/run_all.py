"""End-to-end run over the seven analysis steps (steps/step*/): filing confidence -> tier panel -> lags -> back-test -> attribution -> forecasts -> report -> dashboard.

    python scripts/run_all.py            # uses config/model.yaml
    python scripts/run_all.py --config my_variant.yaml
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for step in sorted((ROOT / "steps").glob("step*/src")):
    sys.path.insert(0, str(step))

from core.config import load_config, OUTPUTS as OUTPUTS_DIR  # noqa: E402
from core.ingest import load_all  # noqa: E402
from core.tiers import build_panel  # noqa: E402
from filing_confidence import run_step1  # noqa: E402   steps/step1_filing_confidence
from attribution import attribution, write_step2  # noqa: E402        steps/step2_attribution
from attribution_path import build_path, write_path, implied_content_series, time_varying_driver  # noqa: E402   steps/step2_attribution (2b)
from step3 import run_step3  # noqa: E402               steps/step3_inventory_mechanism
from supply_graph_report import run_step5  # noqa: E402   steps/step5_supply_graph (graph, lag kernel)
from lags import lag_analysis  # noqa: E402              steps/step4_lag_structure
from backtest import distributed_lag_regression, guidance_bias  # noqa: E402   steps/step6_backtest
from backtest_report import run_walkforward  # noqa: E402   steps/step6_backtest (walk-forward, point-in-time)
from chain_forecast import run_chain, chain_md  # noqa: E402   steps/step7_forecast (7c): the chain inside each forecast
from guidance_record import anchor_table  # noqa: E402   steps/step7_forecast
from guide_error_model import log_challenger, run_guide_error_model  # noqa: E402   steps/step7_forecast (7e): one model of the guide error
from margin_model import write_excess_outputs  # noqa: E402   steps/step7_forecast: channel-excess term in Nordic's GM (F25)
from forecast import forecast_nordic, forecast_logitech, forecast_gn, forecast_table  # noqa: E402   steps/step7_forecast
from scenarios import build_scenarios  # noqa: E402   steps/step7_forecast (7d): risk scenarios for the note
import cross_checks  # noqa: E402   steps/step7_forecast: independent checks beside the six forecasts (cross_checks.csv)
from prereg_q4 import log_q4  # noqa: E402   steps/step7_forecast: Nordic Q4 pre-registration, GR forecast / CH challenger (F22)
from forecast_next import forecast_next_quarter, next_quarter_md  # noqa: E402   steps/step7_forecast: Q4 2026 (h=2), graph-driven
from report import write_outputs  # noqa: E402
from dashboard import build_dashboard  # noqa: E402
from model_inventory import build_inventory  # noqa: E402   steps/step7_forecast: every model + its walk-forward performance
import pitfalls  # noqa: E402   steps/step7_forecast: the pitfall register (audit/pitfalls.csv)
sys.path.insert(0, str(ROOT))
from webapp.snapshot import take as snapshot_outputs  # noqa: E402   results page: remember this run's outputs


def _progress(stage: str) -> None:
    """One line per stage, so a run's log (and the dashboard's scenario sandbox) shows where it is."""
    print(f"[{datetime.now():%H:%M:%S}] {stage}", flush=True)


def main(argv=None) -> int:
    import runpy
    runpy.run_path(str(ROOT / 'scripts' / 'draw_data_flow.py'), run_name='__main__')      # docs/data_flow.svg (dashboard tab 2)
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None, help="alternative YAML (default config/model.yaml)")
    ap.add_argument("--no-dashboard", action="store_true")
    a = ap.parse_args(argv)
    if a.config:                                    # every module that loads the config in this run reads the variant
        os.environ["CASE_STUDY_CONFIG"] = str(Path(a.config).resolve())
    cfg = load_config(a.config)
    _progress("step 1 · filing confidence; data and the tier panel")
    step1 = run_step1()                       # filing confidence table (steps/step1_filing_confidence/outputs)
    data = load_all()
    p = build_panel(data, cfg)
    # step 2 first: the attribution PATH (share of Nordic per quarter) is an input to steps 4, 6 and 7 — the back-test must
    # use the share that was true in each quarter, not today's
    attr = attribution(cfg, panel=p)
    path = build_path(cfg, panel=p)
    write_path(path)
    attr["path"] = path
    paths_step2 = write_step2(attr)
    _progress("step 3 · inventory mechanism and channel state")
    step3 = run_step3(p, cfg)                 # inventory factors, channel index, bullwhip by link, channel call (reads step 2's path)
    _progress("step 5 · supply graph and lag kernel")
    step5 = run_step5(p, cfg)                 # supply graph: paths, lag kernel, point-in-time weights, SVG
    lag = lag_analysis(p, cfg, implied=implied_content_series(p, path), attr=attr)   # attr: step 2 shares fix the edge-2 slice (L7)
    reg_const = distributed_lag_regression(p, cfg)
    reg_tv = distributed_lag_regression(p, cfg, driver=time_varying_driver(p, path, cfg["regression"]["driver"]))
    reg = min((r for r in (reg_const, reg_tv) if r.get("ok")), key=lambda r: r["rmse_loo"], default=reg_const)
    reg["alternatives"] = {r["driver"]: {"rmse_loo": round(r["rmse_loo"], 2), "r2_in_sample": round(r["r2_in_sample"], 3), "sum_lag_effect": round(r["sum_lag_effect"], 2)}
                           for r in (reg_const, reg_tv) if r.get("ok")}
    gb = anchor_table(p, cfg)                     # guidance bias per company from the track record (F14)
    s3 = step3["series"].join(step3["factors"][["mchp_disti_days", "nordic_fwd_dio"]])
    _progress("step 6 · walk-forward back-test (the longest step)")
    wfr = run_walkforward(p, cfg, time_varying_driver(p, path, cfg["regression"]["driver"]), reg, s3=s3)
    _progress("step 7 · forecasts: chain terms, guide-error model, the six prints")
    chain = run_chain(p, cfg, path, wfr["walkforward"], wfr["live"])     # step 7c: lag, mechanism, attribution, breaks as terms
    gem = run_guide_error_model(p, cfg)                                   # step 7e: habit (pooled) + channel state -> expected guide error
    write_excess_outputs(p, cfg)                                          # F25: channel-excess GM term (peer estimate, Nordic walk-forward)
    fn = forecast_nordic(cfg, gb, reg, p, composite=wfr["composite"], chain=chain, gem=gem)
    fl = forecast_logitech(cfg, gb, p, chain=chain, gem=gem)
    fg = forecast_gn(cfg, p, gem=gem)
    log_challenger(gem, fn, cfg)                                           # F16 pooled Nordic model: pre-registered challenger (F20)
    for fc, co in ((fn, "nordic"), (fl, "logitech"), (fg, "gn")):   # step 3 cross-check next to each forecast (does not move the point, D15)
        fc["step3_channel_call"] = step3["call"].set_index("company").loc[co, ["state", "direction", "adj_low", "adj_mid", "adj_high", "unit",
                                                                               "config_line", "config_value", "config_inside_range", "watch_flag"]].to_dict()
    ftab = forecast_table(fn, fl, fg)
    paths = write_outputs(p, lag, reg, gb, attr, fn, fl, fg, ftab, cfg)
    nxt = forecast_next_quarter(p, cfg, time_varying_driver(p, path, cfg["regression"]["driver"]), wfr["metrics"][2],
                                event_usdm=chain["incident"]["nordic_q4_usdm"])       # F21: the incident's Q4 term (step 5d)
    nxt.round(2).to_csv(OUTPUTS_DIR / "forecast_next_quarter.csv", index=False)
    log_q4(nxt, chain, p, cfg)                                             # F22: pre-register Q4 (GR forecast, CH challenger)
    import logitech_odm                                                   # step 7f (F28): Logitech supply-side nowcast, pre-registered challenger
    logitech_odm.write(logitech_odm.run(p, cfg), cfg)
    chain["logitech_point"] = fl["point"]
    _progress("step 7 · scenarios and cross-checks")
    scen = build_scenarios(fn, gb, chain, cfg, fg, gem)                # reads forecast_next_quarter.csv just written
    scen.round(1).to_csv(OUTPUTS_DIR / "scenarios.csv", index=False)
    cross_checks.write()                                               # every check beside each forecast (reads the details, scenarios, chain terms)
    paths["cross_checks"] = cross_checks.OUT
    with open(paths["report"], "a") as f:                  # model_report.md
        f.write("\n" + chain_md(chain) + "\n" + next_quarter_md(nxt) + "\n## Risk scenarios (step 7d, outputs/scenarios.csv)\n\n"
                + scen.round(1).fillna("").to_markdown(index=False) + "\n")
    paths["next_quarter"] = OUTPUTS_DIR / "forecast_next_quarter.csv"
    paths["step1"] = step1["path"]
    paths["step2"] = paths_step2
    paths["step3"] = step3["paths"]["report"]
    paths["step6"] = wfr["report"]
    runpy.run_path(str(ROOT / "scripts" / "draw_data_flow.py"), run_name="__main__")   # re-label the data-flow diagram with this run's numbers
    _progress("deliverables · figures and dashboard")
    if not a.no_dashboard:                          # also refreshes deliverables/figures/ (the write-up's charts) before embedding them
        paths["dashboard"] = build_dashboard(p, data, lag, reg, gb, attr, fn, fl, fg, ftab, cfg, inv=build_inventory())
    pitfalls.write_md(pitfalls.load())
    paths["pitfalls"] = OUTPUTS_DIR / "pitfalls.md"
    paths["run_snapshot"] = snapshot_outputs()       # the results page (scripts/serve.py) diffs against earlier runs
    print("\n=== FORECASTS ===")
    print(ftab.to_string(index=False))
    print("\nOutputs:")
    for k, v in paths.items():
        print(f"  {k:10s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
