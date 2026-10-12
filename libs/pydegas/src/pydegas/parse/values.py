"""Value conversion shared by the handwritten expression listeners."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import torch

from pydegas.exceptions import MissingParameterError


def lookup_parameter(parameters: Mapping[str, torch.Tensor], name: str) -> torch.Tensor:
    """Return the value of parameter *name* (without the underscore).

    Raises ``MissingParameterError`` (a ``KeyError``) if no value was supplied.
    """
    try:
        return parameters[name]
    except KeyError:
        raise MissingParameterError(name, parameters) from None


def unpack_gm_list(ctx: Any, parameters: dict[str, torch.Tensor]) -> torch.Tensor:
    """Read a grammar-validated list without detaching parameter tensors."""
    values = ctx.getText()[1:-1].split(",")
    return torch.stack(
        [
            lookup_parameter(parameters, value[1:]) if value.startswith("_") else torch.tensor(float(value))
            for value in values
        ]
    )
