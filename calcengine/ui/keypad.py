"""The keypad: a data-driven grid of :class:`~.widgets.GlowButton` keys.

Layouts are declarative, so adding a key is a one-line change and the keyboard
shortcut table, the tooltips and the flash-on-keypress animation all follow
automatically.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from typing import Callable

from .theme import FontSet, Theme
from .widgets import Chip, GlowButton, Tooltip

#: ``("insert", text)`` types text; ``("call", method)`` invokes the model.
Action = tuple


@dataclass(frozen=True)
class KeySpec:
    """One key in a layout."""

    label: str
    kind: str = "digit"
    action: Action = ("insert", "")
    span: int = 1
    sublabel: str = ""
    tooltip: str = ""
    #: Keyboard characters that should trigger (and flash) this key.
    keys: tuple = field(default_factory=tuple)


def _insert(text: str) -> Action:
    return ("insert", text)


def _call(method: str) -> Action:
    return ("call", method)


def _fn(name: str, tooltip: str) -> KeySpec:
    """A function key that types ``name(`` and leaves the cursor inside."""
    return KeySpec(name, "function", _insert(f"{name}("), tooltip=tooltip)


SCIENTIFIC_PAGE: list[list[KeySpec]] = [
    [
        KeySpec("AC", "danger", _call("clear"), sublabel="esc",
                tooltip="Clear everything"),
        KeySpec("\u232b", "utility", _call("backspace"), sublabel="del",
                tooltip="Delete the character before the cursor"),
        KeySpec("(", "utility", _insert("("), keys=("(",)),
        KeySpec(")", "utility", _insert(")"), keys=(")",)),
        KeySpec("mod", "utility", _insert(" mod "),
                tooltip="Remainder after floored division"),
        KeySpec("ans", "utility", _insert("ans"),
                tooltip="The previous result"),
    ],
    [
        _fn("sin", "Sine of an angle"),
        _fn("cos", "Cosine of an angle"),
        _fn("tan", "Tangent of an angle"),
        KeySpec("\u03c0", "function", _insert("pi"), tooltip="3.14159..."),
        KeySpec("e", "function", _insert("e"), tooltip="2.71828..."),
        KeySpec("x\u02b8", "operator", _insert("^"), sublabel="^",
                tooltip="Raise to a power", keys=("^",)),
    ],
    [
        _fn("ln", "Natural logarithm"),
        _fn("log", "Base-10 logarithm, or log(x, base)"),
        KeySpec("\u221a", "function", _insert("\u221a"),
                tooltip="Square root"),
        KeySpec("x\u00b2", "function", _insert("\u00b2"),
                tooltip="Square the value to the left"),
        KeySpec("x\u00b3", "function", _insert("\u00b3"),
                tooltip="Cube the value to the left"),
        KeySpec("n!", "function", _insert("!"), tooltip="Factorial"),
    ],
    [
        KeySpec("7", "digit", _insert("7"), keys=("7",)),
        KeySpec("8", "digit", _insert("8"), keys=("8",)),
        KeySpec("9", "digit", _insert("9"), keys=("9",)),
        KeySpec("\u00f7", "operator", _insert("/"), sublabel="/", keys=("/",)),
        KeySpec("MC", "utility", _call("memory_clear"), tooltip="Clear memory"),
        KeySpec("MR", "utility", _call("memory_recall"), tooltip="Recall memory"),
    ],
    [
        KeySpec("4", "digit", _insert("4"), keys=("4",)),
        KeySpec("5", "digit", _insert("5"), keys=("5",)),
        KeySpec("6", "digit", _insert("6"), keys=("6",)),
        KeySpec("\u00d7", "operator", _insert("*"), sublabel="*", keys=("*",)),
        KeySpec("M+", "utility", _call("memory_add"), tooltip="Add to memory"),
        KeySpec("M\u2212", "utility", _call("memory_subtract"),
                tooltip="Subtract from memory"),
    ],
    [
        KeySpec("1", "digit", _insert("1"), keys=("1",)),
        KeySpec("2", "digit", _insert("2"), keys=("2",)),
        KeySpec("3", "digit", _insert("3"), keys=("3",)),
        KeySpec("\u2212", "operator", _insert("-"), sublabel="-", keys=("-",)),
        KeySpec("%", "utility", _insert("%"), tooltip="Divide by one hundred"),
        KeySpec("\u00b1", "utility", _call("toggle_sign"),
                tooltip="Flip the sign of the number at the cursor"),
    ],
    [
        KeySpec("0", "digit", _insert("0"), keys=("0",)),
        KeySpec(".", "digit", _insert("."), keys=(".",)),
        KeySpec(",", "digit", _insert(", "), tooltip="Separate function arguments"),
        KeySpec("+", "operator", _insert("+"), keys=("+",)),
        KeySpec("=", "accent", _call("evaluate"), span=2, sublabel="return"),
    ],
]

FUNCTION_PAGE: list[list[KeySpec]] = [
    [
        _fn("asin", "Inverse sine"),
        _fn("acos", "Inverse cosine"),
        _fn("atan", "Inverse tangent"),
        _fn("atan2", "atan2(y, x), quadrant aware"),
        _fn("sinh", "Hyperbolic sine"),
        _fn("cosh", "Hyperbolic cosine"),
    ],
    [
        _fn("tanh", "Hyperbolic tangent"),
        _fn("abs", "Absolute value"),
        _fn("sign", "-1, 0 or 1"),
        _fn("floor", "Round down"),
        _fn("ceil", "Round up"),
        _fn("round", "round(x) or round(x, places)"),
    ],
    [
        _fn("min", "Smallest argument"),
        _fn("max", "Largest argument"),
        _fn("sum", "Add every argument"),
        _fn("avg", "Arithmetic mean"),
        _fn("median", "Middle value"),
        _fn("stdev", "Standard deviation"),
    ],
    [
        _fn("gcd", "Greatest common divisor"),
        _fn("lcm", "Least common multiple"),
        _fn("hypot", "Euclidean norm"),
        _fn("clamp", "clamp(x, low, high)"),
        _fn("if", "if(condition, then, else)"),
        _fn("rand", "rand(), rand(n) or rand(a, b)"),
    ],
    [
        _fn("exp", "e to the power of x"),
        _fn("pow", "pow(base, exponent)"),
        _fn("root", "root(x, n), the n-th root"),
        _fn("cbrt", "Cube root"),
        _fn("log2", "Base-2 logarithm"),
        _fn("log10", "Base-10 logarithm"),
    ],
    [
        _fn("deg", "Radians to degrees"),
        _fn("rad", "Degrees to radians"),
        _fn("trunc", "Discard the fraction"),
        _fn("fact", "Factorial"),
        KeySpec("\u03c6", "function", _insert("phi"), tooltip="Golden ratio"),
        KeySpec("\u03c4", "function", _insert("tau"), tooltip="Two pi"),
    ],
    [
        KeySpec("AC", "danger", _call("clear"), sublabel="esc"),
        KeySpec("\u232b", "utility", _call("backspace"), sublabel="del"),
        KeySpec("(", "utility", _insert("(")),
        KeySpec(")", "utility", _insert(")")),
        KeySpec("=", "accent", _call("evaluate"), span=2, sublabel="return"),
    ],
]

PAGES: dict[str, list[list[KeySpec]]] = {
    "SCI": SCIENTIFIC_PAGE,
    "FN": FUNCTION_PAGE,
}


class Keypad(tk.Frame):
    """Builds every page, shows one at a time, and animates key presses."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        fonts: FontSet,
        dispatch: Callable[[Action], None],
        tooltip: Tooltip | None = None,
    ):
        super().__init__(parent, background=theme.panel)
        self.theme = theme
        self.fonts = fonts
        self.dispatch = dispatch
        self.tooltip = tooltip

        self._buttons: list[GlowButton] = []
        self._by_key: dict[str, GlowButton] = {}
        self._by_label: dict[str, GlowButton] = {}
        self._pages: dict[str, tk.Frame] = {}
        self._tabs: dict[str, Chip] = {}
        self.active_page = "SCI"

        self._tab_bar = tk.Frame(self, background=theme.panel)
        self._tab_bar.pack(fill="x", padx=10, pady=(6, 2))
        for name in PAGES:
            chip = Chip(
                self._tab_bar,
                theme,
                name,
                command=lambda page=name: self.show_page(page),
                font_family=fonts.ui,
                width=54,
                height=22,
                tooltip=f"Show the {name} keys",
            )
            chip.pack(side="left", padx=(0, 6))
            self._tabs[name] = chip

        self._page_host = tk.Frame(self, background=theme.panel)
        self._page_host.pack(fill="both", expand=True)

        for name, layout in PAGES.items():
            self._pages[name] = self._build_page(layout)

        self.show_page(self.active_page)

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #

    def _build_page(self, layout: list[list[KeySpec]]) -> tk.Frame:
        page = tk.Frame(self._page_host, background=self.theme.panel)
        columns = max(
            sum(spec.span for spec in row) for row in layout
        )
        for column in range(columns):
            page.grid_columnconfigure(column, weight=1, uniform="keys")
        for row in range(len(layout)):
            page.grid_rowconfigure(row, weight=1, uniform="rows")

        for row_index, row in enumerate(layout):
            column_index = 0
            for spec in row:
                button = GlowButton(
                    page,
                    self.theme,
                    spec.label,
                    command=lambda action=spec.action: self.dispatch(action),
                    kind=spec.kind,
                    sublabel=spec.sublabel,
                    font_family=self.fonts.ui,
                    font_size=16 if len(spec.label) <= 3 else 13,
                    tooltip=spec.tooltip,
                )
                button.grid(
                    row=row_index,
                    column=column_index,
                    columnspan=spec.span,
                    sticky="nsew",
                    padx=3,
                    pady=3,
                )
                self._buttons.append(button)
                self._by_label.setdefault(spec.label, button)
                for key in spec.keys:
                    self._by_key.setdefault(key, button)
                if self.tooltip is not None and spec.tooltip:
                    self.tooltip.attach(button, spec.tooltip)
                column_index += spec.span
        return page

    # ------------------------------------------------------------------ #
    # Pages
    # ------------------------------------------------------------------ #

    def show_page(self, name: str) -> None:
        if name not in self._pages:
            return
        for page in self._pages.values():
            page.pack_forget()
        self._pages[name].pack(fill="both", expand=True, padx=7, pady=(2, 8))
        self.active_page = name
        for tab_name, chip in self._tabs.items():
            chip.set_active(tab_name == name)

    def cycle_page(self) -> None:
        names = list(PAGES)
        self.show_page(names[(names.index(self.active_page) + 1) % len(names)])

    # ------------------------------------------------------------------ #
    # Feedback
    # ------------------------------------------------------------------ #

    def flash_key(self, character: str) -> None:
        button = self._by_key.get(character)
        if button is not None:
            button.flash()

    def flash_label(self, label: str) -> None:
        button = self._by_label.get(label)
        if button is not None:
            button.flash()

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.panel)
        self._tab_bar.configure(background=theme.panel)
        self._page_host.configure(background=theme.panel)
        for page in self._pages.values():
            page.configure(background=theme.panel)
        for button in self._buttons:
            button.apply_theme(theme)
        for chip in self._tabs.values():
            chip.apply_theme(theme)
        self.show_page(self.active_page)
