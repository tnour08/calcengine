"""The observable application model.

Holds the input buffer, drives the engine, records history and broadcasts
every change over the :class:`~calcengine.app.events.EventBus`. The UI is a
pure function of the events emitted here, and nothing in this module imports
Tk, so the whole thing is testable headlessly.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from ..core import AngleMode, CalcError, Engine, EvalResult, NotationMode
from .commands import (
    Backspace,
    ClearAll,
    Command,
    CommandStack,
    DeleteForward,
    InsertText,
    SetExpression,
    ToggleSign,
)
from .events import EventBus, Topic
from .history import History, HistoryEntry
from .memory import MemoryBank
from .settings import Settings


class CalculatorModel:
    """Everything the UI needs, with no UI inside it."""

    def __init__(self, bus: EventBus | None = None, engine: Engine | None = None):
        self.bus = bus or EventBus()
        self.engine = engine or Engine()
        self.history = History()
        self.memory = MemoryBank()
        self.commands = CommandStack()

        self._expression = ""
        self._cursor = 0
        self.last_result: EvalResult | None = None
        self.last_error: CalcError | None = None
        self.live_preview = True
        self.theme_name = "midnight"
        self.show_tape = True
        self.show_inspector = False

    # ------------------------------------------------------------------ #
    # Buffer state
    # ------------------------------------------------------------------ #

    @property
    def expression(self) -> str:
        return self._expression

    @property
    def cursor(self) -> int:
        return self._cursor

    def set_expression_silently(self, text: str, cursor: int) -> None:
        """Write the buffer without emitting events.

        Commands call this during ``apply``/``undo``; the public methods below
        publish once afterwards, so a single user action yields one event.
        """
        self._expression = text
        self._cursor = max(0, min(cursor, len(text)))

    # ------------------------------------------------------------------ #
    # Editing
    # ------------------------------------------------------------------ #

    def _run(self, command: Command) -> None:
        self.commands.run(command, self)
        self.last_error = None
        self._announce_expression()

    def _announce_expression(self) -> None:
        self.bus.publish(
            Topic.EXPRESSION_CHANGED,
            expression=self._expression,
            cursor=self._cursor,
            preview=self.preview_text(),
            can_undo=self.commands.can_undo,
            can_redo=self.commands.can_redo,
        )

    def insert(self, text: str) -> None:
        if text:
            self._run(InsertText(text))

    def backspace(self) -> None:
        self._run(Backspace())

    def delete_forward(self) -> None:
        self._run(DeleteForward())

    def clear(self) -> None:
        self._run(ClearAll())
        self.bus.publish(Topic.STATUS, text="Cleared")

    def set_expression(self, text: str) -> None:
        self._run(SetExpression(text))

    def toggle_sign(self) -> None:
        self._run(ToggleSign())

    # -- cursor ------------------------------------------------------------- #

    def move_cursor(self, delta: int) -> None:
        self._cursor = max(0, min(self._cursor + delta, len(self._expression)))
        self._announce_expression()

    def set_cursor(self, index: int) -> None:
        self._cursor = max(0, min(index, len(self._expression)))
        self._announce_expression()

    def cursor_home(self) -> None:
        self.set_cursor(0)

    def cursor_end(self) -> None:
        self.set_cursor(len(self._expression))

    # -- undo/redo ---------------------------------------------------------- #

    def undo(self) -> None:
        command = self.commands.undo(self)
        if command is None:
            self.bus.publish(Topic.STATUS, text="Nothing to undo")
            return
        self.last_error = None
        self._announce_expression()
        self.bus.publish(Topic.STATUS, text=f"Undo {command.label}")

    def redo(self) -> None:
        command = self.commands.redo(self)
        if command is None:
            self.bus.publish(Topic.STATUS, text="Nothing to redo")
            return
        self.last_error = None
        self._announce_expression()
        self.bus.publish(Topic.STATUS, text=f"Redo {command.label}")

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def preview_text(self) -> str:
        """A speculative result for the dim line under the input, or ""."""
        if not self.live_preview or not self._expression.strip():
            return ""
        result = self.engine.try_evaluate(self._expression)
        if result is None:
            return ""
        if result.formatted == self._expression.strip():
            return ""
        return result.formatted

    def evaluate(self) -> EvalResult | None:
        """Commit the buffer: evaluate, record, and replace it with the result."""
        source = self._expression.strip()
        if not source:
            return None

        try:
            result = self.engine.evaluate(source)
        except CalcError as error:
            self.last_error = error
            self.bus.publish(
                Topic.ERROR_RAISED,
                error=error,
                message=error.message,
                code=error.code,
                position=error.position,
                length=error.length,
                source=source,
            )
            return None
        except RecursionError:
            error = CalcError("Expression is too deeply nested.")
            self.last_error = error
            self.bus.publish(
                Topic.ERROR_RAISED, error=error, message=error.message,
                code=error.code, position=None, length=1, source=source,
            )
            return None

        self.last_error = None
        self.last_result = result
        self.history.add(
            HistoryEntry(
                expression=result.source,
                formatted=result.formatted,
                value=result.value,
            )
        )

        # The result becomes the new buffer, so it can be built on directly.
        self.commands.run(SetExpression(result.formatted.replace(",", "")), self)

        self.bus.publish(Topic.RESULT_READY, result=result)
        self.bus.publish(Topic.HISTORY_CHANGED, history=self.history)
        if result.assignments:
            self.bus.publish(
                Topic.VARIABLES_CHANGED, variables=self.engine.context.snapshot()
            )
        self._announce_expression()
        return result

    @property
    def current_value(self) -> Decimal:
        """Best-effort numeric value of the buffer, for memory operations."""
        result = self.engine.try_evaluate(self._expression)
        if result is not None:
            return result.value
        if self.last_result is not None:
            return self.last_result.value
        return Decimal(0)

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #

    def recall_entry(self, entry: HistoryEntry, use_result: bool = False) -> None:
        text = entry.formatted.replace(",", "") if use_result else entry.expression
        self.set_expression(text)
        self.bus.publish(Topic.STATUS, text="Recalled from tape")

    def clear_history(self) -> None:
        self.history.clear()
        self.bus.publish(Topic.HISTORY_CHANGED, history=self.history)
        self.bus.publish(Topic.STATUS, text="Tape cleared")

    # ------------------------------------------------------------------ #
    # Memory
    # ------------------------------------------------------------------ #

    def memory_store(self, slot: str = MemoryBank.DEFAULT_SLOT) -> None:
        self.memory.store(self.current_value, slot)
        self._announce_memory(f"Stored in {slot}")

    def memory_recall(self, slot: str = MemoryBank.DEFAULT_SLOT) -> None:
        value = self.memory.recall(slot)
        self.insert(self.engine.format(value).replace(",", ""))
        self._announce_memory(f"Recalled {slot}")

    def memory_add(self, slot: str = MemoryBank.DEFAULT_SLOT) -> None:
        self.memory.add(self.current_value, slot)
        self._announce_memory(f"Added to {slot}")

    def memory_subtract(self, slot: str = MemoryBank.DEFAULT_SLOT) -> None:
        self.memory.subtract(self.current_value, slot)
        self._announce_memory(f"Subtracted from {slot}")

    def memory_clear(self, slot: str = MemoryBank.DEFAULT_SLOT) -> None:
        self.memory.clear(slot)
        self._announce_memory(f"Cleared {slot}")

    def _announce_memory(self, status: str) -> None:
        self.bus.publish(Topic.MEMORY_CHANGED, memory=self.memory)
        self.bus.publish(Topic.STATUS, text=status)

    # ------------------------------------------------------------------ #
    # Modes
    # ------------------------------------------------------------------ #

    def cycle_angle_mode(self) -> None:
        self.engine.angle_mode = self.engine.angle_mode.next()
        self._announce_mode(f"Angles in {self.engine.angle_mode.value}")

    def cycle_notation(self) -> None:
        self.engine.notation = self.engine.notation.next()
        self._announce_mode(f"Notation {self.engine.notation.value}")

    def set_precision(self, digits: int) -> None:
        self.engine.precision = digits
        self._announce_mode(f"{self.engine.precision} significant digits")

    def set_decimals(self, places: int) -> None:
        self.engine.formatter.decimals = max(0, min(60, places))
        self._announce_mode(f"{self.engine.formatter.decimals} decimal places")

    def toggle_grouping(self) -> None:
        formatter = self.engine.formatter
        formatter.group_thousands = not formatter.group_thousands
        state = "on" if formatter.group_thousands else "off"
        self._announce_mode(f"Digit grouping {state}")

    def toggle_tape(self) -> None:
        self.show_tape = not self.show_tape
        self._announce_mode("Tape " + ("shown" if self.show_tape else "hidden"))

    def toggle_inspector(self) -> None:
        self.show_inspector = not self.show_inspector
        self.engine.collect_trace = self.show_inspector
        state = "shown" if self.show_inspector else "hidden"
        self._announce_mode(f"Inspector {state}")

    def toggle_live_preview(self) -> None:
        self.live_preview = not self.live_preview
        state = "on" if self.live_preview else "off"
        self._announce_mode(f"Live preview {state}")
        self._announce_expression()

    def set_theme(self, name: str) -> None:
        self.theme_name = name
        self._announce_mode(f"Theme {name}")

    def _announce_mode(self, status: str) -> None:
        self.bus.publish(
            Topic.MODE_CHANGED,
            angle_mode=self.engine.angle_mode,
            notation=self.engine.notation,
            precision=self.engine.precision,
            decimals=self.engine.formatter.decimals,
            grouping=self.engine.formatter.group_thousands,
            theme=self.theme_name,
            show_tape=self.show_tape,
            show_inspector=self.show_inspector,
            live_preview=self.live_preview,
        )
        self.bus.publish(Topic.STATUS, text=status)

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def to_settings(self) -> Settings:
        return Settings(
            theme=self.theme_name,
            angle_mode=self.engine.angle_mode.value,
            notation=self.engine.notation.value,
            precision=self.engine.precision,
            decimals=self.engine.formatter.decimals,
            group_thousands=self.engine.formatter.group_thousands,
            show_tape=self.show_tape,
            show_inspector=self.show_inspector,
            live_preview=self.live_preview,
            history=self.history.to_list(),
            memory=self.memory.to_dict(),
            variables={
                name: str(value)
                for name, value in self.engine.context.variables.items()
            },
        )

    def apply_settings(self, settings: Settings) -> None:
        self.theme_name = settings.theme
        self.engine.angle_mode = _enum_or_default(
            AngleMode, settings.angle_mode, AngleMode.RADIANS
        )
        self.engine.notation = _enum_or_default(
            NotationMode, settings.notation, NotationMode.AUTO
        )
        self.engine.precision = settings.precision
        self.engine.formatter.decimals = settings.decimals
        self.engine.formatter.group_thousands = settings.group_thousands
        self.show_tape = settings.show_tape
        self.show_inspector = settings.show_inspector
        self.engine.collect_trace = settings.show_inspector
        self.live_preview = settings.live_preview
        self.history.load(settings.history)
        self.memory.load(settings.memory)
        for name, raw in settings.variables.items():
            try:
                self.engine.context.set_variable(name, Decimal(str(raw)))
            except InvalidOperation:
                continue


def _enum_or_default(enum_class, value, default):
    """Look up an enum by value, falling back when the stored string is stale."""
    try:
        return enum_class(value)
    except ValueError:
        return default
