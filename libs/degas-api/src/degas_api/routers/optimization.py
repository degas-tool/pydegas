from __future__ import annotations

import asyncio
import contextlib
from loguru import logger
import time
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
from pydantic import BaseModel, Field, model_validator

from pydegas.cfg.builder import from_text
from pydegas.cfg.smoother import smooth
from pydegas.exceptions import PyDeGASError
from pydegas.optimize.losses import (
    LOSS_DSL_SOURCE,
    LOSS_PARAM_SCHEMA,
    LOSS_REGISTRY,
    get_loss,
)
from pydegas.optimize.runner import OPTIMIZER_REGISTRY, OptimizationRun
from pydegas.parse.preprocessor import compile_to_soga_text

from degas_api.cache.process import OptimizationRateLimiter
from degas_api.settings import app_settings

router = APIRouter(
    prefix="/optimization",
    tags=["optimization"],
)

# Sentinel returned by next(gen, ...) when the optimization generator is exhausted.
_STEP_DONE = object()


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
    def check_loss_provided(self) -> "OptimizationRequest":
        if self.loss_source is None and self.loss_function is None:
            raise ValueError("Either loss_function or loss_source must be provided.")
        return self

    optimizer: str = Field(..., description="Name from /optimization/optimizers")
    initial_params: dict[str, float]
    n_steps: int = 100
    optimizer_kwargs: dict[str, Any] = Field(default_factory=dict)

    Kmax: int | None = Field(
        default=20,
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
    definition: str | None = (
        None  # DeGASLoss DSL source, for the editor preview/prefill
    )


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
    limiter: OptimizationRateLimiter | None = getattr(
        http_request.app.state, "orl_limiter", None
    )
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


@router.websocket("/ws")
async def ws_optimization(
    websocket: WebSocket,
) -> None:  # TODO: break up to smaller functions to simplify
    """Run an optimization over a WebSocket."""
    await websocket.accept()
    limits = app_settings.optimization_limits
    limiter: OptimizationRateLimiter | None = getattr(
        websocket.app.state, "orl_limiter", None
    )
    # Per-connection tag (host:port, matching uvicorn's access log) to correlate
    # all log lines for one socket. step_count is referenced in the finally.
    peer = (
        f"{websocket.client.host}:{websocket.client.port}"
        if websocket.client
        else "unknown"
    )
    step_count = 0
    logger.info("ws[{peer}] connected", peer=peer)

    # validate request frame
    try:
        body = OptimizationRequest.model_validate(await websocket.receive_json())
    except WebSocketDisconnect:
        logger.info("ws[{peer}] disconnected before sending a request", peer=peer)
        return
    except Exception as e:
        logger.warning("ws[{peer}] invalid request: {err}", peer=peer, err=e)
        await websocket.send_json(
            {"type": "error", "kind": "setup_error", "detail": f"Invalid request: {e}"}
        )
        await websocket.close()
        return

    loss_desc = (
        f"custom({len(body.loss_source)} chars)"
        if body.loss_source
        else body.loss_function
    )
    logger.info(
        "ws[{peer}] request: lang={lang} optimizer={optimizer} loss={loss} n_steps={n_steps} Kmax={kmax}",
        peer=peer,
        lang=body.program_language,
        optimizer=body.optimizer,
        loss=loss_desc,
        n_steps=body.n_steps,
        kmax=body.Kmax,
    )

    # --- admission: limits, rate limit, concurrency slot ---
    if body.n_steps > limits.max_steps:
        logger.warning(
            "ws[{peer}] rejected: n_steps={n_steps} exceeds max {max_steps}",
            peer=peer,
            n_steps=body.n_steps,
            max_steps=limits.max_steps,
        )
        await websocket.send_json(
            {
                "type": "error",
                "kind": "setup_error",
                "detail": f"n_steps={body.n_steps} exceeds the maximum of {limits.max_steps}.",
            }
        )
        await websocket.close()
        return
    if body.Kmax is not None and body.Kmax >= limits.max_kmax:
        logger.warning(
            "ws[{peer}] rejected: Kmax={kmax} below min {max_kmax}",
            peer=peer,
            kmax=body.Kmax,
            max_kmax=limits.max_kmax,
        )
        await websocket.send_json(
            {
                "type": "error",
                "kind": "setup_error",
                "detail": f"Kmax={body.Kmax} is below the minimum of {limits.max_kmax}. Set Kmax=null to disable pruning.",
            }
        )
        await websocket.close()
        return

    acquired = False
    if limiter is not None:
        client_ip = _get_client_ip(websocket)
        allowed, _retry = await limiter.check_rate_limit(client_ip)
        if not allowed:
            logger.warning("ws[{peer}] rejected: rate limited (ip={ip})", peer=peer, ip=client_ip)
            await websocket.send_json(
                {
                    "type": "error",
                    "kind": "rate_limited",
                    "detail": "Too many optimization requests from this address.",
                }
            )
            await websocket.close()
            return
        if not await limiter.try_acquire_slot():
            logger.warning(
                "ws[{peer}] rejected: server at capacity (max {max})",
                peer=peer,
                max=limits.max_concurrent_runs,
            )
            with contextlib.suppress(Exception):
                await limiter.undo_rate_limit_entry(client_ip)
            await websocket.send_json(
                {
                    "type": "error",
                    "kind": "at_capacity",
                    "detail": f"Server at capacity ({limits.max_concurrent_runs} concurrent runs). Please retry shortly.",
                }
            )
            await websocket.close()
            return
        acquired = True
        logger.info("ws[{peer}] concurrency slot acquired", peer=peer)

    try:
        # --- setup (compile, CFG, loss, run); invalid input -> setup_error ---
        try:
            program = body.program
            if body.program_language == "soga_highlevel":
                program = compile_to_soga_text(program, seed=body.compile_seed)
            cfg = from_text(program)
            (
                smooth(cfg, smooth_eps=body.smooth_eps)
                if body.smooth_eps is not None
                else smooth(cfg)
            )

            if body.loss_source:
                from pydegas.optimize.dsl import compile_loss, extract_params

                coerced: dict[str, Any] = {}
                for p in extract_params(body.loss_source):
                    name, type_ann = p["name"], p["type"]
                    raw = body.loss_bindings.get(name)
                    if raw is None:
                        continue
                    if type_ann == "traj_set":
                        if not isinstance(raw, list):
                            raise ValueError(f"binding '{name}' must be a 2-D array.")
                        if len(raw) > limits.max_trajectory_rows or (
                            raw and len(raw[0]) > limits.max_trajectory_cols
                        ):
                            raise ValueError(
                                f"binding '{name}' exceeds the trajectory size limits."
                            )
                        coerced[name] = torch.tensor(raw, dtype=torch.float64)
                    elif type_ann == "index_list":
                        coerced[name] = [int(x) for x in raw]
                    elif type_ann == "scalar":
                        coerced[name] = torch.tensor(float(raw), dtype=torch.float64)
                    elif type_ann == "int":
                        coerced[name] = int(raw)
                    else:
                        coerced[name] = raw
                loss_fn = compile_loss(body.loss_source, **coerced)
            else:
                loss_kwargs = dict(body.loss_kwargs)
                raw = loss_kwargs.get("trajectories")
                if isinstance(raw, list):
                    if len(raw) > limits.max_trajectory_rows or (
                        raw and len(raw[0]) > limits.max_trajectory_cols
                    ):
                        raise ValueError(
                            "trajectories exceeds the trajectory size limits."
                        )
                    loss_kwargs["trajectories"] = torch.tensor(raw, dtype=torch.float64)
                loss_fn = get_loss(body.loss_function, **loss_kwargs)

            optimizer_kwargs = (
                dict(body.optimizer_kwargs) if body.optimizer_kwargs else {}
            )
            if body.optimizer == "LBFGS":
                optimizer_kwargs["max_iter"] = min(
                    optimizer_kwargs.get("max_iter", 20), 20
                )

            run = OptimizationRun(
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
        except (ValueError, PyDeGASError) as e:
            logger.warning("ws[{peer}] setup error: {err}", peer=peer, err=e)
            await websocket.send_json(
                {"type": "error", "kind": "setup_error", "detail": str(e)}
            )
            return

        # run: stream steps; stop / total-timeout honoured between steps # TODO: run in a thread to allow mid-step stop / timeout
        await websocket.send_json({"type": "start", "n_steps": body.n_steps})
        logger.info("ws[{peer}] run started ({n_steps} steps)", peer=peer, n_steps=body.n_steps)
        loop = asyncio.get_running_loop()
        # Any client frame (or disconnect) signals "stop"; created once and reused.
        stop_task = asyncio.ensure_future(websocket.receive_text())
        deadline = time.monotonic() + limits.max_run_seconds
        run_start = time.monotonic()
        gen = run.run_generator(body.n_steps)
        final_params = dict(body.initial_params)
        outcome = "not_converged"
        try:
            while True:
                step_task = loop.run_in_executor(None, next, gen, _STEP_DONE)
                done, _pending = await asyncio.wait(
                    {step_task, stop_task}, return_when=asyncio.FIRST_COMPLETED
                )

                if stop_task in done:
                    # Leave the in-flight step running (a thread can't be killed); just
                    # don't start the next one. Retrieve its result later to avoid a warning.
                    step_task.add_done_callback(lambda f: f.exception())
                    try:
                        stop_task.result()
                        outcome = "stopped"
                        logger.info(
                            "ws[{peer}] stop requested by client after {steps} steps",
                            peer=peer,
                            steps=step_count,
                        )
                    except WebSocketDisconnect:
                        outcome = "connection_lost"
                        logger.info(
                            "ws[{peer}] client disconnected mid-run after {steps} steps",
                            peer=peer,
                            steps=step_count,
                        )
                    break

                step = step_task.result()  # may raise a compute error (e.g. NaN scale)
                if step is _STEP_DONE:
                    outcome = "converged" if run.has_converged() else "not_converged"
                    break

                final_params = step.params
                dist = None
                if body.return_dist_summary:
                    dist = {
                        "var_list": step.dist.var_list,
                        "mean": [float(x) for x in step.dist.gm.mean().tolist()],
                    }
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
                    "converged": run.has_converged(),
                    "final_params": final_params,
                }
            )
    except WebSocketDisconnect:
        logger.info("ws[{peer}] client disconnected after {steps} steps", peer=peer, steps=step_count)
    except (
        Exception
    ) as e:  # mid-run compute/runtime failure (NaN scale, singular matrix, …)
        logger.exception("ws[{peer}] compute error after {steps} steps", peer=peer, steps=step_count)
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "error", "kind": "compute_error", "detail": str(e)}
            )
    finally:
        if acquired and limiter is not None:
            await limiter.release_slot()
            logger.info("ws[{peer}] concurrency slot released", peer=peer)
        with contextlib.suppress(Exception):
            await websocket.close()
        logger.info("ws[{peer}] handler closed", peer=peer)
