"""Tests for the DeGASLoss DSL compiler.

Parameter names in loss definitions must not clash with grammar keywords
(dist, traj_set, index_list, scalar, int, sum, log, etc.).
Use short aliases: d: dist, ts: traj_set, idx: index_list, etc.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def simple_dist():
    """2-variable, 2-component Gaussian mixture."""
    torch = pytest.importorskip("torch")
    from pydegas.mixtures.distribution import Dist
    from pydegas.mixtures.gaussian_mix import GaussianMix

    pi = torch.tensor([[0.6], [0.4]])
    mu = torch.tensor([[0.0, 1.0], [2.0, 3.0]])
    sigma = torch.stack([torch.eye(2) * 0.5, torch.eye(2) * 1.0])
    return Dist(["x", "y"], GaussianMix(pi, mu, sigma))


@pytest.fixture
def traj_and_idx():
    torch = pytest.importorskip("torch")
    traj = torch.tensor([[0.1, 0.9], [1.8, 2.2], [-0.3, 1.1]])
    idx = [0, 1]
    return traj, idx


def test_validate_loss_returns_empty_for_valid_source() -> None:
    from pydegas.optimize.dsl import validate_loss

    # d is the dist param; keywords like dist/traj_set cannot be param names.
    source = """
    loss my_loss(d: dist) =
        - sum( log( d.mean() ) )
    """
    assert validate_loss(source) == []


def test_validate_loss_returns_errors_for_bad_syntax() -> None:
    from pydegas.optimize.dsl import validate_loss

    errors = validate_loss("loss = ??? garbage {{")
    assert len(errors) > 0


def test_validate_loss_returns_errors_for_missing_equals() -> None:
    from pydegas.optimize.dsl import validate_loss

    errors = validate_loss("loss foo(d: dist) sum(d.mean())")
    assert len(errors) > 0


def test_compile_loss_raises_on_syntax_error() -> None:
    from pydegas.exceptions import LossCompileError
    from pydegas.optimize.dsl import compile_loss

    with pytest.raises(LossCompileError, match="syntax errors"):
        compile_loss("loss ??? = bad;")


def test_compile_loss_raises_if_no_dist_param() -> None:
    from pydegas.exceptions import LossCompileError
    from pydegas.optimize.dsl import compile_loss

    source = "loss bad(x: scalar) = x"
    with pytest.raises(LossCompileError, match="no parameter annotated as 'dist'"):
        compile_loss(source, x=1.0)


def test_compile_loss_raises_if_binding_missing() -> None:
    from pydegas.exceptions import LossCompileError
    from pydegas.optimize.dsl import compile_loss

    source = "loss bad(d: dist, target: scalar) = sum( d.mean() )"
    with pytest.raises(LossCompileError, match="requires bindings for"):
        compile_loss(source)  # target not supplied


def test_compile_loss_raises_on_undefined_variable_at_runtime(simple_dist) -> None:
    from pydegas.exceptions import LossCompileError
    from pydegas.optimize.dsl import compile_loss

    source = "loss bad(d: dist) = undefined_var"
    fn = compile_loss(source)
    with pytest.raises(LossCompileError, match="Undefined variable"):
        fn(simple_dist)


def test_compile_loss_returns_scalar_tensor(simple_dist) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    source = "loss const_loss(d: dist) = 42.0"
    fn = compile_loss(source)
    result = fn(simple_dist)
    assert result.shape == torch.Size([])
    assert result.item() == pytest.approx(42.0)


def test_compile_loss_arithmetic(simple_dist) -> None:
    from pydegas.optimize.dsl import compile_loss

    source = "loss arith(d: dist) = 2.0 + 3.0 * 4.0 - 1.0"
    fn = compile_loss(source)
    assert fn(simple_dist).item() == pytest.approx(13.0)


def test_compile_loss_power(simple_dist) -> None:
    from pydegas.optimize.dsl import compile_loss

    source = "loss pw(d: dist) = 2.0 ^ 3.0"
    fn = compile_loss(source)
    assert fn(simple_dist).item() == pytest.approx(8.0)


def test_compile_loss_unary_neg(simple_dist) -> None:
    from pydegas.optimize.dsl import compile_loss

    source = "loss neg(d: dist) = - 5.0"
    fn = compile_loss(source)
    assert fn(simple_dist).item() == pytest.approx(-5.0)


def test_compile_loss_math_functions(simple_dist) -> None:
    from pydegas.optimize.dsl import compile_loss

    source = "loss mf(d: dist) = log( exp( sqrt( abs( -4.0 ) ) ) )"
    fn = compile_loss(source)
    # sqrt(4) = 2, exp(2), log(exp(2)) = 2
    assert fn(simple_dist).item() == pytest.approx(2.0, rel=1e-5)


def test_compile_loss_local_assignment(simple_dist) -> None:
    from pydegas.optimize.dsl import compile_loss

    source = """
    loss with_local(d: dist) =
        a = 3.0;
        b = a * 2.0;
        b
    """
    fn = compile_loss(source)
    assert fn(simple_dist).item() == pytest.approx(6.0)


def test_compile_loss_dist_mean(simple_dist) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    source = "loss mean_sum(d: dist) = sum( d.mean() )"
    fn = compile_loss(source)
    expected = torch.sum(simple_dist.gm.mean())
    assert fn(simple_dist).item() == pytest.approx(expected.item(), rel=1e-5)


def test_compile_loss_dist_mean_indexed(simple_dist) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    source = "loss mean_idx(d: dist) = sum( d.mean[range(0, 2)] )"
    fn = compile_loss(source)
    expected = torch.sum(simple_dist.gm.mean()[[0, 1]])
    assert fn(simple_dist).item() == pytest.approx(expected.item(), rel=1e-5)


def test_compile_loss_dist_var(simple_dist) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    source = "loss var_sum(d: dist) = sum( d.var() )"
    fn = compile_loss(source)
    expected = torch.sum(torch.diag(simple_dist.gm.cov()))
    assert fn(simple_dist).item() == pytest.approx(expected.item(), rel=1e-5)


def test_compile_loss_neg_log_likelihood_matches_builtin(simple_dist, traj_and_idx) -> None:
    pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss
    from pydegas.optimize.losses import neg_log_likelihood

    traj, idx = traj_and_idx

    # traj_set is a keyword, so we use ts; marg_pdf requires a named variable
    # for the sliced data, not an inline expression.
    source = """
    loss neg_log_likelihood(ts: traj_set, d: dist, idx: index_list) =
        sliced = ts[:, idx];
        - sum( log( d.marg_pdf(sliced, idx) ) )
    """
    dsl_fn = compile_loss(source, ts=traj, idx=idx)
    builtin_fn = neg_log_likelihood(traj, idx)

    assert dsl_fn(simple_dist).item() == pytest.approx(builtin_fn(simple_dist).item(), rel=1e-5)


def test_compile_loss_l2_distance_matches_builtin(simple_dist, traj_and_idx) -> None:
    pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss
    from pydegas.optimize.losses import l2_distance

    traj, idx = traj_and_idx

    source = """
    loss l2_distance(ts: traj_set, d: dist, idx: index_list) =
        sliced = ts[:, idx];
        sum( (sliced - d.mean[idx]) ^ 2 )
    """
    dsl_fn = compile_loss(source, ts=traj, idx=idx)
    builtin_fn = l2_distance(traj, idx)

    assert dsl_fn(simple_dist).item() == pytest.approx(builtin_fn(simple_dist).item(), rel=1e-5)


def test_compile_loss_signal_error_matches_builtin(simple_dist) -> None:
    import torch

    pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    target = 1.5

    # Uses range(0, 2) to select both variables in the 2-var dist.
    source = """
    loss signal_error(d: dist, target: scalar) =
        sum( (d.mean[range(0, 2)] - ones(range(0, 2)) * target) ^ 2 )
    """
    dsl_fn = compile_loss(source, target=torch.tensor(target))

    mean = simple_dist.gm.mean()[[0, 1]]
    expected = torch.sum((mean - target) ** 2).item()

    assert dsl_fn(simple_dist).item() == pytest.approx(expected, rel=1e-5)


def test_compile_loss_index_literal(simple_dist) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    source = "loss idx_lit(d: dist) = sum( d.mean[[0, 1]] )"
    fn = compile_loss(source)
    expected = torch.sum(simple_dist.gm.mean()[[0, 1]])
    assert fn(simple_dist).item() == pytest.approx(expected.item(), rel=1e-5)


def test_compile_loss_index_var_binding(simple_dist) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.optimize.dsl import compile_loss

    source = "loss idx_var(d: dist, idx: index_list) = sum( d.mean[idx] )"
    fn = compile_loss(source, idx=[0, 1])
    expected = torch.sum(simple_dist.gm.mean()[[0, 1]])
    assert fn(simple_dist).item() == pytest.approx(expected.item(), rel=1e-5)


def test_compile_loss_returned_function_name_matches_definition(simple_dist) -> None:
    from pydegas.optimize.dsl import compile_loss

    source = "loss my_custom_loss(d: dist) = sum( d.mean() )"
    fn = compile_loss(source)
    assert fn.__name__ == "my_custom_loss"
