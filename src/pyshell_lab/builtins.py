"""Shell builtins, including commands that must mutate parent state."""

from __future__ import annotations

import re
import shutil
import sys
from collections.abc import Callable
from typing import TextIO

from .errors import ShellExit
from .jobs import JobStatus, format_job_line
from .state import ShellState

BuiltinFunc = Callable[[ShellState, list[str], TextIO, TextIO], int]

# ASCII shell-variable name, consistent with expansion and assignment parsing.
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Backslash escapes interpreted by ``echo -e``.
_ECHO_ESCAPES = {
    "\\": "\\",
    "a": "\a",
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}


def is_builtin(name: str) -> bool:
    return name in BUILTINS


def run_builtin(
    state: ShellState,
    argv: list[str],
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    if not argv or argv[0] not in BUILTINS:
        return 127
    return BUILTINS[argv[0]](state, argv, stdout or sys.stdout, stderr or sys.stderr)


def _cd(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) > 2:
        print("cd: too many arguments", file=stderr)
        return 2
    if len(argv) == 1:
        target = state.home()
        if not target:
            print("cd: HOME not set", file=stderr)
            return 1
    elif argv[1] == "-":
        if not state.previous_cwd:
            print("cd: OLDPWD not set", file=stderr)
            return 1
        target = state.previous_cwd
        print(target, file=stdout)
    elif argv[1] == "":
        # Empty operand: a no-op, matching common shell behavior.
        return 0
    else:
        target = argv[1]

    try:
        state.set_cwd(target)
    except OSError as exc:
        print(f"cd: {target}: {exc.strerror}", file=stderr)
        return 1
    return 0


def _pwd(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) > 1:
        print("pwd: too many arguments", file=stderr)
        return 2
    print(state.cwd, file=stdout)
    return 0


def _exit(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) > 2:
        print("exit: too many arguments", file=stderr)
        return 2
    if len(argv) == 2:
        try:
            status = int(argv[1])
        except ValueError:
            print(f"exit: {argv[1]}: numeric argument required", file=stderr)
            return 2
    else:
        status = state.last_status
    # Process exit statuses are 8-bit; mask so $? stays in 0-255.
    raise ShellExit(status & 0xFF)


def _reject_extra_args(name: str, argv: list[str], stderr: TextIO) -> int | None:
    if len(argv) > 1:
        print(f"{name}: too many arguments", file=stderr)
        return 2
    return None


def _help(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if (status := _reject_extra_args("help", argv, stderr)) is not None:
        return status
    print("PyShell Lab builtins:", file=stdout)
    for name in sorted(BUILTINS):
        print(f"  {name}", file=stdout)
    return 0


def _echo(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    args = list(argv[1:])
    trailing_newline = True
    interpret = False
    # Consume leading -n/-e/-E flags (including combined forms like -ne).
    while args and len(args[0]) >= 2 and args[0][0] == "-" and set(args[0][1:]) <= {"n", "e", "E"}:
        flag = args.pop(0)
        if "n" in flag:
            trailing_newline = False
        if "e" in flag:
            interpret = True
        if "E" in flag:
            interpret = False
    text = " ".join(args)
    if interpret:
        text, stop = _decode_echo_escapes(text)
        if stop:
            # \c stops output, including the trailing newline.
            trailing_newline = False
    print(text, file=stdout, end="\n" if trailing_newline else "")
    return 0


def _decode_echo_escapes(text: str) -> tuple[str, bool]:
    """Decode ``echo -e`` escapes. Returns (decoded, stop) where stop is True if
    a ``\\c`` was seen (output should end immediately)."""

    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in _ECHO_ESCAPES:
                result.append(_ECHO_ESCAPES[nxt])
                i += 2
                continue
            if nxt == "c":
                return "".join(result), True
            if nxt == "x":
                digits = _take(text, i + 2, 2, "0123456789abcdefABCDEF")
                if digits:
                    result.append(chr(int(digits, 16)))
                    i += 2 + len(digits)
                    continue
            if nxt == "0":
                digits = _take(text, i + 2, 3, "01234567")
                result.append(chr(int(digits, 8)) if digits else "\0")
                i += 2 + len(digits)
                continue
        result.append(text[i])
        i += 1
    return "".join(result), False


def _take(text: str, start: int, limit: int, alphabet: str) -> str:
    end = start
    while end < len(text) and end - start < limit and text[end] in alphabet:
        end += 1
    return text[start:end]


def _export(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) == 1:
        for name, value in sorted(state.exported_env.items()):
            print(f"export {name}={value}", file=stdout)
        return 0

    status = 0
    for assignment in argv[1:]:
        if "=" in assignment:
            name, value = assignment.split("=", 1)
            if not _valid_name(name):
                print(f"export: {name}: invalid name", file=stderr)
                status = 2
                continue
            state.variables[name] = value
            state.exported_env[name] = value
        else:
            if not _valid_name(assignment):
                print(f"export: {assignment}: invalid name", file=stderr)
                status = 2
                continue
            value = state.variables.get(assignment, state.exported_env.get(assignment, ""))
            state.exported_env[assignment] = value
    return status


def _unset(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) == 1:
        print("unset: not enough arguments", file=stderr)
        return 2
    status = 0
    for name in argv[1:]:
        if not _valid_name(name):
            print(f"unset: {name}: invalid name", file=stderr)
            status = 2
            continue
        state.variables.pop(name, None)
        state.exported_env.pop(name, None)
    return status


def _env(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if (status := _reject_extra_args("env", argv, stderr)) is not None:
        return status
    for name, value in sorted(state.environment().items()):
        print(f"{name}={value}", file=stdout)
    return 0


def _set(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) == 1:
        for name, value in sorted(state.variables.items()):
            print(f"{name}={value}", file=stdout)
        return 0

    status = 0
    for assignment in argv[1:]:
        if "=" not in assignment:
            print(f"set: expected NAME=value, got {assignment!r}", file=stderr)
            status = 2
            continue
        name, value = assignment.split("=", 1)
        if not _valid_name(name):
            print(f"set: {name}: invalid name", file=stderr)
            status = 2
            continue
        state.variables[name] = value
    return status


def _history(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if (status := _reject_extra_args("history", argv, stderr)) is not None:
        return status
    for index, line in enumerate(state.history, start=1):
        print(f"{index:5d}  {line}", file=stdout)
    return 0


def _jobs(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if (status := _reject_extra_args("jobs", argv, stderr)) is not None:
        return status
    state.jobs.reap_finished()
    finished: list[int] = []
    for job in state.jobs.all():
        print(format_job_line(job), file=stdout)
        if job.status != JobStatus.RUNNING:
            finished.append(job.job_id)
    # A completed job is listed once, then dropped so it does not linger forever.
    for job_id in finished:
        state.jobs.remove(job_id)
    return 0


def _command_path(state: ShellState, name: str) -> str | None:
    # Empty PATH means no search, matching ``execvpe`` / ``state.environment()``.
    return shutil.which(name, path=state.exported_env.get("PATH", ""))


def _type(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) == 1:
        print("type: not enough arguments", file=stderr)
        return 2
    status = 0
    for name in argv[1:]:
        if is_builtin(name):
            print(f"{name} is a shell builtin", file=stdout)
            continue
        path = _command_path(state, name)
        if path:
            print(f"{name} is {path}", file=stdout)
        else:
            print(f"{name}: not found", file=stderr)
            status = 1
    return status


def _which(state: ShellState, argv: list[str], stdout: TextIO, stderr: TextIO) -> int:
    if len(argv) == 1:
        print("which: not enough arguments", file=stderr)
        return 2
    status = 0
    for name in argv[1:]:
        path = _command_path(state, name)
        if path:
            print(path, file=stdout)
        else:
            print(f"{name}: not found", file=stderr)
            status = 1
    return status


def _valid_name(name: str) -> bool:
    # ASCII only, matching $name expansion and assignment detection elsewhere.
    return _NAME_RE.fullmatch(name) is not None


BUILTINS: dict[str, BuiltinFunc] = {
    "cd": _cd,
    "pwd": _pwd,
    "exit": _exit,
    "help": _help,
    "echo": _echo,
    "export": _export,
    "unset": _unset,
    "env": _env,
    "set": _set,
    "history": _history,
    "jobs": _jobs,
    "type": _type,
    "which": _which,
}
