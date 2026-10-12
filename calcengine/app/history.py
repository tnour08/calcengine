"""The calculation tape: a bounded, serialisable log of past evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterator


@dataclass(frozen=True)
class HistoryEntry:
    """One completed calculation."""

    expression: str
    formatted: str
    value: Decimal
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def clock(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "formatted": self.formatted,
            "value": str(self.value),
            "timestamp": self.timestamp.isoformat(timespec="seconds"),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "HistoryEntry":
        return cls(
            expression=data["expression"],
            formatted=data["formatted"],
            value=Decimal(data["value"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class History:
    """A ring buffer of :class:`HistoryEntry` with newest-first iteration."""

    def __init__(self, limit: int = 250):
        self.limit = limit
        self._entries: list[HistoryEntry] = []

    def add(self, entry: HistoryEntry) -> None:
        self._entries.append(entry)
        overflow = len(self._entries) - self.limit
        if overflow > 0:
            del self._entries[:overflow]

    def clear(self) -> None:
        self._entries.clear()

    @property
    def entries(self) -> list[HistoryEntry]:
        """Oldest first."""
        return list(self._entries)

    def recent(self, count: int | None = None) -> list[HistoryEntry]:
        """Newest first, optionally truncated."""
        reversed_entries = list(reversed(self._entries))
        return reversed_entries if count is None else reversed_entries[:count]

    @property
    def last(self) -> HistoryEntry | None:
        return self._entries[-1] if self._entries else None

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[HistoryEntry]:
        return iter(self._entries)

    def __bool__(self) -> bool:
        return bool(self._entries)

    # -- persistence -------------------------------------------------------- #

    def to_list(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self._entries]

    def load(self, rows: list[dict[str, Any]]) -> None:
        self._entries.clear()
        for row in rows:
            try:
                self._entries.append(HistoryEntry.from_dict(row))
            except (KeyError, ValueError, TypeError):
                continue  # skip corrupt rows rather than refusing to start
        overflow = len(self._entries) - self.limit
        if overflow > 0:
            del self._entries[:overflow]

    def as_text(self) -> str:
        """Plain-text export, suitable for the clipboard."""
        return "\n".join(
            f"{entry.clock}  {entry.expression} = {entry.formatted}"
            for entry in self._entries
        )
