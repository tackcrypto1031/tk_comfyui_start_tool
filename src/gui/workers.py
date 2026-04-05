"""Async worker threads for running tasks without blocking the UI."""
from PySide6.QtCore import QThread, Signal


class Worker(QThread):
    """Generic worker thread for running any callable without blocking UI."""

    finished = Signal(object)  # Result of the callable
    error = Signal(str)        # Error message string
    progress = Signal(str)     # Progress message string

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
