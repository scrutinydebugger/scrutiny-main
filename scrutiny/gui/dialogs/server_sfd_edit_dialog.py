__all__ = ['ServerSFDEditDialog']

import logging 

from PySide6.QtWidgets import QDialog, QWidget, QTableView, QVBoxLayout
from PySide6.QtCore import Qt, QAbstractItemModel
from PySide6.QtGui import QStandardItemModel, QStandardItem

from scrutiny import sdk
from scrutiny.sdk.client import ScrutinyClient
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.tools.typing import *
from scrutiny import tools

class ReadOnlyStandardItem(QStandardItem):
    @tools.copy_type(QStandardItem.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setEditable(False)
        

class SFDTableModel(QStandardItemModel):

    class Cols:
        PROJECT_NAME=0
        FIRMWARE_ID=1
        SCRUTINY_VERSION=2
        CREATION_DATE=3
    
    NB_COLS=4
    
    @tools.copy_type(QStandardItemModel.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setColumnCount(self.NB_COLS)

        headers:List[str] = ["" for i in range(self.NB_COLS)]
        headers[self.Cols.PROJECT_NAME] = "Project"
        headers[self.Cols.FIRMWARE_ID] = "Firmware ID"
        headers[self.Cols.SCRUTINY_VERSION] = "Scrutiny Version"
        headers[self.Cols.CREATION_DATE] = "Created On"
        self.setHorizontalHeaderLabels(headers)
    
    def add_row(self, sfd_info:sdk.SFDInfo) -> None:
        row = [ReadOnlyStandardItem("N/A") for i in range(self.NB_COLS)]
        row[self.Cols.FIRMWARE_ID].setText(sfd_info.firmware_id)
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

        

class SFDTableView(QTableView):
    _model : SFDTableModel

    @tools.copy_type(QTableView.__init__)
    def __init__(self, *args:Any, **kwargs:Any) -> None:
        super().__init__(*args, **kwargs)
        self.setModel(SFDTableModel(self))
    
    def setModel(self, model:Optional[QAbstractItemModel]) -> None:
        if not isinstance(model, SFDTableModel):
            raise ValueError("model must be a SFDTableModel")
        super().setModel(model)

    def model(self) -> SFDTableModel:
        return cast(SFDTableModel, super().model())

class ServerSFDEditDialog(QDialog):

    _server_manager : ServerManager
    _sfd_table: SFDTableView
    _logger:logging.Logger

    def __init__(self, parent:QWidget, server_manager:ServerManager) -> None:
        super().__init__(parent)
        self.setWindowTitle("Server SFDs")
        self.setMinimumSize(600,400)

        self._server_manager = server_manager
        self._logger = logging.getLogger(self.__class__.__name__)
        self._sfd_table = SFDTableView()
        self._sfd_table.verticalHeader().hide()
        self._sfd_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._sfd_table.setSizeAdjustPolicy(QTableView.SizeAdjustPolicy.AdjustToContents)

        layout = QVBoxLayout(self)
        layout.addWidget(self._sfd_table)
        

        self._server_manager.signals.server_connected.connect(self._server_connected_slot)
        self._server_manager.signals.server_disconnected.connect(self._server_disconnected_slot)

        if self._server_manager.get_server_state() == sdk.ServerState.Connected:
            self.download_sfd_list()
    
    def clear_sfd_list(self) -> None:
        model = self._sfd_table.model()
        model.removeRows(0, model.rowCount())

    def download_sfd_list(self) -> None:
        self.clear_sfd_list()

        def ephemerous_thread_request_download(client:ScrutinyClient) -> Dict[str, sdk.SFDInfo]:
            return client.get_installed_sfds()

        def ui_thread_download_callback(sfds:Optional[Dict[str, sdk.SFDInfo]], error:Optional[Exception]) -> None:
            if sfds is None:
                self._logger.error(f"Failed to download {error}")   # todo
                return
            
            for sfd in sfds.values():
                self._sfd_table.model().add_row(sfd)
            self._sfd_table.resizeColumnsToContents()

        self._server_manager.schedule_client_request(
            user_func = ephemerous_thread_request_download,
            ui_thread_callback = ui_thread_download_callback
        )
    
    def _server_connected_slot(self) -> None:
        self.download_sfd_list()

    def _server_disconnected_slot(self) -> None:
        self.clear_sfd_list()
