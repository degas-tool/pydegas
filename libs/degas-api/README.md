# degas-api

FastAPI service built on [pydegas](../pydegas). It validates loss definitions,
streams optimization runs step by step over a WebSocket, and stores runs as
shareable sessions. Redis holds the concurrency and rate limits; sessions are
stored in SQLite.

```bash
uv sync
uv run degas-api migrate
uv run degas-api serve --reload
```

## Documentation

- [Running the service](docs/running.md)
- [Command line](docs/cli.md)
- [Configuration](docs/configuration.md)
- [Endpoints](docs/endpoints.md)
- [Limits and caveats](docs/limits.md)
