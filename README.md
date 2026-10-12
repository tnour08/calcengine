# calcengine

An expression calculator with a hand-written lexer, Pratt parser, arbitrary-precision
evaluator, and a Tk interface drawn on canvases. Pure standard library — no dependencies.

```
python3 -m calcengine                 # launch the window
python3 -m calcengine "sqrt(2)*3"     # evaluate one expression and exit
python3 -m calcengine --repl          # text interface, no display needed
```

## Why it exists

A keypad calculator chains left to right: `2 + 3 × 4` gives `20`. This one parses a real
grammar, so it gives `14`. And because every number is a `decimal.Decimal` rather than a
float, `0.1 + 0.2` is exactly `0.3` — not `0.30000000000000004`.

## Layers

The dependency arrow points one way only. `core` knows nothing about state, `app` knows
nothing about Tk, and Tk appears nowhere outside `ui`. That is what makes everything
below the UI testable without a display.

```
core/   pure evaluation      no imports from app or ui
  ↑
app/    observable state     no imports from ui
  ↑
ui/     Tk presentation      the only place tkinter is touched
```

### core — text in, number out

```
source → lexer.tokenize → [Token] → parser.parse → Node → Evaluator → Decimal → Formatter → str
```

| Module | Role |
| --- | --- |
| `tokens.py` | Token types, including `×÷−²³√` and the `π τ φ` aliases |
| `lexer.py` | Characters to tokens; disambiguates `2e5` (200000) from `2e` (2·e) |
| `parser.py` | Precedence climbing: right-associative `^`, prefix/postfix, implicit `*` |
| `nodes.py` | Frozen AST dataclasses that pretty-print back to re-parseable source |
| `evaluator.py` | Table-driven visitor, depth guard, "did you mean" suggestions |
| `dmath.py` | Decimal trig, logs, roots — written from scratch, `decimal` has none |
| `functions.py` | Decorator-registered function and constant tables (~45 entries) |
| `formatter.py` | AUTO / FIX / SCI / ENG output, correct at any working precision |
| `engine.py` | The façade, plus introspection: tokens, tree, trace, timings |

`dmath` is the interesting part. The `decimal` module ships no transcendental functions,
so `sin` and `cos` are Taylor series over arguments reduced mod 2π, `atan` uses the
repeated-halving identity, and everything computes with guard digits and rounds once on
exit. Results match libm to the last double bit, and raising the precision to 100 digits
actually produces 100 correct digits.

### app — state worth undoing

| Module | Role |
| --- | --- |
| `events.py` | `EventBus` over a `Topic` enum; the UI never polls the model |
| `commands.py` | Every edit is an undoable command |
| `history.py` | Bounded tape of past evaluations, serialisable |
| `memory.py` | `M`, `M1`–`M3` slots with add/subtract |
| `settings.py` | JSON persistence, written atomically, degrades to defaults |
| `model.py` | Ties the above together and publishes one event per user action |

Typing `1234` coalesces into a single undo step; typing `12+34` produces three, because
the operator breaks the run. An evaluated result becomes the new buffer with its digit
grouping stripped, so you can keep building on it.

Settings are saved to a temp file and then `os.replace`d into position, so an interrupted
write cannot leave a half-written config behind. A corrupt file on load is ignored rather
than fatal.

### ui — everything is a canvas

Buttons, the display, and the tape are drawn with `create_polygon(..., smooth=True)`
rather than being Tk widgets, which is what allows rounded corners, glow, and the
ease-out press animation. The caret is positioned by measuring the actual font, so it
lands between the right glyphs in a right-aligned display.

Four themes (`MIDNIGHT`, `NEON`, `SLATE`, `SOLAR`), 82 keys across two pages, a live
preview that evaluates as you type, and an inspector panel that shows the token stream,
the parse tree, and the reduction trace for whatever you just entered.

## Keys worth knowing

| Key | Does |
| --- | --- |
| `Enter` | Evaluate |
| `Escape` | Clear |
| `Cmd+Z` / `Cmd+Shift+Z` | Undo / redo (`Ctrl+Z` / `Ctrl+Y` elsewhere) |
| `←` `→` `Home` `End` | Move the caret |
| `↑` `↓` | Walk back and forth through history |
| `Tab` | Switch keypad page |
| `Cmd/Ctrl+I` | Toggle the inspector |
| `Cmd/Ctrl+H` | Toggle the tape |
| `Cmd/Ctrl+T` | Next theme |
| `Cmd/Ctrl+D` | Cycle angle mode (RAD → DEG → GRAD) |
| `Cmd/Ctrl+N` | Cycle notation (AUTO → FIX → SCI → ENG) |
| `Cmd/Ctrl+G` | Toggle digit grouping |
| `Cmd/Ctrl+P` | Toggle live preview |
| `Cmd/Ctrl+L` | Clear history |

Precision (16 → 28 → 50 → 100 digits) cycles by clicking the status-bar chip, as do
angle mode, notation, theme, and memory.

## Expression syntax

```
name = expr          assignment, right associative:  a = b = 3
a + b   a - b         additive
a * b   a / b   a mod b    multiplicative (mod is floored: -7 mod 3 = 2)
-a  +a  √a            prefix
a ^ b                 power, right associative:  2^3^2 = 512
a!  a%  a²  a³        postfix
f(x, y)   (expr)      calls and grouping
2π   3(4+5)   2sin(1) implicit multiplication
ans                   the previous result
```

## Tests

```
python3 -m unittest discover -s tests -t .
```

125 tests, no display required. Among them: `dmath` compared against `math` across every
function, a round-trip property check that every pretty-printed AST re-parses to the same
value, and regression tests for each bug found during development — `'²'.isdigit()` being
`True` in Python, `(-2)^2` printing as `-2 ^ 2`, and `pi` at 60 digits being formatted in
a 28-digit context.

`tests/smoke_ui.py` builds the real window and tears it down; it needs a display, so it
is not part of discovery.
