"""Test repl."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from pyshell_lab import config, history
from pyshell_lab.repl import Shell
from pyshell_lab.state import ShellState

POSIX = os.name != "nt" and hasattr(os, "fork")


def test_execute_line_blank_preserves_last_status() -> None:
    state = ShellState()
    state.last_status = 7
    shell = Shell(state)
    assert shell.execute_line("   ") == 7
    assert state.last_status == 7


def test_interactive_eof_exits_with_last_status(monkeypatch) -> None:
    shell = Shell()
    monkeypatch.setattr("builtins.input", lambda _prompt: (_ for _ in ()).throw(EOFError))
    monkeypatch.setattr(history, "load_history", lambda _state: None)
    monkeypatch.setattr(history, "save_history", lambda _state: None)
    assert shell.run_interactive(load_rc=False) == 0


def test_interactive_keyboard_interrupt_sets_status_130(monkeypatch) -> None:
    shell = Shell()
    calls = {"n": 0}

    def fake_input(_prompt: str) -> str:
        calls["n"] += 1
        if calls["n"] == 1:
            raise KeyboardInterrupt
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    monkeypatch.setattr(history, "load_history", lambda _state: None)
    monkeypatch.setattr(history, "save_history", lambda _state: None)
    assert shell.run_interactive(load_rc=False) == 130


def test_report_finished_jobs_prints_completion(capsys) -> None:
    from pyshell_lab.jobs import JobStatus, JobTable

    state = ShellState()
    job = state.jobs.add("sleep 1", [9999], 9999)
    job.status = JobStatus.DONE
    job.pids.clear()
    job.exit_status = 0

    original_reap = JobTable.reap_finished

    def fake_reap(self) -> list:
        return [job]

    JobTable.reap_finished = fake_reap  # type: ignore[method-assign]
    try:
        Shell(state)._report_finished_jobs()
    finally:
        JobTable.reap_finished = original_reap  # type: ignore[method-assign]

    out = capsys.readouterr().out
    assert "[1] done     sleep 1" in out


def test_script_does_not_clobber_history_file(tmp_path, monkeypatch) -> None:
    history_path = tmp_path / "hist"
    history_path.write_text("saved line\n", encoding="utf-8")
    monkeypatch.setattr(history, "default_history_path", lambda: history_path)
    monkeypatch.setattr(history, "load_history", lambda _state: None)

    script = tmp_path / "s.psh"
    script.write_text("echo hi\n", encoding="utf-8")
    Shell().run_script(script, load_rc=False)
    assert history_path.read_text(encoding="utf-8") == "saved line\n"


def test_execute_line_expansion_error_returns_2(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("echo ${UNCLOSED") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capsys.readouterr().err.lower()


def test_execute_line_parser_error_returns_2(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("echo hi |") == 2
    assert shell.state.last_status == 2


def test_execute_line_lexer_error_returns_2(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("echo 'unclosed") == 2
    assert shell.state.last_status == 2
    assert "quote" in capsys.readouterr().err.lower()


def test_bare_path_variable_does_not_affect_type_or_which() -> None:
    import io
    import os
    import sys

    from pyshell_lab.builtins import run_builtin

    state = ShellState()
    state.exported_env.pop("PATH", None)
    state.variables["PATH"] = os.path.dirname(sys.executable)
    out = io.StringIO()
    err = io.StringIO()
    exe = os.path.basename(sys.executable)
    assert run_builtin(state, ["type", exe], out, err) == 1
    assert "not found" in err.getvalue()
    err = io.StringIO()
    assert run_builtin(state, ["which", exe], out, err) == 1
    assert "not found" in err.getvalue()


def test_run_script_missing_file_returns_1(tmp_path, capsys) -> None:
    missing = tmp_path / "missing.psh"
    assert Shell().run_script(missing, load_rc=False) == 1
    assert "missing.psh" in capsys.readouterr().err.lower()


def test_exit_invalid_numeric_keeps_shell_running(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("exit not-a-number") == 2
    assert shell.execute_line("echo still-here") == 0
    assert "still-here" in capsys.readouterr().out


def test_redirect_expansion_error_returns_2(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("ls > ${UNCLOSED") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capsys.readouterr().err.lower()


def test_builtin_redirect_expansion_error_returns_2(capsys) -> None:
    shell = Shell()
    assert shell.execute_line("echo ok > ${UNCLOSED") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capsys.readouterr().err.lower()


@pytest.mark.skipif(not POSIX, reason="script job reap requires POSIX")
def test_script_reaps_background_jobs(tmp_path, capfd) -> None:
    script = tmp_path / "bg.psh"
    script.write_text("sleep 0.2 &\nsleep 0.3\n", encoding="utf-8")
    Shell().run_script(script)
    out = capfd.readouterr().out
    assert "done sleep 0.2 &" in out


def test_rc_read_failure_prints_message(tmp_path, capsys, monkeypatch) -> None:
    rc = tmp_path / "rc"
    rc.write_text("echo hi\n", encoding="utf-8")
    monkeypatch.setattr(config, "default_rc_path", lambda: rc)

    original_read = Path.read_text

    def failing_read(self, *args, **kwargs):
        if self == rc:
            raise OSError("permission denied")
        return original_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", failing_read)
    status = config.run_rc_file(ShellState(), lambda _line: 0, path=rc)
    err = capsys.readouterr().err
    assert status == 1
    assert "permission denied" in err
