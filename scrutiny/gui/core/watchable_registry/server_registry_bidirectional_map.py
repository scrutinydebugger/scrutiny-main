__all__ = ['ServerRegistryBidirectionalMap']

from scrutiny import tools
from scrutiny.tools.typing import *


class ServerRegistryBidirectionalMap:
    __slots__ = ('r2s', 's2r')

    r2s: Dict[int, str]
    s2r: Dict[str, int]

    def __init__(self) -> None:
        self.r2s = {}
        self.s2r = {}

    def get_server_id(self, registry_id: int) -> str:
        return self.r2s[registry_id]

    def get_registry_id(self, server_id: str) -> int:
        return self.s2r[server_id]

    def get_server_id_or_none(self, registry_id: int) -> Optional[str]:
        if registry_id in self.r2s:
            return self.r2s[registry_id]
        return None

    def get_registry_id_or_none(self, server_id: str) -> Optional[int]:
        if server_id in self.s2r:
            return self.s2r[server_id]
        return None

    def map(self, registry_id: int, server_id: str) -> None:
        self.r2s[registry_id] = server_id
        self.s2r[server_id] = registry_id

    def unmap_by_registry_id(self, registry_id: int) -> None:
        with tools.SuppressException(KeyError):
            server_id = self.r2s[registry_id]
            with tools.SuppressException(KeyError):
                del self.s2r[server_id]
            del self.r2s[registry_id]

    def unmap_by_server_id(self, server_id: str) -> None:
        with tools.SuppressException(KeyError):
            registry_id = self.s2r[server_id]
            with tools.SuppressException(KeyError):
                del self.r2s[registry_id]
            del self.s2r[server_id]

    def clear(self) -> None:
        self.s2r.clear()
        self.r2s.clear()

    def __len__(self) -> int:
        return len(self.s2r)
