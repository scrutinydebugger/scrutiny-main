#    signal_throttler.py
#        A throttling mechanism for QT signals that could be fired too many times
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtCore import QObject, Signal, QTimer
from scrutiny.tools.typing import *


class SignalThrottler(QObject):
    triggered = Signal()
    _timer: QTimer

    def __init__(self, interval_ms: int, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pending = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._on_timeout)

    def request(self) -> None:
        if self._timer.isActive():
            self._pending = True
        else:
            self._timer.start()
            self.triggered.emit()

    def _on_timeout(self) -> None:
        if self._pending:
            self._pending = False
            self._timer.start()
            self.triggered.emit()
