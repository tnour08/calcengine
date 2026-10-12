"""The display: expression line, blinking caret, live preview and errors.

Drawn on a canvas rather than built from labels, because we need to place a
caret and an error underline at exact character offsets. Positions come from
``tkinter.font.Font.measure`` against the same font used to draw the text.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont

from .theme import FontSet, Theme, blend

CARET_BLINK_MS = 530


class DisplayPanel(tk.Canvas):
    """Shows what is being typed, what it will evaluate to, and what broke."""

    PADDING_X = 18

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        fonts: FontSet,
        height: int = 158,
    ):
        super().__init__(
            parent,
            height=height,
            highlightthickness=0,
            bd=0,
            background=theme.display,
        )
        self.theme = theme
        self.fonts = fonts

        self.expression_font = tkfont.Font(family=fonts.mono, size=30)
        self.preview_font = tkfont.Font(family=fonts.mono, size=15)
        self.hint_font = tkfont.Font(family=fonts.ui, size=10)
        self.error_font = tkfont.Font(family=fonts.ui, size=11)
        self.caret_font = tkfont.Font(family=fonts.mono, size=30)

        self._expression = ""
        self._cursor = 0
        self._preview = ""
        self._hint = ""
        self._error: tuple[str, int | None, int] | None = None
        self._caret_visible = True
        self._blink_job: str | None = None
        self._result_pulse = 0.0

        # Drawing order matters: underline sits behind the glyphs.
        self._underline = self.create_rectangle(
            0, 0, 0, 0, fill=theme.danger, outline=""
        )
        self._rule = self.create_line(0, 0, 0, 0, fill=theme.border, width=1)
        self._hint_item = self.create_text(
            self.PADDING_X, 16, text="", anchor="w",
            fill=theme.text_faint, font=self.hint_font,
        )
        self._expression_item = self.create_text(
            self.PADDING_X, 64, text="", anchor="w",
            fill=theme.text, font=self.expression_font,
        )
        self._caret_item = self.create_rectangle(
            0, 0, 0, 0, fill=theme.accent, outline=""
        )
        self._preview_item = self.create_text(
            0, 112, text="", anchor="e", fill=theme.text_dim, font=self.preview_font,
        )
        self._error_item = self.create_text(
            self.PADDING_X, 136, text="", anchor="w",
            fill=theme.danger, font=self.error_font,
        )

        self.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Button-1>", self._on_click)
        self._schedule_blink()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    #: Set by the window so clicking the display can move the model's cursor.
    on_cursor_request = None

    def set_expression(self, text: str, cursor: int, preview: str = "") -> None:
        self._expression = text
        self._cursor = max(0, min(cursor, len(text)))
        self._preview = preview
        self._error = None
        self._caret_visible = True
        self._redraw()

    def set_error(self, message: str, position: int | None, length: int = 1) -> None:
        self._error = (message, position, length)
        self._preview = ""
        self._redraw()

    def set_hint(self, text: str) -> None:
        self._hint = text
        self.itemconfigure(self._hint_item, text=text)

    def pulse(self) -> None:
        """Briefly tint the expression to acknowledge a committed result."""
        self._result_pulse = 1.0
        self._step_pulse()

    def _step_pulse(self) -> None:
        self._result_pulse = max(0.0, self._result_pulse - 0.12)
        colour = blend(self.theme.text, self.theme.accent, self._result_pulse)
        self.itemconfigure(self._expression_item, fill=colour)
        if self._result_pulse > 0:
            self.after(28, self._step_pulse)

    # ------------------------------------------------------------------ #
    # Drawing
    # ------------------------------------------------------------------ #

    def _text_origin(self) -> float:
        """Left edge for the expression, right-aligned but caret-aware."""
        width = max(self.winfo_width(), 1)
        right = width - self.PADDING_X
        left = self.PADDING_X
        text_width = self.expression_font.measure(self._expression)

        origin = right - text_width
        if origin > left:
            origin = left if text_width == 0 else origin

        caret_offset = self.expression_font.measure(self._expression[: self._cursor])
        caret_x = origin + caret_offset
        if caret_x < left:
            origin += left - caret_x
        elif caret_x > right:
            origin -= caret_x - right
        return origin

    def _redraw(self) -> None:
        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)
        right = width - self.PADDING_X

        origin = self._text_origin()
        self.coords(self._expression_item, origin, 64)
        self.itemconfigure(self._expression_item, text=self._expression)

        self.coords(self._preview_item, right, 112)
        self.itemconfigure(
            self._preview_item,
            text=f"= {self._preview}" if self._preview else "",
        )

        self.coords(self._rule, self.PADDING_X, 92, right, 92)
        self.itemconfigure(self._rule, fill=self.theme.border)

        # Caret
        caret_x = origin + self.expression_font.measure(
            self._expression[: self._cursor]
        )
        if self._caret_visible and self._error is None:
            self.coords(self._caret_item, caret_x, 44, caret_x + 2, 84)
            self.itemconfigure(self._caret_item, fill=self.theme.accent, state="normal")
        else:
            self.itemconfigure(self._caret_item, state="hidden")

        # Error message plus the squiggle under the offending span
        if self._error is None:
            self.itemconfigure(self._error_item, text="")
            self.coords(self._underline, 0, 0, 0, 0)
        else:
            message, position, length = self._error
            self.itemconfigure(self._error_item, text=message, fill=self.theme.danger)
            if position is not None and position <= len(self._expression):
                start = origin + self.expression_font.measure(
                    self._expression[:position]
                )
                end = origin + self.expression_font.measure(
                    self._expression[: position + length]
                )
                if end <= start:
                    end = start + 10
                self.coords(self._underline, start, 80, end, 83)
                self.itemconfigure(self._underline, fill=self.theme.danger)
            else:
                self.coords(self._underline, 0, 0, 0, 0)

        self.coords(self._error_item, self.PADDING_X, min(136, height - 12))

    # ------------------------------------------------------------------ #
    # Caret blink and clicking
    # ------------------------------------------------------------------ #

    def _schedule_blink(self) -> None:
        self._blink_job = self.after(CARET_BLINK_MS, self._blink)

    def _blink(self) -> None:
        self._caret_visible = not self._caret_visible
        if self._error is None:
            state = "normal" if self._caret_visible else "hidden"
            self.itemconfigure(self._caret_item, state=state)
        self._schedule_blink()

    def _on_click(self, event: tk.Event) -> None:
        """Translate a click x-coordinate into a character offset."""
        if self.on_cursor_request is None:
            return
        origin = self._text_origin()
        best_index = 0
        best_distance = float("inf")
        for index in range(len(self._expression) + 1):
            x = origin + self.expression_font.measure(self._expression[:index])
            distance = abs(x - event.x)
            if distance < best_distance:
                best_distance = distance
                best_index = index
        self.on_cursor_request(best_index)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.display)
        self.itemconfigure(self._expression_item, fill=theme.text)
        self.itemconfigure(self._preview_item, fill=theme.text_dim)
        self.itemconfigure(self._hint_item, fill=theme.text_faint)
        self.itemconfigure(self._error_item, fill=theme.danger)
        self.itemconfigure(self._caret_item, fill=theme.accent)
        self.itemconfigure(self._underline, fill=theme.danger)
        self._redraw()

    def destroy(self) -> None:  # pragma: no cover - teardown path
        if self._blink_job is not None:
            self.after_cancel(self._blink_job)
            self._blink_job = None
        super().destroy()
