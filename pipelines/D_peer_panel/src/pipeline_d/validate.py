"""Every check on the peer panel, one row each; the validation report and data_config statuses are built from these."""
from __future__ import annotations

import pandas as pd

from .releases import PROC


def checks(o: dict) -> pd.DataFrame:
    g, ch, p = o["guides"], o["channel"], o["panel"]
    rows = []
    for c, gg in g.groupby("company"):
        ok = gg[gg["parsed"]]
        rows.append({"company": c, "check": "guide parsed from the release (sentence stored)", "n": len(gg), "passed_n": len(ok),
                     "passed": len(ok) >= 0.8 * len(gg), "detail": "unparsed releases: " + ", ".join(gg.loc[~gg["parsed"], "release_date"]) if (~gg["parsed"]).any() else ""})
        order = (ok["guide_low_usdm"] <= ok["guide_mid_usdm"]) & (ok["guide_mid_usdm"] <= ok["guide_high_usdm"])
        mid = ((ok["guide_low_usdm"] + ok["guide_high_usdm"]) / 2 - ok["guide_mid_usdm"]).abs() <= 0.005 * ok["guide_mid_usdm"]
        rows.append({"company": c, "check": "low <= mid <= high and mid = (low+high)/2", "n": len(ok), "passed_n": int((order & mid).sum()),
                     "passed": bool((order & mid).all()), "detail": ""})
        fixed = gg[gg["flags"].fillna("") != ""]
        if len(fixed):
            rows.append({"company": c, "check": "unit typo in the filing detected and corrected", "n": len(fixed), "passed_n": len(fixed), "passed": True,
                         "detail": "; ".join(f"{r.release_date}: {r.flags}" for r in fixed.itertuples())})
    # Microchip chain: the 'midpoint of our guidance provided on <date>' in release q == our parse of the release on <date>
    m = g[(g["company"] == "microchip")].sort_values("release_date")
    if "backward_mid_usdm" in m:
        fwd = m.set_index("release_date")["guide_mid_usdm"]
        bw = m.dropna(subset=["backward_mid_usdm"])
        res = [(r.release_date, r.guide_date, r.backward_mid_usdm, fwd.get(r.guide_date)) for r in bw.itertuples()]
        good = [abs(b - f) <= 0.005 * f for _, _, b, f in res if pd.notna(f)]
        rows.append({"company": "microchip", "check": "chain: 'midpoint of our guidance provided on <date>' == guide parsed from the <date> release",
                     "n": len(good), "passed_n": int(sum(good)), "passed": bool(good) and all(good),
                     "detail": "; ".join(f"{d}: stated {b:.1f} vs parsed {f:.1f}" for d, _, b, f in res if pd.notna(f) and abs(b - f) > 0.005 * f)})
    if len(ch):
        c2 = ch.sort_values("release_date").reset_index(drop=True)
        same_unit = c2["channel_unit_reported"] == c2["channel_unit_reported"].shift(1)
        d = (c2["channel_weeks_prev_col"] - c2["channel_weeks"].shift(1)).abs()[same_unit].dropna()
        sw = c2[~same_unit & c2.index.to_series().gt(0)]
        rows.append({"company": "nxp", "check": "channel weeks chain within one definition: prior-quarter column == previous release (tolerance 0.5 wk)",
                     "n": len(d), "passed_n": int((d <= 0.5).sum()), "passed": bool((d <= 0.5).all()),
                     "detail": "; ".join(f"definition break at {r.quarter}: restated prior {r.channel_weeks_prev_col:.1f} wk" for r in sw.itertuples())})
    from .releases import load_cfg, earnings_releases
    cfg = load_cfg()
    for ov in (o.get("overrides") or []):
        spec = cfg["peers"][ov["company"]]
        texts = [r["text"] for r in earnings_releases(ov["company"], spec["cik"], cfg["first_release_date"])]
        found = any(ov["quote"] in t for t in texts)
        rows.append({"company": ov["company"], "check": f"actual override {ov['quarter']}: quote found in the company's release",
                     "n": 1, "passed_n": int(found), "passed": found, "detail": ov["reason"]})
    ok_out = {(v["company"], v["quarter"]) for v in (o.get("verified_outliers") or [])}
    for c, pp in p.groupby("company"):
        bad = pp[pp["manual_check"] & ~pp["excluded"] & ~pd.Series([(c, q) in ok_out for q in pp["quarter"]], index=pp.index)]
        rows.append({"company": c, "check": "|beat| <= 15% unless excluded (structural break) or confirmed by a manual read (verified_outliers)", "n": len(pp),
                     "passed_n": len(pp) - len(bad), "passed": bad.empty, "detail": "; ".join(f"{r.quarter} {r.beat_pct:+.1f}%" for r in bad.itertuples())})
    out = pd.DataFrame(rows)
    out.to_csv(PROC / "peer_validation.csv", index=False)
    return out


def check_characteristics() -> pd.DataFrame:
    """Every quote fragment in config/peer_characteristics.csv must be found in the company's latest cached 10-K."""
    import json
    from .releases import PIPE, CACHE, _cached, html_text
    ch = pd.read_csv(PIPE / "config" / "peer_characteristics.csv", dtype=str).fillna("")
    rows = []
    for _, r in ch.iterrows():
        frags = [f for q in (r["distribution_quote"], r["consumer_quote"]) for f in q.split("|") if f.strip()]
        if not frags:
            rows.append({"company": r["company"], "check": "10-K characteristics quote", "n": 0, "passed_n": 0, "passed": True, "detail": r["distribution_basis"]})
            continue
        cik = int(r["cik"])
        sub = json.loads(_cached(CACHE / r["company"] / "submissions.json", f"https://data.sec.gov/submissions/CIK{cik:010d}.json"))["filings"]["recent"]
        a, doc = [(a, d) for f, a, d in zip(sub["form"], sub["accessionNumber"], sub["primaryDocument"]) if f == "10-K"][0]
        t = html_text(_cached(CACHE / r["company"] / a / doc, f"https://www.sec.gov/Archives/edgar/data/{cik}/{a.replace('-', '')}/{doc}"))
        t = " ".join(t.replace("​", " ").split())
        found = [f for f in frags if " ".join(f.split()) in t]
        rows.append({"company": r["company"], "check": "10-K characteristics quote found in the latest 10-K", "n": len(frags), "passed_n": len(found),
                     "passed": len(found) == len(frags), "detail": "; ".join(f for f in frags if f not in found)})
    return pd.DataFrame(rows)


def check_history(h: dict, cfg: dict) -> pd.DataFrame:
    """2008-09 window: every actual has two sources (narrative = income-statement row, or XBRL); release vs XBRL agree where both
    exist (disagreements listed); |beat| <= 15% unless verified; quarters without a numeric guide listed with their reason."""
    hc, g, p = cfg["history"], h["releases"], h["panel"]
    tol = hc["actual_tolerance"]
    need = set(zip(p["company"], p["quarter"])) | set(zip(p["company"], p["quarter"].map(lambda q: str(pd.Period(q, "Q") - 1))))
    used = g[[k in need for k in zip(g["company"], g["reported_quarter"])]]      # actual(q) and the base q-1 of %-guides
    rows = []
    for c, gg in used.groupby("company"):
        pre = gg[gg["actual_xbrl_usdm"].isna()]
        two = pre["actual_table_usdm"].notna()
        rows.append({"company": c, "check": "history: pre-XBRL actual = narrative figure AND an income-statement revenue row (0.5%)", "n": len(pre),
                     "passed_n": int(two.sum()), "passed": bool(two.all()), "detail": ", ".join(pre.loc[~two, "reported_quarter"])})
        both = gg.dropna(subset=["actual_xbrl_usdm", "actual_release_usdm"])
        dis = both[(both["actual_release_usdm"] / both["actual_xbrl_usdm"] - 1).abs() > tol]
        rows.append({"company": c, "check": "history: release figure vs XBRL first reported (XBRL used; disagreements = narrative regex hit a comparative)",
                     "n": len(both), "passed_n": len(both) - len(dis), "passed": len(dis) <= 1,
                     "detail": "; ".join(f"{r.reported_quarter}: '{r.actual_quote}' vs XBRL {r.actual_xbrl_usdm:.1f}" for r in dis.itertuples())})
    ok = {(v["company"], v["quarter"]) for v in hc.get("verified_outliers", [])}
    big = p[(p["beat_pct"].abs() > cfg["sanity_abs_beat_pct"]) & ~p["excluded"]]
    bad = [f"{r.company} {r.quarter} {r.beat_pct:+.1f}%" for r in big.itertuples() if (r.company, r.quarter) not in ok]
    rows.append({"company": "all", "check": "history: |beat| <= 15% unless verified", "n": len(big), "passed_n": len(big) - len(bad),
                 "passed": not bad, "detail": "; ".join(bad)})
    ng = "; ".join(f"{x['company']} {x['release']}" for x in hc.get("no_numeric_guide", []))
    rows.append({"company": "all", "check": "history: releases without a numeric guide (read, listed, not imputed)", "n": len(hc.get("no_numeric_guide", [])),
                 "passed_n": len(hc.get("no_numeric_guide", [])), "passed": True, "detail": ng})
    return pd.DataFrame(rows)
