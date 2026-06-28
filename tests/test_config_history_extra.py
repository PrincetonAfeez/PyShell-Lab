"""Test config history extra."""

from __future__ import annotations

from pathlib import Path

from pyshell_lab import config, history
from pyshell_lab.repl import Shell
from pyshell_lab.state import ShellState


def test_default_rc_path_uses_home(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyshell_lab.config.os.path.expanduser", lambda p: "/tmp/testhome/.pyshellrc"
    )
    assert config.default_rc_path() == Path("/tmp/testhome/.pyshellrc")


def test_run_rc_file_missing_returns_zero() -> None:
    state = ShellState()
    assert config.run_rc_file(state, lambda _line: 0, path=Path("/no/such/rc")) == 0


def test_run_rc_file_skips_comments_and_blanks(tmp_path) -> None:
    rc = tmp_path / "rc"
    rc.write_text("# comment\n\n  \nexport OK=1\n", encoding="utf-8")
    state = ShellState()
    config.run_rc_file(
        state,
        lambda line: Shell(state).execute_line(line, remember=False),
        path=rc,
    )
    assert state.exported_env.get("OK") == "1"


def test_run_rc_file_returns_last_line_status(tmp_path) -> None:
    rc = tmp_path / "rc"
    rc.write_text("which __missing_pyshell_cmd__\n", encoding="utf-8")
    state = ShellState()
    status = config.run_rc_file(
        state,
        lambda line: Shell(state).execute_line(line, remember=False),
        path=rc,
    )
    assert status == 1


def test_default_history_path_uses_home(monkeypatch) -> None:
    monkeypatch.setattr(
        "pyshell_lab.history.os.path.expanduser",
        lambda p: "/tmp/histhome/.pyshell_history",
    )
    assert history.default_history_path() == Path("/tmp/histhome/.pyshell_history")


def test_remember_skips_blank_lines() -> None:
    state = ShellState()
    history.remember(state, "   ")
    assert state.history == []


def test_load_history_oserror_is_ignored(tmp_path, monkeypatch) -> None:
    path = tmp_path / "hist"
    path.write_text("line\n", encoding="utf-8")
    state = ShellState()
    original = Path.read_text

    def fail_read(self, *args, **kwargs):
        if self == path:
            raise OSError("denied")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    history.load_history(state, path=path)
    assert state.history == []


def test_remember_and_load_use_readline_when_available(monkeypatch, tmp_path) -> None:
    added: list[str] = []

    class FakeReadline:
        @staticmethod
        def add_history(line: str) -> None:
            added.append(line)

    monkeypatch.setattr(history, "readline", FakeReadline())
    path = tmp_path / "h"
    path.write_text("saved\n", encoding="utf-8")
    state = ShellState()
    history.remember(state, "first")
    assert "first" in added
    state2 = ShellState()
    history.load_history(state2, path=path)
    assert "saved" in added


def test_save_history_oserror_is_silent(tmp_path, monkeypatch) -> None:
    path = tmp_path / "hist"
    state = ShellState(history=["x"])

    def fail_write(self, data, *args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(Path, "write_text", fail_write)
    history.save_history(state, path=path)  # should not raise
