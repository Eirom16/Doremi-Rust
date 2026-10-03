"""Invalidation notifications, never a second copy of music state."""
from PySide6.QtCore import QObject, Signal


class ExperienceEvents(QObject):
    changed = Signal()
    liked_changed = Signal(str, bool)
    downloaded_changed = Signal(str, bool)
    collections_changed = Signal()
    pin_requested = Signal(str, str, str)
    pin_changed = Signal(str, bool)
    pin_move_requested = Signal(str, str)


events = ExperienceEvents()
