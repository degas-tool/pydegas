"""Insulin-pump running example of the paper (Fig. 1, Listing 1.1).

Tunes the glucose threshold _gTh and the extra insulin dose _uHigh with Adam on
the glycemic-risk objective written in the DeGASLoss language.

Expected end of the output (Listing 1.1, up to small numerical differences
between platforms):

    144 True 0.7823... {'gTh': 128.59..., 'uHigh': 14.98...}

Usage: python examples/insulin_pump.py [TRACE.json]; with TRACE.json, every step
is also written there, for scripts/compare_insulin.py.
"""

import json
import sys
import time
from pathlib import Path

from pydegas.cfg import smooth
from pydegas.cfg.builder import from_text
from pydegas.optimize import OptimizationRun
from pydegas.optimize.dsl import compile_loss, validate_loss
from pydegas.parse.preprocessor import compile_to_soga_text


program = """
array[18] G;
g = 110; x = 0;
q = gauss(80., 20.);
for i in range(18) {
  cgm = g + gauss(0., 6.);
  if cgm > _gTh { u = _uHigh; }
  else {
    if cgm < 80 { u = -15; }
    else { u = 0; } end if;
  } end if;
  xg = x * g;
  g = 0.72*g - 10*xg + 0.15*q + 30.8
      + gauss(0., 2.);
  x = 0.75*x + 0.00013*u;
  q = 0.85*q;
  G[i] = g;
} end for;
"""

loss_src = """
loss glycemic_risk(d: dist, idx: index_list, k: scalar, w: scalar) =
    m = d.mean[idx];
    s = sqrt(d.var[idx]);
    lo = 1.509 * (log(m - k*s) ^ 1.084 - 5.381);
    hi = 1.509 * (log(m + k*s) ^ 1.084 - 5.381);
    low_risk  = 10 * ((abs(lo) - lo) / 2) ^ 2;
    high_risk = 10 * ((abs(hi) + hi) / 2) ^ 2;
    mean_agg(w * low_risk + high_risk)
"""

init_params = {"gTh": 150.0, "uHigh": 20.0}  # starting point for the optimization run

cfg = from_text(compile_to_soga_text(program, seed=0))
smooth(cfg)

assert validate_loss(loss_src) == []
loss = compile_loss(loss_src, idx=list(range(18)), k=2.0, w=2.0)

run = OptimizationRun(
    cfg,
    init_params,
    loss,
    tolerance=1e-3,
    patience=10,
    optimizer="Adam",
    optimizer_kwargs={"lr": 0.15},
    Kmax=100,
)

start = time.time()
trace = []
for r in run.run_generator(150):
    if r.step % 50 == 0 or r.converged:
        print(r.step, round(r.loss, 3), r.params)
    trace.append({"step": r.step, "loss": r.loss, "params": r.params, "converged": r.converged})
    last = r
print(last.step, last.converged, last.loss, last.params)
print(f"wall clock: {time.time() - start:.1f} s", file=sys.stderr)

if len(sys.argv) > 1:
    Path(sys.argv[1]).write_text(json.dumps(trace))
