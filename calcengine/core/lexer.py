"""Hand-written lexer turning source text into a :class:`Token` stream.

Accepts a deliberately forgiving surface syntax so the on-screen keypad can
emit pretty glyphs while the keyboard emits ASCII:

    2\u00d7(1+\u221a9)\u00b2    ->  2 * (1 + sqrt(9)) ** 2
    1_000e-3     ->  1.0
    \u03c0/2          ->  pi / 2
    5!\u00f72         ->  factorial(5) / 2
"""

from __future__ import annotations

from .errors import LexError
from .tokens import (
    KEYWORD_OPERATORS,
    SIMPLE_TOKENS,
    SYMBOL_ALIASES,
    Token,
    TokenType,
)


#: Only ASCII digits start a number. ``str.isdigit`` is true for superscripts
#: such as "\u00b2", which are postfix operators here, not numerals.
ASCII_DIGITS = frozenset("0123456789")


def _is_digit(char: str) -> bool:
    return char in ASCII_DIGITS


def _is_name_start(char: str) -> bool:
    return char == "_" or (char.isascii() and char.isalpha())


def _is_name_part(char: str) -> bool:
    return char == "_" or (char.isascii() and char.isalnum())


class Lexer:
    """Converts a source string into tokens, one pass, no backtracking."""

    def __init__(self, source: str):
        self.source = source
        self.index = 0
        self.tokens: list[Token] = []

    # -- character helpers -------------------------------------------------- #

    def _peek(self, offset: int = 0) -> str:
        position = self.index + offset
        return self.source[position] if position < len(self.source) else ""

    def _at_end(self) -> bool:
        return self.index >= len(self.source)

    # -- main loop ---------------------------------------------------------- #

    def tokenize(self) -> list[Token]:
        while not self._at_end():
            char = self._peek()

            if char.isspace():
                self.index += 1
                continue

            if _is_digit(char) or (char == "." and _is_digit(self._peek(1))):
                self._read_number()
                continue

            if _is_name_start(char):
                self._read_identifier()
                continue

            if char in SYMBOL_ALIASES:
                self.tokens.append(
                    Token(TokenType.IDENT, SYMBOL_ALIASES[char], self.index)
                )
                self.index += 1
                continue

            # "**" is an alias for "^"; check before the single-char table.
            if char == "*" and self._peek(1) == "*":
                self.tokens.append(Token(TokenType.CARET, "**", self.index))
                self.index += 2
                continue

            if char in SIMPLE_TOKENS:
                self.tokens.append(Token(SIMPLE_TOKENS[char], char, self.index))
                self.index += 1
                continue

            raise LexError(f"Unexpected character {char!r}.", self.index)

        self.tokens.append(Token(TokenType.EOF, "", len(self.source)))
        return self.tokens

    # -- scanners ----------------------------------------------------------- #

    def _read_number(self) -> None:
        start = self.index
        seen_dot = False
        seen_exponent = False

        while not self._at_end():
            char = self._peek()
            if _is_digit(char):
                self.index += 1
            elif char == "_":
                # Digit grouping: 1_000_000. Stripped before Decimal parsing.
                self.index += 1
            elif char == "." and not seen_dot and not seen_exponent:
                seen_dot = True
                self.index += 1
            elif char in "eE" and not seen_exponent and self._exponent_follows():
                seen_exponent = True
                self.index += 1
                if self._peek() in "+-":
                    self.index += 1
            else:
                break

        raw = self.source[start:self.index]
        cleaned = raw.replace("_", "")
        if cleaned.endswith((".", "e", "E", "+", "-")):
            raise LexError(f"Malformed number {raw!r}.", start, len(raw))
        self.tokens.append(Token(TokenType.NUMBER, cleaned, start))

    def _exponent_follows(self) -> bool:
        """True when ``e``/``E`` at the cursor really introduces an exponent.

        Guards against swallowing the constant ``e`` in expressions like
        ``2e`` (two times Euler's number) while still accepting ``2e5``.
        """
        after = self._peek(1)
        if _is_digit(after):
            return True
        return after in "+-" and _is_digit(self._peek(2))

    def _read_identifier(self) -> None:
        start = self.index
        while not self._at_end() and _is_name_part(self._peek()):
            self.index += 1
        text = self.source[start:self.index]
        lowered = text.lower()

        if lowered in KEYWORD_OPERATORS:
            self.tokens.append(Token(KEYWORD_OPERATORS[lowered], lowered, start))
        else:
            self.tokens.append(Token(TokenType.IDENT, lowered, start))


def tokenize(source: str) -> list[Token]:
    """Convenience wrapper around :class:`Lexer`."""
    return Lexer(source).tokenize()
