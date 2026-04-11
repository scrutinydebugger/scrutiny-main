#    base_hmi_widget.py
#        Base class for every widgets part of a HMI component.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass
import functools
import time
import logging
import enum

from PySide6.QtWidgets import QWidget, QFormLayout, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtGui import QPainter, QPixmap, QValidator, QBrush
from PySide6.QtCore import QSize, QRectF, QPointF, QObject, QRect, QPoint, Qt

from scrutiny import sdk
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.hmi_graphic_view import Grid
from scrutiny.gui.core.watchable_registry import WatcherIdType, RegistryValueUpdate
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.tools.global_counters import global_i64_counter
from scrutiny.tools.typing import *


if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent

T = TypeVar('T')


class HandlePosition(enum.Enum):
    TOPLEFT = enum.auto()
    TOPMID = enum.auto()
    TOPRIGHT = enum.auto()
    MIDLEFT = enum.auto()
    MIDRIGHT = enum.auto()
    BOTTOMLEFT = enum.auto()
    BOTTOMMID = enum.auto()
    BOTTOMRIGHT = enum.auto()


@dataclass(slots=True, init=False)
class ValueSlot:
    class SlotType(enum.Enum):
        Constant = enum.auto()
        Watchable = enum.auto()
        Both = enum.auto()

    name: str
    display_name: str
    watchable_line_edit: WatchableLineEdit
    watcher_id: str
    last_value_received: Optional[Union[float, int, bool]]
    slot_type: SlotType
    text_validator: QValidator

    def __init__(self,
                 name: str,
                 display_name: str,
                 slot_type: SlotType = SlotType.Both
                 ) -> None:
        self.name = name
        self.display_name = display_name
        self.watchable_line_edit = WatchableLineEdit()
        self.watcher_id = f'{name}{global_i64_counter()}'
        self.last_value_received = None
        self.slot_type = slot_type

    def _read_text_val(self, textval: str) -> Optional[Union[float, int, bool]]:
        textval = textval.lower().strip()
        if textval == "true":
            return True
        if textval == "false":
            return False

        try:
            return int(textval)
        except ValueError:
            pass

        try:
            return float(textval)
        except ValueError:
            pass

        return None

    def is_configured(self) -> bool:
        if self.watchable_line_edit.is_text_mode():
            return self._read_text_val(self.watchable_line_edit.text()) is not None
        else:
            return self.watchable_line_edit.get_watchable() is not None

    def get_val(self) -> Optional[Union[int, float, bool]]:
        if self.watchable_line_edit.is_text_mode():
            return self._read_text_val(self.watchable_line_edit.text())
        else:
            return self.last_value_received


class BaseHMIWidget(QGraphicsItem):
    MAX_DRAW_RATE = 15
    HANDLE_HW = 6
    MAX_DRAW_RATE_NANOSEC = int(round((1 / MAX_DRAW_RATE) * 1e9))
    HALF_HANDLE_HW = HANDLE_HW / 2

    class _Signals(QObject):
        pass

    _wslots: List[ValueSlot]
    _hmi_component: "HMIComponent"
    _need_redraw: bool
    _pending_redraw: bool
    _last_draw_timestamp_ns: int
    _parent_constructor_called: bool
    _size: QSize
    _logger: logging.Logger
    _signals: _Signals
    _draw_resize_handles: bool
    _selected: bool

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__()
        self._wslots = []
        self._hmi_component = hmi_component
        self._need_redraw = False
        self._last_draw_timestamp_ns = time.perf_counter_ns()
        self._parent_constructor_called = True
        self._size = QSize(128, 128)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._signals = self._Signals()
        self._draw_resize_handles = False
        self._selected = False

    @property
    def signals(self) -> _Signals:
        return self._signals

    @classmethod
    def get_category(cls) -> LibraryCategory:
        return cls._read_class_prop('_CATEGORY', LibraryCategory)

    @classmethod
    def get_name(cls) -> str:
        return cls._read_class_prop('_NAME', str)

    @classmethod
    def get_icon_as_pixmap(cls) -> QPixmap:
        icon = cls._read_class_prop('_ICON', assets.Icons)
        return scrutiny_get_theme().load_medium_icon_as_pixmap(icon)

    @classmethod
    def _read_class_prop(cls, propname: str, t: Type[T]) -> T:
        if not hasattr(cls, propname):
            raise RuntimeError(f"Class {cls.__name__} has not defined \"{propname}\" ")
        v = getattr(cls, propname)
        if not isinstance(v, t):
            raise RuntimeError(f"Class {cls.__name__} has defined \"{propname}\" of the wrong type. expected {t.__name__}")
        return v

    def set_size(self, size: QSize) -> None:
        self.prepareGeometryChange()
        self._size = size
        self.update()

    def get_size(self) -> QSize:
        return self._size

    def show_resize_handles(self, val: bool) -> None:
        self._draw_resize_handles = val

    def set_selected(self, val: bool) -> None:
        self._selected = val
        self.update()

    def toggle_selected(self) -> None:
        self.set_selected(not self.is_selected())

    def is_selected(self) -> bool:
        return self._selected

    def declare_value_slot(self, name: str, display_name: str) -> None:
        if not (hasattr(self, '_parent_constructor_called')):
            raise RuntimeError("Parent constructor not called")
        used_names = set([wslot.name for wslot in self._wslots])
        if name in used_names:
            raise ValueError(f"Duplicate watchable slot with name {name}")

        wslot = ValueSlot(
            name=name,
            display_name=display_name
        )

        self._wslots.append(wslot)

        val_update_lost = functools.partial(self._val_update_callback, wslot)
        self._hmi_component.app.watchable_registry.register_watcher(wslot.watcher_id, val_update_lost, self._unwatch_callback)

        partial_slot = functools.partial(self._wslot_configured_slot, wslot)
        wslot.watchable_line_edit.signals.watchable_dropped.connect(partial_slot)

    def destroy(self) -> None:
        for wslots in self._wslots:
            self._hmi_component.app.watchable_registry.unregister_watcher(wslots.watcher_id)    # Will unwatch all
        self._wslots.clear()

    def boundingRect(self) -> QRectF:
        return QRectF(QPointF(0, 0), self._size)


# region Private

    def _val_update_callback(self, wslot: ValueSlot, watcher_id: WatcherIdType, updates: List[RegistryValueUpdate]) -> None:
        wslot.last_value_received = updates[-1].sdk_update.value
        self._need_redraw = True
        invoke_later(self._redraw_if_allowed)

    def _unwatch_callback(self, watcher_id: Union[str, int], server_path: str, watchable_config: sdk.BriefWatchableConfiguration, registry_id: int) -> None:
        pass

    def _wslot_configured_slot(self, wslot: ValueSlot, fqn: str) -> None:
        self._hmi_component.app.watchable_registry.watch_fqn(wslot.watcher_id, fqn)

    def _get_slot_by_name(self, name: str) -> ValueSlot:
        for wslot in self._wslots:
            if wslot.name == name:
                return wslot

        raise ValueError(f"No watchable slot with name {name}")

    def _make_slot_config_widget(self) -> QWidget:
        container = QWidget()
        container_layout = QFormLayout(container)

        for wslot in self._wslots:
            container_layout.addRow(wslot.display_name, wslot.watchable_line_edit)

        return container

    def _all_wslots_filled(self) -> bool:
        for wslot in self._wslots:
            if wslot.watchable_line_edit.is_text_mode():
                if wslot.get_val() is None:
                    return False
            else:
                watchable = wslot.watchable_line_edit.get_watchable()
                if watchable is None:
                    return False

                node = self._hmi_component.app.watchable_registry.get_watchable_node_fqn(watchable.fqn)
                if node is None:
                    return False

        return True

    def _redraw_later(self) -> None:
        def callback() -> None:
            self._pending_redraw = False
            if self._need_redraw:
                self._redraw_if_allowed()

        if not self._pending_redraw:
            self._pending_redraw = True
            invoke_later(callback, int(self.MAX_DRAW_RATE_NANOSEC // 1e6))    # Retry later if still needed

    def _redraw_if_allowed(self) -> None:
        updated = False

        dt_ns = time.perf_counter_ns() - self._last_draw_timestamp_ns
        if dt_ns > self.MAX_DRAW_RATE_NANOSEC:
            self.update()
            updated = True

        if not updated:
            self._redraw_later()

    def resize_handles_coordinates(self) -> Dict[HandlePosition, QRectF]:
        handle_size = QSize(self.HANDLE_HW, self.HANDLE_HW)
        w = self._size.width()
        h = self._size.height()
        left_x = 0
        mid_x = w / 2 - self.HALF_HANDLE_HW
        right_x = w - self.HANDLE_HW
        top_y = 0
        mid_y = h / 2 - self.HALF_HANDLE_HW
        bottom_y = h - self.HANDLE_HW

        return {
            HandlePosition.TOPLEFT: QRectF(QPointF(left_x, top_y), handle_size),
            HandlePosition.TOPMID: QRectF(QPointF(mid_x, top_y), handle_size),
            HandlePosition.TOPRIGHT: QRectF(QPointF(right_x, top_y), handle_size),
            HandlePosition.MIDLEFT: QRectF(QPointF(left_x, mid_y), handle_size),
            HandlePosition.MIDRIGHT: QRectF(QPointF(right_x, mid_y), handle_size),
            HandlePosition.BOTTOMLEFT: QRectF(QPointF(left_x, bottom_y), handle_size),
            HandlePosition.BOTTOMMID: QRectF(QPointF(mid_x, bottom_y), handle_size),
            HandlePosition.BOTTOMRIGHT: QRectF(QPointF(right_x, bottom_y), handle_size),
        }

# endregion

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        self._need_redraw = False
        self._pending_redraw = False

        configured = self._all_wslots_filled()
        values = {wslot.name: wslot.get_val() for wslot in self._wslots}

        self.draw(configured, values, self._size, painter)
        if self._selected:
            highlight_color = scrutiny_get_theme().palette().highlight().color()
            highlight_color.setAlpha(0x66)
            painter.setPen(highlight_color)
            painter.setBrush(highlight_color)
            painter.drawRect(QRect(QPoint(0, 0), self._size))

        if self._draw_resize_handles:
            text_color = scrutiny_get_theme().palette().text().color()
            painter.setPen(text_color)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRect(QRectF(QPointF(0, 0), self._size))
            painter.setBrush(text_color)
            handles = self.resize_handles_coordinates()
            for handle in handles.values():
                painter.drawRect(handle)

        self._last_draw_timestamp_ns = time.perf_counter_ns()
        if self._need_redraw:           # got a value update while drawing
            self._redraw_if_allowed()   # Update rate is enforced here

# region Abstracts methods

    def draw(self,
             configured: bool,
             values: Dict[str, Optional[Union[float, int, bool]]],
             draw_zone_size: QSize,
             painter: QPainter
             ) -> None:
        raise NotImplementedError("draw() must be overridden")

    def valid_size(self, size:QSize) -> bool:
        return size.width() >= Grid.GRID_SPACING and size.height() >= Grid.GRID_SPACING

    def get_config_widget(self) -> Optional[QWidget]:
        return None

# endregion
