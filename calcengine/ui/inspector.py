"""The inspector: shows how an expression was actually understood.

Four sections, all derived from one :class:`~calcengine.core.engine.EvalResult`:
the token stream, the parse tree, the reduction trace, and timing/stats. It is
the panel that makes operator precedence visible instead of surprising.
"""

from __future__ import annotations

import tkinter as tk

from ..core.engine import EvalResult
from ..core.functions import REGISTRY
from ..core.nodes import render_tree
from .theme import FontSet, Theme


class InspectorPanel(tk.Frame):
    """A read-only, syntax-tinted dump of the last parse and evaluation."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        fonts: FontSet,
        width: int = 320,
    ):
        super().__init__(parent, background=theme.panel, width=width)
        self.theme = theme
        self.fonts = fonts

        self._title = tk.Label(
            self,
            text="INSPECTOR",
            background=theme.panel,
            foreground=theme.text_dim,
            font=(fonts.ui, 10, "bold"),
        )
        self._title.pack(anchor="w", padx=12, pady=(12, 6))

        body = tk.Frame(self, background=theme.panel)
        body.pack(fill="both", expand=True, padx=(12, 4), pady=(0, 12))

        self._text = tk.Text(
            body,
            background=theme.panel,
            foreground=theme.text,
            font=(fonts.mono, 10),
            bd=0,
            highlightthickness=0,
            wrap="none",
            cursor="arrow",
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
        self._text.bind("<MouseWheel>", self._on_wheel)
        self.show_welcome()

    # ------------------------------------------------------------------ #
    # Tags
    # ------------------------------------------------------------------ #

    def _configure_tags(self) -> None:
        text = self._text
        text.tag_configure(
            "section",
            foreground=self.theme.accent,
            font=(self.fonts.ui, 9, "bold"),
            spacing1=8,
            spacing3=3,
        )
        text.tag_configure("tree", foreground=self.theme.text)
        text.tag_configure("dim", foreground=self.theme.text_faint)
        text.tag_configure("value", foreground=self.theme.success)
        text.tag_configure("token", foreground=self.theme.text_dim)
        text.tag_configure("error", foreground=self.theme.danger)

    # ------------------------------------------------------------------ #
    # Content
    # ------------------------------------------------------------------ #

    def _write(self, lines: list[tuple[str, str]]) -> None:
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        for content, tag in lines:
            self._text.insert("end", content + "\n", (tag,))
        self._text.configure(state="disabled")
        self._text.see("1.0")

    def show_welcome(self) -> None:
        total = len(REGISTRY.function_names)
        lines: list[tuple[str, str]] = [
            ("WHAT THIS SHOWS", "section"),
            ("Evaluate something and this panel", "dim"),
            ("breaks down how it was parsed:", "dim"),
            ("tokens, the parse tree, and each", "dim"),
            ("reduction step in order.", "dim"),
            ("", "dim"),
            ("AVAILABLE NAMES", "section"),
        ]
        for category, specs in REGISTRY.by_category().items():
            lines.append((category.upper(), "dim"))
            names = ", ".join(spec.name for spec in specs)
            for chunk in _wrap(names, 34):
                lines.append(("  " + chunk, "token"))
        lines.append(("", "dim"))
        lines.append((f"{total} callable names registered.", "dim"))
        self._write(lines)

    def show_result(self, result: EvalResult) -> None:
        lines: list[tuple[str, str]] = [("SOURCE", "section"), (result.source, "tree")]

        if result.normalized != result.source:
            lines += [("AS PARSED", "section"), (result.normalized, "tree")]

        lines.append(("TOKENS", "section"))
        for token in result.tokens:
            if token.type.name == "EOF":
                continue
            lines.append((f"  {token.type.name:<9} {token.text}", "token"))

        lines.append(("PARSE TREE", "section"))
        for line in render_tree(result.tree):
            lines.append(("  " + line, "tree"))

        if result.trace:
            lines.append(("REDUCTION", "section"))
            for step in result.trace:
                lines.append((f"  {step.expression}", "tree"))
                lines.append((f"    = {step.value}", "value"))

        lines.append(("RESULT", "section"))
        lines.append((f"  {result.formatted}", "value"))
        lines.append((f"  exact: {result.value}", "dim"))

        lines.append(("STATS", "section"))
        lines.append((f"  nodes      {result.node_count}", "dim"))
        lines.append((f"  depth      {result.tree.depth}", "dim"))
        lines.append((f"  tokens     {len(result.tokens) - 1}", "dim"))
        lines.append((f"  elapsed    {result.elapsed_ms:.3f} ms", "dim"))
        if result.assignments:
            lines.append(("BOUND", "section"))
            for name, value in result.assignments.items():
                lines.append((f"  {name} = {value}", "value"))

        self._write(lines)

    def show_error(self, message: str, source: str, position: int | None,
                   length: int) -> None:
        lines: list[tuple[str, str]] = [
            ("ERROR", "section"),
            ("  " + message, "error"),
        ]
        if source:
            lines.append(("SOURCE", "section"))
            lines.append(("  " + source, "tree"))
            if position is not None:
                lines.append(("  " + " " * position + "^" * max(1, length), "error"))
        self._write(lines)

    def _on_wheel(self, event: tk.Event) -> str:
        self._text.yview_scroll(-1 if event.delta > 0 else 1, "units")
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
        self._configure_tags()


def _wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap, used for the comma-separated name lists."""
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
