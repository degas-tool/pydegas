"""
This module defines the exception hierarchy for the pydegas library.
"""

from __future__ import annotations


class PyDeGASError(Exception):
    """Base class for all pydegas-raised errors."""


class ParseError(PyDeGASError):
    """Base class for parse failures."""


class SyntaxParseError(ParseError):
    """Syntax-level parse failure (unexpected token, malformed construct)."""


class PreprocessError(ParseError):
    """Preprocessing step failed (normalization, helper syntax rewriting, etc.)."""


class SemanticError(PyDeGASError):
    """Parsed fine, but the program or expression is invalid/meaningless/unsupported."""


class ModelConstructionError(SemanticError):
    """Building/updating internal semantic objects failed (inconsistent internal state)."""


class InvalidConstraintError(SemanticError):
    """Constraints/conditions are inconsistent or ill-formed at the semantic level."""


class LossCompileError(ParseError):
    """The DeGASLoss DSL source could not be compiled (syntax or semantic error)."""
