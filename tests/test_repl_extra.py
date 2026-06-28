"""Test repl extra."""

from __future__ import annotations

from pathlib import Path

from pyshell_lab import config, history
from pyshell_lab.errors import ShellExit
from pyshell_lab.repl import Shell
from pyshell_lab.state import ShellState


def test_prompt_includes_status_and_cwd() -> None:
    state = ShellState(last_status=3)
    assert shell_prompt(state) == f"pyshell[3] {state.cwd}$ "


def shell_prompt(state: ShellState) -> str:
    return Shell(state).prompt()


def test_execute_line_without_remember(tmp_path) -> None:
    state = ShellState()
    shell = Shell(state)
    shell.execute_line("echo hi", remember=False)
    assert state.history == []


def test_execute_line_execution_error_returns_1(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("FOO=bar | echo hi") == 1
    assert "assignment-only" in capsys.readouterr().err


def test_run_interactive_rc_exit(monkeypatch, tmp_path) -> None:
    rc = tmp_path / "rc"
    rc.write_text("exit 5\n", encoding="utf-8")
    monkeypatch.setattr(config, "default_rc_path", lambda: rc)
    monkeypatch.setattr(history, "load_history", lambda _s: None)
    monkeypatch.setattr(history, "save_history", lambda _s: None)
    assert Shell().run_interactive() == 5


def test_run_interactive_shell_exit_breaks_loop(monkeypatch) -> None:
    shell = Shell()
    calls = {"n": 0}

    def fake_input(_prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            return "exit 3"
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(history, "load_history", lambda _s: None)
    monkeypatch.setattr(history, "save_history", lambda _s: None)

    def fake_execute(_line: str, *, remember: bool = True) -> int:
        raise ShellExit(3)

    monkeypatch.setattr(shell, "execute_line", fake_execute)
    assert shell.run_interactive(load_rc=False) == 3


def test_run_interactive_internal_error_survives(monkeypatch) -> None:
    shell = Shell()
    calls = {"n": 0}

    def fake_input(_prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(history, "load_history", lambda _s: None)
    monkeypatch.setattr(history, "save_history", lambda _s: None)
    assert shell.run_interactive(load_rc=False) == 1


def test_run_interactive_saves_history_on_exit(monkeypatch) -> None:
    saved: list[bool] = []
    monkeypatch.setattr(history, "load_history", lambda _s: None)
    monkeypatch.setattr(history, "save_history", lambda _s: saved.append(True))
    monkeypatch.setattr("builtins.input", lambda _p: (_ for _ in ()).throw(EOFError))
    Shell().run_interactive(load_rc=False)
    assert saved == [True]


def test_run_script_keyboard_interrupt(tmp_path) -> None:
    script = tmp_path / "s.psh"
    script.write_text("echo hi\n", encoding="utf-8")
    shell = Shell()

    def interrupt(_line: str, *, remember: bool = True) -> int:
        raise KeyboardInterrupt

    shell.execute_line = interrupt  # type: ignore[method-assign]
    assert shell.run_script(script, load_rc=False) == 130


def test_run_script_internal_errors_continue(tmp_path, capsys) -> None:
    script = tmp_path / "s.psh"
    script.write_text("line1\nline2\n", encoding="utf-8")
    shell = Shell()
    calls = {"n": 0}

    def flaky(_line: str, *, remember: bool = True) -> int:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk")
        if calls["n"] == 2:
            raise ValueError("bug")
        return 0

    shell.execute_line = flaky  # type: ignore[method-assign]
    assert shell.run_script(script, load_rc=False) == 1
    err = capsys.readouterr().err
    assert "disk" in err
    assert "bug" in err


def test_run_script_read_uses_strerror_or_message(tmp_path, monkeypatch, capsys) -> None:
    script = tmp_path / "s.psh"
    script.write_text("echo hi\n", encoding="utf-8")
    original = Path.read_text

    def fail_read(self, *args, **kwargs):
        if self == script:
            exc = OSError()
            exc.strerror = None
            raise exc
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    assert Shell().run_script(script, load_rc=False) == 1
