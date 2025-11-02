#    _api_parser.py
#        Internal parsing function for the Scrutiny server API messages
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

import binascii
import time
from base64 import b64decode
from datetime import datetime
from dataclasses import dataclass

import scrutiny.sdk
import scrutiny.sdk.datalogging
sdk = scrutiny.sdk  # Workaround for vscode linter an submodule on alias
from scrutiny.core.basic_types import *
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.firmware_description import MetadataTypedDict
from scrutiny.core import path_tools
from scrutiny.server.api.API import API
from scrutiny.server.api import typing as api_typing

from scrutiny.tools import validation
from scrutiny.tools.typing import *
import typing


@dataclass(frozen=True, slots=True)
class WelcomeData:
    server_time_zero_timestamp: float


@dataclass(frozen=True, slots=True)
class WatchableUpdate:
    server_id: str
    value: Union[bool, int, float]
    server_time_us: float


@dataclass(frozen=True, slots=True)
class WriteCompletion:
    request_token: str
    watchable: str
    success: bool
    server_time_us: float
    batch_index: int


@dataclass(frozen=True, slots=True)
class WriteConfirmation:
    request_token: str
    count: int


@dataclass(frozen=True, slots=True)
class MemoryReadCompletion:
    request_token: str
    success: bool
    data: Optional[bytes]
    error: str
    server_time_us: float
    local_monotonic_timestamp: float


@dataclass(frozen=True, slots=True)
class MemoryWriteCompletion:
    request_token: str
    success: bool
    error: str
    server_time_us: float
    local_monotonic_timestamp: float


@dataclass(frozen=True, slots=True)
class DataloggingCompletion:
    request_token: str
    reference_id: Optional[str]
    success: bool
    detail_msg: str


@dataclass(frozen=True, slots=True)
class GetWatchableListResponse:
    done: bool
    data: sdk.WatchableListContentPart


@dataclass(frozen=True, slots=True)
class DataloggingListChangeResponse:
    action: sdk.DataloggingListChangeType
    reference_id: Optional[str]


@dataclass(frozen=True, slots=True)
class SFDDownloadChunk:
    firmware_id: str
    data: bytes
    chunk_index: int
    total_size: int


@dataclass(frozen=True, slots=True)
class UploadSFDInitResponse:
    token: str
    will_overwrite: bool


@dataclass(frozen=True, slots=True)
class UploadSFDDataResponse:
    completed: bool
    actual_size: int
    sfd_info: Optional[sdk.SFDInfo]


T = TypeVar('T', str, int, float, bool)
WATCHABLE_TYPE_KEY = Literal['rpv', 'alias', 'var']


def _check_response_dict(cmd: str, d: Any, name: str, types: Union[Type[Any], Iterable[Type[Any]]], prefix: str = '') -> None:
    try:
        validation.assert_dict_key(d, name, types, prefix)
    except Exception as e:
        raise sdk.exceptions.BadResponseError(f"In message {cmd}: {e}")


def _fetch_dict_val(d: Any, path: str, default: Optional[T], allow_none: bool = True) -> Any:
    if d is None:
        return default
    assert isinstance(d, dict)
    parts = path.split('.')
    key = parts[0]
    next_parts = parts[1:]

    if not key:
        raise RuntimeError('Empty path to fetch from dict')

    if key not in d:
        return default

    if len(next_parts) == 0:
        if d[key] is None:
            if allow_none:
                return None
            raise sdk.exceptions.BadResponseError(f'Field {key} cannot be None')
        return d[key]
    else:
        return _fetch_dict_val(d[key], '.'.join(next_parts), default=default)


def _fetch_dict_val_of_type(d: Any, path: str, wanted_type: Type[T], default: Optional[T], allow_none: bool = True) -> Optional[T]:
    val = _fetch_dict_val(d, path, default, allow_none)
    if val is None:
        if allow_none:
            return None
        raise sdk.exceptions.BadResponseError(f'Field {path} cannot be None')
    return wanted_type(val)


def _fetch_dict_val_of_type_no_none(d: Any, path: str, wanted_type: Type[T], default: T) -> T:
    return cast(T, _fetch_dict_val_of_type(d, path, wanted_type, default, allow_none=False))


def _read_sfd_metadata_from_incomplete_dict(obj: Optional[MetadataTypedDict]) -> Optional[sdk.SFDMetadata]:
    if obj is None:
        return None

    timestamp = _fetch_dict_val(obj, 'generation_info.time', default=None)
    if not isinstance(timestamp, (int, type(None))) or isinstance(timestamp, bool):
        raise sdk.exceptions.BadResponseError(f"Invalid timestamp in SFD metadata")

    try:
        # This will raise a TypeError if the data is not of the right type.
        # Expect the server to give the right thing.

        return sdk.SFDMetadata(
            author=_fetch_dict_val(obj, 'author', default=None),
            project_name=_fetch_dict_val(obj, 'project_name', default=None),
            version=_fetch_dict_val(obj, 'version', default=None),
            generation_info=sdk.SFDGenerationInfo(
                python_version=_fetch_dict_val(obj, 'generation_info.python_version', default=None),
                scrutiny_version=_fetch_dict_val(obj, 'generation_info.scrutiny_version', default=None),
                system_type=_fetch_dict_val(obj, 'generation_info.system_type', default=None),
                timestamp=datetime.fromtimestamp(timestamp) if isinstance(timestamp, int) else None
            )
        )
    except (TypeError, ValueError) as e:
        raise sdk.exceptions.BadResponseError(f"Invalid SFD metadata: {e}")


def _read_sfd_info(cmd: str, sfd_info: api_typing.SFDInfo) -> sdk.SFDInfo:
    _check_response_dict(cmd, sfd_info, 'firmware_id', str)
    _check_response_dict(cmd, sfd_info, 'metadata', (dict, type(None)))
    _check_response_dict(cmd, sfd_info, 'filesize', (int, type(None)))

    if sfd_info['filesize'] is not None:
        if sfd_info['filesize'] < 0:
            raise sdk.exceptions.BadResponseError("Invalid filesize")

        if len(sfd_info['firmware_id']) == 0:
            raise sdk.exceptions.BadResponseError("Invalid firmware_id")

    return sdk.SFDInfo(
        firmware_id=sfd_info['firmware_id'],
        metadata=_read_sfd_metadata_from_incomplete_dict(sfd_info['metadata']),
        filesize=sfd_info['filesize']
    )


def parse_get_watchable_list(response: api_typing.S2C.GetWatchableList) -> GetWatchableListResponse:
    """Parse a response to get_watchable_list and assume the request was for a single watchable"""
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE

    _check_response_dict(cmd, response, 'qty.alias', int)
    _check_response_dict(cmd, response, 'qty.rpv', int)
    _check_response_dict(cmd, response, 'qty.var', int)
    _check_response_dict(cmd, response, 'qty.var_factory', int)
    _check_response_dict(cmd, response, 'done', bool)

    _check_response_dict(cmd, response, 'content.alias', list)
    _check_response_dict(cmd, response, 'content.rpv', list)
    _check_response_dict(cmd, response, 'content.var', list)
    _check_response_dict(cmd, response, 'content.var_factory', list)

    outdata = GetWatchableListResponse(
        done=response['done'],
        data=sdk.WatchableListContentPart()
    )

    typekey_to_dict_ref: Dict[WATCHABLE_TYPE_KEY, Dict[str, sdk.WatchableConfiguration]] = {
        'rpv': outdata.data.rpv,
        'alias': outdata.data.alias,
        'var': outdata.data.var
    }
    typekey_to_watchable_type: Dict[WATCHABLE_TYPE_KEY, sdk.WatchableType] = {
        'rpv': sdk.WatchableType.RuntimePublishedValue,
        'alias': sdk.WatchableType.Alias,
        'var': sdk.WatchableType.Variable,
    }

    def get_enum(element: Union[api_typing.DatastoreEntryDefinition, api_typing.VariableFactoryDefinition]) -> Optional[EmbeddedEnum]:
        enum: Optional[EmbeddedEnum] = None
        if 'enum' in element and element['enum'] is not None:
            _check_response_dict(cmd, element, 'enum', dict)
            _check_response_dict(cmd, element, 'enum.name', str)
            _check_response_dict(cmd, element, 'enum.values', dict)
            if len(element['enum']['name']) == 0:
                raise sdk.exceptions.BadResponseError(f"Empty enum name")

            enum = EmbeddedEnum(name=element['enum']['name'])
            for key, val in element['enum']['values'].items():
                if not isinstance(key, str):
                    raise sdk.exceptions.BadResponseError('Invalid enum. Key is not a string')
                if len(key) == 0:
                    raise sdk.exceptions.BadResponseError('Invalid enum. Key is an empty string')
                if not isinstance(val, int) or isinstance(val, bool):   # bools are int for python
                    raise sdk.exceptions.BadResponseError('Invalid enum. Value is not an integer')
                enum.add_value(key, val)
        return enum

    def get_dtype(element: Union[api_typing.DatastoreEntryDefinition, api_typing.VariableFactoryDefinition], keyprefix: str) -> EmbeddedDataType:
        _check_response_dict(cmd, element, 'dtype', str, keyprefix)

        if element['dtype'] not in API.APISTR_2_DATATYPE:
            raise sdk.exceptions.BadResponseError(f"Unknown datatype {element['dtype']}")

        return EmbeddedDataType(API.APISTR_2_DATATYPE[element['dtype']])

    def get_path(element: Union[api_typing.DatastoreEntryDefinition, api_typing.VariableFactoryDefinition], keyprefix: str) -> str:
        _check_response_dict(cmd, element, 'path', str, keyprefix)
        if len(element['path']) == 0:
            raise sdk.exceptions.BadResponseError(f"Empty path")
        return element['path']

    def get_array_dims(element: api_typing.VariableFactoryDefinition, keyprefix: str) -> Dict[str, Tuple[int, ...]]:
        _check_response_dict(cmd, element, 'factory_params.array_nodes', dict, keyprefix)
        outdict: Dict[str, Tuple[int, ...]] = {}
        keyprefix += ".factory_params.array_nodes"
        for path, dims in element['factory_params']['array_nodes'].items():
            if not isinstance(path, str) or len(path) == 0:
                raise sdk.exceptions.BadResponseError(f"{keyprefix}: Array definition not mapped to a valid string")

            if not isinstance(dims, list):
                raise sdk.exceptions.BadResponseError(f"{keyprefix}: Array dimensions are not a list")

            for dim in dims:
                if not isinstance(dim, int):
                    raise sdk.exceptions.BadResponseError(f"{keyprefix}: Invalid array dimensions")

            if path in outdict:
                raise sdk.exceptions.BadResponseError(f"{keyprefix}: Duplicate array node path")

            outdict[path] = tuple(dims)

        return outdict

    for typekey in ['rpv', 'alias', 'var', 'var_factory']:
        typekey = cast(Literal['rpv', 'alias', 'var', 'var_factory'], typekey)
        if response['qty'][typekey] != len(response['content'][typekey]):
            raise sdk.exceptions.BadResponseError(
                f"Mismatch between expected element count ({response['qty'][typekey]}) and actual element count ({len(response['content'][typekey])})")

        container = response['content'][typekey]
        if typekey in ['var', 'alias', 'rpv']:
            typekey = cast(Literal['var', 'alias', 'rpv'], typekey)
            outdict = typekey_to_dict_ref[typekey]
            for i in range(len(container)):
                keyprefix = f'content.{typekey}[{i}]'
                element = cast(api_typing.DatastoreEntryDefinition, container[i])
                path = get_path(element, keyprefix)
                datatype = get_dtype(element, keyprefix)
                enum = get_enum(element)

                outdict[path] = sdk.WatchableConfiguration(
                    watchable_type=typekey_to_watchable_type[typekey],
                    datatype=datatype,
                    enum=enum
                )
        elif typekey == 'var_factory':
            for i in range(len(container)):
                keyprefix = f'content.{typekey}[{i}]'
                element = cast(api_typing.VariableFactoryDefinition, container[i])

                path = get_path(element, keyprefix)
                datatype = get_dtype(element, keyprefix)
                enum = get_enum(element)
                array_dims = get_array_dims(element, keyprefix)
                for subpath in array_dims.keys():
                    if not path_tools.is_subpath(subpath, path):
                        raise sdk.exceptions.BadResponseError(
                            f"Received a Variable Factory with array nodes that does not match the access path ({path}).")

                outdata.data.var_factory[path] = sdk.VariableFactoryInterface(
                    access_path=path,
                    datatype=datatype,
                    enum=enum,
                    array_dims=array_dims
                )
        else:
            raise sdk.exceptions.BadResponseError(f"Unknown data type {typekey}")

    return outdata


def parse_subscribe_watchable_response(response: api_typing.S2C.SubscribeWatchable) -> Dict[str, sdk.WatchableConfigurationWithServerID]:
    """Parse a response to get_watchable_list and assume the request was for a single watchable"""
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE

    outdict: Dict[str, sdk.WatchableConfigurationWithServerID] = {}
    _check_response_dict(cmd, response, 'subscribed', dict)
    for k, v in response['subscribed'].items():
        if not isinstance(k, str):
            raise sdk.exceptions.BadResponseError('Gotten a subscription dict with invalid key')

        _check_response_dict(cmd, v, 'dtype', str)
        _check_response_dict(cmd, v, 'type', str)
        _check_response_dict(cmd, v, 'id', str)

        enum: Optional[EmbeddedEnum] = None
        if 'enum' in v and v['enum'] is not None:
            _check_response_dict(cmd, v, 'enum', dict)
            _check_response_dict(cmd, v, 'enum.name', str)
            _check_response_dict(cmd, v, 'enum.values', dict)
            enum = EmbeddedEnum(name=v['enum']['name'])
            for key, val in v['enum']['values'].items():
                if not isinstance(key, str):
                    raise sdk.exceptions.BadResponseError('Invalid enum. Key is not a string')
                if not isinstance(val, int):
                    raise sdk.exceptions.BadResponseError('Invalid enum. Value is not an integer')
                enum.add_value(key, val)

        if v['dtype'] not in API.APISTR_2_DATATYPE:
            raise sdk.exceptions.BadResponseError(f"Unknown datatype {v['dtype']}")

        datatype = EmbeddedDataType(API.APISTR_2_DATATYPE[v['dtype']])
        if v['type'] == 'alias':
            watchable_type = sdk.WatchableType.Alias
        elif v['type'] == 'var':
            watchable_type = sdk.WatchableType.Variable
        elif v['type'] == 'rpv':
            watchable_type = sdk.WatchableType.RuntimePublishedValue
        else:
            raise sdk.exceptions.BadResponseError(f"Unsupported watchable type {v['type']}")

        outdict[k] = sdk.WatchableConfigurationWithServerID(
            server_id=v['id'],
            watchable_type=watchable_type,
            datatype=datatype,
            enum=enum
        )

    return outdict


def parse_get_device_info(response: api_typing.S2C.GetDeviceInfo) -> Optional[sdk.DeviceInfo]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_DEVICE_INFO
    NoneType: Type[None] = type(None)

    _check_response_dict(cmd, response, 'available', bool)
    _check_response_dict(cmd, response, 'device_info', (dict, NoneType))

    if response['available'] == False:
        _check_response_dict(cmd, response, 'device_info', type(None))
        return None
    else:
        _check_response_dict(cmd, response, 'device_info', dict)
        _check_response_dict(cmd, response, 'device_info.session_id', str)
        _check_response_dict(cmd, response, 'device_info.device_id', str)
        _check_response_dict(cmd, response, 'device_info.display_name', str)
        _check_response_dict(cmd, response, 'device_info.max_tx_data_size', int)
        _check_response_dict(cmd, response, 'device_info.max_rx_data_size', int)
        _check_response_dict(cmd, response, 'device_info.max_bitrate_bps', (int, type(None)))
        _check_response_dict(cmd, response, 'device_info.rx_timeout_us', int)
        _check_response_dict(cmd, response, 'device_info.heartbeat_timeout_us', int)
        _check_response_dict(cmd, response, 'device_info.address_size_bits', int)
        _check_response_dict(cmd, response, 'device_info.protocol_major', int)
        _check_response_dict(cmd, response, 'device_info.protocol_minor', int)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map.memory_write', bool)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map.datalogging', bool)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map.user_command', bool)
        _check_response_dict(cmd, response, 'device_info.supported_feature_map._64bits', bool)
        _check_response_dict(cmd, response, 'device_info.forbidden_memory_regions', list)
        _check_response_dict(cmd, response, 'device_info.readonly_memory_regions', list)
        _check_response_dict(cmd, response, 'device_info.datalogging_capabilities', (dict, type(None)))
        device_info = response['device_info']
        assert device_info is not None
        forbidden_regions: List[sdk.MemoryRegion] = []
        for region in device_info['forbidden_memory_regions']:
            _check_response_dict(cmd, region, 'start', int)
            _check_response_dict(cmd, region, 'end', int)
            if region['end'] <= region['start']:
                raise sdk.exceptions.BadResponseError(f'Received a forbidden memory region with incoherent start and end in message "{cmd}"')
            size = region['end'] - region['start'] + 1
            if size <= 0:
                raise sdk.exceptions.BadResponseError(f'Got a forbidden memory region with an invalid size "{cmd}"')
            forbidden_regions.append(sdk.MemoryRegion(
                start=region['start'],
                size=size
            ))

        readonly_regions: List[sdk.MemoryRegion] = []
        for region in device_info['readonly_memory_regions']:
            _check_response_dict(cmd, region, 'start', int)
            _check_response_dict(cmd, region, 'end', int)
            if region['end'] <= region['start']:
                raise sdk.exceptions.BadResponseError(f'Received a readonly memory region with incoherent start and end in message "{cmd}"')
            size = region['end'] - region['start'] + 1
            if size <= 0:
                raise sdk.exceptions.BadResponseError(f'Got a readonly memory region with an invalid size "{cmd}"')
            readonly_regions.append(sdk.MemoryRegion(
                start=region['start'],
                size=size
            ))

        if device_info['address_size_bits'] not in typing.get_args(sdk.AddressSize):
            raise sdk.exceptions.BadResponseError(f"Unexpected address size {device_info['address_size_bits']}")

        datalogging_capabilities: Optional[sdk.DataloggingCapabilities] = None
        if device_info['datalogging_capabilities'] is not None:
            cap_dict = device_info['datalogging_capabilities']

            _check_response_dict(cmd, cap_dict, 'buffer_size', int)
            _check_response_dict(cmd, cap_dict, 'encoding', str)
            _check_response_dict(cmd, cap_dict, 'max_nb_signal', int)
            _check_response_dict(cmd, cap_dict, 'sampling_rates', list)

            api_to_sdk_encoding_map: Dict[api_typing.DataloggingEncoding, sdk.datalogging.DataloggingEncoding] = {
                'raw': sdk.datalogging.DataloggingEncoding.RAW,
            }

            encoding = cap_dict['encoding']
            if encoding not in api_to_sdk_encoding_map:
                raise sdk.exceptions.BadResponseError(f'Datalogging encoding is not supported: "{encoding}"')

            sampling_rates: List[sdk.datalogging.SamplingRate] = []
            for rate_entry in cap_dict['sampling_rates']:
                _check_response_dict(cmd, rate_entry, 'identifier', int)
                _check_response_dict(cmd, rate_entry, 'name', str)
                _check_response_dict(cmd, rate_entry, 'type', str)

                rate: sdk.datalogging.SamplingRate
                if rate_entry['type'] == 'fixed_freq':
                    _check_response_dict(cmd, rate_entry, 'frequency', (float, int))
                    assert rate_entry['frequency'] is not None

                    rate = sdk.datalogging.FixedFreqSamplingRate(
                        identifier=rate_entry['identifier'],
                        name=rate_entry['name'],
                        frequency=float(rate_entry['frequency']),
                    )
                elif rate_entry['type'] == 'variable_freq':
                    rate = sdk.datalogging.VariableFreqSamplingRate(
                        identifier=rate_entry['identifier'],
                        name=rate_entry['name'],
                    )
                else:
                    raise sdk.exceptions.BadResponseError(f'Unsupported sampling rate type: {rate_entry["type"]}')

                sampling_rates.append(rate)

            datalogging_capabilities = sdk.datalogging.DataloggingCapabilities(
                buffer_size=cap_dict['buffer_size'],
                encoding=api_to_sdk_encoding_map[encoding],
                max_nb_signal=cap_dict['max_nb_signal'],
                sampling_rates=sampling_rates
            )

        return sdk.DeviceInfo(
            session_id=device_info['session_id'],
            device_id=device_info['device_id'],
            display_name=device_info['display_name'],
            max_tx_data_size=device_info['max_tx_data_size'],
            max_rx_data_size=device_info['max_rx_data_size'],
            max_bitrate_bps=device_info['max_bitrate_bps'],
            rx_timeout_us=device_info['rx_timeout_us'],
            heartbeat_timeout=float(device_info['heartbeat_timeout_us']) * 1e-6,
            address_size_bits=cast(sdk.AddressSize, device_info['address_size_bits']),
            protocol_major=device_info['protocol_major'],
            protocol_minor=device_info['protocol_minor'],
            supported_features=sdk.SupportedFeatureMap(
                memory_write=device_info['supported_feature_map']['memory_write'],
                datalogging=device_info['supported_feature_map']['datalogging'],
                user_command=device_info['supported_feature_map']['user_command'],
                sixtyfour_bits=device_info['supported_feature_map']['_64bits'],
            ),
            forbidden_memory_regions=forbidden_regions,
            readonly_memory_regions=readonly_regions,
            datalogging_capabilities=datalogging_capabilities
        )


def parse_inform_server_status(response: api_typing.S2C.InformServerStatus) -> sdk.ServerInfo:
    """Parse the inform_server_status message"""

    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_SERVER_STATUS
    NoneType: Type[None] = type(None)

    _check_response_dict(cmd, response, 'device_status', str)
    _check_response_dict(cmd, response, 'device_session_id', (str, NoneType))

    def _device_status_from_api(api_val: api_typing.DeviceCommStatus) -> sdk.DeviceCommState:
        if api_val == API.DeviceCommStatus.UNKNOWN:
            return sdk.DeviceCommState.NA
        if api_val == API.DeviceCommStatus.DISCONNECTED:
            return sdk.DeviceCommState.Disconnected
        if api_val == API.DeviceCommStatus.CONNECTING:
            return sdk.DeviceCommState.Connecting
        if api_val == API.DeviceCommStatus.CONNECTED:
            return sdk.DeviceCommState.Connecting   # This is not a mistake Connected->Connecting, for sdk simplicity
        if api_val == API.DeviceCommStatus.CONNECTED_READY:
            return sdk.DeviceCommState.ConnectedReady
        raise sdk.exceptions.BadResponseError(f'Unsupported device communication status "{api_val}"')

    _check_response_dict(cmd, response, 'loaded_sfd_firmware_id', (str, type(None)))

    _check_response_dict(cmd, response, 'datalogging_status.datalogging_state', str)
    _check_response_dict(cmd, response, 'datalogging_status.completion_ratio', [NoneType, float, int])

    def _datalogging_status(api_val: api_typing.DataloggingState) -> sdk.DataloggingState:
        if api_val == API.DataloggingStateString.UNAVAILABLE:
            return sdk.DataloggingState.NA
        elif api_val == API.DataloggingStateString.STANDBY:
            return sdk.DataloggingState.Standby
        elif api_val == API.DataloggingStateString.WAITING_FOR_TRIGGER:
            return sdk.DataloggingState.WaitForTrigger
        elif api_val == API.DataloggingStateString.ACQUIRING:
            return sdk.DataloggingState.Acquiring
        elif api_val == API.DataloggingStateString.DOWNLOADING:
            return sdk.DataloggingState.Downloading
        elif api_val == API.DataloggingStateString.ERROR:
            return sdk.DataloggingState.Error
        raise sdk.exceptions.BadResponseError(f'Unsupported datalogging state "{api_val}"')

    completion_ratio = response['datalogging_status']['completion_ratio']
    if completion_ratio is not None:
        completion_ratio = float(completion_ratio)

    datalogging = sdk.DataloggingInfo(
        completion_ratio=completion_ratio,
        state=_datalogging_status(response['datalogging_status']['datalogging_state'])
    )

    _check_response_dict(cmd, response, 'device_comm_link.link_type', str)
    _check_response_dict(cmd, response, 'device_comm_link.link_operational', bool)
    _check_response_dict(cmd, response, 'device_comm_link.demo_mode', bool)

    def _link_type(api_val: api_typing.LinkType) -> sdk.DeviceLinkType:
        if api_val == 'none':
            return sdk.DeviceLinkType.NONE
        if api_val == 'serial':
            return sdk.DeviceLinkType.Serial
        if api_val == 'dummy':
            return sdk.DeviceLinkType._Dummy
        if api_val == 'udp':
            return sdk.DeviceLinkType.UDP
        if api_val == 'rtt':
            return sdk.DeviceLinkType.RTT
        if api_val == 'canbus':
            return sdk.DeviceLinkType.CAN
        raise sdk.exceptions.BadResponseError(f'Unsupported device link type "{api_val}"')

    link_type = _link_type(response['device_comm_link']['link_type'])
    link_operational = response['device_comm_link']['link_operational']
    link_config: Optional[sdk.SupportedLinkConfig]
    if link_type == sdk.DeviceLinkType.NONE:
        link_config = sdk.NoneLinkConfig()
    elif link_type == sdk.DeviceLinkType.UDP:
        udp_config = cast(api_typing.UdpLinkConfig, response['device_comm_link']['link_config'])
        _check_response_dict(cmd, response, 'device_comm_link.link_config.host', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.port', int)
        link_config = sdk.UDPLinkConfig(
            host=udp_config['host'],
            port=udp_config['port'],
        )
    elif link_type == sdk.DeviceLinkType.Serial:
        serial_config = cast(api_typing.SerialLinkConfig, response['device_comm_link']['link_config'])
        _check_response_dict(cmd, response, 'device_comm_link.link_config.portname', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.baudrate', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.stopbits', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.databits', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.parity', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.start_delay', (int, float))

        STOPBIT_TO_SDK = {
            '1': sdk.SerialLinkConfig.StopBits.ONE,
            '1.5': sdk.SerialLinkConfig.StopBits.ONE_POINT_FIVE,
            '2': sdk.SerialLinkConfig.StopBits.TWO
        }

        PARITY_TO_SDK = {
            'none': sdk.SerialLinkConfig.Parity.NONE,
            'even': sdk.SerialLinkConfig.Parity.EVEN,
            'odd': sdk.SerialLinkConfig.Parity.ODD,
            'mark': sdk.SerialLinkConfig.Parity.MARK,
            'space': sdk.SerialLinkConfig.Parity.SPACE
        }

        DATABITS_TO_SDK = {
            5: sdk.SerialLinkConfig.DataBits.FIVE,
            6: sdk.SerialLinkConfig.DataBits.SIX,
            7: sdk.SerialLinkConfig.DataBits.SEVEN,
            8: sdk.SerialLinkConfig.DataBits.EIGHT,
        }

        api_stopbits = serial_config['stopbits']
        if api_stopbits not in STOPBIT_TO_SDK:
            raise sdk.exceptions.BadResponseError(f'Unsupported stop bit value "{api_stopbits}" in message {cmd}')

        api_parity = serial_config['parity']
        if api_parity not in PARITY_TO_SDK:
            raise sdk.exceptions.BadResponseError(f'Unsupported parity value "{api_parity}" in message {cmd}')

        api_databits = serial_config['databits']
        if api_databits not in DATABITS_TO_SDK:
            raise sdk.exceptions.BadResponseError(f'Unsupported number of databits value "{api_databits}" in message {cmd}')

        start_delay = float(serial_config['start_delay'])
        if start_delay < 0:
            raise sdk.exceptions.BadResponseError(f'Unsupported start delay value "{start_delay}" in message {cmd}')

        link_config = sdk.SerialLinkConfig(
            port=serial_config['portname'],
            baudrate=serial_config['baudrate'],
            stopbits=STOPBIT_TO_SDK[api_stopbits],
            parity=PARITY_TO_SDK[api_parity],
            databits=DATABITS_TO_SDK[api_databits],
            start_delay=serial_config['start_delay']
        )
    elif link_type == sdk.DeviceLinkType.RTT:
        _check_response_dict(cmd, response, 'device_comm_link.link_config.jlink_interface', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.target_device', str)
        rtt_config = cast(api_typing.RttLinkConfig, response['device_comm_link']['link_config'])
        interface_name = rtt_config['jlink_interface']
        try:
            jlink_interface = sdk.RTTLinkConfig.JLinkInterface(interface_name)
        except ValueError:
            raise sdk.exceptions.BadResponseError(f'Invalid JLink Interface "{interface_name}"')

        link_config = sdk.RTTLinkConfig(
            target_device=rtt_config['target_device'],
            jlink_interface=jlink_interface
        )
    elif link_type == sdk.DeviceLinkType.CAN:
        _check_response_dict(cmd, response, 'device_comm_link.link_config.interface', str)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.txid', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.rxid', int)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.extended_id', bool)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.fd', bool)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.bitrate_switch', bool)
        _check_response_dict(cmd, response, 'device_comm_link.link_config.subconfig', dict)

        canbus_config = cast(api_typing.CanBusLinkConfig, response['device_comm_link']['link_config'])

        def _can_interface_type(api_val: api_typing.CANInterfaceType) -> sdk.CANLinkConfig.CANInterface:
            api_val_lower = api_val.lower().strip()
            if api_val_lower == 'socketcan':
                return sdk.CANLinkConfig.CANInterface.SocketCAN
            if api_val_lower == 'vector':
                return sdk.CANLinkConfig.CANInterface.Vector
            if api_val_lower == 'kvaser':
                return sdk.CANLinkConfig.CANInterface.KVaser
            if api_val_lower == 'pcan':
                return sdk.CANLinkConfig.CANInterface.PCAN
            if api_val_lower == 'etas':
                return sdk.CANLinkConfig.CANInterface.ETAS

            raise sdk.exceptions.BadResponseError(f'Unsupported CAN interface type "{api_val}"')

        interface = _can_interface_type(cast(api_typing.CANInterfaceType, canbus_config['interface']))

        subconfig: api_typing.CANBUS_ANY_SUBCONFIG_DICT
        interface_config: Union[
            sdk.CANLinkConfig.SocketCANConfig,
            sdk.CANLinkConfig.VectorConfig,
            sdk.CANLinkConfig.KVaserConfig,
            sdk.CANLinkConfig.PCANConfig,
            sdk.CANLinkConfig.ETASConfig,
        ]
        if interface == sdk.CANLinkConfig.CANInterface.SocketCAN:
            subconfig = cast(api_typing.CanBusSocketCanSubconfig, canbus_config['subconfig'])
            _check_response_dict(cmd, subconfig, 'channel', str)
            interface_config = sdk.CANLinkConfig.SocketCANConfig(
                channel=subconfig['channel']
            )
        elif interface == sdk.CANLinkConfig.CANInterface.Vector:
            subconfig = cast(api_typing.CanBusVectorSubconfig, canbus_config['subconfig'])
            _check_response_dict(cmd, subconfig, 'channel', (str, int))
            _check_response_dict(cmd, subconfig, 'bitrate', int)
            _check_response_dict(cmd, subconfig, 'data_bitrate', int)
            interface_config = sdk.CANLinkConfig.VectorConfig(
                channel=subconfig['channel'],
                bitrate=subconfig['bitrate'],
                data_bitrate=subconfig['data_bitrate']
            )
        elif interface == sdk.CANLinkConfig.CANInterface.KVaser:
            subconfig = cast(api_typing.CanBusKVaserSubconfig, canbus_config['subconfig'])
            _check_response_dict(cmd, subconfig, 'channel', int)
            _check_response_dict(cmd, subconfig, 'bitrate', int)
            _check_response_dict(cmd, subconfig, 'data_bitrate', int)
            _check_response_dict(cmd, subconfig, 'fd_non_iso', bool)
            interface_config = sdk.CANLinkConfig.KVaserConfig(
                channel=subconfig['channel'],
                bitrate=subconfig['bitrate'],
                data_bitrate=subconfig['data_bitrate'],
                fd_non_iso=subconfig['fd_non_iso']
            )
        elif interface == sdk.CANLinkConfig.CANInterface.PCAN:
            subconfig = cast(api_typing.CanBusPCANSubconfig, canbus_config['subconfig'])
            _check_response_dict(cmd, subconfig, 'channel', str)
            _check_response_dict(cmd, subconfig, 'bitrate', int)
            interface_config = sdk.CANLinkConfig.PCANConfig(
                channel=subconfig['channel'],
                bitrate=subconfig['bitrate']
            )
        elif interface == sdk.CANLinkConfig.CANInterface.ETAS:
            subconfig = cast(api_typing.CanBusETASSubconfig, canbus_config['subconfig'])
            _check_response_dict(cmd, subconfig, 'channel', str)
            _check_response_dict(cmd, subconfig, 'bitrate', int)
            _check_response_dict(cmd, subconfig, 'data_bitrate', int)
            interface_config = sdk.CANLinkConfig.ETASConfig(
                channel=subconfig['channel'],
                bitrate=subconfig['bitrate'],
                data_bitrate=subconfig['data_bitrate']
            )
        else:
            raise NotImplementedError(f"Unsupported interface type: {interface}")  # should not happen. Validated above

        link_config = sdk.CANLinkConfig(
            interface=interface,
            txid=canbus_config['txid'],
            rxid=canbus_config['rxid'],
            extended_id=canbus_config['extended_id'],
            fd=canbus_config['fd'],
            bitrate_switch=canbus_config['bitrate_switch'],
            interface_config=interface_config
        )
    elif link_type == sdk.DeviceLinkType._Dummy:
        link_config = None
    else:
        raise RuntimeError(f'Unsupported device link type "{link_type}"')

    device_link = sdk.DeviceLinkInfo(
        type=link_type,
        config=link_config,
        operational=link_operational,
        demo_mode=response['device_comm_link']['demo_mode']
    )

    return sdk.ServerInfo(
        device_comm_state=_device_status_from_api(response['device_status']),
        device_session_id=response['device_session_id'],
        datalogging=datalogging,
        sfd_firmware_id=response['loaded_sfd_firmware_id'],
        device_link=device_link
    )


def parse_watchable_update(response: api_typing.S2C.WatchableUpdate) -> List[WatchableUpdate]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.WATCHABLE_UPDATE

    outlist: List[WatchableUpdate] = []

    _check_response_dict(cmd, response, 'updates', list)

    for element in response['updates']:
        _check_response_dict(cmd, element, 'id', str)
        _check_response_dict(cmd, element, 'v', (float, int, bool))
        _check_response_dict(cmd, element, 't', (float, int))
        outlist.append(WatchableUpdate(
            server_id=element['id'],
            value=element['v'],
            server_time_us=float(element['t'])
        ))

    return outlist


def parse_write_value_response(response: api_typing.S2C.WriteValue) -> WriteConfirmation:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.WRITE_WATCHABLE_RESPONSE

    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'count', int)

    if response['count'] < 0:
        raise sdk.exceptions.BadResponseError("Got a negative count")

    if len(response['request_token']) == 0:
        raise sdk.exceptions.BadResponseError("Empty request_token")

    return WriteConfirmation(
        request_token=response['request_token'],
        count=response['count']
    )


def parse_write_completion(response: api_typing.S2C.WriteCompletion) -> WriteCompletion:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_WRITE_COMPLETION

    _check_response_dict(cmd, response, 'watchable', str)
    _check_response_dict(cmd, response, 'success', bool)
    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'completion_server_time_us', (float, int))
    _check_response_dict(cmd, response, 'batch_index', int)

    if len(response['watchable']) == 0:
        raise sdk.exceptions.BadResponseError('Empty watchable')

    if len(response['request_token']) == 0:
        raise sdk.exceptions.BadResponseError('Empty request_token')

    return WriteCompletion(
        request_token=response['request_token'],
        watchable=response['watchable'],
        success=response['success'],
        server_time_us=float(response['completion_server_time_us']),
        batch_index=response['batch_index']
    )


def parse_get_installed_sfds_response(response: api_typing.S2C.GetInstalledSFD) -> Dict[str, sdk.SFDInfo]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_INSTALLED_SFD_RESPONSE

    output: Dict[str, sdk.SFDInfo] = {}
    _check_response_dict(cmd, response, 'sfd_list', list)

    for info_dict in response['sfd_list']:
        info = _read_sfd_info(cmd, info_dict)
        output[info.firmware_id] = info

    return output


def parse_memory_read_completion(response: api_typing.S2C.ReadMemoryComplete) -> MemoryReadCompletion:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_MEMORY_READ_COMPLETE

    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'success', bool)
    _check_response_dict(cmd, response, 'completion_server_time_us', (float, int))
    success = _fetch_dict_val_of_type_no_none(response, 'success', bool, False)
    data_bin: Optional[bytes] = None
    if success:
        _check_response_dict(cmd, response, 'data', str)
        data = _fetch_dict_val_of_type_no_none(response, 'data', str, "")
        try:
            data_bin = b64decode(data, validate=True)
        except binascii.Error as e:
            raise sdk.exceptions.BadResponseError(f"Server returned a invalid base64 data block. {e}")

    _check_response_dict(cmd, response, 'detail_msg', (str, type(None)))
    detail_msg = _fetch_dict_val_of_type(response, 'detail_msg', str, "")

    return MemoryReadCompletion(
        request_token=_fetch_dict_val_of_type_no_none(response, 'request_token', str, ""),
        success=success,
        data=data_bin,
        error=detail_msg if detail_msg is not None else "",
        server_time_us=float(response['completion_server_time_us']),
        local_monotonic_timestamp=time.monotonic()
    )


def parse_memory_write_completion(response: api_typing.S2C.WriteMemoryComplete) -> MemoryWriteCompletion:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_MEMORY_WRITE_COMPLETE

    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'success', bool)
    _check_response_dict(cmd, response, 'completion_server_time_us', (float, int))
    _check_response_dict(cmd, response, 'detail_msg', (str, type(None)))
    detail_msg = _fetch_dict_val_of_type(response, 'detail_msg', str, "")

    return MemoryWriteCompletion(
        request_token=_fetch_dict_val_of_type_no_none(response, 'request_token', str, ""),
        success=_fetch_dict_val_of_type_no_none(response, 'success', bool, False),
        error=detail_msg if detail_msg is not None else "",
        server_time_us=float(response['completion_server_time_us']),
        local_monotonic_timestamp=time.monotonic()
    )


def parse_read_datalogging_acquisition_content_response(response: api_typing.S2C.ReadDataloggingAcquisitionContent) -> sdk.datalogging.DataloggingAcquisition:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.READ_DATALOGGING_ACQUISITION_CONTENT_RESPONSE

    _check_response_dict(cmd, response, 'reference_id', str)
    _check_response_dict(cmd, response, 'firmware_id', str)
    _check_response_dict(cmd, response, 'firmware_name', (str, type(None)))
    _check_response_dict(cmd, response, 'timestamp', float)
    _check_response_dict(cmd, response, 'name', str)
    _check_response_dict(cmd, response, 'trigger_index', (int, type(None)))
    _check_response_dict(cmd, response, 'yaxes', list)
    _check_response_dict(cmd, response, 'signals', list)
    _check_response_dict(cmd, response, 'xdata.name', str)
    _check_response_dict(cmd, response, 'xdata.data', list)
    _check_response_dict(cmd, response, 'xdata.watchable', (dict, type(None)))

    acquisition = sdk.datalogging.DataloggingAcquisition(
        firmware_id=response['firmware_id'],
        reference_id=response['reference_id'],
        acq_time=datetime.fromtimestamp(response['timestamp']),
        name=response['name'],
        firmware_name=response['firmware_name']
    )

    axis_map: Dict[int, sdk.datalogging.AxisDefinition] = {}
    for yaxis in response['yaxes']:
        _check_response_dict(cmd, yaxis, 'id', int)
        _check_response_dict(cmd, yaxis, 'name', str)
        axis_map[yaxis['id']] = sdk.datalogging.AxisDefinition(axis_id=yaxis['id'], name=yaxis['name'])

    xaxis_data: Optional[List[float]] = None
    try:
        xaxis_data = [float(x) for x in response['xdata']['data']]
    except Exception:
        raise sdk.exceptions.BadResponseError('X-Axis data is not all numerical')

    assert xaxis_data is not None

    def response2watchable_desc(d: Optional[api_typing.LoggedWatchable]) -> Optional[sdk.datalogging.LoggedWatchable]:
        if d is None:
            return None

        _check_response_dict(cmd, d, 'path', str)
        _check_response_dict(cmd, d, 'type', str)

        if d['type'] not in WatchableType.all():
            raise sdk.exceptions.BadResponseError(f"Invalid watchable type {d['type']}")
        return scrutiny.sdk.datalogging.LoggedWatchable(
            path=d['path'],
            type=WatchableType(d['type'])
        )

    for sig in response['signals']:
        _check_response_dict(cmd, sig, 'axis_id', int)
        _check_response_dict(cmd, sig, 'watchable', dict)   # None is not allowed for Y-Data
        _check_response_dict(cmd, sig, 'name', str)
        _check_response_dict(cmd, sig, 'data', list)

        yaxis_data: Optional[List[float]] = None
        try:
            yaxis_data = [float(x) for x in sig['data']]    # Convert to float for inf or nan
        except Exception:
            raise sdk.exceptions.BadResponseError(f'Dataseries {sig["name"]} data is not all numerical')
        assert yaxis_data is not None

        if sig['axis_id'] not in axis_map:
            raise sdk.exceptions.BadResponseError(f'Dataseries {sig["name"]} refer to a non-existent Y-Axis')
        ds = sdk.datalogging.DataSeries(
            data=yaxis_data,
            name=sig['name'],
            logged_watchable=response2watchable_desc(sig['watchable'])
        )
        acquisition.add_data(ds, axis=axis_map[sig['axis_id']])

    try:
        xaxis_data = [float(f) for f in response['xdata']['data']]    # Convert to float for inf or nan
    except Exception:
        raise sdk.exceptions.BadResponseError(f'X-Axis Dataseries data is not all numerical')

    xdata = sdk.datalogging.DataSeries(
        data=xaxis_data,
        name=response['xdata']['name'],
        logged_watchable=response2watchable_desc(response['xdata']['watchable'])
    )

    acquisition.set_xdata(xdata)
    try:
        acquisition.set_trigger_index(response['trigger_index'])
    except Exception:
        raise sdk.exceptions.BadResponseError(f'Given Trigger index is not valid. {response["trigger_index"]}')

    return acquisition


def parse_request_datalogging_acquisition_response(response: api_typing.S2C.RequestDataloggingAcquisition) -> str:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE

    _check_response_dict(cmd, response, 'request_token', str)

    return response['request_token']


def parse_datalogging_acquisition_complete(response: api_typing.S2C.InformDataloggingAcquisitionComplete) -> DataloggingCompletion:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_DATALOGGING_ACQUISITION_COMPLETE

    _check_response_dict(cmd, response, 'request_token', str)
    _check_response_dict(cmd, response, 'reference_id', (str, type(None)))
    _check_response_dict(cmd, response, 'success', bool)
    _check_response_dict(cmd, response, 'detail_msg', str)

    if response['success']:
        if response['reference_id'] is None or response['reference_id'] == "":
            raise sdk.exceptions.BadResponseError("Missing reference ID for a successful acquisition")

    if response['request_token'] == "":
        raise sdk.exceptions.BadResponseError("Empty request token in response")

    return DataloggingCompletion(
        request_token=response['request_token'],
        reference_id=response['reference_id'],
        detail_msg=response['detail_msg'],
        success=response['success'],
    )


def parse_datalogging_list_changed(response: api_typing.S2C.InformDataloggingListChanged) -> DataloggingListChangeResponse:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED

    _check_response_dict(cmd, response, 'action', str)
    _check_response_dict(cmd, response, 'reference_id', (str, type(None)))

    server_action = response['action']
    if server_action == 'new':
        change_type = sdk.DataloggingListChangeType.NEW
    elif server_action == 'delete':
        change_type = sdk.DataloggingListChangeType.DELETE
    elif server_action == 'update':
        change_type = sdk.DataloggingListChangeType.UPDATE
    elif server_action == 'delete_all':
        change_type = sdk.DataloggingListChangeType.DELETE_ALL
    else:
        raise sdk.exceptions.BadResponseError("Unknown change type")

    if change_type != sdk.DataloggingListChangeType.DELETE_ALL and response['reference_id'] is None:
        raise sdk.exceptions.BadResponseError(f"Missing reference_id for action : {server_action}")

    if change_type == sdk.DataloggingListChangeType.DELETE_ALL and response['reference_id'] is not None:
        raise sdk.exceptions.BadResponseError(f"Received a reference_id for action : {server_action}")

    return DataloggingListChangeResponse(
        action=change_type,
        reference_id=response['reference_id']
    )


def parse_list_datalogging_acquisitions_response(response: api_typing.S2C.ListDataloggingAcquisition) -> List[sdk.datalogging.DataloggingStorageEntry]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.LIST_DATALOGGING_ACQUISITION_RESPONSE

    _check_response_dict(cmd, response, 'acquisitions', list)
    dataout: List[sdk.datalogging.DataloggingStorageEntry] = []

    for acq in response['acquisitions']:
        _check_response_dict(cmd, acq, 'firmware_id', str)
        _check_response_dict(cmd, acq, 'name', str)
        _check_response_dict(cmd, acq, 'timestamp', float)
        _check_response_dict(cmd, acq, 'reference_id', str)
        _check_response_dict(cmd, acq, 'firmware_metadata', (dict, type(None)))

        entry = sdk.datalogging.DataloggingStorageEntry(
            firmware_id=acq['firmware_id'],
            name=acq['name'] if acq['name'] is not None else '',
            timestamp=datetime.fromtimestamp(acq['timestamp']),
            reference_id=acq['reference_id'],
            firmware_metadata=_read_sfd_metadata_from_incomplete_dict(acq['firmware_metadata'])
        )
        dataout.append(entry)

    return dataout


def parse_user_command_response(response: api_typing.S2C.UserCommand) -> sdk.UserCommandResponse:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.USER_COMMAND_RESPONSE

    _check_response_dict(cmd, response, 'subfunction', int)
    _check_response_dict(cmd, response, 'data', str)

    if response['subfunction'] < 0 or response['subfunction'] > 0xFF:
        raise sdk.exceptions.BadResponseError(f'Invalid subfunction {response["subfunction"]}')

    try:
        data = b64decode(response['data'], validate=True)
    except binascii.Error as e:
        raise sdk.exceptions.BadResponseError(f"Server returned a invalid base64 data block. {e}")

    return sdk.UserCommandResponse(
        subfunction=response['subfunction'],
        data=data
    )


def parse_get_watchable_count(response: api_typing.S2C.GetWatchableCount) -> Dict[sdk.ServerDatastoreContentType, int]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_WATCHABLE_COUNT_RESPONSE

    _check_response_dict(cmd, response, 'qty.var', int)
    _check_response_dict(cmd, response, 'qty.alias', int)
    _check_response_dict(cmd, response, 'qty.rpv', int)
    _check_response_dict(cmd, response, 'qty.var_factory', int)

    ContentTypeKey = Literal['rpv', 'alias', 'var', 'var_factory']
    key: ContentTypeKey
    for key in typing.get_args(ContentTypeKey):
        if response['qty'][key] < 0:
            raise sdk.exceptions.BadResponseError("Received a negative number of watchable")

    return {
        sdk.ServerDatastoreContentType.Variable: response['qty']['var'],
        sdk.ServerDatastoreContentType.Alias: response['qty']['alias'],
        sdk.ServerDatastoreContentType.RuntimePublishedValue: response['qty']['rpv'],
        sdk.ServerDatastoreContentType.VariableFactory: response['qty']['var_factory']
    }


def parse_get_loaded_sfd(response: api_typing.S2C.GetLoadedSFD) -> Optional[sdk.SFDInfo]:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_LOADED_SFD_RESPONSE

    _check_response_dict(cmd, response, 'sfd', (dict, type(None)))

    if response['sfd'] is None:
        return None

    return _read_sfd_info(cmd, response['sfd'])


def parser_server_stats(response: api_typing.S2C.GetServerStats) -> sdk.ServerStatistics:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.GET_SERVER_STATS

    _check_response_dict(cmd, response, 'uptime', (float, int))
    _check_response_dict(cmd, response, 'invalid_request_count', int)
    _check_response_dict(cmd, response, 'unexpected_error_count', int)
    _check_response_dict(cmd, response, 'client_count', int)
    _check_response_dict(cmd, response, 'to_all_clients_datarate_byte_per_sec', (float, int))
    _check_response_dict(cmd, response, 'from_any_client_datarate_byte_per_sec', (float, int))
    _check_response_dict(cmd, response, 'msg_received', int)
    _check_response_dict(cmd, response, 'msg_sent', int)
    _check_response_dict(cmd, response, 'device_session_count', int)
    _check_response_dict(cmd, response, 'to_device_datarate_byte_per_sec', (float, int))
    _check_response_dict(cmd, response, 'from_device_datarate_byte_per_sec', (float, int))
    _check_response_dict(cmd, response, 'device_request_per_sec', (float, int))

    return sdk.ServerStatistics(
        uptime=float(response['uptime']),
        invalid_request_count=response['invalid_request_count'],
        unexpected_error_count=response['unexpected_error_count'],
        client_count=response['client_count'],
        to_all_clients_datarate_byte_per_sec=float(response['to_all_clients_datarate_byte_per_sec']),
        from_any_client_datarate_byte_per_sec=float(response['from_any_client_datarate_byte_per_sec']),
        msg_received=response['msg_received'],
        msg_sent=response['msg_sent'],
        device_session_count=response['device_session_count'],
        to_device_datarate_byte_per_sec=float(response['to_device_datarate_byte_per_sec']),
        from_device_datarate_byte_per_sec=float(response['from_device_datarate_byte_per_sec']),
        device_request_per_sec=float(response['device_request_per_sec'])
    )


def parse_welcome(msg: api_typing.S2C.Welcome) -> WelcomeData:
    assert isinstance(msg, dict)
    assert 'cmd' in msg
    cmd = msg['cmd']
    assert cmd == API.Command.Api2Client.WELCOME

    _check_response_dict(cmd, msg, 'server_time_zero_timestamp', (float, int))

    return WelcomeData(
        server_time_zero_timestamp=float(msg['server_time_zero_timestamp'])
    )


def parse_download_sfd_response(response: api_typing.S2C.DownloadSFD) -> SFDDownloadChunk:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.DOWNLOAD_SFD_RESPONSE

    _check_response_dict(cmd, response, 'firmware_id', str)
    _check_response_dict(cmd, response, 'total_size', int)
    _check_response_dict(cmd, response, 'file_chunk.data', str)
    _check_response_dict(cmd, response, 'file_chunk.chunk_index', int)

    if len(response['firmware_id']) == 0:
        raise sdk.exceptions.BadResponseError("Empty firmware ID")

    if response['total_size'] <= 0:
        raise sdk.exceptions.BadResponseError("SFD Size is not valid")

    if response['file_chunk']['chunk_index'] < 0:
        raise sdk.exceptions.BadResponseError("Chunk index is not valid")

    try:
        data = b64decode(response['file_chunk']['data'], validate=True)
    except binascii.Error as e:
        raise sdk.exceptions.BadResponseError(f"Server returned a invalid base64 data block. {e}")

    return SFDDownloadChunk(
        firmware_id=response['firmware_id'],
        total_size=response['total_size'],
        chunk_index=response['file_chunk']['chunk_index'],
        data=data
    )


def parse_upload_sfd_init_response(response: api_typing.S2C.UploadSFDInit) -> UploadSFDInitResponse:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.UPLOAD_SFD_INIT_RESPONSE

    _check_response_dict(cmd, response, 'token', str)
    _check_response_dict(cmd, response, 'will_overwrite', bool)

    if len(response['token']) == 0:
        raise sdk.exceptions.BadResponseError("Empty token")

    return UploadSFDInitResponse(
        token=response['token'],
        will_overwrite=response['will_overwrite']
    )


def parse_upload_sfd_data_response(response: api_typing.S2C.UploadSFDData) -> UploadSFDDataResponse:
    assert isinstance(response, dict)
    assert 'cmd' in response
    cmd = response['cmd']
    assert cmd == API.Command.Api2Client.UPLOAD_SFD_DATA_RESPONSE

    _check_response_dict(cmd, response, 'completed', bool)
    _check_response_dict(cmd, response, 'actual_size', int)

    if response['actual_size'] < 0:
        raise sdk.exceptions.BadResponseError("Invalid size")

    sfd_info: Optional[sdk.SFDInfo] = None
    if response['completed']:
        _check_response_dict(cmd, response, 'sfd_info', dict)
        assert response['sfd_info'] is not None
        sfd_info = _read_sfd_info(cmd, response['sfd_info'])
    else:
        _check_response_dict(cmd, response, 'sfd_info', type(None))

    return UploadSFDDataResponse(
        completed=response['completed'],
        actual_size=response['actual_size'],
        sfd_info=sfd_info
    )
