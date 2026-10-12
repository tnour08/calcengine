"""Hand-drawn Tk widgets.

Tk's stock buttons cannot do rounded corners, so every key here is a small
:class:`tkinter.Canvas` with a smoothed polygon behind the label. That also
gives us somewhere to run hover and press animations, which are driven by
``after`` callbacks interpolating between two palette colours.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from .theme import Theme, blend, lighten


def rounded_polygon(
    x1: float, y1: float, x2: float, y2: float, radius: float
) -> list[float]:
    """Point list that, drawn with ``smooth=True``, yields a rounded rect."""
    radius = max(0.0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]


class GlowButton(tk.Canvas):
    """A rounded, animated key.

    ``kind`` selects the palette entry (digit/operator/function/utility/
    accent/danger). ``sublabel`` renders a small secondary caption, used for
    keyboard hints.
    """

    ANIMATION_STEPS = 6
    ANIMATION_INTERVAL_MS = 16

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        label: str,
        command: Callable[[], None],
        kind: str = "digit",
        sublabel: str = "",
        font_family: str = "Helvetica",
        font_size: int = 17,
        corner_radius: int = 12,
        width: int = 64,
        height: int = 52,
        tooltip: str = "",
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            background=theme.panel,
        )
        self.theme = theme
        self.label = label
        self.kind = kind
        self.sublabel = sublabel
        self.command = command
        self.font_family = font_family
        self.font_size = font_size
        self.corner_radius = corner_radius
        self.tooltip = tooltip

        self._hovering = False
        self._pressed = False
        self._animation: str | None = None
        self._animation_step = 0
        self._animation_target = 0.0
        self._animation_value = 0.0
        self._enabled = True

        self._shape = self.create_polygon(
            rounded_polygon(1, 1, width - 1, height - 1, corner_radius),
            smooth=True,
            splinesteps=16,
            fill=theme.button_colours(kind)[0],
            outline="",
        )
        self._text = self.create_text(
            width / 2,
            height / 2 if not sublabel else height / 2 - 5,
            text=label,
            fill=theme.button_colours(kind)[1],
            font=(font_family, font_size),
        )
        self._sub = self.create_text(
            width / 2,
            height - 12,
            text=sublabel,
            fill=theme.text_faint,
            font=(font_family, max(7, font_size - 9)),
        )

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_configure)

    # ------------------------------------------------------------------ #
    # Geometry
    # ------------------------------------------------------------------ #

    def _on_configure(self, event: tk.Event) -> None:
        width, height = event.width, event.height
        if width <= 2 or height <= 2:
            return
        self.coords(
            self._shape,
            *rounded_polygon(1, 1, width - 1, height - 1, self.corner_radius),
        )
        self.coords(
            self._text, width / 2, height / 2 if not self.sublabel else height / 2 - 5
        )
        self.coords(self._sub, width / 2, height - 12)

    # ------------------------------------------------------------------ #
    # Interaction
    # ------------------------------------------------------------------ #

    def _on_enter(self, _event: tk.Event | None = None) -> None:
        self._hovering = True
        if self._enabled:
            self._animate_to(0.35)

    def _on_leave(self, _event: tk.Event | None = None) -> None:
        self._hovering = False
        self._pressed = False
        self._animate_to(0.0)

    def _on_press(self, _event: tk.Event | None = None) -> None:
        if not self._enabled:
            return
        self._pressed = True
        self._animate_to(1.0, immediate=True)

    def _on_release(self, _event: tk.Event | None = None) -> None:
        if not self._enabled or not self._pressed:
            return
        self._pressed = False
        self._animate_to(0.35 if self._hovering else 0.0)
        self.command()

    def flash(self) -> None:
        """Pulse the key, so a keyboard press looks like a click."""
        if not self._enabled:
            return
        self._animate_to(1.0, immediate=True)
        self.after(90, lambda: self._animate_to(0.35 if self._hovering else 0.0))

    def set_enabled(self, enabled: bool) -> None:
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self._animation_value = 0.0
        self._repaint(0.0)

    # ------------------------------------------------------------------ #
    # Animation
    # ------------------------------------------------------------------ #

    def _animate_to(self, target: float, immediate: bool = False) -> None:
        self._animation_target = target
        if self._animation is not None:
            self.after_cancel(self._animation)
            self._animation = None
        if immediate:
            self._animation_value = target
            self._repaint(target)
            return
        self._animation_step = 0
        self._tick()

    def _tick(self) -> None:
        self._animation_step += 1
        progress = self._animation_step / self.ANIMATION_STEPS
        # Ease-out so the highlight settles rather than stopping dead.
        eased = 1 - (1 - progress) ** 3
        value = self._animation_value + (
            self._animation_target - self._animation_value
        ) * eased
        self._repaint(value)
        if self._animation_step < self.ANIMATION_STEPS:
            self._animation = self.after(self.ANIMATION_INTERVAL_MS, self._tick)
        else:
            self._animation_value = self._animation_target
            self._animation = None

    def _repaint(self, intensity: float) -> None:
        background, foreground = self.theme.button_colours(self.kind)
        if not self._enabled:
            self.itemconfigure(self._shape, fill=blend(background, self.theme.panel, 0.6))
            self.itemconfigure(self._text, fill=self.theme.text_faint)
            self.itemconfigure(self._sub, text=self.sublabel, fill=self.theme.text_faint)
            return

        highlight = blend(background, self.theme.glow, intensity * 0.55)
        self.itemconfigure(self._shape, fill=highlight)
        self.itemconfigure(
            self._text, fill=lighten(foreground, intensity * 0.25)
        )
        self.itemconfigure(self._sub, text=self.sublabel, fill=self.theme.text_faint)

    # ------------------------------------------------------------------ #
    # Theming
    # ------------------------------------------------------------------ #

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.panel)
        self._repaint(self._animation_value if self._enabled else 0.0)


class Chip(tk.Canvas):
    """A small rounded status pill; click to cycle the setting it represents."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        text: str,
        command: Callable[[], None] | None = None,
        font_family: str = "Helvetica",
        font_size: int = 10,
        width: int = 64,
        height: int = 22,
        tooltip: str = "",
    ):
        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            background=theme.panel,
        )
        self.theme = theme
        self.command = command
        self.tooltip = tooltip
        self._active = False
        self.font_family = font_family
        self.font_size = font_size

        self._shape = self.create_polygon(
            rounded_polygon(1, 1, width - 1, height - 1, height / 2),
            smooth=True,
            splinesteps=12,
            fill=theme.panel_raised,
            outline="",
        )
        self._text = self.create_text(
            width / 2,
            height / 2,
            text=text,
            fill=theme.text_dim,
            font=(font_family, font_size, "bold"),
        )
        self.bind("<Configure>", self._on_configure)
        if command is not None:
            self.bind("<Button-1>", lambda _event: command())
            self.bind("<Enter>", lambda _event: self._set_hover(True))
            self.bind("<Leave>", lambda _event: self._set_hover(False))
            self.configure(cursor="hand2")

    def _on_configure(self, event: tk.Event) -> None:
        if event.width <= 2 or event.height <= 2:
            return
        self.coords(
            self._shape,
            *rounded_polygon(1, 1, event.width - 1, event.height - 1, event.height / 2),
        )
        self.coords(self._text, event.width / 2, event.height / 2)

    def _set_hover(self, hovering: bool) -> None:
        base = self.theme.accent_soft if self._active else self.theme.panel_raised
        fill = lighten(base, 0.18) if hovering else base
        self.itemconfigure(self._shape, fill=fill)

    def set_text(self, text: str) -> None:
        self.itemconfigure(self._text, text=text)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.itemconfigure(
            self._shape,
            fill=self.theme.accent_soft if active else self.theme.panel_raised,
        )
        self.itemconfigure(
            self._text, fill=self.theme.accent if active else self.theme.text_dim
        )

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.configure(background=theme.panel)
        self.set_active(self._active)


class Tooltip:
    """A single reusable hover tooltip, shared across many widgets."""

    def __init__(self, root: tk.Misc, theme: Theme, font_family: str = "Helvetica"):
        self.root = root
        self.theme = theme
        self.font_family = font_family
        self._window: tk.Toplevel | None = None
        self._pending: str | None = None

    def attach(self, widget: tk.Widget, text: str) -> None:
        if not text:
            return
        widget.bind("<Enter>", lambda _e: self._schedule(widget, text), add="+")
        widget.bind("<Leave>", lambda _e: self.hide(), add="+")
        widget.bind("<ButtonPress>", lambda _e: self.hide(), add="+")

    def _schedule(self, widget: tk.Widget, text: str) -> None:
        self.hide()
        self._pending = self.root.after(550, lambda: self._show(widget, text))

    def _show(self, widget: tk.Widget, text: str) -> None:
        self._pending = None
        try:
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() + 6
        except tk.TclError:  # pragma: no cover - widget died mid-hover
            return
        window = tk.Toplevel(self.root)
        window.wm_overrideredirect(True)
        window.configure(background=self.theme.border)
        label = tk.Label(
            window,
            text=text,
            background=self.theme.panel_raised,
            foreground=self.theme.text,
            font=(self.font_family, 10),
            padx=8,
            pady=4,
            bd=0,
        )
        label.pack(padx=1, pady=1)
        window.update_idletasks()
        window.wm_geometry(f"+{x - window.winfo_width() // 2}+{y}")
        self._window = window

    def hide(self) -> None:
        if self._pending is not None:
            self.root.after_cancel(self._pending)
            self._pending = None
        if self._window is not None:
            self._window.destroy()
            self._window = None

    def apply_theme(self, theme: Theme) -> None:
        self.theme = theme
        self.hide()
