from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QPoint, QSize
from PySide6.QtWidgets import QPushButton, QHBoxLayout, QLabel, QWidget, QVBoxLayout
from PySide6.QtGui import QFont

from doremi.ui.design.fonts import AppFont
from doremi.ui.design.icons import Icon
from doremi.ui.widgets.glass_panel import GlassPanel


class GlassComboBox(QPushButton):
    currentTextChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._current_index: int = -1
        self._popup: GlassPanel | None = None
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(38)
        self.setMinimumWidth(160)
        
        # Build button layout
        self.btn_layout = QHBoxLayout(self)
        self.btn_layout.setContentsMargins(12, 0, 12, 0)
        self.btn_layout.setSpacing(8)
        
        self.label = QLabel("Seleccionar...")
        self.label.setFont(AppFont.body(13))
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.btn_layout.addWidget(self.label)
        
        self.btn_layout.addStretch()
        
        self.chevron = Icon.label("keyboard_arrow_down", 16)
        self.chevron.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.btn_layout.addWidget(self.chevron)
        
        self._apply_style()
        self.clicked.connect(self._show_popup)

    def sizeHint(self) -> QSize:
        lbl_hint = self.label.sizeHint()
        chev_hint = self.chevron.sizeHint()
        w = lbl_hint.width() + chev_hint.width() + 64
        return QSize(max(w, 160), 38)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _apply_style(self) -> None:
        from doremi.ui.design import tokens
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.CURRENT.bg_elevated};
                border: 1px solid {tokens.CURRENT.border};
                border-radius: 8px;
                text-align: left;
            }}
            QPushButton:hover {{
                border-color: {tokens.CURRENT.accent};
            }}
        """)
        self.label.setStyleSheet(f" background: transparent;")
        self.chevron.setStyleSheet(f" background: transparent;")

    def addItems(self, items: list[str]) -> None:
        self._items = list(items)
        if self._items and self._current_index == -1:
            self.setCurrentIndex(0)

    def clear(self) -> None:
        self._items.clear()
        self._current_index = -1
        self.label.setText("Seleccionar...")

    def count(self) -> int:
        return len(self._items)

    def currentText(self) -> str:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index]
        return ""

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentText(self, text: str) -> None:
        if text in self._items:
            idx = self._items.index(text)
            self.setCurrentIndex(idx)

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._items):
            self._current_index = index
            text = self._items[index]
            self.label.setText(text)
            self.currentTextChanged.emit(text)
        else:
            self._current_index = -1
            self.label.setText("Seleccionar...")

    def _show_popup(self) -> None:
        if not self._items:
            return
            
        # Create a new GlassPanel popup
        self._popup = GlassPanel(parent=self.window())
        self._popup.setMinimumWidth(self.width())
        
        # Populate popup with standard premium styled option buttons
        layout = self._popup.layout()
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)
        
        from doremi.ui.design import tokens
        accent_color = tokens.CURRENT.accent
        text_primary = tokens.CURRENT.text_primary
        
        for idx, item_text in enumerate(self._items):
            btn = QPushButton()
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Use active dynamic styling matching settings page theme
            is_selected = (idx == self._current_index)
            hover_bg = f"rgba(167,139,250,0.10)" # Default fallback
            if accent_color:
                # Convert accent color to translucent hover bg
                try:
                    from PySide6.QtGui import QColor
                    c = QColor(accent_color)
                    hover_bg = f"rgba({c.red()}, {c.green()}, {c.blue()}, 0.12)"
                except Exception:
                    pass
            
            if is_selected:
                btn_style = f"""
                    QPushButton {{
                        background: {hover_bg};
                        border: none;
                        border-radius: 8px;
                        text-align: left;
                        padding: 0 10px;
                        color: {accent_color};
                    }}
                """
            else:
                btn_style = f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        border-radius: 8px;
                        text-align: left;
                        padding: 0 10px;
                        color: {text_primary};
                    }}
                    QPushButton:hover {{
                        background: {hover_bg};
                        color: {accent_color};
                    }}
                """
            btn.setStyleSheet(btn_style)
            
            btn_layout = QHBoxLayout(btn)
            btn_layout.setContentsMargins(8, 0, 8, 0)
            btn_layout.setSpacing(8)
            
            lbl = QLabel(item_text)
            lbl.setFont(AppFont.body(13))
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            if is_selected:
                lbl.setStyleSheet(f"color: {accent_color}; background: transparent; font-weight: bold;")
            else:
                lbl.setStyleSheet(f"color: {text_primary}; background: transparent;")
                
            btn_layout.addWidget(lbl)
            
            # Arrow or bullet for selected item
            if is_selected:
                check_icon = Icon.label("check", 14, accent_color)
                check_icon.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
                btn_layout.addWidget(check_icon)
                
            btn.clicked.connect(lambda _, i=idx: self._on_item_selected(i))
            layout.addWidget(btn)
            
        # Position popup exactly below the button relative to parent window
        parent_win = self.window()
        if parent_win:
            rel_pos = self.mapTo(parent_win, self.rect().bottomLeft())
        else:
            rel_pos = self.mapToGlobal(self.rect().bottomLeft())
            
        self._popup._trigger_widget = self
        self._popup.popup_at(QPoint(rel_pos.x(), rel_pos.y() + 4))

    def _on_item_selected(self, index: int) -> None:
        self.setCurrentIndex(index)
        if self._popup:
            self._popup.dismiss()
            self._popup = None

    def changeEvent(self, event) -> None:
        from PySide6.QtCore import QEvent
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_style()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
