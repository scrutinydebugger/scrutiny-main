
__all__ = ['WatcherData', 'Watcher']

from scrutiny.tools.typing import *
from scrutiny.gui.core.watchable_registry.common import WatcherIdType, WatcherValueUpdateCallback, UnwatchCallback
from dataclasses import dataclass


@dataclass(slots=True)
class WatcherData:
    update_rate: Optional[float]


@dataclass(init=False, slots=True)
class Watcher:
    watcher_id: WatcherIdType
    value_update_callback: WatcherValueUpdateCallback
    unwatch_callback: UnwatchCallback

    subscribed_registry_id: Set[int]

    def __init__(self,
                 watcher_id: WatcherIdType,
                 value_update_callback: WatcherValueUpdateCallback,
                 unwatch_callback: UnwatchCallback
                 ) -> None:
        if not isinstance(watcher_id, (str, int)):
            raise ValueError("watcher_id is not a string or an int")
        if not callable(value_update_callback):
            raise ValueError("value_update_callback is not a function")
        if not callable(unwatch_callback):
            raise ValueError("unwatch_callback is not a function")

        self.watcher_id = watcher_id
        self.value_update_callback = value_update_callback
        self.unwatch_callback = unwatch_callback
        self.subscribed_registry_id = set()
