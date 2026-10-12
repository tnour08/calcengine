"""Smoke test: build the real window, drive it, tear it down.

Needs a display, so it is deliberately not named ``test_*`` and stays out of
``unittest discover``. Run it from the project root with::

    python3 -m tests.smoke_ui

The window is withdrawn before anything is driven. A mapped window sits on the
live desktop and picks up whatever clicks and keystrokes happen to land on it,
which shows up here as phantom keypresses in the expression buffer.
"""

import os
import tempfile

# Point settings at a throwaway directory before anything reads it: the run
# cycles the theme and precision and then saves on close, which would otherwise
# overwrite the real config.
os.environ["CALCENGINE_HOME"] = tempfile.mkdtemp(prefix="calcengine-smoke-")

from calcengine.ui.window import CalculatorWindow  # noqa: E402


def main() -> None:
    window = CalculatorWindow()
    window.withdraw()
    window.update_idletasks()
    window.update()
    print("window built  :", window.winfo_reqwidth(), "x", window.winfo_reqheight())
    print("theme         :", window.theme.name)
    print("fonts         :", window.fonts.mono, "/", window.fonts.ui)
    print("keypad buttons:", len(window.keypad._buttons))

    for char in "12+5*2":
        window.model.insert(char)
    window.update()
    print("expr / preview:", repr(window.display._expression),
          repr(window.display._preview))

    window.model.evaluate()
    window.update()
    print("after evaluate:", repr(window.display._expression))

    window.model.toggle_inspector()
    window.model.set_expression("2+3*4^2")
    window.model.evaluate()
    window.update()
    print("inspector      :", window.model.show_inspector)
    print("inspector text :", window.inspector._text.get("1.0", "2.end").strip())

    window.model.set_expression("1/0")
    window.model.evaluate()
    window.update()
    print("error state    :", window.display._error)

    for _ in range(4):
        window._cycle_theme()
        window.update()
    print("theme cycled   :", window.theme.name)

    window.keypad.cycle_page()
    window.update()
    print("keypad page    :", window.keypad.active_page)

    window.model.toggle_tape()
    window.update()
    print("tape visible   :", window.model.show_tape)

    window._cycle_precision()
    window.update()
    print("precision      :", window.model.engine.precision)

    window.model.memory_store()
    window.update()
    print("memory         :", dict(window.model.memory.items()))

    # simulate a keyboard-driven session
    window.model.clear()
    for char in "9*9":
        window.model.insert(char)
        window.keypad.flash_key(char)
    window.update()
    window.model.evaluate()
    window.update()
    print("keyboard path  :", window.display._expression)

    window._on_close()
    print("OK - closed cleanly")


if __name__ == "__main__":
    main()
