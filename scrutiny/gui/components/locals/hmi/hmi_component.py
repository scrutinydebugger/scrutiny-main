#    hmi_component.py
#        Human Machine Interface component. Lets the user build a visual dashboard with graphical
#        elements tied to a watchable.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['HMIComponent']

import enum
import functools

from scrutiny.gui.components.locals.hmi.hmi_library import HMILibrary

from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtWidgets import (QVBoxLayout, QGraphicsScene,
                               QGraphicsSceneMouseEvent, QMenu, QSplitter)
from PySide6.QtGui import QIcon, QKeyEvent, QMouseEvent

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent

from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.text_label_hmi_widget import TextLabelHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.gauge_hmi_widget import GaugeHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_graphic_view import HMIGraphicView

from scrutiny.tools.typing import *


class HMIInteractionMode(enum.Enum):
    Display = enum.auto()
    Edit = enum.auto()


class HMIComponent(ScrutinyGUIBaseLocalComponent):
    instance_name: str

    _NAME = "Human Machine Interface"
    _TYPE_ID = "hmi"

    _mode: HMIInteractionMode
    _scene: QGraphicsScene
    _view: HMIGraphicView
    _splitter: QSplitter
    _library: HMILibrary

    _selected_widgets: List[BaseHMIWidget]

# region inherited methods
    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.TestSquare)

    def setup(self) -> None:
        self._mode = HMIInteractionMode.Display
        self._scene = QGraphicsScene()
        self._view = HMIGraphicView(self._scene)
        self._library = HMILibrary()

        self._splitter = QSplitter()
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0, 0, 0, 0)
        self._splitter.setHandleWidth(5)
        self._splitter.addWidget(self._view)
        self._splitter.addWidget(self._library)
        self._splitter.setCollapsible(0, False)  # Cannot collapse the graph
        self._splitter.setCollapsible(1, True)  # Can collapse the right menu

        self.test_widget = GaugeHMIWidget(self)
        self._selected_widgets = []

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.test_widget._make_slot_config_widget())
        layout.addWidget(self._splitter, 1)  # Stretch
        self._view.signals.right_click.connect(self._view_right_click_slot)
        self._view.signals.left_click.connect(self._view_left_click_slot)
        self._view.signals.drop_widget_class.connect(self._view_drop_widget_class_slot)
        self._view.signals.rubber_band_select_widgets.connect(self._view_rubberband_select_widgets_slot)
        self.add(self.test_widget)

        self.set_mode(HMIInteractionMode.Edit)

    def ready(self) -> None:
        pass

    def teardown(self) -> None:
        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget):
                item.destroy()

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def add(self, widget: BaseHMIWidget, scene_pos: Optional[QPoint] = None) -> None:
        self._scene.addItem(widget)
        if scene_pos is not None:
            widget.setPos(scene_pos)

        self.update_hmi_widget_state(widget)

    def select_widgets(self, widgets: List[BaseHMIWidget]) -> None:
        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget) and item not in widgets:
                item.set_selected(False)

        self._selected_widgets.clear()
        self._selected_widgets.extend(widgets)

        for widget in self._selected_widgets:
            widget.set_selected(True)

    def toggle_select_widget(self, widget: BaseHMIWidget) -> None:
        if widget in self._selected_widgets:
            self.deselect_all_widgets()
        else:
            self.select_widgets([widget])

    def deselect_all_widgets(self) -> None:
        for widget in self._selected_widgets:
            widget.set_selected(False)
        self._selected_widgets.clear()

    def is_edit_mode(self) -> bool:
        return self._mode == HMIInteractionMode.Edit

    def update_hmi_widget_state(self, widget: BaseHMIWidget) -> None:
        widget.show_resize_handles(self.is_edit_mode())
        widget.update()

    def set_mode(self, mode: HMIInteractionMode) -> None:
        self._mode = mode

        if self._mode == HMIInteractionMode.Edit:
            self._splitter.handle(1).setEnabled(True)
            self._splitter.setHandleWidth(5)
            self._splitter.setSizes([400, 400])
            self._view.show_grid(True)
            self._view.setAcceptDrops(True)
            self._view.set_allow_edit_widgets(True)
        elif self._mode == HMIInteractionMode.Display:
            self._splitter.handle(1).setEnabled(False)
            self._splitter.setHandleWidth(0)
            self._splitter.setSizes([1, 0])
            self._view.show_grid(False)
            self._view.setAcceptDrops(False)
            self._view.set_allow_edit_widgets(False)

        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget):
                self.update_hmi_widget_state(item)

    def _view_drop_widget_class_slot(self, widget_class: Type[BaseHMIWidget], scene_pos: QPoint) -> None:
        instance = widget_class(self)
        self.add(instance, scene_pos)

    def _view_rubberband_select_widgets_slot(self, widgets: List[BaseHMIWidget]) -> None:
        self.select_widgets(widgets)

    def _view_right_click_slot(self, widget: Optional[BaseHMIWidget], event: QMouseEvent) -> None:
        if self._mode != HMIInteractionMode.Edit:
            return

        if widget is not None:
            self.select_widgets([widget])
            menu = QMenu()
            remove_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")
            edit_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Edit")

            remove_action.triggered.connect(functools.partial(self._delete_widget, widget))

            menu.exec(self._view.mapToGlobal(event.pos()))

    def _view_left_click_slot(self, widget: Optional[BaseHMIWidget]) -> None:
        if widget is None:
            self.deselect_all_widgets()
        else:
            self.select_widgets([widget])

    def _delete_widget(self, widget: BaseHMIWidget) -> None:
        if widget in self._selected_widgets:
            self._selected_widgets.remove(widget)

        widget.destroy()
        self._scene.removeItem(widget)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            for widget in self._selected_widgets:
                self._delete_widget(widget)

        return super().keyPressEvent(event)

# endregion
