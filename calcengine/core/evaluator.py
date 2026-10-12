"""Tree-walking evaluator.

Dispatch is table-driven on node class rather than using ``isinstance`` chains,
and every visit optionally appends to a trace so the UI can show the reduction
step by step.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, Overflow, localcontext
from typing import Callable

from . import dmath
from .context import EvalContext
from .errors import DomainError, EvalError, UnknownSymbolError
from .functions import REGISTRY, Registry, modulo, safe_divide
from .nodes import (
    Assign,
    Binary,
    Call,
    Identifier,
    Node,
    NumberLit,
    Postfix,
    Unary,
    unparse,
)

#: Hard ceiling on tree depth, so a pathological input cannot blow the stack.
MAX_DEPTH = 120


@dataclass
class TraceEntry:
    """One reduction step: a subexpression and the value it produced."""

    expression: str
    value: Decimal
    depth: int


@dataclass
class Evaluator:
    """Evaluates an AST within an :class:`EvalContext`."""

    context: EvalContext
    registry: Registry = REGISTRY
    collect_trace: bool = False
    trace: list[TraceEntry] = field(default_factory=list)
    assignments: dict[str, Decimal] = field(default_factory=dict)
    _depth: int = 0

    # -- public API --------------------------------------------------------- #

    def evaluate(self, node: Node) -> Decimal:
        self.trace.clear()
        self.assignments.clear()
        self._depth = 0
        if node.depth > MAX_DEPTH:
            raise EvalError("Expression is nested too deeply.")
        with localcontext() as ctx:
            ctx.prec = self.context.precision
            return self._visit(node)

    # -- dispatch ----------------------------------------------------------- #

    def _visit(self, node: Node) -> Decimal:
        handler: Callable[[Node], Decimal] | None = _DISPATCH.get(type(node))
        if handler is None:  # pragma: no cover - guards future node types
            raise EvalError(f"Cannot evaluate {type(node).__name__}.", node.position)

        self._depth += 1
        try:
            value = handler(self, node)
        except (InvalidOperation, Overflow) as exc:
            raise DomainError(
                "The result is outside the representable range.", node.position
            ) from exc
        finally:
            self._depth -= 1

        if self.collect_trace and not isinstance(node, (NumberLit, Identifier)):
            self.trace.append(
                TraceEntry(expression=unparse(node), value=value, depth=self._depth)
            )
        return value

    # -- leaves ------------------------------------------------------------- #

    def _visit_number(self, node: NumberLit) -> Decimal:
        return +node.value

    def _visit_identifier(self, node: Identifier) -> Decimal:
        constant = self.registry.get_constant(node.name)
        if constant is not None:
            return constant
        if node.name in self.context.variables:
            return self.context.variables[node.name]
        if self.registry.get_function(node.name) is not None:
            raise EvalError(
                f"'{node.name}' is a function; call it like {node.name}(x).",
                node.position,
                len(node.name),
            )
        raise UnknownSymbolError(
            node.name, node.position, self._suggest(node.name)
        )

    def _suggest(self, name: str) -> str | None:
        candidates = self.registry.all_names + list(self.context.variables)
        matches = difflib.get_close_matches(name, candidates, n=1, cutoff=0.7)
        return matches[0] if matches else None

    # -- operators ---------------------------------------------------------- #

    def _visit_unary(self, node: Unary) -> Decimal:
        value = self._visit(node.operand)
        if node.op == "-":
            return -value
        return value

    def _visit_postfix(self, node: Postfix) -> Decimal:
        value = self._visit(node.operand)
        if node.op == "!":
            try:
                return dmath.factorial(value)
            except DomainError as exc:
                raise DomainError(exc.message, node.position) from exc
        if node.op == "%":
            return value / 100
        if node.op == "\u00b2":
            return value * value
        if node.op == "\u00b3":
            return value * value * value
        raise EvalError(f"Unknown postfix operator {node.op!r}.", node.position)

    def _visit_binary(self, node: Binary) -> Decimal:
        left = self._visit(node.left)
        right = self._visit(node.right)
        try:
            if node.op == "+":
                return left + right
            if node.op == "-":
                return left - right
            if node.op == "*":
                return left * right
            if node.op == "/":
                return safe_divide(left, right)
            if node.op == "mod":
                return modulo(left, right)
            if node.op == "^":
                return dmath.power(left, right)
        except DomainError as exc:
            raise DomainError(exc.message, node.position) from exc
        raise EvalError(f"Unknown operator {node.op!r}.", node.position)

    def _visit_call(self, node: Call) -> Decimal:
        spec = self.registry.get_function(node.name)
        if spec is None:
            if self.registry.has_constant(node.name):
                raise EvalError(
                    f"'{node.name}' is a constant, not a function.",
                    node.position,
                    len(node.name),
                )
            raise UnknownSymbolError(
                node.name, node.position, self._suggest(node.name)
            )
        args = [self._visit(arg) for arg in node.args]
        try:
            return spec(self.context, args)
        except DomainError as exc:
            raise DomainError(exc.message, node.position, len(node.name)) from exc
        except ZeroDivisionError as exc:
            raise DomainError("Division by zero.", node.position) from exc

    def _visit_assign(self, node: Assign) -> Decimal:
        if node.name in EvalContext.RESERVED:
            raise EvalError(
                f"'{node.name}' is a built-in constant and cannot be reassigned.",
                node.position,
                len(node.name),
            )
        if self.registry.get_function(node.name) is not None:
            raise EvalError(
                f"'{node.name}' is a built-in function and cannot be reassigned.",
                node.position,
                len(node.name),
            )
        value = self._visit(node.value)
        self.context.set_variable(node.name, value)
        self.assignments[node.name] = value
        return value


#: Node class -> bound-method name, resolved once at import time.
_DISPATCH: dict[type, Callable[[Evaluator, Node], Decimal]] = {
    NumberLit: Evaluator._visit_number,
    Identifier: Evaluator._visit_identifier,
    Unary: Evaluator._visit_unary,
    Postfix: Evaluator._visit_postfix,
    Binary: Evaluator._visit_binary,
    Call: Evaluator._visit_call,
    Assign: Evaluator._visit_assign,
}
