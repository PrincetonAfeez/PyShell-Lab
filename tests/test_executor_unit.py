"""Test executor unit."""

from __future__ import annotations

import os

import pytest

from pyshell_lab.ast import (
    BackgroundCommand,
    CommandSequence,
    CommandWord,
    Pipeline,
    SequenceItem,
    SimpleCommand,
    WordPart,
)
from pyshell_lab.errors import ExecutionError
from pyshell_lab.executor import (
    _apply_fd_duplication,
    _apply_temp_assignments,
    _close_many,
    _display,
    _require_posix,
    _restore_temp_assignments,
    _set_child_pgid,
    execute,
)
from pyshell_lab.state import ShellState


def _word(text: str) -> CommandWord:
    return CommandWord((WordPart(text),))


def _simple(*words: str) -> SimpleCommand:
    return SimpleCommand(tuple(_word(w) for w in words))


def test_execute_none_returns_last_status() -> None:
    state = ShellState(last_status=9)
    assert execute(None, state) == 9


def test_display_all_node_types() -> None:
    simple = _simple("echo", "hi")
    pipeline = Pipeline((simple, _simple("wc")))
    bg = BackgroundCommand(pipeline)
    seq = CommandSequence(
        (
            SequenceItem(simple),
            SequenceItem(bg, ";"),
        )
    )
    assert _display(simple) == "echo hi"
    assert _display(pipeline) == "echo hi | wc"
    assert _display(bg) == "echo hi | wc &"
    assert "; echo hi | wc &" in _display(seq)


def test_require_posix_raises_on_windows(monkeypatch) -> None:
    monkeypatch.setattr(os, "name", "nt")
    with pytest.raises(ExecutionError, match="POSIX"):
        _require_posix()


def test_apply_temp_assignments_and_restore() -> None:
    state = ShellState()
    state.variables["KEEP"] = "old"
    saved = _apply_temp_assignments(state, [("NEW", "1"), ("KEEP", "tmp")])
    assert state.variables["NEW"] == "1"
    assert state.variables["KEEP"] == "tmp"
    _restore_temp_assignments(state, saved)
    assert "NEW" not in state.variables
    assert state.variables["KEEP"] == "old"


def test_restore_temp_assignments_restores_exported_env() -> None:
    state = ShellState()
    state.exported_env["X"] = "env-old"
    saved = _apply_temp_assignments(state, [("X", "env-new")])
    _restore_temp_assignments(state, saved)
    assert state.exported_env["X"] == "env-old"


def test_apply_fd_duplication_bad_descriptor(tmp_path) -> None:
    from pyshell_lab.ast import Redirection

    state = ShellState()
    redir = Redirection("2>&", _word("not-a-fd"))
    with pytest.raises(OSError, match="bad file descriptor"):
        _apply_fd_duplication(redir, state, [], save=False)


def test_close_many_ignores_errors() -> None:
    _close_many([-1, -2])


def test_set_child_pgid_swallows_oserror(monkeypatch) -> None:
    if not hasattr(os, "setpgid"):
        pytest.skip("setpgid requires POSIX")

    def fail_setpgid(*_args) -> None:
        raise OSError("fail")

    monkeypatch.setattr(os, "setpgid", fail_setpgid)
    _set_child_pgid(1, 1)
