"""Test expansion."""

from __future__ import annotations

import os

import pytest

from pyshell_lab.expansion import expand_word, expand_words
from pyshell_lab.parser import parse_line
from pyshell_lab.state import ShellState


def _words(line: str):
    node = parse_line(line)
    assert hasattr(node, "words")
    return node.words


def test_variable_expansion_forms() -> None:
    state = ShellState()
    state.variables["NAME"] = "Ada"
    state.last_status = 7
    words = _words("echo $NAME ${NAME} $? $$")
    expanded = expand_words(words, state)
    assert expanded[:4] == ["echo", "Ada", "Ada", "7"]
    assert expanded[4] == str(os.getpid())


def test_single_quotes_suppress_expansion_and_double_quotes_allow_it() -> None:
    state = ShellState()
    state.variables["NAME"] = "Ada"
    words = _words("echo '$NAME' \"$NAME\"")
    assert expand_words(words, state) == ["echo", "$NAME", "Ada"]


def test_single_quoted_part_strips_escape_markers() -> None:
    from pyshell_lab.ast import ESCAPE_MARKER, CommandWord, WordPart

    state = ShellState()
    word = CommandWord((WordPart(f"lit{ESCAPE_MARKER}eral", "single"),))
    assert expand_word(word, state) == "literal"


def test_escaped_dollar_is_literal() -> None:
    state = ShellState()
    state.variables["NAME"] = "Ada"
    words = _words(r'echo \$NAME "\$NAME"')
    assert expand_words(words, state) == ["echo", "$NAME", "$NAME"]


def test_tilde_expansion() -> None:
    state = ShellState()
    state.exported_env["HOME"] = "/home/student"
    word = _words("echo ~/project")[1]
    assert expand_word(word, state) == "/home/student/project"


def test_double_quotes_preserve_literal_backslash() -> None:
    state = ShellState()
    state.variables["NAME"] = "Ada"
    word = _words(r'echo "a\b $NAME"')[1]
    assert expand_word(word, state) == r"a\b Ada"


def test_unclosed_braced_expansion_raises() -> None:
    from pyshell_lab.errors import ExpansionError

    state = ShellState()
    word = _words("echo ${UNCLOSED")[1]
    with pytest.raises(ExpansionError, match="unclosed"):
        expand_word(word, state)


def test_bare_tilde_expands_to_home() -> None:
    state = ShellState()
    state.variables["HOME"] = "/home/me"
    word = _words("cd ~")[1]
    assert expand_word(word, state) == "/home/me"


def test_trailing_dollar_is_literal() -> None:
    state = ShellState()
    word = _words("echo foo$")[1]
    assert expand_word(word, state) == "foo$"


def test_invalid_dollar_name_is_literal() -> None:
    state = ShellState()
    word = _words("echo $1bad")[1]
    assert expand_word(word, state) == "$1bad"


def test_variables_overlay_takes_precedence() -> None:
    state = ShellState()
    state.variables["X"] = "shell"
    word = _words("echo $X")[1]
    assert expand_word(word, state, variables_overlay={"X": "overlay"}) == "overlay"


def test_lookup_uses_exported_env_when_not_in_variables() -> None:
    state = ShellState()
    state.exported_env["ONLY_ENV"] = "from-env"
    word = _words("echo $ONLY_ENV")[1]
    assert expand_word(word, state) == "from-env"


def test_tilde_without_home_uses_expanduser(monkeypatch) -> None:
    state = ShellState()
    state.variables.pop("HOME", None)
    state.exported_env.pop("HOME", None)
    monkeypatch.setattr("pyshell_lab.expansion.os.path.expanduser", lambda _: "/fallback")
    word = _words("echo ~")[1]
    assert expand_word(word, state) == "/fallback"


def test_expand_words_returns_list() -> None:
    state = ShellState()
    words = _words("echo a b")
    assert expand_words(words, state) == ["echo", "a", "b"]
