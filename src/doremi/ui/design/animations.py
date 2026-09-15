from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPoint, QParallelAnimationGroup, QPropertyAnimation, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def fade_in(widget: QWidget, duration: int = 250) -> QPropertyAnimation:
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.finished.connect(lambda: widget.setGraphicsEffect(None))
    anim.start()
    widget._doremi_last_animation = anim
    return anim


def slide_in_from_right(widget: QWidget, duration: int = 350, offset: int = 48) -> QParallelAnimationGroup:
    start_pos = widget.pos() + QPoint(offset, 0)
    end_pos = widget.pos()

    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)

    fade = QPropertyAnimation(effect, b"opacity")
    fade.setDuration(duration)
    fade.setStartValue(0.0)
    fade.setEndValue(1.0)
    fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    slide = QPropertyAnimation(widget, b"pos")
    slide.setDuration(duration)
    slide.setStartValue(start_pos)
    slide.setEndValue(end_pos)
    slide.setEasingCurve(QEasingCurve.Type.OutCubic)

    group = QParallelAnimationGroup(widget)
    group.addAnimation(fade)
    group.addAnimation(slide)
    group.finished.connect(lambda: widget.setGraphicsEffect(None))
    group.start()
    widget._doremi_last_animation = group
    return group


def pulse(widget: QWidget, color_start: str = "#A78BFA") -> None:
    original = widget.styleSheet()
    widget.setStyleSheet(original + f"\nbackground-color: {color_start}20;")
    QTimer.singleShot(200, lambda: widget.setStyleSheet(original))

