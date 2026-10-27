# Command line

Run it with `uv run degas-api` in `libs/degas-api`. In the Docker image it is
the entrypoint.

| Command | Does |
|---|---|
| `degas-api migrate` | create the session database or upgrade it to the latest schema |
| `degas-api serve` | start the service; refuses to start until the database is migrated |
| `degas-api health` | query `GET /health` and print the answer |
| `degas-api version` | print the degas-api and pydegas versions |

`degas-api <command> --help` lists the options.

## migrate

`--revision` (default `head`) is the revision to upgrade to. It works on
`DEGAS_API_DB_PATH`. A database created before migrations existed is stamped
with the baseline revision first, so its sessions are kept. Running it again on
an up-to-date database changes nothing.

## serve

| Option | Default | Meaning |
|---|---|---|
| `--host` | `DEGAS_API_HOST` (`0.0.0.0`) | address to listen on |
| `--port` | `DEGAS_API_PORT` (`8000`) | port to listen on |
| `--workers` | `1` | number of worker processes |
| `--reload / --no-reload` | `--no-reload` | restart on source changes; needs `--workers 1` |
| `--log-level` | `DEGAS_API_LOGGING__LEVEL` (`INFO`) | `critical`, `error`, `warning`, `info` or `debug` |

Options override the environment variables for all workers. If the database is
missing or not at the latest revision, `serve` exits with status 1 and asks to
run `degas-api migrate`.

## health

| Option | Default | Meaning |
|---|---|---|
| `--url` | `http://localhost:8000` | base URL of the service |
| `--timeout` | `5.0` | seconds to wait for an answer |

Exits 0 on HTTP 200 and 1 on any other status or when the service cannot be
reached. The Docker image uses it as its `HEALTHCHECK`.

## Schema changes

Edit the model in `src/degas_api/models/`, then:

```bash
uv run alembic revision --autogenerate -m "describe the change"
uv run degas-api migrate
```

Review the generated file in `src/degas_api/migrations/versions/` before
committing it. `tests/test_migrations.py` fails when the models and the
migrations differ.
