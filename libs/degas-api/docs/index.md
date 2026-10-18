# degas-api documentation

degas-api exposes pydegas over HTTP and a WebSocket. It calls the library in
process, admits a bounded number of concurrent runs, and stores saved runs.

| Page | Contents |
|---|---|
| [Command line](cli.md) | `degas-api migrate`, `serve`, `health`, `version`, schema changes |
| [Running the service](running.md) | from source, Redis, Docker image, reverse proxy, trajectory data |
| [Configuration](configuration.md) | environment variables |
| [Endpoints](endpoints.md) | HTTP routes, the WebSocket run protocol, sessions |
| [Limits and caveats](limits.md) | admission, run time, input sizes, session access |

To run the API together with the web interface, use the
[local stack](../../../docs/local-stack.md). To work on the code, see
[CONTRIBUTING](../../../CONTRIBUTING.md#degas-api).
