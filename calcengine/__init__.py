"""calcengine - an expression calculator with a Tk front end.

Layers, outermost last::

    calcengine.core   pure evaluation pipeline (no UI imports)
    calcengine.app    observable state, commands, undo/redo, persistence
    calcengine.ui     Tk widgets drawn on canvases

Run it with ``python -m calcengine``.
"""

__version__ = "1.0.0"

from .core import AngleMode, CalcError, Engine, NotationMode

__all__ = ["AngleMode", "CalcError", "Engine", "NotationMode", "__version__"]
