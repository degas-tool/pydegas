# Getting started

## Installation

pydegas requires Python 3.12 or newer.

```bash
uv add pydegas
```

## A first fit

The program has two parameters, `_a` and `_b`. The script fits them to 200
noisy samples of `y = 2x + 1` by minimizing the negative log-likelihood of the
samples.

```python
import torch

from pydegas.cfg import smooth
from pydegas.cfg.builder import from_text
from pydegas.optimize import OptimizationRun, get_loss
from pydegas.parse.preprocessor import compile_to_soga_text

program = """
x = gauss(0., 1.);
y = _a*x + _b + gauss(0., 0.5);
"""

cfg = from_text(compile_to_soga_text(program))
smooth(cfg)
print(cfg.ID_list)

torch.manual_seed(0)
xs = torch.randn(200)
data = torch.stack([xs, 2.0 * xs + 1.0 + 0.5 * torch.randn(200)], dim=1)

loss_fn = get_loss("neg_log_likelihood", trajectories=data, indices=[0, 1])
run = OptimizationRun(cfg, {"a": 0.0, "b": 0.0}, loss_fn, optimizer_kwargs={"lr": 0.1})

for result in run.run_generator(200):
    if result.step % 50 == 0:
        print(result.step, round(result.loss, 1), {k: round(v, 2) for k, v in result.params.items()})
```

Output:

```text
['x', 'y']
0 2216.1 {'a': 0.1, 'b': 0.1}
50 436.2 {'a': 2.0, 'b': 1.01}
100 434.6 {'a': 1.97, 'b': 0.97}
150 434.6 {'a': 1.96, 'b': 0.98}
```

1. `compile_to_soga_text` turns `gauss(...)` into a Gaussian mixture term,
   `from_text` parses the program and `smooth` removes zero variances that
   would introduce non-differentiable terms, see [Smoothing](concepts.md#smoothing).
2. `cfg.ID_list` is the order of the program's variables. The columns of
   `data` follow it: column 0 holds `x`, column 1 holds `y`.
3. `OptimizationRun` uses Adam by default. Parameter values are passed without
   the underscore: `_a` is `a`.
