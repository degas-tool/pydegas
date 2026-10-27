# Loss DSL

The loss DSL describes a loss as text. `compile_loss` turns it into a loss that
is evaluated with PyTorch operations and used like a Python loss; the text is
never run as Python. The grammar is
[`src/pydegas/grammars/DeGASLoss.g4`](../src/pydegas/grammars/DeGASLoss.g4).

## Example

The random walk `cfg` from [Losses](losses.md#python-losses), whose
`cfg.ID_list` is `['X[0]', 'X[1]', 'X[2]', 'X[3]', 'X[4]', 'x']`, fitted to two
observed walks by the mean squared error of `X[0]` to `X[4]`:

```python
import torch

from pydegas.optimize import OptimizationRun
from pydegas.optimize.dsl import compile_loss

source = """
loss mse(d: dist, data: traj_set, idx: index_list) =
    error = data[:, idx] - d.mean[idx];
    mean_agg(error ^ 2)
"""

data = torch.tensor([
    [0.5, 0.9, 1.3, 1.7, 2.1, 2.1],
    [0.3, 0.7, 1.1, 1.5, 1.9, 1.9],
])
loss_fn = compile_loss(source, data=data, idx=[0, 1, 2, 3, 4])
run = OptimizationRun(cfg, {"mu": 0.0}, loss_fn, optimizer_kwargs={"lr": 0.1})
print(round(run.run(100)[-1].params["mu"], 3))
```

Output:

```text
0.399
```

The observed walks move 0.4 per step on average, so `mu` approaches 0.4.

## Python interface

In `pydegas.optimize.dsl`:

| Function | Returns |
|---|---|
| `compile_loss(source, **bindings)` | the loss of the first definition in `source` |
| `validate_loss(source)` | the syntax errors as `"line L:C message"` strings; `[]` if `source` parses |
| `extract_params(source)` | the parameters of the first definition except the `dist` one, as `[{"name": ..., "type": ...}]`; `[]` on a syntax error |

`LOSS_DSL_SOURCE` in `pydegas.optimize` holds DSL versions of the
[built-in losses](losses.md#built-in-losses) with the same argument names. Its
`signal_error` fixes `time_steps` at 50 and has no default `target`, and its
`neg_log_likelihood` can be infinite where the built-in loss is finite, see
[Expressions](#expressions).

## Definitions

```
loss <name>(<param>: <type>, ...) =
    <local> = <expr>;
    <expr>
```

- Zero or more assignments, each ending in `;`, then the final expression,
  which is the loss value and has no `;`. It must be a scalar: reduce vectors
  with `sum`, `mean_agg`, `max` or `min`.
- Assignments run in order. Only expressions can be assigned, not index
  lists.
- Names are letters, digits and `_`, not starting with a digit, and are
  case-sensitive. Keywords cannot be names: `loss`, `dist`, `traj_set`,
  `index_list`, `scalar`, `int`, `mean`, `var`, `pdf`, `marg_pdf`, `log`,
  `exp`, `abs`, `sqrt`, `sum`, `mean_agg`, `max`, `min`, `range`, `ones`.

## Parameters

One parameter is annotated `dist` and receives the distribution. Bind every
other parameter by keyword in `compile_loss`. Only `dist` is checked; the other
annotations document what to bind.

| Annotation | Bind |
|---|---|
| `traj_set` | 2-D tensor, one row per observation, columns in `cfg.ID_list` order |
| `index_list` | list of int |
| `scalar` | number or 0-dim tensor |
| `int` | int |
| none | any value |

A number used as a function argument must be a tensor: bind
`torch.tensor(3.0)`, not `3.0`, if the loss calls `sum(t)`.

## Expressions

`d` is the `dist` parameter. Positions are zero-based indices into
`cfg.ID_list`.

| Syntax | Value |
|---|---|
| `d.mean()`, `d.var()` | means and variances of all variables |
| `d.mean[idx]`, `d.var[idx]` | means and variances at `idx` |
| `d.marg_pdf(v, idx)` | density of the variables `idx` at each row of `v`, shape (N, 1); column `j` of `v` holds variable `idx[j]`; `idx` must be a list or range |
| `v[:, idx]` | the columns `idx` of every row of `v` |
| `sum(e)`, `max(e)`, `min(e)`, `mean_agg(e)` | sum, maximum, minimum and mean over all elements |
| `log(e)`, `exp(e)`, `abs(e)`, `sqrt(e)` | element by element |
| `ones(idx)` | a vector of ones, one entry per index |
| `+`, `-`, `*`, `/`, `^` | element by element, with broadcasting |

`idx` is a list of integers `[0, 2]`, a range `range(0, 5)` (0 to 4, both
bounds written out), a single integer `3`, or a bound name. Write `d.mean[[0, 2]]`, not
`d.mean[0, 2]`.

`v` in `d.marg_pdf(v, idx)` must be a name, so slice into a local first:

```
loss nll(d: dist, data: traj_set, idx: index_list) =
    observed = data[:, idx];
    - sum( log( d.marg_pdf(observed, idx) ) )
```

`log(d.marg_pdf(...))` is infinite where the density underflows to 0, for data
far from the distribution.

`^` is evaluated before `*` and `/`, which are evaluated before `+` and `-`.
`^` groups right to left, and unary `-` applies first, so `-2 ^ 2` is `4`. Numbers may use exponents
(`1e-3`). Comments are `// to end of line` and `/* block */`.

## Errors

```python
from pydegas.optimize.dsl import validate_loss

print(validate_loss("loss f(d: dist) = sum(d.mean()"))
```

Output:

```text
["line 1:30 no viable alternative at input 'sum(d.mean()'"]
```

Lines count from 1, columns from 0.

| Failure | Raised |
|---|---|
| syntax error, no `dist` parameter, missing binding | `LossCompileError` from `compile_loss` |
| undefined name | `LossCompileError` when the loss is called |
| out-of-range index, wrong data shape or type | the PyTorch or Python exception, such as `IndexError` or `TypeError`, when the loss is called |
| non-scalar result | `RuntimeError` when `OptimizationRun` steps |
