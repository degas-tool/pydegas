"""Smoke test: a three-step run (Listings 1.2/1.3 of the paper) and a loss check."""

import platform

import pydegas
import torch
from pydegas.cfg import smooth
from pydegas.cfg.builder import from_text
from pydegas.optimize import OptimizationRun, get_loss
from pydegas.parse.preprocessor import compile_to_soga_text


print(f"python {platform.python_version()}  machine {platform.machine()}  torch {torch.__version__}")
print(f"pydegas imported from {pydegas.__file__}")

program = """
array[3] T;
currT = 16;
for i in range(3) {
  T[i] = currT;
  if currT > _tOff { heat = -0.5; } else { heat = 0.5; } end if;
  currT = currT + heat + gauss(0., 0.1);
} end for;
"""

cfg = from_text(compile_to_soga_text(program, seed=0))
smooth(cfg)
loss = get_loss("l2_distance", trajectories=torch.tensor([[16.0, 15.5, 15.0]]), indices=[0, 1, 2])
run = OptimizationRun(cfg, {"tOff": 16.0}, loss, optimizer="Adam", optimizer_kwargs={"lr": 0.1}, tolerance=None)
results = run.run(3)
for r in results:
    print(f"step {r.step}  loss {r.loss:.6f}  params {r.params}  mean {r.dist.gm.mean().tolist()}")

# Listing 1.3: first step has loss 2.000630 and tOff 15.9 after the update
assert abs(results[0].loss - 2.000630) < 1e-3, results[0].loss
assert abs(results[0].params["tOff"] - 15.9) < 1e-3, results[0].params
assert results[-1].loss < results[0].loss
print("smoke test OK")
