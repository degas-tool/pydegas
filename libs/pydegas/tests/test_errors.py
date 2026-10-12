from __future__ import annotations

from pathlib import Path

import pytest


def test_syntax_parse_error_is_raised_for_invalid_program_text() -> None:
    from pydegas.cfg.builder import from_text
    from pydegas.exceptions import SyntaxParseError

    with pytest.raises(SyntaxParseError, match="syntax/grammar error"):
        from_text("x = 1")


def test_invalid_constraint_error_is_raised_for_degenerate_equality_condition() -> None:
    from pydegas.cfg.builder import from_text
    from pydegas.exceptions import InvalidConstraintError
    from pydegas.semantics.engine import start_soga

    program = """
x = 0;
if x == 0 {
    skip;
} else {
    skip;
} end if;
"""

    cfg = from_text(program)
    with pytest.raises(InvalidConstraintError, match="Degeneracy in if condition"):
        start_soga(cfg)


def test_from_file_raises_file_not_found_for_missing_path(tmp_path: Path) -> None:
    from pydegas.cfg.builder import from_file

    with pytest.raises(FileNotFoundError):
        from_file(tmp_path / "missing.soga")
