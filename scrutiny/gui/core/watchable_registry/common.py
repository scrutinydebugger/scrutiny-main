__all__ = [
    'WatcherIdType',
    'RegistryValueUpdate',
    'GlobalWatchCallbackData',
    'WatcherValueUpdateCallback',
    'UnwatchCallback',
    'GlobalWatchCallback',
    'GlobalUnwatchCallback',
]


from scrutiny import sdk
from dataclasses import dataclass
from scrutiny.tools.typing import *
from scrutiny.sdk.listeners import ValueUpdate

WatcherIdType = Union[str, int]


@dataclass(frozen=True, slots=True)
class RegistryValueUpdate:
    sdk_update: ValueUpdate
    registry_id: int


@dataclass(slots=True)
class GlobalWatchCallbackData:
    watcher_id: WatcherIdType
    server_path: str
    watchable_config: sdk.BriefWatchableConfiguration
    registry_id: int
    watcher_count: int
    highest_update_rate: Optional[float]


WatcherValueUpdateCallback = Callable[[WatcherIdType, List[RegistryValueUpdate]], None]
UnwatchCallback = Callable[[WatcherIdType, str, sdk.BriefWatchableConfiguration, int], None]
GlobalWatchCallback = Callable[[GlobalWatchCallbackData], None]
GlobalUnwatchCallback = Callable[[GlobalWatchCallbackData], None]
