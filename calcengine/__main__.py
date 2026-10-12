"""``python -m calcengine`` - launch the GUI, or evaluate from the shell.

    python -m calcengine                 open the window
    python -m calcengine "2+3*4"         print one result and exit
    python -m calcengine --repl          interactive prompt, no display needed
"""

from __future__ import annotations

import sys

from .core import CalcError, Engine

USAGE = """\
calcengine - an expression calculator

  python -m calcengine                 launch the graphical calculator
  python -m calcengine "sqrt(2)*3"     evaluate one expression and exit
  python -m calcengine --repl          read expressions from stdin
  python -m calcengine --help          show this message
"""


def run_once(expression: str) -> int:
    engine = Engine()
    try:
        print(engine.evaluate(expression).formatted)
        return 0
    except CalcError as error:
        print(f"error: {error}", file=sys.stderr)
        caret = error.caret_line(expression)
        if caret:
            print(f"  {expression}", file=sys.stderr)
            print(f"  {caret}", file=sys.stderr)
        return 1


def run_repl() -> int:
    engine = Engine()
    print("calcengine - type an expression, or 'quit' to leave.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line in {"quit", "exit"}:
            return 0
        if not line:
            continue
        try:
            result = engine.evaluate(line)
        except CalcError as error:
            print(f"  error: {error}")
            caret = error.caret_line(line)
            if caret:
                print(f"  {' ' * 2}{caret}")
            continue
        print(f"  = {result.formatted}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] in ("-h", "--help"):
        print(USAGE)
        return 0
    if args and args[0] == "--repl":
        return run_repl()
    if args:
        return run_once(" ".join(args))

    try:
        from .ui import launch
    except ImportError as error:  # pragma: no cover - tkinter missing
        print(f"Cannot start the GUI: {error}", file=sys.stderr)
        print("Use --repl for the text interface.", file=sys.stderr)
        return 1
    launch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
