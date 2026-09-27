"""Offline tests for Pipeline C (channel snapshots, design-win evidence). No network."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipelines" / "C_realtime_channel" / "src"))

from pipeline_c.findchips import _stock, _price, ROW, consistency_checks  # noqa: E402
from pipeline_c.mouser import parse_response  # noqa: E402
from pipeline_c.paths import DATA_CONFIG, SNAPSHOTS  # noqa: E402


def test_stock_text_variants():
    assert _stock("9817")[0] == 9817
    assert _stock("&lt;b&gt;Local - &lt;/b&gt;70&lt;/br&gt;&lt;b&gt;Global - &lt;/b&gt;9887")[0] == 9887        # element14: global pool, not local+global
    assert _stock("&lt;b&gt;Stock DE&lt;/b&gt; - 0&lt;br/&gt;&lt;b&gt;Stock HK&lt;/b&gt; - 66000")[0] == 66000  # Rutronik: sum of regions
    assert _stock("")[0] is None


def test_price_tiers_and_row_regex():
    p1, p1k, cur = _price('[[1,&#34;USD&#34;,&#34;5.7600&#34;],[1000,&#34;USD&#34;,&#34;4.0300&#34;]]')
    assert (p1, p1k, cur) == (5.76, 4.03, "USD")
    html = '<tr data-id="100" data-distributor_name="Farnell" data-mfr="Nordic Semiconductor" data-instock="9817" data-stock="9817" data-mfrpartnumber="NRF52840-QIAA-R" data-price="[]" class="row">'
    assert ROW.findall(html)[0][0] == "Farnell" and ROW.findall(html)[0][4] == "NRF52840-QIAA-R"


def test_consistency_checks_flag_pool_disagreement():
    snap = pd.DataFrame([
        {"part": "nRF52840-QIAA-R", "listed_mpn": "NRF52840-QIAA-R", "distributor": "Farnell", "distributor_group": "Farnell/Newark/element14", "authorized": 1, "qty_in_stock": 9817},
        {"part": "nRF52840-QIAA-R", "listed_mpn": "NRF52840-QIAA-R", "distributor": "Newark", "distributor_group": "Farnell/Newark/element14", "authorized": 1, "qty_in_stock": 5000},
        {"part": "nRF52840-QIAA-R", "listed_mpn": "NRF52840-QIAA-R", "distributor": "Broker X", "distributor_group": "Broker X", "authorized": 0, "qty_in_stock": 1}])
    c = {x["check"]: x for x in consistency_checks(snap)}
    assert c["farnell_group_agreement"]["ok"] is False and c["exact_mpn_present"]["ok"] is True and c["authorized_rows_parsed"]["ok"] is True


def test_mouser_parser_on_canned_response():
    payload = {"SearchResults": {"Parts": [{"ManufacturerPartNumber": "nRF52840-QIAA-R", "Manufacturer": "Nordic Semiconductor", "Availability": "12,345 In Stock",
                                             "AvailabilityInStock": "12345", "LeadTime": "16 Weeks", "PriceBreaks": [{"Quantity": 1, "Price": "$7.25"}, {"Quantity": 2000, "Price": "$4.07"}]}]}}
    d = parse_response(payload, "nRF52840-QIAA-R", "2026-09-23")
    assert d.loc[0, "qty_in_stock"] == 12345 and d.loc[0, "price_1"] == 7.25 and d.loc[0, "price_1000"] == 4.07 and d.loc[0, "lead_time"] == "16 Weeks"


def test_snapshot_series_and_config_integrity():
    s = pd.read_csv(SNAPSHOTS, dtype={"snapshot_date": str})
    assert {"snapshot_date", "part", "distributor_group", "authorized", "listed_mpn", "qty_in_stock", "source"} <= set(s.columns)
    assert s["snapshot_date"].str.match(r"\d{4}-\d{2}-\d{2}").all() and s["authorized"].isin([0, 1]).all()
    cfg = pd.read_csv(DATA_CONFIG, dtype=str).fillna("")
    assert cfg["key"].is_unique and (cfg["retrieval_method"] != "").all() and (cfg["validation_method"] != "").all()
    assert set(cfg["validated"]) <= {"yes", "no", "partial", "manual", "not_fetched", "not_configured", "rejected", "see_pipeline_a", ""}

