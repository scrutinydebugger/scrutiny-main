#    device_config_dialog.py
#        A dialog to configure the communication between the server and the device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['DeviceConfigDialog']

import logging
import traceback
from dataclasses import dataclass

from PySide6.QtWidgets import QDialog, QWidget, QComboBox, QVBoxLayout, QDialogButtonBox, QPushButton

from scrutiny import sdk
from scrutiny.gui.dialogs.device_config.base_config_pane import BaseConfigPane
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.core.persistent_data import gui_persistent_data, AppPersistentData

from scrutiny.gui.dialogs.device_config.tcp_udp import TCPConfigPane, UDPConfigPane
from scrutiny.gui.dialogs.device_config.serial import SerialConfigPane
from scrutiny.gui.dialogs.device_config.rtt import RTTConfigPane
from scrutiny.gui.dialogs.device_config.canbus import CanBusConfigPane


from scrutiny.tools.typing import *

class NoConfigPane(BaseConfigPane):
    def get_config(self) -> Optional[sdk.BaseLinkConfig]:
        return sdk.NoneLinkConfig()

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        self.make_config_valid(config)

    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        pass
    
    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        return sdk.NoneLinkConfig()

@dataclass
class SupportedLinkType:
    ui_pane:Type[BaseConfigPane]
    display_name: str
    sort_order: int


class DeviceConfigDialog(QDialog):

    SUPPORTED_LINKS: Dict[sdk.DeviceLinkType, SupportedLinkType] = {
        sdk.DeviceLinkType.NONE: SupportedLinkType(ui_pane=NoConfigPane, display_name='None', sort_order=0),
      #  sdk.DeviceLinkType.TCP: SupportedLinkType(ui_pane=TCPConfigPane, display_name="TCP/IP", sort_order=1), # Not supported by the server yet
        sdk.DeviceLinkType.UDP: SupportedLinkType(ui_pane=UDPConfigPane, display_name="UDP/IP", sort_order=2),
        sdk.DeviceLinkType.Serial: SupportedLinkType(ui_pane=SerialConfigPane, display_name="Serial", sort_order=3),
        sdk.DeviceLinkType.RTT: SupportedLinkType(ui_pane=RTTConfigPane, display_name="JLink RTT", sort_order=4),
        sdk.DeviceLinkType.CAN: SupportedLinkType(ui_pane=CanBusConfigPane, display_name="CAN", sort_order=5)
    }

    _link_type_combo_box: QComboBox
    _config_container: QWidget
    _configs: Dict[sdk.DeviceLinkType, sdk.BaseLinkConfig]
    _active_pane: BaseConfigPane
    _apply_callback: Optional[Callable[["DeviceConfigDialog"], None]]
    _feedback_label: FeedbackLabel
    _btn_ok: QPushButton
    _btn_cancel: QPushButton
    _persistent_data: AppPersistentData

    def __init__(self,
                 parent: Optional[QWidget] = None,
                 apply_callback: Optional[Callable[["DeviceConfigDialog"], None]] = None
                 ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self._apply_callback = apply_callback
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setMinimumWidth(250)
        vlayout = QVBoxLayout(self)
        # Combobox at the top
        self._link_type_combo_box = QComboBox()
        for link_type, link_info in sorted(self.SUPPORTED_LINKS.items(), key=lambda x: x[1].sort_order):
            self._link_type_combo_box.addItem(link_info.display_name, link_type)
        
        # Bottom part that changes based on combo box selection
        self._config_container = QWidget()
        self._config_container.setLayout(QVBoxLayout())

        # A feed
        self._feedback_label = FeedbackLabel()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._btn_ok_click)
        buttons.rejected.connect(self._btn_cancel_click)

        vlayout.addWidget(self._link_type_combo_box)
        vlayout.addWidget(self._config_container)
        vlayout.addWidget(self._feedback_label)
        vlayout.addWidget(buttons)

        self._btn_ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._btn_cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)

        self._configs = {}
        # Preload some default configs to avoid having a blank form
        for link_type, link_info in self.SUPPORTED_LINKS.items():
            self._configs[link_type] = link_info.ui_pane.initialize_config()

        self._link_type_combo_box.currentIndexChanged.connect(self._combobox_changed)
        self._active_pane = NoConfigPane()
        self.swap_config_pane(sdk.DeviceLinkType.NONE)

        self._commit_configs_to_persistent_data()   # Override any corrupted values

    def _commit_configs_to_persistent_data(self) -> None:
        """Put the actual state of the dialog inside the persistent preferences system
        so that they get reloaded on next app startup"""

        for link_type, link_info in self.SUPPORTED_LINKS.items():
            link_info.ui_pane.save_to_persistent_data(self._configs[link_type])
          
    def _get_selected_link_type(self) -> sdk.DeviceLinkType:
        return cast(sdk.DeviceLinkType, self._link_type_combo_box.currentData())

    def _combobox_changed(self) -> None:
        link_type = self._get_selected_link_type()
        self._rebuild_config_layout(link_type)

    def _rebuild_config_layout(self, link_type: sdk.DeviceLinkType) -> None:
        """Change the variable part of the dialog based on the type of link the user wants."""

        for pane in self._config_container.children():
            if isinstance(pane, BaseConfigPane):
                pane.setParent(None)
                pane.deleteLater()

        # Create an instance of the pane associated with the link type
        self._active_pane = self.SUPPORTED_LINKS[link_type].ui_pane()
        layout = self._config_container.layout()
        assert layout is not None
        layout.addWidget(self._active_pane)

        try:
            config = self._active_pane.make_config_valid(self._configs[link_type])
            self._active_pane.load_config(config)
        except Exception as e:
            self.logger.warning(f"Tried to apply an invalid config to the window. {e}")
            self.logger.debug(traceback.format_exc())

    def _btn_ok_click(self) -> None:
        link_type = self._get_selected_link_type()
        config = self._active_pane.get_config()
        self._active_pane.visual_validation()
        # if config is None, it is invalid. Don't close and expect the user to fix
        if config is not None:
            self._configs[link_type] = config
            self._btn_ok.setEnabled(False)
            self._set_waiting_status()
            self._commit_configs_to_persistent_data()
            if self._apply_callback is not None:
                self._apply_callback(self)

    def change_fail_callback(self, error: str) -> None:
        """To be called to confirm a device link change fails"""
        self._set_error_status(error)
        self._btn_ok.setEnabled(True)

    def change_success_callback(self) -> None:
        """To be called to confirm a device link change succeeded"""
        self._clear_status()
        self._btn_ok.setEnabled(True)
        self.close()

    def _clear_status(self) -> None:
        self._feedback_label.clear()

    def _set_error_status(self, error: str) -> None:
        self._feedback_label.set_error(error)

    def _set_waiting_status(self) -> None:
        self._feedback_label.set_info("Waiting for the server...")

    def _btn_cancel_click(self) -> None:
        # Reload to the UI the config that is saved
        config = self._configs[self._get_selected_link_type()]
        self._active_pane.load_config(config)   # Should not raise. This config was there before.
        self._clear_status()
        self.close()

    def set_config(self, link_type: sdk.DeviceLinkType, config: sdk.BaseLinkConfig) -> None:
        """Set the config for a given link type. 
        This config will be displayed when the user select the given link type"""
        if link_type not in self._configs:
            raise ValueError("Unsupported config type")

        valid_config = self.SUPPORTED_LINKS[link_type].ui_pane.make_config_valid(config)
        self._configs[link_type] = valid_config

    def get_type_and_config(self) -> Tuple[sdk.DeviceLinkType, Optional[sdk.BaseLinkConfig]]:
        """Return the device link configuration selected by the user"""
        link_type = self._get_selected_link_type()
        config = self._active_pane.get_config()
        return (link_type, config)

    def swap_config_pane(self, link_type: sdk.DeviceLinkType) -> None:
        """Reconfigure the dialog for a new device type. Change the combo box value + reconfigure the variable part"""
        combobox_index = self._link_type_combo_box.findData(link_type)
        if combobox_index < 0:
            raise ValueError(f"Given link type not in the combobox {link_type}")
        self._link_type_combo_box.setCurrentIndex(combobox_index)   # Will trgger "currentIndexChanged"
