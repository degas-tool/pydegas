"""Built-in loss functions for SOGA optimization."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import torch

from pydegas.mixtures.distribution import Dist


logger = logging.getLogger(__name__)


LossFunction = Callable[[Dist], torch.Tensor]

LossParamDef = dict[str, Any]

LOSS_PARAM_SCHEMA: dict[str, list[LossParamDef]] = {
    "neg_log_likelihood": [
        {"name": "trajectories", "type": "float[][]", "required": True},
        {"name": "indices", "type": "int[]", "required": True},
    ],
    "l2_distance": [
        {"name": "trajectories", "type": "float[][]", "required": True},
        {"name": "indices", "type": "int[]", "required": True},
    ],
    "signal_error": [
        {"name": "target", "type": "float", "required": False, "default": 3.14},
        {"name": "time_steps", "type": "int", "required": False, "default": 50},
    ],
}


def neg_log_likelihood(trajectories: torch.Tensor, indices: list[int]) -> LossFunction:
    """Return a NLL loss over selected marginals of *dist* against *trajectories*.

    Computed in log-space (marg_log_pdf) so that densities below float64 range
    stay finite instead of underflowing to log(0) = -inf.
    """

    def _loss(dist: Dist) -> torch.Tensor:
        return -torch.sum(dist.gm.marg_log_pdf(trajectories[:, indices], indices))

    return _loss


def l2_distance(trajectories: torch.Tensor, indices: list[int]) -> LossFunction:
    """Squared L2 distance between trajectory means and predicted means."""

    def _loss(dist: Dist) -> torch.Tensor:
        predicted = dist.gm.mean()[indices]
        return torch.sum((trajectories[:, indices] - predicted) ** 2)

    return _loss


def signal_error(target: float = 3.14, time_steps: int = 50) -> LossFunction:
    """Squared error between a constant *target* and the predicted mean trace."""

    def _loss(dist: Dist) -> torch.Tensor:
        n = dist.gm.mean().shape[0]
        if time_steps > n:
            raise ValueError(
                f"signal_error: time_steps={time_steps} exceeds the number of program "
                f"variables in the distribution ({n}). Set time_steps <= {n}."
            )
        idx = list(range(1, time_steps))
        target_signal = target * torch.ones(len(idx))
        return torch.sum((dist.gm.mean()[idx] - target_signal) ** 2)

    return _loss


LOSS_REGISTRY: dict[str, Callable[..., LossFunction]] = {
    "neg_log_likelihood": neg_log_likelihood,
    "l2_distance": l2_distance,
    "signal_error": signal_error,
}


# DeGASLoss DSL source equivalents of the built-in losses, used by the UI to
# preview/inspect them and to pre-fill the loss editor.
LOSS_DSL_SOURCE: dict[str, str] = {
    "l2_distance": (
        "loss l2_distance(trajectories: traj_set, distribution: dist, indices: index_list) =\n"
        "    sum( (trajectories[:, indices] - distribution.mean[indices]) ^ 2 )\n"
    ),
    "neg_log_likelihood": (
        "loss neg_log_likelihood(trajectories: traj_set, distribution: dist, indices: index_list) =\n"
        "    sliced = trajectories[:, indices];\n"
        "    - sum( log( distribution.marg_pdf(sliced, indices) ) )\n"
    ),
    "signal_error": (
        "loss signal_error(distribution: dist, target: scalar) =\n"
        "    sum( (distribution.mean[range(0, 5)] - ones(range(0, 5)) * target) ^ 2 )\n"
    ),
}


def get_loss(name: str, **kwargs: Any) -> LossFunction:
    if name not in LOSS_REGISTRY:
        logger.error("unknown loss name=%r; available=%s", name, sorted(LOSS_REGISTRY))
        raise ValueError(
            f"Unknown loss name {name!r}. Available: {sorted(LOSS_REGISTRY)}"
        )
    return LOSS_REGISTRY[name](**kwargs)
