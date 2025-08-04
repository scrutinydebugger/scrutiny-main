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
from scrutiny.gui.core.persistent_data import gui_persistent_data
from scrutiny.gui.dialogs.device_config.base_config_pane import BaseConfigPane
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit
from scrutiny.gui.tools.validators import NotEmptyValidator
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.tools.typing import *
from scrutiny import tools
    

ANY_CAN_SUBCONFIG:TypeAlias = Union[
            sdk.CANLinkConfig.SocketCANConfig, 
            sdk.CANLinkConfig.VectorConfig, 
            sdk.CANLinkConfig.KVaserConfig, 
            sdk.CANLinkConfig.PCANConfig,
            sdk.CANLinkConfig.ETASConfig,
            ]

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

    def get_subconfig(self) -> Optional[sdk.CANLinkConfig.SocketCANConfig]:
        if not self._txt_channel.is_valid():
            return None
        
        return sdk.CANLinkConfig.SocketCANConfig(
            channel=self._txt_channel.text()
        )
    
    def visual_validation(self) -> None:
        self._txt_channel.validate_expect_valid()

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

    def get_subconfig(self) -> Optional[sdk.CANLinkConfig.VectorConfig]:
        for txtbox in [self._txt_channel, self._txt_bitrate, self._txt_data_bitrate]:
            if not txtbox.is_valid():
                return None

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
    
    def visual_validation(self) -> None:
        self._txt_channel.validate_expect_valid()
        self._txt_bitrate.validate_expect_valid()
        self._txt_data_bitrate.validate_expect_valid()
    
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

    def get_subconfig(self) -> Optional[sdk.CANLinkConfig.KVaserConfig]:
        for txtbox in [self._txt_channel, self._txt_bitrate, self._txt_data_bitrate]:
            if not txtbox.is_valid():
                return None

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

    def visual_validation(self) -> None:
        for txtbox in [self._txt_channel, self._txt_bitrate, self._txt_data_bitrate]:
            txtbox.validate_expect_valid()
            
class PCANSubconfigPane(QWidget):
    _txt_channel: ValidableLineEdit
    _txt_bitrate: ValidableLineEdit

    @tools.copy_type(QWidget.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        layout = QFormLayout(self)

        self._txt_channel = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._txt_bitrate = ValidableLineEdit(soft_validator=NotEmptyValidator(), hard_validator=QIntValidator(bottom=10000))
        self._txt_channel.setText('0')
        self._txt_bitrate.setText('500000')

        layout.addRow("Channel", self._txt_channel)
        layout.addRow("Bitrate (bps)", self._txt_bitrate)

    def load_config(self, config: sdk.CANLinkConfig) -> None:
        assert isinstance(config, sdk.CANLinkConfig)
        assert config.interface == sdk.CANLinkConfig.CANInterface.PCAN
        assert isinstance(config.interface_config, sdk.CANLinkConfig.PCANConfig)

        self._txt_channel.setText(config.interface_config.channel)
        self._txt_bitrate.setText(str(config.interface_config.bitrate))

    def get_subconfig(self) -> Optional[sdk.CANLinkConfig.PCANConfig]:
        for txtbox in [self._txt_channel, self._txt_bitrate]:
            if not txtbox.is_valid():
                return None
            
        return sdk.CANLinkConfig.PCANConfig(
            channel=self._txt_channel.text(),
            bitrate=int(self._txt_bitrate.text())
        )

    @classmethod
    def make_subconfig_valid(cls, subconfig: sdk.CANLinkConfig.PCANConfig) -> sdk.CANLinkConfig.PCANConfig:
        outconfig = sdk.CANLinkConfig.PCANConfig(
            channel=subconfig.channel,
            bitrate=max(int(subconfig.bitrate), 0)
        )
        return outconfig    

    def visual_validation(self) -> None:
        for txtbox in [self._txt_channel, self._txt_bitrate]:
            txtbox.validate_expect_valid()    

class ETASSubconfigPane(QWidget):
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
        self._txt_channel.setText('')
        self._txt_bitrate.setText('500000')
        self._txt_data_bitrate.setText('500000')

        layout.addRow("Channel", self._txt_channel)
        layout.addRow("Bitrate (bps)", self._txt_bitrate)
        layout.addRow("Data Bitrate (bps)", self._txt_data_bitrate)

    def load_config(self, config: sdk.CANLinkConfig) -> None:
        assert isinstance(config, sdk.CANLinkConfig)
        assert config.interface == sdk.CANLinkConfig.CANInterface.ETAS
        assert isinstance(config.interface_config, sdk.CANLinkConfig.ETASConfig)

        self._txt_channel.setText(str(config.interface_config.channel))
        self._txt_bitrate.setText(str(config.interface_config.bitrate))
        self._txt_data_bitrate.setText(str(config.interface_config.data_bitrate))

    def get_subconfig(self) -> Optional[sdk.CANLinkConfig.ETASConfig]:
        for txtbox in [self._txt_channel, self._txt_bitrate, self._txt_data_bitrate]:
            if not txtbox.is_valid():
                return None
            
        return sdk.CANLinkConfig.ETASConfig(
            channel=self._txt_channel.text(),
            bitrate=int(self._txt_bitrate.text()),
            data_bitrate=int(self._txt_data_bitrate.text()),
        )

    @classmethod
    def make_subconfig_valid(cls, subconfig: sdk.CANLinkConfig.ETASConfig) -> sdk.CANLinkConfig.ETASConfig:
        outconfig = sdk.CANLinkConfig.ETASConfig(
            channel=subconfig.channel,
            bitrate=max(int(subconfig.bitrate), 0),
            data_bitrate=max(int(subconfig.data_bitrate), 0),
        )
        return outconfig    

    def visual_validation(self) -> None:
        for txtbox in [self._txt_channel, self._txt_bitrate, self._txt_data_bitrate]:
            txtbox.validate_expect_valid()    

ANY_SUBCONFIG_PANE:TypeAlias = Union[
    SocketCanSubconfigPane,
    VectorSubconfigPane,
    KVaserSubconfigPane,
    PCANSubconfigPane,
    ETASSubconfigPane
]

class CanBusConfigPane(BaseConfigPane):

    class PersistentDataKeys:
        INTERFACE = 'interface'
        TXID = 'txid'
        RXID = 'rxid'
        EXTENDED_ID = 'extended_id'
        FD = 'fd'
        BITRATE_SWITCH = 'bitrate_switch'

        SOCKETCAN_CHANNEL = 'socketcan_channel'
        
        VECTOR_CHANNEL = 'vector_channel'
        VECTOR_BITRATE = 'vector_bitrate'
        VECTOR_DATA_BITRATE = 'vector_data_bitrate'
        
        KVASER_CHANNEL = 'kvaser_channel'
        KVASER_BITRATE = 'kvaser_bitrate'
        KVASER_DATA_BITRATE = 'kvaser_data_bitrate'
        KVASER_FD_NON_ISO = 'kvaser_fd_non_iso'
        
        PCAN_CHANNEL = 'pcan_channel'
        PCAN_BITRATE = 'pcan_bitrate'
        
        ETAS_CHANNEL = 'etas_channel'
        ETAS_BITRATE = 'etas_bitrate'
        ETAS_DATA_BITRATE = 'etas_data_bitrate'

    _cmb_can_interface: QComboBox
    """Combobox for selecting CAN bus interface type"""
    _spin_txid: QSpinBox
    """SpinBox for configuring CAN bus transmit ID"""
    _spin_rxid: QSpinBox
    """`SpinBox for configuring CAN bus receive ID"""
    _chk_extended_id: QCheckBox
    """`CheckBox to select extended (29bits ID)"""
    _chk_fd: QCheckBox
    """Checkbox to enable CAN FD"""
    _chk_bitrate_switch: QCheckBox
    """Checkbox to enable bitrate switching for CAN FD"""
    _subconfig_layout: QStackedLayout
    """The layout that will stack different interface-specific configuration panes"""
    _subconfig_socketcan_pane: SocketCanSubconfigPane
    """SocketCAN specific configuration pane"""
    _subconfig_vector_pane: VectorSubconfigPane
    """Vector specific configuration pane"""
    _subconfig_kvaser_pane: KVaserSubconfigPane
    """KVaser specific configuration pane"""
    _subconfig_pcan_pane: PCANSubconfigPane
    """PCAN specific configuration pane"""
    _subconfig_etas_pane: ETASSubconfigPane
    """ETAS specific configuration pane"""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        layout = QFormLayout(self)

        self._cmb_can_interface = QComboBox()

        self._cmb_can_interface.setCurrentIndex(0)
        self._cmb_can_interface.addItem("SocketCAN", sdk.CANLinkConfig.CANInterface.SocketCAN)
        self._cmb_can_interface.addItem("Vector", sdk.CANLinkConfig.CANInterface.Vector)
        self._cmb_can_interface.addItem("KVaser", sdk.CANLinkConfig.CANInterface.KVaser)
        self._cmb_can_interface.addItem("PCAN", sdk.CANLinkConfig.CANInterface.PCAN)
        self._cmb_can_interface.addItem("ETAS", sdk.CANLinkConfig.CANInterface.ETAS)

        self._spin_txid = QSpinBox(prefix="0x", minimum=0, displayIntegerBase=16, maximum=0x7FF)
        self._spin_rxid = QSpinBox(prefix="0x", minimum=0, displayIntegerBase=16, maximum=0x7FF)

        self._chk_extended_id = QCheckBox("Extended ID (29bits)")
        self._chk_fd = QCheckBox("CAN FD")
        self._chk_bitrate_switch = QCheckBox("Bitrate switch")

        subconfig_container = QWidget()
        self._subconfig_layout = QStackedLayout(subconfig_container)
        self._subconfig_socketcan_pane = SocketCanSubconfigPane()
        self._subconfig_vector_pane = VectorSubconfigPane()
        self._subconfig_kvaser_pane = KVaserSubconfigPane()
        self._subconfig_pcan_pane = PCANSubconfigPane()
        self._subconfig_etas_pane = ETASSubconfigPane()

        self._subconfig_layout.addWidget(self._subconfig_socketcan_pane)
        self._subconfig_layout.addWidget(self._subconfig_vector_pane)
        self._subconfig_layout.addWidget(self._subconfig_kvaser_pane)
        self._subconfig_layout.addWidget(self._subconfig_pcan_pane)
        self._subconfig_layout.addWidget(self._subconfig_etas_pane)

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

    def _get_active_subconfig_pane(self) -> ANY_SUBCONFIG_PANE:
        interface = cast(sdk.CANLinkConfig.CANInterface, self._cmb_can_interface.currentData())
        if interface == sdk.CANLinkConfig.CANInterface.SocketCAN:
            return self._subconfig_socketcan_pane
        elif interface == sdk.CANLinkConfig.CANInterface.Vector:
            return self._subconfig_vector_pane
        elif interface == sdk.CANLinkConfig.CANInterface.KVaser:
            return self._subconfig_kvaser_pane
        elif interface == sdk.CANLinkConfig.CANInterface.PCAN:
            return self._subconfig_pcan_pane
        elif interface == sdk.CANLinkConfig.CANInterface.ETAS:
            return self._subconfig_etas_pane
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

        if self._spin_txid.value() == self._spin_rxid.value():
            return None # Invalid
        
        subconfig = self._get_active_subconfig_pane().get_subconfig()
        if subconfig is None:
            return None
        
        return sdk.CANLinkConfig(
            interface=interface,
            txid=self._spin_txid.value(),
            rxid=self._spin_rxid.value(),
            extended_id=extended_id,
            fd=canfd,
            bitrate_switch=bitrate_switch,
            interface_config=subconfig
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

        interface_config: ANY_CAN_SUBCONFIG
        if isinstance(config.interface_config, sdk.CANLinkConfig.SocketCANConfig):
            interface_config = SocketCanSubconfigPane.make_subconfig_valid(config.interface_config)
        elif isinstance(config.interface_config, sdk.CANLinkConfig.VectorConfig):
            interface_config = VectorSubconfigPane.make_subconfig_valid(config.interface_config)
        elif isinstance(config.interface_config, sdk.CANLinkConfig.KVaserConfig):
            interface_config = KVaserSubconfigPane.make_subconfig_valid(config.interface_config)
        elif isinstance(config.interface_config, sdk.CANLinkConfig.PCANConfig):
            interface_config = PCANSubconfigPane.make_subconfig_valid(config.interface_config)
        elif isinstance(config.interface_config, sdk.CANLinkConfig.ETASConfig):
            interface_config = ETASSubconfigPane.make_subconfig_valid(config.interface_config)
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
        if self._spin_rxid.value() == self._spin_txid.value():
            scrutiny_get_theme().set_error_state(self._spin_rxid)
            scrutiny_get_theme().set_error_state(self._spin_txid)
        else:
            scrutiny_get_theme().set_default_state(self._spin_rxid)
            scrutiny_get_theme().set_default_state(self._spin_txid)

        self._get_active_subconfig_pane().visual_validation()


    @classmethod
    def save_to_persistent_data(cls, config:sdk.BaseLinkConfig) -> None:
        can_config = cast(sdk.CANLinkConfig, config)
        namespace = gui_persistent_data.get_namespace(cls.__name__)

        namespace.set_int(cls.PersistentDataKeys.INTERFACE, can_config.interface.value)
        namespace.set_int(cls.PersistentDataKeys.TXID, can_config.txid)
        namespace.set_int(cls.PersistentDataKeys.RXID, can_config.rxid)
        namespace.set_bool(cls.PersistentDataKeys.BITRATE_SWITCH, can_config.bitrate_switch)
        namespace.set_bool(cls.PersistentDataKeys.EXTENDED_ID, can_config.extended_id)
        namespace.set_bool(cls.PersistentDataKeys.FD, can_config.fd)

        if isinstance(can_config.interface_config, sdk.CANLinkConfig.SocketCANConfig):
             namespace.set_str(cls.PersistentDataKeys.SOCKETCAN_CHANNEL, can_config.interface_config.channel)
        elif isinstance(can_config.interface_config, sdk.CANLinkConfig.VectorConfig):
             namespace.set_str(cls.PersistentDataKeys.VECTOR_CHANNEL, str(can_config.interface_config.channel))
             namespace.set_int(cls.PersistentDataKeys.VECTOR_BITRATE, can_config.interface_config.bitrate)
             namespace.set_int(cls.PersistentDataKeys.VECTOR_DATA_BITRATE, can_config.interface_config.data_bitrate)
        elif isinstance(can_config.interface_config, sdk.CANLinkConfig.KVaserConfig):
             namespace.set_int(cls.PersistentDataKeys.KVASER_CHANNEL, can_config.interface_config.channel)
             namespace.set_int(cls.PersistentDataKeys.KVASER_BITRATE, can_config.interface_config.bitrate)
             namespace.set_int(cls.PersistentDataKeys.KVASER_DATA_BITRATE, can_config.interface_config.data_bitrate)
             namespace.set_bool(cls.PersistentDataKeys.KVASER_FD_NON_ISO, can_config.interface_config.fd_non_iso)
        elif isinstance(can_config.interface_config, sdk.CANLinkConfig.PCANConfig):
             namespace.set_str(cls.PersistentDataKeys.PCAN_CHANNEL, can_config.interface_config.channel)
             namespace.set_int(cls.PersistentDataKeys.PCAN_BITRATE, can_config.interface_config.bitrate)
        elif isinstance(can_config.interface_config, sdk.CANLinkConfig.ETASConfig):
             namespace.set_str(cls.PersistentDataKeys.ETAS_CHANNEL, can_config.interface_config.channel)
             namespace.set_int(cls.PersistentDataKeys.ETAS_BITRATE, can_config.interface_config.bitrate)
             namespace.set_int(cls.PersistentDataKeys.ETAS_DATA_BITRATE, can_config.interface_config.data_bitrate)
        else:
            raise NotImplementedError("Unsupported CAN interface {can_interface}")

        namespace.prune(tools.get_class_attr_vals(cls.PersistentDataKeys))

    
    @classmethod
    def initialize_config(cls) -> sdk.BaseLinkConfig:
        namespace = gui_persistent_data.get_namespace(cls.__name__)

        interface_config: ANY_CAN_SUBCONFIG
        
        can_interface = sdk.CANLinkConfig.CANInterface(namespace.get_int(cls.PersistentDataKeys.INTERFACE, 0))
       
        if can_interface == sdk.CANLinkConfig.CANInterface.SocketCAN:
            interface_config = sdk.CANLinkConfig.SocketCANConfig(
                channel=namespace.get_str(cls.PersistentDataKeys.SOCKETCAN_CHANNEL, 'can0')
            )
       
        elif can_interface == sdk.CANLinkConfig.CANInterface.Vector:
            interface_config = sdk.CANLinkConfig.VectorConfig(
                channel=namespace.get_str(cls.PersistentDataKeys.VECTOR_CHANNEL, '0'),
                bitrate=namespace.get_int(cls.PersistentDataKeys.VECTOR_BITRATE, 500000),
                data_bitrate=namespace.get_int(cls.PersistentDataKeys.VECTOR_DATA_BITRATE, 500000)
            )
       
        elif can_interface == sdk.CANLinkConfig.CANInterface.KVaser:
            interface_config = sdk.CANLinkConfig.KVaserConfig(
                channel=namespace.get_int(cls.PersistentDataKeys.KVASER_CHANNEL, 0),
                bitrate=namespace.get_int(cls.PersistentDataKeys.KVASER_BITRATE, 500000),
                data_bitrate=namespace.get_int(cls.PersistentDataKeys.KVASER_DATA_BITRATE, 500000),
                fd_non_iso=namespace.get_bool(cls.PersistentDataKeys.KVASER_FD_NON_ISO, False)
            )
        
        elif can_interface == sdk.CANLinkConfig.CANInterface.PCAN:
            interface_config = sdk.CANLinkConfig.PCANConfig(
                channel=namespace.get_str(cls.PersistentDataKeys.PCAN_CHANNEL, '<channel>'),
                bitrate=namespace.get_int(cls.PersistentDataKeys.PCAN_BITRATE, 500000)
            )
        
        elif can_interface == sdk.CANLinkConfig.CANInterface.ETAS:
            interface_config = sdk.CANLinkConfig.ETASConfig(
                channel=namespace.get_str(cls.PersistentDataKeys.ETAS_CHANNEL, '<channel>'),
                bitrate=namespace.get_int(cls.PersistentDataKeys.ETAS_BITRATE, 500000),
                data_bitrate=namespace.get_int(cls.PersistentDataKeys.ETAS_BITRATE, 500000),
            )
        
        else:
            raise NotImplementedError(f"Unsupported CAN interface {can_interface}")

        return sdk.CANLinkConfig(
            interface=can_interface,
            txid=namespace.get_int(cls.PersistentDataKeys.TXID, 0),
            rxid=namespace.get_int(cls.PersistentDataKeys.RXID, 0),
            extended_id=namespace.get_bool(cls.PersistentDataKeys.EXTENDED_ID, False),
            fd=namespace.get_bool(cls.PersistentDataKeys.FD, False),
            bitrate_switch=namespace.get_bool(cls.PersistentDataKeys.BITRATE_SWITCH, False),
            interface_config=interface_config
        )
       
