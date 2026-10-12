"""
This module implements high-level SOGA-to-grammar SOGA compilation,
rewriting helper syntax like bern, gauss, beta, etc., into grammar-level gm(...) notation.
"""

from __future__ import annotations

import logging
import re

import numpy as np
from sklearn.mixture import GaussianMixture

from pydegas.exceptions import PreprocessError


logger = logging.getLogger(__name__)

_N_SAMPLES = int(10**4)


def _extract_match(input_program: str, regex: str) -> tuple[list[str], list[str]]:
    """Return (captured-groups, full-match-strings) for every match of *regex*."""
    in_matches: list[str] = []
    out_text: list[str] = []
    for match in re.finditer(regex, input_program, re.MULTILINE):
        out_text.append(input_program[match.start() : match.end()])
        for group_num in range(len(match.groups())):
            in_matches.append(match.group(group_num + 1))
    return in_matches, out_text


def _gm_str(weights: np.ndarray, means: np.ndarray, stds: np.ndarray) -> str:
    """Format arrays as a ``gm([…],[…],[…])`` string."""

    def fmt(arr: np.ndarray) -> str:
        return "[" + ",".join(f"{v:.10f}" for v in arr) + "]"

    return f"gm({fmt(weights)},{fmt(means)},{fmt(stds)})"


def _fit_gmm(samples: np.ndarray, n_components: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Fit a full-covariance GM to *samples* and return (weights, means, stds)."""

    gmm = GaussianMixture(n_components=n_components, max_iter=1000, n_init=1, covariance_type="full")
    gmm.fit(samples.reshape(-1, 1))
    weights = gmm.weights_.flatten()
    means = gmm.means_.flatten()
    stds = np.sqrt(gmm.covariances_.flatten())
    return weights, means, stds


def compile_bernoulli(input_program: str) -> str:
    """Rewrite ``bern(p)`` → exact two-component GM over {0, 1}."""
    matches, out_text = _extract_match(input_program, regex=r"bern\((.*?)\)")
    for idx, match in enumerate(matches):
        try:
            p = float(match.split(",")[0].strip())
        except Exception as e:
            raise PreprocessError(f"Invalid bern({match}) arguments. Expected bern(p) with p a float.") from e
        replacement = f"gm([{1 - p:f},{p:f}],[0.0,1.0],[0.0,0.0])"
        logger.debug("bern(%s) → %s", match, replacement)
        input_program = input_program.replace(out_text[idx], replacement)
    return input_program


def compile_gauss(input_program: str) -> str:
    """Rewrite ``gauss(mean, std)`` → single-component GM."""
    matches, out_text = _extract_match(input_program, regex=r"gauss\((.*?)\)")
    for idx, match in enumerate(matches):
        try:
            parts = [p.strip() for p in match.split(",")]
            if len(parts) != 2:
                raise ValueError("expected exactly 2 arguments")
            mean = float(parts[0])
            std = float(parts[1])
        except Exception as e:
            raise PreprocessError(
                f"Invalid gauss({match}) arguments. Expected gauss(mean, std) with two floats."
            ) from e
        replacement = f"gm([1.0],[{mean:f}],[{std:f}])"
        logger.debug("gauss(%s) → %s", match, replacement)
        input_program = input_program.replace(out_text[idx], replacement)
    return input_program


def compile_uniform(input_program: str, rng: np.random.Generator) -> str:
    """Rewrite ``uniform([low, high], n_components)`` → fitted GM."""
    matches, out_text = _extract_match(input_program, regex=r"uniform\((.*?)\)")
    for idx, match in enumerate(matches):
        try:
            parts = re.split(r"(?<=\])\s*,", match)
            if len(parts) != 2:
                raise ValueError("expected two arguments: [low, high], n_components")
            bounds = [b.strip() for b in parts[0].strip().lstrip("[").rstrip("]").split(",")]
            if len(bounds) != 2:
                raise ValueError("expected [low, high]")
            low = float(bounds[0])
            high = float(bounds[1])
            n_comp = int(parts[1].strip())
            samples = rng.uniform(low=low, high=high, size=_N_SAMPLES)
            weights, means, stds = _fit_gmm(samples, n_comp)
        except Exception as e:
            raise PreprocessError(
                f"Invalid uniform({match}) arguments. Expected uniform([low, high], n_components)."
            ) from e
        replacement = _gm_str(weights, means, stds)
        logger.debug("uniform(%s) → %s", match, replacement)
        input_program = input_program.replace(out_text[idx], replacement)
    return input_program


def compile_beta(input_program: str, rng: np.random.Generator) -> str:
    """Rewrite ``beta([a, b], n_components)`` → fitted GM."""
    matches, out_text = _extract_match(input_program, regex=r"beta\((.*?)\)")
    for idx, match in enumerate(matches):
        try:
            parts = re.split(r"(?<=\])\s*,", match)
            if len(parts) != 2:
                raise ValueError("expected two arguments: [a, b], n_components")
            ab = [b.strip() for b in parts[0].strip().lstrip("[").rstrip("]").split(",")]
            if len(ab) != 2:
                raise ValueError("expected [a, b]")
            a = float(ab[0])
            b = float(ab[1])
            n_comp = int(parts[1].strip())
            samples = rng.beta(a, b, size=_N_SAMPLES)
            weights, means, stds = _fit_gmm(samples, n_comp)
        except Exception as e:
            raise PreprocessError(f"Invalid beta({match}) arguments. Expected beta([a, b], n_components).") from e
        replacement = _gm_str(weights, means, stds)
        logger.debug("beta(%s) → %s", match, replacement)
        input_program = input_program.replace(out_text[idx], replacement)
    return input_program


def compile_laplace(input_program: str, rng: np.random.Generator) -> str:
    """Rewrite ``laplace(loc, scale, n_components)`` → fitted GM."""
    matches, out_text = _extract_match(input_program, regex=r"laplace\((.*?)\)")
    for idx, match in enumerate(matches):
        try:
            parts = [s.strip() for s in match.split(",")]
            if len(parts) != 3:
                raise ValueError("expected exactly 3 arguments")
            loc, scale, n_comp = parts
            samples = rng.laplace(float(loc), float(scale), size=_N_SAMPLES)
            weights, means, stds = _fit_gmm(samples, int(n_comp))
        except Exception as e:
            raise PreprocessError(
                f"Invalid laplace({match}) arguments. Expected laplace(loc, scale, n_components)."
            ) from e
        replacement = _gm_str(weights, means, stds)
        logger.debug("laplace(%s) → %s", match, replacement)
        input_program = input_program.replace(out_text[idx], replacement)
    return input_program


def compile_exprnd(input_program: str, rng: np.random.Generator) -> str:
    """Rewrite ``exprnd(scale, n_components)`` → fitted GM."""
    matches, out_text = _extract_match(input_program, regex=r"exprnd\((.*?)\)")
    for idx, match in enumerate(matches):
        try:
            parts = [s.strip() for s in match.split(",")]
            if len(parts) != 2:
                raise ValueError("expected exactly 2 arguments")
            scale, n_comp = parts
            samples = rng.exponential(float(scale), size=_N_SAMPLES)
            weights, means, stds = _fit_gmm(samples, int(n_comp))
        except Exception as e:
            raise PreprocessError(f"Invalid exprnd({match}) arguments. Expected exprnd(scale, n_components).") from e
        replacement = _gm_str(weights, means, stds)
        logger.debug("exprnd(%s) → %s", match, replacement)
        input_program = input_program.replace(out_text[idx], replacement)
    return input_program


def compile_to_soga_text(input_program: str, seed: int | None = None) -> str:
    """Compile a high-level SOGA program string to grammar-level SOGA."""
    try:
        rng = np.random.default_rng(seed)
        program = input_program
        program = compile_exprnd(program, rng)
        program = compile_uniform(program, rng)
        program = compile_beta(program, rng)
        program = compile_laplace(program, rng)
        program = compile_gauss(program)
        program = compile_bernoulli(program)
        logger.debug("compiled to grammar-level SOGA: %r", program)
        return program
    except PreprocessError:
        raise
    except Exception as e:
        raise PreprocessError(f"Failed to preprocess/compile high-level SOGA helper syntax: {e}") from e
