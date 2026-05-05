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

from PySide6.QtCore import Qt, QPoint, QSize, QRect
from PySide6.QtWidgets import QVBoxLayout, QSplitter, QTabWidget, QWidget, QStackedLayout, QScrollArea, QGroupBox
from PySide6.QtGui import QIcon, QKeyEvent, QMouseEvent

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.scrutiny_qmenu import ScrutinyQMenu
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent

from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, ValueSlotStateDict
from scrutiny.gui.components.locals.hmi.hmi_status_bar import HMIStatusBar
from scrutiny.gui.components.locals.hmi.hmi_workzone import HMIWorkZone

from scrutiny.gui.tools.invoker import invoke_later

from scrutiny.tools import validation
from scrutiny import tools
from scrutiny.tools.typing import *


class HMIWidgetStateDict(TypedDict):
    unique_name: str
    pos: Tuple[int, int]
    size: Tuple[int, int]
    zval: int
    value_slots: Dict[str, ValueSlotStateDict]
    implementation_config: Dict[str, Any]


class HMIComponentStateDict(TypedDict):
    hmi_widgets: List[HMIWidgetStateDict]
    workzone_size: Tuple[int, int]


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
    """The actual working mode: Edit or Display"""
    _workzone: HMIWorkZone
    """The drawing zone where the HMI widget goes"""
    _splitter: QSplitter
    """The splitter separating the library/config and the work zone"""
    _config_widget_container: QWidget
    """The widget that will contain the HMI widget configuration when they are selected"""
    _edit_tab_widget: QTabWidget
    """The tab to switch between lLibrary and Configuration"""
    _library: HMILibrary
    """The library displaying the available HMI Widgets"""
    _config_widgets: Dict[int, QWidget]
    """Dict mapping the HMI Widget id to their config widget that they provided with ``get_config_widget()``.
    Used to construct the configuration menu when they are selected """
    _config_widget_container_layout: QStackedLayout
    """The layout containing all config widgets, all staked together. Only one showed at the time"""
    _status_bar: HMIStatusBar
    """The status bar visible in the work zone when in edit mode"""
    _awaiting_delete_set: Set[int]
    """A set of instance ID to keep track of memory leaks."""
    _library_tab_index: int
    """Tab index of the Library Tab"""
    _configure_tab_index: int
    """Tab index of the configure tab"""
    _unittest_mode: bool
    """A flag enabling some unit test behavior"""


# region inherited methods
    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.GaugeLean)

    def setup(self) -> None:
        self._unittest_mode = False
        self._config_widgets = {}
        self._awaiting_delete_set = set()
        self._mode = HMIInteractionMode.Display
        self._status_bar = HMIStatusBar()
        self._workzone = HMIWorkZone(self._status_bar)
        self._library = HMILibrary()
        self._config_widget_container = QWidget()

        config_scroll = QScrollArea()
        config_scroll.setWidget(self._config_widget_container)
        config_scroll.setWidgetResizable(True)
        self._config_widget_container_layout = QStackedLayout(self._config_widget_container)
        self._config_widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._config_widget_container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._config_widget_container_layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._config_widget_container_layout.addWidget(QWidget())   # Empty widget at index 0

        self._edit_tab_widget = QTabWidget()
        self._library_tab_index = self._edit_tab_widget.addTab(self._library, "Library")
        self._configure_tab_index = self._edit_tab_widget.addTab(config_scroll, "Configure")

        self._edit_tab_widget.setMinimumWidth(192)

        workzone_status_bar_container = QWidget()
        workzone_status_bar_container_layout = QVBoxLayout(workzone_status_bar_container)
        workzone_status_bar_container_layout.setContentsMargins(0, 0, 0, 0)

        workzone_status_bar_container_layout.addWidget(self._workzone, 1)
        workzone_status_bar_container_layout.addWidget(self._status_bar)

        self._splitter = QSplitter()
        self._splitter.setOrientation(Qt.Orientation.Horizontal)
        self._splitter.setContentsMargins(0, 0, 0, 0)
        self._splitter.setHandleWidth(5)
        self._splitter.addWidget(self._edit_tab_widget)
        self._splitter.addWidget(workzone_status_bar_container)
        self._splitter.setCollapsible(self.SPLITTER_EDIT_MENU, True)
        self._splitter.setCollapsible(self.SPLITTER_WORKZONE, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._splitter, 1)  # 1=Stretch
        self._workzone.signals.right_click.connect(self._workzone_right_click_slot)
        self._workzone.signals.drop_widget_class.connect(self._workzone_drop_widget_class_slot)
        self._workzone.signals.selection_changed.connect(self._workzone_selection_changed_slot)
        self._show_edit_menu(False)  # Necessary to set the menu to a size of 0, used for state checking

        self._show_config_of(None)

        self.app.server_manager.signals.registry_changed.connect(self._registry_changed_slot)
        self._status_bar.signals.exit_edit_mode.connect(lambda: self.set_mode(HMIInteractionMode.Display))

    def ready(self) -> None:
        if self._workzone.count_hmi_widgets() == 0:
            # Blank component created
            self.set_mode(HMIInteractionMode.Edit)
        else:
            # State loaded from Dashboard
            self.set_mode(HMIInteractionMode.Display)

    def teardown(self) -> None:
        self._show_config_of(None)

        for hmi_widget in self._workzone.iterate_hmi_widgets():
            self.delete_hmi_widget(hmi_widget)

        self._workzone.signals.right_click.disconnect()
        self._workzone.signals.drop_widget_class.disconnect()
        self._workzone.signals.selection_changed.disconnect()
        self.app.server_manager.signals.registry_changed.disconnect()
        self._status_bar.signals.exit_edit_mode.disconnect()

        self._workzone.destroy()

    def get_state(self) -> Dict[Any, Any]:
        outdict: HMIComponentStateDict = {
            'hmi_widgets': [],
            'workzone_size': (self._workzone.size().width(), self._workzone.size().height())
        }

        for hmiwidget in self._workzone.iterate_hmi_widgets():
            pos = hmiwidget.pos().toPoint()
            size = hmiwidget.get_size()

            widget_state: HMIWidgetStateDict = {
                'unique_name': hmiwidget.get_unique_name(),
                'pos': (pos.x(), pos.y()),
                'size': (size.width(), size.height()),
                'zval': int(hmiwidget.zValue()),
                'value_slots': hmiwidget.get_value_slots_state(),
                'implementation_config': hmiwidget.get_implementation_config_dict()
            }

            outdict["hmi_widgets"].append(widget_state)

        return cast(Dict[Any, Any], outdict)

    def load_state(self, state: Dict[Any, Any]) -> bool:
        self.set_mode(HMIInteractionMode.Edit)

        for hmi_widget in list(self._workzone.iterate_hmi_widgets()):
            self.delete_hmi_widget(hmi_widget)

        state_cast = cast(HMIComponentStateDict, state)
        validation.assert_dict_key(state_cast, 'hmi_widgets', list)
        validation.assert_dict_key(state_cast, 'workzone_size', (list, tuple))

        def read_pair(d: Any, key: str) -> Tuple[int, int]:
            validation.assert_dict_key(d, key, (tuple, list))
            v = d[key]
            assert len(v) == 2, "Invalid size"
            assert isinstance(v[0], int), "Invalid size"
            assert isinstance(v[1], int), "Invalid size"
            if v[0] < 0 or v[1] < 0:
                raise ValueError("Invalid Size")
            return tuple(v)

        def read_size(d: Any, key: str) -> QSize:
            pair = read_pair(d, key)
            return QSize(pair[0], pair[1])

        def read_pos(d: Any, key: str) -> QPoint:
            pair = read_pair(d, key)
            return QPoint(pair[0], pair[1])

        workszone_size = read_size(state_cast, 'workzone_size')
        self._workzone.resize(workszone_size)

        fully_loaded_ok = True
        for widget_state in state_cast["hmi_widgets"]:
            hmi_widget_ok = False
            with tools.LogException(self.logger, Exception, "Cannot load invalid HMI widget", str_level=logging.WARNING):
                validation.assert_dict_key(widget_state, 'unique_name', str)

                with tools.LogException(self.logger, Exception, f"Cannot load HMI widget of type {widget_state['unique_name']}. Invalid", str_level=logging.WARNING):
                    widget_class = HMILibrary.load_from_unique_name(widget_state['unique_name'])
                    if widget_class is None:
                        raise ValueError(f"Unknown HMI widget of with unique name : {widget_state['unique_name']}")

                    validation.assert_dict_key(widget_state, 'size', (list, tuple))
                    validation.assert_dict_key(widget_state, 'pos', (list, tuple))
                    validation.assert_dict_key(widget_state, 'zval', int)
                    validation.assert_dict_key(widget_state, 'value_slots', dict)
                    validation.assert_dict_key(widget_state, 'implementation_config', dict)

                    size = read_size(widget_state, 'size')
                    pos = read_pos(widget_state, 'pos')
                    zval = widget_state['zval']

                    instance = widget_class(self.app)
                    instance.set_size(size)

                    self.add_hmi_widget(instance, scene_pos=pos, zval=zval)

                    # If this fails, warning will be logged from within the load function
                    if instance.apply_value_slots_state(widget_state['value_slots']) == False:
                        fully_loaded_ok = False

                    # If this fails, warning will be logged from within the load function
                    if instance.apply_implementation_config_dict(widget_state['implementation_config']) == False:
                        fully_loaded_ok = False

                    hmi_widget_ok = True

            if not hmi_widget_ok:
                fully_loaded_ok = False

        self._reassign_packed_zvalues()
        self.set_mode(HMIInteractionMode.Display)
        return fully_loaded_ok

    def visibilityChanged(self, visible: bool) -> None:
        if visible:
            self._resubscribe_all_hmi_widgets()
        else:
            self._unsubscribe_all_hmi_widgets()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            for widget in self._workzone.selected_widgets():    # This makes a copy
                self.delete_hmi_widget(widget)

        return super().keyPressEvent(event)

# endregion

# region Public

    def get_workzone(self) -> HMIWorkZone:
        return self._workzone

    def hmi_widget_count(self) -> int:
        return self._workzone.count_hmi_widgets()

    def iterate_hmi_widgets(self) -> Generator[BaseHMIWidget, None, None]:
        return self._workzone.iterate_hmi_widgets()

    def set_unittest_mode(self, val: bool) -> None:
        self._unittest_mode = val

    def add_hmi_widget(self, widget: BaseHMIWidget, scene_pos: Optional[QPoint] = None, zval: Optional[int] = None) -> None:
        """Add an HMI Widget to the workzone at the given position"""
        existing_widgets = sorted(list(self._workzone.iterate_hmi_widgets()), key=lambda w: w.zValue())
        self._workzone.add_widget(widget, scene_pos)
        self._create_config_widget_of(widget)
        self._show_config_of(widget)    # Show the config just created

        self.update_hmi_widget_state(widget)

        if zval is not None:
            widget.setZValue(zval)
        else:
            if len(existing_widgets) > 0:
                widget.setZValue(existing_widgets[-1].zValue() + 1)
            else:
                widget.setZValue(0)

    def delete_hmi_widget(self, widget: BaseHMIWidget) -> None:
        """Delete an HMI widget from the work zone."""
        self._workzone.remove_widget(widget)
        widget.destroy()

        # Remove the config pane
        if self._config_widget_container_layout.currentWidget() is self._config_widgets[id(widget)]:
            self._config_widget_container_layout.setCurrentIndex(0)
        del self._config_widgets[id(widget)]    # Should never fail

        self._reassign_packed_zvalues()

        # Try to find memory leaks. Not bulletproof
        # A closure in the server manager could kep the object alive temporarily.
        # Still efficient when developing

        self._awaiting_delete_set.add(widget.instance_id)
        widget.add_del_callback(functools.partial(self._hmi_widget_del_callback, widget.instance_id))

        fn = functools.partial(self.check_is_deleted, widget.instance_id, widget.get_display_name())
        invoke_later(fn)
        gc.collect()

    def move_to_back(self, widget: BaseHMIWidget) -> None:
        all_z = [w.zValue() for w in self._workzone.iterate_hmi_widgets()]
        if len(all_z) > 0:
            widget.setZValue(min(all_z) - 1)
        self._reassign_packed_zvalues()

    def move_to_front(self, widget: BaseHMIWidget) -> None:
        all_z = [w.zValue() for w in self._workzone.iterate_hmi_widgets()]
        if len(all_z) > 0:
            widget.setZValue(max(all_z) + 1)
        self._reassign_packed_zvalues()

    def move_backward(self, widget: BaseHMIWidget) -> None:
        previous = sorted([w for w in self._workzone.iterate_hmi_widgets() if w.zValue() < widget.zValue()], key=lambda w: w.zValue())
        if len(previous) > 0:   # swap
            temp = previous[-1].zValue()
            previous[-1].setZValue(widget.zValue())
            widget.setZValue(temp)

    def move_forward(self, widget: BaseHMIWidget) -> None:
        nexts = sorted([w for w in self._workzone.iterate_hmi_widgets() if w.zValue() > widget.zValue()], key=lambda w: w.zValue())
        if len(nexts) > 0:   # swap
            temp = nexts[0].zValue()
            nexts[0].setZValue(widget.zValue())
            widget.setZValue(temp)

    def is_edit_mode(self) -> bool:
        return self._mode == HMIInteractionMode.Edit

    def update_hmi_widget_state(self, widget: BaseHMIWidget) -> None:
        """Update the visual of the HMI widget based on the state of this component"""
        widget.set_edit_mode(self.is_edit_mode())

    def set_mode(self, mode: HMIInteractionMode) -> None:
        """Switch working mode (Edit or Display)"""
        self._mode = mode
        self._workzone.deselect_all_widgets()

        if self._mode == HMIInteractionMode.Edit:
            self._show_edit_menu(True)
            self._workzone.show_grid(True)
            self._workzone.setAcceptDrops(True)
            self._workzone.set_allow_edit_widgets(True)
            self._status_bar.setVisible(True)
        elif self._mode == HMIInteractionMode.Display:
            self._show_edit_menu(False)
            self._workzone.show_grid(False)
            self._workzone.setAcceptDrops(False)
            self._workzone.set_allow_edit_widgets(False)
            self._status_bar.setVisible(False)

        for hmi_widget in self._workzone.iterate_hmi_widgets():
            self.update_hmi_widget_state(hmi_widget)
# endregion

# region Private

    def _registry_changed_slot(self) -> None:
        """ Called when watchables are added/removed from the registry"""
        self._resubscribe_all_hmi_widgets()

    def _resubscribe_all_hmi_widgets(self) -> None:
        """Try to resubscribe each HMI Widget to their respective watchable (drag&dropped by the user) if possible"""
        for hmi_widget in self._workzone.iterate_hmi_widgets():
            hmi_widget.try_watch_all_vslots()

    def _unsubscribe_all_hmi_widgets(self) -> None:
        """Try to resubscribe each HMI Widget to their respective watchable (drag&dropped by the user) if possible"""
        for hmi_widget in self._workzone.iterate_hmi_widgets():
            hmi_widget.unwatch_all_vslots()

    def _show_edit_menu(self, val: bool) -> None:
        """Show or hide the left part of the splitter"""
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

        vslot_config = widget.get_slot_config_widget()
        if vslot_config is not None:
            vslot_gb = QGroupBox("Input values")
            vslot_gb_layout = QVBoxLayout(vslot_gb)
            vslot_gb_layout.setContentsMargins(0, 0, 0, 0)
            vslot_gb_layout.addWidget(vslot_config)
            layout.addWidget(vslot_gb)

        specific_config = widget.get_config_widget()
        if specific_config is not None:
            layout.addWidget(specific_config)

        self._config_widgets[id(widget)] = config_container
        self._config_widget_container_layout.addWidget(config_container)

    def _workzone_drop_widget_class_slot(self, widget_class: Type[BaseHMIWidget], scene_pos: QPoint) -> None:
        """Callback invoked when a HMI widget is dropped on the workzone from the Library"""
        instance = widget_class(self.app)
        self.add_hmi_widget(instance, scene_pos)

    def _workzone_selection_changed_slot(self, widgets: List[BaseHMIWidget]) -> None:
        """When the user changes the selection"""
        if len(widgets) == 1:   # Show the config only if 1 is selected. Don't manage common properties.
            self._show_config_of(widgets[0])
        else:
            self._show_config_of(None)

    def _workzone_right_click_slot(self, widget: Optional[BaseHMIWidget], event: QMouseEvent) -> None:
        """Right click on an HMI widget in the workzone"""
        menu: Optional[ScrutinyQMenu] = None

        if self._mode == HMIInteractionMode.Display:
            menu = ScrutinyQMenu()
            edit_mode_action = menu.addAction("Edit HMI dashboard")
            edit_mode_action.triggered.connect(lambda: self.set_mode(HMIInteractionMode.Edit))

        elif self._mode == HMIInteractionMode.Edit:
            if widget is None:
                menu = ScrutinyQMenu()
                display_mode_action = menu.addAction("Display mode")
                display_mode_action.triggered.connect(lambda: self.set_mode(HMIInteractionMode.Display))

            else:
                self._workzone.select_widgets([widget])
                menu = ScrutinyQMenu()
                remove_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")
                edit_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Edit")
                move_to_action = menu.addAction("Move")

                move_to_menu = ScrutinyQMenu()
                move_to_back_action = move_to_menu.addAction("To Back")
                move_backward_action = move_to_menu.addAction("Backward")
                move_forward_action = move_to_menu.addAction("Forward")
                move_to_front_action = move_to_menu.addAction("To Front")
                move_to_action.setMenu(move_to_menu)

                move_to_back_action.triggered.connect(functools.partial(self.move_to_back, widget))
                move_backward_action.triggered.connect(functools.partial(self.move_backward, widget))
                move_forward_action.triggered.connect(functools.partial(self.move_forward, widget))
                move_to_front_action.triggered.connect(functools.partial(self.move_to_front, widget))

                def edit_action_slot() -> None:
                    self._edit_tab_widget.setCurrentIndex(self._configure_tab_index)
                    self._show_config_of(widget)
                    self._show_edit_menu(True)

                edit_action.triggered.connect(edit_action_slot)

                def remove_action_slot() -> None:
                    invoke_later(functools.partial(self.delete_hmi_widget, widget))
                remove_action.triggered.connect(remove_action_slot)

        if menu is not None and not self._unittest_mode:
            menu.exec_and_disconnect_triggered(self._workzone.mapToGlobal(event.pos()))  # pragma: no cover

    def _show_config_of(self, widget: Optional[BaseHMIWidget]) -> None:
        """Make the HMI Widget configuration pane visible by swapping the QStackedLayout index. show an empty widget if None"""
        if widget is None:
            self._config_widget_container_layout.setCurrentIndex(0)  # Empty widget
        else:
            config_wdiget = self._config_widgets[id(widget)]
            self._config_widget_container_layout.setCurrentWidget(config_wdiget)

    def _hmi_widget_del_callback(self, instance_id: int) -> None:
        if instance_id in self._awaiting_delete_set:
            self._awaiting_delete_set.remove(instance_id)

    def check_is_deleted(self, instance_id: int, name: str) -> None:
        if instance_id in self._awaiting_delete_set:
            self.logger.warning(f"Dangling reference to widget {name} after deletion")

    def _reassign_packed_zvalues(self) -> None:
        """Take every HMI widget is change their ZValue so they range from 0 to N without holes in between them"""
        w = sorted(self._workzone.iterate_hmi_widgets(), key=lambda w: w.zValue())
        for i in range(len(w)):
            w[i].setZValue(i)    # Reassign packed values
# endregion
