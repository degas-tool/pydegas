"""Joint distribution over named program variables."""

from __future__ import annotations

import copy
from itertools import product
from typing import Any

import torch

from pydegas.mixtures.gaussian_mix import GaussianMix


class Dist:
    """Variable names in order (`var_list`) and joint state as a Gaussian mixture (`gm`)."""

    def __init__(self, var_list: list[str], gm: GaussianMix) -> None:
        self.var_list = var_list
        self.gm = gm

    def __str__(self) -> str:
        return f"Dist<{self.var_list},{self.gm}>"

    def __repr__(self) -> str:
        return str(self)

    def __deepcopy__(self, memo: dict) -> Dist:
        # Delegates GM tensor detachment to GaussianMix.__deepcopy__.
        new = Dist.__new__(Dist)
        memo[id(self)] = new
        new.var_list = list(self.var_list)
        new.gm = copy.deepcopy(self.gm, memo)
        return new


def extend_dist(parser: Any, dist: Dist) -> GaussianMix:
    """Extend *dist* with the auxiliary GM variables accumulated in *parser*.

    *parser* is an ``ASGMTRule`` instance carrying ``aux_pis``, ``aux_means``,
    and ``aux_covs`` populated during the ANTLR walk of the assignment expression.
    If the parser has no auxiliary variables the original GM is returned unchanged.

    Returns the extended ``GaussianMix`` (not a ``Dist`` - the caller slices it
    back to the original dimension after applying the update rule).
    """
    if not parser.aux_pis:
        return dist.gm

    old_dim = dist.gm.n_dim()
    new_dim = old_dim + len(parser.aux_pis)

    new_pis = torch.empty((0, 1))
    new_mus = torch.empty((0, new_dim))
    new_sigmas = torch.empty((0, new_dim, new_dim))

    for part in product(*[range(len(m)) for m in parser.aux_means]):
        aux_pi = torch.prod(torch.stack([parser.aux_pis[i][part[i]] for i in range(len(part))]))
        new_pis = torch.vstack([new_pis, aux_pi * dist.gm.pi])

        aux_mu = torch.hstack([parser.aux_means[i][part[i]] for i in range(len(part))])
        new_mus = torch.vstack([new_mus, torch.cat([dist.gm.mu, aux_mu.expand(dist.gm.n_comp(), len(aux_mu))], dim=1)])

        aux_sigma = torch.diag(torch.hstack([parser.aux_covs[i][part[i]] for i in range(len(part))]))
        aux_sigmas = torch.zeros((dist.gm.n_comp(), new_dim, new_dim))
        aux_sigmas[:, :old_dim, :old_dim] = dist.gm.sigma
        aux_sigmas[:, old_dim:, old_dim:] = aux_sigma
        new_sigmas = torch.vstack([new_sigmas, aux_sigmas])

    extended_gm = GaussianMix(new_pis, new_mus, new_sigmas)
    extended_gm.delete_zeros()
    return extended_gm
