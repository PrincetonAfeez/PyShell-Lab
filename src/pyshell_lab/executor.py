"""Executor that runs parsed commands using POSIX process primitives."""

from __future__ import annotations

import os
import re
import signal
import sys
from collections.abc import Iterable

from . import signals
from .ast import (
    BackgroundCommand,
    CommandNode,
    CommandSequence,
    CommandWord,
    Pipeline,
    Redirection,
    SimpleCommand,
)
from .builtins import is_builtin, run_builtin
from .errors import ExecutionError, ExpansionError, ShellExit
from .expansion import expand_tilde, expand_word, expand_words
from .jobs import decode_wait_status
from .state import ShellState

REDIRECT_SPECS = {
    ">": (1, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666),
    ">>": (1, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o666),
    "<": (0, os.O_RDONLY, 0),
    "2>": (2, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666),
}

# File-descriptor duplication: the operator names the fd being changed.
# "2>&1" makes fd 2 a copy of fd 1; ">&2" makes fd 1 a copy of fd 2.
DUP_SOURCES = {">&": 1, "2>&": 2}

# A leading word of the form NAME= introduces a variable assignment.
_ASSIGNMENT_PREFIX = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")

Assignment = tuple[str, str]


def execute(node: CommandNode | None, state: ShellState, command_line: str = "") -> int:
    if node is None:
        return state.last_status
    status = _execute_node(node, state, command_line or _display(node))
    state.last_status = status
    return status


def _execute_node(node: CommandNode, state: ShellState, command_line: str) -> int:
    if isinstance(node, CommandSequence):
        return _execute_sequence(node, state, command_line)
    if isinstance(node, BackgroundCommand):
        return _execute_background(node, state, command_line)
    if isinstance(node, Pipeline):
        return _execute_pipeline(node, state, command_line, foreground=True)
    if isinstance(node, SimpleCommand):
        return _execute_simple(node, state, foreground=True, command_line=command_line)
    raise ExecutionError(f"unsupported command node: {type(node).__name__}")


def _execute_sequence(sequence: CommandSequence, state: ShellState, command_line: str) -> int:
    status = state.last_status
    for item in sequence.items:
        if item.connector == "&&" and status != 0:
            continue
        if item.connector == "||" and status == 0:
            continue
        status = _execute_node(item.command, state, _display(item.command))
        state.last_status = status
    return status


def _execute_background(node: BackgroundCommand, state: ShellState, command_line: str) -> int:
    _require_posix()
    if isinstance(node.command, Pipeline):
        return _execute_pipeline(node.command, state, command_line, foreground=False)
    if isinstance(node.command, SimpleCommand):
        return _execute_simple(node.command, state, foreground=False, command_line=command_line)
    raise ExecutionError("only simple commands and pipelines can run in the background")


def _execute_simple(
    command: SimpleCommand,
    state: ShellState,
    *,
    foreground: bool,
    command_line: str,
) -> int:
    assignments, remaining = _collect_assignments(command.words, state)

    if not remaining:
        # Assignment-only command (e.g. ``FOO=bar``): mutate shell variables in
        # the shell process itself. Any redirections are still performed so a
        # file target is created, then undone, matching shell behavior.
        try:
            saved = _apply_redirections(command.redirections, state, save=True)
        except OSError as exc:
            print(f"pyshell: redirection failed: {exc}", file=sys.stderr)
            return 1
        try:
            for name, value in assignments:
                state.variables[name] = value
        finally:
            _restore_fds(saved)
        return 0

    # A non-empty command always expands to at least one argument.
    argv = expand_words(remaining, state)

    # A command that expands to a single empty string (e.g. an unset ``$VAR``)
    # is a no-op, matching the "empty line is a no-op" rule rather than failing.
    # Redirection side effects still apply, like assignment-only commands.
    if argv == [""]:
        if command.redirections:
            try:
                saved = _apply_redirections(command.redirections, state, save=True)
            except OSError as exc:
                print(f"pyshell: redirection failed: {exc}", file=sys.stderr)
                return 1
            finally:
                _restore_fds(saved)
        return 0

    _validate_redirections(command.redirections, state)

    # Foreground builtins must run in the shell process so they can mutate it.
    if foreground and is_builtin(argv[0]):
        return _run_builtin_in_parent(command, argv, state, assignments)

    _require_posix()
    try:
        pid = os.fork()
    except OSError as exc:
        print(f"pyshell: fork failed: {exc}", file=sys.stderr)
        return 1
    if pid == 0:
        # Foreground jobs stay in the shell's process group (pgid=None) so they
        # remain the terminal's foreground group; background jobs get their own.
        _run_child_simple(
            command,
            argv,
            state,
            pgid=None if foreground else 0,
            env_overrides=dict(assignments),
        )

    if not foreground:
        _set_child_pgid(pid, pid)
        job = state.jobs.add(command_line, [pid], pid)
        print(f"[{job.job_id}] {pid}")
        return 0

    return _wait_for_pids([pid], foreground=True)


def _run_builtin_in_parent(
    command: SimpleCommand,
    argv: list[str],
    state: ShellState,
    assignments: list[Assignment],
) -> int:
    saved_fds: list[tuple[int, int]] = []
    saved_assignments = _apply_temp_assignments(state, assignments)
    try:
        saved_fds = _apply_redirections(command.redirections, state, save=True)
        return run_builtin(state, argv)
    except ExpansionError as exc:
        print(f"pyshell: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"pyshell: redirection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        _restore_fds(saved_fds)
        _restore_temp_assignments(state, saved_assignments)


def _prepare_pipeline_stage(
    command: SimpleCommand, state: ShellState
) -> tuple[list[Assignment], list[str] | None]:
    """Return stage assignments and argv, or ``None`` argv for a no-op stage."""

    assignments, remaining = _collect_assignments(command.words, state)
    if not remaining:
        if assignments:
            raise ExecutionError("assignment-only pipeline stages are not supported")
        argv: list[str] | None = None
    else:
        expanded = expand_words(remaining, state)
        argv = None if expanded == [""] else expanded
    if command.redirections:
        _validate_redirections(command.redirections, state)
    return assignments, argv


def _execute_pipeline(
    pipeline: Pipeline,
    state: ShellState,
    command_line: str,
    *,
    foreground: bool,
) -> int:
    commands = list(pipeline.commands)
    stages = [_prepare_pipeline_stage(command, state) for command in commands]
    _require_posix()
    try:
        pipes = [os.pipe() for _ in range(max(0, len(commands) - 1))]
    except OSError as exc:
        print(f"pyshell: pipe failed: {exc}", file=sys.stderr)
        return 1

    pids: list[int] = []
    pgid: int | None = None

    try:
        for index, command in enumerate(commands):
            assignments, argv = stages[index]
            try:
                pid = os.fork()
            except OSError as exc:
                _cleanup_pipeline_children(pids)
                print(f"pyshell: fork failed: {exc}", file=sys.stderr)
                return 1
            if pid == 0:
                # Foreground pipelines stay in the shell's process group; a
                # background pipeline becomes one new group led by its first pid.
                stage_pgid = None if foreground else (pgid or 0)
                env_overrides = dict(assignments)
                if argv is None:
                    _run_child_pipeline_noop(
                        command, state, pipes, index, stage_pgid, env_overrides
                    )
                else:
                    _run_child_pipeline_stage(
                        command,
                        argv,
                        state,
                        pipes,
                        index,
                        stage_pgid,
                        env_overrides,
                    )
            if not foreground:
                if pgid is None:
                    pgid = pid
                _set_child_pgid(pid, pgid)
            pids.append(pid)
    finally:
        _close_many(fd for pipe in pipes for fd in pipe)

    if not foreground:
        assert pgid is not None
        job = state.jobs.add(command_line, pids, pgid)
        print(f"[{job.job_id}] {pgid}")
        return 0

    return _wait_for_pids(pids, last_pid=pids[-1], foreground=True)


def _run_child_pipeline_noop(
    command: SimpleCommand,
    state: ShellState,
    pipes: list[tuple[int, int]],
    index: int,
    pgid: int | None,
    env_overrides: dict[str, str],
) -> None:
    try:
        signals.restore_default_child_signals()
        if pgid is not None:
            os.setpgid(0, pgid)
        if index > 0:
            os.dup2(pipes[index - 1][0], 0)
        if index < len(pipes):
            os.dup2(pipes[index][1], 1)
        _close_many(fd for pipe in pipes for fd in pipe)
        _apply_redirections(command.redirections, state, save=False)
        if env_overrides:
            state.variables.update(env_overrides)
            state.exported_env.update(env_overrides)
        _exit_child(0)
    except BaseException as exc:
        _child_fail(exc)


def _run_child_pipeline_stage(
    command: SimpleCommand,
    argv: list[str],
    state: ShellState,
    pipes: list[tuple[int, int]],
    index: int,
    pgid: int | None,
    env_overrides: dict[str, str] | None = None,
) -> None:
    try:
        signals.restore_default_child_signals()
        if pgid is not None:
            os.setpgid(0, pgid)
        if index > 0:
            os.dup2(pipes[index - 1][0], 0)
        if index < len(pipes):
            os.dup2(pipes[index][1], 1)
        _close_many(fd for pipe in pipes for fd in pipe)
        _apply_redirections(command.redirections, state, save=False)
        _exec_or_builtin(argv, state, env_overrides)
    except BaseException as exc:
        _child_fail(exc)


def _run_child_simple(
    command: SimpleCommand,
    argv: list[str],
    state: ShellState,
    pgid: int | None,
    env_overrides: dict[str, str] | None = None,
) -> None:
    try:
        signals.restore_default_child_signals()
        if pgid is not None:
            os.setpgid(0, pgid)
        _apply_redirections(command.redirections, state, save=False)
        _exec_or_builtin(argv, state, env_overrides)
    except BaseException as exc:
        _child_fail(exc)


def _exec_or_builtin(
    argv: list[str],
    state: ShellState,
    env_overrides: dict[str, str] | None = None,
) -> None:
    if not argv or argv == [""]:
        _exit_child(0)
    if is_builtin(argv[0]):
        if env_overrides:
            state.variables.update(env_overrides)
            state.exported_env.update(env_overrides)
        try:
            status = run_builtin(state, argv)
        except ShellExit as exc:
            status = exc.status
        _exit_child(status)
    env = state.environment()
    if env_overrides:
        env.update(env_overrides)
    try:
        os.execvpe(argv[0], argv, env)
    except FileNotFoundError:
        print(f"{argv[0]}: command not found", file=sys.stderr)
        _exit_child(127)
    except PermissionError:
        print(f"{argv[0]}: permission denied", file=sys.stderr)
        _exit_child(126)
    except OSError as exc:
        print(f"{argv[0]}: {exc.strerror}", file=sys.stderr)
        _exit_child(126)


def _collect_assignments(
    words: tuple[CommandWord, ...], state: ShellState
) -> tuple[list[Assignment], tuple[CommandWord, ...]]:
    """Peel leading ``NAME=value`` words off the front of a command.

    Each value is expanded with the earlier assignments on the same line already
    visible, so ``A=1 B=$A`` yields ``B=1``. The shell's own variables are not
    mutated here; the caller decides whether the assignments persist.
    """

    assignments: list[Assignment] = []
    # A throwaway overlay (built only when needed) so a later value can read an
    # earlier one without touching the real shell state during collection.
    overlay: dict[str, str] | None = None
    index = 0
    for word in words:
        name = _assignment_name(word)
        if name is None:
            break
        if overlay is None:
            overlay = dict(state.variables)
        value = _assignment_value(word, name, state, overlay)
        assignments.append((name, value))
        overlay[name] = value
        index += 1
    return assignments, words[index:]


def _assignment_name(word: CommandWord) -> str | None:
    # The name must come from an unquoted leading part: ``"FOO"=bar`` is a
    # command, not an assignment.
    if not word.parts or word.parts[0].quote != "none":
        return None
    match = _ASSIGNMENT_PREFIX.match(word.text)
    if match is None:
        return None
    return word.text[: match.end() - 1]


def _assignment_value(
    word: CommandWord, name: str, state: ShellState, overlay: dict[str, str]
) -> str:
    # Expand the value with the overlay (earlier same-line assignments) visible.
    expanded = expand_word(word, state, variables_overlay=overlay)
    # ``name=`` has no expandable characters, so it survives expansion verbatim.
    value = expanded[len(name) + 1 :]
    # A leading tilde in an unquoted value expands (``FOO=~`` -> home).
    first = word.parts[0]
    if first.quote == "none" and first.rendered()[len(name) + 1 :].startswith("~"):
        value = expand_tilde(value, state)
    return value


def _apply_temp_assignments(
    state: ShellState, assignments: list[Assignment]
) -> list[tuple[str, bool, str | None, bool, str | None]] | None:
    """Apply prefix assignments to a builtin's environment, recording only the
    affected names so the builtin's *other* mutations survive the restore."""

    if not assignments:
        return None
    saved: list[tuple[str, bool, str | None, bool, str | None]] = []
    for name, value in assignments:
        saved.append(
            (
                name,
                name in state.variables,
                state.variables.get(name),
                name in state.exported_env,
                state.exported_env.get(name),
            )
        )
        state.variables[name] = value
        state.exported_env[name] = value
    return saved


def _restore_temp_assignments(
    state: ShellState,
    saved: list[tuple[str, bool, str | None, bool, str | None]] | None,
) -> None:
    if not saved:
        return
    for name, had_var, var_val, had_env, env_val in reversed(saved):
        if had_var:
            state.variables[name] = var_val  # type: ignore[assignment]
        else:
            state.variables.pop(name, None)
        if had_env:
            state.exported_env[name] = env_val  # type: ignore[assignment]
        else:
            state.exported_env.pop(name, None)


def _validate_redirections(redirections: tuple[Redirection, ...], state: ShellState) -> None:
    """Expand redirection targets in the parent so expansion errors surface early."""

    for redirection in redirections:
        expand_word(redirection.target, state)


def _apply_redirections(
    redirections: tuple[Redirection, ...],
    state: ShellState,
    *,
    save: bool,
) -> list[tuple[int, int]]:
    saved: list[tuple[int, int]] = []
    try:
        for redirection in redirections:
            if redirection.operator in DUP_SOURCES:
                _apply_fd_duplication(redirection, state, saved, save=save)
                continue
            target_fd, flags, mode = REDIRECT_SPECS[redirection.operator]
            filename = expand_word(redirection.target, state)
            if not filename:
                raise OSError("empty redirection target")
            if save:
                saved.append((target_fd, os.dup(target_fd)))
            if redirection.operator == "<":
                fd = os.open(filename, flags)
            else:
                fd = os.open(filename, flags, mode)
            try:
                os.dup2(fd, target_fd)
            finally:
                os.close(fd)
    except BaseException:
        # A later redirection failed after earlier ones were applied. Undo the
        # partial work so the parent shell's own fds are not left redirected
        # (and the saved backups are not leaked). The child path saves nothing.
        if save:
            _restore_fds(saved)
        raise
    return saved


def _apply_fd_duplication(
    redirection: Redirection,
    state: ShellState,
    saved: list[tuple[int, int]],
    *,
    save: bool,
) -> None:
    source_fd = DUP_SOURCES[redirection.operator]
    target = expand_word(redirection.target, state)
    if save:
        saved.append((source_fd, os.dup(source_fd)))
    if target == "-":
        # "2>&-" closes the descriptor.
        try:
            os.close(source_fd)
        except OSError:
            pass
        return
    try:
        dest_fd = int(target)
    except ValueError:
        raise OSError(f"bad file descriptor in redirection: {target!r}") from None
    os.dup2(dest_fd, source_fd)


def _restore_fds(saved_fds: list[tuple[int, int]]) -> None:
    for target_fd, saved_fd in reversed(saved_fds):
        try:
            os.dup2(saved_fd, target_fd)
        finally:
            os.close(saved_fd)


def _wait_for_pids(
    pids: list[int], last_pid: int | None = None, *, foreground: bool = False
) -> int:
    # While a foreground job owns the terminal the shell ignores SIGINT so that
    # a terminal Ctrl-C reaches the child (default disposition) instead.
    previous = signals.ignore_sigint_in_parent() if foreground else None
    status_by_pid: dict[int, int] = {}
    try:
        for pid in pids:
            while True:
                try:
                    waited_pid, status_word = os.waitpid(pid, 0)
                    break
                except InterruptedError:
                    continue
            status_by_pid[waited_pid] = decode_wait_status(status_word)
    finally:
        if foreground:
            signals.restore_sigint_in_parent(previous)

    if last_pid is None:
        last_pid = pids[-1]
    return status_by_pid.get(last_pid, 1)


def _cleanup_pipeline_children(pids: list[int]) -> None:
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    for pid in pids:
        try:
            os.waitpid(pid, 0)
        except (ChildProcessError, OSError):
            pass


def _set_child_pgid(pid: int, pgid: int) -> None:
    try:
        os.setpgid(pid, pgid)
    except OSError:
        pass


def _close_many(fds: Iterable[int]) -> None:
    for fd in fds:
        try:
            os.close(fd)
        except OSError:
            pass


def _exit_child(status: int) -> None:
    # os._exit skips Python's buffer flushing, so flush first or builtin output
    # written to a pipe or redirected file would be lost.
    try:
        sys.stdout.flush()
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(status)


def _child_fail(exc: BaseException) -> None:
    if isinstance(exc, ExpansionError):
        print(f"pyshell: {exc}", file=sys.stderr)
        _exit_child(2)
    print(f"pyshell: child setup failed: {exc}", file=sys.stderr)
    _exit_child(1)


def _require_posix() -> None:
    if os.name == "nt" or not hasattr(os, "fork"):
        raise ExecutionError("external command execution requires POSIX/Linux/macOS/WSL")


def _display(node: CommandNode) -> str:
    if isinstance(node, SimpleCommand):
        return node.display
    if isinstance(node, Pipeline):
        return node.display
    if isinstance(node, BackgroundCommand):
        return _display(node.command) + " &"
    if isinstance(node, CommandSequence):
        parts: list[str] = []
        for item in node.items:
            if item.connector:
                parts.append(item.connector)
            parts.append(_display(item.command))
        return " ".join(parts)
    return type(node).__name__
