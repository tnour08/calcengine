"""The function and constant registry.

Functions are registered through a decorator so the keypad, the autocomplete
hints and the help panel can all be generated from one list instead of being
hand-maintained in three places.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Callable, Iterable

from . import dmath
from .context import EvalContext
from .errors import ArityError, DomainError

#: Sentinel arity meaning "one or more arguments".
VARIADIC = -1


@dataclass(frozen=True)
class FunctionSpec:
    """Metadata plus implementation for one callable name."""

    name: str
    arity: int | tuple[int, int]
    impl: Callable[..., Decimal]
    doc: str
    category: str
    needs_context: bool = False

    def arity_text(self) -> str:
        if self.arity == VARIADIC:
            return "1+"
        if isinstance(self.arity, tuple):
            return f"{self.arity[0]}-{self.arity[1]}"
        return str(self.arity)

    def accepts(self, count: int) -> bool:
        if self.arity == VARIADIC:
            return count >= 1
        if isinstance(self.arity, tuple):
            return self.arity[0] <= count <= self.arity[1]
        return count == self.arity

    def check(self, count: int) -> None:
        if not self.accepts(count):
            raise ArityError(
                f"{self.name}() takes {self.arity_text()} argument(s), "
                f"got {count}."
            )

    def __call__(self, ctx: EvalContext, args: list[Decimal]) -> Decimal:
        self.check(len(args))
        if self.needs_context:
            return self.impl(ctx, *args)
        return self.impl(*args)


class Registry:
    """A name -> :class:`FunctionSpec` map with constants alongside."""

    def __init__(self) -> None:
        self._functions: dict[str, FunctionSpec] = {}
        self._constants: dict[str, Callable[[], Decimal]] = {}
        self._constant_docs: dict[str, str] = {}

    # -- registration ------------------------------------------------------- #

    def function(
        self,
        name: str,
        arity: int | tuple[int, int],
        doc: str,
        category: str = "general",
        needs_context: bool = False,
        aliases: Iterable[str] = (),
    ):
        """Decorator registering ``name`` (and any ``aliases``)."""

        def decorator(func: Callable[..., Decimal]) -> Callable[..., Decimal]:
            spec = FunctionSpec(
                name=name,
                arity=arity,
                impl=func,
                doc=doc,
                category=category,
                needs_context=needs_context,
            )
            self._functions[name] = spec
            for alias in aliases:
                self._functions[alias] = spec
            return func

        return decorator

    def constant(self, name: str, doc: str):
        def decorator(func: Callable[[], Decimal]) -> Callable[[], Decimal]:
            self._constants[name] = func
            self._constant_docs[name] = doc
            return func

        return decorator

    # -- lookup ------------------------------------------------------------- #

    def get_function(self, name: str) -> FunctionSpec | None:
        return self._functions.get(name)

    def get_constant(self, name: str) -> Decimal | None:
        producer = self._constants.get(name)
        return producer() if producer else None

    def has_constant(self, name: str) -> bool:
        return name in self._constants

    @property
    def function_names(self) -> list[str]:
        return sorted(self._functions)

    @property
    def constant_names(self) -> list[str]:
        return sorted(self._constants)

    @property
    def all_names(self) -> list[str]:
        return sorted(set(self._functions) | set(self._constants))

    def by_category(self) -> dict[str, list[FunctionSpec]]:
        grouped: dict[str, list[FunctionSpec]] = {}
        for spec in dict.fromkeys(self._functions.values()):
            grouped.setdefault(spec.category, []).append(spec)
        for specs in grouped.values():
            specs.sort(key=lambda s: s.name)
        return dict(sorted(grouped.items()))

    def describe(self, name: str) -> str | None:
        spec = self._functions.get(name)
        if spec:
            return f"{spec.name}({spec.arity_text()}) \u2014 {spec.doc}"
        if name in self._constant_docs:
            return f"{name} \u2014 {self._constant_docs[name]}"
        return None


REGISTRY = Registry()


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REGISTRY.constant("pi", "Ratio of a circle's circumference to its diameter")(dmath.pi)
REGISTRY.constant("tau", "Two pi, one full turn in radians")(dmath.tau)
REGISTRY.constant("e", "Euler's number, the base of the natural logarithm")(dmath.e)
REGISTRY.constant("phi", "The golden ratio")(dmath.phi)


# --------------------------------------------------------------------------- #
# Trigonometry (angle-mode aware)
# --------------------------------------------------------------------------- #


@REGISTRY.function("sin", 1, "Sine of an angle", "trig", needs_context=True)
def _sin(ctx: EvalContext, x: Decimal) -> Decimal:
    return dmath.sin(ctx.to_radians(x))


@REGISTRY.function("cos", 1, "Cosine of an angle", "trig", needs_context=True)
def _cos(ctx: EvalContext, x: Decimal) -> Decimal:
    return dmath.cos(ctx.to_radians(x))


@REGISTRY.function("tan", 1, "Tangent of an angle", "trig", needs_context=True)
def _tan(ctx: EvalContext, x: Decimal) -> Decimal:
    return dmath.tan(ctx.to_radians(x))


@REGISTRY.function("asin", 1, "Inverse sine", "trig", needs_context=True)
def _asin(ctx: EvalContext, x: Decimal) -> Decimal:
    return ctx.from_radians(dmath.asin(x))


@REGISTRY.function("acos", 1, "Inverse cosine", "trig", needs_context=True)
def _acos(ctx: EvalContext, x: Decimal) -> Decimal:
    return ctx.from_radians(dmath.acos(x))


@REGISTRY.function("atan", 1, "Inverse tangent", "trig", needs_context=True)
def _atan(ctx: EvalContext, x: Decimal) -> Decimal:
    return ctx.from_radians(dmath.atan(x))


@REGISTRY.function(
    "atan2", 2, "Inverse tangent of y/x using both signs", "trig", needs_context=True
)
def _atan2(ctx: EvalContext, y: Decimal, x: Decimal) -> Decimal:
    return ctx.from_radians(dmath.atan2(y, x))


@REGISTRY.function("sinh", 1, "Hyperbolic sine", "trig")
def _sinh(x: Decimal) -> Decimal:
    return dmath.sinh(x)


@REGISTRY.function("cosh", 1, "Hyperbolic cosine", "trig")
def _cosh(x: Decimal) -> Decimal:
    return dmath.cosh(x)


@REGISTRY.function("tanh", 1, "Hyperbolic tangent", "trig")
def _tanh(x: Decimal) -> Decimal:
    return dmath.tanh(x)


@REGISTRY.function("rad", 1, "Convert degrees to radians", "trig")
def _rad(x: Decimal) -> Decimal:
    return x * dmath.pi() / 180


@REGISTRY.function("deg", 1, "Convert radians to degrees", "trig")
def _deg(x: Decimal) -> Decimal:
    return x * 180 / dmath.pi()


# --------------------------------------------------------------------------- #
# Powers, roots and logarithms
# --------------------------------------------------------------------------- #


@REGISTRY.function("sqrt", 1, "Square root", "power")
def _sqrt(x: Decimal) -> Decimal:
    return dmath.sqrt(x)


@REGISTRY.function("cbrt", 1, "Cube root", "power")
def _cbrt(x: Decimal) -> Decimal:
    return dmath.cbrt(x)


@REGISTRY.function("root", 2, "The n-th root of x: root(x, n)", "power")
def _root(x: Decimal, n: Decimal) -> Decimal:
    if n == 0:
        raise DomainError("Root degree cannot be zero.")
    return dmath.power(x, 1 / n)


@REGISTRY.function("exp", 1, "e raised to the power of x", "power")
def _exp(x: Decimal) -> Decimal:
    return x.exp()


@REGISTRY.function("pow", 2, "Raise a base to an exponent", "power")
def _pow(base: Decimal, exponent: Decimal) -> Decimal:
    return dmath.power(base, exponent)


@REGISTRY.function("ln", 1, "Natural logarithm", "power")
def _ln(x: Decimal) -> Decimal:
    return dmath.ln(x)


@REGISTRY.function("log10", 1, "Base-10 logarithm", "power")
def _log10(x: Decimal) -> Decimal:
    return dmath.log10(x)


@REGISTRY.function("log2", 1, "Base-2 logarithm", "power")
def _log2(x: Decimal) -> Decimal:
    return dmath.log(x, Decimal(2))


@REGISTRY.function(
    "log", (1, 2), "Logarithm, base 10 by default: log(x) or log(x, b)", "power"
)
def _log(x: Decimal, base: Decimal | None = None) -> Decimal:
    if base is None:
        return dmath.log10(x)
    return dmath.log(x, base)


# --------------------------------------------------------------------------- #
# Rounding and sign
# --------------------------------------------------------------------------- #


@REGISTRY.function("abs", 1, "Absolute value", "numeric")
def _abs(x: Decimal) -> Decimal:
    return abs(x)


@REGISTRY.function("sign", 1, "-1, 0 or 1 matching the sign of x", "numeric")
def _sign(x: Decimal) -> Decimal:
    return Decimal(0) if x == 0 else Decimal(1).copy_sign(x)


@REGISTRY.function("floor", 1, "Round down to a whole number", "numeric")
def _floor(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding="ROUND_FLOOR")


@REGISTRY.function("ceil", 1, "Round up to a whole number", "numeric")
def _ceil(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding="ROUND_CEILING")


@REGISTRY.function("trunc", 1, "Discard the fractional part", "numeric")
def _trunc(x: Decimal) -> Decimal:
    return x.to_integral_value(rounding="ROUND_DOWN")


@REGISTRY.function("round", (1, 2), "Round to n decimal places", "numeric")
def _round(x: Decimal, places: Decimal | None = None) -> Decimal:
    digits = 0 if places is None else int(places)
    quantum = Decimal(1).scaleb(-digits)
    return x.quantize(quantum, rounding="ROUND_HALF_UP")


@REGISTRY.function("fact", 1, "Factorial of a whole number", "numeric")
def _fact(x: Decimal) -> Decimal:
    return dmath.factorial(x)


@REGISTRY.function("gcd", VARIADIC, "Greatest common divisor", "numeric")
def _gcd(*values: Decimal) -> Decimal:
    import math

    integers = []
    for value in values:
        if value != value.to_integral_value():
            raise DomainError("gcd requires whole numbers.")
        integers.append(abs(int(value)))
    return Decimal(math.gcd(*integers))


@REGISTRY.function("lcm", VARIADIC, "Least common multiple", "numeric")
def _lcm(*values: Decimal) -> Decimal:
    import math

    integers = []
    for value in values:
        if value != value.to_integral_value():
            raise DomainError("lcm requires whole numbers.")
        integers.append(abs(int(value)))
    return Decimal(math.lcm(*integers))


# --------------------------------------------------------------------------- #
# Aggregates
# --------------------------------------------------------------------------- #


@REGISTRY.function("min", VARIADIC, "Smallest of the arguments", "stats")
def _min(*values: Decimal) -> Decimal:
    return min(values)


@REGISTRY.function("max", VARIADIC, "Largest of the arguments", "stats")
def _max(*values: Decimal) -> Decimal:
    return max(values)


@REGISTRY.function("sum", VARIADIC, "Sum of the arguments", "stats")
def _sum(*values: Decimal) -> Decimal:
    return sum(values, Decimal(0))


@REGISTRY.function(
    "avg", VARIADIC, "Arithmetic mean of the arguments", "stats", aliases=("mean",)
)
def _avg(*values: Decimal) -> Decimal:
    return sum(values, Decimal(0)) / len(values)


@REGISTRY.function("median", VARIADIC, "Middle value of the arguments", "stats")
def _median(*values: Decimal) -> Decimal:
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


@REGISTRY.function("stdev", VARIADIC, "Population standard deviation", "stats")
def _stdev(*values: Decimal) -> Decimal:
    if len(values) < 2:
        raise DomainError("stdev needs at least two values.")
    mean = sum(values, Decimal(0)) / len(values)
    variance = sum(((v - mean) ** 2 for v in values), Decimal(0)) / len(values)
    return variance.sqrt()


@REGISTRY.function("hypot", VARIADIC, "Euclidean norm of the arguments", "stats")
def _hypot(*values: Decimal) -> Decimal:
    return dmath.hypot(*values)


@REGISTRY.function("rand", (0, 2), "Random value; rand(), rand(n), rand(a, b)", "misc")
def _rand(low: Decimal | None = None, high: Decimal | None = None) -> Decimal:
    if low is None:
        return Decimal(str(random.random()))
    if high is None:
        low, high = Decimal(0), low
    if high < low:
        low, high = high, low
    span = high - low
    return low + span * Decimal(str(random.random()))


@REGISTRY.function("clamp", 3, "Constrain x to the range [lo, hi]", "misc")
def _clamp(x: Decimal, low: Decimal, high: Decimal) -> Decimal:
    if low > high:
        low, high = high, low
    return min(max(x, low), high)


@REGISTRY.function("if", 3, "if(condition, when_true, when_false)", "misc")
def _if(condition: Decimal, when_true: Decimal, when_false: Decimal) -> Decimal:
    return when_true if condition != 0 else when_false


def safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Division that raises a :class:`DomainError` instead of a decimal trap."""
    if denominator == 0:
        raise DomainError("Division by zero.")
    try:
        return numerator / denominator
    except (DivisionByZero, InvalidOperation) as exc:  # pragma: no cover
        raise DomainError("Division by zero.") from exc


def modulo(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Floored modulo, so ``-7 mod 3`` is ``2`` rather than ``-1``."""
    if denominator == 0:
        raise DomainError("Cannot take a modulus of zero.")
    remainder = numerator - denominator * (numerator / denominator).to_integral_value(
        rounding="ROUND_FLOOR"
    )
    return remainder
