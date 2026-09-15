from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QRect, QRectF, QSize, Qt, QPropertyAnimation
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPainterPath, QPixmap
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from doremi.ui.design.icons import Icon


class ArtworkWidget(QWidget):
    def __init__(self, size: int = 200, corner_radius: int | None = None, parent=None):
        super().__init__(parent)
        self._size = size
        self._radius = corner_radius if corner_radius is not None else max(8, size // 10)
        self._pixmap: QPixmap | None = None
        self._opacity = 0.0
        self.setFixedSize(QSize(size, size))

        self._fade_anim = QPropertyAnimation(self, b"img_opacity", self)
        self._fade_anim.setDuration(300)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, value: float) -> None:
        self._opacity = value
        self.update()

    img_opacity = Property(float, _get_opacity, _set_opacity)

    def set_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap.isNull():
            self.set_placeholder()
            return
        # Si ya viene del tamaño correcto (cargado por load_scaled_async), evita re-escalar
        if pixmap.width() == self._size and pixmap.height() == self._size:
            self._pixmap = pixmap
        else:
            self._pixmap = pixmap.scaled(
                self._size,
                self._size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.FastTransformation,  # más rápido, diferencia mínima en thumbnails
            )
        self._fade_anim.stop()
        self._fade_anim.setStartValue(self._opacity)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def set_image_url(self, url: str) -> None:
        pixmap = QPixmap(url)
        if pixmap.isNull():
            self.set_placeholder()
        else:
            self.set_pixmap(pixmap)

    def set_placeholder(self) -> None:
        self._pixmap = None
        self._opacity = 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0, 0, self._size, self._size)
        path = QPainterPath()
        path.addRoundedRect(rect, self._radius, self._radius)
        painter.setClipPath(path)

        if self._pixmap and self._opacity > 0:
            painter.setOpacity(self._opacity)
            painter.drawPixmap(0, 0, self._pixmap)
            painter.setOpacity(1.0)
        else:
            painter.fillRect(self.rect(), QColor("#1E1E38"))
            painter.setPen(QColor("#4A4A6A"))
            painter.setFont(Icon.font(max(20, self._size // 3)))
            painter.drawText(QRect(0, 0, self._size, self._size), Qt.AlignmentFlag.AlignCenter, Icon.get("music_note"))
        painter.end()

