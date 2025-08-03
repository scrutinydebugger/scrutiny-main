#    tcp_udp.py
#        A Widget to configure a TCP/UDP communication
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['TCPConfigPane', 'UDPConfigPane']

from PySide6.QtWidgets import QLabel, QFormLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator

from scrutiny import sdk
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import IpPortValidator, NotEmptyValidator
from scrutiny.gui.dialogs.device_config.base_config_pane import BaseConfigPane
from scrutiny.tools.typing import *
from scrutiny import tools


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
    class PersistentDataKeys:
        TCP_HOST = 'tcp_hostname'
        TCP_PORT = 'tcp_port'

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
        port = max(min(config.port, 0xFFFF), 1)
        hostname = config.host
        if len(hostname) == 0:
            hostname = 'localhost'

        return sdk.TCPLinkConfig(
            host=hostname,
            port=port
        )
    
    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        tcp_config = cast(sdk.TCPLinkConfig, config)
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        namespace.set_str(cls.PersistentDataKeys.TCP_HOST, tcp_config.host)
        namespace.set_int(cls.PersistentDataKeys.TCP_PORT, tcp_config.port)
        namespace.prune(tools.get_class_attr_vals(cls.PersistentDataKeys))

    
    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        hostname = namespace.get_str(cls.PersistentDataKeys.TCP_HOST, default='localhost')
        port = namespace.get_int(cls.PersistentDataKeys.TCP_PORT, default=1234)

        return sdk.TCPLinkConfig(
            host=hostname,
            port=port
        )
        

class UDPConfigPane(IPConfigPane):
    class PersistentDataKeys:
        UDP_HOST = 'udp_hostname'
        UDP_PORT = 'udp_port'

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
        port = max(min(config.port, 0xFFFF), 1)
        hostname = config.host
        if len(hostname) == 0:
            hostname = 'localhost'

        return sdk.UDPLinkConfig(
            host=hostname,
            port=port
        )

    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        udp_config = cast(sdk.UDPLinkConfig, config)
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        namespace.set_str(cls.PersistentDataKeys.UDP_HOST, udp_config.host)
        namespace.set_int(cls.PersistentDataKeys.UDP_PORT, udp_config.port)
        namespace.prune(tools.get_class_attr_vals(cls.PersistentDataKeys))
    
    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        namespace = gui_persistent_data.get_namespace(cls.__name__)
        hostname = namespace.get_str(cls.PersistentDataKeys.UDP_HOST, default='localhost')
        port = namespace.get_int(cls.PersistentDataKeys.UDP_PORT, default=1234)

        return sdk.UDPLinkConfig(
            host=hostname,
            port=port
        )
