"""Domain-specific exceptions for predictable shell errors."""

from __future__ import annotations


class ShellError(Exception):
    """Base class for expected shell errors."""


class LexerError(ShellError):
    """Raised when command text cannot be tokenized."""


class ParserError(ShellError):
    """Raised when tokens do not form a valid command structure."""


class ExpansionError(ShellError):
    """Raised when word expansion fails."""


class ExecutionError(ShellError):
    """Raised for expected execution errors."""


class ShellExit(Exception):
    """Control-flow exception used by the exit builtin."""

    def __init__(self, status: int = 0) -> None:
        super().__init__(status)
        self.status = status
