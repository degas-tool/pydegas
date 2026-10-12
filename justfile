# Run the DeGAS stack. Requires Docker and just.
#
#   just up          start locally on http://localhost:3000
#   just prod up     run any recipe against the production configuration
#   just --list      every recipe
#
# Locally, compose.local.yaml adds an nginx proxy to the ui container so the
# browser reaches the API at the same address. In production Caddy does that.

set shell := ["bash", "-euo", "pipefail", "-c"]

export COMPOSE_FILE := "compose.yaml:compose.local.yaml"
url := "http://localhost:3000"

prod_files := "compose.yaml"
prod_url := "http://localhost:8000"

_default:
    @just --list

# Build if needed, start the stack and wait until it answers.
up:
    docker compose up -d --build
    @just _wait

# Stop and remove the containers. Saved sessions are kept.
down:
    docker compose down

# Follow the logs of all three services.
logs:
    docker compose logs -f

# Show the containers and check the endpoints.
status:
    docker compose ps
    @curl -sf {{url}}/health || echo 'api unreachable'
    @echo

# Rebuild the images from scratch, then start.
rebuild:
    docker compose build --no-cache
    docker compose up -d
    @just _wait

# Stop the stack and delete the stored sessions as well.
reset:
    docker compose down --volumes

# Run another recipe against the production configuration: just prod up
prod +recipe:
    @just COMPOSE_FILE={{prod_files}} url={{prod_url}} {{recipe}}

_wait:
    #!/usr/bin/env bash
    printf 'waiting for {{url}} '
    for _ in {1..60}; do
      if curl -sf -m 2 {{url}}/health > /dev/null; then
        printf '\nready:  {{url}}\n        {{url}}/docs\n'
        exit 0
      fi
      printf '.'
      sleep 2
    done
    printf '\nnot ready after two minutes; recent logs:\n'
    docker compose logs --tail 30
    exit 1
