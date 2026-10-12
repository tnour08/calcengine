"""Pure-computation layer: no UI imports live below this package.

Pipeline::

    source text
        -> lexer.tokenize   -> [Token]
        -> parser.parse     -> Node (AST)
        -> evaluator        -> Decimal
        -> formatter        -> str

:class:`~calcengine.core.engine.Engine` wires those stages together.
"""

from .context import AngleMode, EvalContext
from .engine import Engine, EvalResult
from .errors import (
    ArityError,
    CalcError,
    DomainError,
    EvalError,
    LexError,
    ParseError,
    UnknownSymbolError,
)
from .formatter import Formatter, NotationMode
from .functions import REGISTRY

__all__ = [
    "REGISTRY",
    "AngleMode",
    "ArityError",
    "CalcError",
    "DomainError",
    "Engine",
    "EvalContext",
    "EvalError",
    "EvalResult",
    "Formatter",
    "LexError",
    "NotationMode",
    "ParseError",
    "UnknownSymbolError",
]
