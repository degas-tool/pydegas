# Endpoints

## Overview

| Method | Path | Purpose |
|---|---|---|
| WS | `/api/optimization/ws` | [run one optimization](#optimization-run-websocket) |
| POST | `/api/optimization/loss/validate` | [check a loss DSL source](#loss-validation) |
| GET | `/api/optimization/loss-functions` | [built-in losses](#metadata) |
| GET | `/api/optimization/optimizers` | [optimizer names](#metadata) |
| GET | `/api/optimization/pruning-strategies` | [pruning strategy names](#metadata) |
| POST | `/api/sessions` | [create a session](#sessions) |
| GET | `/api/sessions` | list sessions |
| GET | `/api/sessions/{id}` | read a session |
| PATCH | `/api/sessions/{id}` | update a session |
| DELETE | `/api/sessions/{id}` | delete a session |
| GET | `/health` | `{"unix": <time>, "slots_free": <free run slots>, "max_concurrent": <MAX_CONCURRENT_RUNS>}` |
| GET | `/` | redirect (307) to the API documentation, unless `DEGAS_API_STATIC_DIR` serves a UI |

The API documentation (`DEGAS_API_DOCS_URL`, default `/docs`), `/redoc` and
`/openapi.json` describe the HTTP routes. The
WebSocket is not in the schema; it is described here. For the limits applied
to each request, see [Limits and caveats](limits.md).

## Optimization run (WebSocket)

One connection runs one optimization:

1. The client sends the request as the first message (JSON text).
2. The server sends `start`, one `step` per optimization step, and `end`. A
   `compute_error` takes the place of `end`; every other `error` takes the
   place of `start`.
3. The server closes the connection.

### Request

| Field | Type | Default | Meaning |
|---|---|---|---|
| `program` | string, at most 50 000 characters | required | program text |
| `program_language` | `"soga"` or `"soga_highlevel"` | `"soga"` | `soga_highlevel` is compiled with `compile_to_soga_text` first |
| `compile_seed` | integer or null | null | seed for that compilation |
| `smooth_eps` | number or null | null | smoothing width; null uses the library default `1e-3` |
| `loss_function` | string or null | null | a name from `/loss-functions` |
| `loss_kwargs` | object | `{}` | arguments of that loss |
| `loss_source` | string or null, at most 20 000 characters | null | a [loss DSL](../../pydegas/docs/loss-dsl.md) definition; if non-empty, `loss_function` is ignored |
| `loss_bindings` | object | `{}` | values for the DSL parameters other than the `dist` one |
| `optimizer` | string | required | a name from `/optimizers` |
| `optimizer_kwargs` | object | `{}` | passed to the torch optimizer; `{}` means `{"lr": 0.05}`, except for `LBFGS`: there `max_iter` defaults to 20 and is capped at 20, and without `lr` torch's default `lr` of 1 applies |
| `initial_params` | object of numbers | required | start values, named without the leading underscore (`_tOff` is `tOff`); must name every parameter of the program; an empty object is a `setup_error`, a missing parameter a `compute_error` at the first step |
| `n_steps` | integer | 100 | at least 1 and at most `MAX_STEPS` (500) |
| `Kmax` | integer or null | 20 | at least 1 and below `MAX_KMAX` (100); null disables pruning after `end if` |
| `pruning` | `"classic"`, `"ranking"` or `"kmeans"` | `"classic"` | pruning strategy |
| `tolerance` | number ≥ 0 or null | `1e-8` | null disables the convergence stop |
| `patience` | integer ≥ 1 | 30 | number of loss changes that must stay below `tolerance` |
| `return_dist_summary` | boolean | true | include `dist` in `step` frames |

`loss_function` or a non-empty `loss_source` must be set. Unknown fields are
ignored. Upper-case names are configurable [limits](limits.md).

Trajectory arguments (`loss_kwargs.trajectories` and bindings annotated
`traj_set`) are arrays of equal-length rows, one row per observation. Values
are converted by their annotation, or for built-in losses by their `type`:
`traj_set` or `float[][]` and `scalar` or `float` to float64 tensors,
`index_list` or `int[]` to integers (`1.0` is accepted, `1.5` and `true` are
not), `int` to an integer; unannotated bindings are passed as they are. A value
that cannot be converted, a missing argument or an unknown built-in loss
argument is a `setup_error`; unknown `loss_bindings` are ignored. A value of
the right type that does not fit the program, such as an index out of range,
is a `compute_error` at the first step. See
[Losses](../../pydegas/docs/losses.md) for what the built-in losses compute.

Example: three Adam steps, fitting `_tOff` to one observed trajectory.

```json
{
  "program": "array[3] T;\ncurrT = 16;\nfor i in range(3) {\nT[i] = currT;\nif currT > _tOff { heat = -0.5; } else { heat = 0.5; } end if;\ncurrT = currT + heat + gauss(0., 0.1);\n} end for;",
  "program_language": "soga_highlevel",
  "compile_seed": 0,
  "optimizer": "Adam",
  "optimizer_kwargs": {"lr": 0.1},
  "initial_params": {"tOff": 16.0},
  "loss_function": "l2_distance",
  "loss_kwargs": {"trajectories": [[16.0, 15.5, 15.0]], "indices": [0, 1, 2]},
  "n_steps": 3,
  "tolerance": null
}
```

### Frames

| `type` | Fields |
|---|---|
| `start` | `n_steps` |
| `step` | `step` (from 0), `loss`, `params`, `elapsed_ms`, `dist` (`{"var_list": [...], "mean": [...]}` or null) |
| `end` | `outcome`, `converged` (boolean) and `final_params`, both from the last `step` sent; with no step sent, `false` and the initial values |
| `error` | `kind`, `detail` (message) |

`loss` is evaluated at the parameters before the step's update; `params` are
the values after it.

The server's answer to the example request (frames for steps 1 and 2 left out):

```
{"type":"start","n_steps":3}
{"type":"step","step":0,"loss":2.000629727549886,"params":{"tOff":15.900000043212433},"elapsed_ms":77.90387503337115,"dist":{"var_list":["T[0]","T[1]","T[2]","currT","heat"],"mean":[16.0,16.499999999999996,16.00031481422095,16.368308952478866,0.3679941382579221]}}
{"type":"end","outcome":"not_converged","converged":false,"final_params":{"tOff":15.778461968230024}}
```

| `outcome` | Meaning |
|---|---|
| `converged` | the last `patience` loss changes were all below `tolerance`; the run stops at that step |
| `not_converged` | all `n_steps` steps ran |
| `stopped` | the client sent a message after the request |
| `run_timeout` | the run time limit `MAX_RUN_SECONDS` (300 s) passed; checked after each step |

| `kind` | Cause |
|---|---|
| `setup_error` | first message not JSON text, invalid request (including `n_steps` or `Kmax` out of range), rate limiter unavailable, malformed or oversized trajectory or binding, program or loss that does not compile, unknown optimizer or loss, missing or rejected loss or optimizer arguments |
| `rate_limited` | too many requests from this client in the rate window |
| `at_capacity` | all run slots are taken; retry later |
| `compute_error` | an exception while computing a step (for example a built-in loss index out of range, or a program parameter missing from `initial_params`), or a step whose loss, a parameter or a reported mean is NaN or infinite |

With the default `MAX_STEPS`:

```
{"type":"error","kind":"setup_error","detail":"n_steps=501 exceeds the maximum of 500."}
{"type":"error","kind":"compute_error","detail":"Step 0 produced a non-finite loss, parameter or mean (NaN or infinity); the run was stopped."}
```

### Stopping

Any message sent after the request, text or binary, stops the run: the server
sends `end` with `stopped` and closes the connection. The step being computed
is not interrupted. Closing the connection also stops the run; no frame is
sent.

## Loss validation

`POST /api/optimization/loss/validate` with `{"source": "<DSL text>"}` (at
most 20 000 characters):

```json
{
  "errors": [],
  "params": [
    {"name": "trajectories", "type": "traj_set"},
    {"name": "indices", "type": "index_list"}
  ]
}
```

- `errors` are strings `line <line>:<column> <message>`; the column starts at 0.
- `params` lists the parameters other than the `dist` one, with their
  annotation or `null`. It is empty when there are errors.
- Each call counts against the client's rate window; over the limit the
  response is 429 with a `Retry-After` header.

## Metadata

| Path | Response |
|---|---|
| `/api/optimization/loss-functions` | `[{"name", "params": [{"name", "type", "required", "default"}], "definition"}]`; `type` is `float`, `int`, `float[][]` or `int[]`; `definition` is DSL text for the loss or null |
| `/api/optimization/optimizers` | `["Adam", "AdamW", "SGD", "RMSprop", "Adagrad", "LBFGS"]` |
| `/api/optimization/pruning-strategies` | `["classic", "ranking", "kmeans"]` |

## Sessions

A session stores a run request and its results. The run itself does not write
to it: the client creates the session, runs the optimization, and saves the
steps with `PATCH`.

| Field | Content |
|---|---|
| `id` | 8-character identifier |
| `created_at`, `expires_at` | UTC, without a time zone suffix |
| `loss_mode`, `loss_name` | strings chosen by the client (the UI uses `builtin` or `custom`) |
| `name` | display name or null |
| `request` | the run request as JSON text; stored without validation |
| `steps` | list as sent by the client (the UI sends the `step` frames) |
| `status` | string, `running` after creation |
| `outcome` | string or null |

| Request | Body | Response | Owner token |
|---|---|---|---|
| `POST /api/sessions` | `loss_mode`, `loss_name`, `request` | 201, the session plus `owner_token` | returned only here |
| `GET /api/sessions?limit=50` | | summaries (`id`, `created_at`, `loss_mode`, `loss_name`, `name`, `status`, `outcome`) of unexpired sessions, newest first; `limit` 1 to 100 (default 50), else 422 | not needed |
| `GET /api/sessions/{id}` | | the session; 404 if missing or expired | not needed |
| `PATCH /api/sessions/{id}` | any of `steps`, `status`, `outcome`, `name` | the session; 404 if missing, but an expired session can still be changed | needed only for `name` |
| `DELETE /api/sessions/{id}` | | 204; 404 if missing | needed |

- The token goes in the `X-Owner-Token` header; a missing or wrong token
  gives 403, and the request changes nothing.
- `PATCH` changes only the fields that are present and not null. A blank
  `name` clears it.
- A session expires `DEGAS_API_SESSION_TTL_DAYS` (default 1) days after it
  was created or last read; every `GET` of the session resets that time.
  `PATCH` does not.

## Response headers

HTTP responses carry `DeGAS-Request-Id` (the client's `DeGAS-Request-Id`
header if sent, else a generated `req_<uuid>`), `DeGAS-Api-Version`,
`DeGAS-Request-Duration-ms`, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` and `Referrer-Policy: strict-origin-when-cross-origin`.
Two responses carry none of them: 400 `Invalid host header` for a `Host` not
in `DEGAS_API_ALLOWED_HOSTS`, and the 500 of an unhandled error,
`{"error": "Internal server error", "request_id": "<id>"}`.
