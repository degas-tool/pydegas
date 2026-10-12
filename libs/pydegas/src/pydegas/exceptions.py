"""
This module defines the exception hierarchy for the pydegas library.
"""

from __future__ import annotations

from collections.abc import Iterable


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


class MissingParameterError(PyDeGASError, KeyError):
    """The program uses a parameter ``_name`` for which no value was supplied.

    Subclasses ``KeyError`` for backward compatibility; ``args[0]`` is the
    parameter name without the underscore.
    """

    def __init__(self, name: str, available: Iterable[str] = ()) -> None:
        super().__init__(name)
        self.name = name
        self.available = sorted(available)

    def __str__(self) -> str:
        return (
            f"No value for parameter '_{self.name}': supply it as {self.name!r} (without the underscore). "
            f"Supplied parameters: {self.available}"
        )


class SourceFileNotFoundError(PyDeGASError, FileNotFoundError):
    """The SOGA source file does not exist. Subclasses ``FileNotFoundError``."""


class ConfigurationError(PyDeGASError, ValueError):
    """An optimization setting has an invalid value. Subclasses ``ValueError``."""


class UnknownOptimizerError(ConfigurationError):
    """The optimizer name is not a key of ``OPTIMIZER_REGISTRY``."""


class UnknownLossError(ConfigurationError):
    """The loss name is not a key of ``LOSS_REGISTRY``."""


class UnsupportedOptimizerError(PyDeGASError, TypeError):
    """The optimizer is neither a registered name nor a ``torch.optim.Optimizer`` subclass.

    Subclasses ``TypeError`` for backward compatibility.
    """
