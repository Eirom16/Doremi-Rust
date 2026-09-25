"""QML-backed transient notifications.

The public ``ToastNotification.show`` API is deliberately kept so callers in
controllers and QML adapters do not need presentation-specific knowledge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget

from doremi.ui.theme_bridge import theme_bridge

QML_DIR = Path(__file__).resolve().parent.parent / "qml"


class _ToastViewModel(QObject):
    changed = Signal()
    action_requested = Signal()

    _ICONS = {
        "success": "check_circle",
        "error": "error",
        "info": "info",
        "warning": "warning",
    }

    def __init__(self, parent: QObject) -> None:
        super().__init__(parent)
        self._visible = False
        self._message = ""
        self._kind = "info"
        self._action_text = ""

    def present(self, message: str, kind: str, action_text: str | None) -> None:
        self._message = message
        self._kind = kind if kind in self._ICONS else "info"
        self._action_text = action_text or ""
        self._visible = True
        self.changed.emit()

    def dismiss(self) -> None:
        if self._visible:
            self._visible = False
            self.changed.emit()

    @Property(bool, notify=changed)
    def visible(self) -> bool:
        return self._visible

    @Property(str, notify=changed)
    def message(self) -> str:
        return self._message

    @Property(str, notify=changed)
    def actionText(self) -> str:
        return self._action_text

    @Property(str, notify=changed)
    def iconName(self) -> str:
        return self._ICONS[self._kind]

    @Property(str, notify=changed)
    def accentColor(self) -> str:
        from doremi.ui.design import tokens
        return getattr(tokens.CURRENT, self._kind, tokens.CURRENT.info)

    @Slot()
    def triggerAction(self) -> None:
        self.action_requested.emit()


class ToastNotification:
    """One QML toast overlay per top-level window."""

    _overlays: dict[int, "ToastNotification"] = {}

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent.window() or parent
        self._vm = _ToastViewModel(self._parent)
        self._quick = QQuickWidget(self._parent)
        self._quick.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self._quick.setAutoFillBackground(False)
        self._quick.setClearColor(QColor(0, 0, 0, 0))
        self._quick.engine().addImportPath(str(QML_DIR))
        context = self._quick.rootContext()
        context.setContextProperty("themeBridge", theme_bridge())
        context.setContextProperty("toastVm", self._vm)
        self._quick.setSource(QUrl.fromLocalFile(str(QML_DIR / "Toast.qml")))
        self._quick.setFixedSize(380, 96)
        self._quick.hide()
        self._timer = QTimer(self._quick)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._action_callback: Callable[[], None] | None = None
        self._vm.action_requested.connect(self._on_action)

    def present(
        self,
        message: str,
        kind: str = "info",
        action_text: str | None = None,
        action_callback: Callable[[], None] | None = None,
    ) -> "ToastNotification":
        self._action_callback = action_callback
        self._vm.present(message, kind, action_text if action_callback else None)
        self._quick.show()
        self._position()
        self._quick.raise_()
        self._timer.start(3500)
        return self

    def _position(self) -> None:
        parent_rect = self._parent.rect()
        x = max(20, parent_rect.width() - self._quick.width() - 20)
        y = max(20, parent_rect.height() - self._quick.height() - 96)
        self._quick.move(x, y)

    def _dismiss(self) -> None:
        self._timer.stop()
        self._vm.dismiss()
        self._quick.hide()

    def _on_action(self) -> None:
        callback = self._action_callback
        self._dismiss()
        if callback:
            callback()

    @classmethod
    def show(
        cls,
        parent: QWidget,
        message: str,
        kind: str = "info",
        action_text: str | None = None,
        action_callback: Callable[[], None] | None = None,
    ) -> "ToastNotification":
        host = parent.window() or parent
        key = id(host)
        overlay = cls._overlays.get(key)
        if overlay is None or overlay._quick.parentWidget() is None:
            overlay = cls(host)
            cls._overlays[key] = overlay
        return overlay.present(message, kind, action_text, action_callback)
