# Limits and caveats

Limits named by a variable are configurable, and the number in parentheses is
the default. `MAX_STEPS` and the other upper-case names are the variables with
the prefix `DEGAS_API_OPTIMIZATION_LIMITS__`; see
[Configuration](configuration.md#limits). All other limits are fixed in the
code.

- [Admission](#admission)
- [Run time and stopping](#run-time-and-stopping)
- [Input sizes](#input-sizes)
- [Sessions](#sessions)
- [Trust](#trust)

## Admission

A run request passes these checks in order; the first failure ends it with an
`error` frame.

| Check | Limit | Error `kind` |
|---|---|---|
| first message | JSON text matching the [request model](endpoints.md#request) | `setup_error` |
| `n_steps` | at most `MAX_STEPS` (500) | `setup_error` |
| `Kmax` | below `MAX_KMAX` (100), or null | `setup_error` |
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
  checked after each step. A long step overruns it. A step that never returns holds the run slot until
  the client stops or disconnects, and blocks its thread for good.
- Stop and disconnect take effect at once: the server answers `stopped` (or
  nothing, after a disconnect) and frees the slot. The step being computed
  keeps running in its thread and its result is discarded. The slot count
  therefore does not bound the computation still in progress.
- `LBFGS` runs at most 20 inner iterations per step (fixed).

## Input sizes

| Input | Limit |
|---|---|
| `program` | 50 000 characters (fixed) |
| `loss_source`, `/loss/validate` source | 20 000 characters (fixed) |
| `n_steps` | at least 1 and at most `MAX_STEPS` (500) |
| `Kmax` | at least 1 and below `MAX_KMAX` (100); `null` disables pruning at merges, so the limit does not bound the number of mixture components |
| `loss_kwargs.trajectories`, `traj_set` bindings | `MAX_TRAJECTORY_ROWS` (500) rows; `MAX_TRAJECTORY_COLS` (200) values in the first row |
| session bodies (`request`, `steps`) | no limit in the API |

A trajectory must be an array of rows; only its first row is measured. Rows of
different lengths are rejected with `setup_error` when the tensor is built.
Built-in loss arguments and DSL bindings are checked by type before the run:
index lists must hold integers (`1.0` is accepted, `1.5` and `true` are not),
numbers must be numbers. A wrong type, a missing or an unknown argument is a
`setup_error`; a value that fits its type but not the program, such as an index
out of range, fails at the first step with `compute_error`.

## Sessions

- There are no accounts. Anyone can list all unexpired sessions and read any
  of them.
- Anyone can overwrite a session's `steps`, `status` and `outcome`. The owner
  token is needed only to rename or delete.
- `request` is stored without validation; `status` and `outcome` are free text.
- The run does not save its steps. The client saves them in one `PATCH` after
  the run ends; the UI does this after `end` or `error`. If the page closes
  first, the session keeps an empty step list and status `running`. There is
  no reconnect or replay of a run.
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
