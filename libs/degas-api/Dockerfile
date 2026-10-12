FROM astral/uv:0.11 AS uv

FROM python:3.12-slim-bookworm AS builder

COPY --from=uv /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=never
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build/degas-api

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=libs/degas-api/pyproject.toml,target=/build/degas-api/pyproject.toml \
    --mount=type=bind,source=libs/degas-api/uv.lock,target=/build/degas-api/uv.lock \
    --mount=type=bind,source=libs/pydegas/pyproject.toml,target=/build/pydegas/pyproject.toml \
    uv sync --frozen --no-dev --no-editable --no-install-project --no-install-package pydegas

COPY libs/pydegas /build/pydegas
COPY libs/degas-api /build/degas-api

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm AS runtime

ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DEGAS_API_DB_PATH=/data/sessions.db

RUN useradd --system --no-create-home --uid 1001 appuser && \
    mkdir -p /data && chown appuser /data

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
USER appuser

EXPOSE 8000

ENTRYPOINT ["/opt/venv/bin/uvicorn", "degas_api.server:create_app", "--factory"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
