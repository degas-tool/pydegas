"""Multivariate normal CDF, covariance symmetry helpers, and truncated-normal moments."""

from __future__ import annotations

import logging

import botorch.utils.probability.mvnxpb as mvn
import torch
import torch.distributions as distributions

from pydegas.mixtures.constants import TOL_ERR


logger = logging.getLogger(__name__)


def make_sym(sigma: torch.Tensor) -> torch.Tensor:
    """Make a 2D tensor symmetric by averaging with its transpose."""
    sigma = sigma.clone()
    symmetric_sigma = (sigma + sigma.T) / 2
    diff = torch.abs(symmetric_sigma - sigma)
    indices = torch.nonzero(diff > TOL_ERR, as_tuple=False)
    for i, j in indices:
        logger.warning("Substituting %s with %s", sigma[i, j].item(), symmetric_sigma[i, j].item())
    return symmetric_sigma


class TruncatedNormal:
    """Univariate truncated Normal: computes mean and variance analytically via torch."""

    def __init__(
        self,
        loc: torch.Tensor,
        scale: torch.Tensor,
        lower_bound: torch.Tensor,
        upper_bound: torch.Tensor,
    ) -> None:
        self.loc = loc
        self.scale = scale
        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

        self._standard_normal = distributions.Normal(
            torch.zeros(self.loc.shape), torch.ones(self.scale.squeeze(2).shape)
        )
        self._alpha = (self.lower_bound - self.loc) / self.scale.squeeze(2)
        self._beta = (self.upper_bound - self.loc) / self.scale.squeeze(2)
        self._phi_alpha = self._standard_normal.log_prob(self._alpha).exp()
        self._phi_beta = self._standard_normal.log_prob(self._beta).exp()
        self.norm_const = self._standard_normal.cdf(self._beta) - self._standard_normal.cdf(self._alpha)

    def mean(self) -> torch.Tensor:
        return self.loc + self.scale.squeeze(2) * (self._phi_alpha - self._phi_beta) / self.norm_const

    def var(self) -> torch.Tensor:
        return (
            self.scale.squeeze(2) ** 2
            * (
                torch.tensor(1.0)
                - (self._beta * self._phi_beta - self._alpha * self._phi_alpha) / self.norm_const
                - ((self._phi_alpha - self._phi_beta) / self.norm_const) ** 2
            )
        ).unsqueeze(2)


def mvncdf(x: torch.Tensor, mean: torch.Tensor, cov: torch.Tensor) -> torch.Tensor:
    """CDF of multivariate normal at x (upper orthant style bounds), batch over leading dim of x."""
    if x.dim() == 1:
        x = x.unsqueeze(0)
    batch_size = x.shape[0]
    dim = x.shape[1]
    bounds = torch.stack(
        [torch.tensor([[-torch.inf, x[i, j] - mean[j]] for j in range(dim)]) for i in range(batch_size)]
    )
    res = torch.zeros(batch_size)
    for i in range(batch_size):
        result = torch.exp(mvn.MVNXPB(covariance_matrix=cov, bounds=bounds[i]).solve())
        if result.isnan():
            cov = make_sym(cov)
            result = torch.exp(mvn.MVNXPB(covariance_matrix=cov, bounds=bounds[i]).solve())
        res[i] = result
    return res
