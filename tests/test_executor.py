"""Test executor."""

from __future__ import annotations

import os
import time

import pytest

from pyshell_lab.executor import execute
from pyshell_lab.jobs import JobStatus
from pyshell_lab.parser import parse_line
from pyshell_lab.state import ShellState

POSIX = os.name != "nt" and hasattr(os, "fork")


def run(line: str, state: ShellState | None = None) -> int:
    shell_state = state or ShellState()
    return execute(parse_line(line), shell_state, line)


# --- Sequences and conditionals (builtin-only, so they run on every platform) ---


def test_sequence_runs_each_command(capsys) -> None:
    run("echo one ; echo two")
    assert capsys.readouterr().out == "one\ntwo\n"


def test_and_short_circuits_on_failure(capsys) -> None:
    # `which` of a missing name returns 1, so && must skip the echo; ; continues.
    run("which __pyshell_missing__ && echo nope ; echo done")
    out = capsys.readouterr().out
    assert "nope" not in out
    assert "done" in out


def test_or_runs_right_side_on_failure(capsys) -> None:
    run("which __pyshell_missing__ || echo recovered")
    assert "recovered" in capsys.readouterr().out


def test_exit_status_tracked_across_sequence() -> None:
    state = ShellState()
    run("which __pyshell_missing__", state)
    assert state.last_status == 1
    run("pwd", state)
    assert state.last_status == 0


# --- Variable assignment (handled in the shell process, no fork needed) ---


def test_bare_assignment_sets_shell_variable() -> None:
    state = ShellState()
    assert run("FOO=bar", state) == 0
    assert state.variables["FOO"] == "bar"


def test_assignment_value_is_expanded() -> None:
    state = ShellState()
    run("X=hello", state)
    run("Y=$X-world", state)
    assert state.variables["Y"] == "hello-world"


def test_prefix_assignment_does_not_persist(capsys) -> None:
    state = ShellState()
    run("PREFIX=tmp echo done", state)
    capsys.readouterr()
    assert "PREFIX" not in state.variables


def test_chained_assignment_sees_earlier_values() -> None:
    state = ShellState()
    run("A=1 B=$A", state)
    assert state.variables["A"] == "1"
    assert state.variables["B"] == "1"


def test_prefix_assignment_preserves_builtin_mutation(capsys) -> None:
    # The prefix FOO must not wipe the export the builtin performs.
    state = ShellState()
    run("FOO=tmp export EXPORTED=2", state)
    capsys.readouterr()
    assert state.exported_env.get("EXPORTED") == "2"
    assert "FOO" not in state.variables
    assert "FOO" not in state.exported_env


def test_prefix_assignment_cd_keeps_pwd_consistent(tmp_path) -> None:
    old = os.getcwd()
    state = ShellState(cwd=old)
    try:
        run(f"FOO=tmp cd {tmp_path.as_posix()}", state)
        # pwd (state.cwd) and $PWD (state.variables['PWD']) must agree.
        assert state.cwd == state.variables["PWD"]
        assert os.path.samefile(state.cwd, str(tmp_path))
        assert "FOO" not in state.variables
    finally:
        os.chdir(old)


def test_tilde_in_assignment_value() -> None:
    state = ShellState()
    state.exported_env["HOME"] = "/home/student"
    run("T=~/work", state)
    assert state.variables["T"] == "/home/student/work"


def test_failed_redirection_does_not_corrupt_shell_stdout(tmp_path, capfd) -> None:
    # The second redirect fails after the first applied; the shell's stdout must
    # be restored so later output still reaches it and not the redirect target.
    ok = tmp_path / "ok.txt"
    bad = tmp_path / "missing_dir" / "err.txt"  # parent dir absent -> open fails
    state = ShellState()
    assert run(f"pwd > {ok.as_posix()} 2> {bad.as_posix()}", state) == 1

    run("echo BACK-ON-STDOUT", state)
    assert "BACK-ON-STDOUT" in capfd.readouterr().out
    # The stray output must not have leaked into the redirect target.
    assert ok.read_text(encoding="utf-8") == ""


def test_cd_no_args_uses_shell_variable_home(tmp_path) -> None:
    old = os.getcwd()
    state = ShellState(cwd=old)
    try:
        run(f"HOME={tmp_path.as_posix()}", state)  # bare assignment -> shell var
        assert run("cd", state) == 0
        assert os.path.samefile(state.cwd, str(tmp_path))
    finally:
        os.chdir(old)


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_2redirect_1_merges_stderr_into_stdout(tmp_path) -> None:
    out = tmp_path / "merged.txt"
    # An external command's stderr, with 2>&1, must land in the stdout file.
    # (Builtins write via sys.stderr, which pytest replaces, so an external
    # command is the faithful way to exercise the fd-level duplication.)
    run(f"ls __no_such_path__ > {out.as_posix()} 2>&1")
    assert "__no_such_path__" in out.read_text(encoding="utf-8")


def test_empty_expanded_command_is_a_noop() -> None:
    state = ShellState()
    state.last_status = 5
    assert run("$EMPTY", state) == 0  # unset var -> empty -> no-op
    assert state.last_status == 0


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_empty_expanded_command_applies_redirection(tmp_path) -> None:
    target = tmp_path / "out.txt"
    state = ShellState()
    assert run(f"$EMPTY > {target.as_posix()}", state) == 0
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == ""


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_assignment_only_command_applies_redirection_side_effect(tmp_path) -> None:
    target = tmp_path / "out.txt"
    assert run(f"FOO=bar > {target.as_posix()}") == 0
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == ""


def test_pipeline_noop_stage_redirect_expansion_error_before_fork(capsys) -> None:
    from pyshell_lab.repl import Shell

    shell = Shell()
    assert shell.execute_line("$EMPTY > ${UNCLOSED | echo hi") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capsys.readouterr().err.lower()


def test_cd_empty_operand_is_a_noop() -> None:
    old = os.getcwd()
    state = ShellState(cwd=old)
    try:
        assert run('cd ""', state) == 0
        assert state.cwd == old
    finally:
        os.chdir(old)


def test_rc_file_exit_is_clean(tmp_path, monkeypatch) -> None:
    from pyshell_lab import config
    from pyshell_lab.repl import Shell

    rc = tmp_path / "rc"
    rc.write_text("echo from-rc\nexit 7\n", encoding="utf-8")
    monkeypatch.setattr(config, "default_rc_path", lambda: rc)

    script = tmp_path / "s.psh"
    script.write_text("echo SHOULD-NOT-RUN\n", encoding="utf-8")

    # rc 'exit 7' must exit startup cleanly with 7, not raise a traceback.
    assert Shell().run_script(script, load_rc=True) == 7


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_external_command_exit_statuses() -> None:
    state = ShellState()
    assert run("true", state) == 0
    assert state.last_status == 0
    assert run("false", state) == 1
    assert state.last_status == 1


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_unknown_command_returns_127(capfd) -> None:
    status = run("definitely-not-a-real-command")
    captured = capfd.readouterr()
    assert status == 127
    assert "command not found" in captured.err


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_redirection_writes_file(tmp_path) -> None:
    target = tmp_path / "out.txt"
    state = ShellState()
    assert run(f"echo hello > {target}", state) == 0
    assert target.read_text(encoding="utf-8") == "hello\n"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_input_redirection_reads_file(tmp_path, capfd) -> None:
    source = tmp_path / "in.txt"
    source.write_text("hello\n", encoding="utf-8")
    assert run(f"cat < {source}") == 0
    captured = capfd.readouterr()
    assert captured.out == "hello\n"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_pipeline_produces_expected_output(capfd) -> None:
    assert run("printf hello | wc -c") == 0
    captured = capfd.readouterr()
    assert captured.out.strip() == "5"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_builtin_in_pipeline_flushes_output(capfd) -> None:
    # echo is a builtin; its buffered output must survive os._exit in the child.
    assert run("echo hello | wc -c") == 0
    captured = capfd.readouterr()
    assert captured.out.strip() == "6"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_multi_stage_pipeline_does_not_hang(capfd) -> None:
    assert run("printf 'a\\nb\\na\\n' | sort | uniq | wc -l") == 0
    captured = capfd.readouterr()
    assert captured.out.strip() == "2"


@pytest.mark.skipif(not POSIX, reason="background job tests require POSIX")
def test_background_job_appears_and_is_reaped(capfd) -> None:
    state = ShellState()
    assert run("sleep 0.2 &", state) == 0
    capfd.readouterr()  # discard the "[1] <pid>" notice

    jobs = state.jobs.all()
    assert len(jobs) == 1
    assert jobs[0].status == JobStatus.RUNNING

    reaped: list = []
    deadline = time.time() + 3.0
    while time.time() < deadline:
        reaped = state.jobs.reap_finished()
        if reaped:
            break
        time.sleep(0.05)

    assert len(reaped) == 1
    assert reaped[0].status == JobStatus.DONE
    assert reaped[0].exit_status == 0


def test_external_execution_reports_platform_on_windows() -> None:
    if POSIX:
        pytest.skip("platform guard is only observable without fork")
    from pyshell_lab.repl import Shell

    assert Shell().execute_line("true") == 1


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_empty_expanded_command_in_pipeline_is_a_noop(capfd) -> None:
    assert run("$EMPTY | wc -c") == 0
    captured = capfd.readouterr()
    assert captured.out.strip() == "0"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_prefix_assignment_in_pipeline_stage(capsys) -> None:
    assert run("PREFIX=tmp echo hi | wc -c") == 0
    assert capsys.readouterr().out.strip() == "3"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_prefix_assignment_not_visible_to_same_line_expansion(capfd) -> None:
    run("FOO=bar echo $FOO")
    captured = capfd.readouterr()
    assert captured.out.strip() == ""


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_prefix_assignment_visible_to_external_command_env(tmp_path, capfd) -> None:
    out = tmp_path / "env.txt"
    run(f"FOO=bar env > {out.as_posix()}")
    assert "FOO=bar" in out.read_text(encoding="utf-8")


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_append_redirect(tmp_path) -> None:
    target = tmp_path / "out.txt"
    target.write_text("old\n", encoding="utf-8")
    assert run(f"echo new >> {target}") == 0
    assert target.read_text(encoding="utf-8") == "old\nnew\n"


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_stderr_redirect_to_file(tmp_path) -> None:
    target = tmp_path / "err.txt"
    run(f"ls __no_such_path__ 2> {target.as_posix()}")
    assert "__no_such_path__" in target.read_text(encoding="utf-8")


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_stdout_redirect_to_stderr(capfd) -> None:
    run("echo merged >&2")
    captured = capfd.readouterr()
    assert "merged" in captured.err


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_close_stderr_redirect(capfd) -> None:
    run("echo quiet 2>&-")
    captured = capfd.readouterr()
    assert captured.out.strip() == "quiet"
    assert captured.err == ""


@pytest.mark.skipif(not POSIX, reason="background job tests require POSIX")
def test_background_pipeline(capfd) -> None:
    state = ShellState()
    assert run("printf hi | wc -c &", state) == 0
    capfd.readouterr()  # discard job notice

    reaped = state.jobs.reap_finished()
    deadline = time.time() + 3.0
    while time.time() < deadline and not reaped:
        time.sleep(0.05)
        reaped = state.jobs.reap_finished()
    assert reaped
    assert reaped[0].status == JobStatus.DONE


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_pipeline_fork_failure_cleans_up_children(monkeypatch, capfd) -> None:
    calls = {"fork": 0}
    original_fork = os.fork

    def flaky_fork():
        calls["fork"] += 1
        if calls["fork"] == 2:
            raise OSError("resource temporarily unavailable")
        return original_fork()

    monkeypatch.setattr(os, "fork", flaky_fork)
    status = run("printf a | printf b | wc -c")
    assert status == 1
    assert "fork failed" in capfd.readouterr().err


def test_assignment_only_pipeline_stage_rejected(capfd) -> None:
    from pyshell_lab.repl import Shell

    assert Shell().execute_line("FOO=bar | echo hi") == 1
    assert "assignment-only pipeline" in capfd.readouterr().err


def test_background_command_sequence_rejected(monkeypatch, capfd) -> None:
    from pyshell_lab import executor
    from pyshell_lab.ast import (
        BackgroundCommand,
        CommandSequence,
        CommandWord,
        SequenceItem,
        SimpleCommand,
        WordPart,
    )
    from pyshell_lab.repl import Shell

    def word(text: str) -> CommandWord:
        return CommandWord((WordPart(text),))

    sequence = CommandSequence(
        (
            SequenceItem(SimpleCommand((word("echo"), word("a")))),
            SequenceItem(SimpleCommand((word("echo"), word("b"))), ";"),
        )
    )
    background = BackgroundCommand(sequence)

    monkeypatch.setattr(executor, "_require_posix", lambda: None)
    monkeypatch.setattr("pyshell_lab.repl.parse_line", lambda _line: background)
    assert Shell().execute_line("echo a; echo b &") == 1
    assert "only simple commands and pipelines" in capfd.readouterr().err


def test_prefix_assignment_expansion_error_returns_2(capfd) -> None:
    from pyshell_lab.repl import Shell

    shell = Shell()
    assert shell.execute_line("FOO=${UNCLOSED echo hi") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capfd.readouterr().err.lower()


def test_assignment_only_expansion_error_returns_2(capfd) -> None:
    from pyshell_lab.repl import Shell

    shell = Shell()
    assert shell.execute_line("FOO=${UNCLOSED") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capfd.readouterr().err.lower()


def test_pipeline_expansion_error_before_fork(capfd) -> None:
    from pyshell_lab.repl import Shell

    shell = Shell()
    assert shell.execute_line("echo ok | echo ${UNCLOSED") == 2
    assert shell.state.last_status == 2
    assert "unclosed" in capfd.readouterr().err.lower()


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_empty_redirection_target_returns_1(capfd) -> None:
    state = ShellState()
    state.variables["EMPTY"] = ""
    assert run("echo hi > $EMPTY", state) == 1
    assert "redirection failed" in capfd.readouterr().err


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_pipe_failure_returns_1(monkeypatch, capfd) -> None:
    def fail_pipe() -> tuple[int, int]:
        raise OSError("too many open files")

    monkeypatch.setattr(os, "pipe", fail_pipe)
    assert run("echo a | echo b") == 1
    assert "pipe failed" in capfd.readouterr().err


@pytest.mark.skipif(not POSIX, reason="fork/exec tests require POSIX")
def test_permission_denied_returns_126(tmp_path, capfd) -> None:
    script = tmp_path / "nope.sh"
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    script.chmod(0o644)
    status = run(f"{script.as_posix()}")
    assert status == 126
    assert "permission denied" in capfd.readouterr().err
