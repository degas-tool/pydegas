from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")


@pytest.fixture
def mixture(make_dist):
    return make_dist(
        ["x", "y"],
        [0.1, 0.2, 0.3, 0.4],
        [[-3.0, -2.0], [-2.0, -1.0], [2.0, 1.0], [4.0, 3.0]],
        [[[1.0, 0.2], [0.2, 2.0]]] * 4,
    )


def test_merge_preserves_path_mass_and_weighted_moments(make_dist):
    from pydegas.semantics.merge import merge

    left = make_dist(["x"], [1.0], [[-1.0]], [[[2.0]]])
    right = make_dist(["x"], [1.0], [[3.0]], [[[4.0]]])
    probability, actual = merge([(torch.tensor(0.2), left), (torch.tensor(0.6), right)])
    assert probability.item() == pytest.approx(0.8)
    torch.testing.assert_close(actual.gm.pi.flatten(), torch.tensor([0.25, 0.75]))
    assert actual.gm.mean().item() == pytest.approx(2.0)
    assert actual.gm.cov().item() == pytest.approx(6.5)


@pytest.mark.parametrize("strategy", ["classic", "ranking", "kmeans"])
def test_pruning_caps_components_and_normalizes_weights(mixture, strategy):
    from pydegas.semantics.merge import prune

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        actual = prune(mixture, strategy, 2)
    assert actual.gm.n_comp() <= 2
    assert actual.gm.pi.sum().item() == pytest.approx(1.0)
    assert (actual.gm.pi >= 0).all()
    assert torch.isfinite(actual.gm.mu).all()
    assert torch.isfinite(actual.gm.sigma).all()
    torch.testing.assert_close(actual.gm.sigma, actual.gm.sigma.transpose(-1, -2))
    assert (torch.linalg.eigvalsh(actual.gm.sigma) >= -1e-6).all()


@pytest.mark.parametrize("strategy", ["classic", "kmeans"])
@pytest.mark.parametrize("bound", [1, 2, 3])
def test_moment_matching_pruning_preserves_mean_and_covariance(mixture, strategy, bound):
    from pydegas.semantics.merge import prune

    mean, covariance = mixture.gm.mean().clone(), mixture.gm.cov().clone()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(7)
        actual = prune(mixture, strategy, bound)
    torch.testing.assert_close(actual.gm.mean(), mean, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(actual.gm.cov(), covariance, rtol=1e-5, atol=1e-6)


def test_ranking_keeps_heaviest_components(mixture):
    from pydegas.semantics.merge import prune

    actual = prune(mixture, "ranking", 2)
    torch.testing.assert_close(actual.gm.mu, torch.tensor([[4.0, 3.0], [2.0, 1.0]]))
    torch.testing.assert_close(actual.gm.pi.flatten(), torch.tensor([4 / 7, 3 / 7]))


@pytest.mark.parametrize("strategy", ["classic", "ranking", "kmeans"])
def test_pruning_below_bound_leaves_distribution_unchanged(mixture, strategy):
    from pydegas.semantics.merge import prune

    original = [getattr(mixture.gm, name).clone() for name in ("pi", "mu", "sigma")]
    actual = prune(mixture, strategy, 4)
    for name, expected in zip(("pi", "mu", "sigma"), original, strict=True):
        torch.testing.assert_close(getattr(actual.gm, name), expected, rtol=0, atol=0)
