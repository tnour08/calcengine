"""Command pattern with an undo/redo stack.

Every mutation of the input buffer goes through a :class:`Command`, which
captures the state it replaced so it can put it back. Consecutive keystrokes
coalesce into a single undo step, so Ctrl+Z behaves the way a text field does
rather than rewinding one character at a time.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from .model import CalculatorModel


class Command(ABC):
    """A reversible edit to the model's input buffer."""

    #: Human-readable name, shown in the status bar after undo/redo.
    label = "edit"

    def __init__(self) -> None:
        self._previous_expression: str | None = None
        self._previous_cursor: int = 0

    # -- template method ---------------------------------------------------- #

    def execute(self, model: "CalculatorModel") -> None:
        self._previous_expression = model.expression
        self._previous_cursor = model.cursor
        self.apply(model)

    def undo(self, model: "CalculatorModel") -> None:
        if self._previous_expression is not None:
            model.set_expression_silently(
                self._previous_expression, self._previous_cursor
            )

    @abstractmethod
    def apply(self, model: "CalculatorModel") -> None:
        """Perform the forward edit. Subclasses implement only this."""

    # -- coalescing --------------------------------------------------------- #

    def can_merge(self, other: "Command") -> bool:
        """Whether ``other``, executed next, should fold into this undo step."""
        return False

    def merge(self, other: "Command") -> None:
        """Absorb ``other``; only called when :meth:`can_merge` is true."""


class InsertText(Command):
    """Insert a literal fragment at the cursor."""

    label = "insert"

    def __init__(self, text: str):
        super().__init__()
        self.text = text

    def apply(self, model: "CalculatorModel") -> None:
        expression = model.expression
        cursor = model.cursor
        model.set_expression_silently(
            expression[:cursor] + self.text + expression[cursor:],
            cursor + len(self.text),
        )

    def can_merge(self, other: Command) -> bool:
        # Merge runs of digits/letters, but keep operators as their own step so
        # undo lands on a meaningful boundary.
        return (
            isinstance(other, InsertText)
            and other.text.isalnum()
            and self.text.isalnum()
        )

    def merge(self, other: Command) -> None:
        assert isinstance(other, InsertText)
        self.text += other.text


class Backspace(Command):
    """Delete the character before the cursor."""

    label = "backspace"

    def apply(self, model: "CalculatorModel") -> None:
        cursor = model.cursor
        if cursor == 0:
            return
        expression = model.expression
        model.set_expression_silently(
            expression[: cursor - 1] + expression[cursor:], cursor - 1
        )


class DeleteForward(Command):
    """Delete the character after the cursor."""

    label = "delete"

    def apply(self, model: "CalculatorModel") -> None:
        expression = model.expression
        cursor = model.cursor
        if cursor >= len(expression):
            return
        model.set_expression_silently(
            expression[:cursor] + expression[cursor + 1 :], cursor
        )


class ClearAll(Command):
    """Empty the input buffer."""

    label = "clear"

    def apply(self, model: "CalculatorModel") -> None:
        model.set_expression_silently("", 0)


class SetExpression(Command):
    """Replace the whole buffer, e.g. when recalling a history entry."""

    label = "replace"

    def __init__(self, text: str, cursor: int | None = None):
        super().__init__()
        self.text = text
        self.cursor = len(text) if cursor is None else cursor

    def apply(self, model: "CalculatorModel") -> None:
        model.set_expression_silently(self.text, self.cursor)


class ToggleSign(Command):
    """Negate the numeric literal the cursor is sitting in or next to."""

    label = "negate"

    def apply(self, model: "CalculatorModel") -> None:
        expression = model.expression
        if not expression:
            model.set_expression_silently("-", 1)
            return

        start, end = _literal_span(expression, model.cursor)
        literal = expression[start:end]
        if literal.startswith("-"):
            replacement = literal[1:]
            shift = -1
        else:
            replacement = "-" + literal
            shift = 1
        model.set_expression_silently(
            expression[:start] + replacement + expression[end:],
            max(0, model.cursor + shift),
        )


def _literal_span(expression: str, cursor: int) -> tuple[int, int]:
    """Bounds of the number-ish run of characters around ``cursor``."""
    allowed = set("0123456789._")
    end = min(cursor, len(expression))
    while end < len(expression) and expression[end] in allowed:
        end += 1
    start = end
    while start > 0 and expression[start - 1] in allowed:
        start -= 1
    # Absorb a leading minus when it is a sign rather than a subtraction.
    if start > 0 and expression[start - 1] == "-":
        is_sign = start - 1 == 0 or expression[start - 2] in "(+-*/^,"
        if is_sign:
            start -= 1
    return start, end


class CommandStack:
    """Bounded undo/redo history over executed commands."""

    def __init__(self, limit: int = 300):
        self.limit = limit
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    def run(self, command: Command, model: "CalculatorModel") -> None:
        command.execute(model)
        self._redo.clear()

        if self._undo and self._undo[-1].can_merge(command):
            self._undo[-1].merge(command)
        else:
            self._undo.append(command)
            overflow = len(self._undo) - self.limit
            if overflow > 0:
                del self._undo[:overflow]

    def undo(self, model: "CalculatorModel") -> Command | None:
        if not self._undo:
            return None
        command = self._undo.pop()
        command.undo(model)
        self._redo.append(command)
        return command

    def redo(self, model: "CalculatorModel") -> Command | None:
        if not self._redo:
            return None
        command = self._redo.pop()
        command.execute(model)
        self._undo.append(command)
        return command

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def __len__(self) -> int:
        return len(self._undo)
