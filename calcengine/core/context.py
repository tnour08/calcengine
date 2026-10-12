"""Evaluation context: precision, angle units and the variable namespace."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum

from . import dmath


class AngleMode(Enum):
    """Unit in which trigonometric arguments and results are expressed."""

    RADIANS = "RAD"
    DEGREES = "DEG"
    GRADIANS = "GRAD"

    @property
    def quarter_turn(self) -> Decimal:
        """The value representing 90 degrees in this unit."""
        if self is AngleMode.RADIANS:
            return dmath.pi() / 2
        if self is AngleMode.DEGREES:
            return Decimal(90)
        return Decimal(100)

    def next(self) -> "AngleMode":
        members = list(AngleMode)
        return members[(members.index(self) + 1) % len(members)]


@dataclass
class EvalContext:
    """Everything an evaluation needs besides the tree itself."""

    angle_mode: AngleMode = AngleMode.RADIANS
    precision: int = 28
    variables: dict[str, Decimal] = field(default_factory=dict)

    #: Names the user may not rebind.
    RESERVED = frozenset({"pi", "e", "tau", "phi", "inf"})

    def to_radians(self, value: Decimal) -> Decimal:
        """Convert an angle expressed in the active unit into radians."""
        if self.angle_mode is AngleMode.RADIANS:
            return value
        if self.angle_mode is AngleMode.DEGREES:
            return value * dmath.pi() / 180
        return value * dmath.pi() / 200

    def from_radians(self, value: Decimal) -> Decimal:
        """Convert a radian result back into the active unit."""
        if self.angle_mode is AngleMode.RADIANS:
            return value
        if self.angle_mode is AngleMode.DEGREES:
            return value * 180 / dmath.pi()
        return value * 200 / dmath.pi()

    def set_variable(self, name: str, value: Decimal) -> None:
        self.variables[name] = value

    def snapshot(self) -> dict[str, Decimal]:
        return dict(self.variables)
