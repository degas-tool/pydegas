from __future__ import annotations

import pytest


torch = pytest.importorskip("torch")


@pytest.mark.parametrize(
    "condition, expected",
    [
        ("x < 1", "x >= 1"),
        ("x <= 1", "x > 1"),
        ("x > 1", "x <= 1"),
        ("x >= 1", "x < 1"),
        ("x == 1", "x != 1"),
        ("x != 1", "x == 1"),
        ("x > 0 and x < 1", "x <= 0 or x >= 1"),
        ("x < 0 or x > 1", "x <= 1 and x >= 0"),
    ],
)
def test_negation_applies_complements_and_de_morgan(condition, expected):
    from pydegas.cfg.smoother import negate

    assert negate(condition) == expected


def test_constant_smoothing_adds_noise_with_requested_scale():
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.semantics.engine import start_soga

    cfg = from_text("x = 2;")
    assert smooth(cfg, smooth_eps=0.02) is None
    actual = start_soga(cfg)
    assert cfg.smoothed_vars == ["x"]
    assert actual.gm.mean().item() == pytest.approx(2.0)
    assert actual.gm.cov().item() == pytest.approx(0.02**2, abs=1e-8)


@pytest.mark.parametrize(
    "operator, expected",
    [
        ("==", "x > 0 - 0.5000000000 and x < 0 + 0.5000000000"),
        ("!=", "x < 0 - 0.5000000000 or x > 0 + 0.5000000000"),
        ("<", "x < 0 - 0.5000000000"),
        (">", "x > 0 + 0.5000000000"),
        ("<=", "x <= 0 + 0.5000000000"),
        (">=", "x >= 0 - 0.5000000000"),
    ],
)
def test_smoothing_relaxes_guard_by_five_sqrt_epsilon(operator, expected):
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.nodes import TestNode as BranchNode
    from pydegas.cfg.smoother import smooth

    cfg = from_text(f"x = 0; if x {operator} 0 {{ skip; }} else {{ skip; }} end if;")
    smooth(cfg, smooth_eps=0.01)
    branch = next(node for node in cfg.node_list.values() if isinstance(node, BranchNode))
    assert branch.smooth.replace(" ", "") == expected.replace(" ", "")


def test_nondegenerate_assignment_is_not_perturbed():
    from pydegas.cfg.builder import from_text
    from pydegas.cfg.smoother import smooth
    from pydegas.semantics.engine import start_soga

    cfg = from_text("x = gm([1.0],[2.0],[0.5]);")
    smooth(cfg)
    actual = start_soga(cfg)
    assert cfg.smoothed_vars == []
    assert actual.gm.mean().item() == pytest.approx(2.0)
    assert actual.gm.cov().item() == pytest.approx(0.25)
