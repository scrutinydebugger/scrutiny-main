#    varlist_search.py
#        Variable List component search mechanisms and widgets
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import enum
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget, QLineEdit, QProgressBar, QVBoxLayout, QMenu
from PySide6.QtGui import QContextMenuEvent, QStandardItem
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from scrutiny.gui.components.globals.varlist.varlist_tree_model import VarListComponentTreeModel
from scrutiny.gui.widgets.watchable_tree import WatchableStandardItem, WatchableTreeWidget
from scrutiny.gui.core.watchable_registry import WatchableRegistry, WatchableRegistryIntermediateNode
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.core import path_tools

from scrutiny import sdk

from scrutiny.tools.typing import *


@dataclass(frozen=True, slots=True)
class SingleResult:
    fqn: str
    config: sdk.WatchableConfiguration


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    text: str

    def match(self, candidate: SingleResult) -> bool:
        return self.text in WatchableRegistry.FQN.parse(candidate.fqn).path


class SearchResultTreeModel(VarListComponentTreeModel):
    def get_watchable_extra_columns(self, fqn: str, watchable_config: Optional[sdk.WatchableConfiguration] = None) -> List[QStandardItem]:
        outlist: List[QStandardItem] = [QStandardItem(WatchableRegistry.FQN.parse(fqn).path)]

        if watchable_config is not None:
            typecol = QStandardItem(watchable_config.datatype.name)
            if watchable_config.enum is not None:
                enumcol = QStandardItem(watchable_config.enum.name)
                outlist += [typecol, enumcol]
            else:
                outlist += [typecol]

        for item in outlist:
            item.setEditable(False)

        return outlist

    def append_result(self, result: SingleResult) -> None:
        parsed = WatchableRegistry.FQN.parse(result.fqn)
        name_last_part = path_tools.make_segments(parsed.path)[-1]
        row = self.make_watchable_row(
            name=name_last_part,
            watchable_type=parsed.watchable_type,
            fqn=result.fqn,
            extra_columns=self.get_watchable_extra_columns(result.fqn, result.config),
            editable=False
        )
        self.appendRow(row)


class SearchResultTreeWidget(WatchableTreeWidget):

    class _Signals(QObject):
        reveal_in_varlist = Signal(str)

    _signals: _Signals

    def __init__(self, parent: QWidget, model: SearchResultTreeModel) -> None:
        super().__init__(parent, model)
        self.set_header_labels(['', 'Path', 'Type', 'Enum'])
        self.setDragDropMode(self.DragDropMode.DragOnly)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self._signals = self._Signals()

    @property
    def signals(self) -> _Signals:
        return self._signals

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        selected_indexes = self.selectedIndexes()
        nesting_col = self.model().nesting_col()
        # Assumes that the tree only contains watchable. No folder.
        selected_items = [cast(WatchableStandardItem, self.model().itemFromIndex(index))
                          for index in selected_indexes if index.column() == nesting_col]

        def copy_path_clipboard_slot() -> None:
            self.copy_path_clipboard(selected_items)

        def reveal_in_varlist_slot() -> None:
            if len(selected_items) != 1:
                return
            item = selected_items[0]
            self._signals.reveal_in_varlist.emit(item.fqn)

        reveal_in_varlist_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Eye), "Reveal in Variable List")
        reveal_in_varlist_action.setEnabled(len(selected_items) == 1)
        reveal_in_varlist_action.triggered.connect(reveal_in_varlist_slot)

        copy_path_clipboard_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Copy), "Copy path")
        copy_path_clipboard_action.setEnabled(False)
        copy_path_clipboard_action.triggered.connect(copy_path_clipboard_slot)
        for index in selected_indexes:
            item = self.model().itemFromIndex(index)
            if isinstance(item, WatchableStandardItem):  # At least one watchable, enough to enable
                copy_path_clipboard_action.setEnabled(True)
                break

        self.display_context_menu(context_menu, event.pos())
        event.accept()

    def model(self) -> SearchResultTreeModel:
        return cast(SearchResultTreeModel, super().model())


class PauseSearch:
    pass


SearchGeneratorType: TypeAlias = Generator[Union[SingleResult, PauseSearch], None, None]


class SearchResultWidget(QWidget):
    """A widget able to search the WatchableRegistry and display the search result"""
    _DEFAULT_SEARCH_ITERATION_BATCH_SIZE = 100

    class _InternalSignals(QObject):
        continue_consuming = Signal()
        """Signal used to resume search"""

    class _Signals(QObject):
        reveal_in_varlist = Signal(str)

    class State(enum.Enum):
        EMPTY = enum.auto()
        SEARCHING = enum.auto()
        STOPPED_INCOMPLETE = enum.auto()
        STOPPED_FINISHED = enum.auto()

    _watchable_registry: WatchableRegistry
    """The registry on which this widget performs searches on"""
    _tree: SearchResultTreeWidget
    """The TreeWidget used to display the element that has been found. Elements are shown on a single level, not in a tree."""
    _tree_model: SearchResultTreeModel
    """Model containing the element founds"""
    _state: State
    """State of the search"""
    _active_generator: Optional[SearchGeneratorType]
    """The generator object doing the search"""
    _watchable_processed_counter: int
    """A counter keeping track of how many watchable the search has processed"""
    _internal_signals: _InternalSignals
    """Signals used internally"""
    _signals: _Signals
    """Signals visible externally"""
    _search_batch_size: int
    """Number of watchable element to process before taking a pause and processing the event loop"""
    _pause_counter: int
    """Counts the number of pause taken while searching"""
    _progress_bar: QProgressBar
    """Progress bar showing the search progress"""

    def __init__(self, parent: QWidget, watchable_registry: WatchableRegistry, search_batch_size: int = _DEFAULT_SEARCH_ITERATION_BATCH_SIZE) -> None:
        super().__init__(parent)
        self._watchable_registry = watchable_registry
        self._tree_model = SearchResultTreeModel(self, watchable_registry=self._watchable_registry)
        self._tree = SearchResultTreeWidget(self, self._tree_model)
        self._search_batch_size = search_batch_size
        self._pause_counter = 0

        self._state = self.State.EMPTY
        self._watchable_processed_counter = 0
        self._internal_signals = self._InternalSignals()
        self._signals = self._Signals()

        self._progress_bar = QProgressBar(self)
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setOrientation(Qt.Orientation.Horizontal)
        self._progress_bar.setMaximumHeight(18)

        vlayout = QVBoxLayout(self)
        vlayout.addWidget(self._progress_bar)
        vlayout.addWidget(self._tree)
        vlayout.setContentsMargins(0, 0, 0, 0)

        self._internal_signals.continue_consuming.connect(self._consume_generator, Qt.ConnectionType.QueuedConnection)
        self._signals = self._Signals()
        self._tree.signals.reveal_in_varlist.connect(self._signals.reveal_in_varlist)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def set_search_batch_size(self, size: int) -> None:
        """Set the number of watchable element to process before taking a pause and processing the event loop"""
        self._search_batch_size = size

    def get_pause_counter(self) -> int:
        """Return the number of pause taken since start_search has been invoked"""
        return self._pause_counter

    def clear_content(self) -> None:
        """Clear the search results and set the internal state to a standby state"""
        self._tree_model.removeRows(0, self._tree_model.rowCount())
        self._state = self.State.EMPTY
        self._active_generator = None
        self._watchable_processed_counter = 0
        self._pause_counter = 0
        self._update_progress_bar()

    def _finish_search(self) -> None:
        """Indicates that a search is complete"""
        self._state = self.State.STOPPED_FINISHED
        self._update_progress_bar()

    def stop_search(self) -> None:
        """Stop a search"""
        if self._state == self.State.SEARCHING:
            self._state = self.State.STOPPED_INCOMPLETE
        self._update_progress_bar()

    def start_search(self, text: str) -> None:
        """Start a new search job"""
        self.clear_content()
        self._state = self.State.SEARCHING

        self._active_generator = self._create_search_generator(SearchCriteria(text))
        self._internal_signals.continue_consuming.emit()

    def _consume_generator(self) -> None:
        """Perform a part of the search job. Exit when the search is complete or if a pause must be taken after N watchables 
        have been evaluated, where N is the value of ``_search_batch_size``"""
        if self._active_generator is not None:
            try:
                while self._state == self.State.SEARCHING:
                    item = next(self._active_generator)
                    if isinstance(item, PauseSearch):
                        self._update_progress_bar()
                        self._pause_counter += 1
                        self._internal_signals.continue_consuming.emit()
                        return
                    else:
                        self._tree_model.append_result(item)
            except StopIteration:
                self._finish_search()

    def _create_search_generator(self, criteria: SearchCriteria) -> SearchGeneratorType:
        """Entry point to start the search process. Create a generator that yield either SearchResult or Pause"""
        self._watchable_processed_counter = 0
        self._pause_counter = 0
        for watchable_type in [sdk.WatchableType.Alias, sdk.WatchableType.RuntimePublishedValue, sdk.WatchableType.Variable]:
            root = self._watchable_registry.read(watchable_type, '/')
            if root is None:
                continue
            assert isinstance(root, WatchableRegistryIntermediateNode)

            yield from self._iterate_node_recursive(watchable_type, root, '', criteria)

    def _iterate_node_recursive(self,
                                watchable_type: sdk.WatchableType,
                                node: WatchableRegistryIntermediateNode,
                                path: str, criteria: SearchCriteria
                                ) -> SearchGeneratorType:
        """Internal generator that crawl recursively the watchable registry"""
        for node_name, watchable_node in node.watchables.items():
            self._watchable_processed_counter += 1
            if (self._watchable_processed_counter % self._search_batch_size) == 0:
                yield PauseSearch()

            candidate = SingleResult(
                fqn=WatchableRegistry.FQN.make(watchable_type, path + '/' + node_name),
                config=watchable_node.configuration
            )

            if criteria.match(candidate):
                yield candidate

        for subtree_name in node.subtree:
            subtree_path = path + '/' + subtree_name
            subtree_node = self._watchable_registry.read(watchable_type, subtree_path)
            if subtree_node is None:
                return  # The registry got cleared most likely
            assert isinstance(subtree_node, WatchableRegistryIntermediateNode)
            yield from self._iterate_node_recursive(watchable_type, subtree_node, subtree_path, criteria)

    def _update_progress_bar(self) -> None:
        delta = self._progress_bar.maximum() - self._progress_bar.minimum()
        v = self.completion() * delta + self._progress_bar.minimum()
        self._progress_bar.setValue(int(round(v)))

    def searching(self) -> bool:
        """Returns ``True`` if a search is in progress"""
        return self._state == self.State.SEARCHING

    def finished(self) -> bool:
        """Returns ``True`` if the search has finished without being stopped"""
        return self._state == self.State.STOPPED_FINISHED

    def count_found(self) -> int:
        """Returns the number of element found that matched the search criteria"""
        return self._tree_model.rowCount()

    def completion(self) -> float:
        """Returns a value between 0 and 1 indicating the completion progress"""
        stats = self._watchable_registry.get_stats()
        total_element = stats.rpv_count + stats.alias_count + stats.var_count
        if total_element == 0:
            return 1

        completion = self._watchable_processed_counter / total_element
        return max(min(completion, 1), 0)

    def iterate_found_fqns(self) -> Generator[str, None, None]:
        """Iterate the list of watchable found during a search. Returns the Fully Qualified Name"""
        for i in range(self._tree_model.rowCount()):
            item = cast(WatchableStandardItem, self._tree_model.item(i, self._tree_model.nesting_col()))
            yield item.fqn


class SearchControlWidget(QWidget):

    class _Signals(QObject):
        search_string_updated = Signal(str)
        search_string_cleared = Signal()

    _txt_search: QLineEdit
    _commit_delay_ms: int
    _timer_commit: QTimer
    _last_emitted_text: str
    _signals: _Signals

    def __init__(self, parent: QWidget, commit_delay_ms: int = 500) -> None:
        super().__init__(parent)
        self._last_emitted_text = ""
        self._commit_delay_ms = commit_delay_ms
        self._signals = self._Signals()
        self._timer_commit = QTimer(self)
        self._timer_commit.setInterval(commit_delay_ms)
        self._timer_commit.setSingleShot(True)
        self._timer_commit.timeout.connect(self._timer_commit_timeout_slot)

        self._txt_search = QLineEdit(self)
        self._txt_search.setPlaceholderText("Search")
        self._txt_search.textChanged.connect(self._txt_changed_slot)
        self._txt_search.editingFinished.connect(self._commit_text)

        vlayout = QVBoxLayout(self)
        vlayout.addWidget(self._txt_search)
        vlayout.setAlignment(Qt.AlignmentFlag.AlignTop)
        vlayout.setContentsMargins(0, 0, 0, 0)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def _txt_changed_slot(self, txt: str) -> None:
        self._timer_commit.start()

    def _commit_text(self) -> None:
        text = self._txt_search.text()
        if text != self._last_emitted_text:
            if text == "":
                self._signals.search_string_cleared.emit()
            else:
                self._signals.search_string_updated.emit(text)
            self._last_emitted_text = text

    def _timer_commit_timeout_slot(self) -> None:
        self._commit_text()

    def get_search_string(self) -> str:
        return self._txt_search.text()
