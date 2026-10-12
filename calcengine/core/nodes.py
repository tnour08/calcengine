"""Immutable abstract-syntax-tree nodes plus two visitors.

The tree is the single source of truth shared by the evaluator, the
pretty-printer and the on-screen tree inspector, so nodes stay dumb: they
carry source positions and children, and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterator


@dataclass(frozen=True)
class Node:
    """Base node. ``position`` indexes into the original source string."""

    position: int = 0

    @property
    def label(self) -> str:
        """Short text used by the tree inspector."""
        return type(self).__name__

    def children(self) -> tuple["Node", ...]:
        return ()

    def walk(self) -> Iterator["Node"]:
        """Depth-first pre-order traversal."""
        yield self
        for child in self.children():
            yield from child.walk()

    @property
    def depth(self) -> int:
        kids = self.children()
        return 1 + max((child.depth for child in kids), default=0)


@dataclass(frozen=True)
class NumberLit(Node):
    value: Decimal = Decimal(0)
    raw: str = "0"

    @property
    def label(self) -> str:
        return f"Number {self.raw}"


@dataclass(frozen=True)
class Identifier(Node):
    name: str = ""

    @property
    def label(self) -> str:
        return f"Name {self.name}"


@dataclass(frozen=True)
class Unary(Node):
    op: str = "-"
    operand: Node = field(default_factory=Node)

    @property
    def label(self) -> str:
        return f"Unary {self.op}"

    def children(self) -> tuple[Node, ...]:
        return (self.operand,)


@dataclass(frozen=True)
class Postfix(Node):
    op: str = "!"
    operand: Node = field(default_factory=Node)

    @property
    def label(self) -> str:
        return f"Postfix {self.op}"

    def children(self) -> tuple[Node, ...]:
        return (self.operand,)


@dataclass(frozen=True)
class Binary(Node):
    op: str = "+"
    left: Node = field(default_factory=Node)
    right: Node = field(default_factory=Node)
    implicit: bool = False

    @property
    def label(self) -> str:
        suffix = " (implicit)" if self.implicit else ""
        return f"Binary {self.op}{suffix}"

    def children(self) -> tuple[Node, ...]:
        return (self.left, self.right)


@dataclass(frozen=True)
class Call(Node):
    name: str = ""
    args: tuple[Node, ...] = ()

    @property
    def label(self) -> str:
        return f"Call {self.name}/{len(self.args)}"

    def children(self) -> tuple[Node, ...]:
        return self.args


@dataclass(frozen=True)
class Assign(Node):
    name: str = ""
    value: Node = field(default_factory=Node)

    @property
    def label(self) -> str:
        return f"Assign {self.name}"

    def children(self) -> tuple[Node, ...]:
        return (self.value,)


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #

#: Binding power per construct, used to decide where parentheses are genuinely
#: required when printing a tree back to text. Unary minus sits *below* power
#: because "-2 ^ 2" means "-(2 ^ 2)", so a negated base needs brackets.
_PREC_ADDITIVE = 1
_PREC_MULTIPLICATIVE = 2
_PREC_UNARY = 3
_PREC_POWER = 4
_PREC_POSTFIX = 5
_PREC_ATOM = 99

_PRINT_PRECEDENCE = {
    "+": _PREC_ADDITIVE,
    "-": _PREC_ADDITIVE,
    "*": _PREC_MULTIPLICATIVE,
    "/": _PREC_MULTIPLICATIVE,
    "mod": _PREC_MULTIPLICATIVE,
    "^": _PREC_POWER,
}


def unparse(node: Node) -> str:
    """Render ``node`` back to a minimally-parenthesised expression string."""
    text, _ = _unparse(node)
    return text


def _unparse(node: Node) -> tuple[str, int]:
    """Return ``(text, precedence)`` so callers can add parens as needed."""
    if isinstance(node, NumberLit):
        return node.raw, _PREC_ATOM
    if isinstance(node, Identifier):
        return node.name, _PREC_ATOM
    if isinstance(node, Call):
        inner = ", ".join(unparse(arg) for arg in node.args)
        return f"{node.name}({inner})", _PREC_ATOM
    if isinstance(node, Unary):
        text, prec = _unparse(node.operand)
        if prec < _PREC_POWER:
            text = f"({text})"
        return f"{node.op}{text}", _PREC_UNARY
    if isinstance(node, Postfix):
        text, prec = _unparse(node.operand)
        if prec < _PREC_POSTFIX:
            text = f"({text})"
        return f"{text}{node.op}", _PREC_POSTFIX
    if isinstance(node, Binary):
        precedence = _PRINT_PRECEDENCE.get(node.op, _PREC_ADDITIVE)
        left, left_prec = _unparse(node.left)
        right, right_prec = _unparse(node.right)
        is_power = node.op == "^"
        # Power is right-associative, so an equally-bound *left* operand needs
        # brackets; every other operator is left-associative, so it is the
        # *right* operand that does.
        if left_prec < precedence or (left_prec == precedence and is_power):
            left = f"({left})"
        if right_prec < precedence or (right_prec == precedence and not is_power):
            right = f"({right})"
        if node.implicit:
            return f"{left}{right}", precedence
        return f"{left} {node.op} {right}", precedence
    if isinstance(node, Assign):
        return f"{node.name} = {unparse(node.value)}", 0
    return "?", 0


def render_tree(node: Node, prefix: str = "", connector: str = "") -> list[str]:
    """Render the tree as box-drawing lines for the inspector panel."""
    lines = [f"{prefix}{connector}{node.label}"]
    if connector:
        child_prefix = prefix + ("   " if connector.startswith("\u2514") else "\u2502  ")
    else:
        child_prefix = prefix
    kids = node.children()
    for index, child in enumerate(kids):
        is_last = index == len(kids) - 1
        lines.extend(
            render_tree(child, child_prefix, "\u2514\u2500 " if is_last else "\u251c\u2500 ")
        )
    return lines
