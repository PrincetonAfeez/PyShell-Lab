"""Quote-sensitive word expansion."""

from __future__ import annotations

import os
import re

from .ast import ESCAPE_MARKER, CommandWord
from .errors import ExpansionError
from .state import ShellState

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def expand_words(
    words: tuple[CommandWord, ...],
    state: ShellState,
    *,
    variables_overlay: dict[str, str] | None = None,
) -> list[str]:
    return [expand_word(word, state, variables_overlay=variables_overlay) for word in words]


def expand_word(
    word: CommandWord,
    state: ShellState,
    *,
    variables_overlay: dict[str, str] | None = None,
) -> str:
    pieces: list[str] = []
    for index, part in enumerate(word.parts):
        text = part.text
        if index == 0 and part.quote == "none":
            text = expand_tilde(text, state)
        if part.quote == "single":
            pieces.append(_strip_escapes(text))
        else:
            pieces.append(_expand_variables(text, state, variables_overlay))
    return "".join(pieces)


def expand_tilde(text: str, state: ShellState) -> str:
    if text == "~":
        return _home(state)
    if text.startswith("~/"):
        return _home(state) + text[1:]
    return text


def _home(state: ShellState) -> str:
    # Shared HOME resolution (shell variable, then exported env), with the OS
    # home as a final fallback so a bare tilde always expands to something.
    return state.home() or os.path.expanduser("~")


def _expand_variables(
    text: str,
    state: ShellState,
    variables_overlay: dict[str, str] | None,
) -> str:
    result: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == ESCAPE_MARKER and i + 1 < len(text):
            result.append(text[i + 1])
            i += 2
            continue
        if char != "$":
            result.append(char)
            i += 1
            continue

        if i + 1 >= len(text):
            result.append("$")
            i += 1
            continue

        next_char = text[i + 1]
        if next_char == "?":
            result.append(str(state.last_status))
            i += 2
            continue
        if next_char == "$":
            result.append(str(os.getpid()))
            i += 2
            continue
        if next_char == "{":
            end = text.find("}", i + 2)
            if end == -1:
                raise ExpansionError("unclosed parameter expansion")
            name = text[i + 2 : end]
            result.append(_lookup(name, state, variables_overlay))
            i = end + 1
            continue

        match = _NAME_RE.match(text, i + 1)
        if match is None:
            result.append("$")
            i += 1
            continue
        result.append(_lookup(match.group(0), state, variables_overlay))
        i = match.end()

    return "".join(result)


def _strip_escapes(text: str) -> str:
    result: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == ESCAPE_MARKER and i + 1 < len(text):
            result.append(text[i + 1])
            i += 2
        else:
            result.append(text[i])
            i += 1
    return "".join(result)


def _lookup(
    name: str,
    state: ShellState,
    variables_overlay: dict[str, str] | None,
) -> str:
    if variables_overlay is not None and name in variables_overlay:
        return variables_overlay[name]
    if name in state.variables:
        return state.variables[name]
    return state.exported_env.get(name, "")
