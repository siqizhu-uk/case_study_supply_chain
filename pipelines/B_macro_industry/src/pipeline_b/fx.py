"""Exchange rates for the post-guide FX update (step 7, fx_update.py).

Source: the ECB's euro foreign exchange reference rates (daily, official, keyless SDMX API). FRED's fredgraph endpoint,
the first choice, timed out from this machine (2026-09-27); FRED republishes central-bank rates, so the ECB is the
primary publisher, not a substitute of lower grade. Quarterly averages of the value of one unit of each currency in USD
(Logitech, Nordic report in USD) and in DKK (GN reports in DKK) are written to data/raw/fx_quarterly_ecb.csv, which is
committed so a fresh clone runs without the network.

Checks: DKK per EUR inside the ERM II band (7.46038 +/- 2.25%), every completed quarter has >= 55 fixing days, USD per
EUR inside 0.8-1.6 (plausibility), the last fixing date is reported.
"""
from __future__ import annotations

import pandas as pd

from .fetch import fetch
from .paths import DATA_RAW

CURRENCIES = ("USD", "DKK", "GBP", "CNY", "JPY", "AUD")
ECB_URL = ("https://data-api.ecb.europa.eu/service/data/EXR/D." + "+".join(CURRENCIES)
           + ".EUR.SP00.A?format=csvdata&startPeriod=2019-01-01")
OUT = DATA_RAW / "fx_quarterly_ecb.csv"
ERM2_CENTRAL, ERM2_BAND = 7.46038, 0.0225


def ecb_daily(refresh: bool = False) -> pd.DataFrame:
    """Units of each currency per EUR, one row per fixing day."""
    f = fetch(ECB_URL, "ecb_exr_daily.csv", refresh, timeout=120)
    d = pd.read_csv(f)[["CURRENCY", "TIME_PERIOD", "OBS_VALUE"]]
    w = d.pivot(index="TIME_PERIOD", columns="CURRENCY", values="OBS_VALUE")
    w.index = pd.to_datetime(w.index)
    w["EUR"] = 1.0
    return w.sort_index()


def quarterly(w: pd.DataFrame) -> pd.DataFrame:
    """Quarterly average value of one unit of each currency in USD and in DKK, and the number of fixing days."""
    usd = w.rdiv(w["USD"], axis=0)                          # USD per unit of c = (USD per EUR) / (c per EUR)
    dkk = w.rdiv(w["DKK"], axis=0)
    g = lambda df: df.resample("QE").mean()                 # noqa: E731
    q = pd.concat([g(usd).add_prefix("usd_per_"), g(dkk).add_prefix("dkk_per_"),
                   w["USD"].resample("QE").count().rename("n_days")], axis=1)
    q.index = q.index.to_period("Q")
    q = q.drop(columns=["usd_per_USD", "dkk_per_DKK"])
    return q.rename_axis("quarter").reset_index()


def checks(w: pd.DataFrame, q: pd.DataFrame) -> dict:
    lo, hi = ERM2_CENTRAL * (1 - ERM2_BAND), ERM2_CENTRAL * (1 + ERM2_BAND)
    complete = q[q["quarter"] < pd.Period(w.index.max(), "Q")]
    return {"dkk_in_erm2_band": bool(w["DKK"].between(lo, hi).all()),
            "usd_per_eur_plausible": bool(w["USD"].between(0.8, 1.6).all()),
            "complete_quarters_min_days": int(complete["n_days"].min()),
            "complete_quarters_ok": bool((complete["n_days"] >= 55).all()),
            "last_fixing": str(w.index.max().date()),
            "last_quarter_days": int(q["n_days"].iloc[-1])}


def build_fx(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    w = ecb_daily(refresh)
    q = quarterly(w)
    c = checks(w, q)
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    q.round(6).to_csv(OUT, index=False)
    return q, c
