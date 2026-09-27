"""GN guidance history FY2021-FY2026 (collected 2026-09-26 from gn.com announcements and report PDFs; announcement list in
config/gn_announcement_index.json). Run: python pipelines/A_company_financials/scripts/build_gn_guidance.py
Build gn_guidance_history.csv + gn_guidance_excerpts.md and quote-check every row against the saved text copy."""
import csv, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/cache/verbal"
OUT_CSV = ROOT / "data/raw/gn_guidance_history.csv"
OUT_MD = ROOT / "data/manual/gn_guidance_excerpts.md"
RETRIEVED = "2026-09-26"

ANN = {o["id"]: o for o in json.load(open(ROOT / "config" / "gn_announcement_index.json"))}
B = "https://www.gn.com/-/media/Files/Financial-Download-Center/"
PDF = {
    "Q1_21": B + "2021/Q1/GNSN---Interim-Report-Q1-2021.pdf",
    "Q2_21": B + "2021/Q2/GNSN---Interim-Report-Q2-2021.pdf",
    "Q3_21": B + "2021/Q3/GNSN---Interim-Report-Q3-2021.pdf",
    "Q1_22": B + "2022/Q1/GN-Interim-Report-Q1-2022.pdf",
    "Q3_22": B + "2022/Q3/GN-Interim-Report-Q3-2022.pdf",
    "AR22": B + "2023/Q1/GN-Annual-Report-2022.pdf",
    "AR23": B + "2024/Q1/GN-Annual-Report-2023.pdf",
    "Q1_24": B + "2024/Q2/Interim-Report-Q1-2024.pdf",
    "Q2_24": B + "2024/Q3/GN-Interim-Report-Q2-2024.pdf",
}


def name(url):
    return re.sub(r"[^A-Za-z0-9]+", "_", url)[-120:]


def src(key):
    """(url, local text file) for an announcement id or a PDF key."""
    if key in ANN:
        return ANN[key]["url"], CACHE / (ANN[key]["file"] + ".txt")
    u = PDF[key]
    return u, CACHE / (name(u) + ".pdf.txt")


# (date, fy, metric, scope, low, high, action, source, quote, note); None = open end / not applicable
O, E, OT = "organic_growth_pct", "ebita_margin_pct", "other"
R = [
    # ---------------- FY2021 (pre-SteelSeries; guidance per division; reported EBITA) ----------------
    ("2021-02-11", 2021, O, "hearing", 25, None, "initial", "2173690", "For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.", "'more than 25%': lower bound only (high blank). Annual report 2020 announcement"),
    ("2021-02-11", 2021, E, "hearing", 16, None, "initial", "2173690", "For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.", "'more than 16%'; reported EBITA margin (no adjusted concept yet)"),
    ("2021-02-11", 2021, O, "audio", 20, None, "initial", "2173690", "For full year 2021, GN Audio expects organic revenue growth to be more than 20% and an EBITA margin of more than 21%.", "'more than 20%'; GN Audio = Enterprise + Consumer (pre-SteelSeries)"),
    ("2021-02-11", 2021, E, "audio", 21, None, "initial", "2173690", "For full year 2021, GN Audio expects organic revenue growth to be more than 20% and an EBITA margin of more than 21%.", "'more than 21%'"),
    ("2021-02-11", 2021, OT, "group", 50, None, "initial", "2173690", "GN Store Nord expects a growth in EPS of more than 50% for full year 2021.", "EPS growth %, 'more than 50%'; only group-level metric guided in 2021"),
    ("2021-04-14", 2021, O, "audio", 25, None, "raised", "2209636", "GN Audio upgrades the financial guidance communicated on February 11, 2021 from an organic revenue growth of more than 20% to more than 25% and confirms an EBITA margin of more than 21%.", "ad-hoc announcement with pre-released Q1 figures (Q1 Audio organic +82%)"),
    ("2021-04-14", 2021, E, "audio", 21, None, "reiterated", "2209636", "GN Audio upgrades the financial guidance communicated on February 11, 2021 from an organic revenue growth of more than 20% to more than 25% and confirms an EBITA margin of more than 21%.", ""),
    ("2021-04-14", 2021, O, "hearing", 25, None, "reiterated", "2209636", "For full year 2021, GN Hearing confirms an expected organic revenue growth of more than 25% and an EBITA margin of more than 16%.", ""),
    ("2021-04-14", 2021, E, "hearing", 16, None, "reiterated", "2209636", "For full year 2021, GN Hearing confirms an expected organic revenue growth of more than 25% and an EBITA margin of more than 16%.", ""),
    ("2021-04-14", 2021, OT, "group", 60, None, "raised", "2209636", "GN Store Nord upgrades the financial guidance communicated on February 11, 2021 on growth in EPS from more than 50% to more than 60%.", "EPS growth %"),
    ("2021-05-06", 2021, O, "hearing", 25, None, "reiterated", "Q1_21", "For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.", "Q1 2021 interim report"),
    ("2021-05-06", 2021, E, "hearing", 16, None, "reiterated", "Q1_21", "For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.", "Q1 2021 interim report"),
    ("2021-05-06", 2021, O, "audio", 25, None, "reiterated", "Q1_21", "For full year 2021, GN Audio expects organic revenue growth to be more than 25% and an EBITA margin of more than 21%.", "Q1 2021 interim report"),
    ("2021-05-06", 2021, E, "audio", 21, None, "reiterated", "Q1_21", "For full year 2021, GN Audio expects organic revenue growth to be more than 25% and an EBITA margin of more than 21%.", "Q1 2021 interim report"),
    ("2021-05-06", 2021, OT, "group", 60, None, "reiterated", "Q1_21", "GN Store Nord expects a growth in EPS of more than 60% for full year 2021.", "EPS growth %"),
    ("2021-08-19", 2021, O, "hearing", 25, None, "reiterated", "Q2_21", "For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.", "Q2 2021 interim report ('The financial guidance for 2021 is confirmed')"),
    ("2021-08-19", 2021, E, "hearing", 16, None, "reiterated", "Q2_21", "For full year 2021, GN Hearing expects an organic revenue growth of more than 25% and an EBITA margin of more than 16%.", "Q2 2021 interim report"),
    ("2021-08-19", 2021, O, "audio", 25, None, "reiterated", "Q2_21", "For full year 2021, GN Audio expects organic revenue growth to be more than 25% and an EBITA margin of more than 21%.", "Q2 2021 interim report"),
    ("2021-08-19", 2021, E, "audio", 21, None, "reiterated", "Q2_21", "For full year 2021, GN Audio expects organic revenue growth to be more than 25% and an EBITA margin of more than 21%.", "Q2 2021 interim report"),
    ("2021-08-19", 2021, OT, "group", 60, None, "reiterated", "Q2_21", "GN Store Nord expects a growth in EPS of more than 60% for full year 2021.", "EPS growth %"),
    ("2021-10-05", 2021, O, "hearing", 16, 16, "lowered", "2308394", "The GN Hearing organic revenue growth guidance for 2021 is revised from more than 25% to around 16%", "'around 16%' -> low=high=16; profit warning: product-launch delays"),
    ("2021-10-05", 2021, E, "hearing", 12, None, "lowered", "2308394", "the GN Hearing EBITA margin guidance for 2021 is revised from more than 16% to more than 12%", "'more than 12%'"),
    ("2021-10-05", 2021, OT, "group", 50, None, "lowered", "2308394", "GN Store Nord revises the financial guidance on growth in EPS from more than 60% to more than 50%", "EPS growth %"),
    ("2021-10-05", 2021, O, "audio", 25, None, "reiterated", "2308394", "The 2021 financial guidance for GN Audio is unchanged and confirmed.", "numbers carried from the 14 Apr 2021 guide"),
    ("2021-10-05", 2021, E, "audio", 21, None, "reiterated", "2308394", "The 2021 financial guidance for GN Audio is unchanged and confirmed.", "numbers carried from the 14 Apr 2021 guide"),
    ("2021-10-06", 2021, OT, "group", None, None, "basis_change", "2309255", "Transaction-related costs including integration costs, insurance costs, fees, consultant costs, etc. are expected to be around DKK 150 million in 2021.", "SteelSeries acquisition announced; 'The financial guidance for 2021 excluding transaction related costs is confirmed' -> from here all 2021 guides exclude ~DKK 150m transaction costs; SteelSeries itself not in 2021 guidance (closed 12 Jan 2022)"),
    ("2021-10-29", 2021, O, "audio", 22, 25, "lowered", "2323342", "GN Audio today revises its organic revenue growth guidance for 2021 from more than 25% to 22-25%", "component shortages / supplier de-commitments"),
    ("2021-10-29", 2021, E, "audio", 21, None, "reiterated", "2323342", "The EBITA margin guidance of more than 21% excluding transaction related costs is confirmed", "now excl. SteelSeries transaction costs"),
    ("2021-10-29", 2021, O, "hearing", 16, 16, "reiterated", "Q3_21", "For full year 2021, GN Hearing expects an organic revenue growth of around 16% and an EBITA margin of more than 12%.", "'around 16%'; Q3 2021 interim report"),
    ("2021-10-29", 2021, E, "hearing", 12, None, "reiterated", "Q3_21", "For full year 2021, GN Hearing expects an organic revenue growth of around 16% and an EBITA margin of more than 12%.", "Q3 2021 interim report"),
    ("2021-10-29", 2021, OT, "group", 40, None, "lowered", "2323342", "GN Store Nord now expects a growth in EPS of more than 40% for 2021 excluding transaction related costs", "EPS growth %, excl. transaction costs"),
    ("2022-02-10", 2021, O, "hearing", 16, 16, "actual", "2382398", "GN Hearing’s organic revenue growth in 2021 was 16%, with an EBITA margin of 12.1%.", "Annual report 2021"),
    ("2022-02-10", 2021, E, "hearing", 12.1, 12.1, "actual", "2382398", "GN Hearing’s organic revenue growth in 2021 was 16%, with an EBITA margin of 12.1%.", "reported EBITA margin, same basis as guide"),
    ("2022-02-10", 2021, O, "audio", 22, 22, "actual", "2382398", "2021 organic revenue growth was 22%, with an EBITA-margin of 21.2% excluding transaction related costs of DKK 45 million.", ""),
    ("2022-02-10", 2021, E, "audio", 21.2, 21.2, "actual", "2382398", "2021 organic revenue growth was 22%, with an EBITA-margin of 21.2% excluding transaction related costs of DKK 45 million.", "excl. DKK 45m transaction costs = guide basis after 6 Oct 2021"),
    ("2022-02-10", 2021, OT, "group", 43.0, 43.0, "actual", "2382398", "EBITA of DKK 2.7 billion and EPS was DKK 13.90 (excluding transaction related costs)", "EPS growth % DERIVED: 13.90 / 9.72 - 1 = +43.0% (2020 EPS DKK 9.72 from 11 Feb 2021 announcement: 'EPS was DKK 9.72')"),
    # ---------------- FY2022 (SteelSeries in from 12 Jan 2022; adjusted = excl. non-recurring items) ----------------
    ("2022-02-10", 2022, O, "hearing_core", 5, 10, "initial", "2382398", "In 2022, GN Hearing expects to grow faster than the projected market growth of 4-6% volume growth and -1% to -2% ASP decline, with an organic revenue growth between 5-10%.", "guidance table labels it 'Core business organic' (excl. Emerging Business / Lively)"),
    ("2022-02-10", 2022, E, "hearing_core", 14, 14, "initial", "2382398", "For the core hearing aid business, the EBITA margin is expected to be ~14% for 2022 excluding non-recurring items.", "'~14%' -> low=high=14; adjusted (excl. non-recurring ~DKK -150m); Emerging Business guided separately in DKK (~ -190m), not recorded"),
    ("2022-02-10", 2022, O, "audio", 5, None, "initial", "2382398", "GN Audio’s organic revenue growth for 2022 is expected to be >5%, while the organic revenue growth for SteelSeries is expected to be >10%", "'>5%'; GN Audio organic EXCLUDES SteelSeries (SteelSeries reported as M&A growth)"),
    ("2022-02-10", 2022, O, "steelseries", 10, None, "initial", "2382398", "GN Audio’s organic revenue growth for 2022 is expected to be >5%, while the organic revenue growth for SteelSeries is expected to be >10%", "'>10%'; SteelSeries pro-forma organic, shown as M&A growth in Audio"),
    ("2022-02-10", 2022, E, "audio", 20, 20, "initial", "2382398", "For GN Audio, the EBITA margin is expected to be ~20% for 2022 excluding non-recurring items.", "'~20%'; adjusted; margin INCLUDES SteelSeries (organic growth does not)"),
    ("2022-02-10", 2022, OT, "group", 10, None, "initial", "2382398", "adjusted EPS (excluding non-recurring items and amortization and impairment of acquired intangible assets) is expected to grow >10% compared to adjusted EPS of DKK 15.29 in 2021.", "adj. EPS growth %"),
    ("2022-05-05", 2022, O, "hearing_core", 5, 10, "reiterated", "Q1_22", "- Core business organic 5-10% ~14% ~ -150", "Q1 2022 report guidance table (confirmed as communicated on 10 Feb 2022)"),
    ("2022-05-05", 2022, E, "hearing_core", 14, 14, "reiterated", "Q1_22", "- Core business organic 5-10% ~14% ~ -150", "table row: organic / adj. EBITA margin / non-recurring"),
    ("2022-05-05", 2022, O, "audio", 5, None, "reiterated", "Q1_22", "- GN Audio organic >5%", "table row"),
    ("2022-05-05", 2022, O, "steelseries", 10, None, "reiterated", "Q1_22", "- SteelSeries >10%", "table row"),
    ("2022-05-05", 2022, E, "audio", 20, 20, "reiterated", "Q1_22", "GN Audio2) 3) ~20% ~ -400", "table row"),
    ("2022-05-05", 2022, OT, "group", 10, None, "reiterated", "Q1_22", "GN Store Nord >10%", "adj. EPS growth %, table row"),
    ("2022-08-17", 2022, O, "hearing_core", 5, 8, "lowered", "2500341", "GN Hearing - Core business organic 5-8% ~14% ~ -150", "GN: 'confirming the lower end of the guidance range' (5-10% -> 5-8%); Q2 report pre-released 17 Aug"),
    ("2022-08-17", 2022, E, "hearing_core", 14, 14, "reiterated", "2500341", "GN Hearing - Core business organic 5-8% ~14% ~ -150", ""),
    ("2022-08-17", 2022, O, "audio", 0, 5, "lowered", "2500341", "- GN Audio organic 6) 0-5% - SteelSeries 7) >-25%", "Consumer sentiment; Enterprise assumption unchanged"),
    ("2022-08-17", 2022, O, "steelseries", -25, None, "lowered", "2500341", "- GN Audio organic 6) 0-5% - SteelSeries 7) >-25%", "'>-25%' (report: 'better than -25%'); gaming market assumed -25%"),
    ("2022-08-17", 2022, E, "audio", 17, 18, "lowered", "2500341", "GN Audio 2) 8) 17-18% ~ -400", "GN: 'primarily driven by FX' (USD appreciation)"),
    ("2022-08-17", 2022, OT, "group", -10, 0, "lowered", "2500341", "GN Store Nord now expects growth in adj. EPS between -10% to 0%", "adj. EPS growth %"),
    ("2022-11-02", 2022, O, "audio", -7, -5, "lowered", "2547164", "GN Audio organic revenue growth guidance is revised from “0-5%” to now “-7% to -5%”", "profit warning; consumer markets -30%"),
    ("2022-11-02", 2022, E, "audio", 14, 15, "lowered", "2547164", "GN Audio’s adj. EBITA margin guidance is revised from “17-18%” to now “14-15%”", "lower revenue + stronger USD"),
    ("2022-11-02", 2022, OT, "group", -30, -30, "lowered", "2547164", "GN Store Nord revises the financial guidance on growth in adj. EPS from between -10% to 0% to now “around -30%”", "adj. EPS growth %, 'around -30%'"),
    ("2022-11-02", 2022, O, "hearing_core", 5, 8, "reiterated", "2547164", "All other guidance parameters are confirmed", ""),
    ("2022-11-02", 2022, E, "hearing_core", 14, 14, "reiterated", "2547164", "All other guidance parameters are confirmed", ""),
    ("2022-11-02", 2022, O, "steelseries", -25, None, "reiterated", "2547164", "All other guidance parameters are confirmed", ""),
    ("2022-11-11", 2022, O, "hearing_core", 5, 8, "reiterated", "Q3_22", "- Core business organic 5-8% ~14% ~ -150", "Q3 2022 report table (confirmed as of 11 Nov)"),
    ("2022-11-11", 2022, E, "hearing_core", 14, 14, "reiterated", "Q3_22", "- Core business organic 5-8% ~14% ~ -150", ""),
    ("2022-11-11", 2022, O, "audio", -7, -5, "reiterated", "Q3_22", "- GN Audio organic -7% to -5%", ""),
    ("2022-11-11", 2022, O, "steelseries", -25, None, "reiterated", "Q3_22", "- SteelSeries better than -25%", ""),
    ("2022-11-11", 2022, E, "audio", 14, 15, "reiterated", "Q3_22", "GN Audio2) 6) 14-15% ~ -500", ""),
    ("2022-11-11", 2022, OT, "group", -30, -30, "reiterated", "2553961", "The financial guidance, which was revised on November 2, 2022, is confirmed.", "adj. EPS growth %"),
    ("2023-02-09", 2022, O, "hearing_core", 5, 5, "actual", "AR22", "Organic growth 5% 5% 73% -7% -7% -19%", "AR2022 table: GN Hearing 5% / Core 5% / Emerging 73% / GN Audio -7% / Audio organic -7% / SteelSeries -19%"),
    ("2023-02-09", 2022, E, "hearing_core", 13.1, 13.1, "actual", "AR22", "delivering adj. EBITA of DKK 786 million corresponding to an adj. EBITA margin of 13.1%, which was in line with the financial guidance.", "adjusted, core business (guide ~14%)"),
    ("2023-02-09", 2022, O, "audio", -7, -7, "actual", "2604596", "GN Audio delivered -7% organic revenue growth in 2022, in line with the updated financial guidance.", "excl. SteelSeries (guide basis)"),
    ("2023-02-09", 2022, O, "steelseries", -19, -19, "actual", "AR22", "SteelSeries delivered organic revenue growth of -19% while gaining", ""),
    ("2023-02-09", 2022, E, "audio", 14.1, 14.1, "actual", "AR22", "translating into an adj. EBITA margin of 14.1%, compared to 21.2% in 2021", "adjusted, incl. SteelSeries (guide basis)"),
    ("2023-02-09", 2022, OT, "group", -31, -31, "actual", "AR22", "Adj. earnings per share (adj. EPS) was DKK 10.54 in 2022 compared to DKK 15.29 in 2021, translating into a growth of -31%", "adj. EPS growth %"),
    # ---------------- FY2023 (first group organic guide; margins per division, adjusted) ----------------
    ("2023-02-09", 2023, O, "hearing", 2, 8, "initial", "2604596", "an organic revenue growth between 2% to 8% driven by market share gains is expected for 2023.", "GN Hearing total (core + Emerging)"),
    ("2023-02-09", 2023, E, "hearing_core", 13, 16, "initial", "2604596", "For the core hearing aid business, the EBITA margin is expected to be between 13% to 16% for 2023 excluding non-recurring items.", "adjusted"),
    ("2023-02-09", 2023, O, "audio", -10, 5, "initial", "2604596", "GN Audio is expecting organic revenue growth between -10% to +5%.", "GN Audio now INCLUDES SteelSeries in organic growth (anniversary of 12 Jan 2022 close)"),
    ("2023-02-09", 2023, E, "audio", 10, 15, "initial", "2604596", "The EBITA margin is expected to be 10% to 15% for 2023 excluding non-recurring items.", "adjusted"),
    ("2023-02-09", 2023, O, "group", -6, 6, "initial", "2604596", "For full year 2023, GN Store Nord consequently expects organic revenue growth of -6% to +6% in 2023", "first group-level organic guide; no group margin guide in 2023"),
    ("2023-04-26", 2023, O, "group", -5, 7, "raised", "2655572", "The financial guidance on organic revenue growth is upgraded from “-6% to +6%” to “-5% to +7%”", "TRAP: the same announcement's guidance TABLE prints 'GN Store Nord -5% to +10%'; text, Q1 report and the 16 Aug update all say -5% to +7% -> table is a typo"),
    ("2023-04-26", 2023, O, "hearing", 5, 10, "raised", "2655572", "GN Hearing is upgrading its organic revenue growth guidance from “2% to 8%” to “5% to 10%”.", ""),
    ("2023-04-26", 2023, E, "hearing_core", 14, 16, "raised", "2655572", "the adj. EBITA margin in the core business is upgraded from “13% to 16%” to “14% to 16%”", ""),
    ("2023-04-26", 2023, O, "audio", -10, 5, "reiterated", "2655572", "GN Audio -10% to +5% 10% to 15% ~ -150", "table row; 'Full year guidance confirmed'"),
    ("2023-04-26", 2023, E, "audio", 10, 15, "reiterated", "2655572", "GN Audio -10% to +5% 10% to 15% ~ -150", "table row"),
    ("2023-08-16", 2023, O, "hearing", 9, 13, "raised", "2726719", "GN Hearing is upgrading its organic revenue growth guidance from “5% to 10%” to “9% to 13%”.", ""),
    ("2023-08-16", 2023, E, "hearing_core", 14, 16, "reiterated", "2726719", "The EBITA margin in the core business of “14% to 16%” is confirmed", ""),
    ("2023-08-16", 2023, O, "audio", -10, -4, "lowered", "2726719", "GN Audio’s organic revenue guidance is narrowed from “-10% to +5%” to “-10% to -4%”.", "GN calls it 'narrowed'; midpoint -2.5 -> -7"),
    ("2023-08-16", 2023, E, "audio", 10, 12, "lowered", "2726719", "GN Audio’s adj. EBITA margin is narrowed from “10% to 15%” to “10% to 12%”.", "GN calls it 'narrowed'; midpoint 12.5 -> 11"),
    ("2023-08-16", 2023, O, "group", -4, 2, "lowered", "2726719", "GN Store Nord’s organic revenue growth guidance is narrowed from “-5% to +7%” to “-4% to +2%”.", "GN calls it 'narrowed'; midpoint +1 -> -1"),
    ("2023-11-10", 2023, O, "group", -2, 0, "narrowed", "2778042", "GN Store Nord’s organic revenue growth guidance is narrowed from “-4% to +2%” to “-2% to 0%”.", "midpoint unchanged at -1"),
    ("2023-11-10", 2023, O, "hearing", 11, 13, "raised", "2778042", "GN Hearing is narrowing its organic revenue growth guidance from “9% to 13%” to “11% to 13%”.", "GN calls it 'narrowing'; midpoint 11 -> 12"),
    ("2023-11-10", 2023, E, "hearing_core", 14, 16, "reiterated", "2778042", "The EBITA margin in the core business of “14% to 16%” is confirmed", ""),
    ("2023-11-10", 2023, O, "audio", -9, -7, "lowered", "2778042", "GN Audio’s organic revenue guidance is narrowed from “-10% to -4%” to “-9% to -7%”.", "GN calls it 'narrowed'; midpoint -7 -> -8"),
    ("2023-11-10", 2023, E, "audio", 10, 12, "reiterated", "2778042", "GN Audio’s adj. EBITA margin is confirmed at “10% to 12%”", ""),
    ("2024-02-08", 2023, O, "group", -1, -1, "actual", "2825677", "GN delivered DKK 18.1 billion revenue with organic revenue growth of -1%, as a result of 13% organic revenue growth in GN Hearing and -8% organic revenue growth in GN Audio", "Annual report 2023"),
    ("2024-02-08", 2023, O, "hearing", 13, 13, "actual", "2825677", "GN delivered DKK 18.1 billion revenue with organic revenue growth of -1%, as a result of 13% organic revenue growth in GN Hearing and -8% organic revenue growth in GN Audio", ""),
    ("2024-02-08", 2023, O, "audio", -8, -8, "actual", "2825677", "GN delivered DKK 18.1 billion revenue with organic revenue growth of -1%, as a result of 13% organic revenue growth in GN Hearing and -8% organic revenue growth in GN Audio", "incl. SteelSeries"),
    ("2024-02-08", 2023, E, "hearing_core", 14.7, 14.7, "actual", "AR23", "delivering adj. EBITA of DKK 960 million, equal to an EBITA margin of 14.7% compared to 13.1% in 2022, in line with the financial guidance.", "adjusted, core business"),
    ("2024-02-08", 2023, E, "audio", 10.6, 10.6, "actual", "AR23", "GN Audio’s adj. EBITA ended at DKK 1,197 million, translating into an adj. EBITA margin of 10.6%, compared to 14.1% in 2022", "adjusted"),
    # ---------------- FY2024 (One-GN: GROUP guide, REPORTED EBITA margin; divisions = 'assumptions') ----------------
    ("2024-02-08", 2024, O, "group", 2, 8, "initial", "2825677", "Organic revenue growth EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 8% 12% to 14% >700", "guidance table; first group EBITA-margin guide; margin is REPORTED (no non-recurring adjustment from 2024)"),
    ("2024-02-08", 2024, E, "group", 12, 14, "initial", "2825677", "Organic revenue growth EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 8% 12% to 14% >700", "reported EBITA margin; 2023 comparable was adj. 9.9% / reported 6.6%"),
    ("2024-02-08", 2024, O, "hearing", 8, 12, "initial", "2825677", "the Hearing division assumes to contribute with organic revenue growth of 8% to 12%.", "divisional ASSUMPTION underlying the group guide"),
    ("2024-02-08", 2024, E, "hearing_core", 18, 20, "initial", "2825677", "the underlying assumptions include an EBITA margin in the core hearing aid business of 18% to 20%.", "assumption; FY2024 actual core margin not reported (divisional profit margin reported instead)"),
    ("2024-02-08", 2024, O, "enterprise", -3, 5, "initial", "2825677", "the Enterprise division assumes to contribute with organic revenue growth of -3% to 5%.", "assumption; Enterprise excl. BlueParrott (moved in from Consumer only from 2025)"),
    ("2024-02-08", 2024, O, "gaming_consumer", 2, 10, "initial", "2825677", "the Gaming & Consumer division assumes to contribute with organic revenue growth of 2% to 10%.", "assumption; Gaming & Consumer division = SteelSeries + Jabra Elite/Talk/BlueParrott"),
    ("2024-05-02", 2024, O, "group", 2, 8, "reiterated", "2873806", "The full year guidance is confirmed Financial guidance for 2024 Organic revenue growth EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 8% 12% to 14% >700", ""),
    ("2024-05-02", 2024, E, "group", 12, 14, "reiterated", "2873806", "The full year guidance is confirmed Financial guidance for 2024 Organic revenue growth EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 8% 12% to 14% >700", ""),
    ("2024-05-02", 2024, O, "hearing", 8, 12, "reiterated", "Q1_24", "Hearing division assumes to contribute with organic revenue growth of 8% to 12%", "Q1 2024 report"),
    ("2024-05-02", 2024, E, "hearing_core", 18, 20, "reiterated", "Q1_24", "core hearing aid business of 18% to 20%", "Q1 2024 report"),
    ("2024-05-02", 2024, O, "enterprise", -3, 5, "reiterated", "Q1_24", "contribute with organic revenue growth of -3% to 5%.", "Q1 2024 report (sentence split by 3-column layout; fragment quoted)"),
    ("2024-05-02", 2024, O, "gaming_consumer", 2, 10, "reiterated", "Q1_24", "contribute with organic revenue growth of 2% to 10%.", "Q1 2024 report (fragment)"),
    ("2024-06-11", 2024, O, "group", 2, 6, "lowered", "2896501", "the group organic revenue growth guidance is narrowed from “2% to 8%” to now “2% to 6%”.", "GN calls it 'narrowed'; Elite/Talk wind-down (Consumer ~DKK -450m vs 2023) partly offset by Hearing; ad-hoc announcement"),
    ("2024-06-11", 2024, E, "group", 12, 13, "lowered", "2896501", "GN is narrowing the EBITA margin guidance from “12% to 14%” to now “12% to 13%”.", "GN calls it 'narrowing'; reported margin now absorbs ~DKK -200m extraordinary wind-down costs (~1.1pp of revenue)"),
    ("2024-08-22", 2024, O, "group", 2, 6, "reiterated", "2933940", "The full year guidance, which was adjusted on June 11, is confirmed", "table labels the margin 'Reported EBITA margin'"),
    ("2024-08-22", 2024, E, "group", 12, 13, "reiterated", "2933940", "Organic revenue growth Reported EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 2% to 6% 12% to 13% >900", "explicitly REPORTED EBITA margin (incl. wind-down costs)"),
    ("2024-08-22", 2024, O, "hearing", 10, 12, "raised", "Q2_24", "the Hearing division is trending towards the upper half of the overall organic growth assumption of 8% to 12%.", "'upper half of 8-12%' -> 10-12"),
    ("2024-08-22", 2024, E, "hearing_core", 18, 20, "reiterated", "Q2_24", "GN is also well underway to deliver an EBITA margin of 18% to 20% in the core hearing aid business.", ""),
    ("2024-08-22", 2024, O, "enterprise", -3, 1, "lowered", "Q2_24", "the Enterprise division is trending towards the lower half of the overall organic growth assumption of -3% to +5%.", "'lower half of -3..+5' -> -3..+1"),
    ("2024-08-22", 2024, O, "gaming_consumer", -10, -2, "lowered", "Q2_24", "division is assumed to deliver organic revenue growth of -10% to -2%", "includes Elite/Talk wind-down; Gaming alone 'upper half of +2..+10'"),
    ("2024-11-06", 2024, O, "group", 1, 2, "lowered", "2975901", "Following a somewhat softer market development than earlier anticipated for Enterprise and Gaming, GN adjusts its organic revenue growth guidance to “1% to 2%”", ""),
    ("2024-11-06", 2024, E, "group", 12, 13, "reiterated", "2975901", "a confirmation of the EBITA margin guidance of “12 to 13%”", "reported"),
    ("2024-11-06", 2024, O, "hearing", 10, 12, "reiterated", "2975902", "GN expects the Hearing division to trend towards the upper half of the original organic growth assumption of 8% to 12%.", "'upper half' -> 10-12"),
    ("2024-11-06", 2024, E, "hearing_core", 20, 20, "raised", "2975902", "the Hearing division is projecting an EBITA margin in the core hearing aid business of around 20% for 2024.", "'around 20%' (top of the 18-20% assumption)"),
    ("2024-11-06", 2024, O, "enterprise", -3, -3, "lowered", "2975902", "the Enterprise division is currently assuming an overall organic revenue growth of around -3% for 2024 compared to the original assumption of -3% to +5%.", "'around -3%'; Central Europe sell-in pressure"),
    ("2024-11-06", 2024, O, "gaming_consumer", -10, -2, "reiterated", "2975902", "the Gaming & Consumer division is assumed to deliver organic revenue growth of -10% to -2% reflecting the announcement on June 11, 2024.", ""),
    ("2025-02-06", 2024, O, "group", 1, 1, "actual", "3021706", "translating into organic revenue growth excluding the wind-down of 4%, while the reported organic revenue growth was 1%.", "REPORTED organic (the 2024 guide basis, incl. wind-down); excl. wind-down 4% (next row)"),
    ("2025-02-06", 2024, O, "group", 4, 4, "actual", "3021706", "translating into organic revenue growth excluding the wind-down of 4%, while the reported organic revenue growth was 1%.", "EXCL. wind-down - NOT the 2024 guide basis; shown for the 2025 basis bridge"),
    ("2025-02-06", 2024, E, "group", 12.0, 12.0, "actual", "3021706", "The EBITA-margin increased by 5.4 percentage points compared to 2023 and ended at 12.0% in line with revised financial guidance following the wind-down.", "reported, incl. DKK -202m extraordinary wind-down costs"),
    ("2025-02-06", 2024, O, "hearing", 10, 10, "actual", "3021706", "as a result of 10% organic revenue growth in Hearing, -3% organic revenue growth in Enterprise, 7% organic revenue growth in Gaming, and -31% organic revenue growth in Consumer due to the wind-down", ""),
    ("2025-02-06", 2024, O, "enterprise", -3, -3, "actual", "3021706", "as a result of 10% organic revenue growth in Hearing, -3% organic revenue growth in Enterprise, 7% organic revenue growth in Gaming, and -31% organic revenue growth in Consumer due to the wind-down", "Enterprise excl. BlueParrott (revenue 7,205) = 2024 guide basis; AR2025 restates 2024 Enterprise incl. BlueParrott (7,474)"),
    ("2025-02-06", 2024, O, "gaming_consumer", -5, -5, "actual", "3021706", "translating into total organic revenue growth of -5% for the Gaming & Consumer division.", "Gaming +7%, Consumer -31%"),
    # ---------------- FY2025 (organic EXCL. wind-down; Gaming division ex Consumer; BlueParrott in Enterprise) ----------------
    ("2025-02-06", 2025, O, "group", 3, 7, "initial", "3021706", "Organic revenue growth excl. wind-down EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 3% to 7% 12% to 14% ~800", "organic EXCLUDES Elite/Talk wind-down (-3 to -4pp on reported organic)"),
    ("2025-02-06", 2025, E, "group", 12, 14, "initial", "3021706", "Organic revenue growth excl. wind-down EBITA margin Free cash flow excl. M&A (DKK million) GN Store Nord 3% to 7% 12% to 14% ~800", "reported EBITA margin"),
    ("2025-02-06", 2025, O, "hearing", 5, 9, "initial", "3021706", "the Hearing division assumes to contribute with organic revenue growth of 5% to 9%.", "assumption"),
    ("2025-02-06", 2025, O, "enterprise", 0, 4, "initial", "3021706", "the Enterprise division assumes to contribute with organic revenue growth of 0% to 4%.", "assumption; Enterprise now incl. BlueParrott (2024 restated)"),
    ("2025-02-06", 2025, O, "gaming", 7, 12, "initial", "3021706", "Gaming assumes to contribute with organic revenue growth of 7% to 12% (excluding the impact from the wind-down).", "assumption; wind-down impact on Gaming 19-20pp"),
    ("2025-04-30", 2025, O, "group", -3, 3, "lowered", "3071633", "GN now expects group organic revenue growth of -3% to +3%, an EBITA margin of 11% to 13%, and an unchanged free cash flow excl. M&A guidance of DKK ~800 million.", "US tariffs; ad-hoc announcement same day as Q1 report; excl. wind-down"),
    ("2025-04-30", 2025, E, "group", 11, 13, "lowered", "3071633", "GN now expects group organic revenue growth of -3% to +3%, an EBITA margin of 11% to 13%, and an unchanged free cash flow excl. M&A guidance of DKK ~800 million.", "reported"),
    ("2025-04-30", 2025, O, "hearing", 5, 9, "reiterated", "3071577", "Consequently, the Hearing division assumes to contribute with organic revenue growth of 5% to 9%.", ""),
    ("2025-04-30", 2025, O, "enterprise", -8, 0, "lowered", "3071577", "Consequently, the Enterprise division assumes to contribute with organic revenue growth of -8% to 0%.", ""),
    ("2025-04-30", 2025, O, "gaming", -6, 2, "lowered", "3071577", "Consequently, the Gaming division assumes to contribute with organic revenue growth of -6% to +2% (excluding the impact from the wind-down).", ""),
    ("2025-08-21", 2025, O, "group", -2, 2, "narrowed", "3136821", "The organic revenue growth guidance of -3% to +3% (excluding wind-down effects) is narrowed to -2% to +2%.", "midpoint unchanged at 0"),
    ("2025-08-21", 2025, E, "group", 11, 13, "reiterated", "3136821", "The guidance on EBITA-margin and free cash flow excl. M&A is confirmed", ""),
    ("2025-08-21", 2025, O, "hearing", 5, 7, "lowered", "3136821", "In the beginning of 2025, we assumed the Hearing division to contribute with organic revenue growth of 5% to 9%. Due to the lower market growth assumption, it is currently assumed that the Hearing division will grow at the lower half of that range.", "'lower half of 5-9%' -> 5-7"),
    ("2025-08-21", 2025, O, "enterprise", -4, -4, "narrowed", "3136821", "In April 2025, we assumed the Enterprise division would contribute with organic revenue growth of -8% to 0%, and we are continuing to assume a contribution in the middle of this range.", "'middle of -8..0' -> low=high=-4"),
    ("2025-08-21", 2025, O, "gaming", -2, 2, "raised", "3136821", "Driven by the strong execution in the first half of the year, the Gaming division is now assuming to contribute with organic revenue growth in the upper half of that range.", "'upper half of -6..+2' -> -2..+2 (range stated in preceding sentence)"),
    ("2025-11-06", 2025, O, "group", -2, 2, "reiterated", "3182179", "Following a successful execution in the first nine months of the year, GN’s financial guidance for 2025 is confirmed", ""),
    ("2025-11-06", 2025, E, "group", 11, 13, "reiterated", "3182179", "Confirmed Confirmed Confirmed -2% to +2% 11% to 13% ~800", "table row"),
    ("2025-11-06", 2025, O, "hearing", 5, 7, "reiterated", "3182179", "it is still assumed that the Hearing division will grow at the lower half of that range.", ""),
    ("2025-11-06", 2025, O, "enterprise", -4, -4, "reiterated", "3182179", "we are continuing to assume a contribution in the middle of this range.", ""),
    ("2025-11-06", 2025, O, "gaming", -2, 2, "reiterated", "3182179", "the Gaming division is still assuming to contribute with organic revenue growth in the upper half of that range.", ""),
    ("2026-02-05", 2025, O, "group", -1, -1, "actual", "3232627", "translating into organic revenue growth excluding the wind-down of -1%, while the reported organic revenue growth was -4%.", "excl. wind-down = 2025 guide basis"),
    ("2026-02-05", 2025, O, "group", -4, -4, "actual", "3232627", "translating into organic revenue growth excluding the wind-down of -1%, while the reported organic revenue growth was -4%.", "REPORTED organic - NOT the 2025 guide basis"),
    ("2026-02-05", 2025, E, "group", 11.4, 11.4, "actual", "3232627", "Group EBITA ended at DKK 1,908 million compared to DKK 2,153 million in 2024, equivalent to a margin of 11.4%.", "reported, group incl. Hearing (pre-sale basis)"),
    ("2026-02-05", 2025, O, "hearing", 5, 5, "actual", "3232627", "In the Hearing division, GN delivered another strong year with 5% organic growth", ""),
    ("2026-02-05", 2025, O, "enterprise", -6, -6, "actual", "3232627", "Organic growth was -6% in 2025", "incl. BlueParrott"),
    ("2026-02-05", 2025, O, "gaming", -2, -2, "actual", "3232627", "resulting in organic revenue growth of -2% (excluding the wind-down effect)", ""),
    # ---------------- FY2026 (group -> continuing ops after Hearing sale; margin suspended, then ADJUSTED) ----------------
    ("2026-02-05", 2026, O, "group", 3, 7, "initial", "3232627", "Financial guidance for 2026 Organic revenue growth EBITA margin GN Store Nord 3% to 7% 11.5% to 13.5%", "group incl. Hearing; no wind-down adjustment any more; no FCF guide"),
    ("2026-02-05", 2026, E, "group", 11.5, 13.5, "initial", "3232627", "Financial guidance for 2026 Organic revenue growth EBITA margin GN Store Nord 3% to 7% 11.5% to 13.5%", "reported EBITA margin, group incl. Hearing"),
    ("2026-02-05", 2026, O, "hearing", 3, 7, "initial", "3232627", "Consequently, the Hearing division assumes to contribute with organic revenue growth of 3% to 7%.", "assumption"),
    ("2026-02-05", 2026, O, "enterprise", 0, 6, "initial", "3232627", "it is assumed that the Enterprise division will contribute with organic revenue growth of 0% to 6%.", "assumption"),
    ("2026-02-05", 2026, O, "gaming", 7, 13, "initial", "3232627", "Consequently, Gaming assumes to contribute with organic revenue growth of 7% to 13%.", "assumption"),
    ("2026-03-16", 2026, O, "continuing_ops", 2, 8, "basis_change", "3256006", "Consequently, the organic revenue guidance is now expected to be 2-8%, based on unchanged divisional assumptions of 0-6% organic revenue growth in Enterprise, and 7-13% organic revenue growth in Gaming.", "Hearing sale to Amplifon: Hearing -> discontinued ops; guide now Enterprise + Gaming only. Not a revision of expectations"),
    ("2026-03-16", 2026, E, "group", None, None, "withdrawn", "3256006", "Following the establishment of a standalone operating system structure, the company is expected to re-introduce a profitability guidance.", "EBITA-margin guide (11.5-13.5%) suspended; May 2026 table shows prior = 'Suspended'"),
    ("2026-03-16", 2026, O, "hearing", None, None, "withdrawn", "3256006", "GN’s financial guidance for 2026 now excludes discontinued operations and therefore only reflects Enterprise and Gaming.", "Hearing no longer guided (discontinued operations)"),
    ("2026-03-16", 2026, O, "enterprise", 0, 6, "reiterated", "3256006", "based on unchanged divisional assumptions of 0-6% organic revenue growth in Enterprise, and 7-13% organic revenue growth in Gaming.", ""),
    ("2026-03-16", 2026, O, "gaming", 7, 13, "reiterated", "3256006", "based on unchanged divisional assumptions of 0-6% organic revenue growth in Enterprise, and 7-13% organic revenue growth in Gaming.", ""),
    ("2026-05-06", 2026, O, "continuing_ops", 0, 6, "lowered", "3289173", "GN Store Nord (continuing operations) is adjusting its organic revenue growth guidance from 2% to 8% to now 0% to 6%", "EMEA Enterprise + channel inventory reductions"),
    ("2026-05-06", 2026, E, "continuing_ops", 8, 9, "initial", "3289173", "The adj. EBITA margin (excluding one-off costs) for the continuing operations is expected to be 8-9% in 2026 (compared to 7.6% in 2025)", "RE-INTRODUCED on a new basis: ADJUSTED (excl. ~DKK 750m one-off carve-out/right-sizing costs, ~75% in 2026), continuing ops; FY2025 cont-ops base 7.6%. Not comparable with the Feb 11.5-13.5% reported group guide"),
    ("2026-05-06", 2026, O, "enterprise", -3, 3, "lowered", "3289173", "Consequently, it is assumed that Enterprise will contribute with organic revenue growth of -3% to +3% in a modestly declining market.", ""),
    ("2026-05-06", 2026, O, "gaming", 7, 13, "reiterated", "3289173", "it is still assumed that Gaming will contribute with organic revenue growth of 7% to 13% for 2026.", ""),
    ("2026-08-19", 2026, O, "continuing_ops", 0, 3, "lowered", "3350848", "GN Store Nord (continuing operations) is narrowing its organic revenue growth guidance from 0% to 6% to now 0% to 3%.", "GN calls it 'narrowing'; top end cut, midpoint 3 -> 1.5"),
    ("2026-08-19", 2026, E, "continuing_ops", 9, 10, "raised", "3350848", "which is expected to lead to an adjusted EBITA margin of 9-10% in 2026.", "includes DKK 100-150m expected US IEEPA tariff refunds in H2 (not in prior guide) ~ +1.0-1.6pp on ~DKK 9.5bn revenue"),
    ("2026-08-19", 2026, O, "enterprise", -3, 0, "lowered", "3350848", "it is assumed that Enterprise will contribute with organic revenue growth in the lower half of the earlier assumed range of -3% to +3%", "'lower half of -3..+3' -> -3..0"),
    ("2026-08-19", 2026, O, "gaming", 7, 10, "lowered", "3350848", "it is assumed that Gaming will contribute with organic revenue growth in the lower half of the earlier assumed range of 7% to 13%", "'lower half of 7..13' -> 7..10"),
]



TRAPS = """## Basis changes and traps (read before comparing guide with actual)

1. **Per-division, not group, until 2023.** FY2021-22 guided GN Hearing and GN Audio separately (plus EPS growth for the
   group); FY2023 added a group organic range but margins stayed per division; FY2024 onward guides the group, with
   divisional numbers only as 'assumptions'. Rows keep the scope as stated (`hearing`, `hearing_core`, `audio`,
   `steelseries`, `enterprise`, `gaming_consumer`, `gaming`, `group`, `continuing_ops`).
2. **SteelSeries (closed 12 Jan 2022).** FY2022 'GN Audio organic' EXCLUDES SteelSeries (reported as M&A growth; SteelSeries
   guided separately, `steelseries`), but the GN Audio adj. EBITA margin INCLUDES it. From FY2023 Audio organic includes
   SteelSeries. From 6 Oct 2021 the FY2021 guides exclude ~DKK 150m SteelSeries transaction costs (FY2021 Audio actual
   21.2% is also excl. DKK 45m transaction costs).
3. **Adjusted vs reported EBITA.** FY2021: reported. FY2022-23: adjusted (excl. non-recurring items), and for Hearing only the
   core business (Emerging Business guided in DKK, not recorded). FY2024-25 and Feb 2026: group REPORTED EBITA margin -
   the June 2024 cut to 12-13% absorbs ~DKK -200m extraordinary wind-down costs. From 6 May 2026: ADJUSTED margin for
   continuing operations, excl. ~DKK 750m one-off carve-out/right-sizing costs. Never EBIT: GN guides EBITA throughout;
   consensus sources quoting EBIT (e.g. MarketScreener) differ by amortisation of acquired intangibles (~DKK 0.4bn/yr).
4. **Reported vs organic vs 'organic excl. wind-down'.** All growth guides are organic. FY2025 group (and Gaming) organic
   EXCLUDES the Elite/Talk wind-down (-3 to -4pp group); FY2024 guides were on reported organic (incl. wind-down after
   June 2024). Both actuals are recorded (2024: 1% reported / 4% ex wind-down; 2025: -1% ex / -4% reported), with the
   guide basis flagged in `note`.
5. **Division perimeter changes.** Gaming & Consumer (FY2024) -> Gaming (FY2025+, Consumer wound down); BlueParrott moved
   from Consumer to Enterprise from 2025 (2024 Enterprise 7,205 as guided vs 7,474 restated in AR2025).
6. **Hearing sold (16 Mar 2026).** Group guide -> continuing operations (Enterprise + Gaming): organic 3-7% (group) became
   2-8% (cont. ops) with unchanged divisional assumptions = `basis_change`, not a revision; EBITA-margin guide
   `withdrawn` 16 Mar - 6 May 2026, then re-introduced as adjusted cont.-ops margin 8-9% (FY2025 cont.-ops base 7.6%).
   The FY2026 actual (AR2026, ~Feb 2027) must be read on the cont.-ops adjusted basis; not yet available.
7. **One-offs inside a raise.** The 19 Aug 2026 margin raise to 9-10% includes DKK 100-150m expected US IEEPA tariff
   refunds (not in the prior guide) - worth ~1.0-1.6pp on ~DKK 9.5bn revenue, i.e. most of the 1pp raise.
8. **'Narrowed' that is a cut.** GN's 'narrowed' often moved the midpoint down (Aug 2023 group and Audio, Nov 2023 Audio,
   Jun 2024 group organic and margin, Aug 2026 cont.-ops organic). The `action` column follows the midpoint.
9. **Source typo.** The 26 Apr 2023 announcement's guidance TABLE prints group organic '-5% to +10%'; its text, the Q1 2023
   report and the 16 Aug 2023 update say '-5% to +7%'. Recorded -5 to +7.
10. **Timing.** Guidance announcements are released the evening before the download-center report date (e.g. 19 vs 20 Aug
   2026, 6 vs 7 May 2026, 30 Apr vs 1 May 2025, 6 vs 7 Nov 2024); `statement_date` is the announcement date.
11. **Gaps.** No FY2024 core-hearing EBITA-margin actual is reported (divisional profit margin instead) - no actual row.
   FY2021 EPS-growth actual is derived (13.90 / 9.72 - 1). DKK-denominated guides (Other EBITA, Emerging Business,
   non-recurring items, free cash flow) are not recorded. No IFRS change affecting the guided metrics in 2021-2026
   (IFRS 16 adopted 2019).
"""


def norm(s):
    s = re.sub(r"[‘’´`]", "'", s)
    s = re.sub(r"[“”]", '"', s)
    return re.sub(r"\s+", " ", s).strip().lower()


def found(quote, path):
    raw = path.read_text(errors="ignore")
    dehyph = re.sub(r"(\w)-\n(\w)", r"\1\2", raw)
    q = norm(quote)
    return q in norm(raw) or q in norm(dehyph)


def fmt(v):
    return "" if v is None else (str(int(v)) if float(v).is_integer() else str(v))


rows, checks = [], []
for d, fy, m, sc, lo, hi, act, key, q, note in R:
    url, path = src(key)
    ok = found(q, path)
    nw = len(q.split())
    assert nw <= 50, (d, m, sc, nw)
    rows.append({"company": "gn", "statement_date": d, "fiscal_year": fy, "metric": m, "scope": sc,
                 "low": fmt(lo), "high": fmt(hi), "action": act, "url": url, "quote": q, "note": note})
    checks.append((d, fy, m, sc, act, url, path.name, q, ok))

OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

# ---------- excerpts file: one block per source document, rows listed under it ----------
by_src = {}
for c in checks:
    by_src.setdefault((c[5], c[6]), []).append(c)
lines = [
    "# GN Store Nord - financial guidance history FY2021-FY2026: quote evidence",
    "",
    f"Every row of `data/raw/gn_guidance_history.csv` with the source URL, retrieval date ({RETRIEVED}), the local text copy",
    "(under `data/cache/verbal/`, gitignored) and the exact excerpt. `check` = the excerpt was found word for word in the",
    "saved copy (whitespace collapsed, curly quotes/apostrophes straightened, case-insensitive; for PDFs a line-end",
    "hyphen join is also tried). Company announcements are the gn.com Newsroom pages (GN's company announcements, also",
    "distributed via Nasdaq Copenhagen / GlobeNewswire - those copies were not fetched: globenewswire.com timed out); PDFs are from the gn.com Financial Download Center, extracted three ways per page",
    "(two-column halves, three-column thirds, full width) because GN's layouts interleave columns; table rows are quoted",
    "as their cells in reading order.",
    "",
    "Action convention: `raised` / `lowered` follow the MIDPOINT (or the open bound) of the range, not GN's wording; when",
    "GN calls a change 'narrowed' but the midpoint moved, the row says so in `note`. `narrowed` = midpoint unchanged.",
    "Qualitative ranges are converted: 'upper/lower half of A-B' -> that half; 'middle of A-B' -> low=high=midpoint;",
    "'more than X' / '>X' / 'better than X' -> low=X, high blank; 'around X' / '~X' -> low=high=X.",
    "",
]
for (url, fname), cs in by_src.items():
    lines += [f"## {cs[0][0]} - {url}", "", f"- retrieved: {RETRIEVED}", f"- local copy: `data/cache/verbal/{fname}`", ""]
    seen = set()
    for d, fy, m, sc, act, _, _, q, ok in cs:
        tag = f"FY{fy} {sc} {m} ({act})"
        lines.append(f"- {tag}: check {'found' if ok else 'NOT FOUND'}")
        if q not in seen:
            lines.append(f"  > {q}")
            seen.add(q)
    lines.append("")
OUT_MD.write_text("\n".join(lines) + "\n" + TRAPS)

n_ok = sum(c[-1] for c in checks)
print(f"rows {len(rows)}; quotes found {n_ok}/{len(checks)}")
for c in checks:
    if not c[-1]:
        print("NOT FOUND:", c[0], c[2], c[3], c[6][-50:], "|", c[7][:120])
from collections import Counter
print(Counter(r["fiscal_year"] for r in rows))
