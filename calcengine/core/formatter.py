"""Turning a :class:`~decimal.Decimal` into something pleasant to read."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum


class NotationMode(Enum):
    AUTO = "AUTO"
    FIXED = "FIX"
    SCIENTIFIC = "SCI"
    ENGINEERING = "ENG"

    def next(self) -> "NotationMode":
        members = list(NotationMode)
        return members[(members.index(self) + 1) % len(members)]


@dataclass
class Formatter:
    """Formats results according to the user's display preferences."""

    notation: NotationMode = NotationMode.AUTO
    decimals: int = 10
    group_thousands: bool = True

    #: Must match the engine's working precision, otherwise ``quantize`` trips
    #: over values that carry more digits than the ambient context allows.
    precision: int = 28

    #: Beyond these exponents AUTO switches to scientific notation.
    upper_exponent: int = 15
    lower_exponent: int = -7

    def format(self, value: Decimal) -> str:
        if value.is_nan():
            return "undefined"
        if value.is_infinite():
            return "\u221e" if value > 0 else "-\u221e"

        with localcontext() as ctx:
            # Headroom for the integer part as well as the requested decimals.
            ctx.prec = max(self.precision, self.decimals + 20)
            if self.notation is NotationMode.SCIENTIFIC:
                return self._scientific(value)
            if self.notation is NotationMode.ENGINEERING:
                return self._engineering(value)
            if self.notation is NotationMode.FIXED:
                return self._decorate(self._fixed(value))
            return self._auto(value)

    # -- modes -------------------------------------------------------------- #

    def _auto(self, value: Decimal) -> str:
        if value == 0:
            return "0"
        exponent = value.adjusted()
        if exponent > self.upper_exponent or exponent < self.lower_exponent:
            return self._scientific(value)
        return self._decorate(self._plain(value))

    def _plain(self, value: Decimal) -> str:
        """Shortest faithful fixed-point rendering, trailing zeros removed."""
        quantised = self._round_to_decimals(value)
        text = f"{quantised:f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _fixed(self, value: Decimal) -> str:
        quantum = Decimal(1).scaleb(-self.decimals)
        try:
            return f"{value.quantize(quantum, rounding='ROUND_HALF_UP'):f}"
        except InvalidOperation:
            return self._plain(value)

    def _round_to_decimals(self, value: Decimal) -> Decimal:
        """Round to ``decimals`` places without forcing trailing zeros."""
        quantum = Decimal(1).scaleb(-self.decimals)
        try:
            return value.quantize(quantum, rounding="ROUND_HALF_UP")
        except InvalidOperation:
            # More integer digits than the context allows; keep every digit.
            return value

    def _scientific(self, value: Decimal) -> str:
        if value == 0:
            return "0"
        exponent = value.adjusted()
        with localcontext() as ctx:
            ctx.prec = max(self.decimals + 2, 6)
            mantissa = value.scaleb(-exponent)
        mantissa_text = self._trim(mantissa)
        return f"{mantissa_text}\u00d710{_superscript(exponent)}"

    def _engineering(self, value: Decimal) -> str:
        if value == 0:
            return "0"
        exponent = value.adjusted()
        shift = exponent - (exponent // 3) * 3
        with localcontext() as ctx:
            ctx.prec = max(self.decimals + 3, 6)
            mantissa = value.scaleb(-(exponent - shift))
        mantissa_text = self._trim(mantissa)
        return f"{mantissa_text}\u00d710{_superscript((exponent // 3) * 3)}"

    # -- helpers ------------------------------------------------------------ #

    def _trim(self, value: Decimal) -> str:
        quantum = Decimal(1).scaleb(-min(self.decimals, 12))
        try:
            value = value.quantize(quantum, rounding="ROUND_HALF_UP")
        except InvalidOperation:
            pass
        text = f"{value:f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    def _decorate(self, text: str) -> str:
        if not self.group_thousands:
            return text
        negative = text.startswith("-")
        body = text[1:] if negative else text
        if "." in body:
            whole, fraction = body.split(".", 1)
            fraction = "." + fraction
        else:
            whole, fraction = body, ""
        if len(whole) > 4:
            whole = f"{int(whole):,}" if whole.isdigit() else whole
        return ("-" if negative else "") + whole + fraction


_SUPERSCRIPT_DIGITS = str.maketrans("0123456789-", "\u2070\u00b9\u00b2\u00b3\u2074\u2075\u2076\u2077\u2078\u2079\u207b")


def _superscript(exponent: int) -> str:
    return str(exponent).translate(_SUPERSCRIPT_DIGITS)
