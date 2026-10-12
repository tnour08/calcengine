"""A Pratt (precedence-climbing) parser for the calculator grammar.

Supported forms, loosest binding first::

    name = expr                 assignment
    a + b, a - b                additive
    a * b, a / b, a mod b       multiplicative
    -a, +a, \u221aa                 prefix
    a ^ b                       power (right associative)
    a!, a%, a\u00b2, a\u00b3              postfix
    f(x, y), (expr)             calls and grouping
    2\u03c0, 3(4+5), 2sin(1)         implicit multiplication

Precedence is expressed as plain integers; left-associative operators recurse
at their own level while right-associative ones recurse one level lower.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .errors import ParseError
from .nodes import (
    Assign,
    Binary,
    Call,
    Identifier,
    Node,
    NumberLit,
    Postfix,
    Unary,
)
from .tokens import OPERAND_STARTERS, POSTFIX_TOKENS, Token, TokenType

PREC_LOWEST = 0
PREC_ADDITIVE = 10
PREC_MULTIPLICATIVE = 20
PREC_PREFIX = 30
PREC_POWER = 40
PREC_POSTFIX = 50

#: Infix operators -> (binding power, is_right_associative, display symbol)
INFIX_OPERATORS: dict[TokenType, tuple[int, bool, str]] = {
    TokenType.PLUS: (PREC_ADDITIVE, False, "+"),
    TokenType.MINUS: (PREC_ADDITIVE, False, "-"),
    TokenType.STAR: (PREC_MULTIPLICATIVE, False, "*"),
    TokenType.SLASH: (PREC_MULTIPLICATIVE, False, "/"),
    TokenType.MOD: (PREC_MULTIPLICATIVE, False, "mod"),
    TokenType.CARET: (PREC_POWER, True, "^"),
}

#: Cap on parser recursion. Grouping parentheses produce no AST node, so the
#: evaluator's depth check cannot see them; without this, "((((...1...))))"
#: would exhaust the interpreter stack instead of reporting a clean error.
MAX_NESTING = 100

#: Postfix operators -> display symbol.
POSTFIX_OPERATORS: dict[TokenType, str] = {
    TokenType.BANG: "!",
    TokenType.PERCENT: "%",
    TokenType.SQUARE: "\u00b2",
    TokenType.CUBE: "\u00b3",
}


class Parser:
    """Builds an AST from a token list produced by the lexer."""

    def __init__(self, tokens: list[Token], source: str = ""):
        self.tokens = tokens
        self.source = source
        self.index = 0
        self.depth = 0

    # -- token helpers ------------------------------------------------------ #

    @property
    def current(self) -> Token:
        return self.tokens[self.index]

    def _peek(self, offset: int = 1) -> Token:
        position = min(self.index + offset, len(self.tokens) - 1)
        return self.tokens[position]

    def _advance(self) -> Token:
        token = self.current
        if token.type is not TokenType.EOF:
            self.index += 1
        return token

    def _expect(self, token_type: TokenType, description: str) -> Token:
        if self.current.type is not token_type:
            raise ParseError(
                f"Expected {description} but found "
                f"{self._describe(self.current)}.",
                self.current.position,
                self.current.length,
            )
        return self._advance()

    @staticmethod
    def _describe(token: Token) -> str:
        if token.type is TokenType.EOF:
            return "end of expression"
        return repr(token.text)

    # -- entry point -------------------------------------------------------- #

    def parse(self) -> Node:
        if self.current.type is TokenType.EOF:
            raise ParseError("Nothing to evaluate.", 0)
        node = self._parse_assignment()
        if self.current.type is not TokenType.EOF:
            raise ParseError(
                f"Unexpected {self._describe(self.current)}.",
                self.current.position,
                self.current.length,
            )
        return node

    def _parse_assignment(self) -> Node:
        is_assignment = (
            self.current.type is TokenType.IDENT
            and self._peek().type is TokenType.ASSIGN
        )
        if not is_assignment:
            return self._parse_expression(PREC_LOWEST)

        name_token = self._advance()
        self._advance()  # consume '='
        if self.current.type is TokenType.EOF:
            raise ParseError(
                f"Assignment to '{name_token.text}' is missing a value.",
                self.current.position,
            )
        value = self._parse_assignment()  # right associative: a = b = 3
        return Assign(name=name_token.text, value=value, position=name_token.position)

    # -- precedence climbing ------------------------------------------------ #

    def _parse_expression(self, min_precedence: int) -> Node:
        self.depth += 1
        if self.depth > MAX_NESTING:
            raise ParseError(
                "Expression is nested too deeply.", self.current.position
            )
        try:
            return self._parse_expression_inner(min_precedence)
        finally:
            self.depth -= 1

    def _parse_expression_inner(self, min_precedence: int) -> Node:
        left = self._parse_prefix()

        while True:
            token = self.current

            if token.type in POSTFIX_OPERATORS and PREC_POSTFIX > min_precedence:
                self._advance()
                left = Postfix(
                    op=POSTFIX_OPERATORS[token.type],
                    operand=left,
                    position=token.position,
                )
                continue

            infix = INFIX_OPERATORS.get(token.type)
            if infix is not None:
                precedence, right_associative, symbol = infix
                if precedence <= min_precedence:
                    break
                self._advance()
                next_minimum = (
                    precedence - 1 if right_associative else precedence
                )
                right = self._parse_expression(next_minimum)
                left = Binary(
                    op=symbol, left=left, right=right, position=token.position
                )
                continue

            # Implicit multiplication: "2pi", "3(4)", "(1+2)(3+4)".
            if (
                token.type in OPERAND_STARTERS
                and PREC_MULTIPLICATIVE > min_precedence
            ):
                right = self._parse_expression(PREC_MULTIPLICATIVE)
                left = Binary(
                    op="*",
                    left=left,
                    right=right,
                    implicit=True,
                    position=token.position,
                )
                continue

            break

        return left

    def _parse_prefix(self) -> Node:
        token = self.current

        if token.type is TokenType.NUMBER:
            self._advance()
            try:
                value = Decimal(token.text)
            except InvalidOperation as exc:
                raise ParseError(
                    f"Cannot read {token.text!r} as a number.",
                    token.position,
                    token.length,
                ) from exc
            return NumberLit(value=value, raw=token.text, position=token.position)

        if token.type is TokenType.IDENT:
            self._advance()
            if self.current.type is TokenType.LPAREN:
                return self._parse_call(token)
            return Identifier(name=token.text, position=token.position)

        if token.type in (TokenType.MINUS, TokenType.PLUS):
            self._advance()
            operand = self._parse_expression(PREC_PREFIX)
            if token.type is TokenType.PLUS:
                return operand
            return Unary(op="-", operand=operand, position=token.position)

        if token.type is TokenType.RADICAL:
            self._advance()
            operand = self._parse_expression(PREC_PREFIX)
            return Call(name="sqrt", args=(operand,), position=token.position)

        if token.type is TokenType.LPAREN:
            self._advance()
            inner = self._parse_expression(PREC_LOWEST)
            self._expect(TokenType.RPAREN, "a closing parenthesis")
            return inner

        if token.type is TokenType.EOF:
            raise ParseError("Expression ended unexpectedly.", token.position)

        raise ParseError(
            f"Unexpected {self._describe(token)}.", token.position, token.length
        )

    def _parse_call(self, name_token: Token) -> Node:
        self._expect(TokenType.LPAREN, "an opening parenthesis")
        args: list[Node] = []

        if self.current.type is not TokenType.RPAREN:
            while True:
                args.append(self._parse_expression(PREC_LOWEST))
                if self.current.type is TokenType.COMMA:
                    self._advance()
                    continue
                break

        self._expect(TokenType.RPAREN, "a closing parenthesis")
        return Call(
            name=name_token.text, args=tuple(args), position=name_token.position
        )


def parse(tokens: list[Token], source: str = "") -> Node:
    """Convenience wrapper around :class:`Parser`."""
    return Parser(tokens, source).parse()
