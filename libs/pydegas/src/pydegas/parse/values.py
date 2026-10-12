"""Value conversion shared by the handwritten expression listeners."""

from __future__ import annotations

from typing import Any

import torch


def unpack_gm_list(ctx: Any, parameters: dict[str, torch.Tensor]) -> torch.Tensor:
    """Read a grammar-validated list without detaching parameter tensors."""
    values = ctx.getText()[1:-1].split(",")
    return torch.stack(
        [parameters[value[1:]] if value.startswith("_") else torch.tensor(float(value)) for value in values]
    )
