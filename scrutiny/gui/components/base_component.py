#    base_component.py
#        A base class for a component that can be added to the GUI (globally or on the dashboard)
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ScrutinyGUIBaseComponent']

from abc import abstractmethod

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QIcon
from typing import cast, TYPE_CHECKING

from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.core.watchable_registry import WatchableRegistry
import logging

if TYPE_CHECKING:   # Prevent circular dependency
    from scrutiny.gui.main_window import MainWindow

class ScrutinyGUIBaseComponent(QWidget):
    instance_name:str
    main_window:"MainWindow"
    server_manager:ServerManager
    watchable_registry:WatchableRegistry
    logger:logging.Logger

    def __init__(self, main_window:"MainWindow", 
                 instance_name:str,
                 watchable_registry:WatchableRegistry,
                 server_manager:ServerManager
                 ) -> None:
        self.instance_name = instance_name
        self.main_window = main_window
        self.server_manager = server_manager
        self.watchable_registry=watchable_registry
        self.logger = logging.getLogger(self.__class__.__name__)
        super().__init__()

    @classmethod
    def get_icon(cls) -> QIcon:
        if not hasattr(cls, '_ICON'):
            raise RuntimeError(f"Class {cls.__name__} require the _ICON to be set")
        return  QIcon(str(getattr(cls, '_ICON')))

    @classmethod
    def get_name(cls) -> str: 
        if not hasattr(cls, '_NAME'):
            raise RuntimeError(f"Class {cls.__name__} require the _NAME to be set")
        return cast(str, getattr(cls, '_NAME'))

    @abstractmethod
    def setup(self) -> None:
        pass

    def ready(self) -> None:
        pass

    @abstractmethod
    def teardown(self) -> None:
        pass
    
    def visibilityChanged(self, visible:bool) -> None:
        pass
