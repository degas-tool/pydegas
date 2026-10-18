# Running the service

## From source

From `libs/degas-api`:

```bash
uv sync
uv run degas-api migrate
uv run degas-api serve
```

`degas-api migrate` creates the SQLite file or upgrades it to the latest
schema; `serve` refuses to start until it is up to date. See
[Command line](cli.md) for the options. `uv sync` installs pydegas from `../pydegas` in editable mode, so changes to
it apply without reinstalling, and the development tools (pytest, ruff, mypy);
`uv run pytest` runs the tests. `--workers N` starts N processes; they share
the run limits through Redis. The API documentation is at
`http://localhost:8000/docs`.

## Redis

With the limiter enabled (the default) the service needs Redis on
`localhost:6379` and does not start without it. Start one:

```bash
docker run --rm -p 6379:6379 redis:8.2.5-bookworm
```

Or run without the rate limit and the run-slot limit:

```bash
DEGAS_API_OPTIMIZATION_RATE_LIMITER__ENABLED=false uv run degas-api serve
```

Saved sessions go to the SQLite file `degas_sessions.db` in the working
directory. See [Configuration](configuration.md) for the other settings.

## Docker image

`Dockerfile` is built from the repository root and contains the service and
pydegas from the same checkout; rebuild it after changing either:

```bash
docker build -f libs/degas-api/Dockerfile -t degas-api .
```

The image has no uv. Its entrypoint is `degas-api`, run as a non-root user;
the default command is `serve --host 0.0.0.0 --port 8000 --workers 1`, and
sessions are stored in `/data/sessions.db` (`DEGAS_API_DB_PATH`). Migrate the
database before serving, and check the service with the built-in
`HEALTHCHECK` (`degas-api health`):

```bash
docker run --rm -v degas-data:/data degas-api migrate
docker run -p 8000:8000 -v degas-data:/data degas-api
```

`compose.yaml` runs a one-shot `migrate` service first, then `api` with four
workers, Redis as the `db` service and `/data` on the `sqlite_data` volume;
see the [local stack](../../../docs/local-stack.md).

## Behind a reverse proxy

The proxy must:

- route `/api/` (with the WebSocket upgrade), `/health`, `/docs` and
  `/openapi.json` to the API;
- set `X-Real-IP` to the client's address, replacing any value the client
  sent, because the rate limit is keyed on it;
- send a `Host` header listed in `DEGAS_API_ALLOWED_HOSTS`;
- keep an idle WebSocket open as long as one step can take.

`nginx.local.conf` in the repository root does this for the local stack.

## Trajectory data

`data/` holds generated trajectory CSVs for the thermostat, gearbox and
bouncing-ball examples. `scripts/generate_trajectories.py` regenerates them:

```bash
uv run python scripts/generate_trajectories.py all --n 100 --seed 0
```
