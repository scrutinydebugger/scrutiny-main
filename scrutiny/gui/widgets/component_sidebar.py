#    component_sidebar.py
#        The sidebar with the dashboard component that can be added
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-python)
#
#   Copyright (c) 2021 Scrutiny Debugger

__all__ = ['ComponentSidebar']


from PySide6.QtWidgets import QWidget,  QToolBar,  QToolButton, QSizePolicy
from PySide6.QtCore import Qt, QSize,  Signal
from PySide6.QtGui import QAction
from scrutiny.gui.components.dashboard.base_dashboard_component import ScrutinyGUIBaseDashboardComponent
import functools

from typing import List, Type, Dict

class ComponentSidebar(QToolBar):
    insert_component=Signal(type)

    def __init__(self, components:List[Type[ScrutinyGUIBaseDashboardComponent]]) -> None:
        super().__init__()

        self.setIconSize(QSize(32,24))       
        
        for component in components:
            btn = QToolButton(self)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed))
        
            btn_action = QAction(component.get_icon(), component.get_name().replace(' ', '\n'), self)
            btn_action.triggered.connect( functools.partial(self.trigger_signal, component))

            btn.addAction(btn_action)
            btn.setDefaultAction(btn_action)
            self.addWidget(btn)
    
    def trigger_signal(self, component:Type[ScrutinyGUIBaseDashboardComponent]) -> None:
        self.insert_component.emit(component)
