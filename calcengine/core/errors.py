"""Exception hierarchy for the calculator engine.

Every failure carries enough positional information for the UI to underline
the offending span of the source expression.
"""

from __future__ import annotations


class CalcError(Exception):
    """Base class for every error raised by the engine."""

    #: Short machine-readable tag, surfaced in the UI status bar.
    code = "error"

    def __init__(self, message: str, position: int | None = None, length: int = 1):
        super().__init__(message)
        self.message = message
        self.position = position
        self.length = max(1, length)

    def caret_line(self, source: str) -> str:
        """Return a ``^^^`` underline string aligned to ``source``."""
        if self.position is None:
            return ""
        pad = " " * min(self.position, len(source))
        return pad + "^" * self.length

    def __str__(self) -> str:
        if self.position is None:
            return self.message
        return f"{self.message} (at column {self.position + 1})"


class LexError(CalcError):
    """Raised when the source contains a character we cannot tokenize."""

    code = "lex"


class ParseError(CalcError):
    """Raised when the token stream does not form a valid expression."""

    code = "parse"


class EvalError(CalcError):
    """Raised when a well-formed expression cannot be evaluated."""

    code = "eval"


class UnknownSymbolError(EvalError):
    """Raised for an unbound identifier."""

    code = "name"

    def __init__(self, name: str, position: int | None = None, suggestion: str | None = None):
        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
        super().__init__(f"Unknown name '{name}'.{hint}", position, len(name))
        self.name = name
        self.suggestion = suggestion


class ArityError(EvalError):
    """Raised when a function is called with the wrong number of arguments."""

    code = "arity"


class DomainError(EvalError):
    """Raised when an argument falls outside a function's domain."""

    code = "domain"


class PrecisionError(CalcError):
    """Raised when a computation cannot converge at the configured precision."""

    code = "precision"
