"""A tiny synchronous publish/subscribe bus.

The UI never reaches into the model to read state; instead it subscribes to
topics and redraws when told to. That keeps widgets replaceable and makes the
model testable without a display.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class Topic(Enum):
    """Every message the model can broadcast."""

    EXPRESSION_CHANGED = auto()   # the editable input buffer was edited
    RESULT_READY = auto()         # an evaluation succeeded
    ERROR_RAISED = auto()         # an evaluation failed
    HISTORY_CHANGED = auto()      # an entry was added or the tape was cleared
    MEMORY_CHANGED = auto()       # a memory register was written
    MODE_CHANGED = auto()         # angle/notation/precision/theme changed
    VARIABLES_CHANGED = auto()    # a user variable was bound
    STATUS = auto()               # transient status-bar text


Listener = Callable[["Event"], None]


@dataclass
class Event:
    """A topic plus an arbitrary payload."""

    topic: Topic
    payload: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.payload.get(key, default)


class EventBus:
    """Dispatches events to subscribers, newest last, errors isolated."""

    def __init__(self) -> None:
        self._listeners: dict[Topic, list[Listener]] = defaultdict(list)
        self._muted = False
        #: Retained for debugging and for the test-suite's assertions.
        self.journal: list[Event] = []
        self.journal_limit = 500

    def subscribe(self, topic: Topic, listener: Listener) -> Callable[[], None]:
        """Register ``listener``; returns a callable that unsubscribes it."""
        self._listeners[topic].append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners[topic]:
                self._listeners[topic].remove(listener)

        return unsubscribe

    def subscribe_many(self, topics: list[Topic], listener: Listener) -> None:
        for topic in topics:
            self.subscribe(topic, listener)

    def publish(self, topic: Topic, **payload: Any) -> None:
        event = Event(topic=topic, payload=payload)
        self.journal.append(event)
        if len(self.journal) > self.journal_limit:
            del self.journal[: len(self.journal) // 2]
        if self._muted:
            return
        # Copy, so a listener may unsubscribe during dispatch.
        for listener in list(self._listeners[topic]):
            listener(event)

    def mute(self) -> None:
        self._muted = True

    def unmute(self) -> None:
        self._muted = False
