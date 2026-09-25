from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class OfflineStateQml(QObject):
    """Offline route presenter rendered by ScreenHost.qml."""

    changed = Signal()

    def __init__(
        self,
        message: str,
        action_text: str,
        retry_callback: Callable[[], None] | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._action_text = action_text
        self._retry_callback = retry_callback
        self.qml_source = QUrl.fromLocalFile(str(QML_DIR / "OfflineState.qml"))
        self._load_ok = True

    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Property(str, notify=changed)
    def actionText(self) -> str:
        return self._action_text

    @Slot()
    def retry(self) -> None:
        if self._retry_callback:
            self._retry_callback()
