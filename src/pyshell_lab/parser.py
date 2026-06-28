"""Recursive-descent parser that builds explicit command objects."""

from __future__ import annotations

from typing import cast

from .ast import (
    BackgroundCommand,
    CommandNode,
    CommandSequence,
    CommandWord,
    Connector,
    Pipeline,
    Redirection,
    RedirectOp,
    SequenceItem,
    SimpleCommand,
    Token,
)
from .errors import ParserError
from .lexer import lex

REDIRECT_OPERATORS = {">", ">>", "<", "2>", ">&", "2>&"}
CONNECTORS = {";", "&&", "||"}


def parse_line(line: str) -> CommandNode | None:
    tokens = lex(line)
    if not tokens:
        return None
    return Parser(tokens).parse()


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def parse(self) -> CommandNode:
        sequence = self._parse_sequence()
        token = self._peek()
        if token is not None:
            raise ParserError(f"unexpected operator {token.value!r}")
        if len(sequence.items) == 1 and sequence.items[0].connector is None:
            return sequence.items[0].command
        return sequence

    def _parse_sequence(self) -> CommandSequence:
        items: list[SequenceItem] = []
        connector: Connector | None = None

        while (token := self._peek()) is not None:
            if token.kind == "OP" and token.value in CONNECTORS:
                raise ParserError("empty command in sequence")

            command = self._parse_pipeline()

            if self._accept("&"):
                command = BackgroundCommand(command)
                items.append(SequenceItem(command, connector))
                connector = ";"
                if self._peek() is None:
                    break
                if self._accept(";"):
                    connector = ";"
                    if self._peek() is None:
                        raise ParserError("empty command in sequence")
                    continue
                if self._peek_is("&&") or self._peek_is("||"):
                    raise ParserError("unexpected operator after background command")
                continue

            items.append(SequenceItem(command, connector))
            connector = None

            token = self._peek()
            if token is None:
                break
            if token.kind == "OP" and token.value in CONNECTORS:
                connector = cast(Connector, token.value)
                self.index += 1
                if self._peek() is None:
                    raise ParserError("empty command in sequence")
                continue
            if token.kind == "OP":
                raise ParserError(f"unexpected operator {token.value!r}")
            raise ParserError("missing command separator")

        return CommandSequence(tuple(items))

    def _parse_pipeline(self) -> CommandNode:
        commands = [self._parse_simple_command()]
        while self._accept("|"):
            token = self._peek()
            if token is None or (token.kind == "OP" and token.value not in REDIRECT_OPERATORS):
                raise ParserError("missing command after |")
            commands.append(self._parse_simple_command())

        if len(commands) == 1:
            return commands[0]
        return Pipeline(tuple(commands))

    def _parse_simple_command(self) -> SimpleCommand:
        words: list[CommandWord] = []
        redirections: list[Redirection] = []

        while (token := self._peek()) is not None:
            if token.kind == "WORD":
                words.append(CommandWord.from_token(token))
                self.index += 1
                continue
            if token.kind == "OP" and token.value in REDIRECT_OPERATORS:
                operator = token.value
                self.index += 1
                target = self._peek()
                if target is None or target.kind != "WORD":
                    raise ParserError(f"missing filename after {operator}")
                redirections.append(
                    Redirection(cast(RedirectOp, operator), CommandWord.from_token(target))
                )
                self.index += 1
                continue
            break

        if not words:
            token = self._peek()
            if redirections:
                raise ParserError("redirection without command")
            if token is None:
                raise ParserError("empty command")
            if token.value == "|":
                raise ParserError("missing command before |")
            raise ParserError(f"unexpected operator {token.value!r}")

        return SimpleCommand(tuple(words), tuple(redirections))

    def _peek(self) -> Token | None:
        if self.index >= len(self.tokens):
            return None
        return self.tokens[self.index]

    def _peek_is(self, value: str) -> bool:
        token = self._peek()
        return token is not None and token.kind == "OP" and token.value == value

    def _accept(self, value: str) -> bool:
        if self._peek_is(value):
            self.index += 1
            return True
        return False
