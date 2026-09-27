"""Construct the tier-by-tier quarterly panel.

Tier 0  sell_out   : proxy = Logitech BLE-category YoY + (sell-through minus sell-in gap)
Tier 1  distributor: Ingram / TD Synnex sales, inventory days, endpoint growth
Tier 2  oem        : Logitech BLE-relevant categories; GN Enterprise + SteelSeries (DKK)
Tier 3  component  : Nordic revenue / consumer revenue, own inventory days, distributor state

All growth rates are year-on-year (%). Inventory days = inventory / quarterly COGS * 91.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import load_config, MACRO_PROC

DAYS_Q = 91.25


def _yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(4) - 1.0) * 100.0


def _inv_days(inv: pd.Series, revenue: pd.Series, gm_pct: pd.Series) -> pd.Series:
    cogs = revenue * (1 - gm_pct / 100.0)
    return inv / cogs * DAYS_Q


def build_panel(data: dict[str, pd.DataFrame], cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_config()
    sb = cfg["structural_breaks"]
    idx = pd.period_range("2020Q1", "2026Q3", freq="Q")
    p = pd.DataFrame(index=idx)

    # ---------------- Tier 3: Nordic ----------------
    n = data["nordic"].reindex(idx)
    p["nordic_rev"] = n["revenue_usdm"]
    p["nordic_consumer"] = n["consumer_usdm"]
    p["nordic_ind_health"] = n["ind_health_usdm"]
    gm = n["gm_pct"].copy()
    if sb["nordic_q2_2024_writedown"]["apply"]:
        gm.loc[pd.Period("2024Q2", "Q")] = sb["nordic_q2_2024_writedown"]["adj_gm_pct"]
    if sb["nordic_q4_2025_gm_oneoff"]["apply"]:
        gm.loc[pd.Period("2025Q4", "Q")] = sb["nordic_q4_2025_gm_oneoff"]["adj_gm_pct"]
    p["nordic_gm_adj"] = gm
    p["nordic_gm_reported"] = n["gm_pct"]
    p["nordic_inventory"] = n["inventory_usdm"]
    p["nordic_inv_days"] = _inv_days(n["inventory_usdm"], n["revenue_usdm"], gm)
    p["nordic_inv_days_chg"] = p["nordic_inv_days"].diff()
    p["nordic_dist_state"] = n["dist_inventory_state"]
    p["nordic_backlog"] = n["backlog_usdm"]
    p["nordic_guide_mid"] = (n["guide_low_usdm"] + n["guide_high_usdm"]) / 2
    p["nordic_rev_yoy"] = _yoy(p["nordic_rev"])
    p["nordic_consumer_yoy"] = _yoy(p["nordic_consumer"])
    p["nordic_beat_vs_guide_pct"] = (p["nordic_rev"] / p["nordic_guide_mid"] - 1) * 100

    # ---------------- Tier 2: Logitech ----------------
    l = data["logitech"].reindex(idx)
    p["logi_sales"] = l["net_sales_usdm"]
    rc = cfg["radio_content"]["logitech"]
    core = [k for k, v in rc.items() if v.get("core")]
    # core radio series: lines present in both Logitech taxonomies -> like-for-like YoY from 2021Q2
    p["logi_radio_core"] = sum(rc[k]["weight"] * l[k] for k in core).where(l[core].notna().all(axis=1))
    # broad radio series: every line weighted by its radio content (new taxonomy only, from 2022Q2)
    p["logi_radio_all"] = sum(rc[k]["weight"] * l[k] for k in rc).where(l[list(rc)].notna().all(axis=1))
    p["logi_ble"] = p["logi_radio_all"]            # kept for backward compatibility
    p["logi_ble_ex_headsets"] = p["logi_radio_core"]
    gm_l = l["gm_nongaap_pct"].copy()
    if sb["logitech_tariff_refund_q1fy27"]["apply"]:
        q = pd.Period("2026Q2", "Q")
        gm_l.loc[q] = gm_l.loc[q] + sb["logitech_tariff_refund_q1fy27"]["adj_gm_pts"]
    p["logi_gm_adj"] = gm_l
    p["logi_gm_gaap"] = l["gm_gaap_pct"]
    p["logi_inventory"] = l["inventory_usdm"]
    p["logi_inv_days"] = _inv_days(l["inventory_usdm"], l["net_sales_usdm"], gm_l)
    p["logi_st_gap"] = l["sellthrough_minus_sellin_pts"]
    p["logi_guide_mid"] = (l["guide_low_usdm"] + l["guide_high_usdm"]) / 2
    p["logi_sales_yoy"] = _yoy(p["logi_sales"])
    p["logi_radio_core_yoy"] = _yoy(p["logi_radio_core"])
    p["logi_radio_all_yoy"] = _yoy(p["logi_radio_all"])
    p["logi_ble_yoy"] = p["logi_radio_core_yoy"]   # regression driver (longest like-for-like history)
    p["logi_beat_vs_guide_pct"] = (p["logi_sales"] / p["logi_guide_mid"] - 1) * 100
    p["logi_americas_yoy"] = _yoy(l["americas_usdm"])
    p["logi_emea_yoy"] = _yoy(l["emea_usdm"])

    # ---------------- Tier 0 proxy ----------------
    # Sell-out YoY ≈ sell-in YoY + (sell-through − sell-in gap). Gap is Logitech's own verbal disclosure.
    p["sellout_proxy_yoy"] = p["logi_sales_yoy"] + p["logi_st_gap"].fillna(0.0)

    # ---------------- Tier 2: GN ----------------
    g = data["gn"].reindex(idx)
    rg = cfg["radio_content"]["gn"]
    gam = g["gaming_div_rev_dkkm"].fillna(g["steelseries_rev_dkkm"])
    cons = g["consumer_rev_dkkm"].fillna(0.0).clip(lower=0)   # wind-down residuals (-3..-6) -> 0; blank 2026 -> 0
    parts = {"enterprise_rev_dkkm": g["enterprise_rev_dkkm"], "gaming_div_rev_dkkm": gam,
             "consumer_rev_dkkm": cons, "hearing_rev_dkkm": g["hearing_rev_dkkm"]}
    p["gn_radio_all"] = sum(rg[k]["weight"] * v for k, v in parts.items()).where(g["enterprise_rev_dkkm"].notna() & g["hearing_rev_dkkm"].notna())
    p["gn_periph_dkk"] = g["enterprise_rev_dkkm"] + gam      # Enterprise + Gaming: the PC/office-peripheral subset
    p["gn_enterprise_dkk"] = g["enterprise_rev_dkkm"]
    p["gn_gaming_dkk"] = g["gaming_div_rev_dkkm"].fillna(g["steelseries_rev_dkkm"])  # Gaming division (2024+) else SteelSeries
    p["gn_cont_ops_rev"] = g["cont_ops_rev_dkkm"]
    p["gn_cont_ops_ebita_adj_m"] = g["cont_ops_ebita_adj_margin_pct"]
    p["gn_cont_ops_gm"] = g["cont_ops_gm_pct"]
    p["gn_enterprise_org"] = g["enterprise_org_pct"]
    p["gn_gaming_org"] = g["gaming_org_ex_winddown_pct"].fillna(g["steelseries_org_pct"])
    p["gn_inventory"] = g["inventory_dkkm"]
    p["gn_hearing_dkk"] = g["hearing_rev_dkkm"]
    p["gn_st_gap"] = g["enterprise_sellout_minus_sellin_pts"]     # Enterprise sell-out minus sell-in, pts (verbal; est. flagged in raw)
    p["gn_group_rev"] = g["group_rev_dkkm"]
    p["gn_periph_yoy"] = _yoy(p["gn_periph_dkk"])
    p["gn_radio_all_yoy"] = _yoy(p["gn_radio_all"])

    # ---------------- Tier 1: distributors ----------------
    i = data["ingram"].reindex(idx)
    p["ingm_sales"] = i["net_sales_usdm"]
    p["ingm_inv_days"] = i["inventory_usdm"] / (i["net_sales_usdm"] - i["gross_profit_usdm"]) * DAYS_Q
    p["ingm_sales_yoy"] = _yoy(p["ingm_sales"])
    p["ingm_ces_yoy"] = i["ces_yoy_pct"]
    t = data["tdsynnex"].reindex(idx)
    p["snx_sales"] = t["revenue_usdm"]
    p["snx_inv_days"] = t["inventory_usdm"] / (t["revenue_usdm"] - t["gross_profit_usdm"]) * DAYS_Q
    p["snx_sales_yoy"] = _yoy(p["snx_sales"])
    mb = sb.get("tdsynnex_techdata_merger_2021", {})
    if mb.get("apply"):
        lo, hi = (pd.Period(q, "Q") for q in mb["no_yoy_quarters"])
        p.loc[(p.index >= lo) & (p.index <= hi), "snx_sales_yoy"] = np.nan
    p["snx_endpoint_yoy"] = t["endpoint_gb_yoy_pct"]
    p["dist_inv_days_avg"] = p[["ingm_inv_days", "snx_inv_days"]].mean(axis=1)
    p["dist_inv_days_chg"] = p["dist_inv_days_avg"].diff()
    if sb["distributor_asp_inflation_2026"]["apply"]:
        mask = p.index >= pd.Period("2026Q1", "Q")
        p.loc[mask, "snx_endpoint_units_yoy"] = p.loc[mask, "snx_endpoint_yoy"] - sb["distributor_asp_inflation_2026"]["asp_tailwind_pts"]
        p.loc[~mask, "snx_endpoint_units_yoy"] = p.loc[~mask, "snx_endpoint_yoy"]

    # ---------------- regime label ----------------
    p["regime"] = "normal"
    for name, r in cfg["regimes"].items():
        lo, hi = (pd.Period(q, "Q") for q in r["quarters"])
        p.loc[(p.index >= lo) & (p.index <= hi), "regime"] = name

    # ---- Pipeline B context columns (never regressors): industry billings and US electronics-store sales YoY
    macro = MACRO_PROC / "macro_quarterly.csv"
    if macro.exists():
        m = pd.read_csv(macro)
        m.index = pd.PeriodIndex(m["quarter"], freq="Q")
        p["wsts_yoy"] = m["wsts_yoy_pct"].reindex(p.index)
        p["rseas_yoy"] = m["rseas_yoy_pct"].reindex(p.index)
    else:
        p["wsts_yoy"] = np.nan; p["rseas_yoy"] = np.nan

    p.index.name = "quarter"
    return p


def tier_summary(p: pd.DataFrame) -> pd.DataFrame:
    """Compact view used in the report and dashboard."""
    cols = ["sellout_proxy_yoy", "snx_endpoint_yoy", "ingm_ces_yoy", "dist_inv_days_avg",
            "logi_sales_yoy", "logi_ble_yoy", "logi_st_gap", "logi_inv_days",
            "gn_periph_yoy", "gn_enterprise_org", "gn_gaming_org", "gn_st_gap",
            "nordic_rev_yoy", "nordic_consumer_yoy", "nordic_inv_days", "nordic_dist_state", "regime"]
    return p[cols].round(1)
