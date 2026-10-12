from __future__ import annotations

import copy
import logging
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal

import torch

from pydegas.cfg.graph import ControlFlowGraph
from pydegas.mixtures.distribution import Dist
from pydegas.optimize.losses import LossFunction
from pydegas.optimize.params import initialize_params, snapshot_params
from pydegas.semantics.engine import start_soga


logger = logging.getLogger(__name__)


OPTIMIZER_REGISTRY: dict[str, type[torch.optim.Optimizer]] = {
    "Adam": torch.optim.Adam,
    "AdamW": torch.optim.AdamW,
    "SGD": torch.optim.SGD,
    "RMSprop": torch.optim.RMSprop,
    "Adagrad": torch.optim.Adagrad,
    "LBFGS": torch.optim.LBFGS,
}


type OptimizerSpec = torch.optim.Optimizer | type[torch.optim.Optimizer] | str


def resolve_optimizer(
    spec: OptimizerSpec,
    parameters: list[torch.Tensor],
    **kwargs: Any,
) -> torch.optim.Optimizer:
    if isinstance(spec, torch.optim.Optimizer):
        if kwargs:
            logger.warning("optimizer instance supplied; ignoring kwargs=%s", kwargs)
        return spec

    if isinstance(spec, str):
        if spec not in OPTIMIZER_REGISTRY:
            logger.error("unknown optimizer name=%r; available=%s", spec, sorted(OPTIMIZER_REGISTRY))
            raise ValueError(f"Unknown optimizer name {spec!r}. Available: {sorted(OPTIMIZER_REGISTRY)}")
        cls: type[torch.optim.Optimizer] = OPTIMIZER_REGISTRY[spec]
    elif isinstance(spec, type) and issubclass(spec, torch.optim.Optimizer):
        cls = spec
    else:
        logger.error("unsupported optimizer spec=%r (type=%s)", spec, type(spec).__name__)
        raise TypeError(f"Unsupported optimizer spec: {spec!r}")

    return cls(parameters, **kwargs)


@dataclass
class StepResult:
    step: int
    loss: float
    params: dict[str, float]
    dist: Dist
    elapsed_ms: float = 0.0
    converged: bool = False


class OptimizationRun:
    def __init__(
        self,
        cfg: ControlFlowGraph,
        initial_params: dict[str, float],
        loss_fn: LossFunction,
        optimizer: OptimizerSpec = "Adam",
        *,
        optimizer_kwargs: dict[str, Any] | None = None,
        tolerance: float | None = 1e-8,
        patience: int = 30,
        on_step: Callable[[StepResult], bool] | None = None,
        Kmax: int | None = None,
        pruning: Literal["classic", "ranking", "kmeans"] = "classic",
    ) -> None:
        if optimizer_kwargs is None:
            optimizer_kwargs = {"lr": 0.05}

        self.cfg = cfg
        self.params: dict[str, torch.Tensor] = initialize_params(initial_params)
        self.loss_fn = loss_fn
        self.optimizer: torch.optim.Optimizer = resolve_optimizer(
            optimizer, list(self.params.values()), **optimizer_kwargs
        )

        self.tolerance = tolerance
        self.patience = patience
        self.on_step = on_step
        self.Kmax = Kmax
        self.pruning = pruning

        # sliding window of the last (patience+1) losses
        self._recent_losses: deque[float] = deque(maxlen=patience + 1)

        logger.debug(
            "OptimizationRun initialized: optimizer=%s params=%s tolerance=%s patience=%d Kmax=%s",
            type(self.optimizer).__name__,
            list(initial_params.keys()),
            tolerance,
            patience,
            Kmax,
        )

    def step(self, step_index: int) -> StepResult:
        start = time.perf_counter()

        if isinstance(self.optimizer, torch.optim.LBFGS):
            # LBFGS re-evaluates the function multiple times per step (line search),
            # so it requires a closure. nonlocal lets us capture the last evaluation.
            _last_loss: torch.Tensor | None = None
            _last_dist: Dist | None = None

            def closure() -> torch.Tensor:
                nonlocal _last_loss, _last_dist
                self.optimizer.zero_grad(set_to_none=True)
                _last_dist = start_soga(self.cfg, self.params, pruning=self.pruning, Kmax=self.Kmax)
                _last_loss = self.loss_fn(_last_dist)
                _last_loss.backward()
                return _last_loss

            self.optimizer.step(closure)
            assert _last_loss is not None and _last_dist is not None
            loss, current_dist = _last_loss, _last_dist
        else:
            self.optimizer.zero_grad(set_to_none=True)
            current_dist = start_soga(self.cfg, self.params, pruning=self.pruning, Kmax=self.Kmax)
            loss = self.loss_fn(current_dist)
            loss.backward()
            self.optimizer.step()

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return StepResult(
            step=step_index,
            loss=loss.item(),
            params=snapshot_params(self.params),
            dist=copy.deepcopy(current_dist),
            elapsed_ms=elapsed_ms,
        )

    def has_converged(self) -> bool:
        if self.tolerance is None or len(self._recent_losses) <= self.patience:
            return False
        return all(
            abs(curr - prev) < self.tolerance
            for prev, curr in zip(self._recent_losses, list(self._recent_losses)[1:], strict=False)
        )

    def run_generator(self, n_steps: int) -> Iterator[StepResult]:
        for i in range(n_steps):
            result = self.step(i)
            self._recent_losses.append(result.loss)

            if self.has_converged():
                result.converged = True

            logger.debug(
                "step=%d loss=%.6f params=%s elapsed=%.1fms",
                result.step,
                result.loss,
                result.params,
                result.elapsed_ms,
            )

            if self.on_step is not None and self.on_step(result):
                logger.debug("step=%d early stop via callback", result.step)
                yield result
                return

            yield result

            if result.converged:
                logger.debug(
                    "step=%d converged (tolerance=%g, patience=%d)",
                    result.step,
                    self.tolerance,
                    self.patience,
                )
                return

    def run(self, n_steps: int) -> list[StepResult]:
        return list(self.run_generator(n_steps))


def optimize(
    cfg: ControlFlowGraph,
    initial_params: dict[str, float],
    loss_fn: LossFunction,
    n_steps: int = 100,
    optimizer: OptimizerSpec = "Adam",
    *,
    optimizer_kwargs: dict[str, Any] | None = None,
    **run_kwargs: Any,
) -> OptimizationRun:
    run = OptimizationRun(
        cfg=cfg,
        initial_params=initial_params,
        loss_fn=loss_fn,
        optimizer=optimizer,
        optimizer_kwargs=optimizer_kwargs,
        **run_kwargs,
    )
    run.run(n_steps)
    return run
