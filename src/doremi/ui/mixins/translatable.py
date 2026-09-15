from __future__ import annotations
from typing import Protocol
from PySide6.QtCore import QObject
from doremi.utils.i18n import _manager


class TranslatableProtocol(Protocol):
    def retranslate_ui(self) -> None: ...


class TranslatableWidget:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _manager.language_changed.connect(self._on_language_changed)

    def _on_language_changed(self, lang_code: str) -> None:
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        pass
