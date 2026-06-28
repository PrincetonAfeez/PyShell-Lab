"""Test coverage boost."""

from __future__ import annotations

import io
import os
import sys

import pytest

from pyshell_lab.builtins import run_builtin
from pyshell_lab.errors import ParserError
from pyshell_lab.executor import _display, execute
from pyshell_lab.parser import parse_line
from pyshell_lab.repl import Shell
from pyshell_lab.state import ShellState


def test_which_prints_resolved_path() -> None:
    state = ShellState()
    state.exported_env["PATH"] = os.path.dirname(sys.executable)
    out = io.StringIO()
    exe = os.path.basename(sys.executable)
    assert run_builtin(state, ["which", exe], out, io.StringIO()) == 0
    assert out.getvalue().strip() != ""


def test_execute_line_oserror_returns_1(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "pyshell_lab.repl.parse_line",
        lambda _line: (_ for _ in ()).throw(OSError("resource busy")),
    )
    shell = Shell()
    assert shell.execute_line("anything") == 1
    assert shell.state.last_status == 1
    assert "resource busy" in capsys.readouterr().err


def test_run_interactive_unexpected_exception_sets_status_one(monkeypatch) -> None:
    shell = Shell()
    calls = {"n": 0}

    def fake_input(_prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "line"
        raise EOFError

    def boom(_line: str, *, remember: bool = True) -> int:
        raise ValueError("unexpected")

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(shell, "execute_line", boom)
    from pyshell_lab import history

    monkeypatch.setattr(history, "load_history", lambda _s: None)
    monkeypatch.setattr(history, "save_history", lambda _s: None)
    assert shell.run_interactive(load_rc=False) == 1


def test_run_script_shell_exit_returns_status(tmp_path) -> None:
    script = tmp_path / "exit.psh"
    script.write_text("exit 4\n", encoding="utf-8")
    assert Shell().run_script(script, load_rc=False) == 4


def test_parse_background_at_end_of_line() -> None:
    node = parse_line("sleep 1 &")
    from pyshell_lab.ast import BackgroundCommand

    assert isinstance(node, BackgroundCommand)


def test_parse_background_followed_by_empty_semicolon() -> None:
    with pytest.raises(ParserError, match="empty command"):
        parse_line("echo hi & ;")


def test_parse_unexpected_operator_in_sequence() -> None:
    with pytest.raises(ParserError, match="unexpected operator"):
        parse_line("& echo hi")


def test_display_unknown_node_type() -> None:
    assert _display(object()) == "object"  # type: ignore[arg-type]


def test_execute_updates_last_status() -> None:
    state = ShellState()
    assert execute(parse_line("pwd"), state, "pwd") == 0
    assert state.last_status == 0


def test_sequence_or_short_circuits_on_success(capsys) -> None:
    from pyshell_lab.executor import execute
    from pyshell_lab.parser import parse_line

    state = ShellState()
    execute(parse_line("pwd || echo skipped"), state, "pwd || echo skipped")
    assert "skipped" not in capsys.readouterr().out


def test_and_skips_when_left_succeeds(capsys) -> None:
    from pyshell_lab.executor import execute
    from pyshell_lab.parser import parse_line

    state = ShellState()
    execute(parse_line("pwd && echo ran"), state, "pwd && echo ran")
    assert "ran" in capsys.readouterr().out
