"""Test builtins extra."""

from __future__ import annotations

import io
import os

from pyshell_lab.builtins import BUILTINS, is_builtin, run_builtin
from pyshell_lab.state import ShellState


def test_is_builtin_and_unknown_command() -> None:
    assert is_builtin("cd")
    assert not is_builtin("ls")
    assert run_builtin(ShellState(), ["not-a-builtin"], io.StringIO(), io.StringIO()) == 127


def test_cd_home_without_home_set() -> None:
    state = ShellState()
    state.variables.pop("HOME", None)
    state.exported_env.pop("HOME", None)
    err = io.StringIO()
    assert run_builtin(state, ["cd"], io.StringIO(), err) == 1
    assert "HOME not set" in err.getvalue()


def test_cd_dash_requires_oldpwd(tmp_path) -> None:
    state = ShellState()
    state.previous_cwd = None
    err = io.StringIO()
    assert run_builtin(state, ["cd", "-"], io.StringIO(), err) == 1
    assert "OLDPWD not set" in err.getvalue()


def test_cd_dash_prints_target(tmp_path) -> None:
    old = os.getcwd()
    state = ShellState(cwd=old)
    out = io.StringIO()
    err = io.StringIO()
    try:
        assert run_builtin(state, ["cd", str(tmp_path)], out, err) == 0
        out = io.StringIO()
        assert run_builtin(state, ["cd", "-"], out, err) == 0
        assert old in out.getvalue()
        assert os.path.samefile(state.cwd, old)
    finally:
        os.chdir(old)


def test_cd_empty_operand_is_noop() -> None:
    state = ShellState()
    before = state.cwd
    assert run_builtin(state, ["cd", ""], io.StringIO(), io.StringIO()) == 0
    assert state.cwd == before


def test_cd_too_many_arguments() -> None:
    err = io.StringIO()
    assert run_builtin(ShellState(), ["cd", "a", "b"], io.StringIO(), err) == 2


def test_cd_missing_directory(tmp_path) -> None:
    missing = tmp_path / "nope"
    err = io.StringIO()
    assert run_builtin(ShellState(), ["cd", str(missing)], io.StringIO(), err) == 1


def test_exit_too_many_arguments() -> None:
    err = io.StringIO()
    assert run_builtin(ShellState(), ["exit", "1", "2"], io.StringIO(), err) == 2


def test_export_lists_exported_variables() -> None:
    state = ShellState()
    state.exported_env["A"] = "1"
    out = io.StringIO()
    assert run_builtin(state, ["export"], out, io.StringIO()) == 0
    assert "export A=1" in out.getvalue()


def test_export_name_without_equals_invalid() -> None:
    err = io.StringIO()
    assert run_builtin(ShellState(), ["export", "1BAD"], io.StringIO(), err) == 2


def test_set_lists_shell_variables() -> None:
    state = ShellState()
    state.variables["LOCAL"] = "v"
    out = io.StringIO()
    assert run_builtin(state, ["set"], out, io.StringIO()) == 0
    assert "LOCAL=v" in out.getvalue()


def test_set_rejects_non_assignment() -> None:
    err = io.StringIO()
    assert run_builtin(ShellState(), ["set", "not-an-assignment"], io.StringIO(), err) == 2


def test_set_invalid_name_partial_failure() -> None:
    state = ShellState()
    err = io.StringIO()
    status = run_builtin(state, ["set", "GOOD=1", "1BAD=2"], io.StringIO(), err)
    assert status == 2
    assert state.variables["GOOD"] == "1"
    assert "1BAD" not in state.variables


def test_help_lists_all_builtins() -> None:
    out = io.StringIO()
    assert run_builtin(ShellState(), ["help"], out, io.StringIO()) == 0
    text = out.getvalue()
    for name in BUILTINS:
        assert name in text


def test_env_lists_environment() -> None:
    state = ShellState()
    state.exported_env["DEMO"] = "yes"
    out = io.StringIO()
    assert run_builtin(state, ["env"], out, io.StringIO()) == 0
    assert "DEMO=yes" in out.getvalue()


def test_type_partial_failure() -> None:
    state = ShellState()
    out = io.StringIO()
    err = io.StringIO()
    status = run_builtin(state, ["type", "cd", "missing-cmd-xyz"], out, err)
    assert status == 1
    assert "shell builtin" in out.getvalue()
    assert "not found" in err.getvalue()


def test_which_partial_failure() -> None:
    state = ShellState()
    out = io.StringIO()
    err = io.StringIO()
    status = run_builtin(state, ["which", "cd", "missing-cmd-xyz"], out, err)
    assert status == 1
    assert "not found" in err.getvalue()


def test_echo_e_flag_disables_interpretation() -> None:
    out = io.StringIO()
    assert run_builtin(ShellState(), ["echo", "-E", r"\n"], out, io.StringIO()) == 0
    assert out.getvalue() == "\\n\n"


def test_echo_combined_ne_flags() -> None:
    out = io.StringIO()
    assert run_builtin(ShellState(), ["echo", "-ne", "hi"], out, io.StringIO()) == 0
    assert out.getvalue() == "hi"
