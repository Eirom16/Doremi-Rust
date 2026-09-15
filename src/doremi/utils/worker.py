from PySide6.QtCore import QRunnable, QObject, Signal, Slot
import traceback
from typing import Callable, Any


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(str)
    result = Signal(object)
    progress = Signal(int)


class Worker(QRunnable):

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            )
        finally:
            self.signals.finished.emit()
