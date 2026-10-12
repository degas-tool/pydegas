"""Differential tests against DeGAS/src, not copied expected output or pydegas helpers."""

from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")
pytestmark = pytest.mark.reference

PROGRAMS = [
    pytest.param("x = gm([1.0],[2.0],[0.5]); y = 2*x + 1;", id="affine"),
    pytest.param("x = gm([0.3,0.7],[-1.0,2.0],[0.5,1.0]); y = x + gm([0.4,0.6],[0.0,1.0],[0.2,0.3]);", id="mixtures"),
    pytest.param("x = gm([1.0],[2.0],[0.5]); y = gm([1.0],[3.0],[1.0]); z = x*y;", id="product"),
    pytest.param("x = gm([1.0],[0.0],[1.0]); if x > 0 { y = x; } else { y = -1*x; } end if;", id="branch"),
    pytest.param("x = gm([1.0],[0.0],[1.0]); y = x + gm([1.0],[0.0],[1.0]); observe(y > 0);", id="observe"),
    pytest.param(
        "array[3] X; x = 0; for i in range(3) { x = x + gm([1.0],[0.5],[0.2]); X[i] = x; } end for;", id="loop-array"
    ),
    pytest.param("data a = [1.0,2.0]; array[2] X; for i in range(2) { X[i] = a[i]; } end for;", id="data"),
    pytest.param("x = gm([0.1,0.2,0.3,0.4],[-3.0,-1.0,1.0,3.0],[0.2,0.2,0.2,0.2]); prune(2);", id="explicit-prune"),
]


@pytest.mark.parametrize("program", PROGRAMS)
@pytest.mark.parametrize("smoothed", [False, True], ids=["raw", "smoothed"])
def test_program_distribution_matches_reference(reference, assert_same_distribution, program, smoothed):
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.semantics.engine import start_soga

    actual_cfg = from_text(program)
    expected_cfg = reference.builder.produce_cfg_text(program)
    assert actual_cfg.ID_list == expected_cfg.ID_list
    if smoothed:
        smooth(actual_cfg)
        reference.smoother.smooth_cfg(expected_cfg)
    expected = reference.engine.start_SOGA(expected_cfg)
    actual = start_soga(actual_cfg)
    assert_same_distribution(actual, expected)


@pytest.mark.parametrize("helper", ["gauss(1.5, 0.2)", "bern(0.3)"])
def test_exact_helper_rewriting_matches_reference(reference, helper):
    from pydegas.parse.preprocessor import compile_to_soga_text

    program = f"x = {helper};"
    assert compile_to_soga_text(program, seed=0) == reference.preprocessor.compile2SOGA_text(program)


@pytest.mark.parametrize("condition", ["x > 0", "x < 1", "x + y > 0", "x > -1 and x < 1", "x < -1 or x > 1", "x == 0"])
def test_truncation_mass_and_components_match_reference(reference, make_dist, assert_same_distribution, condition):
    from pydegas.semantics.truncate import truncate

    args = (
        ["x", "y"],
        [0.25, 0.75],
        [[-1.0, 0.5], [1.0, -0.5]],
        [[[1.0, 0.2], [0.2, 2.0]], [[2.0, -0.3], [-0.3, 1.0]]],
    )
    expected_mass, expected = reference.truncate.truncate(
        make_dist(*args, implementation=reference.shared), condition, {}, {}
    )
    actual_mass, actual = truncate(make_dist(*args), condition, {}, {})
    torch.testing.assert_close(actual_mass, expected_mass, rtol=1e-5, atol=1e-6)
    assert_same_distribution(actual, expected)


@pytest.mark.parametrize("strategy", ["classic", "ranking", "kmeans"])
def test_pruning_matches_reference_with_same_random_seed(reference, make_dist, assert_same_distribution, strategy):
    from pydegas.semantics.merge import prune

    args = (
        ["x", "y"],
        [0.1, 0.2, 0.3, 0.4],
        [[-3.0, -2.0], [-2.0, -1.0], [2.0, 1.0], [4.0, 3.0]],
        [[[1.0, 0.2], [0.2, 2.0]]] * 4,
    )
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        expected = reference.merge.prune(make_dist(*args, implementation=reference.shared), strategy, 2)
        torch.manual_seed(7)
        actual = prune(make_dist(*args), strategy, 2)
    assert_same_distribution(actual, expected, rtol=0, atol=0)


def test_parameter_gradients_match_reference(reference, assert_same_distribution):
    from pydegas.cfg.builder import from_text
    from pydegas.semantics.engine import start_soga

    program = "x = gm([1.0],[_mu],[0.5]); y = 2*x + 1; observe(x > 0);"
    old_parameter = torch.tensor(0.3, requires_grad=True)
    new_parameter = torch.tensor(0.3, requires_grad=True)
    expected = reference.engine.start_SOGA(reference.builder.produce_cfg_text(program), {"mu": old_parameter})
    actual = start_soga(from_text(program), {"mu": new_parameter})
    assert_same_distribution(actual, expected)
    old_gradient = torch.autograd.grad(expected.gm.mean().sum() + expected.gm.cov().sum(), old_parameter)[0]
    new_gradient = torch.autograd.grad(actual.gm.mean().sum() + actual.gm.cov().sum(), new_parameter)[0]
    assert torch.isfinite(new_gradient) and new_gradient.abs() > 0
    torch.testing.assert_close(new_gradient, old_gradient, rtol=1e-5, atol=1e-6)


def test_adam_loss_trace_and_final_parameters_match_reference(reference, tmp_path, monkeypatch):
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.optimize import OptimizationRun, get_loss

    # Reference optimize always appends a statistics file; contain that output.
    monkeypatch.chdir(tmp_path)
    program = "array[3] X; x = _mu; for i in range(3) { x = x + gm([1.0],[0.0],[0.1]); X[i] = x; } end for;"
    old_cfg = reference.builder.produce_cfg_text(program)
    new_cfg = from_text(program)
    reference.smoother.smooth_cfg(old_cfg)
    smooth(new_cfg)
    old_params = reference.optimization.initialize_params({"mu": 1.0})
    old_losses, _, old_count = reference.optimization.optimize(
        old_cfg,
        old_params,
        lambda d: reference.optimization.signal_error(d, target=0.5, T=3),
        n_steps=20,
        lr=0.1,
        print_progress=False,
    )
    run = OptimizationRun(
        new_cfg,
        {"mu": 1.0},
        get_loss("signal_error", target=0.5, time_steps=3),
        optimizer="Adam",
        optimizer_kwargs={"lr": 0.1},
        tolerance=None,
    )
    results = run.run(20)
    assert old_count == len(results) == 20
    torch.testing.assert_close(torch.tensor([r.loss for r in results]), torch.tensor(old_losses), rtol=1e-5, atol=1e-6)
    assert results[-1].params["mu"] == pytest.approx(old_params["mu"].item(), rel=1e-5, abs=1e-6)


def test_global_component_bound_is_an_intentional_difference(reference):
    from pydegas.cfg.builder import from_text
    from pydegas.semantics.engine import start_soga

    program = "x = gm([1.0],[0.0],[1.0]); if x > 0 { y = x; } else { y = -1*x; } end if;"
    expected = reference.engine.start_SOGA(reference.builder.produce_cfg_text(program), Kmax=1)
    actual = start_soga(from_text(program), Kmax=1)
    assert actual.gm.n_comp() == 1 < expected.gm.n_comp()
    torch.testing.assert_close(actual.gm.mean(), expected.gm.mean(), rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(actual.gm.cov(), expected.gm.cov(), rtol=1e-5, atol=1e-6)


def test_default_stopping_window_differs_from_reference(reference, tmp_path, monkeypatch):
    from pydegas.cfg.builder import from_text
    from pydegas.optimize import OptimizationRun

    monkeypatch.chdir(tmp_path)
    program = "x = _mu;"

    def loss(dist):
        return dist.gm.mean().square().sum()

    old_losses, _, _ = reference.optimization.optimize(
        reference.builder.produce_cfg_text(program),
        reference.optimization.initialize_params({"mu": 1.0}),
        loss,
        n_steps=40,
        lr=0.0,
        print_progress=False,
    )
    new = OptimizationRun(from_text(program), {"mu": 1.0}, loss, optimizer_kwargs={"lr": 0.0}).run(40)
    assert len(old_losses) == 32
    assert len(new) == 31
    assert new[-1].converged


def test_l2_uses_requested_indices_instead_of_reference_hard_coded_slice(reference, make_dist):
    from pydegas.optimize.losses import l2_distance

    args = ([f"x{i}" for i in range(10)], [1.0], [list(range(10))], [torch.eye(10).tolist()])
    trajectories = torch.zeros(1, 10)
    new = l2_distance(trajectories, [0, 2])(make_dist(*args))
    old = reference.optimization.L2_distance(trajectories, make_dist(*args, implementation=reference.shared), [0, 2])
    assert new.item() == pytest.approx(4.0)
    assert old.item() == pytest.approx(285.0)


@pytest.mark.parametrize("smoothed", [False, True])
def test_gaussian_literal_in_guard_matches_reference(reference, assert_same_distribution, smoothed):
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.semantics.engine import start_soga

    program = "x = gm([1.0],[0.0],[1.0]); observe(x + gm([1.0],[0.0],[1.0]) > 0);"
    old_cfg = reference.builder.produce_cfg_text(program)
    new_cfg = from_text(program)
    if smoothed:
        reference.smoother.smooth_cfg(old_cfg)
        smooth(new_cfg)
    expected = reference.engine.start_SOGA(old_cfg)
    actual = start_soga(new_cfg)
    assert_same_distribution(actual, expected)


def test_gaussian_guard_parameter_gradients_match_reference(reference, make_dist, assert_same_distribution):
    from pydegas.semantics.truncate import truncate

    args = (["x"], [1.0], [[0.0]], [[[1.0]]])
    condition = "x + gm([0.4,0.6],[-1.0,_mu],[0.5,_sigma]) > 0"
    old_params = {"mu": torch.tensor(0.3, requires_grad=True), "sigma": torch.tensor(0.7, requires_grad=True)}
    new_params = {name: value.detach().clone().requires_grad_() for name, value in old_params.items()}
    old_mass, old = reference.truncate.truncate(
        make_dist(*args, implementation=reference.shared), condition, {}, old_params
    )
    new_mass, new = truncate(make_dist(*args), condition, {}, new_params)
    torch.testing.assert_close(new_mass, old_mass)
    assert_same_distribution(new, old)
    old_gradients = torch.autograd.grad(old_mass + old.gm.mean().sum(), tuple(old_params.values()))
    new_gradients = torch.autograd.grad(new_mass + new.gm.mean().sum(), tuple(new_params.values()))
    for actual, expected in zip(new_gradients, old_gradients, strict=True):
        assert torch.isfinite(actual) and actual.abs() > 0
        torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)
