import platform
from loguru import logger

if platform.system() == "Linux":
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QKeySequence, QShortcut
        from PySide6.QtCore import QTimer
        import subprocess
        HAS_MEDIA_KEYS = True
    except ImportError:
        HAS_MEDIA_KEYS = False


class MediaKeys:

    def __init__(self, parent, on_play_pause, on_next, on_prev, on_stop=None):
        self.parent = parent
        self.on_play_pause = on_play_pause
        self.on_next = on_next
        self.on_prev = on_prev
        self.on_stop = on_stop
        self._shortcuts = []
        
        if platform.system() == "Linux" and HAS_MEDIA_KEYS:
            self._setup_mediakeys()

    def _setup_mediakeys(self):
        try:
            shortcuts = [
                ("MediaPlay", self.on_play_pause),
                ("MediaStop", self.on_stop),
                ("MediaNext", self.on_next),
                ("MediaPrevious", self.on_prev),
            ]
            for name, handler in shortcuts:
                if handler is None:
                    continue
                try:
                    shortcut = QShortcut(QKeySequence(name), self.parent)
                    shortcut.activated.connect(handler)
                    self._shortcuts.append(shortcut)
                except Exception as e:
                    logger.debug(f"Could not register media key {name}: {e}")
        except Exception as e:
            logger.debug(f"Could not setup media keys: {e}")
