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
import gc
import logging

from scrutiny.gui.components.locals.hmi.hmi_library import HMILibrary

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QVBoxLayout, QMenu, QSplitter, QTabWidget, QWidget, QStackedLayout
from PySide6.QtGui import QIcon, QKeyEvent, QMouseEvent

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent

from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.gauge_hmi_widget import GaugeHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_workzone import HMIWorkZone

from scrutiny.tools.typing import *


class HMIInteractionMode(enum.Enum):
    Display = enum.auto()
    Edit = enum.auto()


class HMIComponent(ScrutinyGUIBaseLocalComponent):
    instance_name: str

    SPLITTER_EDIT_MENU = 0
    SPLITTER_WORKZONE = 1

    _NAME = "Human Machine Interface"
    _TYPE_ID = "hmi"

    _mode: HMIInteractionMode
    _workzone: HMIWorkZone
    _splitter: QSplitter
    _config_widget_container: QWidget
    _edit_tab_widget: QTabWidget
    _library: HMILibrary
    _config_widgets: Dict[int, QWidget]
    _config_widget_container_layout: QStackedLayout

# region inherited methods
    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.GaugeLean)

    def setup(self) -> None:
        self._mode = HMIInteractionMode.Display
        self._workzone = HMIWorkZone()
        self._library = HMILibrary()
        self._config_widget_container = QWidget()
        self._config_widgets = {}

        self._edit_tab_widget = QTabWidget()
        self._edit_tab_widget.addTab(self._library, "Library")
        self._edit_tab_widget.addTab(self._config_widget_container, "Configure")

        self._config_widget_container_layout = QStackedLayout(self._config_widget_container)
        self._config_widget_container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._config_widget_container_layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._config_widget_container_layout.addWidget(QWidget())   # Empty widget at index 0

        self._splitter = QSplitter()
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0, 0, 0, 0)
        self._splitter.setHandleWidth(5)
        self._splitter.addWidget(self._edit_tab_widget)
        self._splitter.addWidget(self._workzone)
        self._splitter.setCollapsible(self.SPLITTER_EDIT_MENU, True)
        self._splitter.setCollapsible(self.SPLITTER_WORKZONE, False)

        self.test_widget = GaugeHMIWidget(self)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._splitter, 1)  # 1=Stretch
        self._workzone.signals.right_click.connect(self._workzone_right_click_slot)
        self._workzone.signals.left_click.connect(self._workzone_left_click_slot)
        self._workzone.signals.drop_widget_class.connect(self._workzone_drop_widget_class_slot)
        self._show_edit_menu(False)  # Necessary to set the menu to a size of 0, used for state checking

        self._show_config_of(None)

        self.app.server_manager.signals.registry_changed.connect(self._registry_changed_slot)

    def ready(self) -> None:
        self.set_mode(HMIInteractionMode.Edit)

    def teardown(self) -> None:
        for hmi_widget in self._workzone.iterate_hmi_widgets():
            self._delete_widget(hmi_widget)

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def add(self, widget: BaseHMIWidget, scene_pos: Optional[QPoint] = None) -> None:
        existing_widgets = list(self._workzone.iterate_hmi_widgets())
        self._workzone.add_widget(widget, scene_pos)
        self._create_config_widget_of(widget)
        self._show_config_of(widget)    # Show the config just created

        self.update_hmi_widget_state(widget)

        if len(existing_widgets) > 0:
            widget.setZValue(existing_widgets[-1].zValue() + 1)

    def is_edit_mode(self) -> bool:
        return self._mode == HMIInteractionMode.Edit

    def update_hmi_widget_state(self, widget: BaseHMIWidget) -> None:
        widget.show_resize_handles(self.is_edit_mode())
        widget.update()

    def set_mode(self, mode: HMIInteractionMode) -> None:
        self._mode = mode
        self._workzone.deselect_all_widgets()

        if self._mode == HMIInteractionMode.Edit:
            self._show_edit_menu(True)
            self._workzone.show_grid(True)
            self._workzone.setAcceptDrops(True)
            self._workzone.set_allow_edit_widgets(True)
        elif self._mode == HMIInteractionMode.Display:
            self._show_edit_menu(False)
            self._workzone.show_grid(False)
            self._workzone.setAcceptDrops(False)
            self._workzone.set_allow_edit_widgets(False)

        for hmi_widget in self._workzone.iterate_hmi_widgets():
            self.update_hmi_widget_state(hmi_widget)

# region Private
    def _registry_changed_slot(self) -> None:
        self._resubscribe_all_hmi_widgets()

    def _resubscribe_all_hmi_widgets(self) -> None:
        for hmi_widget in self._workzone.iterate_hmi_widgets():
            hmi_widget.try_watch_all_vslots()

    def _show_edit_menu(self, val: bool) -> None:
        if val:
            self._splitter.handle(1).setEnabled(True)
            self._splitter.setHandleWidth(5)
            if self._splitter.sizes()[0] == 0:
                menu_width = self._edit_tab_widget.sizeHint().width()
                self._splitter.setSizes([menu_width, self.width() - menu_width])
        else:
            self._splitter.handle(1).setEnabled(False)
            self._splitter.setHandleWidth(0)
            self._splitter.setSizes([0, 1])

    def _create_config_widget_of(self, widget: BaseHMIWidget) -> None:
        """Create the widget shown in the "configure" tabs for the given HMI Widget"""
        config_container = QWidget()
        layout = QVBoxLayout(config_container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        vslot_config = widget.make_slot_config_widget()
        if vslot_config is not None:
            layout.addWidget(vslot_config)

        specific_config = widget.get_config_widget()
        if specific_config is not None:
            layout.addWidget(specific_config)

        self._config_widgets[id(widget)] = config_container
        self._config_widget_container_layout.addWidget(config_container)

    def _workzone_drop_widget_class_slot(self, widget_class: Type[BaseHMIWidget], scene_pos: QPoint) -> None:
        instance = widget_class(self)
        self.add(instance, scene_pos)

    def _workzone_right_click_slot(self, widget: Optional[BaseHMIWidget], event: QMouseEvent) -> None:
        if self._mode != HMIInteractionMode.Edit:
            return

        if widget is not None:
            self._workzone.select_widgets([widget])
            menu = QMenu()
            remove_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")
            edit_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Edit")
            move_to_action = menu.addAction("Move")

            move_to_menu = QMenu()
            move_to_back_action = move_to_menu.addAction("To Back")
            move_backward_action = move_to_menu.addAction("Backward")
            move_forward_action = move_to_menu.addAction("Forward")
            move_to_front_action = move_to_menu.addAction("To Front")
            move_to_action.setMenu(move_to_menu)

            def move_to_back_slot() -> None:
                all_z = [w.zValue() for w in self._workzone.iterate_hmi_widgets()]
                if len(all_z) > 0:
                    widget.setZValue(min(all_z) - 1)
                self._reassign_packed_zvalues()

            def move_to_front_slot() -> None:
                all_z = [w.zValue() for w in self._workzone.iterate_hmi_widgets()]
                if len(all_z) > 0:
                    widget.setZValue(max(all_z) + 1)
                self._reassign_packed_zvalues()

            def move_backward_slot() -> None:
                previous = sorted([w for w in self._workzone.iterate_hmi_widgets() if w.zValue() < widget.zValue()], key=lambda w: w.zValue())
                if len(previous) > 0:   # swap
                    temp = previous[-1].zValue()
                    previous[-1].setZValue(widget.zValue())
                    widget.setZValue(temp)

            def move_forward_slot() -> None:
                nexts = sorted([w for w in self._workzone.iterate_hmi_widgets() if w.zValue() > widget.zValue()], key=lambda w: w.zValue())
                if len(nexts) > 0:   # swap
                    temp = nexts[0].zValue()
                    nexts[0].setZValue(widget.zValue())
                    widget.setZValue(temp)

            move_to_back_action.triggered.connect(move_to_back_slot)
            move_backward_action.triggered.connect(move_backward_slot)
            move_forward_action.triggered.connect(move_forward_slot)
            move_to_front_action.triggered.connect(move_to_front_slot)

            def edit_action_slot() -> None:
                self._edit_tab_widget.setCurrentWidget(self._config_widget_container)
                self._show_config_of(widget)
                self._show_edit_menu(True)

            edit_action.triggered.connect(edit_action_slot)

            remove_action.triggered.connect(functools.partial(self._delete_widget, widget))

            menu.exec(self._workzone.mapToGlobal(event.pos()))

    def _show_config_of(self, widget: Optional[BaseHMIWidget]) -> None:
        """Make the HMI Widget configuration pane visible by swapping the QStackedLayout index. show an empty widget if None"""
        if widget is None:
            self._config_widget_container_layout.setCurrentIndex(0)  # Empty widget
        else:
            config_container = self._config_widgets[id(widget)]
            self._config_widget_container_layout.setCurrentWidget(config_container)

    def _workzone_left_click_slot(self, widget: Optional[BaseHMIWidget]) -> None:
        pass

    def _reassign_packed_zvalues(self) -> None:
        w = sorted(self._workzone.iterate_hmi_widgets(), key=lambda w: w.zValue())
        for i in range(len(w)):
            w[i].setZValue(i)    # Reassign packed values

    def _delete_widget(self, widget: BaseHMIWidget) -> None:
        """Delete an HMI widget from the view."""
        self._workzone.remove_widget(widget)
        widget.destroy()

        # Remove the config pane
        if self._config_widget_container_layout.currentWidget() is self._config_widgets[id(widget)]:
            self._config_widget_container_layout.setCurrentIndex(0)
        del self._config_widgets[id(widget)]    # Should never fail

        self._reassign_packed_zvalues()

        if self.logger.isEnabledFor(logging.DEBUG):
            ref_count = len(gc.get_referrers(widget))
            if ref_count > 1:
                self.logger.warning(f"Dangling reference to widget {widget.get_name()} after deletion")

# endregion

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            for widget in self._workzone.selected_widgets():
                self._delete_widget(widget)

        return super().keyPressEvent(event)

# endregion
