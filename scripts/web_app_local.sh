#!/usr/bin/env bash
# Starts the web application degas.dev without Docker, Node.js or Redis (e.g. on
# the TACAS VM) on http://localhost:3000 (another port: DEGAS_API_PORT=3001):
# degas-api serves the prebuilt UI in libs/degas-ui/dist and runs without the
# Redis-backed rate limit. Needs network access the first time. Stop it with
# Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="$PWD/.uv-bin:$PATH"
if ! command -v uv > /dev/null; then
  echo "installing uv 0.13.5 into .uv-bin"
  curl -LsSf https://astral.sh/uv/0.13.5/install.sh | UV_UNMANAGED_INSTALL="$PWD/.uv-bin" sh
fi

export DEGAS_API_STATIC_DIR="$PWD/libs/degas-ui/dist"
export DEGAS_API_PORT="${DEGAS_API_PORT:-3000}"
export DEGAS_API_OPTIMIZATION_RATE_LIMITER__ENABLED=false
export DEGAS_API_OPTIMIZATION_LIMITS__MAX_KMAX=1000
export DEGAS_API_OPTIMIZATION_LIMITS__MAX_RUN_SECONDS=3600

cd libs/degas-api
uv sync --frozen --python 3.12
uv run --frozen --no-sync degas-api migrate
url="http://localhost:$DEGAS_API_PORT"
echo "open $url (API documentation: $url/docs); stop with Ctrl+C"
exec uv run --frozen --no-sync degas-api serve --host 127.0.0.1
