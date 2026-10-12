from __future__ import annotations

import pytest


def test_pipeline_end_to_end_program_runs_and_returns_valid_distribution() -> None:
    torch = pytest.importorskip("torch")

    from pydegas.cfg.builder import from_text
    from pydegas.parse.preprocessor import compile_to_soga_text
    from pydegas.semantics.engine import start_soga

    program = """
array[3] X;

x = 0;

for i in range(3) {
    x = x + gauss(0.0, 0.1);
    if x > -1 {
        X[i] = x;
    } else {
        skip;
    } end if;
} end for;

prune(5);
observe(x > -10);
"""

    compiled = compile_to_soga_text(program, seed=0)
    assert "gauss(" not in compiled
    assert "gm(" in compiled

    cfg = from_text(compiled)
    dist = start_soga(cfg)

    assert {"x", "X[0]", "X[1]", "X[2]"} <= set(dist.var_list)

    pi = torch.as_tensor(dist.gm.pi)
    mu = torch.as_tensor(dist.gm.mu)
    sigma = torch.as_tensor(dist.gm.sigma)

    assert mu.shape[1] == len(dist.var_list)
    assert sigma.shape[1:] == (len(dist.var_list), len(dist.var_list))

    assert torch.isfinite(pi).all()
    assert torch.isfinite(mu).all()
    assert torch.isfinite(sigma).all()

    assert pi.sum().item() == pytest.approx(1.0, rel=1e-6, abs=1e-6)
    assert pi.min().item() >= -1e-12
