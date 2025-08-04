#    rtt.py
#        A Widget to configure a Seger RTT communication
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['RTTConfigPane']

from PySide6.QtWidgets import QLabel, QFormLayout, QWidget, QComboBox

from scrutiny import sdk
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import NotEmptyValidator
from scrutiny.gui.dialogs.device_config.base_config_pane import BaseConfigPane
from scrutiny.tools.typing import *
from scrutiny import tools

class RTTConfigPane(BaseConfigPane):

    class PersistentDataKeys:
        TARGET_DEVICE = 'target_device'
        JLINK_INTERFACE = 'jlink_interface'

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
            target_device="<device>" if len(config.target_device) == 0 else config.target_device,
            jlink_interface=config.jlink_interface
        )

    def visual_validation(self) -> None:
        # Called when OK is clicked
        self._target_device_text_box.validate_expect_valid()



    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        rtt_config = cast(sdk.RTTLinkConfig, config)
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        
        namespace.set_str(cls.PersistentDataKeys.TARGET_DEVICE, rtt_config.target_device)
        namespace.set_str(cls.PersistentDataKeys.JLINK_INTERFACE, rtt_config.jlink_interface.to_str())
        namespace.prune(tools.get_class_attr_vals(cls.PersistentDataKeys))

    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        return sdk.RTTLinkConfig(
                target_device=namespace.get_str(cls.PersistentDataKeys.TARGET_DEVICE, '<device>'),
                jlink_interface=sdk.RTTLinkConfig.JLinkInterface.from_str(
                    namespace.get_str(cls.PersistentDataKeys.JLINK_INTERFACE, sdk.RTTLinkConfig.JLinkInterface.SWD.to_str()),
                    sdk.RTTLinkConfig.JLinkInterface.SWD
                )
            )
