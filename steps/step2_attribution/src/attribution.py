"""Step 2 — share of Nordic revenue reached through Logitech / GN.

Five legs, kept separate and reconciled, never averaged:
  A  bottom-up Monte Carlo: units × radios per unit × Nordic socket share × Nordic ASP (priors in config/model.yaml;
     socket share is replaced by the FCC internal-photo census once enough grants have been read — Pipeline C file)
  B  IFRS 8.34: Nordic's AR discloses that its only >= 10% customers are two distributors (30%, 12% in 2025), so no OEM is
     >= 10% -> hard cap if Logitech is invoiced direct, not binding if its ODMs / Suzhou plant buy via ODM or distributor;
     the route is unknown (Logitech builds ~35% in-house), so results are reported per route scenario
  C  category view: PC peripherals as a share of Nordic's Consumer end-market (prior)
  D  proprietary-2.4GHz floor: Nordic's 'Proprietary' technology line was almost purely PC-peripheral receivers; its
     peak-year size and its collapse one quarter after Logitech turned negative in 2022 bound peripherals exposure from below
  E  natural experiment: peak-to-trough of Nordic consumer vs Logitech BLE categories in the 2022-24 destock — a swing
     Logitech alone cannot explain shows it is a minority
Grade: A inputs (filings), D estimate; B once the FCC census replaces the socket-share prior.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

STEP = Path(__file__).resolve().parents[1]
ROOT = STEP.parents[1]
CONFIG, OUT = STEP / "config", STEP / "outputs"
FCC = ROOT / "pipelines" / "C_realtime_channel" / "data" / "raw" / "fcc_logitech_grants_2023_2026.csv"
NORDIC = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_quarterly.csv"
MIN_READ_FOR_CENSUS = 10   # readable peripheral grants (mice / keyboards / receivers) before the census replaces the prior
LOGITECH = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "logitech_quarterly.csv"
PERIPHERAL_CODES = ("MR", "YR", "CU", "RR")          # mouse, keyboard/combo, USB receiver, receiver — the sockets Nordic competes for
AUDIO_CODES = ("A0", "AR", "SR")                     # headsets, audio dongles, speakers — Bluetooth-audio SoCs (Airoha / Realtek / Qualcomm)


def _draw(rng, d: dict, n: int) -> np.ndarray:
    return rng.triangular(d["low"], d["mid"], d["high"], n)


def _q(x) -> dict:
    return {"p10": float(np.percentile(x, 10)), "p50": float(np.percentile(x, 50)), "p90": float(np.percentile(x, 90))}


def _wilson(k: int, n: int, z: float = 1.645) -> dict:
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"low": max(0.0, centre - half), "mid": p, "high": min(1.0, centre + half)}


def socket_share_evidence() -> dict:
    """FCC census state, by product family: readable grants (a SoC marking read from the internal photos) and the
    observed Nordic share with a Wilson 90% interval, separately for peripherals (mice, keyboards, receivers) and audio
    (headsets, dongles, speakers). Below MIN_READ_FOR_CENSUS readable peripheral grants the prior in model.yaml stays."""
    if not FCC.exists():
        return {"grants": 0, "read": 0, "nordic": 0, "used": False, "note": "FCC grant list not found"}
    d = pd.read_csv(FCC, dtype=str).fillna("")
    d["family"] = d["fcc_id"].str[3:5].map(lambda c: "peripheral" if c in PERIPHERAL_CODES else ("audio" if c in AUDIO_CODES else "other"))
    read = d[(d["soc_marking_observed"].str.strip() != "")]
    readable = read[~read["chip_vendor"].str.contains("unreadable", case=False)]
    out = {"grants": int(len(d)), "read": int(len(read)), "readable": int(len(readable)), "unreadable": int(len(read) - len(readable)),
           "nordic": int(readable["chip_vendor"].str.contains("Nordic", case=False).sum()),
           "vendors": readable["chip_vendor"].str.strip().value_counts().to_dict() if len(readable) else {}, "by_family": {}}
    for fam in ("peripheral", "audio"):
        r = readable[readable["family"] == fam]
        n, k = len(r), int(r["chip_vendor"].str.contains("Nordic", case=False).sum())
        out["by_family"][fam] = {"readable": n, "nordic": k, "vendors": r["chip_vendor"].value_counts().to_dict(), "share": _wilson(k, n) if n else None}
    per = out["by_family"]["peripheral"]
    out["used"] = per["readable"] >= MIN_READ_FOR_CENSUS
    out["share"] = per["share"] if per["share"] else None
    return out


def _logitech_ttm() -> dict:
    """TTM Logitech sales by radio family (USD m) from the Pipeline A CSV: peripherals = pointing + keyboards + gaming; headsets."""
    l = pd.read_csv(LOGITECH).dropna(subset=["net_sales_usdm"]).tail(4)
    return {"quarters": l["quarter"].tolist(), "peripherals": float((l["pointing_usdm"] + l["keyboards_usdm"] + l["gaming_usdm"]).sum()),
            "headsets": float(l["headsets_usdm"].sum())}


def leg_d_proprietary(cfg: dict) -> dict:
    """Nordic 'Proprietary' technology-line revenue (USD m) — peak TTM, its share of Nordic then, and the collapse."""
    n = pd.read_csv(NORDIC, dtype={"quarter": str}).set_index("quarter")
    s = n["proprietary_usdm"].dropna()
    if s.empty:
        return {"available": False}
    ttm = s.rolling(4).sum().dropna()
    rev_ttm = n.loc[ttm.index, "revenue_usdm"].rolling(4).sum() if False else n["revenue_usdm"].rolling(4).sum().reindex(ttm.index)
    peak_q = ttm.idxmax()
    trough_q = ttm.loc[peak_q:].idxmin()
    return {"available": True, "line": "proprietary_usdm (Nordic technology split; discontinued in the 2025 taxonomy)",
            "peak_ttm_quarter": peak_q, "peak_ttm_usdm": float(ttm[peak_q]), "peak_share_of_nordic_pct": float(ttm[peak_q] / rev_ttm[peak_q] * 100),
            "trough_ttm_quarter": trough_q, "trough_ttm_usdm": float(ttm[trough_q]), "peak_to_trough_pct": float((ttm[trough_q] / ttm[peak_q] - 1) * 100),
            "first_quarter_below_half_peak": next((q for q in s.loc[peak_q:].index if s[q] < 0.5 * s.loc[:peak_q].max()), None),
            "reading": "floor for PC-peripheral exposure before the BLE/Bolt migration folded it into Short-range; a lower bound, not Logitech alone"}


def leg_e_natural_experiment(p: pd.DataFrame | None, content_pct: float | None = None) -> dict:
    """Peak-to-trough (TTM) in the 2022-24 destock: Nordic consumer vs Logitech BLE-core categories, both USD."""
    if p is None or "nordic_consumer" not in p or "logi_radio_core" not in p:
        return {"available": False}
    ttm = p[["nordic_consumer", "logi_radio_core"]].rolling(4).sum()          # TTM removes Logitech's holiday seasonality
    w = ttm.loc[pd.Period("2021Q4", "Q"):pd.Period("2024Q2", "Q")]
    nc, lc = w["nordic_consumer"].dropna(), w["logi_radio_core"].dropna()
    if nc.empty or lc.empty:
        return {"available": False}
    n_peak, n_tr = nc.idxmax(), nc.loc[nc.idxmax():].idxmin()
    l_peak, l_tr = lc.idxmax(), lc.loc[lc.idxmax():].idxmin()
    dn, dl = float(nc[n_peak] - nc[n_tr]), float(lc[l_peak] - lc[l_tr])
    return {"available": True, "nordic_consumer_peak": str(n_peak), "nordic_consumer_trough": str(n_tr), "nordic_consumer_drop_usdm": dn,
            "nordic_consumer_drop_pct": float((nc[n_tr] / nc[n_peak] - 1) * 100),
            "logitech_ble_core_peak": str(l_peak), "logitech_ble_core_trough": str(l_tr), "logitech_drop_usdm": dl,
            "logitech_drop_pct": float((lc[l_tr] / lc[l_peak] - 1) * 100),
            "nordic_content_needed_if_logitech_alone_pct_of_logitech_sales": float(dn / dl * 100) if dl else None,
            "nordic_content_on_leg_a_priors_pct_of_logitech_sales": content_pct,
            "reading": (f"on the Leg-A priors Nordic content is ≈{content_pct:.1f}% of Logitech's sell-in value, so Logitech alone explains ≈{(content_pct / 100 * dl / dn * 100) if dn else 0:.0f}% of Nordic's drop"
                        if content_pct else "Logitech alone explains only a small part of Nordic's drop") + ": the OEM tier is a timing/direction signal, the level is broad-market"}


def attribution(cfg: dict, n: int = 20000, seed: int = 7, panel: pd.DataFrame | None = None) -> dict:
    a = cfg["attribution"]
    rng = np.random.default_rng(seed)
    L, G = a["logitech"], a["gn"]
    tot, cons = a["nordic_total_rev_usdm_ttm"], a["nordic_consumer_rev_usdm_ttm"]
    cap = a["nordic_no_customer_over_pct"] / 100 * tot

    # ---- Leg A ---------------------------------------------------------------------------------
    census = socket_share_evidence()
    ttm = _logitech_ttm()
    if census["used"]:
        # census in force: peripherals get the observed Nordic share; headsets get the audio-family observation
        # (Bluetooth-audio SoCs — Airoha / Realtek in the FCC photos, Qualcomm in the Jabra teardown), i.e. ~0
        socket = census["share"]
        aud = census["by_family"]["audio"]["share"] or {"low": 0.0, "mid": 0.0, "high": 0.3}
        headset_share = {"low": 0.0, "mid": aud["mid"], "high": min(aud["high"], 0.3)}
        sales_periph, sales_head = ttm["peripherals"], ttm["headsets"]
    else:
        socket, headset_share = L["nordic_socket_share"], L["nordic_socket_share"]
        sales_periph, sales_head = L["ble_relevant_sales_usdm_ttm"], 0.0
    content_pct = L["wireless_share"]["mid"] * L["radios_per_wireless_unit"]["mid"] * socket["mid"] * L["nordic_asp_usd"]["mid"] / L["avg_sell_in_asp_usd"]["mid"] * 100
    asp = _draw(rng, L["avg_sell_in_asp_usd"], n)
    wireless, rpu, nasp = _draw(rng, L["wireless_share"], n), _draw(rng, L["radios_per_wireless_unit"], n), _draw(rng, L["nordic_asp_usd"], n)
    radios_p = sales_periph / asp * wireless * rpu
    radios_h = sales_head / asp * wireless * rpu
    radios = radios_p + radios_h
    logi = radios_p * _draw(rng, socket, n) * nasp + (radios_h * rng.triangular(headset_share["low"], headset_share["mid"], headset_share["high"], n) * nasp if sales_head else 0.0)
    ss = _draw(rng, G["steelseries_units_m"], n) * _draw(rng, G["steelseries_wireless_share"], n) * _draw(rng, G["nordic_socket_share_gaming"], n) * _draw(rng, G["nordic_asp_usd"], n)
    ent = _draw(rng, G["enterprise_units_m"], n) * _draw(rng, G["enterprise_nordic_share"], n) * _draw(rng, G["nordic_asp_usd"], n)
    gn = ss + ent

    # ---- Leg B by invoicing route --------------------------------------------------------------
    direct_share = _draw(rng, a.get("route_direct_share", {"low": 0.3, "mid": 0.5, "high": 0.7}), n)
    routes = {"direct": np.minimum(logi, cap),                                        # whole volume invoiced by Nordic to Logitech
              "indirect": logi,                                                         # via ODMs / distributors: cap sits on them, not binding for Logitech
              "mixed": np.minimum(logi * direct_share, cap) + logi * (1 - direct_share)}  # direct share prior anchored on the 35% in-house build
    pc = _draw(rng, a["pc_peripherals_share_of_nordic_consumer"], n)

    out = {"headline_route": "mixed", "logitech_usdm": _q(routes["direct"]), "logitech_uncapped_usdm": _q(logi), "gn_usdm": _q(gn),
           "by_route": {r: {"logitech_usdm": _q(v), "combined_pct_of_nordic_total": _q((v + gn) / tot * 100),
                            "combined_pct_of_nordic_consumer": _q((v + gn) / cons * 100)} for r, v in routes.items()},
           "combined_usdm": _q(routes["mixed"] + gn),
           "combined_pct_of_nordic_total": _q((routes["mixed"] + gn) / tot * 100),
           "combined_pct_of_nordic_consumer": _q((routes["mixed"] + gn) / cons * 100),
           "pc_peripherals_category_pct_of_consumer": _q(pc * 100), "pc_peripherals_category_pct_of_total": _q(pc * cons / tot * 100),
           "share_of_draws_hitting_10pct_cap": float((logi > cap).mean()), "implied_logitech_radio_units_m": _q(radios),
           "socket_share_used": {"source": "FCC census (peripheral grants)" if census["used"] else "prior (config/model.yaml)", **{k: float(v) for k, v in socket.items()}},
           "headset_share_used": {k: float(v) for k, v in headset_share.items()}, "logitech_ttm_sales_usdm": ttm,
           "fcc_census": census, "leg_d_proprietary_floor": leg_d_proprietary(cfg), "leg_e_natural_experiment": leg_e_natural_experiment(panel, content_pct),
           "grade": "B" if census["used"] else "D",
           "use_in_model": "timing / direction signal for Nordic's consumer line, not a level input"}
    return out


def _quote_in(company: str, key: str, quote: str, constraint: str = "") -> str:
    """Quote check against a hand-saved excerpt (config/evidence/<constraint>.txt), the cached filing (Pipeline A),
    a cached document (Pipeline B) or, for a URL source, a fetched copy cached under steps/step2_attribution/cache/."""
    import re
    sys_path = ROOT / "pipelines" / "A_company_financials" / "src"
    import sys
    if str(sys_path) not in sys.path:
        sys.path.insert(0, str(sys_path))
    from pipeline_a.filings import extract_text
    from core import verify_ledger as ledger
    lk = f"{constraint}|{key}"
    ev = CONFIG / "evidence" / f"{constraint}.txt"
    if ev.exists():
        t = re.sub(r"\s+", " ", ev.read_text(errors="ignore")).lower()
        return "found in saved excerpt" if re.sub(r"\s+", " ", quote).lower() in t else "NOT in saved excerpt"
    if key.startswith("http"):                                   # web source: fetch once, cache under steps/step2_attribution/cache/
        import hashlib, urllib.request
        cache = STEP / "cache"; cache.mkdir(exist_ok=True)
        f = cache / (hashlib.md5(key.encode()).hexdigest()[:12] + ".html")
        if not f.exists() and ledger.recall("step2_quote", lk):      # no network in a model run when the result is on record
            return ledger.recall("step2_quote", lk)[0]
        if not f.exists():
            try:
                req = urllib.request.Request(key, headers={"User-Agent": "Mozilla/5.0 (supply-chain-case-study; siqizhu00@gmail.com)"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    f.write_bytes(r.read())
            except Exception as e:
                return f"fetch failed ({type(e).__name__})"
        t = re.sub(r"<[^>]+>", " ", f.read_text(errors="ignore"))
        return ledger.record("step2_quote", lk, "found" if re.sub(r"\s+", " ", quote).lower() in re.sub(r"\s+", " ", t).lower() else "NOT found")
    cands = [ROOT / "pipelines" / "A_company_financials" / "data" / "cache" / "filings" / company / f"{key}{ext}" for ext in (".pdf", ".htm")]
    cands += [f for f in (ROOT / "pipelines" / "B_macro_industry" / "data" / "cache").glob(f"{key}.*") if f.suffix in (".pdf", ".htm", ".html")]
    for f in cands:
        if f.exists():
            try:
                t = re.sub(r"\s+", " ", extract_text(f)).lower()
            except Exception:
                return "unreadable"
            return ledger.record("step2_quote", lk, "found" if re.sub(r"\s+", " ", quote).lower() in t else "NOT found")
    r = ledger.recall("step2_quote", lk)
    return r[0] if r else "no document cached"


def write_step2(attr: dict) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    cons = pd.read_csv(CONFIG / "constraints.csv", dtype=str).fillna("")
    cons["verified"] = [(_quote_in(r["company"], r["source_key"], r["quote"], r["constraint"]) if r["quote"] else "prior") for _, r in cons.iterrows()]
    from core import verify_ledger
    verify_ledger.save()
    cons.to_csv(OUT / "constraints_used.csv", index=False)
    r = attr["by_route"]
    md = ["# Step 2 — attribution: Logitech + GN as a share of Nordic\n",
          f"**Grade {attr['grade']}** — inputs A (filings), estimate {'B (FCC census in force)' if attr['grade'] == 'B' else 'D (socket share is a prior; FCC census pending)'}. Use: {attr['use_in_model']}.\n",
          "## Result by invoicing route (p10 / p50 / p90, % of Nordic total revenue)\n",
          "| route | Logitech $m | Logitech + GN, % of Nordic total | % of Nordic Consumer |", "|---|---|---|---|"]
    for k, v in r.items():
        md.append(f"| {k} | {v['logitech_usdm']['p10']:.0f} / {v['logitech_usdm']['p50']:.0f} / {v['logitech_usdm']['p90']:.0f} | "
                  f"{v['combined_pct_of_nordic_total']['p10']:.1f} / {v['combined_pct_of_nordic_total']['p50']:.1f} / {v['combined_pct_of_nordic_total']['p90']:.1f} | "
                  f"{v['combined_pct_of_nordic_consumer']['p10']:.0f} / {v['combined_pct_of_nordic_consumer']['p50']:.0f} / {v['combined_pct_of_nordic_consumer']['p90']:.0f} |")
    md += ["", f"Share of Leg-A draws above the IFRS 8.34 ceiling: {attr['share_of_draws_hitting_10pct_cap']:.0%} — the bottom-up and the ceiling disagree at the median, which is why the route matters and why the output is conditional.",
           f"Socket share used: {attr['socket_share_used']['source']} — low {attr['socket_share_used']['low']:.2f} / mid {attr['socket_share_used']['mid']:.2f} / high {attr['socket_share_used']['high']:.2f}. "
           f"FCC census: {attr['fcc_census']['read']} of {attr['fcc_census']['grants']} grants read, {attr['fcc_census']['readable']} legible ({attr['fcc_census']['unreadable']} unreadable); "
           f"peripherals {attr['fcc_census']['by_family']['peripheral']['nordic']}/{attr['fcc_census']['by_family']['peripheral']['readable']} Nordic "
           f"({attr['fcc_census']['by_family']['peripheral']['vendors']}); audio {attr['fcc_census']['by_family']['audio']['nordic']}/{attr['fcc_census']['by_family']['audio']['readable']} Nordic "
           f"({attr['fcc_census']['by_family']['audio']['vendors']}). Headset share used: {attr['headset_share_used']}. Logitech TTM sales: peripherals ${attr['logitech_ttm_sales_usdm']['peripherals']:.0f}m, headsets ${attr['logitech_ttm_sales_usdm']['headsets']:.0f}m. "
           f"The prior is replaced once {MIN_READ_FOR_CENSUS} peripheral grants are legible. Evidence photos: pipelines/C_realtime_channel/data/manual/fcc_photos/.", ""]
    if attr["fcc_census"].get("used"):
        md += ["**Reading the census honestly.** It is a count of *designs* (one FCC grant = one product), not of units. The two non-Nordic "
               "peripherals are Telink parts in entry-level SKUs, which typically ship in larger unit volumes than the MX / G-series designs that "
               "carry Nordic — so the unit-weighted Nordic share is likely below the 85% design share (the Wilson low end, ~63%, is the safer working number). "
               "With the census share, Leg A exceeds the IFRS 8.34 ceiling in almost every draw: either Logitech's radios are invoiced to ODMs / distributors "
               "(consistent with two distributors taking 42% of Nordic's revenue), or the units / ASP priors are high. Both are stated; neither is assumed.", ""]
    d = attr["leg_d_proprietary_floor"]
    if d.get("available"):
        md += ["## Leg D — proprietary-2.4GHz floor\n",
               f"Nordic's Proprietary line peaked at ${d['peak_ttm_usdm']:.0f}m TTM ({d['peak_ttm_quarter']}), {d['peak_share_of_nordic_pct']:.0f}% of Nordic revenue then; it fell {d['peak_to_trough_pct']:.0f}% to ${d['trough_ttm_usdm']:.0f}m by {d['trough_ttm_quarter']}, first quarter below half its peak: {d['first_quarter_below_half_peak']}. {d['reading']}.", ""]
    e = attr["leg_e_natural_experiment"]
    if e.get("available"):
        md += ["## Leg E — natural experiment (2022-24 destock)\n",
               f"Nordic consumer {e['nordic_consumer_peak']} → {e['nordic_consumer_trough']}: {e['nordic_consumer_drop_pct']:.0f}% (${e['nordic_consumer_drop_usdm']:.0f}m). Logitech BLE-core categories {e['logitech_ble_core_peak']} → {e['logitech_ble_core_trough']}: {e['logitech_drop_pct']:.0f}% (${e['logitech_drop_usdm']:.0f}m). "
               f"For Logitech alone to explain Nordic's drop, Nordic content would have to be {e['nordic_content_needed_if_logitech_alone_pct_of_logitech_sales']:.0f}% of Logitech's sell-in value; {e['reading']}.", ""]
    if isinstance(attr.get("path"), pd.DataFrame):
        from attribution_path import path_summary_md
        md += path_summary_md(attr["path"])
    md += ["## Constraints and evidence used\n", cons[["constraint", "company", "value", "source_key", "verified", "role"]].to_markdown(index=False), "",
           "## Upgrade path\n", "1. FCC internal-photo census (Pipeline C `fcc_logitech_grants_2023_2026.csv`, fill `soc_marking_observed` / `chip_vendor`) — turns the socket share from prior into observation, grade D → B.",
           "2. Bluetooth SIG product listings per Logitech product (qualified design shows the radio).", "3. Nordic press releases / case studies naming Logitech designs — cite only if found.",
           "4. Import records or expert calls would settle the route — paid, outside the brief."]
    (OUT / "step2_report.md").write_text("\n".join(md))
    return OUT / "step2_report.md"
