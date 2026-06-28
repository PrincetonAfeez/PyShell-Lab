"""Quote-aware lexer for the PyShell command language."""

from __future__ import annotations

from .ast import ESCAPE_MARKER, Token, WordPart, strip_escape_markers
from .errors import LexerError

# Longer / more specific operators must precede their prefixes (e.g. "2>&"
# before "2>", ">&" and ">>" before ">").
OPERATORS = ("&&", "||", "2>&", ">>", ">&", "2>", "|", ">", "<", "&", ";")

# Inside double quotes POSIX keeps a backslash literal unless it precedes one of
# these characters. Outside quotes a backslash escapes any single character.
_DOUBLE_QUOTE_ESCAPABLES = ('"', "\\", "$", "`", "\n")


def lex(line: str) -> list[Token]:
    """Turn a command line into word and operator tokens."""

    tokens: list[Token] = []
    i = 0
    while i < len(line):
        if line[i].isspace():
            i += 1
            continue

        # A '#' that begins a word starts a comment that runs to end of line.
        # '#' in the middle of a word (echo a#b) stays part of that word.
        if line[i] == "#":
            break

        operator = _match_operator(line, i)
        if operator is not None:
            tokens.append(Token("OP", operator, i))
            i += len(operator)
            continue

        token, i = _read_word(line, i)
        tokens.append(token)

    return tokens


def _match_operator(line: str, index: int) -> str | None:
    for operator in OPERATORS:
        if line.startswith(operator, index):
            return operator
    return None


def _read_word(line: str, index: int) -> tuple[Token, int]:
    parts: list[WordPart] = []
    start = index
    current: list[str] = []
    i = index

    def flush_unquoted() -> None:
        if current:
            parts.append(WordPart("".join(current), "none"))
            current.clear()

    while i < len(line):
        char = line[i]
        if char.isspace():
            break
        operator = _match_operator(line, i)
        # A digit-led operator (only "2>") must not split a word like "foo2>bar":
        # the digit belongs to the word, and the following ">" ends it. "2>" at a
        # token boundary is still recognized by the main lex loop.
        if operator is not None and not operator[0].isdigit():
            break
        if char == "'":
            flush_unquoted()
            text, i = _read_single_quoted(line, i + 1, start)
            parts.append(WordPart(text, "single"))
            continue
        if char == '"':
            flush_unquoted()
            text, i = _read_double_quoted(line, i + 1, start)
            parts.append(WordPart(text, "double"))
            continue
        if char == "\\":
            if i + 1 >= len(line):
                raise LexerError("dangling escape")
            current.append(ESCAPE_MARKER + line[i + 1])
            i += 2
            continue
        current.append(char)
        i += 1

    flush_unquoted()
    value = "".join(strip_escape_markers(part.text) for part in parts)
    return Token("WORD", value, start, tuple(parts)), i


def _read_single_quoted(line: str, index: int, start: int) -> tuple[str, int]:
    current: list[str] = []
    i = index
    while i < len(line):
        if line[i] == "'":
            return "".join(current), i + 1
        current.append(line[i])
        i += 1
    raise LexerError(f"unclosed single quote at position {start}")


def _read_double_quoted(line: str, index: int, start: int) -> tuple[str, int]:
    current: list[str] = []
    i = index
    while i < len(line):
        char = line[i]
        if char == '"':
            return "".join(current), i + 1
        if char == "\\":
            if i + 1 >= len(line):
                raise LexerError("dangling escape")
            nxt = line[i + 1]
            if nxt in _DOUBLE_QUOTE_ESCAPABLES:
                current.append(ESCAPE_MARKER + nxt)
                i += 2
            else:
                # POSIX: backslash is literal before any other character.
                current.append(char)
                i += 1
            continue
        current.append(char)
        i += 1
    raise LexerError(f"unclosed double quote at position {start}")
