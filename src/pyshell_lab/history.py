"""In-memory and persisted history support."""

from __future__ import annotations

import os
from pathlib import Path

from .state import ShellState

try:
    import readline
except ImportError:  # pragma: no cover - platform dependent
    readline = None  # type: ignore[assignment]

HISTORY_LIMIT = 1000


def default_history_path() -> Path:
    return Path(os.path.expanduser("~/.pyshell_history"))


def _trim_history(state: ShellState) -> None:
    if len(state.history) > HISTORY_LIMIT:
        del state.history[:-HISTORY_LIMIT]


def _history_payload(state: ShellState) -> str:
    if not state.history:
        return ""
    return "\n".join(state.history[-HISTORY_LIMIT:]) + "\n"


def load_history(state: ShellState, path: Path | None = None) -> None:
    history_path = path or default_history_path()
    if history_path.exists():
        try:
            lines = history_path.read_text(encoding="utf-8").splitlines()
            state.history.extend(line for line in lines if line)
            _trim_history(state)
        except OSError:
            return
    if readline is not None:
        for line in state.history:
            readline.add_history(line)


def remember(state: ShellState, line: str) -> None:
    if not line.strip():
        return
    state.history.append(line)
    _trim_history(state)
    if readline is not None:
        readline.add_history(line)


def save_history(state: ShellState, path: Path | None = None) -> None:
    history_path = path or default_history_path()
    payload = _history_payload(state)
    try:
        if history_path.exists() and history_path.read_text(encoding="utf-8") == payload:
            return
        history_path.write_text(payload, encoding="utf-8")
    except OSError:
        pass
