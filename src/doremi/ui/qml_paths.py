"""Frozen-aware location of the bundled QML tree.

From source, QML lives next to this file (``src/doremi/ui/qml``). In a
PyInstaller bundle the Python files run from ``_internal`` while datas land at
the bundle root, so ``__file__``-relative lookups break; datas are collected
under ``doremi/ui/qml`` relative to ``sys._MEIPASS`` instead.
"""

from __future__ import annotations

from pathlib import Path


def qml_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "doremi" / "ui" / "qml"
    return Path(__file__).resolve().parent / "qml"
