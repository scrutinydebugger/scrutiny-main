

__all__ = [
    'WatchableRegistryError',
    'WatchableRegistryNodeNotFoundError',
    'WatcherNotFoundError'
]


class WatchableRegistryError(Exception):
    pass


class WatchableRegistryNodeNotFoundError(WatchableRegistryError):
    pass


class WatcherNotFoundError(Exception):
    pass
