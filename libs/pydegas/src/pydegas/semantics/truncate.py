"""
This module implements truncation semantics for conditioning and observation in SOGA,
returning the normalized mass and conditioned distribution after applying a boolean condition.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from typing import Any

import torch
import torch.distributions as distributions
from antlr4 import CommonTokenStream, InputStream, ParseTreeWalker

from pydegas.exceptions import InvalidConstraintError
from pydegas.mixtures.constants import INFTY, SMOOTH_EPS, TOL_PROB
from pydegas.mixtures.distribution import Dist, extend_dist
from pydegas.mixtures.gaussian_mix import GaussianMix
from pydegas.mixtures.numerics import TruncatedNormal
from pydegas.parse.trunc import TRUNCLexer, TRUNCListener, TRUNCParser
from pydegas.parse.values import unpack_gm_list


logger = logging.getLogger(__name__)

TRUNC_TREE_CACHE: dict[str, Any] = {}

# Weight normalisation


def _normalize_weights(weights: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    """Normalize *weights* and return ``(normalizer, normalized_weights)``.

    If the total mass is below ``TOL_PROB`` the weights are returned unchanged
    and *normalizer* is ``0.0``.
    """
    normalizer = torch.sum(weights)
    if normalizer > TOL_PROB:
        return normalizer, weights / normalizer
    return torch.tensor(0.0), weights


# Truncation functions


def _and_func(rule: TruncRule, distribution: Dist) -> tuple[torch.Tensor, Dist]:
    """Truncate to ``lower_bound < var < upper_bound`` (smoothed equality band).

    This function only works for "var > lower and var < upper" so there is no need
    to extend the distribution or change variables.
    """
    inequality_index = int(torch.where(rule.coefficients != 0)[0][0])
    lower = rule.lower_bound
    upper = rule.upper_bound

    # STEP 1: create the hyper-rectangle to integrate on
    lower_bounds = torch.ones(len(rule.coefficients)) * (-INFTY)
    upper_bounds = torch.ones(len(rule.coefficients)) * INFTY
    lower_bounds[inequality_index] = lower
    upper_bounds[inequality_index] = upper

    # STEP 2: compute moments; surviving_indices are components with non-zero probability
    component_probs, truncated_means, truncated_covariances, surviving_indices = _compute_moments(
        distribution.gm.mu, distribution.gm.sigma, lower_bounds, upper_bounds, inequality_index
    )
    if len(surviving_indices) == 0:
        return torch.tensor(0.0), distribution

    # STEP 3: weight normalisation
    new_weights = distribution.gm.pi[surviving_indices] * component_probs.view(-1, 1)
    normalizer, normalized_weights = _normalize_weights(new_weights)
    return normalizer, Dist(
        distribution.var_list, GaussianMix(normalized_weights, truncated_means, truncated_covariances)
    )


def _or_func(rule: TruncRule, distribution: Dist) -> tuple[torch.Tensor, Dist]:
    """Truncate to ``var < upper_bound or var > lower_bound`` (smoothed inequality band)."""
    variable_index = int(torch.where(rule.coefficients != 0)[0][0])
    variable_name = distribution.var_list[variable_index]

    condition_lower = f"{variable_name} < {rule.upper_bound:.10f}"
    condition_upper = f"{variable_name} > {rule.lower_bound:.10f}"

    probability_lower, dist_lower = truncate(distribution, condition_lower, {}, {})
    probability_upper, dist_upper = truncate(distribution, condition_upper, {}, {})

    combined_weights = torch.vstack([probability_lower * dist_lower.gm.pi, probability_upper * dist_upper.gm.pi])
    combined_means = torch.vstack([dist_lower.gm.mu, dist_upper.gm.mu])
    combined_covariances = torch.vstack([dist_lower.gm.sigma, dist_upper.gm.sigma])

    normalizer, normalized_weights = _normalize_weights(combined_weights)
    return normalizer, Dist(
        distribution.var_list, GaussianMix(normalized_weights, combined_means, combined_covariances)
    )


def _ineq_func(rule: TruncRule, distribution: Dist) -> tuple[torch.Tensor, Dist]:
    """Truncate by a general linear inequality ``a·x ≤ c`` or ``a·x ≥ c``."""
    inequality_coefficients = rule.coefficients
    inequality_constant = rule.constant

    # creates extended distribution
    extended_gm = extend_dist(rule, distribution)

    # here there was a part to deal with deltas, but we removed it because in torch everything is differentiable

    # STEP 1: change variables
    norm = torch.linalg.norm(inequality_coefficients)
    inequality_coefficients = inequality_coefficients / norm
    inequality_constant = inequality_constant / norm
    A = _find_basis(inequality_coefficients)

    rotated_means = torch.matmul(A, extended_gm.mu.unsqueeze(2)).squeeze(2)
    rotated_covariances = torch.matmul(torch.matmul(A, extended_gm.sigma), A.t())

    # STEP 2: create the hyper-rectangle to integrate on
    lower_bounds = torch.ones(len(inequality_coefficients)) * (-INFTY)
    upper_bounds = torch.ones(len(inequality_coefficients)) * INFTY
    if rule.operator in (">", ">="):
        lower_bounds[0] = inequality_constant
    if rule.operator in ("<", "<="):
        upper_bounds[0] = inequality_constant

    # STEP 3: compute moments; surviving_indices are components with non-zero probability
    component_probs, truncated_rotated_means, truncated_rotated_covariances, surviving_indices = _compute_moments(
        rotated_means, rotated_covariances, lower_bounds, upper_bounds
    )
    if len(surviving_indices) == 0:
        return torch.tensor(0.0), distribution

    # STEP 4: go back to original coordinates
    old_dim = len(distribution.var_list)
    A_inv = torch.linalg.inv(A)
    truncated_means = torch.matmul(A_inv, truncated_rotated_means.unsqueeze(2)).squeeze(2)[:, :old_dim]
    truncated_covariances = torch.matmul(torch.matmul(A_inv, truncated_rotated_covariances), A_inv.t())[
        :, :old_dim, :old_dim
    ]

    # STEP 5: weight normalisation
    new_weights = extended_gm.pi[surviving_indices] * component_probs.view(-1, 1)
    normalizer, normalized_weights = _normalize_weights(new_weights)
    return normalizer, Dist(
        distribution.var_list, GaussianMix(normalized_weights, truncated_means, truncated_covariances)
    )


def _eq_func(rule: TruncRule, distribution: Dist) -> tuple[torch.Tensor, Dist]:
    """Truncate by an equality observation ``var == c`` (Bayesian conditioning)."""
    equality_coefficients = rule.coefficients
    equality_constant = rule.constant

    # here there was a part to deal with deltas, but we removed it because in torch everything is differentiable

    # observed and non-observed variables
    observed_index = int(list(torch.where(equality_coefficients != 0))[0][0])
    unobserved_mask = torch.arange(distribution.gm.n_dim()) != observed_index

    # computes conditional cov and mean
    conditional_covariance = torch.clone(distribution.gm.sigma[:, unobserved_mask, :][:, :, unobserved_mask])
    conditional_covariance = conditional_covariance - (
        1 / distribution.gm.sigma[:, observed_index, observed_index]
    ).view(-1, 1, 1) * torch.bmm(
        distribution.gm.sigma[:, unobserved_mask, observed_index].unsqueeze(2),
        distribution.gm.sigma[:, observed_index, unobserved_mask].unsqueeze(1),
    )
    conditional_mean = (
        distribution.gm.mu[:, unobserved_mask]
        + (1 / distribution.gm.sigma[:, observed_index, observed_index]).view(-1, 1)
        * (equality_constant - distribution.gm.mu[:, observed_index]).view(distribution.gm.sigma.shape[0], 1)
        * distribution.gm.sigma[:, unobserved_mask, observed_index]
    )

    # if conditioned matrix is Null, it is equivalent to observing a single independent component
    all_zeros = torch.all(conditional_covariance == 0, dim=(1, 2))
    new_weights = torch.where(all_zeros, 0.0, distribution.gm.pi.flatten()).view(-1, 1)
    # normalizes weights
    normalizer, normalized_weights = _normalize_weights(new_weights)

    # extends cond mu and sigma with values for the observed variable (puts small variance on the observed variable)
    n_unobserved = conditional_mean.shape[1]
    new_full_mean = torch.zeros((conditional_mean.shape[0], n_unobserved + 1))
    new_full_mean[:, :observed_index] = conditional_mean[:, :observed_index]
    new_full_mean[:, observed_index] = torch.ones(conditional_mean.shape[0]) * equality_constant
    new_full_mean[:, observed_index + 1 :] = conditional_mean[:, observed_index:]

    keep_mask = torch.ones(n_unobserved + 1, dtype=torch.bool)
    keep_mask[observed_index] = False
    new_full_covariance = torch.zeros((conditional_covariance.shape[0], n_unobserved + 1, n_unobserved + 1))
    block = new_full_covariance[:, keep_mask, :]
    block[:, :, keep_mask] = conditional_covariance
    new_full_covariance[:, keep_mask, :] = block
    new_full_covariance[:, observed_index, observed_index] = torch.ones(conditional_covariance.shape[0]) * SMOOTH_EPS

    return normalizer, Dist(distribution.var_list, GaussianMix(normalized_weights, new_full_mean, new_full_covariance))


class TruncRule(TRUNCListener):
    """ANTLR listener that walks the TRUNC parse tree of a condition string."""

    def __init__(
        self,
        variables: list[str],
        data: dict[str, Any],
        parameters: dict[str, torch.Tensor],
    ) -> None:
        self.variables = variables
        self.data = data
        self.parameters = parameters

        self.operator: str | None = None
        self.coefficients = torch.zeros(len(variables))
        self.constant = torch.tensor(0.0)

        self.aux_pis: list[torch.Tensor] = []
        self.aux_means: list[torch.Tensor] = []
        self.aux_covs: list[torch.Tensor] = []

        self.lower_bound: torch.Tensor | None = None
        self.upper_bound: torch.Tensor | None = None
        self.truncate_func: Callable[[Dist], tuple[torch.Tensor, Dist]] | None = None
        self._current_sign = torch.tensor(1.0)

    def _parse_constant(self, ctx: Any) -> torch.Tensor:
        """Parse a constant from a ``const`` or ``pos_const`` context node."""
        if isinstance(ctx, TRUNCParser.ConstContext):
            if ctx.num() is not None:
                return torch.tensor(float(ctx.num().getText()))
            if ctx.idd() is not None:
                return ctx.idd().getValue(self.data)
            if ctx.par() is not None:
                return ctx.par().getValue(self.parameters)
        if isinstance(ctx, TRUNCParser.Pos_constContext):
            if ctx.POSNUM() is not None:
                return torch.tensor(float(ctx.POSNUM().getText()))
            if ctx.idd() is not None:
                return ctx.idd().getValue(self.data)
            if ctx.par() is not None:
                return ctx.par().getValue(self.parameters)
        raise ValueError(f"Cannot parse constant from context: {ctx!r}")

    def _parse_constant_expression(self, ctx: Any) -> torch.Tensor:
        """Parse an arithmetic expression over constants."""
        value = self._parse_constant(ctx.const())
        if ctx.pos_const():
            for operator, pos_const in zip(ctx.aop(), ctx.pos_const(), strict=False):
                operand = self._parse_constant(pos_const)
                op_text = operator.getText()
                if op_text == "+":
                    value = value + operand
                elif op_text == "-":
                    value = value - operand
                elif op_text == "*":
                    value = value * operand
        return value

    def _collect_gm_term(self, term: Any) -> None:
        """Append weights, means, and variances of a ``gm(π, μ, σ)`` term."""
        gm_ctx = term.gm()
        self.aux_pis.append(unpack_gm_list(gm_ctx.list_(0), self.parameters))
        self.aux_means.append(unpack_gm_list(gm_ctx.list_(1), self.parameters))
        self.aux_covs.append(unpack_gm_list(gm_ctx.list_(2), self.parameters).square())

    def _parse_monomial(self, ctx: Any, operator_ctx: Any = None) -> None:
        """Parse a monomial term and accumulate its coefficient."""
        if ctx.var().gm() is None:
            variable_name = ctx.var()._getText(self.data)
            coefficient = torch.tensor(1.0)
            if ctx.const():
                coefficient = self._parse_constant(ctx.const())
            if operator_ctx and operator_ctx.SUB():
                coefficient = -coefficient
            variable_index = self.variables.index(variable_name)
            self.coefficients[variable_index] = coefficient
        else:
            self._collect_gm_term(ctx.var())
            coefficient = torch.tensor(1.0)
            if ctx.const():
                coefficient = self._parse_constant(ctx.const())
            if operator_ctx and operator_ctx.SUB():
                coefficient = -coefficient
            self.coefficients = torch.hstack([self.coefficients, coefficient])

    def enterIneq(self, ctx: TRUNCParser.IneqContext) -> None:
        self.operator = ctx.inop().getText()
        self.constant = self._parse_constant_expression(ctx.const_expr())

    def enterAnd_trunc(self, ctx: TRUNCParser.And_truncContext) -> None:
        variable_name = ctx.IDV()[0].getText()
        variable_index = self.variables.index(variable_name)
        self.coefficients[variable_index] = torch.tensor(1.0)
        for inop, const_expr in zip(ctx.inop(), ctx.const_expr(), strict=False):
            value = self._parse_constant_expression(const_expr)
            operator_text = inop.getText()
            if "<" in operator_text:
                self.upper_bound = value
            elif ">" in operator_text:
                self.lower_bound = value
        self.truncate_func = partial(_and_func, self)

    def enterOr_trunc(self, ctx: TRUNCParser.Or_truncContext) -> None:
        variable_name = ctx.IDV()[0].getText()
        variable_index = self.variables.index(variable_name)
        self.coefficients[variable_index] = torch.tensor(1.0)
        for inop, const_expr in zip(ctx.inop(), ctx.const_expr(), strict=False):
            value = self._parse_constant_expression(const_expr)
            operator_text = inop.getText()
            if "<" in operator_text:
                self.upper_bound = value
            elif ">" in operator_text:
                self.lower_bound = value
        self.truncate_func = partial(_or_func, self)

    def enterLexpr(self, ctx: TRUNCParser.LexprContext) -> None:
        self._current_sign = torch.tensor(1.0)
        self._parse_monomial(ctx.monom()[0])
        for aop, monomial in zip(ctx.aop(), ctx.monom()[1:], strict=False):
            self._parse_monomial(monomial, aop)

    def exitLexpr(self, ctx: TRUNCParser.LexprContext) -> None:
        self.truncate_func = partial(_ineq_func, self)

    def enterEq(self, ctx: TRUNCParser.EqContext) -> None:
        self.operator = ctx.eqop().getText()
        variable_index = self.variables.index(ctx.var()._getText(self.data))
        self.coefficients[variable_index] = torch.tensor(1.0)
        self.constant = self._parse_constant_expression(ctx.const_expr())
        self.truncate_func = partial(_eq_func, self)


def _find_basis(direction: torch.Tensor) -> torch.Tensor:
    """Return a rotation matrix whose first row is *direction*.

    Used to align a general linear truncation direction with the first axis
    before applying the 1-D truncation moment formulas.
    """
    _, _, v = torch.linalg.svd(direction.reshape(1, direction.shape[0]))
    orthogonal_complement = v[:, 1:]
    return torch.vstack((direction.reshape(1, direction.shape[0]), orthogonal_complement.t()))


def _component_probability(
    means: torch.Tensor,
    covariances: torch.Tensor,
    lower_bounds: torch.Tensor,
    upper_bounds: torch.Tensor,
    truncation_index: int = 0,
) -> torch.Tensor:
    """CDF probability mass of each component inside ``[lower_bounds, upper_bounds]``."""
    normal = distributions.Normal(
        loc=means[:, truncation_index],
        scale=torch.sqrt(covariances[:, truncation_index, truncation_index]),
    )
    return normal.cdf(upper_bounds[truncation_index]) - normal.cdf(lower_bounds[truncation_index])


def _compute_lower_moments(
    means: torch.Tensor,
    covariances: torch.Tensor,
    lower_bounds: torch.Tensor,
    upper_bounds: torch.Tensor,
    direction: str,
) -> torch.Tensor:
    """Compute the Kan-Robotti auxiliary mean μ̃ for the (n-1)-dimensional sub-problem."""
    if direction == "low":
        return (
            means[:, 1:]
            + ((lower_bounds[0] - means[:, 0]) / covariances[:, 0, 0]).view(-1, 1) * covariances[:, 1:, :][:, :, 0]
        )
    return (
        means[:, 1:]
        + ((upper_bounds[0] - means[:, 0]) / covariances[:, 0, 0]).view(-1, 1) * covariances[:, 1:, :][:, :, 0]
    )


def _compute_first_moment(
    means: torch.Tensor,
    covariances: torch.Tensor,
    lower_bounds: torch.Tensor,
    upper_bounds: torch.Tensor,
    direction: str | None,
    component_probabilities: torch.Tensor,
    truncation_index: int = 0,
) -> torch.Tensor:
    """Compute the first moment of the truncated distribution (Kan-Robotti)."""
    correction = torch.zeros(means.shape)
    normal = distributions.Normal(
        means[:, truncation_index], scale=torch.sqrt(covariances[:, truncation_index, truncation_index])
    )
    if direction:
        if direction == "low":
            correction[:, 0] = normal.log_prob(lower_bounds[0]).exp()
        elif direction == "up":
            correction[:, 0] = -normal.log_prob(upper_bounds[0]).exp()
        return means + torch.matmul(covariances, correction.unsqueeze(2)).squeeze(2) / component_probabilities.view(
            -1, 1
        )
    # and_func case
    correction[:, truncation_index] = (
        normal.log_prob(lower_bounds[truncation_index]).exp() - normal.log_prob(upper_bounds[truncation_index]).exp()
    )
    return means + torch.matmul(covariances, correction.unsqueeze(2)).squeeze(2) / component_probabilities.view(-1, 1)


def _compute_second_moment(
    means: torch.Tensor,
    covariances: torch.Tensor,
    lower_bounds: torch.Tensor,
    upper_bounds: torch.Tensor,
    direction: str,
    component_probabilities: torch.Tensor,
    truncated_means: torch.Tensor,
    muj: torch.Tensor,
) -> torch.Tensor:
    """Compute the second moment (covariance) of the truncated distribution (Kan-Robotti)."""
    # vector dimensions
    n = len(lower_bounds)
    c = means.shape[0]
    # creates auxiliary vectors
    e0 = torch.zeros((c, n))
    e0[:, 0] = torch.ones(c)

    correction = component_probabilities.view(c, 1, 1) * torch.eye(n).unsqueeze(0).expand(c, -1, -1)
    normal = distributions.Normal(loc=means[:, 0], scale=torch.sqrt(covariances[:, 0, 0]))

    if direction == "low":
        correction[:, :, 0] += (
            normal.log_prob(lower_bounds[0]).exp().view(-1, 1)
            * (lower_bounds[0] ** e0)
            * torch.hstack((torch.ones((c, 1)), muj))
        )
    elif direction == "up":
        correction[:, :, 0] += (
            -normal.log_prob(upper_bounds[0]).exp().view(-1, 1)
            * (upper_bounds[0] ** e0)
            * torch.hstack((torch.ones((c, 1)), muj))
        )

    # computes the new matrix
    truncated_covariances = component_probabilities.view(c, 1, 1) * torch.matmul(
        means.unsqueeze(2), truncated_means.unsqueeze(1)
    ) + torch.matmul(covariances, correction.transpose(1, 2))
    truncated_covariances = truncated_covariances / component_probabilities.view(c, 1, 1) - torch.matmul(
        truncated_means.unsqueeze(2), truncated_means.unsqueeze(1)
    )
    return truncated_covariances


def _compute_conditional_mean(
    bound: torch.Tensor,
    means: torch.Tensor,
    covariances: torch.Tensor,
    truncation_index: int,
) -> torch.Tensor:
    """Compute auxiliary conditional mean μ_j for the and-truncation second moment."""
    mask = torch.ones(bound.shape[0], dtype=torch.bool)
    mask[truncation_index] = False

    means_without_j = means[:, mask]
    covariance_column = covariances[:, mask, :][:, :, truncation_index]
    conditional_mean = (
        means_without_j
        + (
            (bound[truncation_index] - means[:, truncation_index]) / covariances[:, truncation_index, truncation_index]
        ).view(-1, 1)
        * covariance_column
    )

    full_conditional_mean = torch.ones(means.shape)
    full_conditional_mean[:, :truncation_index] = conditional_mean[:, :truncation_index]
    full_conditional_mean[:, truncation_index + 1 :] = conditional_mean[:, truncation_index:]
    return full_conditional_mean


def _compute_second_moment_and(
    means: torch.Tensor,
    covariances: torch.Tensor,
    lower_bounds: torch.Tensor,
    upper_bounds: torch.Tensor,
    component_probabilities: torch.Tensor,
    truncated_means: torch.Tensor,
    truncation_index: int,
) -> torch.Tensor:
    """Compute the second moment for and-truncation (bilateral interval)."""
    # vector dimensions
    n = len(lower_bounds)
    c = means.shape[0]
    # creates auxiliary vectors
    e0 = torch.zeros((c, n))
    e0[:, truncation_index] = torch.ones(c)

    correction = component_probabilities.view(c, 1, 1) * torch.eye(n).unsqueeze(0).expand(c, -1, -1)
    normal = distributions.Normal(
        loc=means[:, truncation_index], scale=torch.sqrt(covariances[:, truncation_index, truncation_index])
    )
    correction[:, :, truncation_index] += normal.log_prob(lower_bounds[truncation_index]).exp().view(-1, 1) * (
        lower_bounds[truncation_index] ** e0
    ) * _compute_conditional_mean(lower_bounds, means, covariances, truncation_index) - normal.log_prob(
        upper_bounds[truncation_index]
    ).exp().view(-1, 1) * (upper_bounds[truncation_index] ** e0) * _compute_conditional_mean(
        upper_bounds, means, covariances, truncation_index
    )

    # computes the new matrix
    truncated_covariances = component_probabilities.view(c, 1, 1) * torch.matmul(
        means.unsqueeze(2), truncated_means.unsqueeze(1)
    ) + torch.matmul(covariances, correction.transpose(1, 2))
    truncated_covariances = truncated_covariances / component_probabilities.view(c, 1, 1) - torch.matmul(
        truncated_means.unsqueeze(2), truncated_means.unsqueeze(1)
    )
    return truncated_covariances


def _compute_moments(
    means: torch.Tensor,
    covariances: torch.Tensor,
    lower_bounds: torch.Tensor,
    upper_bounds: torch.Tensor,
    truncation_index: int = 0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """Compute means, covariances, and probabilities of each surviving component.

    Returns ``(component_probabilities, truncated_means, truncated_covariances, surviving_indices)``.
    Components whose probability falls below ``TOL_PROB`` are excluded.
    """
    n = len(lower_bounds)

    # truncation in one dimension
    if n == 1:
        truncated_normal = TruncatedNormal(means, torch.sqrt(covariances), lower_bounds, upper_bounds)
        component_probabilities = truncated_normal.norm_const
        # excluding truncated components with probability 0
        surviving_indices = torch.where(component_probabilities > TOL_PROB)[0]
        if len(surviving_indices) == 0:
            return component_probabilities, means, covariances, surviving_indices
        surviving_tn = TruncatedNormal(
            means[surviving_indices], torch.sqrt(covariances[surviving_indices]), lower_bounds, upper_bounds
        )
        return component_probabilities[surviving_indices], surviving_tn.mean(), surviving_tn.var(), surviving_indices

    # if in more dimensions applies Kan-Robotti formulas
    # first determines if the truncation is 'low' (i.e. x > c) or 'up' (i.e. x < c) or None if in and_func
    is_bilateral = lower_bounds[truncation_index] > -INFTY and upper_bounds[truncation_index] < INFTY
    if is_bilateral:
        direction = None
    elif lower_bounds[0] > -INFTY:
        direction = "low"
    else:
        direction = "up"

    component_probabilities = _component_probability(means, covariances, lower_bounds, upper_bounds, truncation_index)
    # excluding truncated components with probability 0
    surviving_indices = torch.where(component_probabilities > TOL_PROB)[0]
    if len(surviving_indices) == 0:
        return component_probabilities, means, covariances, surviving_indices

    # computes first two order moments using the Kan-Robotti recurrence formulas
    truncated_means = _compute_first_moment(
        means[surviving_indices],
        covariances[surviving_indices],
        lower_bounds,
        upper_bounds,
        direction,
        component_probabilities[surviving_indices],
        truncation_index,
    )
    if direction:
        # returns the moments for the distribution of dimension n-1 (the trunc_idx component removed)
        muj = _compute_lower_moments(
            means[surviving_indices], covariances[surviving_indices], lower_bounds, upper_bounds, direction
        )
        truncated_covariances = _compute_second_moment(
            means[surviving_indices],
            covariances[surviving_indices],
            lower_bounds,
            upper_bounds,
            direction,
            component_probabilities[surviving_indices],
            truncated_means,
            muj,
        )
    else:  # and_func
        truncated_covariances = _compute_second_moment_and(
            means[surviving_indices],
            covariances[surviving_indices],
            lower_bounds,
            upper_bounds,
            component_probabilities[surviving_indices],
            truncated_means,
            truncation_index,
        )

    return component_probabilities[surviving_indices], truncated_means, truncated_covariances, surviving_indices


def parse_truncation(
    variables: list[str],
    condition: str,
    data: dict[str, Any],
    parameters: dict[str, torch.Tensor],
) -> TruncRule:
    """Parse *condition* with the TRUNC grammar and return the populated rule."""

    if condition not in TRUNC_TREE_CACHE:
        lexer = TRUNCLexer(InputStream(condition))
        stream = CommonTokenStream(lexer)
        parser = TRUNCParser(stream)
        TRUNC_TREE_CACHE[condition] = parser.trunc()
    rule = TruncRule(variables, data, parameters)

    try:
        ParseTreeWalker().walk(rule, TRUNC_TREE_CACHE[condition])
    except ValueError as e:
        raise InvalidConstraintError(f"Invalid truncation condition: {condition!r}") from e

    return rule


def truncate(
    distribution: Dist,
    condition: str,
    data: dict[str, Any],
    parameters: dict[str, torch.Tensor],
) -> tuple[torch.Tensor, Dist]:
    """Truncate *distribution* to the region where *condition* holds."""
    if condition == "true":
        return torch.tensor(1.0), distribution
    if condition == "false":
        return torch.tensor(0.0), distribution

    logger.debug("truncate  condition=%r  variables=%s", condition, distribution.var_list)
    rule = parse_truncation(distribution.var_list, condition, data, parameters)
    if rule.truncate_func is None:
        logger.error("TruncRule produced no function for condition=%r", condition)
        raise InvalidConstraintError(f"Unsupported or invalid truncation condition: {condition!r}")
    normalizer, new_distribution = rule.truncate_func(distribution)
    return normalizer, new_distribution
