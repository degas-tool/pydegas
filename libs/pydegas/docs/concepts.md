# How pydegas works

## Pipeline

1. `compile_to_soga_text` rewrites helpers such as `gauss(0., 1.)` into
   `gm(...)` terms, representing one-dimensional Gaussian Mixtures.
2. `from_text` or `from_file` parses the program into a `ControlFlowGraph`.
3. `smooth` removes zero variances, see [Smoothing](#smoothing).
4. `start_soga` executes the graph and returns the output `Dist`, a Gaussian
   mixture over all program variables, computed in closed form.
5. A loss maps the `Dist` to a scalar tensor, and `OptimizationRun` steps the
   optimizer on its gradient.

Steps 1 to 3 run once; an optimization run repeats steps 4 and 5.

## Mixtures and pruning

| Statement | Effect on the mixture | Exact |
|---|---|---|
| linear assignment | maps every component; sum with a `gm` term with k components multiplies the number of components K by k | yes |
| `z = x*y` | replaces each component by a Gaussian with the product's mean and covariance | no |
| `if` | splits each component by the guard, approximates each part by a Gaussian and weights it by its probability; the branches are joined at `end if` | no |
| `observe(...)` | keeps the part of each component that satisfies the guard and renormalizes, see [Guards](language.md#guards) | no |

K grows exponentially (ten `bern` assignments give 1024 components), and so
does execution time. Bound it with `prune(k);` statements or with the `Kmax`
argument of `start_soga` and `OptimizationRun`, which prunes after every
`end if`. The `pruning` argument selects the method:

| `pruning` | Reduction |
|---|---|
| `"classic"` (default) | repeatedly merges two components into one with their combined mean and covariance, light and close components first |
| `"ranking"` | keeps the k heaviest components |
| `"kmeans"` | clusters the components by their means and merges each cluster; random, so call `torch.manual_seed` first |

Any other value turns pruning off.

## Smoothing

Deterministic assignments such as `x = 1;` or `y = 2*x + 1;`, and discrete ones
such as `b = bern(0.3);`, give components zero covariance matrices, introducing discontinuities in the gradient.
`smooth(cfg, smooth_eps=1e-3)` fixes this in place:

- it adds Gaussian noise with standard deviation ε = `smooth_eps` to such
  assignments;
- it widens guards on a variable assigned a number or a zero-variance `gm`,
  such as `bern(p)`, by δ = 5√ε: `v == c` becomes `c - δ < v < c + δ`, `v > c`
  becomes `v > c + δ` and `v <= c` becomes `v <= c + δ`.
  The value of δ is chosen to satisfy the consistency condition (see reference paper).

Smooth a graph once. To use another ε, parse the program again.

## Errors and logging

All exceptions derive from `PyDeGASError` in `pydegas.exceptions`.

| Exception | Subclass of | Raised by |
|---|---|---|
| `PreprocessError` | `ParseError` | `compile_to_soga_text`: malformed helper arguments |
| `SyntaxParseError` | `ParseError` | `from_text`, `from_file`: a statement the grammar rejects, listed as `line L:C message` lines and printed to stderr, see [Program structure](language.md#program-structure) |
| `SourceFileNotFoundError` | `FileNotFoundError` | `from_file`: a path that does not exist |
| `LossCompileError` | `ParseError` | the loss DSL, see [Loss DSL](loss-dsl.md#errors) |
| `SemanticError` | | `start_soga`: an assignment it cannot evaluate, such as a loop variable used as a value |
| `InvalidConstraintError` | `SemanticError` | `start_soga`: `==` or `!=` in an `if` on a variable that smoothing did not widen |
| `MissingParameterError` | `KeyError` | `start_soga`, also during a run: a parameter `_name` with no value under `name` |
| `UnknownOptimizerError` | `ConfigurationError` | `OptimizationRun`, `optimize`: an optimizer name not in `OPTIMIZER_REGISTRY` |
| `UnsupportedOptimizerError` | `TypeError` | `OptimizationRun`, `optimize`: an optimizer that is neither a name nor a `torch.optim.Optimizer` subclass |
| `UnknownLossError` | `ConfigurationError` | `get_loss`: a name not in `LOSS_REGISTRY` |
| `ConfigurationError` | `ValueError` | the `signal_error` loss, when evaluated on fewer than `time_steps` variables |

pydegas logs nothing by default. To log one line per optimization step:

```python
import logging

logging.basicConfig()
logging.getLogger("pydegas.optimize.runner").setLevel(logging.DEBUG)
```

Set the `pydegas` logger to `DEBUG` instead to also log every parsed statement
and every assignment.
