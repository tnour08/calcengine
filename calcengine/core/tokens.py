"""Token vocabulary shared by the lexer and the parser."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    NUMBER = auto()
    IDENT = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    CARET = auto()
    MOD = auto()

    BANG = auto()        # postfix factorial
    PERCENT = auto()     # postfix "divide by one hundred"
    SQUARE = auto()      # postfix superscript two
    CUBE = auto()        # postfix superscript three
    RADICAL = auto()     # prefix square-root sign

    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    ASSIGN = auto()
    EOF = auto()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return self.name


@dataclass(frozen=True)
class Token:
    """A lexeme plus the slice of source it came from."""

    type: TokenType
    text: str
    position: int

    @property
    def length(self) -> int:
        return max(1, len(self.text))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"{self.type.name}({self.text!r}@{self.position})"


#: Single characters that map directly onto a token type.
SIMPLE_TOKENS: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "\u2212": TokenType.MINUS,   # unicode minus sign
    "*": TokenType.STAR,
    "\u00d7": TokenType.STAR,    # multiplication sign
    "\u22c5": TokenType.STAR,    # dot operator
    "/": TokenType.SLASH,
    "\u00f7": TokenType.SLASH,   # division sign
    "^": TokenType.CARET,
    "!": TokenType.BANG,
    "%": TokenType.PERCENT,
    "\u00b2": TokenType.SQUARE,  # superscript two
    "\u00b3": TokenType.CUBE,    # superscript three
    "\u221a": TokenType.RADICAL,  # square root sign
    "(": TokenType.LPAREN,
    "[": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "]": TokenType.RPAREN,
    ",": TokenType.COMMA,
    "=": TokenType.ASSIGN,
}

#: Identifiers that are really operators in disguise.
KEYWORD_OPERATORS: dict[str, TokenType] = {
    "mod": TokenType.MOD,
}

#: Pretty single-character aliases expanded into named constants.
SYMBOL_ALIASES: dict[str, str] = {
    "\u03c0": "pi",     # greek small letter pi
    "\u03c4": "tau",    # greek small letter tau
    "\u03c6": "phi",    # greek small letter phi
    "\u2205": "ans",    # empty set, used as "last answer"
}

#: Token types that may begin an operand, enabling implicit multiplication.
OPERAND_STARTERS = frozenset(
    {TokenType.NUMBER, TokenType.IDENT, TokenType.LPAREN, TokenType.RADICAL}
)

#: Postfix operators, handled in the parser's infix loop.
POSTFIX_TOKENS = frozenset(
    {TokenType.BANG, TokenType.PERCENT, TokenType.SQUARE, TokenType.CUBE}
)
