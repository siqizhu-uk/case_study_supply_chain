"""Step 3a — inventory factors per company and quarter. Every factor is one formula (README section 2):

  DIO          = inventory_t / COGS_t x 91.25                        own-balance-sheet days on trailing cost of sales
  forward DIO  = inventory_t / E_t[COGS_{t+1}] x 91.25               days on the NEXT quarter's guided cost of sales
  spread       = YoY%(inventory or stage) - YoY%(revenue)            Bernard & Noel (1991); Thomas & Zhang (2002)
  FG share     = finished goods / inventory
  FG weeks     = finished goods / COGS_t x 13                        OEM finished-goods cover
  DSO          = receivables_t / revenue_t x 91.25
  purchases    = COGS_t + inventory_t - inventory_{t-1}              what the company bought from its suppliers
  distributor DIO (Arrow, Avnet) and Microchip distributor days      component-channel cover

Inputs: the tier panel (Pipeline A company CSVs) plus the step-3 extracts written by Pipeline A
(inventory_detail_xbrl.csv, mchp_distributor_days.csv, nordic_balance_extract.csv, nordic_inventory_stage.csv).
"""
from __future__ import annotations

import pandas as pd

from core.config import DATA_RAW

DAYS_Q = 91.25


def _yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(4) - 1.0) * 100.0


def dio(inv: pd.Series, cogs: pd.Series, days: float = DAYS_Q) -> pd.Series:
    return inv / cogs * days


def forward_dio(inv: pd.Series, next_cogs: pd.Series, days: float = DAYS_Q) -> pd.Series:
    return inv / next_cogs * days


def growth_spread(a: pd.Series, b: pd.Series) -> pd.Series:
    return _yoy(a) - _yoy(b)


def dso(ar: pd.Series, rev: pd.Series, days: float = DAYS_Q) -> pd.Series:
    return ar / rev * days


def purchases(cogs: pd.Series, inv: pd.Series) -> pd.Series:
    return cogs + inv.diff()


# ------------------------------------------------------------------ loaders for the Pipeline A step-3 extracts
def _qidx(df: pd.DataFrame, col: str = "quarter") -> pd.DataFrame:
    return df.assign(**{col: pd.PeriodIndex(df[col], freq="Q")}).set_index(col)


def load_extracts() -> dict[str, pd.DataFrame]:
    det = pd.read_csv(DATA_RAW / "inventory_detail_xbrl.csv")
    wide = det.pivot_table(index="quarter", columns=["company", "metric"], values="value_usdm")
    wide.index = pd.PeriodIndex(wide.index, freq="Q")
    return {"xbrl": wide,
            "mchp": _qidx(pd.read_csv(DATA_RAW / "mchp_distributor_days.csv")),
            "nordic_bal": _qidx(pd.read_csv(DATA_RAW / "nordic_balance_extract.csv")),
            "nordic_stage": pd.read_csv(DATA_RAW / "nordic_inventory_stage.csv"),
            "concentration": pd.read_csv(DATA_RAW / "nordic_customer_concentration.csv")}


# ------------------------------------------------------------------ per company
def logitech_factors(p: pd.DataFrame, x: pd.DataFrame) -> pd.DataFrame:
    idx = p.index
    sales = p["logi_sales"]
    cogs = sales * (1 - p["logi_gm_gaap"] / 100)                     # GAAP: the balance sheet is GAAP
    lx = x["logitech"].reindex(idx)
    guide_cogs = (p["logi_guide_mid"] * (1 - p["logi_gm_adj"].fillna(p["logi_gm_gaap"]) / 100)).shift(-1)
    f = pd.DataFrame(index=idx)
    f["logi_dio"] = dio(p["logi_inventory"], cogs)
    f["logi_fwd_dio"] = forward_dio(p["logi_inventory"], guide_cogs)                 # guided quarters only (2025Q1+)
    f["logi_fwd_dio_expost"] = forward_dio(p["logi_inventory"], cogs.shift(-1))     # realised next-quarter COGS (look-ahead: diagnostics only)
    f["logi_inv_spread"] = growth_spread(p["logi_inventory"], sales)
    f["logi_fg_share"] = lx["inv_finished_goods"] / lx["inventory"]
    f["logi_fg_weeks"] = lx["inv_finished_goods"] / cogs * 13
    f["logi_fg_spread"] = growth_spread(lx["inv_finished_goods"], sales)
    f["logi_rm_spread"] = growth_spread(lx["inv_raw_materials"], sales)
    f["logi_dso"] = dso(lx["receivables"], sales)
    f["logi_dso_yoy_chg"] = f["logi_dso"].diff(4)
    f["logi_purchases_usdm"] = purchases(cogs, p["logi_inventory"])
    f["logi_purchases_yoy"] = _yoy(f["logi_purchases_usdm"])
    return f


def nordic_factors(p: pd.DataFrame, bal: pd.DataFrame, break_q: str) -> pd.DataFrame:
    idx = p.index
    rev = p["nordic_rev"]
    cogs = rev * (1 - p["nordic_gm_adj"] / 100)
    # Nordic guides revenue as a range and gross margin as a floor ('above 50%') -> next-quarter COGS at the trailing margin
    guide_cogs_next = p["nordic_guide_mid"].shift(-1) * (1 - p["nordic_gm_adj"] / 100)
    ar = bal["receivables_usdm"].reindex(idx)
    f = pd.DataFrame(index=idx)
    f["nordic_dio"] = dio(p["nordic_inventory"], cogs)
    f["nordic_fwd_dio"] = forward_dio(p["nordic_inventory"], guide_cogs_next)
    f["nordic_inv_spread"] = growth_spread(p["nordic_inventory"], rev)
    f["nordic_dso"] = dso(ar, rev)
    chg = f["nordic_dso"].diff(4)
    brk = pd.Period(break_q, "Q")
    f["nordic_dso_yoy_chg"] = chg.where(idx >= brk + 4)               # 'improved collection' in 2024: no YoY across the break
    f["nordic_ar_spread"] = growth_spread(ar, rev).where(idx >= brk + 4)
    return f


def nordic_stage_table(stage: pd.DataFrame, p: pd.DataFrame) -> pd.DataFrame:
    """Year-end inventory by stage (AR note) with each stage's growth minus revenue growth (Bernard-Noel by stage)."""
    rev_y = p["nordic_rev"].groupby(p.index.year).sum(min_count=4)
    s = stage.set_index("year")[["raw_materials_usdm", "work_in_progress_usdm", "finished_goods_usdm", "total_usdm"]].copy()
    s["revenue_usdm"] = rev_y.reindex(s.index)
    for k in ("raw_materials", "work_in_progress", "finished_goods", "total"):
        s[f"{k}_share"] = s[f"{k}_usdm"] / s["total_usdm"]
        s[f"{k}_spread_pts"] = (s[f"{k}_usdm"].pct_change() - s["revenue_usdm"].pct_change()) * 100
    cogs_q4 = (p["nordic_rev"] * (1 - p["nordic_gm_adj"] / 100)).groupby(p.index.year).last()
    s["finished_goods_weeks_on_q4_cogs"] = s["finished_goods_usdm"] / cogs_q4.reindex(s.index) * 13
    return s.round(3)


def distributor_factors(p: pd.DataFrame, x: pd.DataFrame, mchp: pd.DataFrame) -> pd.DataFrame:
    idx = p.index
    f = pd.DataFrame(index=idx)
    for c in ("arrow", "avnet"):
        cx = x[c].reindex(idx)
        f[f"{c}_dio"] = dio(cx["inventory"], cx["cogs"])
        f[f"{c}_dio_yoy_chg"] = f[f"{c}_dio"].diff(4)
        f[f"{c}_sales_yoy"] = _yoy(cx["revenue"])
    f["comp_dist_dio_avg"] = f[["arrow_dio", "avnet_dio"]].mean(axis=1)
    f["mchp_disti_days"] = mchp["disti_days"].reindex(idx)
    lo, hi = mchp["range10y_low"].reindex(idx), mchp["range10y_high"].reindex(idx)
    f["mchp_pos_in_10y_range"] = (f["mchp_disti_days"] - lo) / (hi - lo)      # 0 = ten-year low, 1 = ten-year high (range from the filing)
    f["it_dist_dio_avg"] = p["dist_inv_days_avg"]                     # Ingram / TD Synnex (Logitech side), existing panel
    return f


def build_factors(p: pd.DataFrame, cfg: dict, ex: dict | None = None) -> dict:
    ex = ex or load_extracts()
    im = cfg["inventory_mechanism"]
    brk = im["channel_call"]["dso_break_quarter"]["nordic"]
    q = pd.concat([nordic_factors(p, ex["nordic_bal"], brk), logitech_factors(p, ex["xbrl"]),
                   distributor_factors(p, ex["xbrl"], ex["mchp"])], axis=1)
    q["nordic_dist_state"] = p["nordic_dist_state"]
    q["logi_st_gap"] = p["logi_st_gap"]
    q["gn_st_gap"] = p["gn_st_gap"]
    return {"quarterly": q, "nordic_stage": nordic_stage_table(ex["nordic_stage"], p), "extracts": ex}
