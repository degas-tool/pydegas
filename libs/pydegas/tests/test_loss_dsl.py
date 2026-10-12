from __future__ import annotations

import pytest


def _sample_dist():
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.semantics.engine import start_soga

    program = "array[6] X;\nx = 0;\nfor i in range(6) { x = x + gm([1.0],[0.5],[0.2]); X[i] = x; } end for;\n"
    cfg = from_text(program)
    smooth(cfg)
    return start_soga(cfg, {})


def test_every_registered_loss_has_a_dsl_definition() -> None:
    from pydegas.optimize.losses import LOSS_DSL_SOURCE, LOSS_REGISTRY

    assert set(LOSS_REGISTRY) <= set(LOSS_DSL_SOURCE), (
        "every loss in LOSS_REGISTRY needs a LOSS_DSL_SOURCE entry: "
        f"missing {set(LOSS_REGISTRY) - set(LOSS_DSL_SOURCE)}"
    )


def test_all_dsl_definitions_parse() -> None:
    from pydegas.optimize.dsl import validate_loss
    from pydegas.optimize.losses import LOSS_DSL_SOURCE

    for name, source in LOSS_DSL_SOURCE.items():
        errors = validate_loss(source)
        assert not errors, f"{name} DSL has parse errors: {errors}"


def test_l2_distance_dsl_matches_python() -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss
    from pydegas.optimize.losses import LOSS_DSL_SOURCE, l2_distance

    dist = _sample_dist()
    n = dist.gm.mean().shape[0]
    torch.manual_seed(0)
    indices = [0, 1, 2, 3, 4]
    traj = dist.gm.mean().detach().double().unsqueeze(0).repeat(8, 1) + 0.05 * torch.randn(8, n, dtype=torch.float64)

    py = l2_distance(traj, indices)(dist)
    dsl = compile_loss(LOSS_DSL_SOURCE["l2_distance"], trajectories=traj, indices=indices)(dist)
    assert torch.allclose(dsl.double(), py.double(), rtol=1e-5, atol=1e-6)


def test_neg_log_likelihood_dsl_matches_python() -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss
    from pydegas.optimize.losses import LOSS_DSL_SOURCE, neg_log_likelihood

    dist = _sample_dist()
    n = dist.gm.mean().shape[0]
    torch.manual_seed(0)
    indices = [0, 1, 2, 3, 4]
    # keep trajectories near the mean so the pdf (and its log) stays finite.
    traj = dist.gm.mean().detach().double().unsqueeze(0).repeat(8, 1) + 0.05 * torch.randn(8, n, dtype=torch.float64)

    py = neg_log_likelihood(traj, indices)(dist)
    dsl = compile_loss(LOSS_DSL_SOURCE["neg_log_likelihood"], trajectories=traj, indices=indices)(dist)
    assert torch.isfinite(dsl)
    assert torch.allclose(dsl.double(), py.double(), rtol=1e-5, atol=1e-6)


def test_signal_error_dsl_compiles_and_runs() -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss
    from pydegas.optimize.losses import LOSS_DSL_SOURCE

    dist = _sample_dist()
    dsl = compile_loss(LOSS_DSL_SOURCE["signal_error"], target=0.7)(dist)
    assert torch.isfinite(dsl)


@pytest.mark.parametrize("name", ["l2_distance", "neg_log_likelihood"])
def test_shipped_dsl_matches_builtin_parameter_gradient(name):
    torch = pytest.importorskip("torch")
    from pydegas.cfg.builder import from_text
    from pydegas.optimize.dsl import compile_loss
    from pydegas.optimize.losses import LOSS_DSL_SOURCE, get_loss
    from pydegas.semantics.engine import start_soga

    parameter = torch.tensor(0.3, requires_grad=True)
    dist = start_soga(from_text("x = gm([1.0],[_mu],[1.0]);"), {"mu": parameter})
    trajectories = torch.tensor([[-0.5], [0.0], [0.8]])
    bindings = {"trajectories": trajectories, "indices": [0]}
    builtin = get_loss(name, **bindings)(dist)
    dsl = compile_loss(LOSS_DSL_SOURCE[name], **bindings)(dist)
    builtin_gradient = torch.autograd.grad(builtin, parameter, retain_graph=True)[0]
    dsl_gradient = torch.autograd.grad(dsl, parameter)[0]
    assert torch.isfinite(dsl_gradient) and dsl_gradient.abs() > 0
    torch.testing.assert_close(dsl_gradient, builtin_gradient, rtol=1e-5, atol=1e-6)
