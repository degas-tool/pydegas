"""Gaussian mixture representation."""

from __future__ import annotations

import logging

import torch
import torch.distributions as distributions
from torch.distributions import Categorical, MultivariateNormal

from pydegas.mixtures.constants import TOL_PROB
from pydegas.mixtures.numerics import make_sym, mvncdf


logger = logging.getLogger(__name__)


class GaussianMix:
    """Mixture of multivariate Gaussians: pi (c,1), mu (c,d), sigma (c,d,d)."""

    def __init__(self, pi: torch.Tensor, mu: torch.Tensor, sigma: torch.Tensor) -> None:
        self.pi = pi
        self.mu = mu
        self.sigma = sigma

    def n_comp(self) -> int:
        return self.pi.shape[0]

    def n_dim(self) -> int:
        return self.mu.shape[1]

    def __repr__(self) -> str:
        return "pi: " + str(self.pi) + "\nmu: " + str(self.mu) + "\nsigma: " + str(self.sigma)

    def __deepcopy__(self, memo: dict) -> GaussianMix:
        # Tensors carry autograd history during optimization; .clone().detach()
        # gives a leaf copy that is safe to deepcopy / serialize.
        new = GaussianMix.__new__(GaussianMix)
        memo[id(self)] = new
        new.pi = self.pi.clone().detach()
        new.mu = self.mu.clone().detach()
        new.sigma = self.sigma.clone().detach()
        return new

    def comp(self, k: int) -> GaussianMix:
        return GaussianMix(
            torch.tensor([[1.0]]),
            torch.clone(self.mu[k, :].unsqueeze(0)),
            torch.clone(self.sigma[k, :, :].unsqueeze(0)),
        )

    def comp_pdf(self, x: torch.Tensor, k: int) -> torch.Tensor:
        if self.n_dim() > 1:
            try:
                return torch.exp(MultivariateNormal(self.mu[k], covariance_matrix=self.sigma[k]).log_prob(x))
            except ValueError:
                sigma = self.sigma[k]
                eigs, _ = torch.linalg.eigh(sigma)
                is_psd = torch.all(eigs > 0)
                is_sym = torch.all(sigma == sigma.T)
                if not is_psd:
                    logger.warning("matrix k=%d is not psd! eigs: %s", k, eigs)
                    logger.warning("matrix k=%d is not psd! sigma: %s", k, sigma)
                    raise
                if not is_sym:
                    self.sigma[k] = make_sym(self.sigma[k])
                return torch.exp(MultivariateNormal(self.mu[k], covariance_matrix=self.sigma[k]).log_prob(x))
        return torch.exp(distributions.Normal(self.mu[k], torch.sqrt(self.sigma[k])).log_prob(x)).reshape(x.shape)

    def marg_comp_log_pdf(self, x: torch.Tensor, k: int, idx: list[int] | int) -> torch.Tensor:
        if isinstance(idx, list):
            cov_submatrix = torch.clone(self.sigma[k][torch.tensor(idx).unsqueeze(1), torch.tensor(idx)])
            try:
                return MultivariateNormal(self.mu[k][idx], covariance_matrix=cov_submatrix).log_prob(x)
            except ValueError:
                eigs, _ = torch.linalg.eigh(cov_submatrix)
                if not torch.all(eigs > 0):
                    logger.warning("matrix k=%d is not psd! eigs: %s", k, eigs)
                    logger.warning("matrix k=%d is not psd! cov_submatrix: %s", k, cov_submatrix)
                    raise
                if not torch.all(cov_submatrix == cov_submatrix.T):
                    logger.warning("matrix k=%d is not symmetric! cov_submatrix: %s", k, cov_submatrix)
                    cov_submatrix = make_sym(cov_submatrix)
                    self.sigma[k][torch.tensor(idx).unsqueeze(1), torch.tensor(idx)] = cov_submatrix
                return MultivariateNormal(self.mu[k][idx], covariance_matrix=cov_submatrix).log_prob(x)
        return distributions.Normal(self.mu[k][idx], torch.sqrt(self.sigma[k][idx, idx])).log_prob(x)

    def marg_comp_pdf(self, x: torch.Tensor, k: int, idx: list[int] | int) -> torch.Tensor:
        return torch.exp(self.marg_comp_log_pdf(x, k, idx))

    def pdf(self, x: torch.Tensor) -> torch.Tensor:
        comp_pdfs = torch.stack([self.comp_pdf(x, k) for k in range(self.n_comp())], dim=1)
        return torch.matmul(comp_pdfs.squeeze(2), self.pi.view(-1, 1))

    def marg_pdf(self, x: torch.Tensor, idx: list[int] | int) -> torch.Tensor:
        comp_pdfs = torch.stack([self.marg_comp_pdf(x, k, idx) for k in range(self.n_comp())], dim=1)
        return torch.matmul(comp_pdfs, self.pi)

    def marg_log_pdf(self, x: torch.Tensor, idx: list[int] | int) -> torch.Tensor:
        """Log-density of the mixture marginal, entirely in log-space.

        logsumexp over components keeps densities far below float64 range
        finite, where log(marg_pdf(x)) would underflow to -inf.
        """
        log_pdfs = torch.stack([self.marg_comp_log_pdf(x, k, idx) for k in range(self.n_comp())], dim=1)
        return torch.logsumexp(log_pdfs + torch.log(self.pi).view(1, -1), dim=1)

    def comp_cdf(self, x: torch.Tensor, k: int) -> torch.Tensor:
        if self.n_dim() > 1:
            return mvncdf(x, self.mu[k], self.sigma[k])
        return distributions.Normal(self.mu[k], torch.sqrt(self.sigma[k])).cdf(x)

    def marg_comp_cdf(self, x: torch.Tensor, k: int, idx: list[int] | int) -> torch.Tensor:
        if isinstance(idx, list):
            cov_submatrix = torch.clone(self.sigma[k][torch.tensor(idx).unsqueeze(1), torch.tensor(idx)])
            return mvncdf(x, self.mu[k][idx], cov_submatrix)
        return distributions.Normal(self.mu[k][idx], torch.sqrt(self.sigma[k][idx, idx])).cdf(x)

    def cdf(self, x: torch.Tensor) -> torch.Tensor:
        comp_cdfs = torch.stack([self.comp_cdf(x, k) for k in range(self.n_comp())], dim=1)
        return torch.matmul(comp_cdfs, self.pi.view(-1, 1))

    def marg_cdf(self, x: torch.Tensor, idx: list[int] | int) -> torch.Tensor:
        comp_cdfs = torch.stack([self.marg_comp_cdf(x, k, idx) for k in range(self.n_comp())], dim=1)
        return torch.matmul(comp_cdfs, self.pi.view(-1, 1))

    def mean(self) -> torch.Tensor:
        return torch.sum(self.pi * self.mu, dim=0)

    def cov(self) -> torch.Tensor:
        pi = self.pi.view(-1, 1, 1)
        v = self.mu - self.mean()
        return (pi * self.sigma).sum(dim=0) + torch.mm(v.t(), self.pi * v)

    def delete_zeros(self) -> None:
        indexes = torch.where(self.pi >= TOL_PROB)
        self.pi = self.pi[indexes].reshape(-1, 1)
        self.pi = self.pi / torch.sum(self.pi)
        self.mu = self.mu[indexes[0], :]
        self.sigma = self.sigma[indexes[0], :, :]

    def sample(self, n_samples: int = 1) -> torch.Tensor:
        weights = self.pi.squeeze()
        mus = self.mu.squeeze()
        covs = self.sigma.squeeze()
        _, d = mus.shape
        categorical = Categorical(weights)
        component_ids = categorical.sample((n_samples,))
        samples = []
        for k in component_ids:
            dist = MultivariateNormal(mus[k], covs[k] + 1e-6 * torch.eye(d))
            samples.append(dist.sample())
        return torch.stack(samples)
