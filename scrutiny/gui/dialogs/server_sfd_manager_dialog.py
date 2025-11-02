#    server_sfd_manager_dialog.py
#        A dialog to manage the already installed Scrutiny Firmware Description files on the
#        server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ServerSFDManagerDialog']

import logging
import os

from PySide6.QtWidgets import QDialog, QWidget, QTableView, QVBoxLayout, QMenu, QMenuBar, QProgressBar, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, QAbstractItemModel, Signal, QObject, QPoint, QTimer
from PySide6.QtGui import QCloseEvent, QKeyEvent, QShowEvent, QStandardItemModel, QStandardItem, QContextMenuEvent, QAction

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient, SFDUploadRequest, SFDDownloadRequest
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.dialogs.sfd_content_dialog import SFDContentDialog
from scrutiny.gui.tools import prompt
from scrutiny.gui import assets

from scrutiny.tools.typing import *
from scrutiny import tools


class ReadOnlyStandardItem(QStandardItem):
    @tools.copy_type(QStandardItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.setEditable(False)


class SFDTableModel(QStandardItemModel):
    """The model used to display the list of SFD in a QTableView"""

    class Cols:
        PROJECT_NAME = 0
        FIRMWARE_ID = 1
        SCRUTINY_VERSION = 2
        CREATION_DATE = 3
        FILESIZE = 4

    NB_COLS = 5
    SFD_INFO_ROLE = Qt.ItemDataRole.UserRole + 5    # We will store the SFDInfo structure in the firmware ID col with this data role

    @tools.copy_type(QStandardItemModel.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.setColumnCount(self.NB_COLS)

        headers: List[str] = ["" for i in range(self.NB_COLS)]
        headers[self.Cols.PROJECT_NAME] = "Project"
        headers[self.Cols.FIRMWARE_ID] = "Firmware ID"
        headers[self.Cols.SCRUTINY_VERSION] = "Scrutiny Version"
        headers[self.Cols.CREATION_DATE] = "Created On"
        headers[self.Cols.FILESIZE] = "File Size"
        self.setHorizontalHeaderLabels(headers)

    def add_row(self, sfd_info: sdk.SFDInfo) -> int:
        """Add a single row to the QTableView"""
        row = [ReadOnlyStandardItem("N/A") for i in range(self.NB_COLS)]
        row[self.Cols.FIRMWARE_ID].setText(sfd_info.firmware_id)
        row[self.Cols.FIRMWARE_ID].setData(sfd_info, self.SFD_INFO_ROLE)    # Store the SFD info

        filesize_txt = "N/A"
        if sfd_info.filesize is not None:
            filesize_txt = tools.format_eng_unit(sfd_info.filesize, decimal=1, unit="B", binary=True)
        row[self.Cols.FILESIZE].setText(filesize_txt)

        if sfd_info.metadata is not None:
            if sfd_info.metadata.project_name is not None:
                project_name = sfd_info.metadata.project_name

                if sfd_info.metadata.version is not None:
                    project_name += f" {sfd_info.metadata.version}"
                row[self.Cols.PROJECT_NAME].setText(project_name)

            if sfd_info.metadata.generation_info is not None:
                if sfd_info.metadata.generation_info.scrutiny_version is not None:
                    row[self.Cols.SCRUTINY_VERSION].setText(f"Scrutiny {sfd_info.metadata.generation_info.scrutiny_version}")

                if sfd_info.metadata.generation_info.timestamp is not None:
                    format_str = gui_persistent_data.global_namespace().long_datetime_format()  # Take format from preferences
                    row[self.Cols.CREATION_DATE].setText(sfd_info.metadata.generation_info.timestamp.strftime(format_str))

        self.appendRow(row)
        return self.rowCount() - 1

    def remove_sfd_rows(self, firmware_ids: List[str]) -> None:
        """Remove several rows identified by firmware IDs"""
        i = 0
        firmware_ids_set = set(firmware_ids)
        while i < self.rowCount():
            firmware_id_item = self.item(i, self.Cols.FIRMWARE_ID)
            if firmware_id_item is None:
                break
            firmware_id = firmware_id_item.text()
            if firmware_id in firmware_ids_set:
                self.removeRow(i)
            else:
                i += 1


class SFDTableView(QTableView):
    """An extension of QTableView to display a list of SFD"""

    class _Signals(QObject):
        uninstall = Signal(object)
        save = Signal(object)
        show_details = Signal(object)

    _signals: _Signals

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._signals = self._Signals()
        self.setModel(SFDTableModel(self))
        self.setSortingEnabled(True)
        self._allow_save = True

    @property
    def signals(self) -> _Signals:
        return self._signals

    def setModel(self, model: Optional[QAbstractItemModel]) -> None:
        if not isinstance(model, SFDTableModel):
            raise ValueError("model must be a SFDTableModel")
        super().setModel(model)

    def model(self) -> SFDTableModel:
        return cast(SFDTableModel, super().model())

    def allow_save(self, val: bool) -> None:
        self._allow_save = val

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:

        menu = QMenu(self)
        uninstall_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Uninstall")
        save_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Download), "Save")
        details_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Info), "Details")

        firmware_id_indexes = [index for index in self.selectedIndexes() if index.isValid() and index.column() == SFDTableModel.Cols.FIRMWARE_ID]
        firmware_ids = [self.model().itemFromIndex(index).text() for index in firmware_id_indexes]

        def uninstall_action_slot() -> None:
            if len(firmware_ids) > 0:
                self._signals.uninstall.emit(firmware_ids)

        def save_action_slot() -> None:
            if len(firmware_ids) == 1:  # Only possible for a single selection
                assert len(firmware_id_indexes) == 1
                sfd_info = cast(sdk.SFDInfo, firmware_id_indexes[0].data(self.model().SFD_INFO_ROLE))
                assert isinstance(sfd_info, sdk.SFDInfo)
                self._signals.save.emit(sfd_info)

        def details_action_slot() -> None:
            if len(firmware_ids) == 1:  # Only possible for a single selection
                assert len(firmware_id_indexes) == 1
                sfd_info = cast(sdk.SFDInfo, firmware_id_indexes[0].data(self.model().SFD_INFO_ROLE))
                assert isinstance(sfd_info, sdk.SFDInfo)
                self._signals.show_details.emit(sfd_info)

        uninstall_action.triggered.connect(uninstall_action_slot)
        save_action.triggered.connect(save_action_slot)
        details_action.triggered.connect(details_action_slot)

        if len(firmware_ids) != 1:
            save_action.setDisabled(True)
            details_action.setDisabled(True)

        if len(firmware_ids) == 0:
            uninstall_action.setDisabled(True)

        if not self._allow_save:
            save_action.setDisabled(True)

        self.display_context_menu(menu, event.pos())

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            firmware_id_indexes = [index for index in self.selectedIndexes() if index.isValid() and index.column() == SFDTableModel.Cols.FIRMWARE_ID]
            firmware_ids = [self.model().itemFromIndex(index).text() for index in firmware_id_indexes]
            if len(firmware_ids) > 0:
                self._signals.uninstall.emit(firmware_ids)

        return super().keyPressEvent(event)

    def display_context_menu(self, menu: QMenu, pos: QPoint) -> None:
        """Display a menu at given relative position, and make sure it goes below the cursor to mimic what most people are used to"""
        actions = menu.actions()
        at: Optional[QAction] = None
        if len(actions) > 0:
            pos += QPoint(0, menu.actionGeometry(actions[0]).height())
            at = actions[0]
        menu.popup(self.mapToGlobal(pos), at)


class ProgressWidget(QWidget):
    """This widget show the transfer (upload or download) of a SFD progress state."""

    class _Signals(QObject):
        cancel = Signal()

    progress_bar: QProgressBar
    btn_cancel: QPushButton
    _update_timer: QTimer
    _read_progress_callback: Callable[[], float]
    _signals: _Signals

    def __init__(self, parent: QWidget, read_progress_callback: Callable[[], float]) -> None:
        super().__init__(parent)

        self._signals = self._Signals()
        self.progress_bar = QProgressBar(self, minimum=0, maximum=100, orientation=Qt.Orientation.Horizontal)
        self.btn_cancel = QPushButton("Cancel")
        self._update_timer = QTimer()
        self._update_timer.setInterval(200)
        self._read_progress_callback = read_progress_callback

        layout = QHBoxLayout(self)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.btn_cancel)

        self.btn_cancel.setMaximumWidth(75)
        self.btn_cancel.clicked.connect(self._signals.cancel)

        self._update_timer.timeout.connect(self._update_progress_bar_val)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def _update_progress_bar_val(self) -> None:
        val = self._read_progress_callback()
        val = val * (self.progress_bar.maximum() - self.progress_bar.minimum()) + self.progress_bar.minimum()
        val = int(round(val))
        self.progress_bar.setValue(val)

    def activate(self) -> None:
        self._update_progress_bar_val()
        self.progress_bar.setVisible(True)
        self.btn_cancel.setVisible(True)
        if not self._update_timer.isActive():
            self._update_timer.start()

    def deactivate(self) -> None:
        self.progress_bar.setVisible(False)
        self.btn_cancel.setVisible(False)
        self._update_timer.stop()
        self.progress_bar.setValue(self.progress_bar.minimum())


class ServerSFDManagerDialog(QDialog):
    class _InternalSignals(QObject):
        sfd_transfer_started = Signal(object)
        sfd_transfer_stopped = Signal()

    _internal_signals: _InternalSignals
    """A dialog to edit the list of installed Scrutiny Firmware Description files on the server"""
    _server_manager: ServerManager
    """The server manager to send request to the server"""
    _sfd_table: SFDTableView
    """The QTableView displaying the list of SFD installed"""
    _feedback_label: FeedbackLabel
    """A label to display errors"""
    _menubar: QMenuBar
    """The dialog top menu bar"""
    _install_action: QAction
    """The Install button in the menu bar"""
    _logger: logging.Logger
    """The logger"""
    _active_transfer_req: Optional[Union[SFDUploadRequest, SFDDownloadRequest]]
    _progress_widget: ProgressWidget

    def __init__(self, parent: QWidget, server_manager: ServerManager) -> None:
        super().__init__(parent)
        self.setWindowTitle("Server SFDs")
        self.setMinimumSize(600, 400)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint)

        self._server_manager = server_manager
        self._menubar = QMenuBar(self)
        install_menu = self._menubar.addMenu("Install")
        self._install_action = install_menu.addAction("Browse")
        self._active_transfer_req = None

        def read_progress() -> float:
            if self._active_transfer_req is None:
                return 0
            return self._active_transfer_req.get_progress()
        self._progress_widget = ProgressWidget(self, read_progress)

        def cancel_progress_slot() -> None:
            if self._active_transfer_req is not None:
                self._active_transfer_req.cancel()
        self._progress_widget.signals.cancel.connect(cancel_progress_slot)

        self._logger = logging.getLogger(self.__class__.__name__)
        self._feedback_label = FeedbackLabel()
        self._sfd_table = SFDTableView(self)
        self._sfd_table.verticalHeader().hide()
        self._sfd_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._sfd_table.setSizeAdjustPolicy(QTableView.SizeAdjustPolicy.AdjustToContents)

        self._sfd_table.signals.uninstall.connect(self._uninstall_sfds_slot)
        self._sfd_table.signals.save.connect(self._save_sfd_slot)
        self._sfd_table.signals.show_details.connect(self._show_sfd_details_slot)
        self._install_action.triggered.connect(self._install_sfd_click_slot)

        content = QWidget()

        layout = QVBoxLayout(content)
        layout.addWidget(self._feedback_label)
        layout.addWidget(self._sfd_table)
        layout.addWidget(self._progress_widget)

        menubar_layout = QVBoxLayout(self)
        menubar_layout.setContentsMargins(0, 0, 0, 0)
        menubar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        menubar_layout.addWidget(self._menubar)
        menubar_layout.addWidget(content)

        self._internal_signals = self._InternalSignals()
        self._internal_signals.sfd_transfer_started.connect(self.set_transfer_active)
        self._internal_signals.sfd_transfer_stopped.connect(self.set_transfer_inactive)

        # Update the status of the window when the server comes and go
        self._server_manager.signals.server_connected.connect(self.connect_disconnect)
        self._server_manager.signals.server_disconnected.connect(self.connect_disconnect)
        self._set_disconnected()

    def _set_connected(self) -> None:
        """Enables the window when the server is connected"""
        self._install_action.setEnabled(True)
        self._feedback_label.clear()
        self.download_sfd_list()

    def _set_disconnected(self) -> None:
        """Disable the window content when the server is disconnected"""
        self._install_action.setDisabled(True)
        self._feedback_label.clear()
        self.set_transfer_inactive()
        self.clear_sfd_list()

    def _uninstall_sfds_slot(self, firmware_ids: List[str]) -> None:
        """Called when right click an SFD and select "uninstall """
        if self._server_manager.get_server_state() != sdk.ServerState.Connected:
            return

        result = prompt.warning_yes_no_question(self, f"Are you sure you want to uninstall {len(firmware_ids)} SFD from the server?", "Are you sure?")
        if not result:
            return

        # Let's send a request to the server for uninstalling the selected SFD
        self._feedback_label.clear()

        def ephemerous_thread_request_uninstall(client: ScrutinyClient) -> None:
            client.uninstall_sfds(firmware_ids)  # Blocking request

        def ui_thread_uninstall_complete(response: None, error: Optional[Exception]) -> None:
            if error is not None:
                self._feedback_label.set_error(str(error))
                tools.log_exception(self._logger, error, "Failed to uninstall SFDs")
                return
            # Success. Let's update the UI
            self._feedback_label.clear()
            self._sfd_table.model().remove_sfd_rows(firmware_ids)
            nb_sfd = len(firmware_ids)
            self._feedback_label.set_success(f"Uninstalled {nb_sfd} Scrutiny Firmware Description (SFD) files.")

        self._server_manager.schedule_client_request(
            user_func=ephemerous_thread_request_uninstall,
            ui_thread_callback=ui_thread_uninstall_complete
        )

    def _save_sfd_slot(self, sfd_info: sdk.SFDInfo) -> None:
        """Called when right click an SFD and select "save """
        if self._server_manager.get_server_state() != sdk.ServerState.Connected:
            return

        if self.is_transfer_active():
            return

        def ephemerous_thread_request_download(client: ScrutinyClient) -> bytes:
            req = client.download_sfd(sfd_info.firmware_id)
            self._internal_signals.sfd_transfer_started.emit(req)
            req.wait_for_completion()   # Blocking call
            return req.get()

        def ui_thread_download_complete(data: Optional[bytes], error: Optional[Exception]) -> None:
            self._internal_signals.sfd_transfer_stopped.emit()
            if error is not None:
                self._feedback_label.set_error(str(error))
                tools.log_exception(self._logger, error, "Failed to download SFDs")
                return
            # Success, Let's update the UI
            self._feedback_label.clear()

            assert data is not None
            default_name = self._make_sfd_default_name(sfd_info)
            save_path = prompt.get_save_filepath_from_last_save_dir(self, ".sfd", "Save SFD", default_name=default_name)
            if save_path is not None:
                try:
                    with open(save_path, 'wb') as f:
                        f.write(data)
                    self._feedback_label.set_success(f"SFD saved to {save_path}")
                except Exception as e:
                    self._feedback_label.set_error(f"Failed to save. {e}")
                    tools.log_exception(self._logger, e, f"Failed to save SFD to {save_path}")

        self._server_manager.schedule_client_request(
            user_func=ephemerous_thread_request_download,
            ui_thread_callback=ui_thread_download_complete
        )

    def _show_sfd_details_slot(self, sfd_info: sdk.SFDInfo) -> None:
        """Called when right click an SFD and select "Details """
        dialog = SFDContentDialog(self, sfd_info)
        dialog.show()

    def _make_sfd_default_name(self, sfd_info: sdk.SFDInfo) -> str:
        """Makes a default filename from the SFDInfo structure."""

        EXTENSION = '.sfd'
        if sfd_info.metadata is None:
            return sfd_info.firmware_id + EXTENSION

        if sfd_info.metadata.project_name is None:
            return sfd_info.firmware_id + EXTENSION

        project_name = sfd_info.metadata.project_name
        if sfd_info.metadata.version is not None:
            project_name += f'V{sfd_info.metadata.version}'

        return f"{project_name} ({sfd_info.firmware_id})" + EXTENSION

    def _install_sfd_click_slot(self) -> None:
        """Top menu bar: Install -> Browse"""
        if self._server_manager.get_server_state() != sdk.ServerState.Connected:
            return

        if self.is_transfer_active():
            return

        filepath = prompt.get_open_filepath_from_last_save_dir(self, ".sfd", "Scrutiny Firmware Description")
        if filepath is None:
            return

        def ephemerous_thread_upload_init(client: ScrutinyClient) -> SFDUploadRequest:
            return client.init_sfd_upload(filepath)

        def ui_thread_upload_init_completed(req: Optional[SFDUploadRequest], error: Optional[Exception]) -> None:
            if error is not None:
                self._feedback_label.set_error(str(error))
                tools.log_exception(self._logger, error, "Failed to install SFDs")
                return

            assert req is not None

            proceed = True
            if req.will_overwrite:
                proceed = prompt.warning_yes_no_question(
                    parent=self,
                    msg="Installing this file will overwrite an existing SFD on the server that shares the same firmware ID. Proceed?",
                    title="Proceed?"
                )

            if not proceed:
                self._feedback_label.clear()
                return

            self._internal_signals.sfd_transfer_started.emit(req)

            def ephemerous_thread_upload(client: ScrutinyClient) -> SFDUploadRequest:
                req.start()
                req.wait_for_completion()
                return req

            def ui_thread_upload_complete(data: Optional[SFDUploadRequest], error: Optional[Exception]) -> None:
                self._internal_signals.sfd_transfer_stopped.emit()
                if error is not None:
                    self._feedback_label.set_error(str(error))
                    tools.log_exception(self._logger, error, "Failed to install SFDs")
                    return

                assert data is not None
                self._feedback_label.clear()
                self._sfd_table.model().remove_sfd_rows([data.firmware_id])
                sfd_info = req.get_sfd_info()
                row_number = self._sfd_table.model().add_row(sfd_info)  # Append a row
                self._sfd_table.selectRow(row_number)   # Select inserted row (last one)

                prompt.success_msgbox(self, "Installed", f"Installed SFD {data.firmware_id}")

            self._server_manager.schedule_client_request(
                user_func=ephemerous_thread_upload,
                ui_thread_callback=ui_thread_upload_complete
            )

        self._server_manager.schedule_client_request(
            user_func=ephemerous_thread_upload_init,
            ui_thread_callback=ui_thread_upload_init_completed
        )

    def clear_sfd_list(self) -> None:
        """Empty the QTableView"""
        model = self._sfd_table.model()
        model.removeRows(0, model.rowCount())

    def download_sfd_list(self) -> None:
        """Downloads the installed SFD from the server and populates the table view"""
        self.clear_sfd_list()

        def ephemerous_thread_request_download(client: ScrutinyClient) -> Dict[str, sdk.SFDInfo]:
            return client.get_installed_sfds()  # Blocking call

        def ui_thread_download_callback(sfds: Optional[Dict[str, sdk.SFDInfo]], error: Optional[Exception]) -> None:
            # Called when the list is received
            if sfds is None:
                # Failed to download
                assert error is not None
                self._feedback_label.set_error(str(error))
                tools.log_exception(self._logger, error, "Failed to download the SFD list")
                return

            for sfd in sfds.values():
                self._sfd_table.model().add_row(sfd)
            self._sfd_table.resizeColumnsToContents()
            self._sfd_table.sortByColumn(SFDTableModel.Cols.CREATION_DATE, Qt.SortOrder.DescendingOrder)

        self._server_manager.schedule_client_request(
            user_func=ephemerous_thread_request_download,
            ui_thread_callback=ui_thread_download_callback
        )

    def connect_disconnect(self) -> None:
        """Set connected/disconnected based on server status"""
        if self._server_manager.get_server_state() == sdk.ServerState.Connected:
            self._set_connected()
        else:
            self._set_disconnected()

    def closeEvent(self, e: QCloseEvent) -> None:
        self._feedback_label.clear()
        return super().closeEvent(e)

    def showEvent(self, e: QShowEvent) -> None:
        self._feedback_label.clear()
        self.connect_disconnect()
        return super().showEvent(e)

    def set_transfer_active(self, req: Union[SFDDownloadRequest, SFDUploadRequest]) -> None:
        self._active_transfer_req = req
        self._sfd_table.allow_save(False)
        self._install_action.setEnabled(False)
        self._progress_widget.activate()

    def set_transfer_inactive(self) -> None:
        self._active_transfer_req = None
        self._sfd_table.allow_save(True)
        self._install_action.setEnabled(True)
        self._progress_widget.deactivate()

    def is_transfer_active(self) -> bool:
        return self._active_transfer_req is not None
