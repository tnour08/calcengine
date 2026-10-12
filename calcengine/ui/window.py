"""The main window: assembles the panels and translates input into commands.

This is the only module that knows about both the model and the widgets. It
subscribes to the event bus and pushes state into the panels; it never lets a
panel read the model directly.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from ..app.events import Event, EventBus, Topic
from ..app.history import HistoryEntry
from ..app.model import CalculatorModel
from ..app.settings import SettingsStore
from .display import DisplayPanel
from .inspector import InspectorPanel
from .keypad import Action, Keypad
from .statusbar import StatusBar
from .tape import TapePanel
from .theme import FontSet, get_theme, next_theme
from .widgets import Tooltip

WINDOW_TITLE = "calcengine"
MIN_WIDTH, MIN_HEIGHT = 560, 640

#: Characters that insert themselves verbatim when typed.
TYPEABLE = set("0123456789.+-*/^%!()eπτφ,√²³ ")

#: Precision steps cycled by clicking the precision chip.
PRECISION_STEPS = (16, 28, 50, 100)


class CalculatorWindow(tk.Tk):
    """The application window."""

    def __init__(self, store: SettingsStore | None = None):
        super().__init__()
        self.store = store or SettingsStore()
        self.bus = EventBus()
        self.model = CalculatorModel(bus=self.bus)

        self.settings = self.store.load()
        self.model.apply_settings(self.settings)

        self.theme = get_theme(self.model.theme_name)
        self.fonts = FontSet.resolve(tkfont.families(self))

        self.title(WINDOW_TITLE)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.configure(background=self.theme.window)

        self.tooltip = Tooltip(self, self.theme, self.fonts.ui)

        self._build_layout()
        self._wire_events()
        self._bind_keys()

        self._refresh_everything()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._centre(980 if self.model.show_tape else 560, 760)

    def _centre(self, width: int, height: int) -> None:
        """Open centred, never narrower than the layout actually asks for.

        The side panels and the keypad both have a natural width; opening below
        it silently squeezes every key, so treat the arguments as a floor
        rather than as the size.
        """
        self.update_idletasks()
        width = max(width, self.winfo_reqwidth())
        height = max(height, self.winfo_reqheight())
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")

    # ------------------------------------------------------------------ #
    # Layout
    # ------------------------------------------------------------------ #

    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self._root_frame = tk.Frame(self, background=self.theme.window)
        self._root_frame.grid(row=0, column=0, sticky="nsew")
        self._root_frame.rowconfigure(0, weight=1)
        self._root_frame.columnconfigure(0, weight=1, minsize=400)

        # Left: display + keypad + status
        self._main = tk.Frame(self._root_frame, background=self.theme.panel)
        self._main.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self._main.rowconfigure(1, weight=1)
        self._main.columnconfigure(0, weight=1)

        self.display = DisplayPanel(self._main, self.theme, self.fonts)
        self.display.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.display.on_cursor_request = self.model.set_cursor

        self.keypad = Keypad(
            self._main, self.theme, self.fonts, self._dispatch, self.tooltip
        )
        self.keypad.grid(row=1, column=0, sticky="nsew")

        self.status = StatusBar(
            self._main,
            self.theme,
            self.fonts,
            handlers={
                "angle": self.model.cycle_angle_mode,
                "notation": self.model.cycle_notation,
                "precision": self._cycle_precision,
                "theme": self._cycle_theme,
                "memory": self.model.memory_store,
            },
            tooltip=self.tooltip,
        )
        self.status.grid(row=2, column=0, sticky="ew", pady=(8, 2), padx=4)

        # Right: tape and inspector, each independently toggleable
        self._side = tk.Frame(self._root_frame, background=self.theme.window)
        self._side.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        self._side.rowconfigure(0, weight=1)
        self._side.rowconfigure(1, weight=1)
        self._side.columnconfigure(0, weight=1, minsize=250)

        self.tape = TapePanel(
            self._side,
            self.theme,
            self.fonts,
            on_recall=self._on_recall,
            on_clear=self.model.clear_history,
        )
        self.inspector = InspectorPanel(self._side, self.theme, self.fonts)

    def _layout_side_panels(self) -> None:
        """Show or hide the side column based on the two toggles."""
        self.tape.grid_forget()
        self.inspector.grid_forget()

        show_tape = self.model.show_tape
        show_inspector = self.model.show_inspector

        if not (show_tape or show_inspector):
            self._side.grid_remove()
            self._root_frame.columnconfigure(1, weight=0, minsize=0)
            return

        self._side.grid()
        self._root_frame.columnconfigure(1, weight=1, minsize=260)
        row = 0
        if show_tape:
            self.tape.grid(row=row, column=0, sticky="nsew", pady=(0, 5))
            self._side.rowconfigure(row, weight=1)
            row += 1
        else:
            self._side.rowconfigure(0, weight=0)
        if show_inspector:
            self.inspector.grid(row=row, column=0, sticky="nsew")
            self._side.rowconfigure(row, weight=2 if show_tape else 1)
        if row < 1:
            self._side.rowconfigure(1, weight=0)

    # ------------------------------------------------------------------ #
    # Event wiring
    # ------------------------------------------------------------------ #

    def _wire_events(self) -> None:
        self.bus.subscribe(Topic.EXPRESSION_CHANGED, self._on_expression)
        self.bus.subscribe(Topic.RESULT_READY, self._on_result)
        self.bus.subscribe(Topic.ERROR_RAISED, self._on_error)
        self.bus.subscribe(Topic.HISTORY_CHANGED, self._on_history)
        self.bus.subscribe(Topic.MEMORY_CHANGED, self._on_memory)
        self.bus.subscribe(Topic.MODE_CHANGED, self._on_mode)
        self.bus.subscribe(Topic.STATUS, self._on_status)

    def _on_expression(self, event: Event) -> None:
        self.display.set_expression(
            event.get("expression", ""),
            event.get("cursor", 0),
            event.get("preview", ""),
        )
        self.display.set_hint(self._completion_hint())

    def _completion_hint(self) -> str:
        """Describe the identifier the cursor is currently inside."""
        expression = self.model.expression
        cursor = self.model.cursor
        start = cursor
        while start > 0 and (expression[start - 1].isalnum() or expression[start - 1] == "_"):
            start -= 1
        word = expression[start:cursor]
        if len(word) < 2:
            return ""
        described = self.model.engine.describe(word)
        if described:
            return described
        matches = self.model.engine.completions(word)
        return "  ".join(matches) if matches else ""

    def _on_result(self, event: Event) -> None:
        result = event.get("result")
        if result is None:
            return
        self.display.pulse()
        if self.model.show_inspector:
            self.inspector.show_result(result)
        self.status.set_message(
            f"{result.node_count} nodes in {result.elapsed_ms:.2f} ms", "good"
        )

    def _on_error(self, event: Event) -> None:
        self.display.set_error(
            event.get("message", "Error"),
            event.get("position"),
            event.get("length", 1),
        )
        self.status.set_message(event.get("message", "Error"), "error")
        if self.model.show_inspector:
            self.inspector.show_error(
                event.get("message", "Error"),
                event.get("source", ""),
                event.get("position"),
                event.get("length", 1),
            )

    def _on_history(self, _event: Event) -> None:
        self.tape.render(self.model.history)

    def _on_memory(self, _event: Event) -> None:
        self.status.set_memory(self.model.memory)

    def _on_mode(self, _event: Event) -> None:
        self.status.set_modes(
            self.model.engine.angle_mode,
            self.model.engine.notation,
            self.model.engine.precision,
            get_theme(self.model.theme_name).label,
        )
        if get_theme(self.model.theme_name) is not self.theme:
            self._apply_theme(self.model.theme_name)
        self._layout_side_panels()
        self.display.set_expression(
            self.model.expression, self.model.cursor, self.model.preview_text()
        )

    def _on_status(self, event: Event) -> None:
        self.status.set_message(event.get("text", ""))

    def _refresh_everything(self) -> None:
        self.status.set_modes(
            self.model.engine.angle_mode,
            self.model.engine.notation,
            self.model.engine.precision,
            self.theme.label,
        )
        self.status.set_memory(self.model.memory)
        self.tape.render(self.model.history)
        self._layout_side_panels()
        self.display.set_expression(
            self.model.expression, self.model.cursor, self.model.preview_text()
        )

    # ------------------------------------------------------------------ #
    # Dispatch
    # ------------------------------------------------------------------ #

    def _dispatch(self, action: Action) -> None:
        kind, payload = action
        if kind == "insert":
            self.model.insert(payload)
        elif kind == "call":
            method = getattr(self.model, payload, None)
            if callable(method):
                method()

    def _on_recall(self, entry: HistoryEntry, use_result: bool) -> None:
        self.model.recall_entry(entry, use_result)

    def _cycle_precision(self) -> None:
        current = self.model.engine.precision
        for step in PRECISION_STEPS:
            if step > current:
                self.model.set_precision(step)
                return
        self.model.set_precision(PRECISION_STEPS[0])

    def _cycle_theme(self) -> None:
        self.model.set_theme(next_theme(self.model.theme_name))

    def _apply_theme(self, name: str) -> None:
        self.theme = get_theme(name)
        self.configure(background=self.theme.window)
        self._root_frame.configure(background=self.theme.window)
        self._main.configure(background=self.theme.panel)
        self._side.configure(background=self.theme.window)
        self.tooltip.apply_theme(self.theme)
        self.display.apply_theme(self.theme)
        self.keypad.apply_theme(self.theme)
        self.status.apply_theme(self.theme)
        self.tape.apply_theme(self.theme)
        self.inspector.apply_theme(self.theme)
        self.tape.render(self.model.history)
        self.status.set_memory(self.model.memory)
        self.status.set_modes(
            self.model.engine.angle_mode,
            self.model.engine.notation,
            self.model.engine.precision,
            self.theme.label,
        )

    # ------------------------------------------------------------------ #
    # Keyboard
    # ------------------------------------------------------------------ #

    def _bind_keys(self) -> None:
        self.bind("<Key>", self._on_key)
        self.bind("<Return>", self._on_equals)
        self.bind("<KP_Enter>", self._on_equals)
        self.bind("<BackSpace>", self._on_backspace)
        self.bind("<Delete>", lambda _e: self.model.delete_forward())
        self.bind("<Escape>", self._on_escape)
        self.bind("<Left>", lambda _e: self.model.move_cursor(-1))
        self.bind("<Right>", lambda _e: self.model.move_cursor(1))
        self.bind("<Home>", lambda _e: self.model.cursor_home())
        self.bind("<End>", lambda _e: self.model.cursor_end())
        self.bind("<Up>", lambda _e: self._recall_relative(-1))
        self.bind("<Down>", lambda _e: self._recall_relative(1))

        for sequence, handler in {
            "<Command-z>": self.model.undo,
            "<Control-z>": self.model.undo,
            "<Command-Shift-Z>": self.model.redo,
            "<Control-y>": self.model.redo,
            "<Command-t>": self._cycle_theme,
            "<Control-t>": self._cycle_theme,
            "<Command-d>": self.model.cycle_angle_mode,
            "<Control-d>": self.model.cycle_angle_mode,
            "<Command-n>": self.model.cycle_notation,
            "<Control-n>": self.model.cycle_notation,
            "<Command-h>": self.model.toggle_tape,
            "<Control-h>": self.model.toggle_tape,
            "<Command-i>": self.model.toggle_inspector,
            "<Control-i>": self.model.toggle_inspector,
            "<Command-l>": self.model.clear_history,
            "<Control-l>": self.model.clear_history,
            "<Command-p>": self.model.toggle_live_preview,
            "<Control-p>": self.model.toggle_live_preview,
            "<Command-g>": self.model.toggle_grouping,
            "<Control-g>": self.model.toggle_grouping,
            "<Tab>": self.keypad.cycle_page,
        }.items():
            self.bind(sequence, self._wrap_shortcut(handler))

        self._history_offset = 0

    @staticmethod
    def _wrap_shortcut(handler):
        def run(_event: tk.Event) -> str:
            handler()
            return "break"
        return run

    def _on_key(self, event: tk.Event) -> str | None:
        if event.state & 0x0008 or event.state & 0x0004:
            return None  # let Command/Control shortcuts through
        character = event.char
        if not character:
            return None
        if character in TYPEABLE:
            self.model.insert(character)
            self.keypad.flash_key(character)
            return "break"
        if character.isalpha():
            self.model.insert(character)
            return "break"
        if character == "=":
            return self._on_equals(event)
        return None

    def _on_equals(self, _event: tk.Event) -> str:
        self.keypad.flash_label("=")
        self.model.evaluate()
        self._history_offset = 0
        return "break"

    def _on_backspace(self, _event: tk.Event) -> str:
        self.keypad.flash_label("\u232b")
        self.model.backspace()
        return "break"

    def _on_escape(self, _event: tk.Event) -> str:
        self.keypad.flash_label("AC")
        self.model.clear()
        self._history_offset = 0
        return "break"

    def _recall_relative(self, delta: int) -> None:
        """Up/Down walk back through the tape, shell-history style."""
        entries = self.model.history.recent()
        if not entries:
            return
        self._history_offset = max(
            0, min(len(entries), self._history_offset - delta)
        )
        if self._history_offset == 0:
            self.model.set_expression("")
            return
        entry = entries[self._history_offset - 1]
        self.model.set_expression(entry.expression)

    # ------------------------------------------------------------------ #
    # Teardown
    # ------------------------------------------------------------------ #

    def _on_close(self) -> None:
        self.store.save(self.model.to_settings())
        self.tooltip.hide()
        self.destroy()


def launch() -> None:
    """Entry point used by ``python -m calcengine``."""
    CalculatorWindow().mainloop()
