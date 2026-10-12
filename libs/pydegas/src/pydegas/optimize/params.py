"""This module implements parameter handling helpers for SOGA optimization."""

from __future__ import annotations

import torch


def initialize_params(
    initial: dict[str, float],
    *,
    device: torch.device | str | None = None,
    dtype: torch.dtype | None = None,
) -> dict[str, torch.Tensor]:
    """Create grad-tracked tensors from a ``{name: float}`` mapping."""
    device_ = torch.device(device) if device is not None else None
    return {key: torch.tensor(value, requires_grad=True, device=device_, dtype=dtype) for key, value in initial.items()}


def snapshot_params(params: dict[str, torch.Tensor]) -> dict[str, float]:
    """Detach a live params dict to plain floats."""
    return {key: tensor.item() for key, tensor in params.items()}
