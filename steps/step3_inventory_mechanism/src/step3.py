"""Step 3 — inventory mechanism (bullwhip): orchestrator. Called by scripts/run_all.py after the tier panel is built,
or on its own: python steps/step3_inventory_mechanism/scripts/run.py

  3a inventory factors per company (inventory_factors.py)       3d why the chain amplifies (amplification.py)
  3b channel-inventory index (channel_index.py)                 3e channel call for the next prints (channel_call.py)
  3c bullwhip by link + slice multiplier (bullwhip.py)          report + figures (step3_report.py)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import ROOT, DATA_RAW
from inventory_factors import build_factors
from channel_index import build_channel
from bullwhip import link_table, concentration_table, slice_multiplier
from amplification import prior_cover_weeks, mechanism_tests, chain_consistency, predict_reduced
from channel_call import build_call

STEP = Path(__file__).resolve().parents[1]
CONFIG = STEP / "config"
WINDOWS = {"all": ("2021Q2", "2026Q2"), "destock": ("2022Q3", "2024Q1"), "normal": ("2024Q2", "2026Q2")}


def nordic_beats() -> pd.Series:
    """Nordic's guide error (actual / guide mid - 1, %) for every guided quarter in the raw series - the same series the
    guide-error model (step 7e) reads, so the state table and the model see the same record (F32)."""
    n = pd.read_csv(DATA_RAW / "nordic_quarterly.csv")
    n.index = pd.PeriodIndex(n["quarter"], freq="Q")
    mid = (n["guide_low_usdm"] + n["guide_high_usdm"]) / 2
    return ((n["revenue_usdm"] / mid - 1) * 100).dropna()


def derived_series(p: pd.DataFrame, f: pd.DataFrame) -> pd.DataFrame:
    """Panel plus the three series step 3 adds: Logitech sell-through YoY, Logitech purchases YoY, Nordic Bluetooth."""
    nordic = pd.read_csv(DATA_RAW / "nordic_quarterly.csv")
    sr = pd.Series(nordic["short_range_usdm"].values, index=pd.PeriodIndex(nordic["quarter"], freq="Q"))
    return p.assign(logi_sellthrough_yoy=(p["logi_sales_yoy"] + p["logi_st_gap"]).where(p["logi_st_gap"].notna()),
                    logi_purchases_yoy=f["logi_purchases_yoy"], nordic_short_range=sr.reindex(p.index))


def check_anchors(anchors: pd.DataFrame) -> pd.DataFrame:
    """Each anchor's quote fragment must be in its saved excerpt; web anchors defer to the verbal_metrics check."""
    vm = pd.read_csv(DATA_RAW / "verbal_metrics.csv")
    rows = []
    for _, a in anchors.iterrows():
        src = ROOT / a["source_file"] if not str(a["source_file"]).startswith("http") else None
        if src is not None and src.exists():
            ok = a["quote_fragment"] in " ".join(src.read_text().split())
            how = "fragment found in saved excerpt" if ok else "FRAGMENT NOT FOUND"
        else:
            hit = vm[(vm["company"] == a["company"]) & (vm["quarter"] == a["quarter"]) & (vm["quote"] == a["quote_fragment"])]
            ok = bool(len(hit)) and str(hit.iloc[0]["verified"]).startswith("found")
            how = f"verbal_metrics row verified={hit.iloc[0]['verified']}" if len(hit) else "no verbal_metrics row"
        rows.append({**a.to_dict(), "verified": ok, "check": how})
    return pd.DataFrame(rows)


def run_step3(p: pd.DataFrame, cfg: dict, write: bool = True) -> dict:
    im = cfg["inventory_mechanism"]
    fac = build_factors(p, cfg)
    f = fac["quarterly"]
    s = derived_series(p, f)
    anchors = check_anchors(pd.read_csv(CONFIG / "anchors.csv"))
    ch = build_channel(s, cfg)
    links = link_table(s, WINDOWS, im["bootstrap"])
    conc = concentration_table(fac["extracts"]["concentration"], s, f)
    ap_file = ROOT / "steps" / "step2_attribution" / "outputs" / "attribution_path.csv"
    ap = pd.read_csv(ap_file) if ap_file.exists() else None
    sl = slice_multiplier(conc, links, ap, im["slice_amplitude"]["top10_avg_customer_usdm_2023"])
    sample = tuple(im["accelerator"]["sample"])
    prior = prior_cover_weeks(f, cfg, sample)
    gap_proxy = f["comp_dist_dio_avg"] - f["comp_dist_dio_avg"].loc["2021Q1":"2026Q2"].mean()
    mech, fits = mechanism_tests(s, gap_proxy, prior, cfg)
    chain = chain_consistency(s, cfg)
    reduced = fits[("nordic", "A demand")]
    pred = predict_reduced(reduced, s["logi_sellthrough_yoy"], "2026Q3")
    call = build_call(p, f, ch, cfg)
    out = {"factors": f, "nordic_stage": fac["nordic_stage"], "series": s, "anchors": anchors, "channel": ch,
           "bullwhip": links, "concentration": conc, "slice": sl, "prior": prior, "mechanism": mech, "fits": fits,
           "chain": chain, "reduced": reduced, "prediction": pred, "call": call,
           "decisions": pd.read_csv(CONFIG / "decisions.csv")}
    if write:
        from step3_report import write_step3
        out["paths"] = write_step3(out, p, cfg)
        from cycle_state import run_cycle_state            # step 3b (D22): cycle state read from the mechanism data
        out["cycle"] = run_cycle_state(cfg, nordic_beats())        # every guided quarter (from 2019Q1), not only the panel's
        from nordic_channel import run_nordic_channel       # D25: Nordic's own channel size and wording vs the proxy
        out["nordic_channel"] = run_nordic_channel(conc, f, p, out["cycle"]["states"])
    return out
