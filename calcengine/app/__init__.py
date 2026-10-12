"""Application layer: observable state, reversible commands, persistence.

Nothing here imports Tk. The UI subscribes to :class:`~.events.EventBus`
topics published by :class:`~.model.CalculatorModel`.
"""

from .commands import Command, CommandStack
from .events import Event, EventBus, Topic
from .history import History, HistoryEntry
from .memory import MemoryBank
from .model import CalculatorModel
from .settings import Settings, SettingsStore

__all__ = [
    "CalculatorModel",
    "Command",
    "CommandStack",
    "Event",
    "EventBus",
    "History",
    "HistoryEntry",
    "MemoryBank",
    "Settings",
    "SettingsStore",
    "Topic",
]
