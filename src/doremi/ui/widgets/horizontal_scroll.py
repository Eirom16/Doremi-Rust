from __future__ import annotations

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QEvent
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QScrollArea, QPushButton,
    QGraphicsOpacityEffect, QFrame
)
from doremi.ui.design.icons import Icon
from doremi.ui.design import tokens


class HorizontalScrollArea(QWidget):
    """
    A premium horizontally scrolling container for music cards (playlists, albums, artists).
    Features smooth scrolling animations and elegant floating navigation buttons
    ('<' and '>') that fade in/out on hover.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(236)
        self._build_ui()

    def _build_ui(self):
        # 1. Main Scroll Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        # Content Widget to hold the cards
        self.content_widget = QWidget()
        self.content_widget.setStyleSheet("background: transparent;")
        self.layout_content = QHBoxLayout(self.content_widget)
        self.layout_content.setContentsMargins(0, 4, 0, 4)
        self.layout_content.setSpacing(16)
        self.layout_content.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.scroll_area.setWidget(self.content_widget)

        # Main wrapper layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.scroll_area)

        # 2. Left & Right Navigation Buttons
        self.btn_left = QPushButton(self)
        self.btn_left.setText(Icon.get("chevron_left"))
        self.btn_left.setFont(Icon.font(24))
        self.btn_left.setFixedSize(38, 38)
        self.btn_left.setCursor(Qt.CursorShape.PointingHandCursor)

        self.btn_right = QPushButton(self)
        self.btn_right.setText(Icon.get("chevron_right"))
        self.btn_right.setFont(Icon.font(24))
        self.btn_right.setFixedSize(38, 38)
        self.btn_right.setCursor(Qt.CursorShape.PointingHandCursor)

        self._apply_styles()

        # Button connections
        self.btn_left.clicked.connect(self._scroll_left)
        self.btn_right.clicked.connect(self._scroll_right)

        # Opacity effects for premium hover fade transitions
        self.opacity_left = QGraphicsOpacityEffect(self.btn_left)
        self.btn_left.setGraphicsEffect(self.opacity_left)
        self.opacity_left.setOpacity(0.0)

        self.opacity_right = QGraphicsOpacityEffect(self.btn_right)
        self.btn_right.setGraphicsEffect(self.opacity_right)
        self.opacity_right.setOpacity(0.0)

        self.anim_left = QPropertyAnimation(self.opacity_left, b"opacity", self)
        self.anim_left.setDuration(180)
        self.anim_left.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.anim_right = QPropertyAnimation(self.opacity_right, b"opacity", self)
        self.anim_right.setDuration(180)
        self.anim_right.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Track scroll position to dynamically show/hide buttons
        self.scroll_area.horizontalScrollBar().valueChanged.connect(self._update_button_visibility)
        
        # Initially hide buttons since we are at scroll 0
        self.btn_left.hide()

    def addWidget(self, widget: QWidget):
        self.layout_content.addWidget(widget)
        self._update_button_visibility()

    def clear(self):
        while self.layout_content.count():
            item = self.layout_content.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._update_button_visibility()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Position navigation buttons floating on top of scroll container
        h = self.height()
        w = self.width()
        
        # Center vertically on the scroll area, offset slightly from edges
        self.btn_left.move(4, (h - self.btn_left.height()) // 2)
        self.btn_right.move(w - self.btn_right.width() - 4, (h - self.btn_right.height()) // 2)
        
        self._update_button_visibility()

    def enterEvent(self, event):
        super().enterEvent(event)
        self._fade_buttons(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._fade_buttons(False)

    def _fade_buttons(self, show: bool):
        target = 1.0 if show else 0.0
        bar = self.scroll_area.horizontalScrollBar()
        
        # Left button fade
        if show and bar.value() > 0:
            self.anim_left.stop()
            self.anim_left.setEndValue(target)
            self.anim_left.start()
        elif not show:
            self.anim_left.stop()
            self.anim_left.setEndValue(target)
            self.anim_left.start()

        # Right button fade
        if show and bar.value() < bar.maximum():
            self.anim_right.stop()
            self.anim_right.setEndValue(target)
            self.anim_right.start()
        elif not show:
            self.anim_right.stop()
            self.anim_right.setEndValue(target)
            self.anim_right.start()

    def _update_button_visibility(self):
        bar = self.scroll_area.horizontalScrollBar()
        can_scroll_left = bar.value() > 0
        can_scroll_right = bar.value() < bar.maximum()

        # Update left button
        if can_scroll_left:
            self.btn_left.show()
            # If mouse is currently inside, let it show
            under_mouse = self.rect().contains(self.mapFromGlobal(self.cursor().pos()))
            if under_mouse:
                self.opacity_left.setOpacity(1.0)
        else:
            self.btn_left.hide()
            self.opacity_left.setOpacity(0.0)

        # Update right button
        if can_scroll_right:
            self.btn_right.show()
            under_mouse = self.rect().contains(self.mapFromGlobal(self.cursor().pos()))
            if under_mouse:
                self.opacity_right.setOpacity(1.0)
        else:
            self.btn_right.hide()
            self.opacity_right.setOpacity(0.0)

    def _scroll_left(self):
        bar = self.scroll_area.horizontalScrollBar()
        amount = self.scroll_area.width() * 0.75
        target = max(0, bar.value() - amount)
        self._animate_scroll(target)

    def _scroll_right(self):
        bar = self.scroll_area.horizontalScrollBar()
        amount = self.scroll_area.width() * 0.75
        target = min(bar.maximum(), bar.value() + amount)
        self._animate_scroll(target)

    def _animate_scroll(self, target_value):
        bar = self.scroll_area.horizontalScrollBar()
        self.scroll_anim = QPropertyAnimation(bar, b"value", self)
        self.scroll_anim.setDuration(350)
        self.scroll_anim.setStartValue(bar.value())
        self.scroll_anim.setEndValue(int(target_value))
        self.scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.scroll_anim.start()

    def _apply_styles(self):
        t = tokens.CURRENT
        style = f"""
            QPushButton {{
                background-color: {t.bg_surface}E6;
                border: 1px solid {t.border};
                border-radius: 19px;
                color: {t.text_primary};
                font-family: 'Material Symbols Rounded';
                font-size: 24px;
            }}
            QPushButton:hover {{
                background-color: {t.bg_high}F2;
                border-color: {t.accent};
                color: {t.accent};
            }}
        """
        self.btn_left.setStyleSheet(style)
        self.btn_right.setStyleSheet(style)

    def changeEvent(self, event):
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            if not getattr(self, '_in_style_change', False):
                self._in_style_change = True
                try:
                    self._apply_styles()
                finally:
                    self._in_style_change = False
        super().changeEvent(event)
