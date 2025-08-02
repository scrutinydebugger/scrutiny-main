#    canbus.py
#        A Widget to configure a CAN bus communication
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['CanBusConfigPane']

from PySide6.QtWidgets import QWidget, QComboBox, QFormLayout, QLabel, QCheckBox, QSpinBox, QStackedLayout
from PySide6.QtGui import QIntValidator

from scrutiny import sdk
from scrutiny.gui.dialogs.device_config.base_config_pane import BaseConfigPane
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import NotEmptyValidator
from scrutiny.tools.typing import *
from scrutiny import tools

class CanBusConfigPane(BaseConfigPane):

    class SocketCanSubconfigPane(QWidget):
        _txt_channel: ValidableLineEdit

        @tools.copy_type(QWidget.__init__)
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._txt_channel = ValidableLineEdit(soft_validator=NotEmptyValidator())
            self._txt_channel.setText('can0')
            layout = QFormLayout(self)
            layout.addRow("Channel", self._txt_channel)

        def load_config(self, config: sdk.CANLinkConfig) -> None:
            assert isinstance(config, sdk.CANLinkConfig)
            assert config.interface == sdk.CANLinkConfig.CANInterface.SocketCAN
            assert isinstance(config.interface_config, sdk.CANLinkConfig.SocketCANConfig)

            self._txt_channel.setText(config.interface_config.channel)

        def get_subconfig(self) -> sdk.CANLinkConfig.SocketCANConfig:
            return sdk.CANLinkConfig.SocketCANConfig(
                channel=self._txt_channel.text()
            )

        @classmethod
        def make_subconfig_valid(cls, subconfig: sdk.CANLinkConfig.SocketCANConfig) -> sdk.CANLinkConfig.SocketCANConfig:
            channel = subconfig.channel
            if not isinstance(channel, str):
                channel = 'can0'
            return sdk.CANLinkConfig.SocketCANConfig(
                channel=channel
            )

    class VectorSubconfigPane(QWidget):
        _txt_channel: ValidableLineEdit
        _txt_bitrate: ValidableLineEdit
        _txt_data_bitrate: ValidableLineEdit

        @tools.copy_type(QWidget.__init__)
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            layout = QFormLayout(self)

            self._txt_channel = ValidableLineEdit(soft_validator=NotEmptyValidator())
            self._txt_bitrate = ValidableLineEdit(soft_validator=NotEmptyValidator(), hard_validator=QIntValidator(bottom=10000))
            self._txt_data_bitrate = ValidableLineEdit(soft_validator=NotEmptyValidator(), hard_validator=QIntValidator(bottom=10000))
            self._txt_channel.setText('0')
            self._txt_bitrate.setText('500000')
            self._txt_data_bitrate.setText('500000')

            layout.addRow("Channel", self._txt_channel)
            layout.addRow("Bitrate (bps)", self._txt_bitrate)
            layout.addRow("Data Bitrate (bps)", self._txt_data_bitrate)

        def load_config(self, config: sdk.CANLinkConfig) -> None:
            assert isinstance(config, sdk.CANLinkConfig)
            assert config.interface == sdk.CANLinkConfig.CANInterface.Vector
            assert isinstance(config.interface_config, sdk.CANLinkConfig.VectorConfig)

            self._txt_channel.setText(str(config.interface_config.channel))
            self._txt_bitrate.setText(str(config.interface_config.bitrate))
            self._txt_data_bitrate.setText(str(config.interface_config.data_bitrate))

        def get_subconfig(self) -> sdk.CANLinkConfig.VectorConfig:
            return sdk.CANLinkConfig.VectorConfig(
                channel=self._txt_channel.text(),
                bitrate=int(self._txt_bitrate.text()),
                data_bitrate=int(self._txt_data_bitrate.text())
            )

        @classmethod
        def make_subconfig_valid(cls, subconfig: sdk.CANLinkConfig.VectorConfig) -> sdk.CANLinkConfig.VectorConfig:
            outconfig = sdk.CANLinkConfig.VectorConfig(
                channel=subconfig.channel,
                bitrate=max(int(subconfig.bitrate), 0),
                data_bitrate=max(int(subconfig.data_bitrate), 0),
            )
            return outconfig
        

    class KVaserSubconfigPane(QWidget):
        _txt_channel: ValidableLineEdit
        _txt_bitrate: ValidableLineEdit
        _txt_data_bitrate: ValidableLineEdit
        _chk_fd_non_iso: QCheckBox

        @tools.copy_type(QWidget.__init__)
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            layout = QFormLayout(self)

            self._txt_channel = ValidableLineEdit(soft_validator=NotEmptyValidator(), hard_validator=QIntValidator(bottom=0))
            self._txt_bitrate = ValidableLineEdit(soft_validator=NotEmptyValidator(), hard_validator=QIntValidator(bottom=10000))
            self._txt_data_bitrate = ValidableLineEdit(soft_validator=NotEmptyValidator(), hard_validator=QIntValidator(bottom=10000))
            self._chk_fd_non_iso = QCheckBox()
            self._txt_channel.setText('0')
            self._txt_bitrate.setText('500000')
            self._txt_data_bitrate.setText('500000')

            layout.addRow("Channel", self._txt_channel)
            layout.addRow("Bitrate (bps)", self._txt_bitrate)
            layout.addRow("Data Bitrate (bps)", self._txt_data_bitrate)
            layout.addRow("Non ISO FD (Bosch)", self._chk_fd_non_iso)

        def load_config(self, config: sdk.CANLinkConfig) -> None:
            assert isinstance(config, sdk.CANLinkConfig)
            assert config.interface == sdk.CANLinkConfig.CANInterface.KVaser
            assert isinstance(config.interface_config, sdk.CANLinkConfig.KVaserConfig)

            self._txt_channel.setText(str(config.interface_config.channel))
            self._txt_bitrate.setText(str(config.interface_config.bitrate))
            self._txt_data_bitrate.setText(str(config.interface_config.data_bitrate))
            self._chk_fd_non_iso.setChecked(config.interface_config.fd_non_iso and config.fd)

        def get_subconfig(self) -> sdk.CANLinkConfig.KVaserConfig:
            return sdk.CANLinkConfig.KVaserConfig(
                channel=int(self._txt_channel.text()),
                bitrate=int(self._txt_bitrate.text()),
                data_bitrate=int(self._txt_data_bitrate.text()),
                fd_non_iso=self._chk_fd_non_iso.isChecked()
            )

        @classmethod
        def make_subconfig_valid(cls, subconfig: sdk.CANLinkConfig.KVaserConfig) -> sdk.CANLinkConfig.KVaserConfig:
            outconfig = sdk.CANLinkConfig.KVaserConfig(
                channel=subconfig.channel,
                bitrate=max(int(subconfig.bitrate), 0),
                data_bitrate=max(int(subconfig.data_bitrate), 0),
                fd_non_iso=subconfig.fd_non_iso
            )
            return outconfig        

    _cmb_can_interface: QComboBox
    _spin_txid: QSpinBox
    _spin_rxid: QSpinBox
    _chk_extended_id: QCheckBox
    _chk_fd: QCheckBox
    _chk_bitrate_switch: QCheckBox
    _subconfig_layout: QStackedLayout
    _subconfig_socketcan_pane: SocketCanSubconfigPane
    _subconfig_vector_pane: VectorSubconfigPane
    _subconfig_kvaser_pane: KVaserSubconfigPane

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QFormLayout(self)

        self._cmb_can_interface = QComboBox()

        self._cmb_can_interface.setCurrentIndex(0)
        self._cmb_can_interface.addItem("SocketCAN", sdk.CANLinkConfig.CANInterface.SocketCAN)
        self._cmb_can_interface.addItem("Vector", sdk.CANLinkConfig.CANInterface.Vector)
        self._cmb_can_interface.addItem("KVaser", sdk.CANLinkConfig.CANInterface.KVaser)

        self._spin_txid = QSpinBox(prefix="0x", minimum=0, displayIntegerBase=16, maximum=0x7FF)
        self._spin_rxid = QSpinBox(prefix="0x", minimum=0, displayIntegerBase=16, maximum=0x7FF)

        self._chk_extended_id = QCheckBox("Extended ID (29bits)")
        self._chk_fd = QCheckBox("CAN FD")
        self._chk_bitrate_switch = QCheckBox("Bitrate switch")

        subconfig_container = QWidget()
        self._subconfig_layout = QStackedLayout(subconfig_container)
        self._subconfig_socketcan_pane = self.SocketCanSubconfigPane()
        self._subconfig_vector_pane = self.VectorSubconfigPane()
        self._subconfig_kvaser_pane = self.KVaserSubconfigPane()

        self._subconfig_layout.addWidget(self._subconfig_socketcan_pane)
        self._subconfig_layout.addWidget(self._subconfig_vector_pane)
        self._subconfig_layout.addWidget(self._subconfig_kvaser_pane)

        layout.addRow(QLabel("Interface: "), self._cmb_can_interface)
        layout.addRow(QLabel("Tx ID: "), self._spin_txid)
        layout.addRow(QLabel("Rx ID: "), self._spin_rxid)
        layout.addRow(self._chk_extended_id)
        layout.addRow(self._chk_fd)
        layout.addRow(self._chk_bitrate_switch)
        layout.addRow(subconfig_container)

        self._cmb_can_interface.currentIndexChanged.connect(self._update_ui)
        self._chk_extended_id.checkStateChanged.connect(self._update_ui)
        self._chk_fd.checkStateChanged.connect(self._update_ui)
        self._chk_bitrate_switch.checkStateChanged.connect(self._update_ui)

        self._update_ui()

    def _get_active_subconfig_pane(self) -> Union[SocketCanSubconfigPane, VectorSubconfigPane, KVaserSubconfigPane]:
        interface = cast(sdk.CANLinkConfig.CANInterface, self._cmb_can_interface.currentData())
        if interface == sdk.CANLinkConfig.CANInterface.SocketCAN:
            return self._subconfig_socketcan_pane
        elif interface == sdk.CANLinkConfig.CANInterface.Vector:
            return self._subconfig_vector_pane
        elif interface == sdk.CANLinkConfig.CANInterface.KVaser:
            return self._subconfig_kvaser_pane
        raise NotImplementedError(f"Unsupported subconfig pane for interface {interface}")

    def _update_ui(self) -> None:
        extended_id = self._chk_extended_id.isChecked()
        can_id_max = 0x7FF
        if extended_id:
            can_id_max = 0x1FFFFFFF
        self._spin_rxid.setMaximum(can_id_max)
        self._spin_txid.setMaximum(can_id_max)

        can_fd = self._chk_fd.isChecked()
        if not can_fd:
            self._chk_bitrate_switch.setChecked(False)

        self._chk_bitrate_switch.setEnabled(can_fd)

        self._update_subconfig_pane()

    def _update_subconfig_pane(self) -> None:
        for i in range(self._subconfig_layout.count()):
            subconfig_pane = self._subconfig_layout.widget(i)
            subconfig_pane.setVisible(False)

        self._get_active_subconfig_pane().setVisible(True)

    def get_config(self) -> Optional[sdk.CANLinkConfig]:
        interface = cast(sdk.CANLinkConfig.CANInterface, self._cmb_can_interface.currentData())

        extended_id = self._chk_extended_id.isChecked()
        canfd = self._chk_fd.isChecked()
        bitrate_switch = self._chk_bitrate_switch.isChecked() and canfd

        return sdk.CANLinkConfig(
            interface=interface,
            txid=self._spin_txid.value(),
            rxid=self._spin_rxid.value(),
            extended_id=extended_id,
            fd=canfd,
            bitrate_switch=bitrate_switch,
            interface_config=self._get_active_subconfig_pane().get_subconfig()
        )

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.CANLinkConfig)

        interface_index = self._cmb_can_interface.findData(config.interface)
        if interface_index != -1:
            self._cmb_can_interface.setCurrentIndex(interface_index)
        self._spin_txid.setValue(config.txid)
        self._spin_rxid.setValue(config.rxid)
        self._chk_bitrate_switch.setChecked(config.bitrate_switch)
        self._chk_extended_id.setChecked(config.extended_id)
        self._chk_fd.setChecked(config.fd)

        subconfig_pane = self._get_active_subconfig_pane()
        subconfig_pane.load_config(config)

        self._update_ui()

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert isinstance(config, sdk.CANLinkConfig)

        try:
            interface = sdk.CANLinkConfig.CANInterface(config.interface)
        except Exception:
            interface = sdk.CANLinkConfig.CANInterface.SocketCAN

        extended_id = config.extended_id
        can_fd = config.fd
        txid = min(max(config.txid, 0), 0x1FFFFFFF)
        rxid = min(max(config.rxid, 0), 0x1FFFFFFF)

        if not extended_id:
            txid = min(max(config.txid, 0), 0x7FF)
            rxid = min(max(config.rxid, 0), 0x7FF)

        bitrate_switch = config.bitrate_switch
        if not can_fd:
            bitrate_switch = False

        interface_config: Union[sdk.CANLinkConfig.SocketCANConfig, sdk.CANLinkConfig.VectorConfig, sdk.CANLinkConfig.KVaserConfig]
        if isinstance(config.interface_config, sdk.CANLinkConfig.SocketCANConfig):
            interface_config = cls.SocketCanSubconfigPane.make_subconfig_valid(config.interface_config)
        elif isinstance(config.interface_config, sdk.CANLinkConfig.VectorConfig):
            interface_config = cls.VectorSubconfigPane.make_subconfig_valid(config.interface_config)
        elif isinstance(config.interface_config, sdk.CANLinkConfig.KVaserConfig):
            interface_config = cls.KVaserSubconfigPane.make_subconfig_valid(config.interface_config)
        else:
            raise NotImplementedError("Unsupported subconfig")

        return sdk.CANLinkConfig(
            interface=interface,
            txid=txid,
            rxid=rxid,
            extended_id=extended_id,
            fd=can_fd,
            bitrate_switch=bitrate_switch,
            interface_config=interface_config
        )

    def visual_validation(self) -> None:
        # Called when OK is clicked
        pass
