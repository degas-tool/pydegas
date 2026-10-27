# Program language

The grammar is [`src/pydegas/grammars/SOGA.g4`](../src/pydegas/grammars/SOGA.g4).

## Example

A linear trend with occasional outliers:

```python
import torch

from pydegas.cfg import smooth
from pydegas.cfg.builder import from_text
from pydegas.parse.preprocessor import compile_to_soga_text
from pydegas.semantics.engine import start_soga

source = """
data t = [1., 2., 3.];
array[3] y;

slope = gm([1.], [_mu], [_sigma]);
for i in range(3) {
    y[i] = t[i]*slope + gauss(0., 0.1);
    outlier = bern(0.1);
    if outlier == 1 {
        y[i] = y[i] + gauss(0., 2.);
    } else {
        skip;
    } end if;
} end for;
prune(4);
observe(slope > 0);
"""

cfg = from_text(compile_to_soga_text(source))
smooth(cfg)
dist = start_soga(cfg, {"mu": torch.tensor(1.0), "sigma": torch.tensor(0.5)})
print(dist.var_list)
print([round(m, 2) for m in dist.gm.mean().tolist()])
```

Output:

```text
['y[0]', 'y[1]', 'y[2]', 'slope', 'outlier']
[1.03, 2.06, 3.08, 1.03, 0.1]
```

## Program structure

- `data t = [1., 2., 3.];` declares read-only numbers, read as `t[0]` or
  `t[i]`. Write all `data` declarations first.
- `array[3] y;` declares `y[0]` to `y[2]`, at the top level only. Scalar
  variables need no declaration. Every variable starts at 0.
- Every statement ends with `;`, including `end if;` and `end for;`.
- An index is an integer literal or a loop variable: `y[2]` or `t[i]`, not
  `y[i+1]`.
- Names are letters and digits, starting with a letter, other than `data`,
  `skip`, `if`, `else` and `for`. A leading `_` marks a parameter.
- Numbers are written `3`, `-2`, `0.5` or `1.`, without exponents.
- Comments use `/* ... */`.
- `end if`, `end for` and `in range(` are written with one space. `gm(`,
  `observe(`, `prune(`, `array[` and helpers such as `gauss(` have no space
  before the bracket.

Parsing stops without an error at the first top-level statement that does not
start like one, such as a `data` declaration after other statements; the rest
of the program is ignored. Characters outside the grammar are skipped with a
message on stderr, so `y = .5;` reads as `y = 5;`.

## Statements

| Statement | Form |
|---|---|
| Assignment | `x = expression;` |
| No-op | `skip;` |
| Conditional | `if guard { block } else { block } end if;` |
| Bounded loop | `for i in range(n) { block } end for;` |
| Observation | `observe(guard);` |
| Pruning | `prune(k);` |

**Assignments.** The right-hand side is one of:

- A linear expression: terms joined by `+` or `-`, each `c*v`, `v` or `c`,
  where `v` is a variable, an array element or a distribution, and `c` is a
  number, a parameter or a data element. Examples: `x = x + 1;`,
  `y = _a*x + _b + gauss(0., 1.);`, `y[i] = t[i]*slope;`.
- A product of two variables, array elements or distributions, and nothing
  else: `z = x*y;`. A coefficient, as in `2*x*y`, is ignored; scale in a
  second statement: `z = 2*z;`.

Rules for linear expressions:

- A term has one coefficient: `2*x`, `_a*x`, not `2*_a*x`.
- Each variable appears once: write `2*y`, not `y + y`, which runs as `y`.
- There is no division: write `0.5*y`.
- Put spaces around a minus sign, `y - 1`, and negate with `-1*y`.

**Conditionals.** The `else` branch is required and every block holds at least
one statement; use `skip;` for an empty branch. Conditionals and loops nest.

**Loops.** The bound `n` is an integer literal or a data element
(`range(n[0])`). The loop variable runs from 0 to `n - 1` and is used only as
an index.

**Pruning.** `prune(k);`, with an integer literal `k`, reduces the mixture to
at most `k` components, see [Mixtures and pruning](concepts.md#mixtures-and-pruning).

## Guards

Guards appear in `if` and `observe`:

- `lin op c` with `op` one of `<`, `<=`, `>`, `>=`. `lin` is a linear
  combination of variables without a constant term (`x > 0`,
  `x + 2*y <= 1`, `x - _k*y > 0`), and `c` is a number, a parameter or a data
  element: write `x > -1`, not `x + 1 > 0`.
- `v == c` or `v != c` on a single variable.

There is no `and`, `or` or negation; nest conditionals instead.

In an `if`, use `==` and `!=` only on a variable assigned a number or a
zero-variance `gm` such as `bern(p)`, and [smooth](concepts.md#smoothing) the
graph first.

In `observe`, an inequality keeps the part of the distribution that satisfies
it, and so do `==` and `!=` on a variable that smoothing widens. On any other
variable, `v == c` conditions each component on `v = c` without reweighting the
components, so it is exact only for a single component, and it leaves no
components if `v` is the only variable; `v != c` acts as `v == c`.

On array elements, `==` and `!=` give wrong results in both. Compare with a
threshold between the values instead: `if b[i] < 0.5` for `b[i] = bern(p);`.

## Distributions

`gm([w1, ..., wk], [m1, ..., mk], [s1, ..., sk])` is a Gaussian mixture with
the given weights, means and standard deviations, each a number or a
parameter. Helpers, rewritten by `compile_to_soga_text`, take numbers only:

| Helper | Distribution |
|---|---|
| `gauss(mean, std)` | normal |
| `bern(p)` | 1 with probability `p`, else 0 |
| `uniform([a, b], k)` | uniform on `[a, b]`, approximated by `k` components |
| `beta([a, b], k)` | Beta(a, b), approximated by `k` components |
| `laplace(loc, scale, k)` | Laplace(loc, scale), approximated by `k` components |
| `exprnd(scale, k)` | exponential with mean `scale`, approximated by `k` components |

The approximated helpers are fitted to random samples. For the same program
text on every run, pass `seed` to `compile_to_soga_text` and call
`numpy.random.seed(0)` before it.

## Parameters

A parameter is written `_name` and can be a coefficient, a constant term, the
right-hand side of a guard or an entry of a `gm(...)` list. It cannot appear in
`data` lists, loop bounds, `prune(k)` or helper arguments: write
`gm([1.], [_mu], [_sigma])`, not `gauss(_mu, _sigma)`. Values are passed under
the name without the underscore: `_mu` takes its value from
`{"mu": torch.tensor(1.0)}`.

Parameters are unconstrained. Mixture weights are renormalized, and a
component with a negative weight is dropped. A standard deviation enters
squared, so its sign does not matter.

## Executing a program

| Function | Module | Notes |
|---|---|---|
| `compile_to_soga_text(input_program, seed=None)` | `pydegas.parse.preprocessor` | rewrites the helpers; programs that use only `gm` can skip it |
| `from_text(program)`, `from_file(path)` | `pydegas.cfg.builder` | return a `ControlFlowGraph`; `cfg.ID_list` lists the variables in order of first appearance |
| `smooth(cfg, smooth_eps=1e-3)` | `pydegas.cfg` | modifies `cfg` in place, see [Smoothing](concepts.md#smoothing) |
| `start_soga(cfg, params_dict=None, pruning="classic", Kmax=None)` | `pydegas.semantics.engine` | executes the graph with parameter values as tensors and returns a `Dist` |

## The output `Dist`

| Attribute | Value |
|---|---|
| `dist.var_list` | variable names, as in `cfg.ID_list` |
| `dist.gm.pi`, `dist.gm.mu`, `dist.gm.sigma` | weights (K × 1), means (K × n), covariances (K × n × n) |
| `dist.gm.mean()`, `dist.gm.cov()` | mean (n) and covariance (n × n) of the mixture |
| `dist.gm.marg_pdf(x, idx)`, `marg_log_pdf`, `marg_cdf` | marginal density (N × 1), log-density (N) and CDF (N × 1) over the list of positions `idx`, at the N rows of `x` (one column per position) |
| `dist.gm.sample(n_samples)` | `n_samples` samples; needs at least two components and two variables |

Losses refer to variables by their position in `dist.var_list`. Tensors use
PyTorch's default dtype; for float64, call
`torch.set_default_dtype(torch.float64)` first.
