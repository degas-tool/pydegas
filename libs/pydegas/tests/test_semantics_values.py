"""Analytical oracles independent of the reference implementation."""

from __future__ import annotations

import math
from statistics import NormalDist

import pytest


torch = pytest.importorskip("torch")


def test_affine_assignment_transforms_mean_and_covariance(make_dist):
    from pydegas.semantics.update import update_rule

    dist = make_dist(["x", "y"], [1.0], [[1.0, 2.0]], [[[4.0, 1.0], [1.0, 9.0]]])
    actual = update_rule(dist, "x = 2*y + 3", {}, {})
    torch.testing.assert_close(actual.gm.mean(), torch.tensor([7.0, 2.0]))
    torch.testing.assert_close(actual.gm.cov(), torch.tensor([[36.0, 18.0], [18.0, 9.0]]))


def test_product_assignment_uses_gaussian_second_moments(make_dist):
    from pydegas.semantics.update import update_rule

    dist = make_dist(["x", "y", "z"], [1.0], [[0.0, 2.0, 3.0]], [[[1.0, 0.0, 0.0], [0.0, 4.0, 1.0], [0.0, 1.0, 9.0]]])
    actual = update_rule(dist, "x = y*z", {}, {})
    # E[YZ] = E[Y]E[Z] + Cov(Y,Z); Var(YZ) = 121 by Isserlis' identity.
    torch.testing.assert_close(actual.gm.mean(), torch.tensor([7.0, 2.0, 3.0]))
    torch.testing.assert_close(actual.gm.cov(), torch.tensor([[121.0, 14.0, 21.0], [14.0, 4.0, 1.0], [21.0, 1.0, 9.0]]))


def test_constant_assignment_removes_previous_covariance(make_dist):
    from pydegas.semantics.update import update_rule

    dist = make_dist(["x", "y"], [1.0], [[1.0, 2.0]], [[[4.0, 1.0], [1.0, 9.0]]])
    actual = update_rule(dist, "x = 5", {}, {})
    torch.testing.assert_close(actual.gm.mean(), torch.tensor([5.0, 2.0]))
    torch.testing.assert_close(actual.gm.cov(), torch.tensor([[0.0, 0.0], [0.0, 9.0]]))


@pytest.mark.parametrize("condition, sign", [("x > 0", 1), ("x < 0", -1)])
def test_halfspace_truncation_updates_correlated_moments(make_dist, condition, sign):
    from pydegas.semantics.truncate import truncate

    dist = make_dist(["x", "y"], [1.0], [[0.0, 0.0]], [[[1.0, 0.5], [0.5, 2.0]]])
    probability, actual = truncate(dist, condition, {}, {})
    shift = sign * math.sqrt(2 / math.pi)
    correction = 2 / math.pi
    assert probability.item() == pytest.approx(0.5, abs=1e-6)
    torch.testing.assert_close(actual.gm.mean(), torch.tensor([shift, 0.5 * shift]))
    torch.testing.assert_close(
        actual.gm.cov(),
        torch.tensor(
            [
                [1 - correction, 0.5 * (1 - correction)],
                [0.5 * (1 - correction), 2 - 0.25 * correction],
            ]
        ),
        rtol=1e-5,
        atol=1e-6,
    )


@pytest.mark.parametrize("condition, inside", [("x > -1 and x < 1", True), ("x < -1 or x > 1", False)])
def test_interval_truncation_mass_and_moments(make_dist, condition, inside):
    from pydegas.semantics.truncate import truncate

    dist = make_dist(["x"], [1.0], [[0.0]], [[[1.0]]])
    probability, actual = truncate(dist, condition, {}, {})
    normal = NormalDist()
    mass = 2 * normal.cdf(1) - 1 if inside else 2 * (1 - normal.cdf(1))
    variance = 1 + (-1 if inside else 1) * 2 * normal.pdf(1) / mass
    assert probability.item() == pytest.approx(mass, abs=1e-6)
    assert actual.gm.mean().item() == pytest.approx(0, abs=1e-6)
    assert actual.gm.cov().item() == pytest.approx(variance, abs=2e-6)


def test_general_linear_guard_matches_halfspace_formula(make_dist):
    from pydegas.semantics.truncate import truncate

    dist = make_dist(["x", "y"], [1.0], [[0.0, 0.0]], [[[1.0, 0.0], [0.0, 1.0]]])
    probability, actual = truncate(dist, "x + y > 0", {}, {})
    assert probability.item() == pytest.approx(0.5, abs=1e-6)
    torch.testing.assert_close(actual.gm.mean(), torch.full((2,), 1 / math.sqrt(math.pi)))
    torch.testing.assert_close(actual.gm.cov(), torch.eye(2) - torch.full((2, 2), 1 / math.pi), rtol=1e-5, atol=1e-6)


def test_scaled_gaussian_guard_matches_independent_halfspace_formula(make_dist):
    from pydegas.semantics.truncate import truncate

    # X + 2*Z > 0 for independent standard normals; Var(X + 2*Z) = 5.
    dist = make_dist(["x"], [1.0], [[0.0]], [[[1.0]]])
    probability, actual = truncate(dist, "x + 2*gm([1.0],[0.0],[1.0]) > 0", {}, {})
    assert probability.item() == pytest.approx(0.5, abs=1e-6)
    assert actual.gm.mean().item() == pytest.approx(math.sqrt(2 / (5 * math.pi)), abs=1e-6)
    assert actual.gm.cov().item() == pytest.approx(1 - 2 / (5 * math.pi), abs=1e-6)


def test_truncation_reweights_mixture_components(make_dist):
    from pydegas.semantics.truncate import truncate

    dist = make_dist(["x"], [0.25, 0.75], [[-1.0], [1.0]], [[[1.0]], [[1.0]]])
    probability, actual = truncate(dist, "x > 0", {}, {})
    masses = torch.tensor([0.25 * NormalDist().cdf(-1), 0.75 * NormalDist().cdf(1)])
    assert probability.item() == pytest.approx(masses.sum().item(), abs=1e-6)
    torch.testing.assert_close(actual.gm.pi.flatten(), masses / masses.sum())


def test_equality_conditioning_of_correlated_gaussian(make_dist):
    from pydegas.semantics.truncate import truncate

    dist = make_dist(["x", "y"], [1.0], [[0.0, 1.0]], [[[4.0, 2.0], [2.0, 9.0]]])
    _, actual = truncate(dist, "x == 2", {}, {})
    assert actual.gm.mean()[1].item() == pytest.approx(2.0)
    assert actual.gm.cov()[1, 1].item() == pytest.approx(8.0)
    assert actual.gm.cov()[0, 1].item() == pytest.approx(0.0)


def test_truncation_gradients_match_analytical_half_normal():
    from pydegas.mixtures.distribution import Dist
    from pydegas.mixtures.gaussian_mix import GaussianMix
    from pydegas.semantics.truncate import truncate

    mean = torch.tensor(0.0, requires_grad=True)
    dist = Dist(["x"], GaussianMix(torch.ones(1, 1), mean.reshape(1, 1), torch.ones(1, 1, 1)))
    probability, actual = truncate(dist, "x > 0", {}, {})
    mass_gradient = torch.autograd.grad(probability, mean, retain_graph=True)[0]
    mean_gradient = torch.autograd.grad(actual.gm.mean().sum(), mean)[0]
    assert mass_gradient.item() == pytest.approx(1 / math.sqrt(2 * math.pi), abs=1e-6)
    assert mean_gradient.item() == pytest.approx(1 - 2 / math.pi, abs=1e-6)
