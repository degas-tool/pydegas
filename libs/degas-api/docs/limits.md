# Limits and caveats

`MAX_STEPS` and the other short upper-case names are variables with the prefix
`DEGAS_API_OPTIMIZATION_LIMITS__` ([Configuration](configuration.md#limits));
the numbers in parentheses are their defaults. All other limits are fixed.

## Admission

A run request passes these checks in order; the first failure ends it with an
`error` frame.

| Check | Limit | Error `kind` |
|---|---|---|
| first message | JSON text matching the [request model](endpoints.md#request) | `setup_error` |
| `n_steps` | at least 1 and at most `MAX_STEPS` (500) | `setup_error` |
| `Kmax` | at least 1 and below `MAX_KMAX` (100), or null, which leaves only `prune(k);` statements to bound the number of mixture components | `setup_error` |
| rate limiter | Redis answers | `setup_error` |
| client rate window | `RATE_LIMIT_REQUESTS` (20) requests per `RATE_LIMIT_WINDOW_SECONDS` (60) | `rate_limited` |
| run slots | `MAX_CONCURRENT_RUNS` (2) concurrent runs | `at_capacity` |

- The rate window and the run slots live in Redis and are shared by all API
  workers. With `DEGAS_API_OPTIMIZATION_RATE_LIMITER__ENABLED=false` both
  checks are skipped and `/health` always reports every slot free.
- The rate window is shared by runs and `/loss/validate`. The UI validates a
  custom loss each time typing pauses for 400 ms, so editing a loss uses the
  same budget as starting runs.
- A request refused for capacity is not queued and does not count against the
  rate window.
- The client is identified by `X-Real-IP`, else the first `X-Forwarded-For`
  entry, else the connection's address. The API trusts these headers, so a
  proxy in front of it must overwrite them; see
  [Running the service](running.md#behind-a-reverse-proxy).
- Every worker sets the run counter to 0 when it starts. A worker that starts
  while another worker is serving a run makes that run's slot free again, so
  more runs than the limit can be admitted until it ends.
- With the limiter enabled, the service does not start if Redis is
  unreachable. If Redis fails later, a run request ends with `setup_error`
  (`The rate limiter is unavailable. Please retry shortly.`) and
  `/loss/validate` returns 500.

## Run time and stopping

Steps run one at a time in a thread of the worker that holds the connection.

- The run time limit, `MAX_RUN_SECONDS` (300), starts after setup and is
  checked after each step. A long step overruns it. A step that never returns
  holds the run slot until the client stops or disconnects, and blocks its
  thread for good.
- After a [stop or disconnect](endpoints.md#stopping) the slot is freed at
  once, but the step in progress keeps running in its thread, so the slot
  count does not bound the computation in progress.

## Input sizes

| Input | Limit |
|---|---|
| `program` | 50 000 characters (fixed) |
| `loss_source`, `/loss/validate` source | 20 000 characters (fixed) |
| `loss_kwargs.trajectories`, `traj_set` bindings | `MAX_TRAJECTORY_ROWS` (500) rows; `MAX_TRAJECTORY_COLS` (200) values in the first row |
| session bodies (`request`, `steps`) | no limit in the API |

Only the first row of a trajectory is measured. Argument types are checked
before the run, see [Request](endpoints.md#request).

## Sessions

- There are no accounts. Anyone can list unexpired sessions and read any of
  them.
- Anyone can overwrite a session's `steps`, `status` and `outcome`. The owner
  token is needed only to rename or delete.
- The UI saves the steps after `end` or `error`. If the page closes first, the
  session keeps an empty step list and status `running`. There is no reconnect
  or replay of a run.
- An expired session disappears from list and read at once, but is deleted
  only by the cleanup that runs every
  `DEGAS_API_SESSION_CLEANUP_INTERVAL_HOURS` (6) hours. Until then `PATCH`
  and `DELETE` still work on it.

## Trust

- The API has no authentication. `DEGAS_API_ALLOWED_HOSTS` checks the `Host`
  header only; the WebSocket's `Origin` is not checked.
- Remote users cannot run Python: losses are written in the
  [loss DSL](../../pydegas/docs/loss-dsl.md) and optimizers are chosen
  by name.
- Runs are not isolated in CPU or memory.
