"""Test AST."""

from __future__ import annotations

from pyshell_lab.ast import (
    ESCAPE_MARKER,
    BackgroundCommand,
    CommandSequence,
    CommandWord,
    Pipeline,
    SequenceItem,
    SimpleCommand,
    Token,
    WordPart,
    strip_escape_markers,
)
from pyshell_lab.lexer import lex


def test_strip_escape_markers() -> None:
    assert strip_escape_markers(f"a{ESCAPE_MARKER}b") == "ab"
    assert strip_escape_markers("plain") == "plain"


def test_command_word_text_and_from_token() -> None:
    token = lex(r"hel\ lo")[0]
    word = CommandWord.from_token(token)
    assert word.text == "hel lo"


def test_word_part_rendered() -> None:
    part = WordPart(f"hel{ESCAPE_MARKER}lo", "none")
    assert part.rendered() == "hello"


def test_simple_command_display() -> None:
    node = SimpleCommand((CommandWord((WordPart("echo"),)), CommandWord((WordPart("hi"),))))
    assert node.display == "echo hi"


def test_pipeline_display() -> None:
    left = SimpleCommand((CommandWord((WordPart("echo"),)),))
    right = SimpleCommand((CommandWord((WordPart("wc"),)),))
    assert Pipeline((left, right)).display == "echo | wc"


def test_token_defaults() -> None:
    token = Token("WORD", "x", 0)
    assert token.parts == ()


def test_background_and_sequence_dataclasses() -> None:
    inner = SimpleCommand((CommandWord((WordPart("sleep"),)),))
    bg = BackgroundCommand(inner)
    seq = CommandSequence((SequenceItem(bg),))
    assert seq.items[0].command is bg
