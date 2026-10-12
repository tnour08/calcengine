"""Colour palettes, font selection and small colour-maths helpers."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable


# --------------------------------------------------------------------------- #
# Colour maths
# --------------------------------------------------------------------------- #


def hex_to_rgb(colour: str) -> tuple[int, int, int]:
    text = colour.lstrip("#")
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def rgb_to_hex(rgb: Iterable[float]) -> str:
    red, green, blue = (max(0, min(255, int(round(channel)))) for channel in rgb)
    return f"#{red:02x}{green:02x}{blue:02x}"


def blend(start: str, end: str, amount: float) -> str:
    """Linear interpolation between two colours; ``amount`` runs 0 -> 1."""
    ratio = max(0.0, min(1.0, amount))
    first = hex_to_rgb(start)
    second = hex_to_rgb(end)
    return rgb_to_hex(
        first[channel] + (second[channel] - first[channel]) * ratio
        for channel in range(3)
    )


def lighten(colour: str, amount: float = 0.2) -> str:
    return blend(colour, "#ffffff", amount)


def darken(colour: str, amount: float = 0.2) -> str:
    return blend(colour, "#000000", amount)


def readable_on(background: str, light: str = "#ffffff", dark: str = "#10131a") -> str:
    """Pick whichever of ``light``/``dark`` contrasts better."""
    red, green, blue = hex_to_rgb(background)
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return dark if luminance > 0.55 else light


# --------------------------------------------------------------------------- #
# Palette
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Theme:
    """One complete colour scheme."""

    name: str
    label: str

    window: str
    panel: str
    panel_raised: str
    display: str

    text: str
    text_dim: str
    text_faint: str

    accent: str
    accent_soft: str

    digit: str
    digit_text: str
    operator: str
    operator_text: str
    function: str
    function_text: str
    utility: str
    utility_text: str

    danger: str
    success: str
    border: str
    glow: str

    def button_colours(self, kind: str) -> tuple[str, str]:
        """``(background, foreground)`` for a keypad button ``kind``."""
        table = {
            "digit": (self.digit, self.digit_text),
            "operator": (self.operator, self.operator_text),
            "function": (self.function, self.function_text),
            "utility": (self.utility, self.utility_text),
            "accent": (self.accent, readable_on(self.accent)),
            "danger": (self.danger, readable_on(self.danger)),
        }
        return table.get(kind, (self.digit, self.digit_text))

    def with_accent(self, accent: str) -> "Theme":
        return replace(self, accent=accent, accent_soft=darken(accent, 0.45))


MIDNIGHT = Theme(
    name="midnight",
    label="Midnight",
    window="#0b0e14",
    panel="#11151f",
    panel_raised="#171c28",
    display="#0d1017",
    text="#e8edf7",
    text_dim="#8a94ab",
    text_faint="#4c5568",
    accent="#38bdf8",
    accent_soft="#1e3a4c",
    digit="#1c2230",
    digit_text="#e8edf7",
    operator="#1f4e63",
    operator_text="#d6f3ff",
    function="#191e2b",
    function_text="#9fb3c8",
    utility="#262c3b",
    utility_text="#cfd7e6",
    danger="#f87171",
    success="#4ade80",
    border="#1e2533",
    glow="#38bdf8",
)

NEON = Theme(
    name="neon",
    label="Neon",
    window="#07070b",
    panel="#0d0d14",
    panel_raised="#15151f",
    display="#09090f",
    text="#f5f3ff",
    text_dim="#a79fd1",
    text_faint="#5b5480",
    accent="#f0abfc",
    accent_soft="#3b1d49",
    digit="#17172a",
    digit_text="#f5f3ff",
    operator="#4c1d6b",
    operator_text="#fbe7ff",
    function="#121221",
    function_text="#9d93d4",
    utility="#241f3d",
    utility_text="#ded9ff",
    danger="#fb7185",
    success="#34d399",
    border="#221d38",
    glow="#f0abfc",
)

SOLAR = Theme(
    name="solar",
    label="Solar",
    window="#f4ece0",
    panel="#ebe0cf",
    panel_raised="#fdf8f0",
    display="#fffaf1",
    text="#3a2f22",
    text_dim="#7c6a54",
    text_faint="#a89478",
    accent="#c2601c",
    accent_soft="#e9c9a8",
    digit="#fdf8f0",
    digit_text="#3a2f22",
    operator="#e8a46a",
    operator_text="#3a2317",
    function="#e3d6c2",
    function_text="#5c4a35",
    utility="#d8c7ad",
    utility_text="#3a2f22",
    danger="#c0392b",
    success="#4f772d",
    border="#d6c6ae",
    glow="#c2601c",
)

SLATE = Theme(
    name="slate",
    label="Slate",
    window="#16181d",
    panel="#1d2026",
    panel_raised="#24282f",
    display="#14161a",
    text="#e6e8ec",
    text_dim="#9aa0ac",
    text_faint="#5e6470",
    accent="#7dd3a8",
    accent_soft="#234437",
    digit="#272b33",
    digit_text="#e6e8ec",
    operator="#3a4a44",
    operator_text="#dff5ea",
    function="#20242b",
    function_text="#a7aeba",
    utility="#30353e",
    utility_text="#dadee5",
    danger="#e8836f",
    success="#7dd3a8",
    border="#2a2f37",
    glow="#7dd3a8",
)

THEMES: dict[str, Theme] = {
    theme.name: theme for theme in (MIDNIGHT, NEON, SLATE, SOLAR)
}

DEFAULT_THEME = MIDNIGHT.name


def get_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES[DEFAULT_THEME])


def theme_order() -> list[str]:
    return list(THEMES)


def next_theme(name: str) -> str:
    order = theme_order()
    if name not in order:
        return DEFAULT_THEME
    return order[(order.index(name) + 1) % len(order)]


# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #

#: Preference order; the first family actually installed wins.
DISPLAY_FONT_STACK = ("SF Mono", "Menlo", "DejaVu Sans Mono", "Consolas", "Courier")
UI_FONT_STACK = ("SF Pro Text", "Helvetica Neue", "Segoe UI", "DejaVu Sans", "Helvetica")


def pick_family(stack: Iterable[str], available: Iterable[str]) -> str:
    """First family in ``stack`` that exists in ``available``."""
    installed = {name.lower() for name in available}
    for family in stack:
        if family.lower() in installed:
            return family
    return "TkDefaultFont"


@dataclass(frozen=True)
class FontSet:
    """Resolved font families, shared by every widget."""

    mono: str
    ui: str

    @classmethod
    def resolve(cls, available: Iterable[str]) -> "FontSet":
        families = list(available)
        return cls(
            mono=pick_family(DISPLAY_FONT_STACK, families),
            ui=pick_family(UI_FONT_STACK, families),
        )
