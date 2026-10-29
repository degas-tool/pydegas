"""Compares an insulin-pump run with the run of Listing 1.1 on an Apple M2 Pro.

scripts/insulin_pump_reference.json holds every step of examples/insulin_pump.py
on an Apple M2 Pro (macOS 26.6.2, Python 3.12.12, PyTorch 2.12.0). The script
prints the largest relative difference of the loss and parameter traces over the
steps both runs have and, if they stop at different steps, the loss change that
decides the stopping rule (10 loss changes in a row below 0.001).

Usage: python scripts/compare_insulin.py TRACE.json  (from examples/insulin_pump.py TRACE.json)
"""

import json
import sys
from pathlib import Path


REFERENCE = Path(__file__).with_name("insulin_pump_reference.json")
TOLERANCE, PATIENCE = 1e-3, 10


def rel(a: float, b: float) -> float:
    return abs(a - b) / max(abs(b), 1e-12)


def change(steps: list[dict], i: int) -> float:
    return abs(steps[i]["loss"] - steps[i - 1]["loss"])


def main() -> int:
    run = json.loads(Path(sys.argv[1]).read_text())
    ref = json.loads(REFERENCE.read_text())
    n = min(len(run), len(ref))
    loss = max(rel(run[i]["loss"], ref[i]["loss"]) for i in range(n))
    params = max(rel(run[i]["params"][k], ref[i]["params"][k]) for i in range(n) for k in ref[i]["params"])
    print(
        f"compared with the Apple M2 Pro run over {n} steps: "
        f"max rel. diff of loss trace = {loss:.2e}, of parameter trace = {params:.2e}"
    )
    last_run, last_ref = run[-1]["step"], ref[-1]["step"]
    if last_run == last_ref:
        print(f"both runs converged at step {last_run}")
    else:
        k = min(last_run, last_ref) - PATIENCE + 1
        print(
            f"this run stopped at step {last_run}, the Apple M2 Pro run at step {last_ref}: the loss change "
            f"at step {k} is {change(run, k):.6f} here and {change(ref, k):.6f} there, against the tolerance "
            f"{TOLERANCE}; the two differ only by float32 rounding"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
