#    common.py
#        Common definitions related to the WatchableRegistry that have no dependencies
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = [
    'WatcherIdType',
    'RegistryValueUpdate',
    'RegistryNodeConfiguration',
    'GlobalWatchCallbackData',
    'WatcherValueUpdateCallback',
    'UnwatchCallback',
    'GlobalWatchCallback',
    'GlobalUnwatchCallback',
    'BaseUpdate',
    'MathUpdate',
    'RegistryNodeType'
]


import enum
from dataclasses import dataclass
from scrutiny import sdk
from scrutiny.tools.typing import *
from scrutiny.sdk.listeners import BaseUpdate
from datetime import datetime

WatcherIdType = Union[str, int]


class RegistryNodeType(str, enum.Enum):
    Variable = sdk.WatchableType.Variable
    RuntimePublishedValue = sdk.WatchableType.RuntimePublishedValue
    Alias = sdk.WatchableType.Alias
    Math = 'math'

    @classmethod
    def from_sdk(cls, watchable_type: sdk.WatchableType) -> Self:
        return cls(watchable_type.value)

    def to_sdk(self) -> sdk.WatchableType:
        return sdk.WatchableType(self.value)

    def is_server_node(self) -> bool:
        try:
            self.to_sdk()
            return True
        except Exception:
            return False


class MathUpdate(BaseUpdate):
    _math_watchable_signature: str

    def __init__(self, value: Optional[Union[int, float, bool]], math_watchable_signature: str, update_timestamp: datetime) -> None:
        super().__init__(value, data=None, status=sdk.ValueStatus.Valid, update_timestamp=update_timestamp)
        self._math_watchable_signature = math_watchable_signature

    def get_datatype(self) -> sdk.EmbeddedDataType:
        return sdk.EmbeddedDataType.float64

    def get_id(self) -> str:
        return self._math_watchable_signature

    def get_user_unique_name(self) -> str:
        return self._math_watchable_signature


@dataclass(slots=True)
class RegistryValueUpdate:
    sdk_update: BaseUpdate
    registry_id: int
    node_type: RegistryNodeType


@dataclass(slots=True)
class RegistryNodeConfiguration:
    node_type: RegistryNodeType
    datatype: sdk.EmbeddedDataType
    enum: Optional[sdk.EmbeddedEnum]

    @classmethod
    def from_sdk(cls, config: sdk.BriefWatchableConfiguration) -> Self:
        return cls(
            node_type=RegistryNodeType(config.watchable_type.value),
            datatype=config.datatype,
            enum=config.enum
        )


@dataclass(slots=True)
class GlobalWatchCallbackData:
    watcher_id: WatcherIdType
    server_path: str
    node_config: RegistryNodeConfiguration
    registry_id: int
    watcher_count: int
    highest_update_rate: Optional[float]


WatcherValueUpdateCallback = Callable[[WatcherIdType, List[RegistryValueUpdate]], None]
UnwatchCallback = Callable[[WatcherIdType, str, int], None]
GlobalWatchCallback = Callable[[GlobalWatchCallbackData], None]
GlobalUnwatchCallback = Callable[[GlobalWatchCallbackData], None]
