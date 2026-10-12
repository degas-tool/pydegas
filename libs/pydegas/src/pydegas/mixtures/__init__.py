"""Gaussian mixtures and joint distributions over program variables"""

from pydegas.mixtures.constants import (
    EPS,
    INFTY,
    SMOOTH_DELTA,
    SMOOTH_EPS,
    TOL_EIG,
    TOL_ERR,
    TOL_PROB,
)
from pydegas.mixtures.distribution import Dist
from pydegas.mixtures.gaussian_mix import GaussianMix
from pydegas.mixtures.numerics import TruncatedNormal, make_sym, mvncdf


__all__ = [
    # core types
    "GaussianMix",
    "Dist",
    # numerics
    "TruncatedNormal",
    "make_sym",
    "mvncdf",
    # constants
    "EPS",
    "INFTY",
    "SMOOTH_DELTA",
    "SMOOTH_EPS",
    "TOL_EIG",
    "TOL_ERR",
    "TOL_PROB",
]
