#    device_config_dialog.py
#        A dialog meant to change the link between the server and the device and its configuration.
#        Contains no app logic, has callback to integrate with an app.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = ['DeviceConfigDialog']

import logging
import traceback

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


class DeviceConfigDialog(QDialog):

    class PersistentPreferences:
        UDP_HOST = 'udp_hostname'
        UDP_PORT = 'udp_port'

        TCP_HOST = 'tcp_hostname'
        TCP_PORT = 'tcp_port'

        SERIAL_PORT = 'serial_port'
        SERIAL_BAUDRATE = 'serial_baudrate'
        SERIAL_START_DELAY = 'serial_start_delay'
        SERIAL_STOPBIT = 'serial_stopbit'
        SERIAL_PARITY = 'serial_parity'
        SERIAL_DATABITS = 'serial_databits'

        RTT_TARGET_DEVICE = 'rtt_target_device'
        RTT_JLINK_INTERFACE = 'rtt_jlink_interface'

        CAN_INTERFACE = 'can_interface'
        CAN_TXID = 'can_txid'
        CAN_RXID = 'can_rxid'
        CAN_EXTENDED_ID = 'can_extended_id'
        CAN_FD = 'can_fd'
        CAN_BITRATE_SWITCH = 'can_bitrate_switch'

        CAN_SOCKETCAN_CHANNEL = 'can_socketcan_channel'
        CAN_VECTOR_CHANNEL = 'can_vector_channel'
        CAN_VECTOR_BITRATE = 'can_vector_bitrate'
        CAN_VECTOR_DATA_BITRATE = 'can_vector_data_bitrate'
        CAN_KVASER_CHANNEL = 'can_kvaser_channel'
        CAN_KVASER_BITRATE = 'can_kvaser_bitrate'
        CAN_KVASER_DATA_BITRATE = 'can_kvaser_data_bitrate'
        CAN_KVASER_FD_NON_ISO = 'can_kvaser_fd_non_iso'

        @classmethod
        def get_all(cls) -> List[str]:
            return [attr for attr in dir(cls) if not callable(getattr(cls, attr)) and not attr.startswith("__")]

    CONFIG_TYPE_TO_WIDGET: Dict[sdk.DeviceLinkType, Type[BaseConfigPane]] = {
        sdk.DeviceLinkType.NONE: NoConfigPane,
        sdk.DeviceLinkType.TCP: TCPConfigPane,
        sdk.DeviceLinkType.UDP: UDPConfigPane,
        sdk.DeviceLinkType.Serial: SerialConfigPane,
        sdk.DeviceLinkType.RTT: RTTConfigPane,
        sdk.DeviceLinkType.CAN: CanBusConfigPane
    }

    _link_type_combo_box: QComboBox
    _config_container: QWidget
    _configs: Dict[sdk.DeviceLinkType, sdk.BaseLinkConfig]
    _active_pane: BaseConfigPane
    _apply_callback: Optional[Callable[["DeviceConfigDialog"], None]]
    _feedback_label: FeedbackLabel
    _btn_ok: QPushButton
    _btn_cancel: QPushButton
    _preferences: AppPersistentData

    def __init__(self,
                 parent: Optional[QWidget] = None,
                 apply_callback: Optional[Callable[["DeviceConfigDialog"], None]] = None
                 ) -> None:
        super().__init__(parent)
        self.setModal(True)
        self._preferences = gui_persistent_data.get_namespace(self.__class__.__name__)
        self._apply_callback = apply_callback
        self.logger = logging.getLogger(self.__class__.__name__)
        self.setMinimumWidth(250)
        vlayout = QVBoxLayout(self)
        # Combobox at the top
        self._link_type_combo_box = QComboBox()
        self._link_type_combo_box.addItem("None", sdk.DeviceLinkType.NONE)
        self._link_type_combo_box.addItem("Serial", sdk.DeviceLinkType.Serial)
        self._link_type_combo_box.addItem("UDP/IP", sdk.DeviceLinkType.UDP)
        self._link_type_combo_box.addItem("TCP/IP", sdk.DeviceLinkType.TCP)
        self._link_type_combo_box.addItem("JLink RTT", sdk.DeviceLinkType.RTT)
        self._link_type_combo_box.addItem("CAN", sdk.DeviceLinkType.CAN)

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
        self._configs[sdk.DeviceLinkType.NONE] = sdk.NoneLinkConfig()
        self._configs[sdk.DeviceLinkType.UDP] = sdk.UDPLinkConfig(
            host=self._preferences.get_str(self.PersistentPreferences.UDP_HOST, 'localhost'),
            port=self._preferences.get_int(self.PersistentPreferences.UDP_PORT, 12345),
        )

        self._configs[sdk.DeviceLinkType.TCP] = sdk.TCPLinkConfig(
            host=self._preferences.get_str(self.PersistentPreferences.TCP_HOST, 'localhost'),
            port=self._preferences.get_int(self.PersistentPreferences.TCP_PORT, 12345),
        )

        self._configs[sdk.DeviceLinkType.Serial] = sdk.SerialLinkConfig(
            port=self._preferences.get_str(self.PersistentPreferences.SERIAL_PORT, '<port>'),
            baudrate=self._preferences.get_int(self.PersistentPreferences.SERIAL_BAUDRATE, 115200),
            start_delay=self._preferences.get_float(self.PersistentPreferences.SERIAL_START_DELAY, 0),
            parity=sdk.SerialLinkConfig.Parity.from_str(
                self._preferences.get_str(self.PersistentPreferences.SERIAL_PARITY, sdk.SerialLinkConfig.Parity.NONE.to_str()),
                sdk.SerialLinkConfig.Parity.NONE    # preference file could be corrupted
            ),
            stopbits=sdk.SerialLinkConfig.StopBits.from_float(
                self._preferences.get_float(self.PersistentPreferences.SERIAL_STOPBIT, sdk.SerialLinkConfig.StopBits.ONE.to_float()),
                default=sdk.SerialLinkConfig.StopBits.ONE   # preference file could be corrupted
            ),
            databits=sdk.SerialLinkConfig.DataBits.from_int(
                self._preferences.get_int(self.PersistentPreferences.SERIAL_DATABITS, sdk.SerialLinkConfig.DataBits.EIGHT.to_int()),
                default=sdk.SerialLinkConfig.DataBits.EIGHT   # preference file could be corrupted
            )
        )

        self._configs[sdk.DeviceLinkType.RTT] = sdk.RTTLinkConfig(
            target_device=self._preferences.get_str(self.PersistentPreferences.RTT_TARGET_DEVICE, '<device>'),
            jlink_interface=sdk.RTTLinkConfig.JLinkInterface.from_str(
                self._preferences.get_str(self.PersistentPreferences.RTT_JLINK_INTERFACE, sdk.RTTLinkConfig.JLinkInterface.SWD.to_str()),
                sdk.RTTLinkConfig.JLinkInterface.SWD
            )
        )

        interface_config: Union[sdk.CANLinkConfig.SocketCANConfig, sdk.CANLinkConfig.VectorConfig, sdk.CANLinkConfig.KVaserConfig]
        can_interface = sdk.CANLinkConfig.CANInterface(self._preferences.get_int(self.PersistentPreferences.CAN_INTERFACE, 0))
        if can_interface == sdk.CANLinkConfig.CANInterface.SocketCAN:
            interface_config = sdk.CANLinkConfig.SocketCANConfig(
                channel=self._preferences.get_str(self.PersistentPreferences.CAN_SOCKETCAN_CHANNEL, 'can0')
            )
        elif can_interface == sdk.CANLinkConfig.CANInterface.Vector:
            interface_config = sdk.CANLinkConfig.VectorConfig(
                channel=self._preferences.get_str(self.PersistentPreferences.CAN_VECTOR_CHANNEL, '0'),
                bitrate=self._preferences.get_int(self.PersistentPreferences.CAN_VECTOR_BITRATE, 500000),
                data_bitrate=self._preferences.get_int(self.PersistentPreferences.CAN_VECTOR_DATA_BITRATE, 500000)
            )
        elif can_interface == sdk.CANLinkConfig.CANInterface.KVaser:
            interface_config = sdk.CANLinkConfig.KVaserConfig(
                channel=self._preferences.get_int(self.PersistentPreferences.CAN_KVASER_CHANNEL, 0),
                bitrate=self._preferences.get_int(self.PersistentPreferences.CAN_KVASER_BITRATE, 500000),
                data_bitrate=self._preferences.get_int(self.PersistentPreferences.CAN_KVASER_DATA_BITRATE, 500000),
                fd_non_iso=self._preferences.get_bool(self.PersistentPreferences.CAN_KVASER_FD_NON_ISO, False)
            )
        else:
            raise NotImplementedError(f"Unsupported CAN interface {can_interface}")

        self._configs[sdk.DeviceLinkType.CAN] = sdk.CANLinkConfig(
            interface=can_interface,
            txid=self._preferences.get_int(self.PersistentPreferences.CAN_TXID, 0),
            rxid=self._preferences.get_int(self.PersistentPreferences.CAN_RXID, 0),
            extended_id=self._preferences.get_bool(self.PersistentPreferences.CAN_EXTENDED_ID, False),
            fd=self._preferences.get_bool(self.PersistentPreferences.CAN_FD, False),
            bitrate_switch=self._preferences.get_bool(self.PersistentPreferences.CAN_BITRATE_SWITCH, False),
            interface_config=interface_config
        )

        self._link_type_combo_box.currentIndexChanged.connect(self._combobox_changed)
        self._active_pane = NoConfigPane()
        self.swap_config_pane(sdk.DeviceLinkType.NONE)

        self._preferences.prune(self.PersistentPreferences.get_all())    # Remove extra keys
        self._commit_configs_to_preferences()   # Override any corrupted values

    def _commit_configs_to_preferences(self) -> None:
        """Put the actual state of the dialog inside the persistent preferences system
        so that they get reloaded on next app startup"""
        udp_config = cast(sdk.UDPLinkConfig, self._configs[sdk.DeviceLinkType.UDP])
        self._preferences.set_str(self.PersistentPreferences.UDP_HOST, udp_config.host)
        self._preferences.set_int(self.PersistentPreferences.UDP_PORT, udp_config.port)

        tcp_config = cast(sdk.TCPLinkConfig, self._configs[sdk.DeviceLinkType.TCP])
        self._preferences.set_str(self.PersistentPreferences.TCP_HOST, tcp_config.host)
        self._preferences.set_int(self.PersistentPreferences.TCP_PORT, tcp_config.port)

        serial_config = cast(sdk.SerialLinkConfig, self._configs[sdk.DeviceLinkType.Serial])
        self._preferences.set_str(self.PersistentPreferences.SERIAL_PORT, serial_config.port)
        self._preferences.set_int(self.PersistentPreferences.SERIAL_BAUDRATE, serial_config.baudrate)
        self._preferences.set_float(self.PersistentPreferences.SERIAL_START_DELAY, serial_config.start_delay)
        self._preferences.set_str(self.PersistentPreferences.SERIAL_PARITY, serial_config.parity.to_str())
        self._preferences.set_int(self.PersistentPreferences.SERIAL_DATABITS, serial_config.databits.to_int())
        self._preferences.set_float(self.PersistentPreferences.SERIAL_STOPBIT, serial_config.stopbits.to_float())

        rtt_config = cast(sdk.RTTLinkConfig, self._configs[sdk.DeviceLinkType.RTT])
        self._preferences.set_str(self.PersistentPreferences.RTT_TARGET_DEVICE, rtt_config.target_device)
        self._preferences.set_str(self.PersistentPreferences.RTT_JLINK_INTERFACE, rtt_config.jlink_interface.to_str())

        can_config = cast(sdk.CANLinkConfig, self._configs[sdk.DeviceLinkType.CAN])
        self._preferences.set_int(self.PersistentPreferences.CAN_INTERFACE, can_config.interface.value)
        self._preferences.set_int(self.PersistentPreferences.CAN_TXID, can_config.txid)
        self._preferences.set_int(self.PersistentPreferences.CAN_RXID, can_config.rxid)
        self._preferences.set_bool(self.PersistentPreferences.CAN_BITRATE_SWITCH, can_config.bitrate_switch)
        self._preferences.set_bool(self.PersistentPreferences.CAN_EXTENDED_ID, can_config.extended_id)
        self._preferences.set_bool(self.PersistentPreferences.CAN_FD, can_config.fd)

        if isinstance(can_config.interface_config, sdk.CANLinkConfig.SocketCANConfig):
             self._preferences.set_str(self.PersistentPreferences.CAN_SOCKETCAN_CHANNEL, can_config.interface_config.channel)
        elif isinstance(can_config.interface_config, sdk.CANLinkConfig.VectorConfig):
             self._preferences.set_str(self.PersistentPreferences.CAN_VECTOR_CHANNEL, str(can_config.interface_config.channel))
             self._preferences.set_int(self.PersistentPreferences.CAN_VECTOR_BITRATE, can_config.interface_config.bitrate)
             self._preferences.set_int(self.PersistentPreferences.CAN_VECTOR_DATA_BITRATE, can_config.interface_config.data_bitrate)
        elif isinstance(can_config.interface_config, sdk.CANLinkConfig.KVaserConfig):
             self._preferences.set_str(self.PersistentPreferences.CAN_KVASER_CHANNEL, str(can_config.interface_config.channel))
             self._preferences.set_int(self.PersistentPreferences.CAN_KVASER_BITRATE, can_config.interface_config.bitrate)
             self._preferences.set_int(self.PersistentPreferences.CAN_KVASER_DATA_BITRATE, can_config.interface_config.data_bitrate)
             self._preferences.set_bool(self.PersistentPreferences.CAN_KVASER_FD_NON_ISO, can_config.interface_config.fd_non_iso)


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
        self._active_pane = self.CONFIG_TYPE_TO_WIDGET[link_type]()
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
            self._commit_configs_to_preferences()
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

        valid_config = self.CONFIG_TYPE_TO_WIDGET[link_type].make_config_valid(config)
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
