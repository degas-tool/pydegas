"""Differential check of the optimization case studies (paper, Section 5).

For the thermostat, gearbox and PID case studies of the DeGAS paper, the same
program text and the same hyperparameters are optimized twice:

  * by the reference implementation in reference/DeGAS/src (Adam loop of
    reference/DeGAS/src/optimization.py), and
  * by pydegas (OptimizationRun).

The script prints, per case study, the maximum relative difference between the
two loss traces and between the final parameters.

Usage: python scripts/case_studies.py [--steps N] [thermostat gearbox pid ...]
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
import tempfile
import time
from pathlib import Path

import torch


ROOT = Path(__file__).resolve().parents[1]
REF_SRC = ROOT / "reference" / "DeGAS" / "src"
# programs of the bundled web examples (libs/degas-ui/src/examples.ts); they bound the
# number of mixture components with prune(10);
PROGRAMS = ROOT / "scripts" / "programs"

# program file, initial parameters, learning rate, steps, signal_error(target, time_steps), pruning.
# The web examples use kmeans pruning, which is random and not in the reference; classic is used here.
CASES = {
    "thermostat": ("thermostat.soga", {"tOff": 22.0, "tOn": 15.0}, 0.2, 100, (18.0, 31), "classic"),
    "gearbox": ("gearbox.soga", {"s1": 8.0, "s2": 12.0}, 0.3, 200, (15.0, 21), "classic"),
    "pid": ("pid.soga", {"s0": 46.0, "s1": -23.0, "s2": 0.0}, 0.2, 500, (3.14, 51), "classic"),
}


def load_reference():
    torch.set_default_dtype(torch.float64)  # as in the reference notebooks
    sys.path.insert(0, str(REF_SRC))
    names = ("producecfg", "libSOGA", "smoothcfg", "sogaPreprocessor", "optimization")
    return {n: importlib.import_module(n) for n in names}


def run_reference(ref, program, init, lr, steps, loss_args, pruning):
    cfg = ref["producecfg"].produce_cfg_text(ref["sogaPreprocessor"].compile2SOGA_text(program))
    ref["smoothcfg"].smooth_cfg(cfg)
    opt = ref["optimization"]
    params = opt.initialize_params(init)
    optimizer = torch.optim.Adam(list(params.values()), lr=lr)
    target, time_steps = loss_args
    losses = []
    for _ in range(steps):
        optimizer.zero_grad()
        dist = ref["libSOGA"].start_SOGA(cfg, params, pruning=pruning)
        loss = opt.signal_error(dist, target=target, T=time_steps)
        losses.append(loss.item())
        loss.backward(retain_graph=True)
        optimizer.step()
    return losses, {k: v.item() for k, v in params.items()}


def run_pydegas(program, init, lr, steps, loss_args, pruning):
    from pydegas.cfg import smooth
    from pydegas.cfg.builder import from_text
    from pydegas.optimize import OptimizationRun, get_loss
    from pydegas.parse.preprocessor import compile_to_soga_text

    cfg = from_text(compile_to_soga_text(program))
    smooth(cfg)
    target, time_steps = loss_args
    run = OptimizationRun(
        cfg,
        init,
        get_loss("signal_error", target=target, time_steps=time_steps),
        optimizer="Adam",
        optimizer_kwargs={"lr": lr},
        tolerance=None,
        pruning=pruning,
    )
    results = run.run(steps)
    return [r.loss for r in results], dict(results[-1].params)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", nargs="*", metavar="case", help="thermostat, gearbox and/or pid (default: all)")
    parser.add_argument("--steps", type=int, default=None, help="override the number of steps")
    args = parser.parse_args()
    args.cases = args.cases or list(CASES)
    unknown = [c for c in args.cases if c not in CASES]
    if unknown:
        parser.error(f"unknown case(s) {unknown}; choose from {list(CASES)}")

    ref = load_reference()
    os.chdir(tempfile.mkdtemp())  # the reference optimizer writes statistics files into the cwd
    worst = 0.0
    for name in args.cases:
        file, init, lr, steps, loss_args, pruning = CASES[name]
        steps = args.steps or steps
        program = (PROGRAMS / file).read_text()
        t0 = time.time()
        torch.manual_seed(0)
        old_losses, old_params = run_reference(ref, program, init, lr, steps, loss_args, pruning)
        t1 = time.time()
        torch.manual_seed(0)
        new_losses, new_params = run_pydegas(program, init, lr, steps, loss_args, pruning)
        t2 = time.time()
        old, new = torch.tensor(old_losses, dtype=torch.float64), torch.tensor(new_losses, dtype=torch.float64)
        trace = ((new - old).abs() / old.abs().clamp_min(1e-12)).max().item()
        par = max(abs(new_params[k] - old_params[k]) / max(abs(old_params[k]), 1e-12) for k in old_params)
        worst = max(worst, trace)
        print(
            f"{name:11s} steps={steps:4d}  loss {old_losses[0]:.4f} -> {old_losses[-1]:.4f}  "
            f"max rel. diff of loss trace = {trace:.2e}, of final parameters = {par:.2e}  "
            f"(reference {t1 - t0:.0f}s, pydegas {t2 - t1:.0f}s)",
            flush=True,
        )
    print(f"worst loss-trace relative difference: {worst:.2e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
