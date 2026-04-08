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

from PySide6.QtWidgets import QWidget, QFormLayout, QGraphicsItem, QStyleOptionGraphicsItem
from PySide6.QtGui import QPainter
from PySide6.QtCore import QSize, QRectF

from scrutiny import sdk
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.core.watchable_registry import WatcherIdType, RegistryValueUpdate
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.tools.typing import *
from scrutiny.tools.global_counters import global_i64_counter

WatchableSlotValidator: TypeAlias = Callable[[sdk.BriefWatchableConfiguration], bool]


@dataclass(slots=True, init=False)
class WatchableSlot:
    name: str
    display_name: str
    validator: Optional[WatchableSlotValidator]
    drop_line_edit: WatchableLineEdit
    watcher_id: str
    last_value_received: Optional[Union[float, int, bool]]

    def __init__(self, name: str, display_name: str, validator: Optional[WatchableSlotValidator] = None) -> None:
        self.name = name
        self.display_name = display_name
        self.validator = validator
        self.drop_line_edit = WatchableLineEdit()
        self.drop_line_edit.set_text_mode_enabled(False)
        self.watcher_id = f'{name}{global_i64_counter()}'
        self.last_value_received = None

    def validate(self, watchable_config: sdk.BriefWatchableConfiguration) -> bool:
        if self.validator is not None:
            return self.validator(watchable_config)
        return True


class BaseHMIWidget(QGraphicsItem):
    MAX_DRAW_RATE = 15
    MAX_DRAW_RATE_NANOSEC = int(round((1 / MAX_DRAW_RATE) * 1e9))

    _wslots: List[WatchableSlot]
    _app_interface: AbstractComponentAppInterface
    _need_redraw: bool
    _pending_redraw: bool
    _last_draw_timestamp_ns: int
    _parent_constructor_called: bool
    _logger: logging.Logger

    def __init__(self, app_interface: AbstractComponentAppInterface) -> None:
        super().__init__()
        self._wslots = []
        self._app_interface = app_interface
        self._need_redraw = False
        self._last_draw_timestamp_ns = time.perf_counter_ns()
        self._parent_constructor_called = True
        self._logger = logging.getLogger(self.__class__.__name__)

    def declare_watchable_slot(self, name: str, display_name: str, validator: Optional[WatchableSlotValidator]) -> None:
        if not (hasattr(self, '_parent_constructor_called')):
            raise RuntimeError("Parent constructor not called")
        used_names = set([wslot.name for wslot in self._wslots])
        if name in used_names:
            raise ValueError(f"Duplicate watchable slot with name {name}")

        wslot = WatchableSlot(
            name=name,
            display_name=display_name,
            validator=validator
        )

        self._wslots.append(wslot)

        val_update_lost = functools.partial(self._val_update_callback, wslot)
        self._app_interface.watchable_registry.register_watcher(wslot.watcher_id, val_update_lost, self._unwatch_callback)

        partial_slot = functools.partial(self._wslot_configured_slot, wslot)
        wslot.drop_line_edit.signals.watchable_dropped.connect(partial_slot)

    def destroy(self) -> None:
        for wslots in self._wslots:
            self._app_interface.watchable_registry.unregister_watcher(wslots.watcher_id)    # Will unwatch all
        self._wslots.clear()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, 128, 64)


# region Private

    def _val_update_callback(self, wslot: WatchableSlot, watcher_id: WatcherIdType, updates: List[RegistryValueUpdate]) -> None:
        wslot.last_value_received = updates[-1].sdk_update.value
        self._need_redraw = True
        invoke_later(self._redraw_if_allowed)

    def _unwatch_callback(self, watcher_id: Union[str, int], server_path: str, watchable_config: sdk.BriefWatchableConfiguration, registry_id: int) -> None:
        pass

    def _wslot_configured_slot(self, wslot: WatchableSlot, fqn: str) -> None:
        self._app_interface.watchable_registry.watch_fqn(wslot.watcher_id, fqn)

    def _get_slot_by_name(self, name: str) -> WatchableSlot:
        for wslot in self._wslots:
            if wslot.name == name:
                return wslot

        raise ValueError(f"No watchable slot with name {name}")

    def _make_slot_config_widget(self) -> QWidget:
        container = QWidget()
        container_layout = QFormLayout(container)

        for wslot in self._wslots:
            container_layout.addRow(wslot.display_name, wslot.drop_line_edit)

        return container

    def _all_wslots_filled(self) -> bool:
        for wslot in self._wslots:
            watchable = wslot.drop_line_edit.get_watchable()
            if watchable is None:
                return False

            node = self._app_interface.watchable_registry.get_watchable_node_fqn(watchable.fqn)
            if node is None:
                return False

        return True

    def _redraw_later(self) -> None:
        def callback() -> None:
            self._pending_redraw = False
            if self._need_redraw:
                self._logger.debug("later_finished")
                self._redraw_if_allowed()

        if not self._pending_redraw:
            self._pending_redraw = True
            self._logger.debug("later")
            invoke_later(callback, int(self.MAX_DRAW_RATE_NANOSEC // 1e6))    # Retry later if still needed

    def _redraw_if_allowed(self) -> None:
        updated = False

        dt_ns = time.perf_counter_ns() - self._last_draw_timestamp_ns
        if dt_ns > self.MAX_DRAW_RATE_NANOSEC:
            self.update()
            updated = True
        else:
            self._logger.debug("wait")

        if not updated:
            self._redraw_later()

# endregion

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        self._logger.debug("paint")
        self._need_redraw = False
        self._pending_redraw = False

        configured = self._all_wslots_filled()
        values = {wslot.name: wslot.last_value_received for wslot in self._wslots}

        self.draw(configured, values, QSize(128, 32), painter)
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
        pass

# endregion
