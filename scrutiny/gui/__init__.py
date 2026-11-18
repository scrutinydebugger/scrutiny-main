__all__ = ['DEFAULT_SERVER_PORT', 'get_qt_version']
from typing import Tuple

DEFAULT_SERVER_PORT = 8765


def get_qt_version() -> Tuple[int, ...]:
    from PySide6.QtCore import qVersion
    return tuple(int(x) for x in qVersion().split('.')[:2])
