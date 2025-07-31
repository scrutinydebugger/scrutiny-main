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

from PySide6.QtWidgets import QDialog, QWidget, QComboBox, QVBoxLayout, QDialogButtonBox, QFormLayout, QLabel, QPushButton, QCheckBox, QSpinBox, QStackedLayout
from PySide6.QtGui import QIntValidator, QDoubleValidator
from PySide6.QtCore import Qt

from scrutiny import sdk
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
from scrutiny.gui.core.persistent_data import gui_persistent_data, AppPersistentData
from scrutiny.tools.typing import *
from scrutiny import tools


class BaseConfigPane(QWidget):
    def get_config(self) -> Optional[sdk.BaseLinkConfig]:
        raise NotImplementedError("abstract method")

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        raise NotImplementedError("abstract method")

    def visual_validation(self) -> None:
        pass

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert config is not None
        return config


class NoConfigPane(BaseConfigPane):
    def get_config(self) -> Optional[sdk.BaseLinkConfig]:
        return sdk.NoneLinkConfig()

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        self.make_config_valid(config)


class IPConfigPane(BaseConfigPane):
    _hostname_textbox: ValidableLineEdit
    _port_textbox: ValidableLineEdit

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        form_layout = QFormLayout(self)
        form_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        hostname_label = QLabel("Hostname: ")
        port_label = QLabel("Port: ")
        self._hostname_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._port_textbox = ValidableLineEdit(hard_validator=QIntValidator(0, 0xFFFF), soft_validator=IpPortValidator())

        # Make sure the red background disappear when we type (fixing the invalid content)
        self._hostname_textbox.textChanged.connect(self._hostname_textbox.validate_expect_not_wrong_default_slot)
        self._port_textbox.textChanged.connect(self._port_textbox.validate_expect_not_wrong_default_slot)

        form_layout.addRow(hostname_label, self._hostname_textbox)
        form_layout.addRow(port_label, self._port_textbox)

    def get_port(self) -> Optional[int]:
        port_txt = self._port_textbox.text()
        state, _, _ = IpPortValidator().validate(port_txt, 0)
        if state == IpPortValidator.State.Acceptable:
            return int(port_txt)    # Should not fail
        return None

    def set_port(self, port: int) -> None:
        port_txt = str(port)
        state, _, _ = IpPortValidator().validate(port_txt, 0)
        if state != IpPortValidator.State.Acceptable:
            raise ValueError(f"Invalid port number: {port}")
        self._port_textbox.setText(port_txt)

    def get_hostname(self) -> str:
        return self._hostname_textbox.text()

    def set_hostname(self, hostname: str) -> None:
        self._hostname_textbox.setText(hostname)

    def visual_validation(self) -> None:
        # Called when OK is clicked
        self._port_textbox.validate_expect_valid()
        self._hostname_textbox.validate_expect_valid()


class TCPConfigPane(IPConfigPane):
    def get_config(self) -> Optional[sdk.TCPLinkConfig]:
        port = self.get_port()
        if port is None:
            return None

        return sdk.TCPLinkConfig(
            host=self.get_hostname(),
            port=port,
        )

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.TCPLinkConfig)
        self.set_hostname(config.host)
        self.set_port(config.port)

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert isinstance(config, sdk.TCPLinkConfig)
        port = max(min(config.port, 0xFFFF), 0)
        hostname = config.host
        if len(hostname) == 0:
            hostname = 'localhost'

        return sdk.TCPLinkConfig(
            host=hostname,
            port=port
        )


class UDPConfigPane(IPConfigPane):
    def get_config(self) -> Optional[sdk.UDPLinkConfig]:
        port = self.get_port()
        if port is None:
            return None

        return sdk.UDPLinkConfig(
            host=self.get_hostname(),
            port=port,
        )

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.UDPLinkConfig)
        self.set_hostname(config.host)
        self.set_port(config.port)

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert isinstance(config, sdk.UDPLinkConfig)
        port = max(min(config.port, 0xFFFF), 0)
        hostname = config.host
        if len(hostname) == 0:
            hostname = 'localhost'

        return sdk.UDPLinkConfig(
            host=hostname,
            port=port
        )


class SerialConfigPane(BaseConfigPane):
    _port_name_textbox: ValidableLineEdit
    _baudrate_textbox: ValidableLineEdit
    _stopbits_combo_box: QComboBox
    _databits_combo_box: QComboBox
    _parity_combo_box: QComboBox
    _start_delay_textbox: ValidableLineEdit

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QFormLayout(self)
        self._port_name_textbox = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._baudrate_textbox = ValidableLineEdit(
            hard_validator=QIntValidator(0, 0x7FFFFFFF),
            soft_validator=NotEmptyValidator()
        )
        self._start_delay_textbox = ValidableLineEdit(
            hard_validator=QDoubleValidator(0, 5, 2, self),
            soft_validator=NotEmptyValidator()
        )
        self._stopbits_combo_box = QComboBox()
        self._stopbits_combo_box.addItem("1", sdk.SerialLinkConfig.StopBits.ONE)
        self._stopbits_combo_box.addItem("1.5", sdk.SerialLinkConfig.StopBits.ONE_POINT_FIVE)
        self._stopbits_combo_box.addItem("2", sdk.SerialLinkConfig.StopBits.TWO)
        self._stopbits_combo_box.setCurrentIndex(self._stopbits_combo_box.findData(sdk.SerialLinkConfig.StopBits.ONE))

        self._databits_combo_box = QComboBox()
        self._databits_combo_box.addItem("5", sdk.SerialLinkConfig.DataBits.FIVE)
        self._databits_combo_box.addItem("6", sdk.SerialLinkConfig.DataBits.SIX)
        self._databits_combo_box.addItem("7", sdk.SerialLinkConfig.DataBits.SEVEN)
        self._databits_combo_box.addItem("8", sdk.SerialLinkConfig.DataBits.EIGHT)
        self._databits_combo_box.setCurrentIndex(self._databits_combo_box.findData(sdk.SerialLinkConfig.DataBits.EIGHT))

        self._parity_combo_box = QComboBox()
        self._parity_combo_box.addItem("None", sdk.SerialLinkConfig.Parity.NONE)
        self._parity_combo_box.addItem("Even", sdk.SerialLinkConfig.Parity.EVEN)
        self._parity_combo_box.addItem("Odd", sdk.SerialLinkConfig.Parity.ODD)
        self._parity_combo_box.addItem("Mark", sdk.SerialLinkConfig.Parity.MARK)
        self._parity_combo_box.addItem("Space", sdk.SerialLinkConfig.Parity.SPACE)
        self._parity_combo_box.setCurrentIndex(self._parity_combo_box.findData(sdk.SerialLinkConfig.Parity.NONE))

        layout.addRow(QLabel("Port: "), self._port_name_textbox)
        layout.addRow(QLabel("Baudrate: "), self._baudrate_textbox)
        layout.addRow(QLabel("Stop bits: "), self._stopbits_combo_box)
        layout.addRow(QLabel("Data bits: "), self._databits_combo_box)
        layout.addRow(QLabel("Parity: "), self._parity_combo_box)
        layout.addRow(QLabel("Start delay (sec): "), self._start_delay_textbox)

        # Make sure the red background disappear when we type (fixing the invalid content)
        self._port_name_textbox.textChanged.connect(self._port_name_textbox.validate_expect_not_wrong_default_slot)
        self._baudrate_textbox.textChanged.connect(self._baudrate_textbox.validate_expect_not_wrong_default_slot)
        self._start_delay_textbox.textChanged.connect(self._baudrate_textbox.validate_expect_not_wrong_default_slot)

    def get_config(self) -> Optional[sdk.SerialLinkConfig]:
        port = self._port_name_textbox.text()
        baudrate_str = self._baudrate_textbox.text()
        stopbits = cast(sdk.SerialLinkConfig.StopBits, self._stopbits_combo_box.currentData())
        databits = cast(sdk.SerialLinkConfig.DataBits, self._databits_combo_box.currentData())
        parity = cast(sdk.SerialLinkConfig.Parity, self._parity_combo_box.currentData())
        try:
            start_delay = float(self._start_delay_textbox.text())
        except Exception:
            return None

        if len(port) == 0:
            return None

        try:
            baudrate = int(baudrate_str)
        except Exception:
            return None

        if baudrate < 0:
            return None

        return sdk.SerialLinkConfig(
            port=port,
            baudrate=baudrate,
            stopbits=stopbits,
            databits=databits,
            parity=parity,
            start_delay=start_delay
        )

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.SerialLinkConfig)

        self._port_name_textbox.setText(config.port)
        self._baudrate_textbox.setText(str(config.baudrate))
        self._stopbits_combo_box.setCurrentIndex(self._stopbits_combo_box.findData(config.stopbits))
        self._databits_combo_box.setCurrentIndex(self._databits_combo_box.findData(config.databits))
        self._parity_combo_box.setCurrentIndex(self._parity_combo_box.findData(config.parity))
        self._start_delay_textbox.setText(str(config.start_delay))

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert isinstance(config, sdk.SerialLinkConfig)
        return sdk.SerialLinkConfig(
            port="<port>" if len(config.port) == 0 else config.port,
            baudrate=max(config.baudrate, 1),
            stopbits=config.stopbits,
            databits=config.databits,
            parity=config.parity,
            start_delay=max(config.start_delay, 0)
        )

    def visual_validation(self) -> None:
        # Called when OK is clicked
        self._port_name_textbox.validate_expect_valid()
        self._baudrate_textbox.validate_expect_valid()
        self._start_delay_textbox.validate_expect_valid()


class RTTConfigPane(BaseConfigPane):
    _target_device_text_box: ValidableLineEdit
    _jlink_interface_combo_box: QComboBox

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QFormLayout(self)

        self._target_device_text_box = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._jlink_interface_combo_box = QComboBox()

        self._jlink_interface_combo_box.addItem("SWD", sdk.RTTLinkConfig.JLinkInterface.SWD)
        self._jlink_interface_combo_box.addItem("JTAG", sdk.RTTLinkConfig.JLinkInterface.JTAG)
        self._jlink_interface_combo_box.addItem("ICSP", sdk.RTTLinkConfig.JLinkInterface.ICSP)
        self._jlink_interface_combo_box.addItem("FINE", sdk.RTTLinkConfig.JLinkInterface.FINE)
        self._jlink_interface_combo_box.addItem("SPI", sdk.RTTLinkConfig.JLinkInterface.SPI)
        self._jlink_interface_combo_box.addItem("C2", sdk.RTTLinkConfig.JLinkInterface.C2)

        layout.addRow(QLabel("Interface: "), self._jlink_interface_combo_box)
        layout.addRow(QLabel("Target Device: "), self._target_device_text_box)

        # Make sure the red background disappear when we type (fixing the invalid content)
        self._target_device_text_box.textChanged.connect(self._target_device_text_box.validate_expect_not_wrong_default_slot)

    def get_config(self) -> Optional[sdk.RTTLinkConfig]:
        target_device = self._target_device_text_box.text()
        interface = cast(sdk.RTTLinkConfig.JLinkInterface, self._jlink_interface_combo_box.currentData())

        if len(target_device) == 0:
            return None

        return sdk.RTTLinkConfig(
            target_device=target_device,
            jlink_interface=interface
        )

    def load_config(self, config: Optional[sdk.BaseLinkConfig]) -> None:
        config = self.make_config_valid(config)
        assert isinstance(config, sdk.RTTLinkConfig)

        self._target_device_text_box.setText(config.target_device)
        self._jlink_interface_combo_box.setCurrentIndex(self._jlink_interface_combo_box.findData(config.jlink_interface))

    @classmethod
    def make_config_valid(cls, config: Optional[sdk.BaseLinkConfig]) -> sdk.BaseLinkConfig:
        assert isinstance(config, sdk.RTTLinkConfig)
        return sdk.RTTLinkConfig(
            target_device="<device>" if len(config.target_device) else config.target_device,
            jlink_interface=config.jlink_interface
        )

    def visual_validation(self) -> None:
        # Called when OK is clicked
        self._target_device_text_box.validate_expect_valid()


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

        interface_config: Union[sdk.CANLinkConfig.SocketCANConfig, sdk.CANLinkConfig.VectorConfig]
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
