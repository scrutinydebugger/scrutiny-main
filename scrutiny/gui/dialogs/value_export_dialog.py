__all__ = ['ValueExportDialog']

import functools
import enum
import logging
from dataclasses import dataclass

from PySide6.QtGui import QCloseEvent, QContextMenuEvent
from PySide6.QtWidgets import (QDialog, QWidget, QProgressBar, QVBoxLayout, QFormLayout, QHBoxLayout, QMenu,
                               QTableWidget, QTableWidgetItem, QPushButton, QLabel, QHeaderView)
from PySide6.QtCore import Qt, QSize

from scrutiny import sdk
from scrutiny.gui.core.serializable_value_set import SerializableValueSet
from scrutiny.gui.core.watchable_registry import WatchableRegistry, ParsedFullyQualifiedName, WatcherNotFoundError, RegistryValueUpdate
from scrutiny.gui.core.server_manager import ServerManager
from scrutiny.gui.widgets.watchable_tree import get_watchable_icon
from scrutiny.gui.tools.invoker import invoke_later
from scrutiny.sdk.client import ScrutinyClient
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.gui.widgets import mixins as gui_mixins
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.tools.global_counters import global_i64_counter


@dataclass(slots=True)
class WatchableState:
    fqn: str
    value: Optional[Union[float, bool, int]]


class ValueExportDialog(QDialog):
    _watchable_registry: WatchableRegistry
    _logger: logging.Logger
    _watcher_id: str
    _state_dict: Dict[Union[str, int], WatchableState]
    _finished_gathering: bool
    _received_count: int
    _progress_bar: QProgressBar

    def __init__(self,
                 watchable_registry: WatchableRegistry,
                 export_fqn_list: List[str],
                 parent: Optional[QWidget] = None
                 ) -> None:
        super().__init__(parent)
        self._watchable_registry = watchable_registry
        self._logger = logging.getLogger(self.__class__.__name__)
        self._watcher_id = self.__class__.__name__ + str(global_i64_counter())
        self._finished_gathering = False
        self._received_count = 0

        self._watchable_registry.register_watcher(
            watcher_id=self._watcher_id,
            value_update_callback=self._value_update_callback,
            unwatch_callback=self._unwatch_callback,
        )

        self._state_dict = {}
        for fqn in export_fqn_list:
            registry_id = self._watchable_registry.watch_fqn(self._watcher_id, fqn)

            self._state_dict[registry_id] = WatchableState(
                fqn=fqn,
                value=None
            )

        self._progress_bar = QProgressBar(
            minimum=0,
            maximum=len(export_fqn_list),
            orientation=Qt.Orientation.Horizontal,
            textVisible=True
        )
        layout = QVBoxLayout(self)
        layout.addWidget(self._progress_bar)

        self.finished.connect(self._cleanup)

    def _value_update_callback(self, watcher_id: Union[str, int], updates: List[RegistryValueUpdate]) -> None:
        if self._finished_gathering:
            return

        to_unwatch_fqn: Set[str] = set()
        for update in updates:
            state = self._state_dict[update.registry_id]
            if state.value is None:
                self._received_count += 1
            state.value = update.sdk_update.value
            to_unwatch_fqn.add(state.fqn)

        self._progress_bar.setValue(self._received_count)

        for fqn in to_unwatch_fqn:
            self._watchable_registry.unwatch_fqn(self._watcher_id, fqn)

        print(f"{self._received_count}/{len(self._state_dict)}")

        if self._received_count >= len(self._state_dict):
            self._finished_gathering = True
            invoke_later(self.accept)

    def _unwatch_callback(self, watcher_id: Union[str, int], fqn: str, configuration: sdk.BriefWatchableConfiguration, registry_id: int) -> None:
        pass

    def _cleanup(self) -> None:
        print("cleanup")
        # for state in self._state_dict.values():
        #    print(state.fqn)
        with tools.SuppressException(WatcherNotFoundError):   # Suppress if not registered
            self._watchable_registry.unregister_watcher(self._watcher_id)

    def get_value_set(self) -> SerializableValueSet:
        if not self._finished_gathering:
            raise RuntimeError("No ValueSet available. Data did not finished gathering")

        value_set = SerializableValueSet()
        for state in self._state_dict.values():
            assert state.value is not None
            value_set.add(state.fqn, state.value)
        return value_set
