#!/usr/bin/env bash
# Smoke test (about 1 minute): import check, a 3-step optimization, the unit and
# differential test suite, and a short run of the case-study comparison.
# Run from anywhere; needs `python` to be the environment with pydegas installed.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== 1/3  three-step optimization (Listings 1.2 and 1.3) =="
python scripts/smoke_test.py

echo "== 2/3  test suite incl. differential tests against reference/DeGAS =="
(cd libs/pydegas && python -m pytest -q -p no:cacheprovider)

echo "== 3/3  case studies, 3 steps each, against the reference =="
python scripts/case_studies.py --steps 3

echo "SMOKE TEST PASSED"
