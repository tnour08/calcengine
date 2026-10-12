"""Arbitrary-precision elementary functions over :class:`decimal.Decimal`.

``decimal`` ships with ``exp``, ``ln``, ``log10`` and ``sqrt`` but nothing
trigonometric, so the circular and hyperbolic functions here are built from
Taylor/Maclaurin series with explicit argument reduction.  Every public helper
computes at elevated precision internally and rounds once on the way out, which
keeps the final digit honest instead of accumulating series error.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, localcontext

from .errors import DomainError

#: Extra working digits used while a series converges.
GUARD_DIGITS = 12

ZERO = Decimal(0)
ONE = Decimal(1)
TWO = Decimal(2)
HALF = Decimal("0.5")


@contextmanager
def _guarded(extra: int = GUARD_DIGITS):
    """Temporarily widen precision so series truncation stays invisible."""
    with localcontext() as ctx:
        ctx.prec += extra
        yield ctx


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_PI_CACHE: dict[int, Decimal] = {}


def pi() -> Decimal:
    """Pi at the active precision, via the Gosper/AGM-style series.

    This is the classic ``decimal`` recipe: an accelerated arctangent-free
    expansion that gains roughly one digit per iteration.
    """
    with localcontext() as ctx:
        prec = ctx.prec
    if prec in _PI_CACHE:
        return +_PI_CACHE[prec]

    with _guarded(GUARD_DIGITS + 5):
        three = Decimal(3)
        lasts, t, s, n, na, d, da = ZERO, three, Decimal(3), 1, 0, 0, 24
        while s != lasts:
            lasts = s
            n, na = n + na, na + 8
            d, da = d + da, da + 32
            t = (t * n) / d
            s += t
        result = s
    rounded = +result
    _PI_CACHE[prec] = rounded
    return rounded


def tau() -> Decimal:
    with _guarded():
        value = pi() * 2
    return +value


def e() -> Decimal:
    return ONE.exp()


def phi() -> Decimal:
    """The golden ratio, (1 + sqrt(5)) / 2."""
    with _guarded():
        value = (ONE + Decimal(5).sqrt()) / TWO
    return +value


# --------------------------------------------------------------------------- #
# Argument reduction
# --------------------------------------------------------------------------- #


def _reduce_mod_tau(x: Decimal) -> Decimal:
    """Fold ``x`` into ``(-pi, pi]`` so the sine series converges quickly."""
    two_pi = pi() * 2
    if abs(x) < two_pi:
        reduced = x
    else:
        quotient = (x / two_pi).to_integral_value(rounding="ROUND_HALF_EVEN")
        reduced = x - quotient * two_pi
    half = pi()
    while reduced > half:
        reduced -= two_pi
    while reduced <= -half:
        reduced += two_pi
    return reduced


# --------------------------------------------------------------------------- #
# Circular functions
# --------------------------------------------------------------------------- #


def _sin_series(x: Decimal) -> Decimal:
    """sin(x) = x - x^3/3! + x^5/5! - ... for a pre-reduced ``x``."""
    i, lasts, s, fact, num, sign = 1, ZERO, x, 1, x, 1
    while s != lasts:
        lasts = s
        i += 2
        fact *= i * (i - 1)
        num *= x * x
        sign *= -1
        s += num / fact * sign
    return s


def _cos_series(x: Decimal) -> Decimal:
    """cos(x) = 1 - x^2/2! + x^4/4! - ... for a pre-reduced ``x``."""
    i, lasts, s, fact, num, sign = 0, ZERO, ONE, 1, ONE, 1
    while s != lasts:
        lasts = s
        i += 2
        fact *= i * (i - 1)
        num *= x * x
        sign *= -1
        s += num / fact * sign
    return s


def sin(x: Decimal) -> Decimal:
    with _guarded():
        value = _sin_series(_reduce_mod_tau(x))
    return +value


def cos(x: Decimal) -> Decimal:
    with _guarded():
        value = _cos_series(_reduce_mod_tau(x))
    return +value


def tan(x: Decimal) -> Decimal:
    with _guarded():
        reduced = _reduce_mod_tau(x)
        denominator = _cos_series(reduced)
        if denominator == 0:
            raise DomainError("tan is undefined at odd multiples of pi/2.")
        value = _sin_series(reduced) / denominator
    return +value


# --------------------------------------------------------------------------- #
# Inverse circular functions
# --------------------------------------------------------------------------- #


def _atan_core(x: Decimal) -> Decimal:
    """Arctangent of a non-negative ``x`` at the active (widened) precision."""
    if x > 1:
        return pi() / 2 - _atan_core(1 / x)

    # Halve the argument until the alternating series converges fast:
    #   atan(x) = 2 * atan( x / (1 + sqrt(1 + x^2)) )
    halvings = 0
    threshold = Decimal("0.05")
    while x > threshold:
        x = x / (ONE + (ONE + x * x).sqrt())
        halvings += 1

    total = term = x
    x_squared = x * x
    denominator = 1
    sign = -1
    while True:
        term *= x_squared
        denominator += 2
        candidate = total + term / denominator * sign
        if candidate == total:
            break
        total = candidate
        sign = -sign
    return total * (1 << halvings)


def atan(x: Decimal) -> Decimal:
    with _guarded():
        value = -_atan_core(-x) if x < 0 else _atan_core(x)
    return +value


def atan2(y: Decimal, x: Decimal) -> Decimal:
    with _guarded():
        if x > 0:
            value = atan(y / x)
        elif x < 0:
            value = atan(y / x) + (pi() if y >= 0 else -pi())
        elif y > 0:
            value = pi() / 2
        elif y < 0:
            value = -pi() / 2
        else:
            raise DomainError("atan2(0, 0) is undefined.")
    return +value


def asin(x: Decimal) -> Decimal:
    if abs(x) > 1:
        raise DomainError("asin is only defined on [-1, 1].")
    with _guarded():
        if abs(x) == 1:
            value = pi() / 2 * (1 if x > 0 else -1)
        else:
            value = _atan_core(abs(x) / (ONE - x * x).sqrt())
            if x < 0:
                value = -value
    return +value


def acos(x: Decimal) -> Decimal:
    if abs(x) > 1:
        raise DomainError("acos is only defined on [-1, 1].")
    with _guarded():
        value = pi() / 2 - asin(x)
    return +value


# --------------------------------------------------------------------------- #
# Hyperbolic functions
# --------------------------------------------------------------------------- #


def sinh(x: Decimal) -> Decimal:
    with _guarded():
        value = (x.exp() - (-x).exp()) / TWO
    return +value


def cosh(x: Decimal) -> Decimal:
    with _guarded():
        value = (x.exp() + (-x).exp()) / TWO
    return +value


def tanh(x: Decimal) -> Decimal:
    with _guarded():
        hi = x.exp()
        lo = (-x).exp()
        value = (hi - lo) / (hi + lo)
    return +value


# --------------------------------------------------------------------------- #
# Powers, roots and logarithms
# --------------------------------------------------------------------------- #


def sqrt(x: Decimal) -> Decimal:
    if x < 0:
        raise DomainError("Cannot take the square root of a negative number.")
    return x.sqrt()


def cbrt(x: Decimal) -> Decimal:
    if x == 0:
        return ZERO
    with _guarded():
        magnitude = (abs(x).ln() / 3).exp()
        value = magnitude if x > 0 else -magnitude
    return +value


def ln(x: Decimal) -> Decimal:
    if x <= 0:
        raise DomainError("ln is only defined for positive values.")
    return x.ln()


def log10(x: Decimal) -> Decimal:
    if x <= 0:
        raise DomainError("log10 is only defined for positive values.")
    return x.log10()


def log(x: Decimal, base: Decimal) -> Decimal:
    if x <= 0:
        raise DomainError("log is only defined for positive values.")
    if base <= 0 or base == 1:
        raise DomainError("Logarithm base must be positive and not equal to 1.")
    with _guarded():
        value = x.ln() / base.ln()
    return +value


def power(base: Decimal, exponent: Decimal) -> Decimal:
    """``base ** exponent`` with support for negative bases at integer powers."""
    if base == 0 and exponent < 0:
        raise DomainError("Cannot raise zero to a negative power.")
    is_integer_exponent = exponent == exponent.to_integral_value()
    if base < 0 and not is_integer_exponent:
        raise DomainError("A negative base requires an integer exponent.")

    try:
        if is_integer_exponent:
            with _guarded():
                value = base ** int(exponent)
            return +value
        with _guarded():
            value = (exponent * base.ln()).exp()
        return +value
    except (InvalidOperation, OverflowError) as exc:  # pragma: no cover
        raise DomainError(f"Cannot evaluate {base} ^ {exponent}.") from exc


def factorial(x: Decimal) -> Decimal:
    if x != x.to_integral_value():
        raise DomainError("Factorial requires a whole number.")
    if x < 0:
        raise DomainError("Factorial is undefined for negative numbers.")
    n = int(x)
    if n > 20000:
        raise DomainError("Factorial argument is too large (limit 20000).")
    result = ONE
    for multiplier in range(2, n + 1):
        result *= multiplier
    return +result


def hypot(*values: Decimal) -> Decimal:
    with _guarded():
        total = sum((v * v for v in values), ZERO)
        value = total.sqrt()
    return +value


__all__ = [
    "GUARD_DIGITS",
    "acos",
    "asin",
    "atan",
    "atan2",
    "cbrt",
    "cos",
    "cosh",
    "e",
    "factorial",
    "hypot",
    "ln",
    "log",
    "log10",
    "phi",
    "pi",
    "power",
    "sin",
    "sinh",
    "sqrt",
    "tan",
    "tanh",
    "tau",
]
