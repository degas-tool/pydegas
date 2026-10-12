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
    from pydegas.exceptions import PyDeGASError, SourceFileNotFoundError

    missing = tmp_path / "missing.soga"
    with pytest.raises(SourceFileNotFoundError) as excinfo:
        from_file(missing)
    assert isinstance(excinfo.value, FileNotFoundError)
    assert isinstance(excinfo.value, PyDeGASError)
    assert excinfo.value.filename == str(missing)


def test_from_file_syntax_error_is_not_its_own_cause(tmp_path: Path) -> None:
    from pydegas.cfg.builder import from_file
    from pydegas.exceptions import SyntaxParseError

    source = tmp_path / "bad.soga"
    source.write_text("x = 1")
    with pytest.raises(SyntaxParseError) as excinfo:
        from_file(source)
    assert excinfo.value.__cause__ is not excinfo.value


def test_syntax_parse_error_message_lists_the_error_positions() -> None:
    from pydegas.cfg.builder import from_text
    from pydegas.exceptions import SyntaxParseError

    with pytest.raises(SyntaxParseError, match=r"(?s)syntax/grammar error.*line 1:5 missing ';' at '<EOF>'"):
        from_text("x = 1")
    with pytest.raises(SyntaxParseError, match=r"(?s)line 1:13 token recognition error.*line 1:15 extraneous input"):
        from_text("x = 2; y = x @ 1;")


@pytest.mark.parametrize(
    "program",
    [
        pytest.param("x = _mu;", id="assignment-constant"),
        pytest.param("x = gm([1.0],[_mu],[1.0]);", id="assignment-gm-list"),
        pytest.param("x = gm([1.0],[0.0],[1.0]); if x < _mu { skip; } else { skip; } end if;", id="guard-constant"),
        pytest.param(
            "x = gm([1.0],[0.0],[1.0]); if x + gm([1.0],[_mu],[1.0]) > 0 { skip; } else { skip; } end if;",
            id="guard-gm-list",
        ),
    ],
)
def test_missing_parameter_raises_missing_parameter_error(program: str) -> None:
    torch = pytest.importorskip("torch")
    from pydegas.cfg.builder import from_text
    from pydegas.exceptions import MissingParameterError, PyDeGASError
    from pydegas.semantics.engine import start_soga

    with pytest.raises(MissingParameterError) as excinfo:
        start_soga(from_text(program), {"other": torch.tensor(1.0)})
    assert isinstance(excinfo.value, KeyError)
    assert isinstance(excinfo.value, PyDeGASError)
    assert excinfo.value.args == ("mu",)
    assert "'_mu'" in str(excinfo.value) and "['other']" in str(excinfo.value)


def test_unknown_loss_name_raises_unknown_loss_error() -> None:
    from pydegas.exceptions import PyDeGASError, UnknownLossError
    from pydegas.optimize import get_loss

    with pytest.raises(UnknownLossError, match="Available: ") as excinfo:
        get_loss("no_such_loss")
    assert isinstance(excinfo.value, ValueError)
    assert isinstance(excinfo.value, PyDeGASError)


def test_signal_error_with_too_many_time_steps_raises_configuration_error() -> None:
    from pydegas.cfg.builder import from_text
    from pydegas.exceptions import ConfigurationError
    from pydegas.optimize import signal_error
    from pydegas.semantics.engine import start_soga

    dist = start_soga(from_text("x = 1;"))
    with pytest.raises(ConfigurationError, match="time_steps=50") as excinfo:
        signal_error()(dist)
    assert isinstance(excinfo.value, ValueError)
