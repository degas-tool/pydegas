# Optimization

`OptimizationRun` in `pydegas.optimize` fits a smoothed program's parameters:

```python
OptimizationRun(cfg, initial_params, loss_fn, optimizer="Adam", *,
                optimizer_kwargs=None, tolerance=1e-8, patience=30,
                on_step=None, Kmax=None, pruning="classic")
```

| Argument | Meaning |
|---|---|
| `initial_params` | start values as floats (`0.0`, not `0`), by parameter name without the underscore; the run keeps the current values as tensors in `run.params` |
| `loss_fn` | a [loss](losses.md) |
| `optimizer` | a name from `OPTIMIZER_REGISTRY` (`Adam`, `AdamW`, `SGD`, `RMSprop`, `Adagrad`, `LBFGS`) or a `torch.optim.Optimizer` subclass |
| `optimizer_kwargs` | passed to the optimizer; `{"lr": 0.05}` when omitted, otherwise the optimizer's own `lr` default applies |
| `tolerance`, `patience` | stop once the last `patience` changes of the loss are all smaller than `tolerance`; `tolerance=None` turns this off |
| `on_step` | called with each step result; returning true stops the run after that step |
| `Kmax`, `pruning` | see [Mixtures and pruning](concepts.md#mixtures-and-pruning) |

## Steps

`run.run(n_steps)` returns the step results as a list; `run.run_generator(n_steps)`
yields them one at a time. Calling either again continues from the current
parameters, optimizer state and loss history, with `step` starting at 0.

Each step gives a `StepResult`:

| Field | Meaning |
|---|---|
| `step` | step index, starting at 0 |
| `loss` | loss before the update |
| `params` | parameter values (floats) after the update |
| `dist` | the output distribution before the update |
| `elapsed_ms` | duration of the step |
| `converged` | whether the loss has converged after this step |

With the default `patience=30`, a new run cannot converge before step 30.

`LBFGS` evaluates the program several times per step; `loss` and `dist` come
from its last evaluation. With `cfg` and `loss_fn` from
[Getting started](getting-started.md):

```python
run = OptimizationRun(cfg, {"a": 0.0, "b": 0.0}, loss_fn, "LBFGS",
                      optimizer_kwargs={"lr": 1.0}, patience=2)
for result in run.run_generator(20):
    print(result.step, round(result.loss, 1), {k: round(v, 2) for k, v in result.params.items()}, result.converged)
```

Output:

```text
0 434.6 {'a': 1.96, 'b': 0.98} False
1 434.6 {'a': 1.96, 'b': 0.98} False
2 434.6 {'a': 1.96, 'b': 0.98} True
```

## One call

```python
optimize(cfg, initial_params, loss_fn, n_steps=100, optimizer="Adam", *,
         optimizer_kwargs=None, **run_kwargs)
```

creates an `OptimizationRun` with the remaining keyword arguments, runs it and
returns the run. Read the fitted values from `run.params`.
