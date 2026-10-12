"""The engine facade: one call takes a string and returns a rich result.

This is the only module the rest of the application needs to know about; the
lexer, parser and evaluator stay private behind it.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal

from .context import AngleMode, EvalContext
from .errors import CalcError
from .evaluator import Evaluator, TraceEntry
from .formatter import Formatter, NotationMode
from .functions import REGISTRY, Registry
from .lexer import tokenize
from .nodes import Node, render_tree, unparse
from .parser import parse
from .tokens import Token


@dataclass
class EvalResult:
    """Everything produced by one successful evaluation."""

    source: str
    value: Decimal
    formatted: str
    tree: Node
    tokens: list[Token]
    normalized: str
    assignments: dict[str, Decimal] = field(default_factory=dict)
    trace: list[TraceEntry] = field(default_factory=list)
    elapsed_ms: float = 0.0

    def tree_lines(self) -> list[str]:
        return render_tree(self.tree)

    @property
    def node_count(self) -> int:
        return sum(1 for _ in self.tree.walk())


class Engine:
    """Stateful front door to the evaluation pipeline."""

    def __init__(
        self,
        precision: int = 28,
        angle_mode: AngleMode = AngleMode.RADIANS,
        registry: Registry = REGISTRY,
    ):
        self.context = EvalContext(angle_mode=angle_mode, precision=precision)
        self.registry = registry
        self.formatter = Formatter(precision=precision)
        self.collect_trace = False

    # -- configuration ------------------------------------------------------ #

    @property
    def angle_mode(self) -> AngleMode:
        return self.context.angle_mode

    @angle_mode.setter
    def angle_mode(self, mode: AngleMode) -> None:
        self.context.angle_mode = mode

    @property
    def precision(self) -> int:
        return self.context.precision

    @precision.setter
    def precision(self, digits: int) -> None:
        clamped = max(6, min(200, digits))
        self.context.precision = clamped
        self.formatter.precision = clamped

    @property
    def notation(self) -> NotationMode:
        return self.formatter.notation

    @notation.setter
    def notation(self, mode: NotationMode) -> None:
        self.formatter.notation = mode

    # -- evaluation --------------------------------------------------------- #

    def evaluate(self, source: str) -> EvalResult:
        """Run the full pipeline. Raises :class:`CalcError` on any failure."""
        text = source.strip()
        if not text:
            raise CalcError("Nothing to evaluate.", 0)

        started = time.perf_counter()
        tokens = tokenize(text)
        tree = parse(tokens, text)

        evaluator = Evaluator(
            context=self.context,
            registry=self.registry,
            collect_trace=self.collect_trace,
        )
        value = evaluator.evaluate(tree)
        elapsed = (time.perf_counter() - started) * 1000

        self.context.set_variable("ans", value)

        return EvalResult(
            source=text,
            value=value,
            formatted=self.formatter.format(value),
            tree=tree,
            tokens=tokens,
            normalized=unparse(tree),
            assignments=dict(evaluator.assignments),
            trace=list(evaluator.trace),
            elapsed_ms=elapsed,
        )

    def try_evaluate(self, source: str) -> EvalResult | None:
        """Evaluate, returning ``None`` instead of raising. Used for live preview."""
        try:
            return self.evaluate(source)
        except CalcError:
            return None
        except (ArithmeticError, ValueError, RecursionError):
            return None

    # -- introspection ------------------------------------------------------ #

    def format(self, value: Decimal) -> str:
        return self.formatter.format(value)

    def completions(self, prefix: str) -> list[str]:
        """Names that start with ``prefix``, for the autocomplete hint bar."""
        if not prefix:
            return []
        lowered = prefix.lower()
        names = self.registry.all_names + sorted(self.context.variables)
        return [name for name in names if name.startswith(lowered)][:8]

    def describe(self, name: str) -> str | None:
        return self.registry.describe(name)

    def reset_variables(self) -> None:
        self.context.variables.clear()
