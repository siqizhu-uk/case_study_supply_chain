"""Step 5f — which route proxy is published by the origin of the live nowcast (decision G27): the availability table.

For each source, every period that overlaps the target quarter q: its period end, its release date (the stored filing date,
or period end + the configured typical lag when the period is not in the repo yet or has no stored date), whether that is on
or before origin(q), and the months it shares with q. Amazon, Ingram and CDW report calendar quarters ~30 days after quarter
end - after Nordic's report - so the same rule that admits TD Synnex and Best Buy excludes them.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import route_nowcast_data as rnd

CALENDAR_SOURCES = {"logitech": "Logitech sell-through YoY (the target)", "amazon": "Amazon revenue YoY (XBRL)",
                    "ingram": "Ingram Micro sales YoY", "cdw": "CDW revenue YoY (XBRL)"}


def _row(cfg: dict, source: str, series: str, label: str, period_end, release, basis: str, q: pd.Period, value: float,
         used_in: str) -> dict:
    at = rnd.origin(q, cfg)
    rel = pd.Timestamp(release)
    return {"source": source, "series": series, "period": label, "period_end": pd.Timestamp(period_end).date().isoformat(),
            "months_in_target": rnd.overlap_months(pd.Timestamp(period_end), q, 1 if source == "rseas" else 3),
            "release_date": rel.date().isoformat(), "release_basis": basis, "origin": at.date().isoformat(),
            "available_at_origin": bool(rel <= at), "value": value, "grade": cfg["route_nowcast"]["release_lag"][source]["grade"],
            "used_in": used_in}


def _lookup(table: pd.DataFrame, label) -> tuple[float, object]:
    """(value, stored release date) of a label, NaN / None when the repo has no row for it."""
    t = table[table["label"] == label]
    return (float(t["value"].iloc[0]), t["release_date"].iloc[0]) if len(t) else (np.nan, None)


def calendar_rows(cfg: dict, q: pd.Period, series: dict) -> list[dict]:
    """Calendar-quarter reporters: the quarter q itself, released at quarter end + typical lag."""
    rows = []
    for src, name in CALENDAR_SOURCES.items():
        lag = cfg["route_nowcast"]["release_lag"][src]
        end = q.end_time.normalize()
        used = "target (known only after the origin)" if src == "logitech" else "excluded by the availability rule"
        rows.append(_row(cfg, src, name, str(q), end, end + pd.Timedelta(days=int(lag["days"])), f"rule: +{lag['days']} d ({lag['basis']})",
                         q, float(series.get(src, pd.Series(dtype=float)).get(q, np.nan)), used))
    return rows


def tdsynnex_rows(cfg: dict, q: pd.Period, S: dict) -> list[dict]:
    m, lag = int(cfg["route_nowcast"]["tdsynnex_period_end_month"]), cfg["route_nowcast"]["release_lag"]["tdsynnex"]
    end = rnd.month_end(q, m)
    rows = []
    for name in ("snx_sales", "snx_endpoint"):
        v, _ = _lookup(S[name], q)
        used = f"N2 ({name})" if np.isfinite(v) else "released, but this split is not in the release (no value)"
        rows.append(_row(cfg, "tdsynnex", cfg["route_nowcast"]["proxies"][name]["note"], f"{q} (FQ ending {end:%b %Y})", end,
                         end + pd.Timedelta(days=int(lag["days"])), f"rule: FQ end +{lag['days']} d ({lag['basis']})", q, v, used))
    return rows


def bestbuy_rows(cfg: dict, q: pd.Period, S: dict) -> list[dict]:
    """Label q-1 (ends in month 1 of q, filed in month 2) and label q (ends a month after q; filing date by the median stored lag)."""
    t = S["bestbuy_computing"]
    typical = (pd.to_datetime(t["release_date"]) - pd.to_datetime(t["period_end"])).median()
    rows = []
    for lab in (q - 1, q):
        v, filed = _lookup(t, lab)
        stored = t[t["label"] == lab]
        end = pd.Timestamp(stored["period_end"].iloc[0]) if len(stored) else (lab + 1).asfreq("M", "start").end_time.normalize()
        rel, basis = (filed, "8-K filing date (stored)") if filed is not None else (end + typical, f"median stored filing lag {typical.days} d")
        rows.append(_row(cfg, "bestbuy", "Best Buy Computing & Mobile comps", f"{lab} (fiscal, ends {end:%d %b %Y})", end, rel, basis, q, v,
                         "N2c (1 month of the target)" if rel <= rnd.origin(q, cfg) else "not yet filed"))
    return rows


def rseas_rows(cfg: dict, q: pd.Period, S: dict) -> list[dict]:
    lag = cfg["route_nowcast"]["release_lag"]["rseas"]
    rows = []
    for mo in pd.period_range(q.asfreq("M", "start"), q.asfreq("M", "end"), freq="M"):
        end = mo.end_time.normalize()
        v, _ = _lookup(S["rseas"], mo)
        rel = end + pd.Timedelta(days=int(lag["days"]))
        rows.append(_row(cfg, "rseas", "US electronics & appliance stores (USD m, monthly)", str(mo), end, rel,
                         f"rule: month end +{lag['days']} d ({lag['basis']})", q, v,
                         "N2c (partial-quarter YoY)" if rel <= rnd.origin(q, cfg) else "after the origin"))
    return rows


def guide_row(cfg: dict, q: pd.Period, S: dict) -> dict:
    lag = cfg["route_nowcast"]["release_lag"]["logitech_guide"]
    v, rel = _lookup(S["logitech_guide"], q)
    rel = rel if rel is not None else (q - 1).end_time.normalize() + pd.Timedelta(days=int(lag["days"]))
    return _row(cfg, "logitech_guide", "Logitech's own guide for q (guided sales YoY + last gap)", str(q), q.end_time.normalize(), rel,
                f"rule: +{lag['days']} d after q-1 ({lag['basis']})", q, v, "N1 / GRg (comparison only: user rule)")


def availability(p: pd.DataFrame, cfg: dict, S: dict, q: pd.Period) -> pd.DataFrame:
    """The availability table for target quarter q (live: route_nowcast.live_quarter)."""
    from route_demand import load_route_proxies
    px = load_route_proxies(p)
    series = {"logitech": pd.Series(S["logitech"]["value"].values, index=pd.PeriodIndex(S["logitech"]["label"], freq="Q")),
              "amazon": px["amazon_revenue_yoy"], "cdw": px["cdw_revenue_yoy"], "ingram": p["ingm_sales_yoy"]}
    rows = calendar_rows(cfg, q, series) + tdsynnex_rows(cfg, q, S) + bestbuy_rows(cfg, q, S) + rseas_rows(cfg, q, S) + [guide_row(cfg, q, S)]
    return pd.DataFrame(rows)
