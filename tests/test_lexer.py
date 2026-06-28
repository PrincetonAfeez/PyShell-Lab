"""Test lexer."""

from __future__ import annotations

import pytest

from pyshell_lab.errors import LexerError
from pyshell_lab.lexer import lex


def values(line: str) -> list[str]:
    return [token.value for token in lex(line)]


def test_whitespace_and_words() -> None:
    assert values("  ls   -la /tmp ") == ["ls", "-la", "/tmp"]


def test_core_operators() -> None:
    assert values("cat < in | grep x >> out 2> err && echo ok || false; jobs &") == [
        "cat",
        "<",
        "in",
        "|",
        "grep",
        "x",
        ">>",
        "out",
        "2>",
        "err",
        "&&",
        "echo",
        "ok",
        "||",
        "false",
        ";",
        "jobs",
        "&",
    ]


def test_single_and_double_quotes_preserve_word() -> None:
    tokens = lex("echo 'literal $HOME' \"hello $USER\"")
    assert [token.value for token in tokens] == ["echo", "literal $HOME", "hello $USER"]
    assert tokens[1].parts[0].quote == "single"
    assert tokens[2].parts[0].quote == "double"


def test_backslash_escape_keeps_space_in_word() -> None:
    assert values(r"echo hello\ world") == ["echo", "hello world"]


def test_double_quote_backslash_follows_posix() -> None:
    # Inside double quotes a backslash is literal unless it precedes $ ` " or \.
    assert values(r'echo "a\b"') == ["echo", r"a\b"]
    assert values(r'echo "a\\b"') == ["echo", r"a\b"]
    assert values(r'echo "a\$b"') == ["echo", "a$b"]
    assert values(r'echo "a\"b"') == ["echo", 'a"b']


def test_comments_start_at_a_word_boundary() -> None:
    assert values("echo hi # trailing comment") == ["echo", "hi"]
    assert values("# whole line") == []
    assert values("echo a#b") == ["echo", "a#b"]


def test_2redirect_does_not_split_a_digit_ending_word() -> None:
    # "foo2>bar" is the word "foo2" then ">", not "foo" then "2>".
    assert values("echo foo2>bar") == ["echo", "foo2", ">", "bar"]
    # At a token boundary, 2> is still recognized.
    assert values("echo 2>bar") == ["echo", "2>", "bar"]
    assert values("ls 2> err") == ["ls", "2>", "err"]


def test_fd_duplication_operators() -> None:
    assert values("echo hi 2>&1") == ["echo", "hi", "2>&", "1"]
    assert values("echo hi >&2") == ["echo", "hi", ">&", "2"]
    assert values("cmd > f 2>&1") == ["cmd", ">", "f", "2>&", "1"]
    assert values("cmd 2>&-") == ["cmd", "2>&", "-"]


def test_lexer_errors_are_clear() -> None:
    with pytest.raises(LexerError, match="unclosed single quote"):
        lex("echo 'oops")
    with pytest.raises(LexerError, match="unclosed double quote"):
        lex('echo "oops')
    with pytest.raises(LexerError, match="dangling escape"):
        lex("echo hello\\")


def test_double_quote_dangling_backslash() -> None:
    with pytest.raises(LexerError, match="dangling escape"):
        lex('echo "oops\\')


def test_double_quote_backslash_before_non_special_is_literal() -> None:
    assert values(r'echo "a\z"') == ["echo", r"a\z"]
