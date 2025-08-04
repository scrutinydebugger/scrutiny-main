#    typing.py
#        Mypy typing information for API
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

from scrutiny.core.typehints import EmptyDict

import scrutiny.core.firmware_description
import scrutiny.server.device.links.typing

from scrutiny.tools.typing import *

WatchableType = Literal['alias', 'var', 'rpv']
# Mapping between app type and API type.
SFDMetadata = scrutiny.core.firmware_description.MetadataTypedDict
SerialLinkConfig = scrutiny.server.device.links.typing.SerialConfigDict
UdpLinkConfig = scrutiny.server.device.links.typing.UdpConfigDict
RttLinkConfig = scrutiny.server.device.links.typing.RttConfigDict
CanBusLinkConfig = scrutiny.server.device.links.typing.CanBusConfigDict

CanBusSocketCanSubconfig = scrutiny.server.device.links.typing.SocketCanSubconfigDict
CanBusVectorSubconfig = scrutiny.server.device.links.typing.VectorSubconfigDict
CanBusKVaserSubconfig = scrutiny.server.device.links.typing.KVaserCanSubconfigDict
CanBusPCANSubconfig = scrutiny.server.device.links.typing.PCANCanSubconfigDict
CanBusETASSubconfig = scrutiny.server.device.links.typing.ETASCanSubconfigDict
CANBUS_ANY_SUBCONFIG_DICT = scrutiny.server.device.links.typing.CANBUS_ANY_SUBCONFIG_DICT

LinkConfig = Union[EmptyDict, UdpLinkConfig, SerialLinkConfig, RttLinkConfig, CanBusLinkConfig]
LinkType = Literal['none', 'udp', 'serial', 'dummy', 'rtt', 'canbus']
SupportedFeature = Literal['memory_write', 'datalogging', 'user_command', '_64bits']
Datatype = Literal[
    'sint8', 'sint16', 'sint32', 'sint64', 'sint128', 'sint256',
    'uint8', 'uint16', 'uint32', 'uint64', 'uint128', 'uint256',
    'float8', 'float16', 'float32', 'float64', 'float128', 'float256',
    'cfloat8', 'cfloat16', 'cfloat32', 'cfloat64', 'cfloat128', 'cfloat256',
    'boolean'
]
CANInterfaceType = Literal['socketcan', 'vector']

DeviceCommStatus = Literal['unknown', 'disconnected', 'connecting', 'connected', 'connected_ready']
DataloggingState = Literal["unavailable", "standby", "waiting_for_trigger", "acquiring", "downloading", "error"]
DataloggingCondition = Literal['true', 'eq', 'neq', 'get', 'gt', 'let', 'lt', 'within', 'cmt']
DataloggingEncoding = Literal['raw']
LoopType = Literal['fixed_freq', 'variable_freq']


class DataloggingStatus(TypedDict):
    datalogging_state: DataloggingState
    completion_ratio: Optional[float]


class BaseC2SMessage(TypedDict):
    cmd: str
    reqid: int


class BaseS2CMessage(TypedDict):
    cmd: str
    reqid: Optional[int]


class EnumDefinition(TypedDict):
    name: str
    values: Dict[str, int]


class DatastoreEntryDefinition(TypedDict, total=False):
    id: str
    display_path: str
    datatype: Datatype
    type: WatchableType              # Can be missing
    enum: Optional[EnumDefinition]  # Can be missing. Default to None


class WatchableListContent(TypedDict):
    var: List[DatastoreEntryDefinition]
    alias: List[DatastoreEntryDefinition]
    rpv: List[DatastoreEntryDefinition]


class SamplingRate(TypedDict):
    type: Literal['fixed_freq', 'variable_freq']
    name: str
    frequency: Optional[float]
    identifier: int


class DataloggingCapabilities(TypedDict):
    encoding: Literal['raw']
    buffer_size: int
    max_nb_signal: int
    sampling_rates: List[SamplingRate]


class DeviceInfo(TypedDict):
    session_id: str
    device_id: str
    display_name: str
    max_tx_data_size: int
    max_rx_data_size: int
    max_bitrate_bps: Optional[int]
    rx_timeout_us: int
    heartbeat_timeout_us: int
    address_size_bits: int
    protocol_major: int
    protocol_minor: int
    supported_feature_map: Dict[SupportedFeature, bool]
    forbidden_memory_regions: List[Dict[Literal['start', 'size', 'end'], int]]
    readonly_memory_regions: List[Dict[Literal['start', 'size', 'end'], int]]
    datalogging_capabilities: Optional[DataloggingCapabilities]


class DeviceCommLinkDef(TypedDict):
    link_type: LinkType
    link_config: LinkConfig
    link_operational: bool


class GetWatchableList_Filter(TypedDict, total=False):
    type: WatchableType
    name: str


class WatchableCount(TypedDict):
    alias: int
    var: int
    rpv: int


class UpdateRecord(TypedDict):
    batch_index: int
    watchable: str
    value: Any


class DataloggingOperand(TypedDict):
    type: Literal['literal', 'watchable']
    value: Union[float, str]


class WatchableUpdateRecord(TypedDict):
    # We want compact key names to save some bandwidth
    id: str
    t: float
    v: Union[bool, float, int]


class SupportedCondition(TypedDict):
    name: str
    pretty_name: str
    help_str: str
    nb_operands: int


class DataloggingAcquisitionRequestSignalDef(TypedDict, total=False):
    path: str
    name: Optional[str]
    axis_id: int


class XAxisSignal(TypedDict):
    path: str
    name: Optional[str]


class DataloggingAxisDef(TypedDict):
    name: str
    id: int


class DataloggingAcquisitionMetadata(TypedDict):
    reference_id: str
    name: Optional[str]
    timestamp: float
    firmware_id: str
    firmware_metadata: Optional[SFDMetadata]


class LoggedWatchable(TypedDict):
    path: str
    type: str


class DataloggingSignalData(TypedDict):
    name: str
    data: List[Union[float, str]]
    watchable: Optional[LoggedWatchable]


class DataloggingSignalDataWithAxis(DataloggingSignalData):
    axis_id: int


class AxisNameUpdateEntry(TypedDict):
    id: int
    name: str


class C2S:
    "Client To Server"
    class Echo(BaseC2SMessage):
        payload: str

    class GetInstalledSFD(BaseC2SMessage):
        pass

    class GetLoadedSFD(BaseC2SMessage):
        pass

    class GetServerStatus(BaseC2SMessage):
        pass

    class GetDeviceInfo(BaseC2SMessage):
        pass

    class GetWatchableCount(BaseC2SMessage):
        pass

    class GetWatchableList(BaseC2SMessage):
        max_per_response: int
        filter: GetWatchableList_Filter

    class LoadSFD(BaseC2SMessage):
        firmware_id: str

    class SubscribeWatchable(BaseC2SMessage):
        watchables: List[str]

    class UnsubscribeWatchable(BaseC2SMessage):
        watchables: List[str]

    class SetLinkConfig(BaseC2SMessage, DeviceCommLinkDef):
        pass

    class WriteValue(BaseC2SMessage):
        updates: List[UpdateRecord]

    class RequestDataloggingAcquisition(BaseC2SMessage):
        name: Optional[str]
        sampling_rate_id: int
        decimation: int
        timeout: float
        trigger_hold_time: float
        probe_location: float
        condition: DataloggingCondition
        operands: List[DataloggingOperand]
        yaxes: List[DataloggingAxisDef]
        signals: List[DataloggingAcquisitionRequestSignalDef]
        x_axis_type: Literal['measured_time', 'ideal_time', 'signal', 'index']
        x_axis_signal: Optional[XAxisSignal]

    class ReadDataloggingAcquisitionContent(BaseC2SMessage):
        reference_id: str

    class ListDataloggingAcquisitions(BaseC2SMessage):
        reference_id: Optional[str]
        firmware_id: Optional[str]
        before_timestamp: Optional[int]
        count: int

    class UpdateDataloggingAcquisition(BaseC2SMessage):
        reference_id: str
        name: Optional[str]
        axis_name: Optional[List[AxisNameUpdateEntry]]

    class DeleteDataloggingAcquisition(BaseC2SMessage):
        reference_id: str

    class ReadMemory(BaseC2SMessage):
        address: int
        size: int

    class WriteMemory(BaseC2SMessage):
        address: int
        data: str

    class UserCommand(BaseC2SMessage):
        subfunction: int
        data: str

    class GetServerStats(BaseC2SMessage):
        pass

    GetPossibleLinkConfig = Dict[Any, Any]  # Todo


class S2C:
    "Server To Client"
    class Empty(BaseS2CMessage):
        pass

    class Echo(BaseS2CMessage):
        payload: str

    class Error(BaseS2CMessage):
        request_cmd: str
        msg: str

    class Welcome(BaseS2CMessage):
        server_time_zero_timestamp: float

    class GetInstalledSFD(BaseS2CMessage):
        sfd_list: Dict[str, SFDMetadata]

    class GetLoadedSFD(BaseS2CMessage):
        firmware_id: Optional[str]
        metadata: Optional[SFDMetadata]

    class InformServerStatus(BaseS2CMessage):
        device_status: DeviceCommStatus
        device_session_id: Optional[str]
        loaded_sfd_firmware_id: Optional[str]
        datalogging_status: DataloggingStatus
        device_comm_link: DeviceCommLinkDef   # Dict is Any,Any.  Should be EmptyDict.

    class GetDeviceInfo(BaseS2CMessage):
        available: bool
        device_info: Optional[DeviceInfo]

    class GetWatchableCount(BaseS2CMessage):
        qty: WatchableCount

    class GetWatchableList(BaseS2CMessage):
        qty: WatchableCount
        content: WatchableListContent
        done: bool

    class SubscribeWatchable(BaseS2CMessage):
        subscribed: Dict[str, DatastoreEntryDefinition]

    class UnsubscribeWatchable(BaseS2CMessage):
        unsubscribed: List[str]

    class WatchableUpdate(BaseS2CMessage):
        updates: List[WatchableUpdateRecord]

    GetPossibleLinkConfig = Dict[Any, Any]  # TODO

    class WriteValue(BaseS2CMessage):
        count: int
        request_token: str

    class WriteCompletion(BaseS2CMessage):
        batch_index: int
        watchable: str
        success: bool
        request_token: str
        completion_server_time_us: float

    class RequestDataloggingAcquisition(BaseS2CMessage):
        request_token: str

    class InformDataloggingAcquisitionComplete(BaseS2CMessage):
        request_token: str
        reference_id: Optional[str]
        success: bool
        detail_msg: str

    class InformDataloggingListChanged(BaseS2CMessage):
        reference_id: Optional[str]
        action: Literal['delete', 'new', 'update', 'delete_all']

    class ListDataloggingAcquisition(BaseS2CMessage):
        acquisitions: List[DataloggingAcquisitionMetadata]

    class ReadDataloggingAcquisitionContent(BaseS2CMessage):
        reference_id: str
        firmware_id: str
        firmware_name: Optional[str]
        name: str
        timestamp: float
        trigger_index: Optional[int]
        yaxes: List[DataloggingAxisDef]
        signals: List[DataloggingSignalDataWithAxis]
        xdata: DataloggingSignalData

    class UpdateDataloggingAcquisition(BaseS2CMessage):
        pass

    class DeleteDataloggingAcquisition(BaseS2CMessage):
        pass

    class ReadMemory(BaseS2CMessage):
        request_token: str

    class ReadMemoryComplete(BaseS2CMessage):
        request_token: str
        success: bool
        data: Optional[str]
        completion_server_time_us: float
        detail_msg: Optional[str]

    class WriteMemory(BaseS2CMessage):
        request_token: str

    class WriteMemoryComplete(BaseS2CMessage):
        request_token: str
        success: bool
        completion_server_time_us: float
        detail_msg: Optional[str]

    class UserCommand(BaseS2CMessage):
        subfunction: int
        data: str

    class GetServerStats(BaseS2CMessage):
        uptime: float
        invalid_request_count: int
        unexpected_error_count: int
        client_count: int
        to_all_clients_datarate_byte_per_sec: float
        from_any_client_datarate_byte_per_sec: float
        msg_received: int
        msg_sent: int
        device_session_count: int
        to_device_datarate_byte_per_sec: float
        from_device_datarate_byte_per_sec: float
        device_request_per_sec: float


C2SMessage = Union[
    C2S.Echo,
    C2S.GetInstalledSFD,
    C2S.GetLoadedSFD,
    C2S.GetServerStatus,
    C2S.GetDeviceInfo,
    C2S.GetWatchableCount,
    C2S.GetWatchableList,
    C2S.LoadSFD,
    C2S.SubscribeWatchable,
    C2S.UnsubscribeWatchable,
    C2S.GetPossibleLinkConfig,
    C2S.WriteValue,
    C2S.RequestDataloggingAcquisition,
    C2S.ReadDataloggingAcquisitionContent,
    C2S.ListDataloggingAcquisitions,
    C2S.UpdateDataloggingAcquisition,
    C2S.DeleteDataloggingAcquisition,
    C2S.ReadMemory,
    C2S.WriteMemory,
    C2S.UserCommand,
]

S2CMessage = Union[
    S2C.Empty,
    S2C.Echo,
    S2C.Error,
    S2C.Welcome,
    S2C.GetInstalledSFD,
    S2C.GetLoadedSFD,
    S2C.InformServerStatus,
    S2C.GetDeviceInfo,
    S2C.GetWatchableCount,
    S2C.GetWatchableList,
    S2C.SubscribeWatchable,
    S2C.UnsubscribeWatchable,
    S2C.WatchableUpdate,
    S2C.GetPossibleLinkConfig,
    S2C.WriteValue,
    S2C.WriteCompletion,
    S2C.RequestDataloggingAcquisition,
    S2C.InformDataloggingListChanged,
    S2C.ListDataloggingAcquisition,
    S2C.ReadDataloggingAcquisitionContent,
    S2C.DeleteDataloggingAcquisition,
    S2C.ReadMemory,
    S2C.ReadMemoryComplete,
    S2C.WriteMemory,
    S2C.WriteMemoryComplete,
    S2C.UserCommand,
]
