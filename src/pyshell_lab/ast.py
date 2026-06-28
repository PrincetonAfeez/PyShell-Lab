"""Structured command data used between parsing and execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

QuoteKind = Literal["none", "single", "double"]
Connector = Literal[";", "&&", "||"]
RedirectOp = Literal[">", ">>", "<", "2>", ">&", "2>&"]

# A small internal marker used by the lexer to remember that a character was
# escaped before expansion runs. It is stripped before execution.
ESCAPE_MARKER = "\x1f"


def strip_escape_markers(text: str) -> str:
    rendered: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == ESCAPE_MARKER and i + 1 < len(text):
            rendered.append(text[i + 1])
            i += 2
        else:
            rendered.append(text[i])
            i += 1
    return "".join(rendered)


@dataclass(frozen=True)
class WordPart:
    text: str
    quote: QuoteKind = "none"

    def rendered(self) -> str:
        return strip_escape_markers(self.text)


@dataclass(frozen=True)
class Token:
    kind: Literal["WORD", "OP"]
    value: str
    position: int
    parts: tuple[WordPart, ...] = ()


@dataclass(frozen=True)
class CommandWord:
    parts: tuple[WordPart, ...]

    @property
    def text(self) -> str:
        return "".join(part.rendered() for part in self.parts)

    @classmethod
    def from_token(cls, token: Token) -> CommandWord:
        return cls(token.parts)


@dataclass(frozen=True)
class Redirection:
    operator: RedirectOp
    target: CommandWord


@dataclass(frozen=True)
class SimpleCommand:
    words: tuple[CommandWord, ...]
    redirections: tuple[Redirection, ...] = ()

    @property
    def display(self) -> str:
        return " ".join(word.text for word in self.words)


@dataclass(frozen=True)
class Pipeline:
    commands: tuple[SimpleCommand, ...]

    @property
    def display(self) -> str:
        return " | ".join(command.display for command in self.commands)


@dataclass(frozen=True)
class BackgroundCommand:
    command: CommandNode


@dataclass(frozen=True)
class SequenceItem:
    command: CommandNode
    connector: Connector | None = None


@dataclass(frozen=True)
class CommandSequence:
    items: tuple[SequenceItem, ...] = field(default_factory=tuple)


CommandNode = SimpleCommand | Pipeline | BackgroundCommand | CommandSequence
