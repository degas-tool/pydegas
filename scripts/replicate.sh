#!/usr/bin/env bash
# Replicates the experimental results of the paper. Everything is written to
# results/ as well as to the terminal. Approximately 40 minutes on a laptop.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p results

echo "== A. Running example (Listing 1.1): insulin pump, Adam, 150 steps max =="
echo "   expected: 'gTh' ~128.6, 'uHigh' ~15.0, loss ~0.782, converged at step 144 (or 143, see README)"
python examples/insulin_pump.py results/insulin_pump_trace.json 2>&1 | tee results/insulin_pump.txt
python scripts/compare_insulin.py results/insulin_pump_trace.json 2>&1 | tee -a results/insulin_pump.txt

echo "== B. Test suite incl. differential tests against the reference =="
(cd libs/pydegas && python -m pytest -p no:cacheprovider -q) 2>&1 | tee results/tests.txt

echo "== C. Case studies (thermostat, gearbox, PID) vs. the reference =="
python scripts/case_studies.py 2>&1 | tee results/case_studies.txt

echo "Done. Results are in $(pwd)/results"
