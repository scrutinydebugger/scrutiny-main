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
import json
from dataclasses import dataclass

from scrutiny.gui.components.locals.hmi.hmi_library import HMILibrary

from PySide6.QtCore import Qt, QPoint, QSize, QRect, QMimeData, QByteArray, QPointF, QRectF
from PySide6.QtWidgets import QVBoxLayout, QSplitter, QTabWidget, QWidget, QStackedLayout, QGroupBox, QApplication
from PySide6.QtGui import QIcon, QKeyEvent, QMouseEvent

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.scrutiny_qmenu import ScrutinyQMenu
from scrutiny.gui.widgets.vertical_scroll_area import VerticalScrollArea
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


class CopyPasteStateDict(TypedDict):
    hmi_widgets: List[HMIWidgetStateDict]


class HMIComponentStateDict(TypedDict):
    hmi_widgets: List[HMIWidgetStateDict]
    workzone_size: Tuple[int, int]


class HMIInteractionMode(enum.Enum):
    Display = enum.auto()
    Edit = enum.auto()


@dataclass
class HMIWidgetCreatedFromState:
    instance: BaseHMIWidget
    pos: QPoint
    zval: int
    fully_loaded: bool


class StateParser:

    @staticmethod
    def read_posint_pair(d: Any, key: str) -> Tuple[int, int]:
        validation.assert_dict_key(d, key, (tuple, list))
        v = d[key]
        assert len(v) == 2, f"Invalid {key}"
        assert isinstance(v[0], int), f"Invalid {key}"
        assert isinstance(v[1], int), f"Invalid {key}"
        if v[0] < 0 or v[1] < 0:
            raise ValueError(f"Invalid {key}")
        return tuple(v)

    @staticmethod
    def read_size(d: Any, key: str) -> QSize:
        pair = StateParser.read_posint_pair(d, key)
        return QSize(pair[0], pair[1])

    @staticmethod
    def read_pos(d: Any, key: str) -> QPoint:
        pair = StateParser.read_posint_pair(d, key)
        return QPoint(pair[0], pair[1])


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
    _has_unsaved_changes: bool
    """A flag used to prompt the user for a confirmation on close if there are modifications """


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
        self._has_unsaved_changes = False

        config_scroll = VerticalScrollArea()
        config_scroll.setWidget(self._config_widget_container)
        library_scroll = VerticalScrollArea()
        library_scroll.setWidget(self._library)
        self._config_widget_container_layout = QStackedLayout(self._config_widget_container)
        self._config_widget_container_layout.setContentsMargins(0, 0, 0, 0)
        self._config_widget_container_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._config_widget_container_layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._config_widget_container_layout.addWidget(QWidget())   # Empty widget at index 0

        self._edit_tab_widget = QTabWidget()
        self._library_tab_index = self._edit_tab_widget.addTab(library_scroll, "Library")
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
        self._workzone.signals.double_click_edit_widget.connect(self._workzone_double_click_edit_widget_slot)
        self._workzone.signals.drop_widget_class.connect(self._workzone_drop_widget_class_slot)
        self._workzone.signals.selection_changed.connect(self._workzone_selection_changed_slot)
        self._workzone.signals.modified.connect(self._invalidate_save)
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

        self.delete_hmi_widgets(list(self._workzone.iterate_hmi_widgets()))

        self._workzone.signals.right_click.disconnect()
        self._workzone.signals.drop_widget_class.disconnect()
        self._workzone.signals.selection_changed.disconnect()
        self._workzone.signals.double_click_edit_widget.disconnect()
        self.app.server_manager.signals.registry_changed.disconnect(self._registry_changed_slot)
        self._status_bar.signals.exit_edit_mode.disconnect()

        self._workzone.destroy()

    def get_state(self) -> Dict[Any, Any]:
        outdict: HMIComponentStateDict = {
            'hmi_widgets': [],
            'workzone_size': (self._workzone.size().width(), self._workzone.size().height())
        }

        for hmiwidget in self._workzone.iterate_hmi_widgets():
            outdict["hmi_widgets"].append(self._make_hmi_widget_state(hmiwidget))

        return cast(Dict[Any, Any], outdict)

    def _create_hmi_widget_from_state_dict(self, widget_state: HMIWidgetStateDict) -> HMIWidgetCreatedFromState:
        fully_loaded = True

        widget_class = HMILibrary.load_from_unique_name(widget_state['unique_name'])
        if widget_class is None:
            raise ValueError(f"Unknown HMI widget of with unique name : {widget_state['unique_name']}")

        validation.assert_dict_key(widget_state, 'size', (list, tuple))
        validation.assert_dict_key(widget_state, 'pos', (list, tuple))
        validation.assert_dict_key(widget_state, 'zval', int)
        validation.assert_dict_key(widget_state, 'value_slots', dict)
        validation.assert_dict_key(widget_state, 'implementation_config', dict)

        size = StateParser.read_size(widget_state, 'size')
        pos = StateParser.read_pos(widget_state, 'pos')
        zval = widget_state['zval']

        instance = widget_class(self.app)
        instance.set_size(size)

        # If this fails, warning will be logged from within the load function
        if instance.apply_value_slots_state(widget_state['value_slots']) == False:
            fully_loaded = False

        # If this fails, warning will be logged from within the load function
        if instance.apply_implementation_config_dict(widget_state['implementation_config']) == False:
            fully_loaded = False

        return HMIWidgetCreatedFromState(
            instance=instance,
            pos=pos,
            zval=zval,
            fully_loaded=fully_loaded
        )

    def load_state(self, state: Dict[Any, Any]) -> bool:
        self.set_mode(HMIInteractionMode.Edit)

        self.delete_hmi_widgets(list(self._workzone.iterate_hmi_widgets()))

        state_cast = cast(HMIComponentStateDict, state)
        validation.assert_dict_key(state_cast, 'hmi_widgets', list)
        validation.assert_dict_key(state_cast, 'workzone_size', (list, tuple))

        workszone_size = StateParser.read_size(state_cast, 'workzone_size')
        self._workzone.setSceneRect(QRect(QPoint(0, 0), workszone_size))
        self._workzone.resize(workszone_size)

        fully_loaded_ok = True
        for widget_state in state_cast["hmi_widgets"]:
            with tools.LogException(self.logger, Exception, "Cannot load invalid HMI widget", str_level=logging.WARNING):
                validation.assert_dict_key(widget_state, 'unique_name', str)

                with tools.LogException(self.logger, Exception, f"Cannot load HMI widget of type {widget_state['unique_name']}. Invalid", str_level=logging.WARNING):
                    hmi_widget = self._create_hmi_widget_from_state_dict(widget_state)
                    self.add_hmi_widget(hmi_widget.instance, scene_pos=hmi_widget.pos, zval=hmi_widget.zval)
                    if not hmi_widget.fully_loaded:
                        fully_loaded_ok = False

        self._reassign_packed_zvalues()
        self._resubscribe_all_hmi_widgets()
        self.set_mode(HMIInteractionMode.Display)
        self._has_unsaved_changes = False
        return fully_loaded_ok

    def visibilityChanged(self, visible: bool) -> None:
        if visible:
            self._resubscribe_all_hmi_widgets()
        else:
            self._unsubscribe_all_hmi_widgets()

    def has_unsaved_changes(self) -> bool:
        return self._has_unsaved_changes

    def saved(self) -> None:
        self._has_unsaved_changes = False

    def keyPressEvent(self, event: QKeyEvent) -> None:

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_C:
                self.copy_widgets_to_clipboard(self._workzone.selected_widgets())
            elif event.key() == Qt.Key.Key_V:
                self.paste_widgets_from_clipboard(scene_pos=None)

        elif event.modifiers() == Qt.KeyboardModifier.NoModifier:
            if event.key() == Qt.Key.Key_Delete:
                self.delete_hmi_widgets(self._workzone.selected_widgets())

        return super().keyPressEvent(event)

# endregion

# region Public

    def get_workzone(self) -> HMIWorkZone:
        return self._workzone

    def selected_widgets(self) -> List[BaseHMIWidget]:
        return self._workzone.selected_widgets()

    def hmi_widget_count(self) -> int:
        return self._workzone.count_hmi_widgets()

    def iterate_hmi_widgets(self) -> Generator[BaseHMIWidget, None, None]:
        return self._workzone.iterate_hmi_widgets()

    def set_unittest_mode(self, val: bool) -> None:
        self._unittest_mode = val

    def add_hmi_widget(self, widget: BaseHMIWidget, scene_pos: Optional[QPoint] = None, zval: Optional[int] = None) -> None:
        """Add an HMI Widget to the workzone at the given position"""
        existing_widgets = sorted(list(self._workzone.iterate_hmi_widgets()), key=lambda w: w.zValue())
        self._workzone.add_widget(widget, scene_pos)    # Will emit "modified"
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

        widget.signals.modified.connect(self._invalidate_save)

    def delete_hmi_widgets(self, widgets: List[BaseHMIWidget]) -> None:
        """Delete multiple HMI widget from the work zone."""
        for widget in widgets:
            widget.signals.modified.disconnect(self._invalidate_save)

            self._workzone.remove_widget(widget)    # Will emit "modified"
            widget.destroy()

            # Remove the config pane
            if self._config_widget_container_layout.currentWidget() is self._config_widgets[id(widget)]:
                self._config_widget_container_layout.setCurrentIndex(0)
            del self._config_widgets[id(widget)]    # Should never fail

            # Try to find memory leaks. Not bulletproof
            # A closure in the server manager could keep the object alive temporarily.
            # Still efficient when developing
            self._awaiting_delete_set.add(widget.instance_id)
            widget.add_del_callback(functools.partial(self._hmi_widget_del_callback, widget.instance_id))

            fn = functools.partial(self._check_is_deleted, widget.instance_id, widget.get_display_name())
            invoke_later(fn)

        self._reassign_packed_zvalues()
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
            self._workzone.set_edit_mode(True)
            self._status_bar.setVisible(True)
        elif self._mode == HMIInteractionMode.Display:
            self._show_edit_menu(False)
            self._workzone.show_grid(False)
            self._workzone.setAcceptDrops(False)
            self._workzone.set_edit_mode(False)
            self._status_bar.setVisible(False)

        for hmi_widget in self._workzone.iterate_hmi_widgets():
            self.update_hmi_widget_state(hmi_widget)

    def copy_widgets_to_clipboard(self, widgets: List[BaseHMIWidget]) -> None:
        """Take the widgets and put their state in the clipboard so they can be pasted later"""
        state_dict: CopyPasteStateDict = {
            'hmi_widgets': []
        }

        for widget in widgets:
            state_dict['hmi_widgets'].append(self._make_hmi_widget_state(widget))

        serializable_dict = {
            'type': 'hmi_widget_state',
            'state': state_dict
        }
        data = QMimeData()
        data.setData('application/json', QByteArray.fromStdString(json.dumps(serializable_dict)))
        QApplication.clipboard().setMimeData(data)

    def paste_widgets_from_clipboard(self, scene_pos: Optional[QPointF]) -> None:
        selection = self._read_clipboard_selection()
        if selection is not None:
            self._paste_widgets(selection, scene_pos=scene_pos)


# endregion

# region Private

    def _invalidate_save(self) -> None:
        self._has_unsaved_changes = True

    def _make_hmi_widget_state(self, hmiwidget: BaseHMIWidget) -> HMIWidgetStateDict:
        pos = hmiwidget.pos().toPoint()
        size = hmiwidget.get_size()

        return {
            'unique_name': hmiwidget.get_unique_name(),
            'pos': (pos.x(), pos.y()),
            'size': (size.width(), size.height()),
            'zval': int(hmiwidget.zValue()),
            'value_slots': hmiwidget.get_value_slots_state(),
            'implementation_config': hmiwidget.get_implementation_config_dict()
        }

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

    def _workzone_right_click_slot(self, widgets: List[BaseHMIWidget], event: QMouseEvent) -> None:
        """Right click on an HMI widget in the workzone"""
        menu: Optional[ScrutinyQMenu] = None

        if self._mode == HMIInteractionMode.Display:
            menu = ScrutinyQMenu()
            edit_mode_action = menu.addAction("Edit HMI dashboard")
            edit_mode_action.triggered.connect(lambda: self.set_mode(HMIInteractionMode.Edit))

        elif self._mode == HMIInteractionMode.Edit:
            if len(widgets) == 0:
                menu = ScrutinyQMenu()
                display_mode_action = menu.addAction("Display mode")
                display_mode_action.triggered.connect(lambda: self.set_mode(HMIInteractionMode.Display))

                paste_action = menu.addAction("Paste")
                data_to_paste = self._read_clipboard_selection()
                paste_action.setEnabled(data_to_paste is not None)
                if data_to_paste is not None:
                    paste_partial_func = functools.partial(self._paste_widgets, data_to_paste, self._workzone.mapToScene(event.pos()))
                    paste_action.triggered.connect(paste_partial_func)

            else:
                self._workzone.select_widgets(widgets)
                menu = ScrutinyQMenu()
                remove_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")
                edit_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Edit")
                copy_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Copy), "Copy")
                move_to_action = menu.addAction("Move")

                move_to_menu = ScrutinyQMenu()
                move_to_back_action = move_to_menu.addAction("To Back")
                move_backward_action = move_to_menu.addAction("Backward")
                move_forward_action = move_to_menu.addAction("Forward")
                move_to_front_action = move_to_menu.addAction("To Front")
                move_to_action.setMenu(move_to_menu)

                if len(widgets) == 1:
                    move_to_back_action.triggered.connect(functools.partial(self.move_to_back, widgets[0]))
                    move_backward_action.triggered.connect(functools.partial(self.move_backward, widgets[0]))
                    move_forward_action.triggered.connect(functools.partial(self.move_forward, widgets[0]))
                    move_to_front_action.triggered.connect(functools.partial(self.move_to_front, widgets[0]))

                    edit_action.triggered.connect(functools.partial(self._request_edit_of_widget, widgets[0]))

                else:
                    move_to_back_action.setEnabled(False)
                    move_backward_action.setEnabled(False)
                    move_forward_action.setEnabled(False)
                    move_to_front_action.setEnabled(False)
                    edit_action.setEnabled(False)

                copy_action.triggered.connect(functools.partial(self.copy_widgets_to_clipboard, widgets))
                copy_action.setEnabled(len(widgets) > 0)

                def remove_action_slot() -> None:
                    invoke_later(functools.partial(self.delete_hmi_widgets, widgets))
                remove_action.triggered.connect(remove_action_slot)

        if menu is not None and not self._unittest_mode:
            menu.exec_and_disconnect_triggered(self._workzone.mapToGlobal(event.pos()))  # pragma: no cover

    def _workzone_double_click_edit_widget_slot(self, widget: BaseHMIWidget) -> None:
        """Invoked when the user double click a widget in edit mode"""
        self._request_edit_of_widget(widget)

    def _request_edit_of_widget(self, widget: BaseHMIWidget) -> None:
        """Open the edition menu and show config of given widget. """
        self._edit_tab_widget.setCurrentIndex(self._configure_tab_index)
        self._show_config_of(widget)
        self._show_edit_menu(True)

    def _read_clipboard_selection(self) -> Optional[CopyPasteStateDict]:
        """Read the clipboard for a possible dictionary containing a series of HMI widgets copied.
         Return None if there is no valid selection in the clipboard. """
        mime_data = QApplication.clipboard().mimeData()
        if mime_data is None:
            return None
        json_data = mime_data.data('application/json')

        try:
            json_decoded = json.loads(QByteArray.toStdString(json_data))
        except json.JSONDecodeError:
            return None

        if not json_decoded.get('type', '') == 'hmi_widget_state':
            return None

        if 'state' not in json_decoded or not isinstance(json_decoded['state'], dict):
            return None

        return cast(CopyPasteStateDict, json_decoded['state'])

    def _paste_widgets(self, copy_paste_state_dict: CopyPasteStateDict, scene_pos: Optional[QPointF]) -> None:
        """Read a state dictionary created by a clipboard copy and add the widgets at the specified location.
        If no location is specified, shift on the grid by 1 step"""

        if 'hmi_widgets' not in copy_paste_state_dict or not isinstance(copy_paste_state_dict['hmi_widgets'], list):
            return

        hmi_widgets: List[HMIWidgetCreatedFromState] = []
        try:
            for widget_state_dict in copy_paste_state_dict['hmi_widgets']:
                hmi_widgets.append(self._create_hmi_widget_from_state_dict(widget_state_dict))
        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to paste HMI widgets")
            return

        if len(hmi_widgets) == 0:
            return

        bounding_box = QRectF(
            hmi_widgets[0].pos,
            hmi_widgets[0].instance.get_size()
        )
        max_zval = max(int(w.zValue()) for w in self.iterate_hmi_widgets())
        hmi_widgets.sort(key=lambda w: w.zval)

        for hmi_widget in hmi_widgets:
            bounding_box.setLeft(min(bounding_box.left(), hmi_widget.pos.x()))
            bounding_box.setTop(min(bounding_box.top(), hmi_widget.pos.y()))
            bounding_box.setRight(max(bounding_box.right(), hmi_widget.pos.x() + hmi_widget.instance.get_size().width()))
            bounding_box.setBottom(max(bounding_box.bottom(), hmi_widget.pos.y() + hmi_widget.instance.get_size().height()))

        top_left_insert_offset = QPointF(self._workzone.get_grid_spacing(), self._workzone.get_grid_spacing())
        if scene_pos is not None:
            top_left_insert_offset = scene_pos - bounding_box.topLeft()

        for hmi_widget in hmi_widgets:
            new_pos = hmi_widget.pos + top_left_insert_offset.toPoint()
            self.add_hmi_widget(hmi_widget.instance, scene_pos=new_pos, zval=max_zval)
            max_zval += 1

        self._reassign_packed_zvalues()
        self._resubscribe_all_hmi_widgets()

        self._workzone.select_widgets([w.instance for w in hmi_widgets])

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

    def _check_is_deleted(self, instance_id: int, name: str) -> None:
        if instance_id in self._awaiting_delete_set:
            self.logger.warning(f"Dangling reference to widget {name} after deletion")

    def _reassign_packed_zvalues(self) -> None:
        """Take every HMI widget is change their ZValue so they range from 0 to N without holes in between them"""
        w = sorted(self._workzone.iterate_hmi_widgets(), key=lambda w: w.zValue())
        for i in range(len(w)):
            w[i].setZValue(i)    # Reassign packed values
# endregion
