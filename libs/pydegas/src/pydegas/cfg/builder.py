"""
This module includes the functions to build a ControlFlowGraph from a SOGA source string or file.
"""

from __future__ import annotations

import logging
from pathlib import Path

from antlr4 import CommonTokenStream, InputStream, ParseTreeWalker

from pydegas.cfg.graph import ControlFlowGraph
from pydegas.exceptions import SourceFileNotFoundError, SyntaxParseError
from pydegas.parse.errors import CollectingErrorListener
from pydegas.parse.soga.SOGALexer import SOGALexer
from pydegas.parse.soga.SOGAParser import SOGAParser


logger = logging.getLogger(__name__)

_SYNTAX_ERROR_MESSAGE = "Failed to parse SOGA program (syntax/grammar error)."


def from_text(program: str) -> ControlFlowGraph:
    """Parse a SOGA program string and return the corresponding CFG.

    Raises ``SyntaxParseError`` on a parser error; its message lists the
    lexer and parser errors as ``"line L:C message"`` lines.
    """
    logger.debug("Parsing SOGA program (%d chars)", len(program))
    listener = CollectingErrorListener()
    try:
        lexer = SOGALexer(InputStream(program))
        lexer.addErrorListener(listener)
        parser = SOGAParser(CommonTokenStream(lexer))
        parser.addErrorListener(listener)
        tree = parser.progr()
        if parser.getNumberOfSyntaxErrors() > 0:
            raise SyntaxParseError("\n".join([_SYNTAX_ERROR_MESSAGE, *listener.errors]))
        cfg = ControlFlowGraph()
        ParseTreeWalker().walk(cfg, tree)
    except SyntaxParseError:
        raise
    except Exception as e:
        logger.exception("Failed to parse SOGA program: %s", e)
        raise SyntaxParseError(_SYNTAX_ERROR_MESSAGE) from e
    return cfg


def from_file(path: str | Path) -> ControlFlowGraph:
    """Parse a SOGA source file and return the corresponding CFG.

    Raises ``SourceFileNotFoundError`` (a ``FileNotFoundError``) if *path* does not exist.
    """
    logger.debug("Reading SOGA source file: %s", path)
    try:
        file_text = Path(path).read_text()
    except FileNotFoundError as e:
        logger.error("SOGA source file not found: %s", path)
        raise SourceFileNotFoundError(e.errno, e.strerror, e.filename) from e
    except OSError:
        logger.exception("Failed to read SOGA source file: %s", path)
        raise
    try:
        return from_text(file_text)
    except SyntaxParseError as e:
        logger.error("Failed to parse SOGA program from file: %s: %s", path, e)
        raise
