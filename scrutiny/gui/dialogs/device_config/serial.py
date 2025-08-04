#    serial.py
#        A Widget to configure a Serial port communication
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['SerialConfigPane']

from PySide6.QtWidgets import QLabel, QFormLayout, QWidget, QComboBox
from PySide6.QtGui import QIntValidator, QDoubleValidator

from scrutiny import sdk
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import NotEmptyValidator
from scrutiny.gui.dialogs.device_config.base_config_pane import BaseConfigPane
from scrutiny.tools.typing import *
from scrutiny import tools

class SerialConfigPane(BaseConfigPane):

    class PersistentDataKeys:
        PORT = 'port'
        BAUDRATE = 'baudrate'
        START_DELAY = 'start_delay'
        STOPBIT = 'stopbit'
        PARITY = 'parity'
        DATABITS = 'databits'


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

    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        serial_config = cast(sdk.SerialLinkConfig, config)
        namespace = gui_persistent_data.get_namespace(cls.__name__)        
        namespace.set_str(cls.PersistentDataKeys.PORT, serial_config.port)
        namespace.set_int(cls.PersistentDataKeys.BAUDRATE, serial_config.baudrate)
        namespace.set_float(cls.PersistentDataKeys.START_DELAY, serial_config.start_delay)
        namespace.set_str(cls.PersistentDataKeys.PARITY, serial_config.parity.to_str())
        namespace.set_int(cls.PersistentDataKeys.DATABITS, serial_config.databits.to_int())
        namespace.set_float(cls.PersistentDataKeys.STOPBIT, serial_config.stopbits.to_float())
        namespace.prune(tools.get_class_attr_vals(cls.PersistentDataKeys))


    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        return sdk.SerialLinkConfig(
            port=namespace.get_str(cls.PersistentDataKeys.PORT, '<port>'),
            baudrate=namespace.get_int(cls.PersistentDataKeys.BAUDRATE, 115200),
            start_delay=namespace.get_float(cls.PersistentDataKeys.START_DELAY, 0),
            parity=sdk.SerialLinkConfig.Parity.from_str(
                namespace.get_str(cls.PersistentDataKeys.PARITY, sdk.SerialLinkConfig.Parity.NONE.to_str()),
                sdk.SerialLinkConfig.Parity.NONE    # preference file could be corrupted
            ),
            stopbits=sdk.SerialLinkConfig.StopBits.from_float(
                namespace.get_float(cls.PersistentDataKeys.STOPBIT, sdk.SerialLinkConfig.StopBits.ONE.to_float()),
                default=sdk.SerialLinkConfig.StopBits.ONE   # preference file could be corrupted
            ),
            databits=sdk.SerialLinkConfig.DataBits.from_int(
                namespace.get_int(cls.PersistentDataKeys.DATABITS, sdk.SerialLinkConfig.DataBits.EIGHT.to_int()),
                default=sdk.SerialLinkConfig.DataBits.EIGHT   # preference file could be corrupted
            )
        )
