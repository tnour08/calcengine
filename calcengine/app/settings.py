"""JSON-backed session persistence.

Saving is best-effort: a corrupt or unwritable file must never stop the
calculator from starting, so every failure degrades to defaults.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

APP_DIRECTORY_NAME = "calcengine"
SESSION_FILENAME = "session.json"


def default_config_directory() -> Path:
    """Platform-appropriate directory for the session file."""
    override = os.environ.get("CALCENGINE_HOME")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":  # pragma: no cover - not exercised on macOS/Linux
        base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(base) / APP_DIRECTORY_NAME
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / APP_DIRECTORY_NAME


@dataclass
class Settings:
    """User-facing preferences, all JSON-serialisable primitives."""

    theme: str = "midnight"
    angle_mode: str = "RAD"
    notation: str = "AUTO"
    precision: int = 28
    decimals: int = 10
    group_thousands: bool = True
    show_tape: bool = True
    show_inspector: bool = False
    live_preview: bool = True
    history: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, str] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)

    # -- serialisation ------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Settings":
        """Build settings from untrusted data, ignoring anything unexpected."""
        known = {f.name: f for f in fields(cls)}
        kwargs: dict[str, Any] = {}
        for name, value in (data or {}).items():
            spec = known.get(name)
            if spec is None:
                continue
            if spec.type in ("int", int) and isinstance(value, bool):
                continue  # bools are ints in Python; reject the confusion
            kwargs[name] = value
        instance = cls(**kwargs) if kwargs else cls()
        instance._coerce()
        return instance

    def _coerce(self) -> None:
        """Clamp and type-check fields loaded from disk."""
        self.precision = _clamp_int(self.precision, 6, 200, 28)
        self.decimals = _clamp_int(self.decimals, 0, 60, 10)
        self.group_thousands = bool(self.group_thousands)
        self.show_tape = bool(self.show_tape)
        self.show_inspector = bool(self.show_inspector)
        self.live_preview = bool(self.live_preview)
        if not isinstance(self.history, list):
            self.history = []
        if not isinstance(self.memory, dict):
            self.memory = {}
        if not isinstance(self.variables, dict):
            self.variables = {}
        for name in ("theme", "angle_mode", "notation"):
            if not isinstance(getattr(self, name), str):
                setattr(self, name, getattr(Settings(), name))


def _clamp_int(value: Any, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


class SettingsStore:
    """Reads and writes :class:`Settings` atomically."""

    def __init__(self, path: Path | None = None):
        self.path = path or (default_config_directory() / SESSION_FILENAME)

    def load(self) -> Settings:
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return Settings()
        if not isinstance(data, dict):
            return Settings()
        return Settings.from_dict(data)

    def save(self, settings: Settings) -> bool:
        """Write via a temp file + rename, so a crash cannot truncate state."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(settings.to_dict(), indent=2)
            handle = tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=".session-",
                suffix=".tmp",
                delete=False,
            )
            try:
                with handle as stream:
                    stream.write(payload)
                os.replace(handle.name, self.path)
            except BaseException:
                Path(handle.name).unlink(missing_ok=True)
                raise
            return True
        except (OSError, TypeError, ValueError):
            return False
