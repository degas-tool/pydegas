#!/usr/bin/env bash
# Starts (or stops) the web application degas.dev locally on http://localhost:3000.
# Needs Docker with Compose, run on the host (not inside the evaluation image).
#   scripts/web_app.sh up | down | logs
set -euo pipefail
cd "$(dirname "$0")/.."
export COMPOSE_FILE=compose.yaml:compose.local.yaml
case "${1:-up}" in
  up)
    docker compose up -d --build
    printf 'waiting for http://localhost:3000 '
    for _ in $(seq 1 90); do
      if curl -sf -m 2 http://localhost:3000/health > /dev/null; then
        printf '\nready: http://localhost:3000  (API docs: http://localhost:3000/docs)\n'; exit 0
      fi
      printf '.'; sleep 2
    done
    echo; echo "not ready after 3 minutes, see: bash scripts/web_app.sh logs" >&2; exit 1 ;;
  down) docker compose down --volumes ;;
  logs) docker compose logs -f ;;
  *) echo "usage: $0 up|down|logs" >&2; exit 2 ;;
esac
