__all__ = ['ValueExportDialog']

import logging
from dataclasses import dataclass
import time
import enum

from PySide6.QtWidgets import QDialog, QWidget, QProgressBar, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QFormLayout
from PySide6.QtCore import Qt, QTimer, QObject, Signal

from scrutiny import sdk
from scrutiny.gui.core.serializable_value_set import SerializableValueSet
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatcherNotFoundError, RegistryValueUpdate, WatchableRegistryError
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.tools.global_counters import global_i64_counter

_BATCH_SIZE = 50
_EXPIRE_TIMEOUT_SEC = 5
_MAINTENANCE_INTERVAL_MS = 300
_BATCH_OVERLAP_SIZE = 10


class ValueDownloadResult(enum.Enum):
    NotAvailable = enum.auto()
    TimedOut = enum.auto()
    CancelledByUser = enum.auto()
    Received = enum.auto()


@dataclass(slots=True, init=False)
class ValueDownloadState:
    fqn: str
    value: Optional[Union[float, bool, int]]
    result: Optional[ValueDownloadResult]
    started_timestamp: Optional[float]
    in_progress: bool

    def __hash__(self) -> int:  # Hash function for pending set
        return hash(id(self)) ^ hash(self.fqn)

    def __init__(self, fqn: str) -> None:
        self.fqn = fqn
        self.value = None
        self.result = None
        self.in_progress = False
        self.started_timestamp = None

    def value_available(self) -> bool:
        if not self.is_finished():
            return False

        return self.value is not None

    def set_in_progress(self) -> None:
        assert not self.in_progress
        assert not self.is_finished()
        self.started_timestamp = time.monotonic()
        self.in_progress = True

    def set_result(self, result: ValueDownloadResult) -> None:
        assert not self.is_finished()
        self.in_progress = False
        self.result = result

    def is_finished(self) -> bool:
        return self.result is not None

    def is_expired(self) -> bool:
        if self.started_timestamp is None:
            return False
        return time.monotonic() > self.started_timestamp + _EXPIRE_TIMEOUT_SEC


class ExportLogic:

    class _Signals(QObject):
        stats_changed = Signal()
        stopped = Signal()

    _logger: logging.Logger
    """The logger"""
    _fqn_list_in_order: List[str]
    """List of FQN given by the user, sorted alphabetically and without duplicates"""
    _fqn_list_cursor: int
    """A cursor to iterate the list of FQN"""
    _fqn_to_state: Dict[str, ValueDownloadState]
    """A dict mapping FQN to state var"""
    _registry_id_to_fqn: Dict[Union[int, str], str]
    """A dict mapping registry ID to FQN"""
    _result_count: Dict[ValueDownloadResult, int]
    """Keep count by result"""
    _inprogress_set: Set[ValueDownloadState]
    """A set of state var that are actively waiting for a value."""
    _watchable_registry: WatchableRegistry
    """The app Watchable Registry"""
    _watcher_id: str
    """The watcher ID tha this class uses to watch an element"""
    _finished_gathering: bool
    """The watcher Id this dialog will use to register to the registry"""
    _maintenance_timer: QTimer
    """A timer to detect timeouts and clear stalled elements"""
    _signals: _Signals

    def __init__(self,
                 fqn_list: List[str],
                 server_manager: ServerManager,
                 watchable_registry: WatchableRegistry,
                 logger: logging.Logger) -> None:
        self._watcher_id = self.__class__.__name__ + str(global_i64_counter())
        self._logger = logger
        self._fqn_to_state = {}
        self._registry_id_to_fqn = {}
        self._inprogress_set = set()
        self._watchable_registry = watchable_registry
        self._finished_gathering = False
        self._signals = self._Signals()

        self._maintenance_timer = QTimer()
        self._maintenance_timer.setInterval(_MAINTENANCE_INTERVAL_MS)
        self._maintenance_timer.timeout.connect(self._maintenance_timer_slot, Qt.ConnectionType.QueuedConnection)

        self._result_count = {}
        for r in ValueDownloadResult:
            self._result_count[r] = 0

        self._fqn_list_cursor = 0
        self._fqn_list_in_order = sorted(set(fqn_list))
        for fqn in self._fqn_list_in_order:
            if fqn not in self._fqn_to_state:
                self._fqn_to_state[fqn] = ValueDownloadState(fqn)

        # No clean handling if the content change while we are gathering. Just stop and report to the user.
        server_manager.signals.registry_changed.connect(self.stop)

# region Public
    @property
    def signals(self) -> _Signals:
        return self._signals

    def start(self) -> None:
        """Launch the gathering process"""
        self._watchable_registry.register_watcher(
            watcher_id=self._watcher_id,
            value_update_callback=self._value_update_callback,
            unwatch_callback=self._unwatch_callback,
        )
        self._maybe_start_next_batch()
        self._maintenance_timer.start()

    def stop(self) -> None:
        for state in self._fqn_to_state.values():
            if not state.is_finished():
                self._set_finished(state, ValueDownloadResult.CancelledByUser)
        self._maintenance_timer.stop()
        self._finished_gathering = True
        self._signals.stopped.emit()

    def is_finished(self) -> bool:
        return self._finished_gathering

    def cleanup(self) -> None:
        self._maintenance_timer.stop()

        for state in self._fqn_to_state.values():
            if not state.is_finished():
                print(state.fqn)        # TEMP TEMP TEMP
        with tools.SuppressException(WatcherNotFoundError):   # Suppress if not registered
            self._watchable_registry.unregister_watcher(self._watcher_id)

    def count_total(self) -> int:
        return len(self._fqn_list_in_order)

    def count_timedout(self) -> int:
        return self._result_count[ValueDownloadResult.TimedOut]

    def count_not_available(self) -> int:
        return self._result_count[ValueDownloadResult.NotAvailable]

    def count_inprogress(self) -> int:
        return len(self._inprogress_set)

    def count_finished(self) -> int:
        return sum([n for n in self._result_count.values()])

    def count_notstarted(self) -> int:
        return self.count_total() - self.count_finished() - self.count_inprogress()

    def count_received(self) -> int:
        return self._result_count[ValueDownloadResult.Received]

    def get_value_set(self) -> SerializableValueSet:
        if not self.is_finished():
            raise RuntimeError("No ValueSet available. Data did not finished gathering")

        value_set = SerializableValueSet()
        for state in self._fqn_to_state.values():
            assert state.is_finished()
            if state.value is not None:  # Invalid value (nullptr or forbidden)
                value_set.add(state.fqn, state.value)
        return value_set

# endregion


# region Private


    def _get_state_by_fqn(self, fqn: str) -> ValueDownloadState:
        return self._fqn_to_state[fqn]

    def _get_state_by_registry_id(self, registry_id: Union[str, int]) -> ValueDownloadState:
        fqn = self._registry_id_to_fqn[registry_id]
        return self._fqn_to_state[fqn]

    def _set_finished(self, state: ValueDownloadState, result: ValueDownloadResult) -> None:
        if state.is_finished():
            raise RuntimeError(f"Watchable {state.fqn} already finished. Cannot change the status")

        state.set_result(result)
        self._result_count[result] += 1
        if state in self._inprogress_set:
            self._inprogress_set.remove(state)
            self._watchable_registry.unwatch_fqn(self._watcher_id, state.fqn)

    def _set_inprogress(self, state: ValueDownloadState) -> None:
        if state.is_finished():
            raise RuntimeError(f"Watchable {state.fqn} already finished. Cannot change the status")

        try:
            registry_id = self._watchable_registry.watch_fqn(self._watcher_id, state.fqn)
        except WatchableRegistryError as e:
            tools.log_exception(self._logger, e, f"Failed to request a value for {state.fqn}", str_level=logging.WARNING)
            self._set_finished(state, ValueDownloadResult.NotAvailable)
            return

        if registry_id in self._registry_id_to_fqn:
            raise RuntimeError(f"Duplicate registry ID for FQN : {state.fqn}")
        self._registry_id_to_fqn[registry_id] = state.fqn
        state.set_in_progress()
        self._inprogress_set.add(state)

    def _get_inprogress_states(self) -> List[ValueDownloadState]:
        return list(self._inprogress_set)

    def _value_update_callback(self, watcher_id: Union[str, int], updates: List[RegistryValueUpdate]) -> None:
        if self.is_finished():
            return

        to_unwatch_fqn: Set[str] = set()
        for update in updates:
            state = self._get_state_by_registry_id(update.registry_id)
            if not state.is_finished():
                if update.sdk_update.value is None:
                    self._set_finished(state, ValueDownloadResult.NotAvailable)
                else:
                    state.value = update.sdk_update.value
                    self._set_finished(state, ValueDownloadResult.Received)

        for fqn in to_unwatch_fqn:
            self._watchable_registry.unwatch_fqn(self._watcher_id, fqn)

        # This condition is not necessary since we check inside _maybe_start_next_batch
        # but avoid unnecessary work load
        if self.count_inprogress() <= _BATCH_OVERLAP_SIZE:
            invoke_later(self._maybe_start_next_batch)

        self._signals.stats_changed.emit()

    def _unwatch_callback(self, watcher_id: Union[str, int], fqn: str, configuration: sdk.BriefWatchableConfiguration, registry_id: int) -> None:
        pass

    def _maybe_start_next_batch(self) -> None:
        """Start a new batch"""
        self._check_completion()    # will latch _finished_gathering=True if we're done

        if self.is_finished():    # Nothing to do anymore
            return

        # If we still have too many in the pipeline, wait
        if self.count_inprogress() > _BATCH_OVERLAP_SIZE:
            return

        batch_end = min(self._fqn_list_cursor + _BATCH_SIZE, len(self._fqn_list_in_order))
        while self._fqn_list_cursor < batch_end:
            fqn = self._fqn_list_in_order[self._fqn_list_cursor]
            self._set_inprogress(self._fqn_to_state[fqn])   # Set to N/A if watching fails.
            self._fqn_list_cursor += 1

        if self.count_inprogress() < _BATCH_OVERLAP_SIZE:
            invoke_later(self._maybe_start_next_batch)

    def _check_completion(self) -> None:
        """Check if we are done gathering and either save or prompt the user"""
        if self.is_finished():
            return

        if self.count_finished() >= len(self._fqn_list_in_order):
            self.stop()

    def _maintenance_timer_slot(self) -> None:
        for state in self._get_inprogress_states():
            if state.is_expired():
                self._set_finished(state, ValueDownloadResult.TimedOut)

        if not self.is_finished():
            invoke_later(self._maybe_start_next_batch)

        self._signals.stats_changed.emit()


# endregion

class ValueExportDialog(QDialog):
    """The watchable registry"""
    _logger: logging.Logger
    """The logger"""
    _logic: ExportLogic
    """The export logic decoupled from the UI"""

    _progress_bar: QProgressBar
    """The UI progress bar"""
    _btn_cancel: QPushButton
    """Cancel button"""
    _btn_stop: QPushButton
    """Stop button"""
    _feedback_label: FeedbackLabel
    """A label to give feedback to the user about the state of the process"""
    _lbl_count_received: QLabel
    "A label to show the number of values we successfully have received"
    _lbl_timedout_count: QLabel
    """A label to show how many values we failed to get. (timeout or user cancelled.)"""
    _lbl_unavailable_count: QLabel
    """A label to show how many values were simply unavailable for fetching (device gone or SFD unloaded)."""
    _lbl_count_total: QLabel
    """A label to show the total number of values requested"""
    _finished_processed: bool

    def __init__(self,
                 watchable_registry: WatchableRegistry,
                 server_manager: ServerManager,
                 export_fqn_list: List[str],
                 parent: Optional[QWidget] = None
                 ) -> None:
        super().__init__(parent)
        self._logger = logging.getLogger(self.__class__.__name__)

        self._logic = ExportLogic(
            fqn_list=export_fqn_list,
            watchable_registry=watchable_registry,
            server_manager=server_manager,
            logger=self._logger)
        self._feedback_label = FeedbackLabel()
        self._finished_processed = False

        self._btn_cancel = QPushButton("Cancel")
        self._btn_stop_save = QPushButton("Stop")
        self._lbl_count_received = QLabel()
        self._lbl_timedout_count = QLabel()
        self._lbl_unavailable_count = QLabel()
        self._lbl_count_total = QLabel()

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
        stat_label_container_layout.addRow("Received", self._lbl_count_received)
        stat_label_container_layout.addRow("Timed Out", self._lbl_timedout_count)
        stat_label_container_layout.addRow("Unavailable", self._lbl_unavailable_count)
        stat_label_container_layout.addRow("Total", self._lbl_count_total)

        layout = QVBoxLayout(self)
        layout.addWidget(stat_label_container)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._feedback_label)
        layout.addWidget(btn_container)

        self.finished.connect(self._logic.cleanup)
        self._btn_stop_save.clicked.connect(self._btn_stop_slot)
        self._btn_cancel.clicked.connect(self._btn_cancel_slot)

        self._logic.signals.stats_changed.connect(self._update_ui_feedback)
        self._logic.signals.stopped.connect(self._stop_slot)

        invoke_later(self._logic.start)  # Start the process later to let the UI show correctly without freezing

    def _update_btn_stop_save(self) -> None:
        if not self._finished_processed:
            if self._logic.is_finished():
                self._btn_stop_save.clicked.disconnect(self._btn_stop_slot)
                self._btn_stop_save.setText("Save")
                self._btn_stop_save.clicked.connect(self._btn_save_slot)
            self._finished_processed = True

    def _process_stop(self) -> None:
        self._update_btn_stop_save()

        if self._logic.count_received() == 0:
            self._feedback_label.set_error("No values could be fetched")
            self._btn_stop_save.setDisabled(True)
        elif self._logic.count_received() != self._logic.count_total():
            self._feedback_label.set_warning("Not all values were received")
        elif self._logic.count_received() == self._logic.count_total():
            self.accept()

    def _stop_slot(self) -> None:
        self._process_stop()

    def _btn_stop_slot(self) -> None:
        """Stop gathering. Leave the window open. Leave the opportunity to the user to save partial results"""
        self._logic.stop()
        self._process_stop()

    def _btn_save_slot(self) -> None:
        self.accept()

    def _btn_cancel_slot(self) -> None:
        """Stops the gathering process and reject the window. Will cause a cleanup and exit"""
        if not self._logic.is_finished():
            self._logic.stop()
        self.reject()

    def _update_ui_feedback(self) -> None:
        self._progress_bar.setValue(self._logic.count_finished())
        self._lbl_count_received.setText(str(self._logic.count_received()))
        self._lbl_timedout_count.setText(str(self._logic.count_timedout()))
        self._lbl_unavailable_count.setText(str(self._logic.count_not_available()))
        self._lbl_count_total.setText(str(self._logic.count_total()))

    def get_value_set(self) -> SerializableValueSet:
        return self._logic.get_value_set()
