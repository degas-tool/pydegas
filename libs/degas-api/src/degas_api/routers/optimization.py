from __future__ import annotations

import asyncio
import contextlib
import json
import math
import time
from collections.abc import Iterator
from typing import Any, Literal, get_args

import torch
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from loguru import logger
from pydantic import BaseModel, Field, ValidationError, model_validator
from pydegas.cfg.builder import from_text
from pydegas.cfg.smoother import smooth
from pydegas.exceptions import PyDeGASError
from pydegas.optimize.losses import (
    LOSS_DSL_SOURCE,
    LOSS_PARAM_SCHEMA,
    LOSS_REGISTRY,
    LossFunction,
    get_loss,
)
from pydegas.optimize.runner import OPTIMIZER_REGISTRY, OptimizationRun, StepResult
from pydegas.parse.preprocessor import compile_to_soga_text

from degas_api.cache.process import OptimizationRateLimiter
from degas_api.settings import OptimizationLimitsSettings, app_settings


router = APIRouter(
    prefix="/optimization",
    tags=["optimization"],
)


class LossValidateRequest(BaseModel):
    source: str = Field(..., max_length=20_000)


class LossParamInfo(BaseModel):
    name: str
    type: str | None


class LossValidateResponse(BaseModel):
    errors: list[str]
    params: list[LossParamInfo]


class OptimizationRequest(BaseModel):
    program: str = Field(..., max_length=50_000)
    program_language: Literal["soga", "soga_highlevel"] = "soga"
    compile_seed: int | None = None
    smooth_eps: float | None = None

    loss_function: str | None = Field(
        default=None,
        description="Name from /optimization/loss-functions. Ignored when loss_source is set.",
    )
    loss_kwargs: dict[str, Any] = Field(default_factory=dict)

    loss_source: str | None = Field(
        default=None,
        max_length=20_000,
        description="DeGASLoss DSL source. When set, loss_function is ignored.",
    )
    loss_bindings: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON bindings for non-dist parameters in the custom loss DSL.",
    )

    @model_validator(mode="after")
    def check_loss_provided(self) -> OptimizationRequest:
        if not self.loss_source and self.loss_function is None:
            raise ValueError("Either loss_function or loss_source must be provided.")
        return self

    optimizer: str = Field(..., description="Name from /optimization/optimizers")
    initial_params: dict[str, float]
    n_steps: int = Field(default=100, ge=1)
    optimizer_kwargs: dict[str, Any] = Field(default_factory=dict)

    Kmax: int | None = Field(
        default=20,
        ge=1,
        description="Maximum number of Gaussian components per merge. None = no pruning.",
    )
    pruning: Literal["classic", "ranking", "kmeans"] = "classic"

    tolerance: float | None = Field(
        default=1e-8,
        ge=0,
        description="Loss-stability threshold for convergence detection. None disables it.",
    )
    patience: int = Field(
        default=30,
        ge=1,
        description="Number of consecutive stable steps required before flagging converged.",
    )

    return_dist_summary: bool = True


class LossParamDef(BaseModel):
    name: str
    type: str
    required: bool
    default: float | int | None = None


class LossFunctionInfo(BaseModel):
    name: str
    params: list[LossParamDef]
    definition: str | None = None  # DeGASLoss DSL source, for the editor preview/prefill


def _get_client_ip(conn: Request | WebSocket) -> str:
    """Extract the real client IP from an HTTP request or WebSocket connection."""
    real_ip = conn.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    forwarded_for = conn.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return conn.client.host if conn.client else "unknown"


async def check_validate_rate_limit(http_request: Request) -> None:
    """Sliding-window rate limit for /loss/validate (no concurrency slot)."""
    limiter: OptimizationRateLimiter | None = getattr(http_request.app.state, "orl_limiter", None)
    if limiter is None:
        return
    client_ip = _get_client_ip(http_request)
    allowed, retry_after = await limiter.check_rate_limit(client_ip)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Too many requests from this address.",
            headers={"Retry-After": str(retry_after)},
        )


@router.post("/loss/validate", response_model=LossValidateResponse)
def validate_loss_source(
    body: LossValidateRequest,
    _: None = Depends(check_validate_rate_limit),
) -> LossValidateResponse:
    from pydegas.optimize.dsl import extract_params, validate_loss

    errors = validate_loss(body.source)
    params = extract_params(body.source) if not errors else []
    return LossValidateResponse(
        errors=errors,
        params=[LossParamInfo(**p) for p in params],
    )


@router.get("/loss-functions")
def get_loss_functions() -> list[LossFunctionInfo]:
    return [
        LossFunctionInfo(
            name=name,
            params=[LossParamDef(**p) for p in LOSS_PARAM_SCHEMA.get(name, [])],
            definition=LOSS_DSL_SOURCE.get(name),
        )
        for name in LOSS_REGISTRY
    ]


@router.get("/optimizers")
def get_optimizers() -> list[str]:
    return list(OPTIMIZER_REGISTRY.keys())


@router.get("/pruning-strategies")
def get_pruning_strategies() -> list[str]:
    return list(get_args(OptimizationRequest.model_fields["pruning"].annotation))


_BINDING_EXPECTATIONS = {
    "index_list": "a list of integers",
    "scalar": "a number",
    "int": "an integer",
}


def _format_validation_error(error: ValidationError) -> str:
    parts = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"])
        message = item["msg"].removeprefix("Value error, ")
        parts.append(f"{location}: {message}" if location else message)
    return "; ".join(parts)


def _error_detail(error: Exception) -> str:
    return str(error) or type(error).__name__


def _check_finite(step: StepResult, dist: dict[str, Any] | None) -> None:
    values = [step.loss, *step.params.values(), *(dist["mean"] if dist else [])]
    if not all(math.isfinite(v) for v in values):
        raise ValueError(
            f"Step {step.step} produced a non-finite loss, parameter or mean (NaN or infinity); the run was stopped."
        )


def _trajectory_tensor(label: str, raw: Any, limits: OptimizationLimitsSettings) -> torch.Tensor:
    if not isinstance(raw, list) or not all(isinstance(row, list) for row in raw):
        raise ValueError(f"{label} must be a 2-D array.")
    if len(raw) > limits.max_trajectory_rows or (raw and len(raw[0]) > limits.max_trajectory_cols):
        raise ValueError(f"{label} exceeds the trajectory size limits.")
    return torch.tensor(raw, dtype=torch.float64)


_SCHEMA_ANNOTATIONS = {"float[][]": "traj_set", "int[]": "index_list", "float": "scalar", "int": "int"}


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise TypeError(value)


def _as_float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(value)
    return float(value)


def _coerce_binding(label: str, type_ann: str | None, raw: Any, limits: OptimizationLimitsSettings) -> Any:
    if type_ann == "traj_set":
        return _trajectory_tensor(label, raw, limits)
    expected = _BINDING_EXPECTATIONS.get(type_ann or "")
    if expected is None:
        return raw
    invalid = ValueError(f"{label} must be {expected}.")
    if type_ann == "index_list" and not isinstance(raw, list):
        raise invalid
    try:
        if type_ann == "index_list":
            return [_as_int(x) for x in raw]
        if type_ann == "scalar":
            return torch.tensor(_as_float(raw), dtype=torch.float64)
        return _as_int(raw)
    except (TypeError, ValueError) as e:
        raise invalid from e


def _build_loss(body: OptimizationRequest, limits: OptimizationLimitsSettings) -> LossFunction:
    if body.loss_source:
        from pydegas.optimize.dsl import compile_loss, extract_params

        coerced: dict[str, Any] = {}
        for param in extract_params(body.loss_source):
            name = str(param["name"])
            raw = body.loss_bindings.get(name)
            if raw is None:
                continue
            coerced[name] = _coerce_binding(f"binding '{name}'", param["type"], raw, limits)
        return compile_loss(body.loss_source, **coerced)

    if body.loss_function is None:
        raise ValueError("Either loss_function or loss_source must be provided.")
    loss_kwargs = dict(body.loss_kwargs)
    for param in LOSS_PARAM_SCHEMA.get(body.loss_function, []):
        name = str(param["name"])
        if loss_kwargs.get(name) is not None:
            loss_kwargs[name] = _coerce_binding(
                name, _SCHEMA_ANNOTATIONS.get(str(param["type"])), loss_kwargs[name], limits
            )
    return get_loss(body.loss_function, **loss_kwargs)


def _build_run(body: OptimizationRequest, limits: OptimizationLimitsSettings) -> OptimizationRun:
    program = body.program
    if body.program_language == "soga_highlevel":
        program = compile_to_soga_text(program, seed=body.compile_seed)
    cfg = from_text(program)
    if body.smooth_eps is not None:
        smooth(cfg, smooth_eps=body.smooth_eps)
    else:
        smooth(cfg)

    loss_fn = _build_loss(body, limits)

    optimizer_kwargs = dict(body.optimizer_kwargs)
    if body.optimizer == "LBFGS":
        optimizer_kwargs["max_iter"] = min(optimizer_kwargs.get("max_iter", 20), 20)

    return OptimizationRun(
        cfg=cfg,
        initial_params=body.initial_params,
        loss_fn=loss_fn,
        optimizer=body.optimizer,
        optimizer_kwargs=optimizer_kwargs or None,
        Kmax=body.Kmax,
        pruning=body.pruning,
        tolerance=body.tolerance,
        patience=body.patience,
    )


def _next_step(gen: Iterator[StepResult]) -> StepResult | None:
    return next(gen, None)


def _discard_result(future: asyncio.Future[Any]) -> None:
    if not future.cancelled():
        future.exception()


async def _receive_request(websocket: WebSocket) -> OptimizationRequest:
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))
    text = message.get("text")
    if text is None:
        raise ValueError("the request must be sent as a JSON text message.")
    return OptimizationRequest.model_validate(json.loads(text))


async def _reject(websocket: WebSocket, kind: str, detail: str) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_json({"type": "error", "kind": kind, "detail": detail})
    with contextlib.suppress(Exception):
        await websocket.close()


@router.websocket("/ws")
async def ws_optimization(
    websocket: WebSocket,
) -> None:
    """Run an optimization over a WebSocket."""
    await websocket.accept()
    limits = app_settings.optimization_limits
    limiter: OptimizationRateLimiter | None = getattr(websocket.app.state, "orl_limiter", None)
    peer = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
    step_count = 0
    logger.info("ws[{peer}] connected", peer=peer)

    try:
        body = await _receive_request(websocket)
    except WebSocketDisconnect:
        logger.info("ws[{peer}] disconnected before sending a request", peer=peer)
        return
    except Exception as e:
        detail = _format_validation_error(e) if isinstance(e, ValidationError) else _error_detail(e)
        logger.warning("ws[{peer}] invalid request: {err}", peer=peer, err=detail)
        await _reject(websocket, "setup_error", f"Invalid request: {detail}")
        return

    loss_desc = f"custom({len(body.loss_source)} chars)" if body.loss_source else body.loss_function
    logger.info(
        "ws[{peer}] request: lang={lang} optimizer={optimizer} loss={loss} n_steps={n_steps} Kmax={kmax}",
        peer=peer,
        lang=body.program_language,
        optimizer=body.optimizer,
        loss=loss_desc,
        n_steps=body.n_steps,
        kmax=body.Kmax,
    )

    if body.n_steps > limits.max_steps:
        logger.warning(
            "ws[{peer}] rejected: n_steps={n_steps} exceeds max {max_steps}",
            peer=peer,
            n_steps=body.n_steps,
            max_steps=limits.max_steps,
        )
        await _reject(
            websocket,
            "setup_error",
            f"n_steps={body.n_steps} exceeds the maximum of {limits.max_steps}.",
        )
        return
    if body.Kmax is not None and body.Kmax >= limits.max_kmax:
        logger.warning(
            "ws[{peer}] rejected: Kmax={kmax} is not below {max_kmax}",
            peer=peer,
            kmax=body.Kmax,
            max_kmax=limits.max_kmax,
        )
        await _reject(
            websocket,
            "setup_error",
            f"Kmax={body.Kmax} must be below {limits.max_kmax}. Set Kmax=null to disable pruning.",
        )
        return

    acquired = False
    if limiter is not None:
        client_ip = _get_client_ip(websocket)
        try:
            allowed, _retry = await limiter.check_rate_limit(client_ip)
            if allowed:
                acquired = await limiter.try_acquire_slot()
                if not acquired:
                    with contextlib.suppress(Exception):
                        await limiter.undo_rate_limit_entry(client_ip)
        except Exception:
            logger.exception("ws[{peer}] rate limiter unavailable", peer=peer)
            await _reject(
                websocket,
                "setup_error",
                "The rate limiter is unavailable. Please retry shortly.",
            )
            return
        if not allowed:
            logger.warning("ws[{peer}] rejected: rate limited (ip={ip})", peer=peer, ip=client_ip)
            await _reject(
                websocket,
                "rate_limited",
                "Too many optimization requests from this address.",
            )
            return
        if not acquired:
            logger.warning(
                "ws[{peer}] rejected: server at capacity (max {max})",
                peer=peer,
                max=limits.max_concurrent_runs,
            )
            await _reject(
                websocket,
                "at_capacity",
                f"Server at capacity ({limits.max_concurrent_runs} concurrent runs). Please retry shortly.",
            )
            return
        logger.info("ws[{peer}] concurrency slot acquired", peer=peer)

    try:
        try:
            run = _build_run(body, limits)
        except Exception as e:
            if isinstance(e, ValueError | PyDeGASError):
                logger.warning("ws[{peer}] setup error: {err}", peer=peer, err=e)
            else:
                logger.opt(exception=e).warning("ws[{peer}] setup error: {err}", peer=peer, err=e)
            await websocket.send_json({"type": "error", "kind": "setup_error", "detail": _error_detail(e)})
            return

        await websocket.send_json({"type": "start", "n_steps": body.n_steps})
        logger.info("ws[{peer}] run started ({n_steps} steps)", peer=peer, n_steps=body.n_steps)
        loop = asyncio.get_running_loop()
        stop_task = asyncio.ensure_future(websocket.receive())
        deadline = time.monotonic() + limits.max_run_seconds
        run_start = time.monotonic()
        gen = run.run_generator(body.n_steps)
        final_params = dict(body.initial_params)
        converged = False
        outcome = "not_converged"
        try:
            while True:
                step_task = loop.run_in_executor(None, _next_step, gen)
                waiting: set[asyncio.Future[Any]] = {step_task, stop_task}
                done, _pending = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)

                if stop_task in done:
                    step_task.add_done_callback(_discard_result)
                    if stop_task.result()["type"] == "websocket.disconnect":
                        outcome = "connection_lost"
                        logger.info(
                            "ws[{peer}] client disconnected mid-run after {steps} steps",
                            peer=peer,
                            steps=step_count,
                        )
                    else:
                        outcome = "stopped"
                        logger.info(
                            "ws[{peer}] stop requested by client after {steps} steps",
                            peer=peer,
                            steps=step_count,
                        )
                    break

                step = step_task.result()
                if step is None:
                    outcome = "converged" if converged else "not_converged"
                    break

                final_params = step.params
                converged = step.converged
                dist = None
                if body.return_dist_summary:
                    dist = {
                        "var_list": step.dist.var_list,
                        "mean": [float(x) for x in step.dist.gm.mean().tolist()],
                    }
                _check_finite(step, dist)
                await websocket.send_json(
                    {
                        "type": "step",
                        "step": step.step,
                        "loss": step.loss,
                        "params": step.params,
                        "elapsed_ms": step.elapsed_ms,
                        "dist": dist,
                    }
                )
                step_count += 1
                logger.debug(
                    "ws[{peer}] step {step} loss={loss:.6g} ({elapsed:.0f}ms)",
                    peer=peer,
                    step=step.step,
                    loss=step.loss,
                    elapsed=step.elapsed_ms,
                )

                if time.monotonic() > deadline:
                    outcome = "run_timeout"
                    logger.info(
                        "ws[{peer}] total run timeout after {steps} steps",
                        peer=peer,
                        steps=step_count,
                    )
                    break
        finally:
            stop_task.cancel()

        logger.info(
            "ws[{peer}] run finished: outcome={outcome} steps={steps} elapsed={elapsed:.1f}s",
            peer=peer,
            outcome=outcome,
            steps=step_count,
            elapsed=time.monotonic() - run_start,
        )
        if outcome != "connection_lost":
            await websocket.send_json(
                {
                    "type": "end",
                    "outcome": outcome,
                    "converged": converged,
                    "final_params": final_params,
                }
            )
    except WebSocketDisconnect:
        logger.info(
            "ws[{peer}] client disconnected after {steps} steps",
            peer=peer,
            steps=step_count,
        )
    except Exception as e:
        logger.exception("ws[{peer}] compute error after {steps} steps", peer=peer, steps=step_count)
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "kind": "compute_error", "detail": _error_detail(e)})
    finally:
        if acquired and limiter is not None:
            await limiter.release_slot()
            logger.info("ws[{peer}] concurrency slot released", peer=peer)
        with contextlib.suppress(Exception):
            await websocket.close()
        logger.info("ws[{peer}] handler closed", peer=peer)
