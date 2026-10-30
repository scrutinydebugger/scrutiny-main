__all__ = ['DEFAULT_SERVER_PORT']
from PySide6.QtCore import qVersion

DEFAULT_SERVER_PORT = 8765
QT_VERSION = tuple(int(x) for x in qVersion().split('.')[:2])
