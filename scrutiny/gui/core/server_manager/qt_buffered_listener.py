from scrutiny import sdk
import threading
import time
import logging
import queue
import enum
from copy import copy
from dataclasses import dataclass

from PySide6.QtCore import Signal, QObject
import shiboken6

from scrutiny.sdk.listeners import BaseListener, ValueUpdate
from scrutiny.gui.core.user_messages_manager import UserMessagesManager
from scrutiny.gui.core.threads import QT_THREAD_NAME, SERVER_MANAGER_THREAD_NAME
from scrutiny.gui.tools.invoker import invoke_in_qt_thread_synchronized, invoke_later
from scrutiny import tools
from scrutiny.tools.thread_enforcer import thread_func, enforce_thread
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny.tools.typing import *
from scrutiny.gui.app_settings import app_settings

USER_MSG_UPDATE_OVERRUN = "listener_update_dropped"

class QtBufferedListener(BaseListener):
    """A listener that can plug into the SDK. This listener receives the updates from the server and buffers them in a queue.
    A signal is emitted when new data is received to tell the UI to come read the queue. The signal is only emitted when the
    UI is ready to receive it for natural derating on update speed if the CPU is overloaded"""

    MAX_SIGNALS_PER_SEC = 15
    """Maximum number of ``data_received`` QT signals this listener is allowed to emit per seconds.
    Prevent overflowing the event loop"""
    TARGET_PROCESS_INTERVAL = 0.2
    """Delay between 2 calls to ``process()``. Override ``BaseListener`` value"""

    class _Signals(QObject):
        data_received = Signal()

    to_gui_thread_queue: "queue.Queue[List[ValueUpdate]]"
    """A queue to transfer the value updates to the GUI thread"""
    signals: _Signals
    """The signals that this listener can emit"""
    last_signal_perf_cnt_ns: int
    """Timestamp of the last signal being sent"""
    minimal_inter_signal_delay_ns: int = int(1e9 / MAX_SIGNALS_PER_SEC)
    """Minimal amount of time between two data_received signals"""
    emit_allowed: bool
    """Flag preventing overflowing the event loop if the GUI thread is overloaded"""
    update_dropped_count: int
    """A counter that keeps track of how many value updates were lost during this session"""
    _last_drop_message_monotonic_time: Optional[float]
    """A timestamp used to avoid spamming the logger/messaging system when the queue overflows"""

    def __init__(self, *args: Any, **kwargs: Any):
        BaseListener.__init__(self, *args, **kwargs)
        self.to_gui_thread_queue = queue.Queue(maxsize=1000)    # Full load test peaks at 50
        self.signals = self._Signals()
        self.last_signal_perf_cnt_ns = time.perf_counter_ns()
        self.emit_allowed = True
        self.qt_event_rate_measurement = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=0.1)
        self.update_dropped_count = 0
        self._last_drop_message_monotonic_time = None

    def setup(self) -> None:
        self.update_dropped_count = 0
        self.qt_event_rate_measurement.enable()
        self.emit_allowed = True

    def teardown(self) -> None:
        self.emit_allowed = False
        self.qt_event_rate_measurement.disable()

    def ready_for_next_update(self) -> None:
        self.emit_allowed = True

    def _emit_signal_if_possible(self) -> None:
        tnow = time.perf_counter_ns()
        tdiff = tnow - self.last_signal_perf_cnt_ns
        expired = tdiff >= self.minimal_inter_signal_delay_ns or tdiff < 0  # Unclear if that counter can wrap. being careful here
        if expired and self.emit_allowed:
            self.qt_event_rate_measurement.add_data(1)
            self.last_signal_perf_cnt_ns = tnow
            self.emit_allowed = False
            # The signal is created in the main thread, but used in the listener thread
            # Even very improbable, there is a slight time window where
            # this signal can be deleted before teardown is called. So suppress the exception for normal operation
            with tools.LogException(self._logger, RuntimeError, "Failed to emit", str_level=logging.DEBUG, traceback_level=logging.DEBUG):
                self.signals.data_received.emit()

    def receive(self, updates: List[ValueUpdate]) -> None:
        try:
            self.to_gui_thread_queue.put(updates.copy(), block=False)
        except queue.Full:
            self.update_dropped_count += 1
            if self._last_drop_message_monotonic_time is None or time.monotonic() - self._last_drop_message_monotonic_time > 1:
                msg = f"Value update overrun. Total lost: {self.update_dropped_count} updates"
                self._logger.error(msg)
                UserMessagesManager.instance().register_message_thread_safe(USER_MSG_UPDATE_OVERRUN, msg, 3)
                self._last_drop_message_monotonic_time = time.monotonic()

        self._emit_signal_if_possible()

    def process(self) -> None:
        # Slow call rate. Called at rate defined by TARGET_PROCESS_INTERVAL
        if self.gui_qsize > 0:
            self._emit_signal_if_possible()  # Prune any remaining content if the server stops broadcasting
        self.qt_event_rate_measurement.update()

    def allow_subscription_changes_while_running(self) -> bool:
        return True

    @property
    def gui_qsize(self) -> int:
        """Return the number of value updates presently stored in the queue linking the listener thread and the QT GUI thread."""
        return self.to_gui_thread_queue.qsize()

    @property
    def effective_event_rate(self) -> float:
        """Returned the measured rate at which the ``data_received`` signal is being emitted"""
        return self.qt_event_rate_measurement.get_value()
