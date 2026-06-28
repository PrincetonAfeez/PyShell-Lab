"""Test parser."""

from __future__ import annotations

import pytest

from pyshell_lab.ast import BackgroundCommand, CommandSequence, Pipeline, SimpleCommand
from pyshell_lab.errors import ParserError
from pyshell_lab.parser import parse_line


def test_parse_simple_command() -> None:
    node = parse_line("ls -la /tmp")
    assert isinstance(node, SimpleCommand)
    assert [word.text for word in node.words] == ["ls", "-la", "/tmp"]


def test_parse_redirection() -> None:
    node = parse_line("echo hello > out.txt 2> err.txt")
    assert isinstance(node, SimpleCommand)
    assert [redir.operator for redir in node.redirections] == [">", "2>"]
    assert [redir.target.text for redir in node.redirections] == ["out.txt", "err.txt"]


def test_parse_fd_duplication() -> None:
    node = parse_line("cmd > out.txt 2>&1")
    assert isinstance(node, SimpleCommand)
    assert [r.operator for r in node.redirections] == [">", "2>&"]
    assert [r.target.text for r in node.redirections] == ["out.txt", "1"]


def test_parse_pipeline() -> None:
    node = parse_line("cat file.txt | grep error | wc -l")
    assert isinstance(node, Pipeline)
    assert len(node.commands) == 3
    assert node.commands[1].words[0].text == "grep"


def test_parse_background_command() -> None:
    node = parse_line("sleep 10 &")
    assert isinstance(node, BackgroundCommand)


def test_background_binds_to_preceding_pipeline_only() -> None:
    node = parse_line("echo a; echo b &")
    assert isinstance(node, CommandSequence)
    assert not isinstance(node.items[0].command, BackgroundCommand)
    assert isinstance(node.items[1].command, BackgroundCommand)
    assert node.items[1].connector == ";"


def test_parse_sequence_and_conditionals() -> None:
    node = parse_line("false || echo recovered; true && echo ok")
    assert isinstance(node, CommandSequence)
    assert [item.connector for item in node.items] == [None, "||", ";", "&&"]


def test_parser_errors() -> None:
    with pytest.raises(ParserError, match=r"missing command after \|"):
        parse_line("echo hi |")
    with pytest.raises(ParserError, match="missing filename after >"):
        parse_line("echo hi >")
    with pytest.raises(ParserError, match="empty command in sequence"):
        parse_line("echo hi ; ; echo bye")
    with pytest.raises(ParserError, match="unexpected operator"):
        parse_line("& echo hi")


def test_parse_empty_line_returns_none() -> None:
    assert parse_line("") is None
    assert parse_line("   ") is None
    assert parse_line("# comment only") is None


def test_parse_append_and_input_redirect() -> None:
    node = parse_line("cat >> log.txt < in.txt")
    assert isinstance(node, SimpleCommand)
    assert [r.operator for r in node.redirections] == [">>", "<"]


def test_parse_redirection_without_command() -> None:
    with pytest.raises(ParserError, match="redirection without command"):
        parse_line("> out.txt")


def test_parse_missing_command_before_pipe() -> None:
    with pytest.raises(ParserError, match="missing command before"):
        parse_line("| echo hi")


def test_parse_trailing_unexpected_operator() -> None:
    with pytest.raises(ParserError, match="empty command in sequence"):
        parse_line("echo hi &&")


def test_parse_background_then_semicolon_continues() -> None:
    node = parse_line("sleep 1 & ; echo hi")
    assert isinstance(node, CommandSequence)
    assert isinstance(node.items[0].command, BackgroundCommand)
    assert node.items[1].connector == ";"


def test_parse_unexpected_operator_after_background() -> None:
    with pytest.raises(ParserError, match="unexpected operator after background"):
        parse_line("echo hi & && echo nope")


def test_quoted_assignment_is_not_prefix_assignment() -> None:
    node = parse_line(r'"FOO"=bar echo hi')
    assert isinstance(node, SimpleCommand)
    assert node.words[0].text == "FOO=bar"
    assert node.words[1].text == "echo"
    assert node.words[2].text == "hi"
