__all__ = [
    'WatcherIdType',
    'RegistryValueUpdate',
    'GlobalWatchCallbackData',
    'WatcherValueUpdateCallback',
    'UnwatchCallback',
    'GlobalWatchCallback',
    'GlobalUnwatchCallback',
]


import enum
from dataclasses import dataclass
from scrutiny import sdk
from scrutiny.tools.typing import *
from scrutiny.sdk.listeners import ValueUpdate

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


@dataclass(slots=True)
class RegistryValueUpdate:
    sdk_update: ValueUpdate
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
UnwatchCallback = Callable[[WatcherIdType, str, RegistryNodeConfiguration, int], None]
GlobalWatchCallback = Callable[[GlobalWatchCallbackData], None]
GlobalUnwatchCallback = Callable[[GlobalWatchCallbackData], None]
