# Losses

A loss takes the output `Dist` and returns a scalar tensor. Pass it to
`OptimizationRun` or `optimize`. A loss can be a Python function, a
[built-in loss](#built-in-losses) or a [loss DSL](loss-dsl.md) definition
compiled with `compile_loss`.

## Python losses

The program below is a random walk with drift `_mu`. The loss pulls the mean
of the last position `X[4]` to 2.

```python
from pydegas.cfg import smooth
from pydegas.cfg.builder import from_text
from pydegas.optimize import OptimizationRun
from pydegas.parse.preprocessor import compile_to_soga_text

program = """
array[5] X;
x = 0.;
for i in range(5) {
    x = x + _mu + gauss(0., 0.1);
    X[i] = x;
} end for;
"""

cfg = from_text(compile_to_soga_text(program))
smooth(cfg)
last = cfg.ID_list.index("X[4]")


def final_mean(dist):
    return (dist.gm.mean()[last] - 2.0) ** 2


run = OptimizationRun(cfg, {"mu": 0.0}, final_mean, optimizer_kwargs={"lr": 0.1})
print(round(run.run(100)[-1].params["mu"], 3))
```

Output:

```text
0.399
```

The mean of `X[4]` is `5*mu`, so `mu` approaches 0.4. The `Dist` attributes
are listed in [The output `Dist`](language.md#the-output-dist).

## Built-in losses

`get_loss(name, **kwargs)` from `pydegas.optimize` builds a built-in loss:

```python
loss_fn = get_loss("l2_distance", trajectories=data, indices=[0, 1])
```

`trajectories` is a 2-D tensor with one row per observation and one column per
variable, in `cfg.ID_list` order. `indices` selects the variables to compare.

| Name | Arguments | Value |
|---|---|---|
| `neg_log_likelihood` | `trajectories`, `indices` | minus the sum over rows of the log marginal density of `trajectories[:, indices]` |
| `l2_distance` | `trajectories`, `indices` | `sum((trajectories[:, indices] - mean[indices]) ** 2)` |
| `signal_error` | `target=3.14`, `time_steps=50` | `sum((mean[1:time_steps] - target) ** 2)`; `ConfigurationError` if the program has fewer than `time_steps` variables |

`mean` is `dist.gm.mean()`. The names are the keys
of `LOSS_REGISTRY`, and `LOSS_PARAM_SCHEMA` lists each loss's arguments with
their type and default.
