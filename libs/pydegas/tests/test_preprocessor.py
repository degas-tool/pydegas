from __future__ import annotations

import math

import pytest


def test_compile_to_soga_text_rewrites_gauss_to_gm() -> None:
    from pydegas.parse.preprocessor import compile_to_soga_text

    compiled = compile_to_soga_text("x = gauss(0.0, 1.0);", seed=0)
    assert "gauss(" not in compiled
    assert "gm(" in compiled


def test_preprocess_error_is_raised_for_invalid_gauss_args() -> None:
    from pydegas.exceptions import PreprocessError
    from pydegas.parse.preprocessor import compile_to_soga_text

    with pytest.raises(PreprocessError, match=r"Invalid gauss\(0\.0\) arguments"):
        compile_to_soga_text("x = gauss(0.0);", seed=0)


def test_preprocess_error_is_raised_for_invalid_uniform_args() -> None:
    from pydegas.exceptions import PreprocessError
    from pydegas.parse.preprocessor import compile_to_soga_text

    with pytest.raises(PreprocessError, match=r"Invalid uniform"):
        compile_to_soga_text("x = uniform([0, 1]);", seed=0)


@pytest.mark.parametrize(
    "helper, mean, variance",
    [
        ("uniform([-1, 3], 1)", 1.0, 4 / 3),
        ("beta([2, 5], 1)", 2 / 7, 10 / 392),
        ("laplace(1, 0.5, 1)", 1.0, 0.5),
        ("exprnd(2, 1)", 2.0, 4.0),
    ],
)
def test_fitted_helpers_approximate_their_distribution_moments(helper, mean, variance):
    from pydegas.cfg.builder import from_text
    from pydegas.parse.preprocessor import compile_to_soga_text
    from pydegas.semantics.engine import start_soga

    # One component tests the sampled distribution's moments, independent of
    # random multi-component initialization. Allow sampling error at n=10,000.
    compiled = compile_to_soga_text(f"x = {helper};", seed=0)
    actual = start_soga(from_text(compiled))
    assert actual.gm.n_comp() == 1
    assert actual.gm.mean().item() == pytest.approx(mean, abs=6 * math.sqrt(variance / 10_000))
    assert actual.gm.cov().item() == pytest.approx(variance, rel=0.12)
