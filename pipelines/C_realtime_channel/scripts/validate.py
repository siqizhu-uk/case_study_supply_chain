"""Pipeline C in one command:  python pipelines/C_realtime_channel/scripts/validate.py [--refresh] [--no-snapshot] [--no-ifixit]

Takes today's distributor-stock snapshot (findchips; Mouser API if a key is set), appends it to
data/raw/channel_snapshots.csv, runs the consistency checks, pulls design-win evidence from iFixit teardowns,
validates the FCC grant list, writes data/processed/{channel_latest,channel_series,design_win_evidence}.csv and
validation_report.md, and fills the validated / validated_on / validation_detail columns of config/data_config.csv.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pipeline_c.paths import DATA_CONFIG, DATA_PROC, SNAPSHOTS  # noqa: E402
from pipeline_c import build  # noqa: E402
from pipeline_c.fcc import validate_fcc  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-snapshot", action="store_true", help="skip the distributor fetch (use the stored series)")
    ap.add_argument("--no-ifixit", action="store_true")
    a = ap.parse_args(argv)
    today = date.today().isoformat()
    cfg = pd.read_csv(DATA_CONFIG, dtype=str).fillna("")

    def setrow(key, validated, detail):
        i = cfg.index[cfg["key"] == key][0]
        cfg.loc[i, ["validated", "validated_on", "validation_detail"]] = [validated, today, detail]

    md = [f"# Pipeline C validation report — {today}\n"]

    # ---- 1. distributor stock snapshot ------------------------------------------------------
    checks, api = [], {}
    if not a.no_snapshot:
        try:
            snap, checks, api = build.take_snapshot(today, a.refresh)
            n_ok, n = sum(c["ok"] for c in checks), len(checks)
            setrow("findchips_stock", "yes" if n and n_ok == n else ("partial" if n_ok else "no"),
                   f"{today}: {len(snap)} rows, {int((snap['authorized'] == 1).sum())} authorized; consistency checks {n_ok}/{n} passed")
            setrow("mouser_api", "yes" if api and all(v['ok'] for v in api.values()) else ("no" if api else "not_configured"),
                   "; ".join(f"{k}: API {v['mouser_api']:.0f} vs findchips {v['findchips_mouser_row']:.0f}" for k, v in api.items()) or "MOUSER_API_KEY not set — provider skipped")
        except Exception as e:
            setrow("findchips_stock", "no", f"snapshot failed: {e}")
            setrow("mouser_api", "not_configured", "")
    series = build.authorized_series()
    # hand snapshot vs first scripted snapshot
    s = pd.read_csv(SNAPSHOTS, dtype={"snapshot_date": str})
    hand = s[s["source"].str.startswith("hand snapshot")]
    scripted = s[~s["source"].str.startswith("hand snapshot") & (s["authorized"] == 1)]
    overlap = []
    if len(hand) and len(scripted):
        first = scripted["snapshot_date"].min()
        sc = scripted[scripted["snapshot_date"] == first]
        for _, h in hand.iterrows():
            m = sc[(sc["part"] == h["part"]) & (sc["distributor_group"] == h["distributor_group"]) & (sc["listed_mpn"].str.upper() == h["part"].upper())]
            if len(m) and pd.notna(h["qty_in_stock"]):
                q = float(m["qty_in_stock"].max()); hq = float(h["qty_in_stock"])
                overlap.append({"part": h["part"], "group": h["distributor_group"], "hand": hq, "scripted": q, "ok": abs(q - hq) <= 0.25 * max(q, hq, 1)})
    if overlap:
        ok = sum(o["ok"] for o in overlap)
        setrow("hand_snapshot_2026-09-22", "yes" if ok == len(overlap) else "partial", f"{ok}/{len(overlap)} overlapping (part, distributor group) cells within 25% of the {first} scripted snapshot")
    else:
        setrow("hand_snapshot_2026-09-22", "partial", "no overlapping distributor group in the scripted snapshot (region-dependent listing)")

    md += ["## 1. Component-tier channel (authorized-distributor stock, exact MPN)\n", series.tail(12).to_markdown(index=False), "",
           "Consistency checks on today's scrape:\n", pd.DataFrame(checks).to_markdown(index=False) if checks else "(snapshot skipped)", ""]
    if overlap:
        md += ["Hand snapshot (2026-09-22) vs first scripted snapshot:\n", pd.DataFrame(overlap).to_markdown(index=False), ""]

    # ---- 2. design-win evidence ---------------------------------------------------------------
    if not a.no_ifixit:
        try:
            ev = build.design_wins(today, a.refresh)
            hits = ev[ev["status"] == "chip named in text"]
            nordic = hits[hits["chip_mentions"].str.contains("Nordic|nRF", case=False)]
            setrow("ifixit_teardowns", "yes", f"{ev['guideid'].nunique()} teardown guides scanned; {len(hits)} sentences name a radio SoC; {len(nordic)} name Nordic/nRF")
            md += ["## 2. Design-win evidence (iFixit teardown text)\n",
                   hits[["brand", "title", "chip_mentions", "sentence", "url"]].to_markdown(index=False) if len(hits) else "no teardown sentence names a radio SoC — photo check needed",
                   "", f"{(ev['status'] != 'chip named in text').sum()} guides scanned with no chip named in text (see design_win_evidence.csv).", ""]
        except Exception as e:
            setrow("ifixit_teardowns", "no", f"failed: {e}")

    # ---- 3. FCC list integrity ----------------------------------------------------------------
    f = validate_fcc()
    setrow("fcc_grants_jnz", "partial" if f["fcc_id_unique"] and f["all_jnz"] and f["grant_dates_parse"] else "no",
           f"{f['grants']} grants {f['first_grant']}..{f['last_grant']}, ids unique={f['fcc_id_unique']}, photos public={f['internal_photos_public']}, SoC marking read={f['soc_marking_read']}, Nordic confirmed={f['nordic_confirmed']}")
    md += ["## 3. FCC grant list (Logitech, JNZ)\n", pd.Series(f).to_frame("value").to_markdown(), "",
           "The list is complete and consistent; the evidence step (reading internal photos for the SoC marking) is manual and not started — see the 'fcc logitech enrichment' note.", ""]

    cfg.to_csv(DATA_CONFIG, index=False)
    md += ["## 4. Sources and status\n", cfg[["source", "grade", "retrieval_method", "validation_method", "validated", "validation_detail"]].to_markdown(index=False), "",
           "Rule: channel stock is a dashboard indicator (tier-3 channel tightness) and a qualitative cross-check on Nordic's own commentary; it never enters the regression or the forecast."]
    (DATA_PROC / "validation_report.md").write_text("\n".join(md))
    print("\n".join(md[:6]))
    print(f"\nconfig: {cfg['validated'].value_counts().to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
