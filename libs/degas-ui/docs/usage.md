# Using the interface

The left column holds the program editor, the loss editor and the toolbar;
the right column holds the results plot and the parameter-trajectory plot.
The dividers between panels can be dragged. The header has the history
(**previous runs**), **+ new**, the number of free run slots on the server,
and the light/dark switch; until the switch is used, the theme follows the
system setting.

- [Program and parameters](#program-and-parameters)
- [Loss](#loss)
- [Loss arguments](#loss-arguments)
- [Run settings](#run-settings)
- [Examples](#examples)
- [Running and results](#running-and-results)
- [Export](#export)
- [History and sharing](#history-and-sharing)

## Program and parameters

The program is written in the high-level [program language](../../pydegas/docs/language.md)
and compiled by the API with seed 0. Syntax errors are reported when a run
starts.

Every `_name` in the program text (an underscore, a letter, then letters and
digits) gets a field under **initial parameters**, also when it appears in a
comment. A new name starts at 0.

## Loss

| Mode | Loss editor | Sent to the API |
|---|---|---|
| built-in (default) | read-only DSL text of the selected loss | the loss name and its arguments |
| **custom** | editable [loss DSL](../../pydegas/docs/loss-dsl.md) | the editor text and its bindings |

- Switching to **custom** fills the editor with the selected built-in loss if
  the editor holds unedited text. **load <name> definition** does this on
  request.
- The custom loss is validated 400 ms after typing stops. Errors appear as
  markers at their line and column, with an error count above the editor.
  Run is disabled while errors remain.
- Each validation counts against the API's
  [rate limit](../../degas-api/docs/limits.md#admission). A refused
  validation leaves the markers and the argument fields unchanged.

## Loss arguments

The fields under **loss arguments** come from the selected built-in loss, or
from the parameters the custom loss declares (except the `dist` one).

| Built-in type | DSL annotation | Field | Sent as |
|---|---|---|---|
| `float` | `scalar` | number | number |
| `int` | `int` | number | integer |
| `int[]` | `index_list` | `0, 1, 2` | list of integers; an invalid entry is 0 |
| `float[][]` | `traj_set` | CSV upload | list of rows |
| | none | JSON text | parsed JSON, or the text itself |

A built-in loss is sent only the arguments it declares. An empty built-in
field is left out of the request, so the loss's default applies; number fields
show that default as a placeholder. A required argument left empty makes the
run fail with a `setup_error`. An empty or invalid DSL `scalar` or `int` field
sends 0.

CSV files for trajectories:

- comma-separated numbers, no header line, one row per trajectory;
- for the built-in losses, column `i` is compared with program variable `i`
  (see [Losses](../../pydegas/docs/losses.md#built-in-losses));
- a cell that is not a number makes the run fail with a `setup_error`;
- at most 500 rows and 200 columns.

After an upload the field shows rows × columns. For a
built-in loss an empty `indices` field is filled with `0, 1, …, columns - 1`.
`libs/degas-api/data/` has trajectories for the thermostat, gearbox and
bouncing-ball examples.

## Run settings

| Control | Request field | Initial value | Notes |
|---|---|---|---|
| optimizer | `optimizer` | Adam | names from the API |
| lr | `optimizer_kwargs.lr` | from the example | the only optimizer argument the UI sets; empty is left out, so the optimizer's default applies |
| steps | `n_steps` | from the example | the API allows 1 to 500; empty sends 0, which fails with a `setup_error`; with LBFGS each step runs up to 20 iterations |
| tol | `tolerance` | `1e-8` | empty disables the convergence stop |
| patience | `patience` | 30 | empty or 0 sends 30 |
| smooth_eps | `smooth_eps` | 0.001 | empty uses the library default |
| pruning | `pruning` | from the example | names from the API, or `classic`, `ranking`, `kmeans` if they cannot be loaded |

`Kmax` is not sent, so runs use the API default of 20. The meaning of each
field: [request](../../degas-api/docs/endpoints.md#request).

## Examples

| Example | Initial parameters | Loss | Loss arguments | lr | Steps |
|---|---|---|---|---|---|
| Thermostat | `_tOff` 22, `_tOn` 15 | `signal_error` | `target` 18, `time_steps` 31 | 0.2 | 100 |
| Gearbox | `_s1` 8, `_s2` 12 | `signal_error` | `target` 15, `time_steps` 21 | 0.3 | 200 |
| PID | `_s0` 46, `_s1` −23, `_s2` 0 | `signal_error` | `target` 3.14, `time_steps` 51 | 0.2 | 500 |
| BouncingBall | `_R` −1, `_C` 450 | `l2_distance` | upload `bouncing_ball_trajectories.csv` | 0.8 | 100 |

All use Adam and `kmeans` pruning, and each program prunes to 10 components
with `prune(10)` in its loop. Selecting an example sets the program,
optimizer, lr, pruning, the built-in loss (leaving custom mode), loss
arguments, initial parameters and steps; tol, patience and smooth_eps keep
their current values. Editing the program switches the selector to Custom.

## Running and results

**Run** (▶) saves a new session, puts `?s=<id>` in the address without adding
a browser history entry, and starts the run. While it runs, **Stop** (■) asks
the server to stop; the run ends when the server answers, after the
[step in progress](../../degas-api/docs/limits.md#run-time-and-stopping).
**Stop** before the connection is open ends the run at once as stopped.

The results plot shows the loss (left axis) and each parameter (right axis)
per step, updated as steps arrive. The pills above it hide and show traces.
The lower plot shows the parameter values alone. The loss of a step is
computed before that step's parameter update, the plotted parameter values
after it. The previous run's plots stay until the first step arrives; a run
that fails or is stopped before its first step clears them.

After the run, the panel shows a badge and, unless the run failed, the number
of steps and the final parameter values:

| Badge | Cause |
|---|---|
| converged | the loss changed by less than `tol` for `patience` steps |
| not converged | all steps ran |
| stopped | **Stop** was pressed |
| timed out | the server's run time limit (300 s by default) passed |
| failed | the server reported an error, or the connection could not be opened or was lost |

A failure message is prefixed `Rate limited:`, `Server busy:` (no free run
slot) or `Optimization failed:` (error during a step); setup errors are shown
as the API sends them. The message "Could not connect to the server." means
the connection could not be opened. If no step arrives for 15 s, a warning
suggests checking the loss arguments and learning rate or stopping the run.

## Export

The **data** button downloads `degas-run-<time>.json` for the run shown: a
run started in this page once it has ended, or a session opened from the
history or a link. It is disabled during a run and when there are no steps;
its tooltip says why.

| Field | Content |
|---|---|
| `schema_version` | 1 |
| `exported_at` | time of the export |
| `outcome` | outcome, or the error kind (for example `connection_lost`); `error` for an opened session that failed |
| `error` | error message, or null (always null for an opened session) |
| `timing` | `engine_compute_ms` (sum of step times), `wall_clock_ms` (measured in the browser; null for an opened session), `n_steps` (steps received) |
| `config` | the request the run was started with: `program`, `program_language`, `optimizer`, `optimizer_kwargs`, `n_steps`, `tolerance`, `patience`, `smooth_eps`, `pruning`, `initial_params`, `loss` (`mode` with `name` and `kwargs`, or `source` and `bindings`) |
| `final_params` | parameters after the last step |
| `steps` | `step`, `loss`, `params`, `elapsed_ms` per step |

The export leaves out `compile_seed` (0), `Kmax` (API default) and the
distribution means of each step.

## History and sharing

- A link with `?s=<id>` opens a saved session: the program, the loss (name,
  or custom text), the steps and the outcome; a failed session shows
  **failed**. The loss arguments, initial parameters and run settings are not
  restored, so running again uses the toolbar's values, not the saved ones.
- **previous runs** lists the 50 newest sessions on the server, from all
  users. Rename and delete appear only for sessions created in this browser.
  A rename or delete the server refuses (for example with 403) leaves the
  list unchanged and shows the error for five seconds. Deleting the open session removes it from the address.
- Every run creates a new session. **+ new** only removes the session from
  the address.
- Only a run started in this page saves its steps, once, when the run ends or
  fails; opening a session never overwrites it. If the page is closed or
  reloaded during a run, the session keeps no steps.
- A session expires one day after it was created or last opened. Anyone with
  the link can open it; see
  [session caveats](../../degas-api/docs/limits.md#sessions).
