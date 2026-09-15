from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

from doremi.ui.design.tokens import Elevation


def artwork_shadow(parent: QWidget) -> QGraphicsDropShadowEffect:
    """La única sombra del sistema: la que reposa bajo el artwork.

    blur 30, offset (3, 5), rgba(0,0,0,0.22) — ver DESIGN-apple.md.
    Prohibido usarla en botones, cards, paneles o texto.
    """
    effect = QGraphicsDropShadowEffect(parent)
    effect.setBlurRadius(Elevation.ARTWORK_BLUR)
    effect.setOffset(Elevation.ARTWORK_OFFSET_X, Elevation.ARTWORK_OFFSET_Y)
    effect.setColor(QColor(0, 0, 0, Elevation.ARTWORK_ALPHA))
    return effect
