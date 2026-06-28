"""Test errors."""

from __future__ import annotations

from pyshell_lab.errors import (
    ExecutionError,
    ExpansionError,
    LexerError,
    ParserError,
    ShellError,
    ShellExit,
)


def test_shell_exit_stores_status() -> None:
    exc = ShellExit(42)
    assert exc.status == 42
    assert exc.args == (42,)


def test_shell_exit_default_status() -> None:
    assert ShellExit().status == 0


def test_error_hierarchy() -> None:
    assert issubclass(LexerError, ShellError)
    assert issubclass(ParserError, ShellError)
    assert issubclass(ExpansionError, ShellError)
    assert issubclass(ExecutionError, ShellError)
    assert not issubclass(ShellExit, ShellError)
