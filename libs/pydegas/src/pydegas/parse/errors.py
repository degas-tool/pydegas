"""ANTLR error listener that records syntax errors as strings."""

from __future__ import annotations

from typing import Any

from antlr4.error.ErrorListener import ErrorListener


class CollectingErrorListener(ErrorListener):
    """Record lexer and parser errors as ``"line L:C message"`` strings."""

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def syntaxError(self, recognizer: Any, offendingSymbol: Any, line: int, column: int, msg: str, e: Any) -> None:
        self.errors.append(f"line {line}:{column} {msg}")
