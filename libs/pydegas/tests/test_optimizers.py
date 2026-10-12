"""Smoke tests: every registered optimizer completes 3 steps without error."""

from __future__ import annotations

import pytest


# _mu is a learnable parameter (underscore prefix); initial value supplied via initial_params
SIMPLE_PROGRAM = """
array[5] X;
x = _mu;
for i in range(5) {
    x = x + gauss(0.0, 0.1);
    X[i] = x;
} end for;
"""


@pytest.fixture
def cfg():
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.parse.preprocessor import compile_to_soga_text

    compiled = compile_to_soga_text(SIMPLE_PROGRAM, seed=0)
    graph = from_text(compiled)
    smooth(graph)
    return graph


@pytest.fixture(scope="module")
def loss_fn():
    from pydegas.optimize.losses import signal_error

    return signal_error(target=0.5, time_steps=4)


@pytest.mark.parametrize("optimizer_name", ["Adam", "AdamW", "SGD", "RMSprop", "Adagrad", "LBFGS"])
def test_optimizer_runs_3_steps(cfg, loss_fn, optimizer_name) -> None:
    pytest.importorskip("torch")
    import torch

    from pydegas.optimize.runner import OptimizationRun

    run = OptimizationRun(
        cfg=cfg,
        initial_params={"mu": 1.0},
        loss_fn=loss_fn,
        optimizer=optimizer_name,
        optimizer_kwargs={"lr": 0.1},
    )
    steps = run.run(3)

    assert len(steps) == 3, f"{optimizer_name}: expected 3 steps, got {len(steps)}"
    for s in steps:
        assert torch.isfinite(torch.tensor(s.loss)), f"{optimizer_name}: non-finite loss at step {s.step}"
        assert "mu" in s.params, f"{optimizer_name}: param 'mu' missing at step {s.step}"
        assert torch.isfinite(torch.tensor(s.params["mu"])), f"{optimizer_name}: non-finite param at step {s.step}"
    assert steps[-1].loss < steps[0].loss, f"{optimizer_name}: loss did not decrease"
    assert steps[-1].params["mu"] != pytest.approx(1.0), f"{optimizer_name}: parameter did not change"
