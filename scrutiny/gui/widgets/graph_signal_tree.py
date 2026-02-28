#    graph_signal_tree.py
#        The widget that allow the user to define a graph axis/signals using a 2 level tree.
#        First level for axes, Second level for watchables
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'AxisStandardItem',
    'ChartSeriesWatchableStandardItem',
    'AxisContent',
    'GraphSignalModel',
    'GraphSignalTree',
    'ValueItems'
]

from dataclasses import dataclass

from PySide6.QtWidgets import QAbstractItemDelegate, QWidget, QMenu
from PySide6.QtGui import (QStandardItem, QDropEvent, QDragEnterEvent, QDragMoveEvent,
                           QContextMenuEvent, QKeyEvent, QPixmap, QPalette)
from PySide6.QtCore import QMimeData, QModelIndex, Qt, QPersistentModelIndex, QItemSelection, QObject, Signal, QSortFilterProxyModel
from PySide6.QtCharts import QLineSeries, QAbstractSeries, QValueAxis

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData, WatchableListDescriptor, SingleWatchableDescriptor
from scrutiny.gui.widgets.watchable_tree import WatchableStandardItem, get_watchable_icon
from scrutiny.gui.widgets.base_tree import BaseTreeModel, BaseTreeView, SerializableItemIndexDescriptor
from scrutiny.gui.widgets.chart_range_edit_dialog import ChartRangeEditDialog
from scrutiny import tools

from scrutiny.tools.typing import *


class AxisStandardItem(QStandardItem):
    _chart_axis: Optional[QValueAxis]

    def __init__(self, name: str):
        axis_icon = scrutiny_get_theme().load_tiny_icon(assets.Icons.GraphAxis)
        super().__init__(axis_icon, name)
        self.setDropEnabled(True)
        self.setDragEnabled(False)
        self._chart_axis = None

    def attach_axis(self, axis: QValueAxis) -> None:
        self._chart_axis = axis

    def detach_axis(self) -> None:
        self._chart_axis = None

    def axis_attached(self) -> bool:
        return self._chart_axis is not None

    def axis(self) -> QValueAxis:
        assert self._chart_axis is not None
        return self._chart_axis


class ChartSeriesWatchableStandardItem(WatchableStandardItem):
    _chart_series: Optional[QLineSeries] = None

    @tools.copy_type(WatchableStandardItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._chart_series = None

    def _assert_series_set(self) -> None:
        if self._chart_series is None:
            raise RuntimeError("A series must be attached first")

    def attach_series(self, series: QLineSeries) -> None:
        if not isinstance(series, QAbstractSeries):
            raise ValueError("A chart series must be given")
        self._chart_series = series
        self.change_icon_to_series_color()

    def detach_series(self) -> None:
        self._assert_series_set()
        self._chart_series = None
        self.reload_watchable_icon()

    def series_attached(self) -> bool:
        return self._chart_series is not None

    def series(self) -> QLineSeries:
        self._assert_series_set()
        assert self._chart_series is not None   # for mypy
        return self._chart_series

    def change_icon_to_series_color(self) -> None:
        LINE_WIDTH = 12
        LINE_HEIGHT = 5
        color = self.series().color()
        new_pix = QPixmap(LINE_WIDTH, LINE_HEIGHT)
        new_pix.fill(color)
        self.setIcon(new_pix)

    def reload_watchable_icon(self) -> None:
        self.setIcon(get_watchable_icon(self.watchable_type))

    def hide_series(self) -> None:
        series = self.series()
        series.hide()
        font = self.font()
        font.setStrikeOut(True)
        self.setFont(font)

    def show_series(self) -> None:
        series = self.series()
        series.show()
        font = self.font()
        font.setStrikeOut(False)
        self.setFont(font)

    def series_visible(self) -> bool:
        series = self.series()
        return series.isVisible()


@dataclass(slots=True)
class AxisContent:
    axis_name: str
    axis_item: AxisStandardItem
    signal_items: List[ChartSeriesWatchableStandardItem]


@dataclass(slots=True)
class ValueItems:
    """Contains all the value Tree items attached to a data series"""
    value1: QStandardItem
    value2: QStandardItem
    delta: QStandardItem


class GraphSignalModel(BaseTreeModel):
    _watchable_registry: WatchableRegistry
    _available_palette: QPalette
    _unavailable_palette: QPalette
    _globally_uneditable: bool

    def __init__(self,
                 parent: QWidget,
                 watchable_registry: WatchableRegistry,
                 available_palette: Optional[QPalette] = None,
                 unavailable_palette: Optional[QPalette] = None
                 ) -> None:
        super().__init__(parent, nesting_col=self.axis_col())
        self._watchable_registry = watchable_registry
        self._globally_uneditable = False
        self.setColumnCount(2)

        if available_palette is not None:
            self._available_palette = available_palette
        else:
            self._available_palette = QPalette()
            self._available_palette.setCurrentColorGroup(QPalette.ColorGroup.Active)

        if unavailable_palette is not None:
            self._unavailable_palette = unavailable_palette
        else:
            self._unavailable_palette = QPalette()
            self._unavailable_palette.setCurrentColorGroup(QPalette.ColorGroup.Disabled)

    def make_axis_row(self, axis_name: str) -> List[AxisStandardItem]:
        axis_item = AxisStandardItem(axis_name)
        axis_item.setEditable(True)
        if self._globally_uneditable:
            axis_item.setEditable(False)

        return [axis_item]

    def axis_col(self) -> int:
        return 0

    def watchable_col(self) -> int:
        return 0

    def value_col(self) -> int:
        return 1

    def _make_watchable_detail_data_row(self, label: str) -> List[QStandardItem]:
        label_item = QStandardItem()
        label_item.setText(label)
        value_item = QStandardItem()
        label_item.setEditable(False)
        value_item.setEditable(False)
        return [label_item, value_item]

    def make_watchable_item_row(self, watchable_item: ChartSeriesWatchableStandardItem) -> List[QStandardItem]:
        watchable_item.setEditable(True)
        if self._globally_uneditable:
            watchable_item.setEditable(False)
        watchable_item.setDragEnabled(True)

        watchable_item.appendRow(self._make_watchable_detail_data_row("y2"))
        watchable_item.appendRow(self._make_watchable_detail_data_row("Δy"))

        value_item = QStandardItem()
        value_item.setEditable(False)
        return [watchable_item, value_item]

    def get_watchable_row_from_dragged_watchable_desc(self, watchable_desc: SingleWatchableDescriptor) -> List[QStandardItem]:
        watchable_item = ChartSeriesWatchableStandardItem.from_drag_watchable_descriptor(watchable_desc)
        return self.make_watchable_item_row(watchable_item)

    def _validate_drag_data(self, drag_data: Optional[ScrutinyDragData], action: Qt.DropAction) -> bool:

        if drag_data is None:
            return False

        if drag_data.type != ScrutinyDragData.DataType.WatchableList:
            return False

        if action not in [Qt.DropAction.CopyAction, Qt.DropAction.MoveAction]:
            return False

        if action == Qt.DropAction.CopyAction:
            if drag_data.data_copy is None:
                return False

        if action == Qt.DropAction.MoveAction:
            if drag_data.data_move is None:
                return False

        return True

    def _get_last_axis_or_create(self) -> AxisStandardItem:
        if self.rowCount() == 0:
            self.add_axis("Axis 1")

        axis_item = self.item(self.rowCount() - 1, self.axis_col())
        assert isinstance(axis_item, AxisStandardItem)
        return axis_item

    def add_axis(self, name: str) -> AxisStandardItem:
        row = self.make_axis_row(name)
        self.appendRow(row)
        return row[0]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        item_list: List[WatchableStandardItem] = []
        for index in indexes:
            if index.isValid() and index.column() == self.watchable_col():
                item = self.itemFromIndex(index)
                if isinstance(item, WatchableStandardItem):
                    item_list.append(item)

        self.sort_items_by_path(item_list, top_to_bottom=True)
        item_descriptors: List[SingleWatchableDescriptor] = []
        for item in item_list:
            item_descriptors.append(SingleWatchableDescriptor(
                fqn=item.fqn,
                text=item.text()
            ))
        move_data = [self.make_serializable_item_index_descriptor(item) for item in item_list]
        drag_data = WatchableListDescriptor(item_descriptors).to_drag_data(move_data)

        mime_data = drag_data.to_mime()
        assert mime_data is not None
        return mime_data

    def canDropMimeData(self, mime_data: QMimeData,
                        action: Qt.DropAction,
                        row_index: int,
                        column_index: int,
                        parent: Union[QModelIndex, QPersistentModelIndex]
                        ) -> bool:

        drag_data = ScrutinyDragData.from_mime(mime_data)

        if not self._validate_drag_data(drag_data, action):
            return False

        if parent.isValid():
            parent_item = self.itemFromIndex(parent)
            if not isinstance(parent_item, AxisStandardItem):
                return False

        return True

    def dropMimeData(self,
                     mime_data: QMimeData,
                     action: Qt.DropAction,
                     row_index: int,
                     column_index: int,
                     parent: Union[QModelIndex, QPersistentModelIndex]
                     ) -> bool:
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if not self._validate_drag_data(drag_data, action):
            return False
        assert drag_data is not None

        parent_item = self.itemFromIndex(parent)
        del parent
        last_axis = self._get_last_axis_or_create()

        if parent_item is None:
            parent_item = last_axis
            row_index = -1

        if not isinstance(parent_item, AxisStandardItem):
            return False

        if action == Qt.DropAction.CopyAction:
            watchable_list = WatchableListDescriptor.from_drag_data(drag_data)
            if watchable_list is None:
                return False

            for watchable_desc in watchable_list.data:
                row = self.get_watchable_row_from_dragged_watchable_desc(watchable_desc)
                if row_index == -1:
                    parent_item.appendRow(row)
                else:
                    parent_item.insertRow(row_index, row)

                series_item = row[self.watchable_col()]
                assert isinstance(series_item, ChartSeriesWatchableStandardItem)
                self.update_availability(series_item)

        elif action == Qt.DropAction.MoveAction:
            self.handle_internal_move(parent_item.index(), row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))
        return True

    def get_signals(self) -> List[AxisContent]:
        outlist: List[AxisContent] = []

        for i in range(self.rowCount()):
            axis_item = self.item(i, self.axis_col())
            assert isinstance(axis_item, AxisStandardItem)

            if axis_item.rowCount() == 0:
                continue
            axis = AxisContent(axis_name=axis_item.text(), axis_item=axis_item, signal_items=[])

            for j in range(axis_item.rowCount()):
                watchable_item = axis_item.child(j, self.watchable_col())
                assert isinstance(watchable_item, ChartSeriesWatchableStandardItem)
                axis.signal_items.append(watchable_item)
            outlist.append(axis)
        return outlist

    def get_value_item_by_attached_series(self) -> List[Tuple[QLineSeries, ValueItems]]:
        outlist: List[Tuple[QLineSeries, ValueItems]] = []
        for i in range(self.rowCount()):
            axis_item = self.item(i, self.axis_col())
            for j in range(axis_item.rowCount()):
                watchable_item = axis_item.child(j, self.watchable_col())
                assert isinstance(watchable_item, ChartSeriesWatchableStandardItem)
                value2_item = watchable_item.child(0, self.value_col())
                delta_item = watchable_item.child(1, self.value_col())

                value_items = ValueItems(
                    value1=axis_item.child(j, self.value_col()),
                    value2=value2_item,
                    delta=delta_item
                )
                outlist.append((watchable_item.series(), value_items))
        return outlist

    def reload_original_icons(self) -> None:
        for axis_index in range(self.rowCount()):
            axis = self.item(axis_index, self.axis_col())
            for signal_index in range(axis.rowCount()):
                signal_item = axis.child(signal_index, self.watchable_col())
                assert isinstance(signal_item, ChartSeriesWatchableStandardItem)
                signal_item.reload_watchable_icon()

    def update_availability(self, series_item: ChartSeriesWatchableStandardItem) -> None:
        """Change the availability of an item based on its availability in the registry.
        When the watchable referred by an element is not in the registry, becomes "unavailable" (grayed out).
        """
        if self._watchable_registry.is_watchable_fqn(series_item.fqn):
            self.set_available(series_item)
        else:
            self.set_unavailable(series_item)

    def update_all_availabilities(self) -> None:
        """Change the availability of all item based on their availability in the registry.
        When the watchable referred by an element is not in the registry, becomes "unavailable" (grayed out).
        """
        for i in range(self.rowCount()):
            axis = self.item(i, self.axis_col())
            for j in range(axis.rowCount()):
                series_item = axis.child(j, self.watchable_col())
                assert isinstance(series_item, ChartSeriesWatchableStandardItem)
                self.update_availability(series_item)

    def set_all_available(self) -> None:
        for i in range(self.rowCount()):
            axis = self.item(i, self.axis_col())
            for j in range(axis.rowCount()):
                series_item = axis.child(j, self.watchable_col())
                assert isinstance(series_item, ChartSeriesWatchableStandardItem)
                self.set_available(series_item)

    def has_unavailable_signals(self) -> bool:
        """Return True if one signal refers to an unavailable watchable in the registry"""
        for i in range(self.rowCount()):
            axis = self.item(i, self.axis_col())
            for j in range(axis.rowCount()):
                signal_item = axis.child(j, self.watchable_col())
                assert isinstance(signal_item, ChartSeriesWatchableStandardItem)

                if not self._watchable_registry.is_watchable_fqn(signal_item.fqn):
                    return True
        return False

    def set_unavailable(self, arg_item: QStandardItem) -> None:
        """Make an item in the tree unavailable (grayed out)"""
        background_color = self._unavailable_palette.color(QPalette.ColorRole.Base)
        forground_color = self._unavailable_palette.color(QPalette.ColorRole.Text)
        for i in range(self.columnCount()):
            item = self.itemFromIndex(arg_item.index().siblingAtColumn(i))
            if item is not None:
                item.setBackground(background_color)
                item.setForeground(forground_color)

    def set_available(self, arg_item: QStandardItem) -> None:
        """Make an item in the tree available (normal color)"""
        background_color = self._available_palette.color(QPalette.ColorRole.Base)
        forground_color = self._available_palette.color(QPalette.ColorRole.Text)
        for i in range(self.columnCount()):
            item = self.itemFromIndex(arg_item.index().siblingAtColumn(i))
            if item is not None:
                item.setBackground(background_color)
                item.setForeground(forground_color)

    def get_all_value_items(self) -> List[ValueItems]:
        outlist: List[ValueItems] = []
        for i in range(self.rowCount()):
            axis_item = self.item(i, self.axis_col())
            for j in range(axis_item.rowCount()):
                watchable_item = axis_item.child(j, self.watchable_col())
                assert isinstance(watchable_item, ChartSeriesWatchableStandardItem)
                value2_item = watchable_item.child(0, self.value_col())
                delta_item = watchable_item.child(1, self.value_col())
                value_items = ValueItems(
                    value1=axis_item.child(j, self.value_col()),
                    value2=value2_item,
                    delta=delta_item
                )
                outlist.append(value_items)
        return outlist

    def _update_editable_field(self) -> None:
        editable = not self._globally_uneditable
        for i in range(self.rowCount()):
            axis_item = self.item(i, self.axis_col())
            axis_item.setEditable(editable)
            for j in range(axis_item.rowCount()):
                axis_item.child(j, self.watchable_col()).setEditable(editable)

    def disallow_item_edition(self) -> None:
        self._globally_uneditable = True
        self._update_editable_field()

    def allow_item_edition(self) -> None:
        self._globally_uneditable = False
        self._update_editable_field()

    def detach_all_chart_elements(self) -> None:
        """Detach chart axes from axis item and detach data series from watchable rows"""
        for i in range(self.rowCount()):
            axis_item = cast(AxisStandardItem, self.item(i, self.axis_col()))

            for j in range(axis_item.rowCount()):
                signal_item = cast(ChartSeriesWatchableStandardItem, axis_item.child(j, self.watchable_col()))
                if signal_item.series_attached():
                    signal_item.detach_series()

            if axis_item.axis_attached():
                axis_item.detach_axis()


class GraphSignalDetailFilterProxy(QSortFilterProxyModel):

    _show_details: bool

    @tools.copy_type(QSortFilterProxyModel.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._show_details = False

    def sourceModel(self) -> GraphSignalModel:
        return cast(GraphSignalModel, super().sourceModel())

    def filterAcceptsRow(self, source_row: int, source_parent: Union[QModelIndex, QPersistentModelIndex]) -> bool:
        parent_item = self.sourceModel().itemFromIndex(source_parent)
        if parent_item is not None:
            if isinstance(parent_item, WatchableStandardItem):
                return self._show_details
        return super().filterAcceptsRow(source_row, source_parent)

    def hide_details_row(self) -> None:
        self._show_details = False
        self.invalidate()

    def show_details_row(self) -> None:
        self._show_details = True
        self.invalidate()


class GraphSignalTree(BaseTreeView):

    class _Signals(QObject):
        selection_changed = Signal()
        content_changed = Signal()

    _locked: bool
    _signals: _Signals
    _model: GraphSignalModel
    _detail_filter_proxy: GraphSignalDetailFilterProxy

    def real_model_selected_indexes(self) -> List[QModelIndex]:
        # FIXME: Sometime raise an error? When deleting elements in the tree
        mapped = [self._detail_filter_proxy.mapToSource(index) for index in self.selectedIndexes() if index.isValid()]
        return [index for index in mapped if index.isValid()]

    def real_model(self) -> GraphSignalModel:
        return self._model

    def __init__(self, parent: QWidget, watchable_registry: WatchableRegistry) -> None:
        super().__init__(parent)
        self._locked = False
        self._signals = self._Signals()

        self._model = GraphSignalModel(self, watchable_registry)
        self._detail_filter_proxy = GraphSignalDetailFilterProxy()
        self._detail_filter_proxy.setSourceModel(self._model)
        self.setModel(self._detail_filter_proxy)
        self._model.add_axis("Axis 1")
        self.setUniformRowHeights(True)   # Documentation says it helps performance
        self.setAnimated(False)
        self.header().setStretchLastSection(True)
        self.header().setVisible(False)
        self.setDragEnabled(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def update_all_availabilities(self) -> None:
        self._model.update_all_availabilities()

    def set_all_available(self) -> None:
        self._model.set_all_available()

    def has_unavailable_signals(self) -> bool:
        return self._model.has_unavailable_signals()

    def rowsInserted(self, parent: Union[QModelIndex, QPersistentModelIndex], start: int, end: int) -> None:
        if parent.isValid():
            self.expand(parent)
        super().rowsInserted(parent, start, end)
        self.resizeColumnToContents(0)
        self._signals.content_changed.emit()

    def rowsRemoved(self, parent: Union[QModelIndex, QPersistentModelIndex], first: int, last: int) -> None:
        super().rowsRemoved(parent, first, last)
        self.resizeColumnToContents(0)
        self._signals.content_changed.emit()

    def _set_drag_and_drop_action(self, event: Union[QDragEnterEvent, QDragMoveEvent, QDropEvent]) -> None:
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
        else:
            event.setDropAction(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._set_drag_and_drop_action(event)
        super().dragEnterEvent(event)
        event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dropEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        selected_indexes_no_nested_unordered = self._model.remove_nested_indexes_unordered(self.real_model_selected_indexes())
        nesting_col = self._model.nesting_col()
        selected_items_no_nested_unordered = [self._model.itemFromIndex(index)
                                              for index in selected_indexes_no_nested_unordered if index.column() == nesting_col]
        # Filter None. Should not happen, but be safe
        selected_items_no_nested_unordered = [item for item in selected_items_no_nested_unordered if item is not None]

        def new_axis_action_slot() -> None:
            self._model.appendRow(self._model.make_axis_row("New Axis"))

        def remove_action_slot() -> None:
            for item in selected_items_no_nested_unordered:
                self._model.removeRow(item.row(), item.index().parent())

        new_axis_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.GraphAxis), "New Axis")
        new_axis_action.triggered.connect(new_axis_action_slot)

        indexes = self.real_model_selected_indexes()

        items = [self._model.itemFromIndex(index) for index in indexes if index.isValid()]
        signals_with_series = [item for item in items if isinstance(item, ChartSeriesWatchableStandardItem) and item.series_attached()]

        if len(signals_with_series) > 0:
            all_visible = True
            for item in signals_with_series:
                if not item.series_visible():
                    all_visible = False

            if all_visible:
                show_hide_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.EyeBar), "Hide")

                def hide_action_slot() -> None:
                    for item in signals_with_series:
                        item.hide_series()
                show_hide_action.triggered.connect(hide_action_slot)
            else:
                show_hide_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Eye), "Show")

                def show_action_slot() -> None:
                    for item in signals_with_series:
                        item.show_series()
                show_hide_action.triggered.connect(show_action_slot)

        remove_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")
        remove_action.setEnabled(len(selected_items_no_nested_unordered) > 0)
        remove_action.triggered.connect(remove_action_slot)
        axis_item: Optional[AxisStandardItem] = None
        if len(selected_items_no_nested_unordered) == 1:
            if isinstance(selected_items_no_nested_unordered[0], AxisStandardItem):
                axis_item = selected_items_no_nested_unordered[0]

        def edit_range_action_slot() -> None:
            if axis_item is not None:
                dialog = ChartRangeEditDialog(axis_item.axis(), self)
                dialog.show()

        edit_range_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.YRange), "Edit range")
        edit_range_action.triggered.connect(edit_range_action_slot)
        edit_range_action.setVisible(axis_item is not None)

        if self._locked:
            new_axis_action.setDisabled(True)
            remove_action.setDisabled(True)

        edit_range_action.setEnabled(axis_item is not None and axis_item.axis_attached())

        context_menu.popup(self.mapToGlobal(event.pos()))
        event.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete and not self._locked:
            # Avoid errors when parent is deleted before children
            indexes_without_nested_values = self._model.remove_nested_indexes_unordered(self.real_model_selected_indexes())
            items = [self._model.itemFromIndex(index) for index in indexes_without_nested_values]
            for item in items:
                if item is not None:
                    self._model.removeRow(item.row(), item.index().parent())
        else:
            return super().keyPressEvent(event)

    def get_signals(self) -> List[AxisContent]:
        return self._model.get_signals()

    def get_selected_axes(self, include_if_signal_is_selected: bool = True) -> List[AxisStandardItem]:
        selected_items = [self._model.itemFromIndex(index) for index in self.real_model_selected_indexes() if index.isValid()]
        selected_axes: Dict[int, AxisStandardItem] = {}
        for item in selected_items:
            if item is None:
                continue    # Should not happen since we checked Valid(). Better safe than sorry
            if isinstance(item, AxisStandardItem):
                selected_axes[id(item)] = item
            elif include_if_signal_is_selected:
                parent = item.parent()
                if isinstance(parent, AxisStandardItem):
                    selected_axes[id(parent)] = parent

        return list(selected_axes.values())

    def closeEditor(self, editor: QWidget, hint: QAbstractItemDelegate.EndEditHint) -> None:
        self.resizeColumnToContents(0)
        return super().closeEditor(editor, hint)

    def lock(self) -> None:
        self.setDragDropMode(self.DragDropMode.DragOnly)
        self._locked = True
        self._model.disallow_item_edition()

    def unlock(self) -> None:
        self.setDragDropMode(self.DragDropMode.DragDrop)
        self._locked = False
        self._model.allow_item_edition()

    def reload_original_icons(self) -> None:
        self._model.reload_original_icons()

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        super().selectionChanged(selected, deselected)
        self._signals.selection_changed.emit()

    def get_value_item_by_attached_series(self) -> List[Tuple[QLineSeries, ValueItems]]:
        return self._model.get_value_item_by_attached_series()

    def get_all_value_items(self) -> List[ValueItems]:
        return self._model.get_all_value_items()

    def enable_cursor2_rows(self) -> None:
        self._detail_filter_proxy.show_details_row()

    def disable_cursor2_rows(self) -> None:
        self._detail_filter_proxy.hide_details_row()

    def detach_all_chart_elements(self) -> None:
        self._model.detach_all_chart_elements()
