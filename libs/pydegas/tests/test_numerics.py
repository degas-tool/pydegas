from __future__ import annotations

import math
from statistics import NormalDist

import pytest


torch = pytest.importorskip("torch")


def test_mixture_mean_and_total_covariance(make_dist):
    dist = make_dist(
        ["x", "y"], [0.25, 0.75], [[0.0, 1.0], [4.0, -1.0]], [[[1.0, 0.2], [0.2, 2.0]], [[2.0, -0.4], [-0.4, 1.0]]]
    )
    torch.testing.assert_close(dist.gm.mean(), torch.tensor([3.0, -0.5]))
    torch.testing.assert_close(dist.gm.cov(), torch.tensor([[4.75, -1.75], [-1.75, 2.0]]))


@pytest.mark.parametrize("rho", [-0.6, 0.0, 0.6])
def test_bivariate_cdf_at_origin_matches_arcsine_identity(rho):
    from pydegas.mixtures.numerics import mvncdf

    actual = mvncdf(torch.zeros(2), torch.zeros(2), torch.tensor([[1.0, rho], [rho, 1.0]]))
    expected = 0.25 + math.asin(rho) / (2 * math.pi)
    assert actual.shape == (1,)
    assert actual.item() == pytest.approx(expected, abs=2e-6)


def test_multivariate_cdf_batch_matches_independent_normal_product():
    from pydegas.mixtures.numerics import mvncdf

    points = torch.tensor([[-1.0, 0.0, 2.0], [0.5, 2.0, -1.0]])
    means = torch.tensor([0.5, -0.5, 1.0])
    scales = [1.0, 2.0, 0.5]
    actual = mvncdf(points, means, torch.diag(torch.tensor(scales).square()))
    expected = torch.tensor(
        [
            math.prod(
                NormalDist(float(mean), scale).cdf(float(x)) for x, mean, scale in zip(row, means, scales, strict=True)
            )
            for row in points
        ]
    )
    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-7)


def test_marginal_density_and_cdf_include_mixture_weights(make_dist):
    dist = make_dist(
        ["x", "y"], [0.25, 0.75], [[0.0, 1.0], [4.0, -1.0]], [[[1.0, 0.2], [0.2, 2.0]], [[2.0, -0.4], [-0.4, 1.0]]]
    )
    points = torch.tensor([[-1.0], [0.0], [2.0]])
    normals = [NormalDist(1.0, math.sqrt(2)), NormalDist(-1.0, 1.0)]
    density = [sum(w * n.pdf(float(x)) for w, n in zip([0.25, 0.75], normals, strict=True)) for x in points[:, 0]]
    cdf = [sum(w * n.cdf(float(x)) for w, n in zip([0.25, 0.75], normals, strict=True)) for x in points[:, 0]]
    torch.testing.assert_close(dist.gm.marg_pdf(points, [1]).flatten(), torch.tensor(density))
    torch.testing.assert_close(dist.gm.marg_cdf(points, [1]).flatten(), torch.tensor(cdf), rtol=1e-5, atol=1e-6)


def test_nll_stays_finite_in_extreme_tail(make_dist):
    from pydegas.optimize.losses import neg_log_likelihood

    dist = make_dist(["x", "y"], [1.0], [[0.0, 0.0]], [[[1.0, 0.0], [0.0, 1.0]]])
    actual = neg_log_likelihood(torch.tensor([[60.0, 60.0]]), [0, 1])(dist)
    assert actual.item() == pytest.approx(3600 + math.log(2 * math.pi), abs=3e-4)
