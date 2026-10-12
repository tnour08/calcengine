"""The status strip: clickable mode chips plus a self-clearing message."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..app.memory import MemoryBank
from ..core.context import AngleMode
from ..core.formatter import NotationMode
from .theme import FontSet, Theme
from .widgets import Chip, Tooltip

STATUS_HOLD_MS = 2600


class StatusBar(tk.Frame):
    """Shows current modes and transient feedback."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        fonts: FontSet,
        handlers: dict[str, Callable[[], None]],
        tooltip: Tooltip | None = None,
    ):
        super().__init__(parent, background=theme.panel)
        self.theme = theme
        self.fonts = fonts
        self._clear_job: str | None = None

        self._chips: dict[str, Chip] = {}
        chip_specs = [
            ("angle", "RAD", "Click to cycle radians / degrees / gradians", 56),
            ("notation", "AUTO", "Click to cycle number notation", 58),
            ("precision", "28d", "Working precision in significant digits", 46),
            ("theme", "Midnight", "Click to change theme", 74),
            ("memory", "M", "Memory register state", 34),
        ]
        for key, label, hint, width in chip_specs:
            chip = Chip(
                self,
                theme,
                label,
                command=handlers.get(key),
                font_family=fonts.ui,
                width=width,
                height=22,
                tooltip=hint,
            )
            chip.pack(side="left", padx=(0, 6))
            self._chips[key] = chip
            if tooltip is not None:
                tooltip.attach(chip, hint)

        self._message = tk.Label(
            self,
            text="Ready",
            background=theme.panel,
            foreground=theme.text_faint,
            font=(fonts.ui, 10),
            anchor="e",
        )
        self._message.pack(side="right", fill="x", expand=True, padx=(8, 2))

    # ------------------------------------------------------------------ #
    # Updates
    # ------------------------------------------------------------------ #

    def set_modes(
        self,
        angle_mode: AngleMode,
        notation: NotationMode,
        precision: int,
        theme_label: str,
    ) -> None:
        self._chips["angle"].set_text(angle_mode.value)
        self._chips["angle"].set_active(angle_mode is not AngleMode.RADIANS)
        self._chips["notation"].set_text(notation.value)
        self._chips["notation"].set_active(notation is not NotationMode.AUTO)
        self._chips["precision"].set_text(f"{precision}d")
        self._chips["theme"].set_text(theme_label)

    def set_memory(self, memory: MemoryBank) -> None:
        chip = self._chips["memory"]
        occupied = memory.occupied
        chip.set_text("M" if not occupied else f"M{len(occupied)}")
        chip.set_active(bool(occupied))

    def set_message(self, text: str, tone: str = "dim") -> None:
        colours = {
            "dim": self.theme.text_faint,
            "error": self.theme.danger,
            "good": self.theme.success,
        }
        self._message.configure(text=text, foreground=colours.get(tone, self.theme.text_faint))
        if self._clear_job is not None:
            self.after_cancel(self._clear_job)
        self._clear_job = self.after(STATUS_HOLD_MS, self._fade)

    def _fade(self) -> None:
        self._clear_job = None
        self._message.configure(text="Ready", foreground=self.theme.text_faint)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.panel)
        self._message.configure(background=theme.panel, foreground=theme.text_faint)
        for chip in self._chips.values():
            chip.apply_theme(theme)

    def destroy(self) -> None:  # pragma: no cover - teardown path
        if self._clear_job is not None:
            self.after_cancel(self._clear_job)
            self._clear_job = None
        super().destroy()
