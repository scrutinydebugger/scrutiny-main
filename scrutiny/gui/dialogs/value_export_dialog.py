#    value_export_dialog.py
#        A dialog that start a value gathering process for all the watchable given. Successively
#        watch them, wait for a value, report success/failure and unwatch them. Provides
#        a ValueSet object to be saved to a .scval file
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ValueExportDialog']

import logging
from dataclasses import dataclass
import time
import enum

from PySide6.QtWidgets import (QDialog, QWidget, QProgressBar, QVBoxLayout, QPushButton, QHBoxLayout, QLabel,
                               QFormLayout, QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox)
from PySide6.QtCore import Qt, QTimer, QObject, Signal
from PySide6.QtGui import QContextMenuEvent


from scrutiny import sdk
from scrutiny.gui.core.serializable_value_set import SerializableValueSet
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatcherNotFoundError, RegistryValueUpdate, WatchableRegistryError, ParsedFullyQualifiedName
from scrutiny.gui.widgets.watchable_tree import get_watchable_icon
from scrutiny.gui.widgets.scrutiny_qmenu import ScrutinyQMenu
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.gui.widgets import mixins as gui_mixins

from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.tools.global_counters import global_i64_counter

_BATCH_SIZE = 50
"""How many element we watch in parallel"""
_EXPIRE_TIMEOUT_SEC = 5
"""How long we wait before declaring a value as unavailable"""
_MAINTENANCE_INTERVAL_MS = 300
"""Rate at which we check for timeouts"""
_BATCH_OVERLAP_SIZE = 10
"""How many elements max can be in progress before we start the next batch. This being > 0 avoid blocking when a timeout occur."""


class ValueDownloadResult(enum.Enum):
    NotAvailable = enum.auto()
    """Value is not available. Either it is not in the registry, the server is not
    available or the server explicitly says it cannot give it (forbidden region or nullptr dereference)"""
    TimedOut = enum.auto()
    """We waited for too long. We gave up on getting a value"""
    CancelledByUser = enum.auto()
    """USer hit the cancel button"""
    Received = enum.auto()
    """Success: A value has been received."""


class StatusItem(QTableWidgetItem):
    """A TableViewItem that contains the upload status (pending / success / Failed)"""

    def __init__(self, result: ValueDownloadResult) -> None:
        super().__init__()

        self.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.set_status(result)

    def set_status(self, status: ValueDownloadResult, msg: str = "") -> None:
        if len(msg) > 0:
            msg = f" : {msg}"

        if status == ValueDownloadResult.NotAvailable:
            self.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.Error))
            self.setText(f"Value not available")
        elif status == ValueDownloadResult.TimedOut:
            self.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.Error))
            self.setText(f"Timed out")
        elif status == ValueDownloadResult.CancelledByUser:
            self.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.Error))
            self.setText(f"Cancelled")
        elif status == ValueDownloadResult.Received:
            self.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.Success))
            self.setText(f"Received")


class PathItem(QTableWidgetItem):
    """A TableViewItem that contains the watchable server path"""
    _parsed_fqn: ParsedFullyQualifiedName

    def __init__(self, fqn: str) -> None:
        self._parsed_fqn = WatchableRegistry.FQN.parse(fqn)
        super().__init__(get_watchable_icon(self._parsed_fqn.watchable_type), self._parsed_fqn.path)
        self.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.setToolTip(self._parsed_fqn.path)

    def get_path(self) -> str:
        return self._parsed_fqn.path


class ResultTableWidget(QTableWidget):

    class Columns:
        PATH = 0
        STATUS = 1

    _logger: logging.Logger

    def __init__(self, logger: logging.Logger) -> None:
        super().__init__()
        self._logger = logger
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Element", "Status"])
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        header = self.horizontalHeader()
        header.setSectionResizeMode(self.Columns.PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.Columns.STATUS, QHeaderView.ResizeMode.ResizeToContents)
        self.setStyleSheet(r"QTableView::item {padding: 0 10 0 5; }")

    def add_row(self, fqn: str, result: ValueDownloadResult) -> None:
        self.setRowCount(self.rowCount() + 1)
        row_index = self.rowCount() - 1

        try:
            path_item = PathItem(fqn)
        except WatchableRegistryError as e:
            tools.log_exception(self._logger, e, "Invalid element Fully Qualified Name")
            return

        status_item = StatusItem(result)

        self.setItem(row_index, self.Columns.PATH, path_item)
        self.setItem(row_index, self.Columns.STATUS, status_item)

    def contextMenuEvent(self, e: QContextMenuEvent) -> None:
        items = [cast(PathItem, item) for item in self.selectedItems() if item.column() == self.Columns.PATH]
        paths = [item.get_path() for item in items]
        menu = ScrutinyQMenu()
        copy_path_action = gui_mixins.qmenu_add_copy_path_action(menu, paths)
        copy_path_action.setEnabled(len(paths) > 0)

        menu.exec_and_disconnect_triggered(self.mapToGlobal(e.pos()), copy_path_action)


@dataclass(slots=True, init=False)
class ValueDownloadState:
    """A class containing the state variable related to a single watchable value download"""
    fqn: str
    """The Fully Qualified Name of the watchable"""
    value: Optional[Union[float, bool, int]]
    """The value gotten. ``None`` means N/A"""
    result: Optional[ValueDownloadResult]
    """The result (success or not) for this element. ``None`` means it is not finished yet. """
    started_timestamp: Optional[float]
    """Indicate when this element passed to InProgress state"""
    in_progress: bool
    """Tells if this watchable is actively being watched and waiting on a value from the server"""

    def __hash__(self) -> int:  # Hash function for pending set
        return hash(id(self)) ^ hash(self.fqn)

    def __init__(self, fqn: str) -> None:
        self.fqn = fqn
        self.value = None
        self.result = None
        self.in_progress = False
        self.started_timestamp = None

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
        """When there is something to show to the user"""
        stopped = Signal()
        """Gathering process stopped. Either naturally or by an explicit call to ``stop()``"""
        result_gotten = Signal(str, object)
        """Emitted each time we get a result"""

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
    _server_manager: ServerManager
    """the server manager"""
    _watcher_id: str
    """The watcher ID tha this class uses to watch an element"""
    _finished_gathering: bool
    """The watcher Id this dialog will use to register to the registry"""
    _maintenance_timer: QTimer
    """A timer to detect timeouts and clear stalled elements"""
    _signals: _Signals
    """The public signals"""

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
        self._server_manager = server_manager
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
        """Request to stop the gathering process.
        Any incomplete value download will be set as Finished with a result of ``CancelledByUser``"""
        if self.is_finished():
            return
        for state in self._fqn_to_state.values():
            if not state.is_finished():
                self._set_finished(state, ValueDownloadResult.CancelledByUser)
        self._maintenance_timer.stop()
        self._finished_gathering = True
        self._signals.stopped.emit()

    def is_finished(self) -> bool:
        """Tells if the gathering prrocess is completed"""
        return self._finished_gathering

    def cleanup(self) -> None:
        """Stop and unregister the watcher from the registry"""
        self._maintenance_timer.stop()

        unfinished_count = 0
        for state in self._fqn_to_state.values():
            if not state.is_finished():
                unfinished_count += 1
        if unfinished_count > 0:
            self._logger.error("Not all watchable we processed fully.")
        with tools.SuppressException(WatcherNotFoundError):   # Suppress if not registered
            self._watchable_registry.unregister_watcher(self._watcher_id)
        self._server_manager.signals.registry_changed.disconnect(self.stop)

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
        """Return the values gotten. Can be a partial result in case of failures.
        Raise a RuntimeError if the gathering process is not finished. Stop Signal must be sent to signal it is finished"""
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
        """Fetch the state object based on its fully Qualified Name"""
        return self._fqn_to_state[fqn]

    def _get_state_by_registry_id(self, registry_id: Union[str, int]) -> ValueDownloadState:
        """Fetch the state object based on the Watchable Registry ID"""
        fqn = self._registry_id_to_fqn[registry_id]
        return self._fqn_to_state[fqn]

    def _set_finished(self, state: ValueDownloadState, result: ValueDownloadResult) -> None:
        """Indicates that the value download process for a single element is finished, success or failure"""
        if state.is_finished():
            raise RuntimeError(f"Watchable {state.fqn} already finished. Cannot change the status")

        state.set_result(result)
        self._result_count[result] += 1
        if state in self._inprogress_set:
            self._inprogress_set.remove(state)
            self._watchable_registry.unwatch_fqn(self._watcher_id, state.fqn)
        self._signals.result_gotten.emit(state.fqn, result)

    def _set_inprogress(self, state: ValueDownloadState) -> None:
        """Sets an element in In Progress state. Starts watching this element and wait for the value.
        Sets the elements as NotAvailable if watching is not possible."""
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
        """Get all the ValueDownloadState that are presently being watched and waiting on their value."""
        return list(self._inprogress_set)

    def _value_update_callback(self, watcher_id: Union[str, int], updates: List[RegistryValueUpdate]) -> None:
        """Callback invoked by the registry when a value update is received from the server"""
        if self.is_finished():
            return

        for update in updates:
            state = self._get_state_by_registry_id(update.registry_id)
            if not state.is_finished():
                if update.sdk_update.value is None:
                    self._set_finished(state, ValueDownloadResult.NotAvailable)
                else:
                    state.value = update.sdk_update.value
                    self._set_finished(state, ValueDownloadResult.Received)

        # This condition is not necessary since we check inside _maybe_start_next_batch
        # but avoid unnecessary work load
        if self.count_inprogress() <= _BATCH_OVERLAP_SIZE:
            invoke_later(self._maybe_start_next_batch)

        self._signals.stats_changed.emit()

    def _unwatch_callback(self, watcher_id: Union[str, int], fqn: str, configuration: sdk.BriefWatchableConfiguration, registry_id: int) -> None:
        pass

    def _maybe_start_next_batch(self) -> None:
        """Start a new batch if it's time. This method should be called again and again until all data is completed."""
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
        """Periodic task to verify a timeout"""
        for state in self._get_inprogress_states():
            if state.is_expired():
                self._set_finished(state, ValueDownloadResult.TimedOut)

        if not self.is_finished():
            invoke_later(self._maybe_start_next_batch)

        self._signals.stats_changed.emit()


# endregion

class ValueExportDialog(QDialog):
    """A dialog that gather the values of a series of watchables.
    Upon exec, it register a watcher to the registry, wait for every update then exits.
    ValueExportDialog.get_value_set() can be called after exec to get the values gathered.

    In case of gathering failures (value not available, or time out), the user is prompted with Save/cancel choice.

    This dialog returns accept() if all the values are correctly received or if the user request to Save.
    Return a reject() if the user hits "Cancel"
    """

    _logger: logging.Logger
    """The logger"""
    _logic: ExportLogic
    """The export logic decoupled from the UI"""
    _progress_bar: QProgressBar
    """The UI progress bar"""
    _btn_cancel: QPushButton
    """Cancel button"""
    _btn_stop_save: QPushButton
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
    """A flag indicated if the download process is finished. Set once. Used to control the stop/save button state"""
    _result_table: ResultTableWidget
    """A table used to display failures"""

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

        self._result_table = ResultTableWidget(self._logger)
        self._logic.signals.result_gotten.connect(self._process_new_result)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_stop_save = QPushButton("Stop")
        self._lbl_count_received = QLabel()
        self._lbl_timedout_count = QLabel()
        self._lbl_unavailable_count = QLabel()
        self._lbl_count_total = QLabel()

        self._progress_bar = QProgressBar(
            minimum=0,
            maximum=self._logic.count_total(),
            orientation=Qt.Orientation.Horizontal,
            textVisible=True
        )

        btn_container = QWidget()
        btn_container_layout = QHBoxLayout(btn_container)
        btn_container_layout.addWidget(self._btn_cancel)
        btn_container_layout.addWidget(self._btn_stop_save)
        btn_container_layout.setContentsMargins(0, 0, 0, 0)
        btn_container_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        gb_result = QGroupBox("Failures")
        gb_result_layout = QVBoxLayout(gb_result)
        gb_result_layout.addWidget(self._result_table)

        gb_stat_label_container = QGroupBox("Stats")
        gb_stat_label_container_layout = QFormLayout(gb_stat_label_container)
        gb_stat_label_container_layout.addRow("Received", self._lbl_count_received)
        gb_stat_label_container_layout.addRow("Timed Out", self._lbl_timedout_count)
        gb_stat_label_container_layout.addRow("Unavailable", self._lbl_unavailable_count)
        gb_stat_label_container_layout.addRow("Total", self._lbl_count_total)

        layout = QVBoxLayout(self)
        layout.addWidget(gb_result)
        layout.addWidget(gb_stat_label_container)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._feedback_label)
        layout.addWidget(btn_container)

        self.finished.connect(self._logic.cleanup)
        self._btn_stop_save.clicked.connect(self._logic.stop)
        self._btn_cancel.clicked.connect(self._btn_cancel_slot)

        self._logic.signals.stats_changed.connect(self._update_ui_feedback)
        self._logic.signals.stopped.connect(self._stop_slot)

        self.setMinimumWidth(400)

        invoke_later(self._logic.start)  # Start the process later to let the UI show correctly without freezing

    def _process_new_result(self, fqn: str, result: ValueDownloadResult) -> None:
        """Called when the logic sets an element as "finished", success or failure"""
        if result == ValueDownloadResult.Received:  # We don't report successes
            return

        # Add a failure case to the table
        self._result_table.add_row(fqn, result)

    def _update_btn_stop_save(self) -> None:
        """Transform the Stop button into a Save button once the gathering process is finished. One-shot"""
        if not self._finished_processed:
            if self._logic.is_finished():
                self._btn_stop_save.clicked.disconnect(self._logic.stop)
                self._btn_stop_save.setText("Save")
                self._btn_stop_save.clicked.connect(self._btn_save_slot)
                self._finished_processed = True

    def _stop_slot(self) -> None:
        """Logic emitted a Stop signal. """
        self._update_btn_stop_save()

        if self._logic.count_received() == 0:
            self._feedback_label.set_error("No values could be fetched")
            self._btn_stop_save.setDisabled(True)
        elif self._logic.count_received() != self._logic.count_total():
            self._feedback_label.set_warning("Not all values were received")
        else:
            # self._logic.count_received() == self._logic.count_total()
            self.accept()

    def _btn_save_slot(self) -> None:
        """UIser clicked on Save button"""
        self.accept()

    def _btn_cancel_slot(self) -> None:
        """Stops the gathering process and reject the window. Will cause a cleanup and exit"""
        if not self._logic.is_finished():
            self._logic.stop()
        self.reject()

    def _update_ui_feedback(self) -> None:
        """Update the visual component based on the actual logic state. Report to the user how we're doing so far"""
        self._progress_bar.setValue(self._logic.count_finished())
        self._lbl_count_received.setText(str(self._logic.count_received()))
        self._lbl_timedout_count.setText(str(self._logic.count_timedout()))
        self._lbl_unavailable_count.setText(str(self._logic.count_not_available()))
        self._lbl_count_total.setText(str(self._logic.count_total()))

    def get_value_set(self) -> SerializableValueSet:
        """Extract the ValueSet from the logic. Raise if the logic is not finished gathering the data.
        Need a Stop to happen first.
        """
        return self._logic.get_value_set()
