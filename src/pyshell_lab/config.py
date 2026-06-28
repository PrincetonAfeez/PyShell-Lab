"""Startup configuration helpers."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from .errors import ShellExit
from .state import ShellState

Executor = Callable[[str], int]


def default_rc_path() -> Path:
    return Path(os.path.expanduser("~/.pyshellrc"))


def run_rc_file(state: ShellState, execute_line: Executor, path: Path | None = None) -> int:
    rc_path = path or default_rc_path()
    if not rc_path.exists():
        return 0
    status = 0
    rc_exit: ShellExit | None = None

    def run_line(line: str) -> int:
        nonlocal rc_exit
        try:
            return execute_line(line)
        except ShellExit as exc:
            rc_exit = exc
            return exc.status & 0xFF

    try:
        for line in rc_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            status = run_line(line)
    except OSError as exc:
        message = exc.strerror or str(exc)
        print(f"pyshell: {rc_path}: {message}", file=sys.stderr)
        return 1
    if rc_exit is not None:
        raise rc_exit
    return status
