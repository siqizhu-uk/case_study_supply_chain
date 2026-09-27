"""Registry of the six companies and the filing URLs used for verification."""
from __future__ import annotations

COMPANIES = {
    "nordic":   {"name": "Nordic Semiconductor ASA", "ticker": "NOD.OL", "exchange": "Oslo Børs", "currency": "USD",
                 "fy_end_month": 12, "sec_cik": None, "ir": "https://www.nordicsemi.com/Investor-Relations",
                 "raw_csv": "nordic_quarterly.csv", "role": "component (tier 3)"},
    "logitech": {"name": "Logitech International S.A.", "ticker": "LOGI / LOGN", "exchange": "Nasdaq / SIX", "currency": "USD",
                 "fy_end_month": 3, "sec_cik": 1032975, "ir": "https://ir.logitech.com",
                 "raw_csv": "logitech_quarterly.csv", "role": "OEM (tier 2)"},
    "gn":       {"name": "GN Store Nord A/S", "ticker": "GN.CO", "exchange": "Nasdaq Copenhagen", "currency": "DKK",
                 "fy_end_month": 12, "sec_cik": None, "ir": "https://www.gn.com/investor",
                 "raw_csv": "gn_quarterly.csv", "role": "OEM (tier 2)"},
    "ingram":   {"name": "Ingram Micro Holding Corp", "ticker": "INGM", "exchange": "NYSE", "currency": "USD",
                 "fy_end_month": 12, "sec_cik": 1897762, "ir": "https://ingrammicro.gcs-web.com",
                 "raw_csv": "ingram_quarterly.csv", "role": "distributor (tier 1)"},
    "tdsynnex": {"name": "TD SYNNEX Corp", "ticker": "SNX", "exchange": "NYSE", "currency": "USD",
                 "fy_end_month": 11, "sec_cik": 1177394, "ir": "https://ir.tdsynnex.com",
                 "raw_csv": "tdsynnex_quarterly.csv", "role": "distributor (tier 1)"},
    "amazon":   {"name": "Amazon.com Inc", "ticker": "AMZN", "exchange": "Nasdaq", "currency": "USD",
                 "fy_end_month": 12, "sec_cik": 1018724, "ir": "https://ir.aboutamazon.com",
                 "raw_csv": None, "role": "retail sell-out (tier 0); context only, peripherals not disclosed"},
    # step 5 lag bounds (retail / reseller inventory cover, all categories): read by inventory_detail.py
    "bestbuy":  {"name": "Best Buy Co Inc", "ticker": "BBY", "exchange": "NYSE", "currency": "USD", "fy_end_month": 1,
                 "sec_cik": 764478, "raw_csv": None, "in_sec_quarterly": False, "role": "electronics retailer: inventory cover proxy for 'other retail'"},
    "walmart":  {"name": "Walmart Inc", "ticker": "WMT", "exchange": "NYSE", "currency": "USD", "fy_end_month": 1,
                 "sec_cik": 104169, "raw_csv": None, "in_sec_quarterly": False, "role": "general retailer: inventory cover proxy (context)"},
    "target":   {"name": "Target Corp", "ticker": "TGT", "exchange": "NYSE", "currency": "USD", "fy_end_month": 1,
                 "sec_cik": 27419, "raw_csv": None, "in_sec_quarterly": False, "role": "general retailer: inventory cover proxy (context)"},
    "cdw":      {"name": "CDW Corp", "ticker": "CDW", "exchange": "Nasdaq", "currency": "USD", "fy_end_month": 12,
                 "sec_cik": 1402057, "raw_csv": None, "in_sec_quarterly": False, "role": "IT reseller: inventory cover proxy for distributor -> reseller"},
    # step 3 (inventory mechanism) context filers: read by inventory_detail.py, not part of the headline XBRL table
    "arrow":    {"name": "Arrow Electronics Inc", "ticker": "ARW", "exchange": "NYSE", "currency": "USD", "fy_end_month": 12,
                 "sec_cik": 7536, "raw_csv": None, "in_sec_quarterly": False, "role": "Nordic franchised distributor (component channel)"},
    "avnet":    {"name": "Avnet Inc", "ticker": "AVT", "exchange": "Nasdaq", "currency": "USD", "fy_end_month": 6,
                 "sec_cik": 8858, "raw_csv": None, "in_sec_quarterly": False, "role": "Nordic franchised distributor (component channel)"},
    "microchip": {"name": "Microchip Technology Inc", "ticker": "MCHP", "exchange": "Nasdaq", "currency": "USD", "fy_end_month": 3,
                  "sec_cik": 827054, "raw_csv": None, "in_sec_quarterly": False, "role": "MCU peer: discloses distributor days of inventory"},
    "silicon_labs": {"name": "Silicon Laboratories Inc", "ticker": "SLAB", "exchange": "Nasdaq", "currency": "USD", "fy_end_month": 12,
                     "sec_cik": 1038074, "raw_csv": None, "in_sec_quarterly": False, "role": "BLE peer: checked, no channel-days disclosure (rejected)"},
}

# XBRL tags tried in order for each concept (first present wins).
XBRL_TAGS = {
    "revenue":      ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "cogs":         ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "inventory":    ["InventoryNet"],
}

# All filing / document URLs live in config/data_config.csv (one row per source, with a `validated` column that
# pipelines/A_company_financials/scripts/validate.py fills in). Add a new quarter by adding a row there; nothing in the code changes.
import csv as _csv
from .paths import DATA_CONFIG  # noqa: F401 (re-exported)

DOWNLOADABLE = {"ir_pdf", "ir_pdf_fallback", "sec_8k_exhibit", "sec_10k", "sec_s1"}


def load_data_config() -> list[dict]:
    with open(DATA_CONFIG, newline="") as f:
        return list(_csv.DictReader(f))


def filings_from_config() -> dict[str, dict[str, str]]:
    """{company: {key: url}} for every downloadable document (NewsWeb attachments are handled by newsweb.py)."""
    out: dict[str, dict[str, str]] = {}
    for r in load_data_config():
        if r["source_type"] in DOWNLOADABLE:
            out.setdefault(r["company"], {}).setdefault(r["key"], r["url"])   # first wins: primary before fallback
    return out


FILINGS = filings_from_config()

# Which raw-CSV columns to look for in which filing (quarter row -> its own report; annual figures -> AR).
VERIFY_COLUMNS = {
    "nordic":   ["revenue_usdm", "consumer_usdm", "ind_health_usdm", "inventory_usdm", "short_range_usdm", "long_range_usdm"],
    "gn":       ["group_rev_dkkm", "hearing_rev_dkkm", "enterprise_rev_dkkm", "gaming_div_rev_dkkm", "cont_ops_rev_dkkm", "inventory_dkkm"],
    "logitech": ["net_sales_usdm", "gaming_usdm", "keyboards_usdm", "pointing_usdm", "video_collab_usdm", "webcams_usdm",
                 "tablet_usdm", "headsets_usdm", "inventory_usdm"],   # regions come from 10-Q segment notes (not in the 8-K)
    "ingram":   ["net_sales_usdm", "gross_profit_usdm", "inventory_usdm"],
    "tdsynnex": ["revenue_usdm", "gross_billings_usdm", "gross_profit_usdm", "inventory_usdm"],
}
