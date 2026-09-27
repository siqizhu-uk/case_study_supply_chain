"""Parse the revenue guide (and NXP's channel-inventory weeks) from each release; every value keeps its sentence."""
from __future__ import annotations

import re

import pandas as pd

UNIT = {"billion": 1000.0, "million": 1.0}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_guide(text: str, patterns: list[dict], plausible=None) -> dict | None:
    """First match, over patterns in order and matches in document order, whose mid passes `plausible(mid)`."""
    for p in patterns:
        for m in re.finditer(p["re"], text, re.I):
            out = _one(m, p)
            if out is None:
                continue
            if plausible is None or out.get("pattern_kind") == "pct_seq" or plausible(out["guide_mid_usdm"]):
                return out
    return None


def _one(m: re.Match, p: dict) -> dict | None:
    """One regex match -> guide dict in USD m (or a sequential-% guide converted later in build())."""
    g, k = m.groups(), p["kind"]
    words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    if k in ("pct_pm", "pct_flat_down", "pct_flat_up"):   # 'flat +/- 5 percent', 'flat to down 4%': sequential % around the reported quarter
        x = float(words.get(g[0].lower(), g[0])) if not g[0].replace(".", "").isdigit() else float(g[0])
        lo, hi = {"pct_pm": (-x, x), "pct_flat_down": (-x, 0.0), "pct_flat_up": (0.0, x)}[k]
        return {"guide_pct_low": lo, "guide_pct_high": hi, "pattern_kind": "pct_seq", "quote": m.group(0)[:400]}
    if k == "pct_center_pm":                            # 'decrease by three percent ... plus or minus five percent'
        num = lambda v: float(words.get(v.lower(), v)) if not v.replace(".", "").isdigit() else float(v)   # noqa: E731
        c = num(g[1]) * (-1 if g[0].lower() in ("decrease", "decline") else 1)
        pm = num(g[2])
        return {"guide_pct_low": c - pm, "guide_pct_high": c + pm, "pattern_kind": "pct_seq", "quote": m.group(0)[:400]}
    if k == "pm_fixed_unit":                            # table with the unit in its header: 'Net sales $ 190.0 +/- $10.0'
        u = UNIT[p["unit"]]
        mid, half = _num(g[0]) * u, _num(g[1]) * u
        return {"guide_low_usdm": mid - half, "guide_mid_usdm": mid, "guide_high_usdm": mid + half, "pattern_kind": k, "quote": m.group(0)[:400]}
    if k == "pct_point":                                # 'revenues to decline sequentially by approximately 20%': low = high
        x = float(g[1]) * (-1 if g[0].lower() in ("decline", "decrease") else 1)
        return {"guide_pct_low": x, "guide_pct_high": x, "pattern_kind": "pct_seq", "quote": m.group(0)[:400]}
    if k == "pct_flat":                                 # 'approximately flat'
        return {"guide_pct_low": 0.0, "guide_pct_high": 0.0, "pattern_kind": "pct_seq", "quote": m.group(0)[:400]}
    if k == "pct_signed_range":                         # 'minus 2% to plus 3%'
        a, b = (float(v) * (-1 if s_.lower() == "minus" else 1) for s_, v in ((g[0], g[1]), (g[2], g[3])))
        return {"guide_pct_low": min(a, b), "guide_pct_high": max(a, b), "pattern_kind": "pct_seq", "quote": m.group(0)[:400]}
    if k in ("pct_seq", "pct_seq_down"):
        a, b = (float(words.get(v.lower(), v)) if not v.replace(".", "").isdigit() else float(v) for v in g[:2])
        lo, hi = (-max(a, b), -min(a, b)) if k == "pct_seq_down" else (min(a, b), max(a, b))
        return {"guide_pct_low": lo, "guide_pct_high": hi, "pattern_kind": "pct_seq", "quote": m.group(0)[:400]}
    if k == "range":
        low, high = _num(g[0]) * UNIT[g[1].lower()], _num(g[2]) * UNIT[g[3].lower()]
        mid = (low + high) / 2
    elif k == "range_one_unit":
        unit = UNIT[(p.get("unit") or g[2]).lower()]              # 'unit' in config for tables that print bare numbers ('$210 - $220')
        low, high = _num(g[0]) * unit, _num(g[1]) * unit
        mid = (low + high) / 2
    elif k == "plusminus":
        mid, half = _num(g[0]) * UNIT[g[1].lower()], _num(g[2]) * UNIT[g[3].lower()]
        low, high = mid - half, mid + half
    elif k == "plusminus_mid":                  # a single midpoint ('$255 million at the midpoint ...'): low = mid = high
        mid = _num(g[0]) * UNIT[g[1].lower()]
        low = high = mid
    elif k == "lmh":
        low, mid, high = (_num(x) for x in g[:3])
    else:
        return None
    return {"guide_low_usdm": low, "guide_mid_usdm": mid, "guide_high_usdm": high, "pattern_kind": k, "quote": m.group(0)[:400]}


def parse_backward(text: str, spec: dict | None) -> dict | None:
    if not spec:
        return None
    m = re.search(spec["re"], text, re.I)
    if not m:
        return None
    return {"guide_date": str(pd.Timestamp(m.group(1)).date()), "backward_mid_usdm": _num(m.group(2)) * UNIT[m.group(3).lower()],
            "backward_quote": m.group(0)[:300]}


def parse_channel_weeks(text: str, pat: str | None) -> dict | None:
    """NXP: 'Channel Inventory (months) 1.6 1.6 2.4' early, '(weeks) 11 11 9' later -> weeks, unit kept."""
    if not pat:
        return None
    m = re.search(pat, text)
    if not m:
        return None
    unit = m.group(1)
    k = 52 / 12 if unit == "months" else 1.0
    cur, prev, yago = (float(x) * k for x in m.groups()[1:4])
    return {"channel_weeks": cur, "channel_weeks_prev_col": prev, "channel_weeks_yago_col": yago,
            "channel_unit_reported": unit, "channel_quote": m.group(0)}
