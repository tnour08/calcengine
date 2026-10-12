"""The tape: a clickable, scrollable log of past calculations.

Built on a read-only ``Text`` widget so scrolling and wrapping come for free;
each entry gets its own tag bound to click handlers, which is how rows become
individually interactive.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..app.history import History, HistoryEntry
from .theme import FontSet, Theme
from .widgets import Chip


class TapePanel(tk.Frame):
    """Newest-first history with click-to-recall."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        fonts: FontSet,
        on_recall: Callable[[HistoryEntry, bool], None],
        on_clear: Callable[[], None],
        width: int = 268,
    ):
        super().__init__(parent, background=theme.panel, width=width)
        self.theme = theme
        self.fonts = fonts
        self.on_recall = on_recall
        self.on_clear = on_clear
        self._entries: list[HistoryEntry] = []

        header = tk.Frame(self, background=theme.panel)
        header.pack(fill="x", padx=12, pady=(12, 6))
        self._title = tk.Label(
            header,
            text="TAPE",
            background=theme.panel,
            foreground=theme.text_dim,
            font=(fonts.ui, 10, "bold"),
        )
        self._title.pack(side="left")
        self._clear_chip = Chip(
            header,
            theme,
            "clear",
            command=self.on_clear,
            font_family=fonts.ui,
            width=48,
            height=20,
        )
        self._clear_chip.pack(side="right")

        body = tk.Frame(self, background=theme.panel)
        body.pack(fill="both", expand=True, padx=(12, 4), pady=(0, 12))

        self._text = tk.Text(
            body,
            background=theme.panel,
            foreground=theme.text,
            font=(fonts.mono, 11),
            bd=0,
            highlightthickness=0,
            wrap="none",
            cursor="arrow",
            spacing1=2,
            spacing3=6,
            padx=0,
            pady=0,
        )
        self._scroll = tk.Scrollbar(
            body, command=self._text.yview, width=10,
            troughcolor=theme.panel, background=theme.border,
            bd=0, highlightthickness=0, relief="flat",
            activebackground=theme.text_faint,
        )
        self._text.configure(yscrollcommand=self._scroll.set)
        self._text.pack(side="left", fill="both", expand=True)
        self._scroll.pack(side="right", fill="y")

        self._configure_tags()
        self._text.configure(state="disabled")
        self._text.bind("<MouseWheel>", self._on_wheel)

        self._empty_hint()

    # ------------------------------------------------------------------ #
    # Tags
    # ------------------------------------------------------------------ #

    def _configure_tags(self) -> None:
        self._text.tag_configure(
            "expression", foreground=self.theme.text_dim, font=(self.fonts.mono, 10)
        )
        self._text.tag_configure(
            "result",
            foreground=self.theme.text,
            font=(self.fonts.mono, 14, "bold"),
            justify="right",
        )
        self._text.tag_configure(
            "clock", foreground=self.theme.text_faint, font=(self.fonts.mono, 9)
        )
        self._text.tag_configure(
            "hint", foreground=self.theme.text_faint, font=(self.fonts.ui, 10)
        )
        self._text.tag_configure("hover", background=self.theme.panel_raised)

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _empty_hint(self) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert(
            "end",
            "Nothing yet.\n\nPress Return to evaluate.\n"
            "Click a past result to reuse it.\n",
            "hint",
        )
        self._text.configure(state="disabled")

    def render(self, history: History) -> None:
        self._entries = history.recent()
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")

        if not self._entries:
            self._text.configure(state="disabled")
            self._empty_hint()
            return

        for index, entry in enumerate(self._entries):
            tag = f"entry{index}"
            start = self._text.index("end-1c")
            self._text.insert("end", f"{entry.clock}\n", ("clock",))
            self._text.insert("end", f"{entry.expression}\n", ("expression",))
            self._text.insert("end", f"{entry.formatted}\n\n", ("result",))
            end = self._text.index("end-1c")
            self._text.tag_add(tag, start, end)
            self._bind_entry(tag, entry)

        self._text.configure(state="disabled")
        self._text.see("1.0")

    def _bind_entry(self, tag: str, entry: HistoryEntry) -> None:
        text = self._text
        text.tag_bind(
            tag, "<Button-1>", lambda _event: self.on_recall(entry, False)
        )
        text.tag_bind(
            tag, "<Double-Button-1>", lambda _event: self.on_recall(entry, True)
        )
        text.tag_bind(tag, "<Enter>", lambda _event: self._hover(tag, True))
        text.tag_bind(tag, "<Leave>", lambda _event: self._hover(tag, False))

    def _hover(self, tag: str, hovering: bool) -> None:
        background = self.theme.panel_raised if hovering else self.theme.panel
        self._text.tag_configure(tag, background=background)
        self._text.configure(cursor="hand2" if hovering else "arrow")

    def _on_wheel(self, event: tk.Event) -> str:
        # macOS delivers small deltas; normalise to whole lines either way.
        step = -1 if event.delta > 0 else 1
        self._text.yview_scroll(step, "units")
        return "break"

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.panel)
        self._title.configure(background=theme.panel, foreground=theme.text_dim)
        self._text.configure(background=theme.panel, foreground=theme.text)
        self._scroll.configure(
            troughcolor=theme.panel,
            background=theme.border,
            activebackground=theme.text_faint,
        )
        for child in self.winfo_children():
            if isinstance(child, tk.Frame):
                child.configure(background=theme.panel)
        self._clear_chip.apply_theme(theme)
        self._configure_tags()
