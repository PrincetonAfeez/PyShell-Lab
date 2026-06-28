"""Test builtins."""

from __future__ import annotations

import io
import os

import pytest

from pyshell_lab.builtins import run_builtin
from pyshell_lab.errors import ShellExit
from pyshell_lab.state import ShellState


def test_cd_and_pwd_update_shell_process(tmp_path) -> None:
    old = os.getcwd()
    state = ShellState(cwd=old)
    out = io.StringIO()
    err = io.StringIO()
    try:
        assert run_builtin(state, ["cd", str(tmp_path)], out, err) == 0
        assert state.cwd == str(tmp_path)
        assert os.getcwd() == str(tmp_path)
        assert state.previous_cwd == old
        assert run_builtin(state, ["pwd"], out, err) == 0
        assert str(tmp_path) in out.getvalue()
    finally:
        os.chdir(old)


def test_export_unset_env_and_set() -> None:
    state = ShellState()
    out = io.StringIO()
    err = io.StringIO()

    assert run_builtin(state, ["set", "LOCAL=value"], out, err) == 0
    assert state.variables["LOCAL"] == "value"
    assert "LOCAL" not in state.exported_env

    assert run_builtin(state, ["export", "LOCAL"], out, err) == 0
    assert state.exported_env["LOCAL"] == "value"

    assert run_builtin(state, ["unset", "LOCAL"], out, err) == 0
    assert "LOCAL" not in state.variables
    assert "LOCAL" not in state.exported_env


def test_export_invalid_name_returns_2_but_exports_valid_names() -> None:
    state = ShellState()
    state.variables["GOOD"] = "yes"
    out = io.StringIO()
    err = io.StringIO()
    status = run_builtin(state, ["export", "GOOD", "1BAD=val", "ALSO=ok"], out, err)
    assert status == 2
    assert state.exported_env["GOOD"] == "yes"
    assert state.exported_env["ALSO"] == "ok"
    assert "1BAD" not in state.exported_env
    assert "invalid name" in err.getvalue()


def test_history_type_and_which() -> None:
    state = ShellState()
    state.history.extend(["echo hi", "pwd"])
    out = io.StringIO()
    err = io.StringIO()

    assert run_builtin(state, ["history"], out, err) == 0
    assert "echo hi" in out.getvalue()

    out = io.StringIO()
    assert run_builtin(state, ["type", "cd"], out, err) == 0
    assert "shell builtin" in out.getvalue()

    out = io.StringIO()
    status = run_builtin(state, ["which", "definitely-not-a-real-command"], out, err)
    assert status == 1


def test_echo_flags() -> None:
    state = ShellState()
    err = io.StringIO()

    out = io.StringIO()
    assert run_builtin(state, ["echo", "-n", "hi"], out, err) == 0
    assert out.getvalue() == "hi"

    out = io.StringIO()
    assert run_builtin(state, ["echo", "-e", r"a\tb\nc"], out, err) == 0
    assert out.getvalue() == "a\tb\nc\n"

    out = io.StringIO()
    assert run_builtin(state, ["echo", "plain", "text"], out, err) == 0
    assert out.getvalue() == "plain text\n"


def test_echo_e_hex_octal_and_stop() -> None:
    state = ShellState()
    err = io.StringIO()

    out = io.StringIO()
    assert run_builtin(state, ["echo", "-e", r"\x41\x42"], out, err) == 0
    assert out.getvalue() == "AB\n"

    out = io.StringIO()
    assert run_builtin(state, ["echo", "-e", r"\0101"], out, err) == 0  # octal 101 = 'A'
    assert out.getvalue() == "A\n"

    out = io.StringIO()
    assert run_builtin(state, ["echo", "-e", r"a\cb"], out, err) == 0  # \c stops output
    assert out.getvalue() == "a"


def test_exit_masks_status_to_one_byte() -> None:
    state = ShellState()
    out = io.StringIO()
    err = io.StringIO()
    with pytest.raises(ShellExit) as excinfo:
        run_builtin(state, ["exit", "300"], out, err)
    assert excinfo.value.status == 44  # 300 & 0xFF


def test_exit_without_args_uses_last_status() -> None:
    state = ShellState(last_status=7)
    out = io.StringIO()
    err = io.StringIO()
    with pytest.raises(ShellExit) as excinfo:
        run_builtin(state, ["exit"], out, err)
    assert excinfo.value.status == 7


def test_exit_invalid_numeric_returns_2_without_exiting() -> None:
    state = ShellState()
    out = io.StringIO()
    err = io.StringIO()
    assert run_builtin(state, ["exit", "not-a-number"], out, err) == 2
    assert "numeric argument required" in err.getvalue()


def test_unset_path_breaks_type_and_which() -> None:
    import os
    import sys

    state = ShellState()
    state.exported_env["PATH"] = os.path.dirname(sys.executable)
    out = io.StringIO()
    err = io.StringIO()
    exe = os.path.basename(sys.executable)
    assert run_builtin(state, ["type", exe], out, err) == 0
    assert run_builtin(state, ["unset", "PATH"], out, err) == 0
    err = io.StringIO()
    assert run_builtin(state, ["type", exe], out, err) == 1
    assert "not found" in err.getvalue()
    err = io.StringIO()
    assert run_builtin(state, ["which", exe], out, err) == 1
    assert "not found" in err.getvalue()


def test_which_not_found_prints_to_stderr() -> None:
    state = ShellState()
    out = io.StringIO()
    err = io.StringIO()
    assert run_builtin(state, ["which", "definitely-not-a-real-command"], out, err) == 1
    assert "not found" in err.getvalue()


def test_valid_name_is_ascii_only() -> None:
    from pyshell_lab.builtins import _valid_name

    assert _valid_name("FOO_1")
    assert _valid_name("_x")
    assert not _valid_name("")
    assert not _valid_name("1abc")
    assert not _valid_name("a-b")
    assert not _valid_name("café")  # non-ASCII must be rejected, like $name


def test_pwd_rejects_extra_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["pwd", "extra"], io.StringIO(), err) == 2
    assert "too many arguments" in err.getvalue()


def test_unset_requires_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["unset"], io.StringIO(), err) == 2


def test_type_requires_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["type"], io.StringIO(), err) == 2


def test_which_requires_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["which"], io.StringIO(), err) == 2


def test_unset_rejects_invalid_name() -> None:
    state = ShellState()
    state.variables["OK"] = "1"
    err = io.StringIO()
    assert run_builtin(state, ["unset", "1BAD"], io.StringIO(), err) == 2
    assert "invalid name" in err.getvalue()
    assert state.variables["OK"] == "1"


def test_help_rejects_extra_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["help", "extra"], io.StringIO(), err) == 2


def test_env_rejects_extra_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["env", "extra"], io.StringIO(), err) == 2


def test_history_rejects_extra_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["history", "extra"], io.StringIO(), err) == 2


def test_jobs_rejects_extra_arguments() -> None:
    state = ShellState()
    err = io.StringIO()
    assert run_builtin(state, ["jobs", "extra"], io.StringIO(), err) == 2


def test_jobs_builtin_lists_running_job() -> None:
    from pyshell_lab.jobs import JobStatus

    state = ShellState()
    job = state.jobs.add("sleep 5", [4242], 4242)
    out = io.StringIO()
    err = io.StringIO()
    assert run_builtin(state, ["jobs"], out, err) == 0
    assert f"[{job.job_id}] running  sleep 5" in out.getvalue()

    job.status = JobStatus.DONE
    job.pids.clear()
    job.exit_status = 0
    out = io.StringIO()
    assert run_builtin(state, ["jobs"], out, err) == 0
    assert "done" in out.getvalue()
    assert job.job_id not in state.jobs.jobs
