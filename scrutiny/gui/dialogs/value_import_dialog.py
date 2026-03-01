#    value_upload_status_dialog.py
#        A dialog that makes the value import and gives the user a progress of each element
#        individually
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ValueImportDialog']

import functools
import enum
import logging
from dataclasses import dataclass

from PySide6.QtGui import QCloseEvent, QContextMenuEvent
from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QMenu,
                               QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView)
from PySide6.QtCore import Qt, QSize

from scrutiny.gui.core.serializable_value_set import SerializableValueSet
from scrutiny.gui.core.watchable_registry import WatchableRegistry, ParsedFullyQualifiedName, WatchableRegistryError
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.widgets.watchable_tree import get_watchable_icon
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.sdk.client import ScrutinyClient
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.gui.widgets import mixins as gui_mixins
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *
from scrutiny import tools


class Columns:
    PATH = 0
    STATUS = 1


class WriteStatus(enum.Enum):
    Pending = enum.auto()
    Success = enum.auto()
    Failed = enum.auto()


@dataclass(slots=True)
class ProgressStats:
    """The stats of the actual import operation"""
    pending: int = 0
    success: int = 0
    failed: int = 0

    def total(self) -> int:
        return self.pending + self.success + self.failed

    def add_fail(self) -> None:
        if self.pending > 0:
            self.pending -= 1
            self.failed += 1

    def add_success(self) -> None:
        if self.pending > 0:
            self.pending -= 1
            self.success += 1


VALUE_TO_WRITE_ROLE = Qt.ItemDataRole.UserRole + 1
"""Role used to store the value requested by the user on the path item"""


class StatusItem(QTableWidgetItem):
    """A TableViewItem that contains the upload status (pending / success / Failed)"""

    @tools.copy_type(QTableWidgetItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.set_status(WriteStatus.Pending)

    def set_status(self, status: WriteStatus, msg: str = "") -> None:
        if len(msg) > 0:
            msg = f" : {msg}"

        if status == WriteStatus.Pending:
            self.setText(f"Pending{msg}")
            self.setData(Qt.ItemDataRole.DecorationRole, None)  # setIcon interface does not want None
        elif status == WriteStatus.Success:
            self.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.Success))
            self.setText(f"Success{msg}")
        elif status == WriteStatus.Failed:
            self.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.Error))
            self.setText(f"Failed{msg}")


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


class StatsWidget(QWidget):
    """Widget displaying the progress stats"""
    lbl_pending: QLabel
    lbl_success: QLabel
    lbl_failed: QLabel

    def __init__(self) -> None:
        super().__init__()
        self.lbl_pending = QLabel()
        self.lbl_success = QLabel()
        self.lbl_failed = QLabel()

        layout = QFormLayout(self)
        layout.addRow("Pending: ", self.lbl_pending)
        layout.addRow("Success: ", self.lbl_success)
        layout.addRow("Failed: ", self.lbl_failed)

    def update_stats(self, stats: ProgressStats) -> None:
        self.lbl_pending.setText(str(stats.pending))
        self.lbl_success.setText(str(stats.success))
        self.lbl_failed.setText(str(stats.failed))


class UploadTable(QTableWidget):
    """QTableWidget displaying all the values to be updated"""

    @tools.copy_type(QTableWidget.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Element", "Status"])
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(True)
        header = self.horizontalHeader()
        header.setSectionResizeMode(Columns.PATH, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(Columns.STATUS, QHeaderView.ResizeMode.ResizeToContents)
        self.setStyleSheet(r"QTableView::item {padding: 0 10 0 5; }")

    def contextMenuEvent(self, e: QContextMenuEvent) -> None:
        items = [cast(PathItem, item) for item in self.selectedItems() if item.column() == Columns.PATH]
        paths = [item.get_path() for item in items]
        menu = QMenu()
        copy_path_action = gui_mixins.qmenu_add_copy_path_action(menu, paths)
        copy_path_action.setEnabled(len(paths) > 0)

        menu.exec(self.mapToGlobal(e.pos()), copy_path_action)


class ValueImportDialog(QDialog):
    """Dialog that writes every entry in a SerializableValueSet to the device via
    the ServerManager and displays the per-item write status (Pending / Success / Failed)."""

    _table: UploadTable
    """Scrollable table listing type, path and status for each entry"""
    _server_manager: ServerManager
    """The server manager"""
    _logger: logging.Logger
    """The logger"""
    _stats: ProgressStats
    """The count of pending / success / failed"""
    _btn_stop: QPushButton
    """Stop button"""
    _btn_close: QPushButton
    """Close button"""
    _stop_requested: bool
    """A flag triggered by a window exit stopping the import process"""
    _stats_widget: StatsWidget
    """A widget to display the progress stats"""
    _complete_summary_label: FeedbackLabel
    """A feedback label showing the import process summary once completed"""

    def __init__(self,
                 value_set: SerializableValueSet,
                 server_manager: ServerManager,
                 parent: Optional[QWidget] = None
                 ) -> None:
        super().__init__(parent)

        self.setWindowTitle("Import values")
        self._server_manager = server_manager
        self._logger = logging.getLogger(self.__class__.__name__)
        self._stats = ProgressStats()

        self._btn_stop = QPushButton("Stop")
        self._btn_close = QPushButton("Close")
        self._stop_requested = False
        self._stats_widget = StatsWidget()
        self._complete_summary_label = FeedbackLabel()

        def stop_slot() -> None:
            self._stop_requested = True

        self._btn_stop.clicked.connect(stop_slot)
        self._btn_close.clicked.connect(self.close)
        self._btn_stop.setEnabled(True)
        self._btn_close.setEnabled(False)

        self._table = UploadTable(self)

        btn_row = QWidget()
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        btn_row_layout.addWidget(self._btn_stop)
        btn_row_layout.addWidget(self._btn_close)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self._table)
        main_layout.addWidget(self._stats_widget)
        main_layout.addWidget(self._complete_summary_label)
        main_layout.addWidget(btn_row)

        self.resize(800, 600)

        self._populate_table(value_set)
        self._write_value(row=0)     # Trigger write chain

    def closeEvent(self, e: QCloseEvent) -> None:
        """Use this event to stop the import process"""
        self._stop_requested = True
        super().closeEvent(e)

    def _populate_table(self, value_set: SerializableValueSet) -> None:
        """Fill the table with one row per entry and immediately schedule each write.
        Store the value to be written in the Path item because the valueset is unordered"""
        items = list(value_set.to_dict().items())
        self._table.setRowCount(len(items))
        skipped = 0
        for i, (fqn, value) in enumerate(items):
            try:
                path_item = PathItem(fqn)
            except WatchableRegistryError as e:
                tools.log_exception(self._logger, e, "Invalid element Fully Qualified Name")
                continue
            path_item.setData(VALUE_TO_WRITE_ROLE, value)
            status_item = StatusItem()

            row = i - skipped
            self._table.setItem(row, Columns.PATH, path_item)
            self._table.setItem(row, Columns.STATUS, status_item)
            self._stats.pending += 1

        self._stats_widget.update_stats(self._stats)

    def _write_value(self, row: int) -> None:
        """Makes an API call to write the watchable"""
        if row >= self._table.rowCount():
            self._complete()    # Natural end
            return

        if self._stop_requested:    # User wants to stop
            for i in range(row, self._table.rowCount()):    # Pending becomes fail
                self._stats.add_fail()
                self._set_row_status(i, WriteStatus.Failed, "Stopped")
            self._complete()
            return

        path_item = cast(PathItem, self._table.item(row, Columns.PATH))
        assert path_item is not None
        value_to_write = path_item.data(VALUE_TO_WRITE_ROLE)
        start_write_next_row = functools.partial(self._write_value, row + 1)

        # Bad value, immediate fail. Require a corrupted file
        if not isinstance(value_to_write, (int, float, bool, str)):
            self._set_row_status(row, WriteStatus.Failed, "Invalid data type")
            self._stats.add_fail()
            invoke_later(start_write_next_row)
            return

        try:
            self._server_manager.schedule_client_request(
                user_func=functools.partial(self._ephemerous_thread_write_func, path_item.get_path(), value_to_write),
                ui_thread_callback=functools.partial(self._qt_thread_write_callback, row)
            )
        except Exception as e:
            self._set_row_status(row, WriteStatus.Failed, str(e))
            self._stats.add_fail()
            invoke_later(start_write_next_row)
            return

    def _ephemerous_thread_write_func(self, path: str, value: Union[int, bool, float, str], client: ScrutinyClient) -> None:
        """Executed in a background thread. Blocks until completion"""
        self._logger.debug(f"Write value ({value}) of {path}")
        client.write_watchable(path, value)

    def _qt_thread_write_callback(self, row: int, _val: None, error: Optional[Exception]) -> None:
        """Callback once the API call is unblocked"""
        if error is None:   # API call success
            self._set_row_status(row, WriteStatus.Success)
            self._stats.add_success()
        else:   # API call failed
            self._set_row_status(row, WriteStatus.Failed, str(error))
            self._stats.add_fail()

        self._stats_widget.update_stats(self._stats)
        invoke_later(functools.partial(self._write_value, row + 1))

    def _complete(self) -> None:
        """All watchables have been imported (or failed)"""
        self._stats_widget.update_stats(self._stats)
        self._btn_stop.setEnabled(False)
        self._btn_close.setEnabled(True)

        msg = f"{self._stats.success}/{self._stats.total()} values imported"
        if self._stats.success == self._stats.total():
            self._complete_summary_label.set_success(msg)
        else:
            self._complete_summary_label.set_warning(msg)

    def _set_row_status(self, row: int, status: WriteStatus, msg: str = "") -> None:
        """Helper to update a row status visually"""
        status_item = cast(StatusItem, self._table.item(row, Columns.STATUS))
        if status_item is not None:
            status_item.set_status(status, msg)
            self._table.resizeColumnToContents(Columns.STATUS)
