"""Memory registers: the classic MS/MR/M+/M- bank, with named slots."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class MemoryBank:
    """A small keyed store of :class:`~decimal.Decimal` values.

    Slot ``"M"`` is the default register driven by the MS/MR/M+/M- keys; any
    other key can be used for the numbered slots shown in the side panel.
    """

    DEFAULT_SLOT = "M"

    def __init__(self, slots: int = 4):
        self.slot_names = [self.DEFAULT_SLOT] + [f"M{i}" for i in range(1, slots)]
        self._values: dict[str, Decimal] = {}

    # -- single-slot operations --------------------------------------------- #

    def store(self, value: Decimal, slot: str = DEFAULT_SLOT) -> None:
        self._values[slot] = value

    def recall(self, slot: str = DEFAULT_SLOT) -> Decimal:
        return self._values.get(slot, Decimal(0))

    def add(self, value: Decimal, slot: str = DEFAULT_SLOT) -> Decimal:
        self._values[slot] = self.recall(slot) + value
        return self._values[slot]

    def subtract(self, value: Decimal, slot: str = DEFAULT_SLOT) -> Decimal:
        self._values[slot] = self.recall(slot) - value
        return self._values[slot]

    def clear(self, slot: str = DEFAULT_SLOT) -> None:
        self._values.pop(slot, None)

    def clear_all(self) -> None:
        self._values.clear()

    # -- inspection --------------------------------------------------------- #

    def is_set(self, slot: str = DEFAULT_SLOT) -> bool:
        return slot in self._values

    @property
    def occupied(self) -> list[str]:
        return [name for name in self.slot_names if name in self._values]

    def items(self) -> list[tuple[str, Decimal]]:
        return [(name, self._values[name]) for name in self.occupied]

    def __len__(self) -> int:
        return len(self._values)

    def __bool__(self) -> bool:
        return bool(self._values)

    # -- persistence -------------------------------------------------------- #

    def to_dict(self) -> dict[str, str]:
        return {name: str(value) for name, value in self._values.items()}

    def load(self, data: dict[str, Any]) -> None:
        self._values.clear()
        for name, raw in data.items():
            try:
                self._values[name] = Decimal(str(raw))
            except Exception:
                continue  # ignore unreadable slots
