#!/usr/bin/env bash
# One-shot run from the committed data (no network, ~2 min): install deps, run the model, run the tests.
#   ./run.sh                 model + tests
#   ./run.sh --refresh-data  first re-fetch and re-validate every data pipeline (SEC / company sites; ~1 GB, slow on first run)
#   ./run.sh --live          take a fresh distributor-stock reading for the live gauge (Nordic channel tightness), then run
set -e
python3 -m pip install -q -r requirements.txt
if [ "$1" = "--refresh-data" ]; then
  python3 pipelines/A_company_financials/scripts/validate.py --no-fetch-verbal   # Pipeline A: company financials
  python3 pipelines/B_macro_industry/scripts/validate.py                          # Pipeline B: macro / industry context
  python3 pipelines/C_realtime_channel/scripts/validate.py --no-snapshot --no-ifixit   # Pipeline C: stored channel series
  python3 pipelines/D_peer_panel/scripts/validate.py                             # Pipeline D: peer guidance panel
fi
if [ "$1" = "--live" ]; then
  python3 pipelines/C_realtime_channel/scripts/validate.py --no-ifixit           # today's authorized-distributor reading
fi
python3 scripts/run_all.py                                                      # steps 1-7 -> outputs/
python3 -m pytest -q tests
