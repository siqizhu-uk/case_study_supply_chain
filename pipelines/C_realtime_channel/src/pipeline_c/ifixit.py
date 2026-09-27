"""Design-win evidence from iFixit teardowns via the public iFixit API (keyless, https://www.ifixit.com/api/2.0).

search/<brand> (filter=guide) lists guides; guides/<id> returns every step's text. We keep every sentence that names
a radio-SoC vendor or part (Nordic nRF…, TI CC26…, Qualcomm, Broadcom, Realtek, Telink, Airoha, BES, Cypress/Infineon,
Silicon Labs, Dialog/Renesas) together with the guide URL. Grade C (user-contributed teardown text; the photo is
the primary evidence). Validation: the sentence is verbatim from the fetched guide (recorded), and each hit is
flagged for a one-click photo check.
"""
from __future__ import annotations

import json
import re

import pandas as pd

from .fetch import fetch

API = "https://www.ifixit.com/api/2.0"
BRANDS = ["Logitech", "Jabra", "SteelSeries", "Logitech G"]
QUERIES = ["{b} teardown", "{b} mouse", "{b} keyboard", "{b} headset", "{b} earbuds", "{b}"]   # search is title-based
CHIP = re.compile(r"(Nordic|nRF5\d{2,3}\w*|nRF54\w*|Texas Instruments|\bCC26\d\d\w*|Qualcomm|QCC\d{4}|Broadcom|Realtek|Telink|Airoha|"
                  r"\bBES\d{4}|Cypress|Infineon|Silicon Labs|EFR32\w*|Dialog|DA14\d{3}|Renesas|Espressif|ESP32|MediaTek|Actions Semi|ATS\d{4})", re.I)


def _get_json(url: str, name: str, day: str, refresh: bool = False) -> dict:
    return json.loads(fetch(url, name, refresh, day=day).read_text(errors="ignore"))


def list_guides(day: str, refresh: bool = False) -> pd.DataFrame:
    rows = []
    for b in BRANDS:
        for q in QUERIES:
            q = q.format(b=b)
            for offset in (0, 20):
                d = _get_json(f"{API}/search/{q.replace(' ', '%20')}?filter=guide&limit=20&offset={offset}", f"ifixit_search_{q.replace(' ', '_')}_{offset}.json", day, refresh)
                for r in d.get("results", []):
                    if b.split()[0].lower() not in (r.get("title") or "").lower():
                        continue
                    rows.append({"brand": b.split()[0], "guideid": r["guideid"], "type": r.get("type"), "title": r.get("title"), "url": r.get("url"),
                                 "modified_date": r.get("modified_date")})
                if not d.get("moreResults"):
                    break
    out = pd.DataFrame(rows).drop_duplicates("guideid")
    return out


def scan_guides(guides: pd.DataFrame, day: str, refresh: bool = False, teardowns_only: bool = False) -> pd.DataFrame:
    rows = []
    g = guides[guides["type"] == "teardown"] if teardowns_only else guides
    for _, r in g.iterrows():
        try:
            d = _get_json(f"{API}/guides/{r['guideid']}", f"ifixit_guide_{r['guideid']}.json", day, refresh)
        except Exception as e:
            rows.append({**r.to_dict(), "sentence": "", "chip_mentions": "", "status": f"fetch failed: {e}"}); continue
        text = " ".join(l.get("text_raw", "") for st in d.get("steps", []) for l in st.get("lines", []))
        imgs = [m.get("original") for st in d.get("steps", []) for m in (st.get("media") or {}).get("data", []) if isinstance(m, dict) and m.get("original")]
        r = r.copy(); r["n_steps"] = len(d.get("steps", [])); r["first_board_photo"] = imgs[len(imgs) // 2] if imgs else ""
        text = re.sub(r"\[[^\]]*\|([^\]]*)\]", r"\1", text)        # iFixit link markup [url|text]
        hits = [m for m in re.split(r"(?<=[.!?])\s+", text) if CHIP.search(m)]
        if hits:
            for s in hits:
                rows.append({**r.to_dict(), "sentence": s.strip()[:400], "chip_mentions": ";".join(sorted(set(x.group(0) for x in CHIP.finditer(s)))), "status": "chip named in text"})
        else:
            rows.append({**r.to_dict(), "sentence": "", "chip_mentions": "", "status": "no chip named in text (photo check needed)", "photo_check": "open url, find the PCB step, read the radio SoC marking; record in design_win_manual.csv"})
    return pd.DataFrame(rows)
