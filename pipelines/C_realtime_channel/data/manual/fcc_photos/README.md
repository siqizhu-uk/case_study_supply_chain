# FCC internal-photo evidence (Logitech, grantee JNZ)

Each PNG is a screenshot taken in the user's Chrome on 2026-09-23 from the fccid.io mirror of the FCC OET exhibit
(`https://fccid.io/<FCC_ID>/Internal-Photos/Internal-Photos-<attachment_id>.pdf`; apps.fcc.gov refuses non-US clients,
fccid.io / fcc.report show a human "Continue" check that the user clicked). `<FCC_ID>_soc.png` / `_zoom*.png` are the
chip close-ups the reading rests on; `<FCC_ID>_p<N>.png` are full pages. The reading (marking, vendor, page, confidence)
is written into `../../raw/fcc_logitech_grants_2023_2026.csv` (`soc_marking_observed`, `chip_vendor`, `notes`) and, for
the batch captured by the sub-agent, also in `READINGS.csv`. Nordic package codes: QFAA = nRF52832 / nRF52810,
QIAA = nRF52833 / nRF52840, QDAA = nRF52820. Step 2 (`steps/step2_attribution`) reads the CSV: once ≥ 10 peripheral
grants are legible the census replaces the socket-share prior.
