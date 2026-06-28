"""Test config."""

from __future__ import annotations

import pytest

from pyshell_lab import config
from pyshell_lab.repl import Shell
from pyshell_lab.state import ShellState


def test_run_rc_file_passes_unstripped_line(tmp_path) -> None:
    rc = tmp_path / "rc"
    rc.write_text("  export SPACED=value  \n", encoding="utf-8")
    state = ShellState()
    config.run_rc_file(state, lambda line: Shell(state).execute_line(line, remember=False), path=rc)
    assert state.exported_env.get("SPACED") == "value"


def test_run_rc_file_exit_stops_with_status(tmp_path) -> None:
    from pyshell_lab.errors import ShellExit

    rc = tmp_path / "rc"
    rc.write_text("exit 9\n", encoding="utf-8")
    shell = Shell()
    with pytest.raises(ShellExit) as excinfo:
        config.run_rc_file(
            shell.state,
            lambda line: shell.execute_line(line, remember=False),
            path=rc,
        )
    assert excinfo.value.status == 9


def test_run_rc_file_continues_after_parse_error(tmp_path, capsys) -> None:
    rc = tmp_path / "rc"
    rc.write_text("echo bad |\nexport OK=1\n", encoding="utf-8")
    state = ShellState()
    status = config.run_rc_file(
        state,
        lambda line: Shell(state).execute_line(line, remember=False),
        path=rc,
    )
    err = capsys.readouterr().err
    assert status == 0
    assert state.exported_env.get("OK") == "1"
    assert "unexpected operator" in err or "missing command" in err
