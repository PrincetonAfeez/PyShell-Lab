"""Test state."""

from __future__ import annotations

import os

from pyshell_lab.state import ShellState


def test_environment_includes_pwd_and_exported() -> None:
    state = ShellState()
    state.exported_env["FOO"] = "bar"
    env = state.environment()
    assert env["FOO"] == "bar"
    assert env["PWD"] == state.cwd


def test_home_prefers_shell_variable() -> None:
    state = ShellState()
    state.variables["HOME"] = "/var/home/me"
    state.exported_env["HOME"] = "/other"
    assert state.home() == "/var/home/me"


def test_home_falls_back_to_exported_env() -> None:
    state = ShellState()
    state.variables.pop("HOME", None)
    state.exported_env["HOME"] = "/exported/home"
    assert state.home() == "/exported/home"


def test_home_returns_none_when_unset() -> None:
    state = ShellState()
    state.variables.pop("HOME", None)
    state.exported_env.pop("HOME", None)
    assert state.home() is None


def test_set_cwd_updates_all_pwd_fields(tmp_path) -> None:
    old = os.getcwd()
    state = ShellState(cwd=old)
    try:
        state.set_cwd(str(tmp_path))
        assert state.cwd == os.getcwd()
        assert state.variables["PWD"] == state.cwd
        assert state.exported_env["PWD"] == state.cwd
        assert state.variables["OLDPWD"] == old
        assert state.previous_cwd == old
    finally:
        os.chdir(old)


def test_post_init_sets_pwd_defaults() -> None:
    state = ShellState()
    assert state.variables["PWD"] == state.cwd
    assert state.exported_env["PWD"] == state.cwd
