from __future__ import annotations

import http.client
import os
import urllib.error
import urllib.request
from importlib.metadata import version as package_version
from typing import Annotated

import typer
import uvicorn

from degas_api import __version__, migrate
from degas_api.settings import app_settings


APP_IMPORT_STRING = "degas_api.server:create_app"
LOG_LEVELS = ["critical", "error", "warning", "info", "debug"]

app = typer.Typer(
    help="Run and maintain the DeGAS API service.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def _log_level(value: str) -> str:
    if value.lower() not in LOG_LEVELS:
        raise typer.BadParameter(f"{value!r} is not one of {', '.join(LOG_LEVELS)}")
    return value.lower()


def _use_settings(host: str, port: int, log_level: str) -> None:
    app_settings.host = host
    app_settings.port = port
    app_settings.logging.level = log_level.upper()
    os.environ["DEGAS_API_HOST"] = host
    os.environ["DEGAS_API_PORT"] = str(port)
    os.environ["DEGAS_API_LOGGING__LEVEL"] = log_level.upper()


@app.command()
def serve(
    host: Annotated[
        str, typer.Option(help="Address to listen on; DEGAS_API_HOST sets the default.")
    ] = app_settings.host,
    port: Annotated[int, typer.Option(help="Port to listen on; DEGAS_API_PORT sets the default.")] = app_settings.port,
    workers: Annotated[int, typer.Option(min=1, help="Number of worker processes.")] = 1,
    reload: Annotated[bool, typer.Option(help="Restart on source changes, for development.")] = False,
    log_level: Annotated[
        str,
        typer.Option(
            callback=_log_level,
            help=f"Log level, one of {', '.join(LOG_LEVELS)}; DEGAS_API_LOGGING__LEVEL sets the default.",
        ),
    ] = app_settings.logging.level,
) -> None:
    """Start the service with uvicorn. The database must be migrated first."""
    if reload and workers > 1:
        raise typer.BadParameter("--reload works with a single worker only", param_hint="'--workers'")

    try:
        migrate.check_schema(app_settings.db_path)
    except migrate.DatabaseNotMigratedError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None

    _use_settings(host, port, log_level)
    uvicorn.run(
        APP_IMPORT_STRING,
        factory=True,
        host=host,
        port=port,
        workers=workers,
        reload=reload,
        log_level=log_level,
    )


@app.command("migrate")
def migrate_command(
    revision: Annotated[str, typer.Option(help="Revision to upgrade to.")] = "head",
) -> None:
    """Upgrade the session database (DEGAS_API_DB_PATH) to the latest schema.

    A database created before migrations existed is stamped with the baseline revision first.
    """
    migrate.run(revision)


@app.command()
def health(
    url: Annotated[str, typer.Option(help="Base URL of the service.")] = "http://localhost:8000",
    timeout: Annotated[float, typer.Option(help="Seconds to wait for an answer.")] = 5.0,
) -> None:
    """Query GET /health and print the answer. Exits 0 on HTTP 200, 1 otherwise."""
    target = f"{url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(target, timeout=timeout) as response:
            status = response.status
            body = response.read().decode()
    except urllib.error.HTTPError as exc:
        typer.echo(f"Error: {target} answered HTTP {exc.code}", err=True)
        raise typer.Exit(1) from None
    except (OSError, ValueError, http.client.HTTPException) as exc:
        typer.echo(f"Error: cannot reach {target}: {getattr(exc, 'reason', exc)}", err=True)
        raise typer.Exit(1) from None

    if status != 200:
        typer.echo(f"Error: {target} answered HTTP {status}", err=True)
        raise typer.Exit(1)
    typer.echo(body)


@app.command()
def version() -> None:
    """Print the degas-api and pydegas versions."""
    typer.echo(f"degas-api {__version__}")
    typer.echo(f"pydegas {package_version('pydegas')}")
