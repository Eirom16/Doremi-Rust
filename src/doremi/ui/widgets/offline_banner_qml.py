from __future__ import annotations

from PySide6.QtCore import Property, QObject, QTimer, Signal


class OfflineBannerQml(QObject):
    """Offline banner presenter rendered by MainShell.qml."""

    shown_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shown = False
        self._load_ok = True
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(300)
        self._hide_timer.timeout.connect(self._finish_hiding)


    @property
    def is_ok(self) -> bool:
        return self._load_ok

    @Property(bool, notify=shown_changed)
    def shown(self) -> bool:
        return self._shown

    def show_banner(self) -> None:
        self._hide_timer.stop()
        if not self._shown:
            self._shown = True
            self.shown_changed.emit()

    def hide_banner(self) -> None:
        if not self._shown:
            return
        self._shown = False
        self.shown_changed.emit()
        self._hide_timer.start()

    def _finish_hiding(self) -> None:
        return None

    def _apply_style(self) -> None:
        """Retained for ThemeManager parity; QML reacts to themeBridge itself."""
