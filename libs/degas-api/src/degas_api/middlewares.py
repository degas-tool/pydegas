from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from loguru import logger
from uuid import uuid4


async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def set_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing

    request_id = request.headers.get("DeGAS-Request-Id") or f"req_{uuid4()}"
    request.state.request_id = request_id
    return request_id


async def add_request_duration_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["DeGAS-Request-Duration-ms"] = f"{duration_ms:.2f}"
    return response


def api_version_middleware(version: str) -> Callable:
    async def add_api_version_header(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["DeGAS-Api-Version"] = version
        return response

    return add_api_version_header


async def add_request_id_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request_id = set_request_id(request)
    response = await call_next(request)
    response.headers["DeGAS-Request-Id"] = request_id
    return response


def logging_context_middleware() -> Callable:
    async def add_logging_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = set_request_id(request)
        method = request.method

        with logger.contextualize(
            request_id=request_id,
            method=method,
        ):
            response = await call_next(request)
        return response

    return add_logging_context
