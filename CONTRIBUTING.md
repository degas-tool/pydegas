# Contributing

## Setup

Requires uv, Node.js `^22.13 || >=24` with npm (`.nvmrc`: 24), and for the
local stack Docker and just.

```bash
git clone https://github.com/degas-tool/pydegas.git
cd pydegas
git submodule update --init --depth 1
```

The submodule `reference/DeGAS` is the original DeGAS code, used by the
pydegas reference tests. Do not clone with `--recurse-submodules`: it fails on
a broken nested submodule inside DeGAS.

## Environments

Each project has its own environment in its own directory:

| Directory | Command |
|---|---|
| `libs/pydegas` | `uv sync` |
| `libs/degas-api` | `uv sync` |
| `libs/degas-ui` | `npm ci` |

- degas-api uses the pydegas release from PyPI. To try unreleased pydegas
  changes in the API, run
  `uv pip install --no-deps --editable ../pydegas` in `libs/degas-api`, then
  `uv run --no-sync <command>`. After a pydegas release, run
  `uv lock --upgrade-package pydegas` in `libs/degas-api`.
- After changing dependencies, run `uv lock` and commit `uv.lock`.

## pydegas

In `libs/pydegas`:

```bash
uv run pytest
uv run ruff check
uv run ruff format
uv run mypy
```

Tests marked `reference` need the submodule and are skipped without it.

`src/pydegas/parse/` holds ANTLR-generated parsers. Do not regenerate them:
the ASGMT and TRUNC parsers contain hand-written methods.

## degas-api

In `libs/degas-api`:

```bash
uv run degas-api migrate
uv run degas-api serve --reload
uv run pytest
uv run ruff check
uv run ruff format
uv run mypy
```

The service needs Redis on `localhost:6379`. Without Redis, set
`DEGAS_API_OPTIMIZATION_RATE_LIMITER__ENABLED=false`.

After changing a model in `src/degas_api/models/`, add a migration with
`uv run alembic revision --autogenerate -m "describe the change"`, review it in
`src/degas_api/migrations/versions/` and run `uv run degas-api migrate`.
`tests/test_migrations.py` fails when the models and the migrations differ.

`uv run python scripts/generate_trajectories.py` regenerates the CSVs in
`data/`.

## degas-ui

In `libs/degas-ui`:

| Command | Does |
|---|---|
| `npm run dev` | dev server on `http://localhost:5173`, proxying `/api` and `/health` to `http://127.0.0.1:8000` (override with `VITE_API_TARGET`) |
| `npm run build` | type-check and build into `dist/` |
| `npm run typecheck` | TypeScript check |
| `npm run lint` | ESLint; fails on any warning |
| `npm run format` | format with Prettier; `format:check` only checks |

## Pre-commit

```bash
uvx pre-commit install
uvx pre-commit run --all-files
```

The hooks run ruff, mypy, Prettier, ESLint and tsc per project, check the
lockfiles, and lint Dockerfiles and the compose file. The mypy, ESLint and tsc
hooks use the project environments, so create them first.

## Commit messages

Short, lowercase, imperative, no body: `add degas-api`.
