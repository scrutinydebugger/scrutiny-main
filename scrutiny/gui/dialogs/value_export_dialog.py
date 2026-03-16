__all__ = ['ValueExportDialog']

import logging
from dataclasses import dataclass
import time

from PySide6.QtWidgets import QDialog, QWidget, QProgressBar, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QFormLayout
from PySide6.QtCore import Qt, QTimer

from scrutiny import sdk
from scrutiny.gui.core.serializable_value_set import SerializableValueSet
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatcherNotFoundError, RegistryValueUpdate
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.tools.global_counters import global_i64_counter

_BATCH_SIZE = 50
_EXPIRE_TIMEOUT_SEC = 5
_MAINTENANCE_INTERVAL = 300
_BATCH_OVERLAP_SIZE = 10


@dataclass(slots=True)
class ProgressStats:
    received: int = 0
    """Number of watchable with a valid value received"""
    cancelled: int = 0
    """Number of watchable for which we gave up getting a value (timeout)"""

    def total(self) -> int:
        return self.received + self.cancelled


@dataclass(slots=True, init=False)
class WatchableState:
    def __hash__(self) -> int:  # Hash function for pending set
        return hash(id(self)) ^ hash(self.fqn)

    def __init__(self, fqn: str) -> None:
        self.fqn = fqn
        self.value = None
        self.value_received = False
        self.cancelled = False
        self.register_timestamp = time.monotonic()

    fqn: str
    value: Optional[Union[float, bool, int]]
    value_received: bool
    cancelled: bool
    register_timestamp: float

    def cancel(self) -> None:
        self.cancelled = True

    def received(self) -> None:
        self.value_received = True

    def finished(self) -> bool:
        return self.value_received or self.cancelled

    def is_expired(self) -> bool:
        return time.monotonic() > self.register_timestamp + _EXPIRE_TIMEOUT_SEC


class ValueExportDialog(QDialog):
    _watchable_registry: WatchableRegistry
    """The watchable registry"""
    _logger: logging.Logger
    """The logger"""
    _watcher_id: str
    """The watcher Id this dialog will use to register to the registry"""
    _state_dict: Dict[Union[str, int], WatchableState]
    """A dict mapping fqn to a state object"""
    _finished_gathering: bool
    """A latch flag that indicates we are done"""
    _progress_stats: ProgressStats
    """Stats about gathering process (nbr received + cancelled)"""
    _pending_states: Set[WatchableState]
    """A set of state variable of all the watchables presently waiting for a value (actively watched)"""
    _progress_bar: QProgressBar
    """The UI progress bar"""
    _register_list_cusrsor: int
    """A cursor to iterate the user FQN list in batch"""
    _export_fqn_list: List[str]
    """The user provided FQN list"""
    _maintenance_timer: QTimer
    """A timer to detect timeouts and clear stalled elements"""
    _btn_cancel: QPushButton
    """Cancel button"""
    _btn_stop: QPushButton
    """Stop button"""
    _feedback_label: FeedbackLabel
    """A label to give feedback to the user about the state of the process"""
    _lbl_received_count: QLabel
    "A label to show the number of values we successfully have received"
    _lbl_cancelled_count: QLabel
    """A label to show how many values we failed to get. (timeout or user cancelled.)"""
    _lbl_total_count: QLabel
    """A label to show the total number of values requested"""

    def __init__(self,
                 watchable_registry: WatchableRegistry,
                 export_fqn_list: List[str],
                 parent: Optional[QWidget] = None
                 ) -> None:
        super().__init__(parent)
        self._watchable_registry = watchable_registry
        self._logger = logging.getLogger(self.__class__.__name__)
        self._watcher_id = self.__class__.__name__ + str(global_i64_counter())
        self._finished_gathering = False
        self._progress_stats = ProgressStats()
        self._pending_states = set()

        self._state_dict = {}
        self._register_list_cusrsor = 0
        self._maintenance_timer = QTimer()
        self._maintenance_timer.setInterval(_MAINTENANCE_INTERVAL)
        self._maintenance_timer.timeout.connect(self._maintenance_timer_slot, Qt.ConnectionType.QueuedConnection)
        self._feedback_label = FeedbackLabel()

        self._btn_cancel = QPushButton("Cancel")
        self._btn_stop_save = QPushButton("Stop")
        self._lbl_received_count = QLabel()
        self._lbl_cancelled_count = QLabel()
        self._lbl_total_count = QLabel()

        # remove duplicates and make a copy. sorting increase chance of agglomerated request on server side
        self._export_fqn_list = sorted(set(export_fqn_list))

        self._progress_bar = QProgressBar(
            minimum=0,
            maximum=len(export_fqn_list),
            orientation=Qt.Orientation.Horizontal,
            textVisible=True
        )
        self._progress_bar.setTextVisible(True)

        btn_container = QWidget()
        btn_container_layout = QHBoxLayout(btn_container)
        btn_container_layout.addWidget(self._btn_cancel)
        btn_container_layout.addWidget(self._btn_stop_save)
        btn_container_layout.setContentsMargins(0, 0, 0, 0)
        btn_container_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        stat_label_container = QWidget()
        stat_label_container_layout = QFormLayout(stat_label_container)
        stat_label_container_layout.addRow("Received", self._lbl_received_count)
        stat_label_container_layout.addRow("Cancelled", self._lbl_cancelled_count)
        stat_label_container_layout.addRow("Total", self._lbl_total_count)

        layout = QVBoxLayout(self)
        layout.addWidget(stat_label_container)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._feedback_label)
        layout.addWidget(btn_container)

        self.finished.connect(self._cleanup)
        self._btn_stop_save.clicked.connect(self._btn_stop_slot)
        self._btn_cancel.clicked.connect(self._btn_cancel_slot)
        invoke_later(self._start_gathering_process)  # Start the process later to let the UI show correctly without freezing

    def _start_gathering_process(self) -> None:
        """Launch the gathering process"""
        self._watchable_registry.register_watcher(
            watcher_id=self._watcher_id,
            value_update_callback=self._value_update_callback,
            unwatch_callback=self._unwatch_callback,
        )
        self._maybe_start_next_batch()
        self._maintenance_timer.start()

    def _btn_stop_slot(self) -> None:
        self._stop()

    def _stop(self) -> None:
        """Stop gathering. Leave the window open. Leave the opportunity to the user to save partial results"""
        self._finished_gathering = True

        for state in self._state_dict.values():
            if not state.finished():
                self._progress_stats.cancelled += 1
                state.cancel()

        self._update_ui_feedback()
        self._feedback_label.set_warning("Not all values were received")
        self._btn_stop_save.clicked.disconnect(self._btn_stop_slot)
        self._btn_stop_save.setText("Save")
        self._btn_stop_save.clicked.connect(self._btn_save_slot)

    def _btn_save_slot(self) -> None:
        self.accept()

    def _btn_cancel_slot(self) -> None:
        """Stops the gathering process and reject the window. Will cause a cleanup and exit"""
        self._finished_gathering = True
        self.reject()

    def _maybe_start_next_batch(self) -> None:
        """Start a new batch"""
        self._check_completion()    # will latch _finished_gathering=True if we're done

        if self._finished_gathering:    # Nothing to do anymore
            return

        # If we still have too many in the pipeline, wait
        if len(self._pending_states) > _BATCH_OVERLAP_SIZE:
            return

        batch_end = min(self._register_list_cusrsor + _BATCH_SIZE, len(self._export_fqn_list))
        while self._register_list_cusrsor < batch_end:
            fqn = self._export_fqn_list[self._register_list_cusrsor]
            self._register_list_cusrsor += 1
            try:
                registry_id = self._watchable_registry.watch_fqn(self._watcher_id, fqn)
                self._state_dict[registry_id] = WatchableState(fqn)
                self._pending_states.add(self._state_dict[registry_id])
            except Exception as e:
                tools.log_exception(self._logger, e, f"Failed to request a value for {fqn}")

    def _value_update_callback(self, watcher_id: Union[str, int], updates: List[RegistryValueUpdate]) -> None:
        if self._finished_gathering:
            return

        to_unwatch_fqn: Set[str] = set()
        for update in updates:
            state = self._state_dict[update.registry_id]
            if not state.value_received:
                self._progress_stats.received += 1
                state.received()
                self._pending_states.remove(state)
            state.value = update.sdk_update.value
            to_unwatch_fqn.add(state.fqn)

        self._update_ui_feedback()

        for fqn in to_unwatch_fqn:
            self._watchable_registry.unwatch_fqn(self._watcher_id, fqn)

        # This condition is not necessary since we check inside _maybe_start_next_batch
        # but avoid unnecessary work load
        if len(self._pending_states) <= _BATCH_OVERLAP_SIZE:
            invoke_later(self._maybe_start_next_batch)

    def _unwatch_callback(self, watcher_id: Union[str, int], fqn: str, configuration: sdk.BriefWatchableConfiguration, registry_id: int) -> None:
        pass

    def _update_ui_feedback(self) -> None:
        finished_count = self._progress_stats.cancelled + self._progress_stats.received
        self._progress_bar.setValue(finished_count)
        self._lbl_cancelled_count.setText(str(self._progress_stats.cancelled))
        self._lbl_received_count.setText(str(self._progress_stats.received))
        self._lbl_total_count.setText(str(self._progress_stats.total()))

    def _check_completion(self) -> None:
        """Check if we are done gathering and either save or prompt the suer"""
        total_processed = self._progress_stats.received + self._progress_stats.cancelled
        if total_processed >= len(self._export_fqn_list):
            if self._progress_stats.cancelled > 0:
                # Let the user save or cancel since we don't have everything he wants
                self._stop()
            else:
                # We got all the values successfully. Save right away
                self._finished_gathering = True
                invoke_later(self.accept)

    def _maintenance_timer_slot(self) -> None:
        for pending in list(self._pending_states):
            if pending.is_expired():
                self._pending_states.remove(pending)
                pending.cancel()
                self._progress_stats.cancelled += 1

        if not self._finished_gathering:
            invoke_later(self._maybe_start_next_batch)

    def _cleanup(self) -> None:
        for state in self._state_dict.values():
            if not state.value_received:
                print(state.fqn)
        with tools.SuppressException(WatcherNotFoundError):   # Suppress if not registered
            self._watchable_registry.unregister_watcher(self._watcher_id)
        self._maintenance_timer.stop()

    def get_value_set(self) -> SerializableValueSet:
        if not self._finished_gathering:
            raise RuntimeError("No ValueSet available. Data did not finished gathering")

        value_set = SerializableValueSet()
        for state in self._state_dict.values():
            assert state.finished()
            if state.value is not None:  # Invalid value (nullptr or forbidden)
                value_set.add(state.fqn, state.value)
        return value_set
