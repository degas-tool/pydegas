# Local stack

Runs the UI, the API and Redis in Docker. Requires Docker with Compose and
[just](https://github.com/casey/just#installation). On Windows, run the
commands in WSL 2.

```bash
just up
```

Then open `http://localhost:3000` (UI) and `http://localhost:3000/docs` (API).
The `migrate` service upgrades the session database and exits before the API
starts.

| Command | Does |
|---|---|
| `just up` | build if needed, start, wait until ready |
| `just down` | stop; saved sessions are kept |
| `just status` | show containers and check the endpoints |
| `just logs` | follow the logs |
| `just rebuild` | rebuild the images from scratch and start |
| `just reset` | stop and delete saved sessions |

`just prod <command>` uses the production configuration: `compose.yaml`
without `compose.local.yaml`, for a host where Caddy routes `/api` to the API.
