# Configuration

Settings are read from environment variables with the prefix `DEGAS_API_`
(defined in `src/degas_api/settings.py`). Nested settings use `__` as the
separator, for example `DEGAS_API_LOGGING__LEVEL=DEBUG`. A `.env` file in the
working directory or one of its parents is loaded at startup. List values are
written as JSON, for example `DEGAS_API_ALLOWED_HOSTS='["localhost"]'`.

## Service

| Variable | Default | Meaning |
|---|---|---|
| `DEGAS_API_HOST` | `0.0.0.0` | address `degas-api serve` listens on |
| `DEGAS_API_PORT` | `8000` | port `degas-api serve` listens on |
| `DEGAS_API_DOCS_URL` | `/docs` | path of the interactive API documentation |
| `DEGAS_API_STATIC_DIR` | unset | directory with a built UI to serve from the API |
| `DEGAS_API_ALLOWED_HOSTS` | `["*"]` | accepted `Host` header values |
| `DEGAS_API_LOGGING__LEVEL` | `INFO` | log level |

`degas-api serve --host`, `--port` and `--log-level` override them for all workers,
and `--workers` sets the number of processes; see the
[command line](cli.md).

## Sessions

| Variable | Default | Meaning |
|---|---|---|
| `DEGAS_API_DB_PATH` | `degas_sessions.db`; `/data/sessions.db` in the Docker image | SQLite file for saved sessions; create or upgrade it with `degas-api migrate` |
| `DEGAS_API_SESSION_TTL_DAYS` | `1` | days a session is kept after it was created or last read |
| `DEGAS_API_SESSION_CLEANUP_INTERVAL_HOURS` | `6` | interval of the job that deletes expired sessions |

## Redis

Prefix `DEGAS_API_OPTIMIZATION_RATE_LIMITER__`:

| Variable | Default | Meaning |
|---|---|---|
| `ENABLED` | `true` | `false` skips the rate limit and the run-slot limit; Redis is then not used |
| `HOST` | `localhost` | Redis host |
| `PORT` | `6379` | Redis port |
| `DB` | `0` | Redis database |
| `USERNAME` | unset | Redis ACL user |
| `PASSWORD` | unset | Redis password |
| `SSL` | `false` | `true` connects with TLS |

## Limits

Prefix `DEGAS_API_OPTIMIZATION_LIMITS__`. How they are enforced:
[Limits and caveats](limits.md).

| Variable | Default | Meaning |
|---|---|---|
| `MAX_CONCURRENT_RUNS` | `2` | runs admitted at the same time, across all workers |
| `MAX_STEPS` | `500` | largest `n_steps` per run |
| `RATE_LIMIT_REQUESTS` | `20` | runs and loss validations per client per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | length of the rate-limit window |
| `MAX_KMAX` | `100` | `Kmax` values at or above this are rejected |
| `MAX_RUN_SECONDS` | `300` | run time limit, checked after each step |
| `MAX_TRAJECTORY_ROWS` | `500` | rows in a trajectory input |
| `MAX_TRAJECTORY_COLS` | `200` | values in the first row of a trajectory input |
