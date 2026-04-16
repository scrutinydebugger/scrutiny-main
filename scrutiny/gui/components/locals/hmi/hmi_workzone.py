#    hmi_workzone.py
#        A workzone where HMI widgets lives visually. Can be shown in display mode or dragged/edited
#        in Edit mode
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['HMIWorkZone']

import enum
from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt, Signal, QRect, QPoint, QObject, QMimeData, QSize, QPointF, QSizeF
from PySide6.QtWidgets import QGraphicsView, QGraphicsItem, QRubberBand, QGraphicsScene, QStyleOptionGraphicsItem, QWidget
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QMouseEvent, QPainter, QResizeEvent

from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.components.locals.hmi.hmi_library import HMILibrary
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, HandlePosition
from scrutiny.gui.components.locals.hmi.hmi_edit_grid import HMIEditGrid
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme


from scrutiny import tools
from scrutiny.tools.typing import *

RESIZE_CURSOR_MAP = {
    HandlePosition.MIDLEFT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.MIDRIGHT: Qt.CursorShape.SizeHorCursor,
    HandlePosition.TOPMID: Qt.CursorShape.SizeVerCursor,
    HandlePosition.BOTTOMMID: Qt.CursorShape.SizeVerCursor,
    HandlePosition.TOPRIGHT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.BOTTOMLEFT: Qt.CursorShape.SizeBDiagCursor,
    HandlePosition.TOPLEFT: Qt.CursorShape.SizeFDiagCursor,
    HandlePosition.BOTTOMRIGHT: Qt.CursorShape.SizeFDiagCursor,
}


@dataclass
class WidgetMouseEditData:
    class Action(enum.Enum):
        Move = enum.auto()
        Resize = enum.auto()

    @dataclass
    class ResizeData:
        original_pos: QPoint
        original_size: QSize
        handle_clicked: HandlePosition
        widget: BaseHMIWidget

    @dataclass
    class MoveData:
        cursor_start: QPoint
        widget_offset_to_bounding_rect: Dict[int, QPoint]
        selection_bouding_rect: QRect

    action: Action
    resize_data: Optional[ResizeData] = None
    move_data: Optional[MoveData] = None


class DropPlaceholder(QGraphicsItem):
    _size: QSize

    @tools.copy_type(QGraphicsItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._size = QSize()

    def set_size(self, size: QSize) -> None:
        self._size = size

    def get_size(self) -> QSize:
        return self._size

    def boundingRect(self) -> QRectF:
        return QRectF(QPointF(0, 0), self._size)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setPen(HMITheme.Color.select_frame_border())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.boundingRect())


class HMIWorkZone(QGraphicsView):

    MIN_RUBBERBAND_AREA = 5 * 5

    class _Signals(QObject):
        right_click = Signal(object, QMouseEvent)    # Optional[BaseHMIWidget], QMouseEvent
        left_click = Signal(object, QMouseEvent)    # Optional[BaseHMIWidget], QMouseEvent
        drop_widget_class = Signal(type, QPoint)
        selection_changed = Signal(list)

    _signals: _Signals

    _mouse_down_widget: Optional[BaseHMIWidget]
    _mouse_down_start: Optional[QPoint]
    _rubberband: QRubberBand
    _rubberband_active: bool
    _allow_edit_widgets: bool
    _mouse_edit_data: Optional[WidgetMouseEditData]
    _grid: HMIEditGrid
    _selected_widgets: List[BaseHMIWidget]
    _scene: QGraphicsScene
    _drop_placeholder: DropPlaceholder

    @tools.copy_type(QGraphicsView.__init__)
    def __init__(self) -> None:
        self._scene = QGraphicsScene()
        super().__init__(self._scene)
        self._signals = self._Signals()

        self._mouse_down_start = None
        self._mouse_down_widget = None

        self._rubberband = QRubberBand(QRubberBand.Shape.Rectangle)
        self._rubberband.setParent(self)
        self._rubberband_active = False
        self._rubberband.setVisible(False)
        self._allow_edit_widgets = False
        self._mouse_edit_data = None
        self._grid = HMIEditGrid(self)
        self._grid.set_size(self.viewport().size())
        self._selected_widgets = []
        self._drop_placeholder = DropPlaceholder()
        self._drop_placeholder.setVisible(False)
        self._drop_placeholder.setZValue(10000)
        self.scene().addItem(self._grid)
        self.scene().addItem(self._drop_placeholder)

    def show_grid(self, val: bool) -> None:
        self._grid.setVisible(val)

    def add_widgets_to_selection(self, widgets: List[BaseHMIWidget]) -> None:
        self._selected_widgets.extend(widgets)
        for widget in widgets:
            widget.set_selected(True)
        self._signals.selection_changed.emit(self._selected_widgets.copy())

    def select_widgets(self, widgets: List[BaseHMIWidget]) -> None:
        for hmi_widget in self.iterate_hmi_widgets():
            hmi_widget.set_selected(False)

        self._selected_widgets.clear()
        self._selected_widgets.extend(widgets)

        for widget in self._selected_widgets:
            widget.set_selected(True)

        self._signals.selection_changed.emit(self._selected_widgets.copy())

    def deselect_all_widgets(self) -> None:
        for widget in self._selected_widgets:
            widget.set_selected(False)
        self._selected_widgets.clear()
        self._signals.selection_changed.emit(self._selected_widgets.copy())

    def remove_widget(self, widget: BaseHMIWidget) -> None:
        if widget in self._selected_widgets:
            self._selected_widgets.remove(widget)

        self.scene().removeItem(widget)

    def add_widget(self, widget: BaseHMIWidget, scene_pos: Optional[QPoint] = None) -> None:
        self.scene().addItem(widget)
        if scene_pos is not None:
            widget.setPos(self._snap_to_grid(scene_pos, widget.get_size()))

    def selected_widgets(self) -> List[BaseHMIWidget]:
        return self._selected_widgets.copy()

    def set_allow_edit_widgets(self, val: bool) -> None:
        self._allow_edit_widgets = val

        if self._allow_edit_widgets:
            self.setMouseTracking(True)
        else:
            self._mouse_edit_data = None
            self.setMouseTracking(False)

    def _compute_rubber_band_rect(self, start: QPoint, end: QPoint) -> QRect:
        top = min(start.y(), end.y())
        bottom = max(start.y(), end.y())
        left = min(start.x(), end.x())
        right = max(start.x(), end.x())
        return QRect(QPoint(left, top), QPoint(right, bottom))

    def hmi_widget_at(self, pos: QPoint) -> Optional[BaseHMIWidget]:
        for item in self.items(pos):
            if isinstance(item, BaseHMIWidget):
                return item
        return None

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._resize_scene()

    def _resize_scene(self) -> None:
        self.viewport().size()
        width = self.viewport().size().width()
        height = self.viewport().size().height()
        for widget in self.iterate_hmi_widgets():
            width = max(width, int(widget.x()) + widget.get_size().width())
            height = max(height, int(widget.y()) + widget.get_size().height())
        new_size = QSize(width, height)
        self.setSceneRect(QRect(QPoint(0, 0), new_size))
        self._grid.set_size(new_size)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        event.accept()
        cursor = Qt.CursorShape.ArrowCursor

        if self._allow_edit_widgets:
            if self._rubberband_active:
                assert self._mouse_down_start is not None
                self._rubberband.setVisible(True)
                self._rubberband.setGeometry(self._compute_rubber_band_rect(self._mouse_down_start, event.pos()))
            else:
                if self._mouse_edit_data is not None:
                    if self._mouse_edit_data.action == WidgetMouseEditData.Action.Move:
                        cursor = self._view_mousemove_move_widget(event)
                    elif self._mouse_edit_data.action == WidgetMouseEditData.Action.Resize:
                        cursor = self._view_mousemove_resize_widget(event)
                else:
                    # Check if we should display a resize cursor if use hover a resize handle
                    item = self.hmi_widget_at(event.pos())
                    if item is not None:
                        local_pos = item.mapFromScene(self.mapToScene(event.pos()))
                        for handle, rect in item.resize_handles_coordinates().items():
                            if rect.contains(local_pos):
                                cursor = RESIZE_CURSOR_MAP[handle]
                                break

        self.setCursor(cursor)

    def _snap_to_grid(self, p: Union[QPoint, QPointF], size: Optional[Union[QSizeF, QSize]] = None) -> QPoint:
        if size is None:
            size = QSize(0, 0)
        max_x = int(((self.sceneRect().right() - size.width()) // self._grid.GRID_SPACING) * self._grid.GRID_SPACING)
        max_y = int(((self.sceneRect().bottom() - size.height()) // self._grid.GRID_SPACING) * self._grid.GRID_SPACING)

        return QPoint(
            int(max(min(round(p.x() / self._grid.GRID_SPACING, 0) * self._grid.GRID_SPACING, max_x), 0)),
            int(max(min(round(p.y() / self._grid.GRID_SPACING, 0) * self._grid.GRID_SPACING, max_y), 0))
        )

    def _view_mousemove_move_widget(self, event: QMouseEvent) -> Qt.CursorShape:
        assert self._mouse_edit_data is not None
        assert self._mouse_edit_data.move_data is not None

        delta_since_start = self.mapToScene(event.pos()).toPoint() - self._mouse_edit_data.move_data.cursor_start

        new_bounding_rect = self._mouse_edit_data.move_data.selection_bouding_rect.translated(delta_since_start)
        new_bounding_rect_top_left = self._snap_to_grid(new_bounding_rect.topLeft(), new_bounding_rect.size())

        for widget in self._selected_widgets:
            offset_to_bounding_rect = self._mouse_edit_data.move_data.widget_offset_to_bounding_rect[id(widget)]
            new_pos = QPoint(
                new_bounding_rect_top_left.x() + offset_to_bounding_rect.x(),
                new_bounding_rect_top_left.y() + offset_to_bounding_rect.y()
            )
            widget.setPos(self._snap_to_grid(new_pos))

        return Qt.CursorShape.DragMoveCursor

    def _view_mousemove_resize_widget(self, event: QMouseEvent) -> Qt.CursorShape:
        assert self._mouse_edit_data is not None
        assert self._mouse_edit_data.resize_data is not None

        previous_pos = self._mouse_edit_data.resize_data.widget.pos().toPoint()
        previous_size = self._mouse_edit_data.resize_data.widget.get_size()
        new_pos = QPoint(previous_pos)
        new_size = QSize(previous_size)
        handle = self._mouse_edit_data.resize_data.handle_clicked
        cursor = RESIZE_CURSOR_MAP[self._mouse_edit_data.resize_data.handle_clicked]

        # Clip event to grid limits
        clipped_event_pos = QPoint(
            min(max(event.pos().x(), 0), (self.width() // HMIEditGrid.GRID_SPACING) * HMIEditGrid.GRID_SPACING),
            min(max(event.pos().y(), 0), (self.height() // HMIEditGrid.GRID_SPACING) * HMIEditGrid.GRID_SPACING)
        )

        diff_point = self.mapToScene(clipped_event_pos).toPoint() - self._mouse_edit_data.resize_data.original_pos
        diff_size = QSize(
            int(round(diff_point.x() / HMIEditGrid.GRID_SPACING, 0) * HMIEditGrid.GRID_SPACING),
            int(round(diff_point.y() / HMIEditGrid.GRID_SPACING, 0) * HMIEditGrid.GRID_SPACING)
        )

        if handle == HandlePosition.BOTTOMRIGHT:
            new_size = QSize(diff_size)
        elif handle == HandlePosition.BOTTOMMID:
            new_size = QSize(previous_size.width(), diff_size.height())
        elif handle == HandlePosition.MIDRIGHT:
            new_size = QSize(diff_size.width(), previous_size.height())
        elif handle == HandlePosition.TOPRIGHT:
            new_size = QSize(diff_size.width(), self._mouse_edit_data.resize_data.original_size.height() - diff_size.height())
            new_pos = QPoint(
                self._mouse_edit_data.resize_data.original_pos.x(),
                self._mouse_edit_data.resize_data.original_pos.y() + diff_size.height()
            )
        elif handle == HandlePosition.TOPMID:
            new_size = QSize(previous_size.width(), self._mouse_edit_data.resize_data.original_size.height() - diff_size.height())
            new_pos = QPoint(
                self._mouse_edit_data.resize_data.original_pos.x(),
                self._mouse_edit_data.resize_data.original_pos.y() + diff_size.height()
            )
        elif handle == HandlePosition.TOPLEFT:
            new_size = self._mouse_edit_data.resize_data.original_size - diff_size  # QSize - QSize = QSize
            new_pos = self._mouse_edit_data.resize_data.original_pos + QPoint(diff_size.width(), diff_size.height())
        elif handle == HandlePosition.MIDLEFT:
            new_size = QSize(self._mouse_edit_data.resize_data.original_size.width() - diff_size.width(), previous_size.height())
            new_pos = QPoint(self._mouse_edit_data.resize_data.original_pos.x() + diff_size.width(), previous_pos.y())
        elif handle == HandlePosition.BOTTOMLEFT:
            new_size = QSize(self._mouse_edit_data.resize_data.original_size.width() - diff_size.width(), diff_size.height())
            new_pos = QPoint(self._mouse_edit_data.resize_data.original_pos.x() + diff_size.width(), previous_pos.y())

        # Apply only on dimensions that are allowed to change
        widget = self._mouse_edit_data.resize_data.widget
        if new_size.width() >= widget.min_width() and new_size.height() >= widget.min_height():
            self._mouse_edit_data.resize_data.widget.setPos(new_pos)
            self._mouse_edit_data.resize_data.widget.set_size(new_size)
        elif new_size.width() >= widget.min_width():
            self._mouse_edit_data.resize_data.widget.setPos(QPoint(new_pos.x(), previous_pos.y()))
            self._mouse_edit_data.resize_data.widget.set_size(QSize(new_size.width(), previous_size.height()))
        elif new_size.height() >= widget.min_height():
            self._mouse_edit_data.resize_data.widget.setPos(QPoint(previous_pos.x(), new_pos.y()))
            self._mouse_edit_data.resize_data.widget.set_size(QSize(previous_size.width(), new_size.height()))
        else:
            pass    # Leave untouched

        return cursor

    def mousePressEvent(self, event: QMouseEvent) -> None:
        event.accept()

        self._mouse_down_start = event.pos()
        mouse_down_item = self.hmi_widget_at(event.pos())
        self._mouse_down_widget = None

        if isinstance(mouse_down_item, BaseHMIWidget):
            self._mouse_down_widget = mouse_down_item

        if event.button() == Qt.MouseButton.LeftButton:
            self._mouse_edit_data = None
            if self._allow_edit_widgets:
                if self._mouse_down_widget is None:
                    self._rubberband_active = True
                else:
                    resize_handles = self._mouse_down_widget.resize_handles_coordinates()
                    resize_handle: Optional[HandlePosition] = None
                    pos_mapped_to_widget = self._mouse_down_widget.mapFromScene(self.mapToScene(event.pos())).toPoint()
                    for handle, rect in resize_handles.items():
                        if rect.contains(pos_mapped_to_widget):
                            resize_handle = handle
                            break

                    if resize_handle:
                        self._mouse_edit_data = WidgetMouseEditData(
                            action=WidgetMouseEditData.Action.Resize,
                            resize_data=WidgetMouseEditData.ResizeData(
                                widget=self._mouse_down_widget,
                                handle_clicked=resize_handle,
                                original_pos=QPoint(self._mouse_down_widget.pos().toPoint()),
                                original_size=QSize(self._mouse_down_widget.get_size())
                            )
                        )
                    else:
                        if self._mouse_down_widget not in self._selected_widgets:
                            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                                self.add_widgets_to_selection([self._mouse_down_widget])
                            else:
                                self.select_widgets([self._mouse_down_widget])

                        selection_bounding_rect = self._mouse_down_widget.mapToScene(self._mouse_down_widget.boundingRect().toRect()).boundingRect()
                        for widget in self._selected_widgets:
                            bounding_rect = widget.mapToScene(widget.boundingRect().toRect()).boundingRect()
                            selection_bounding_rect.setTop(min(selection_bounding_rect.top(), bounding_rect.top()))
                            selection_bounding_rect.setLeft(min(selection_bounding_rect.left(), bounding_rect.left()))
                            selection_bounding_rect.setBottom(max(selection_bounding_rect.bottom(), bounding_rect.bottom()))
                            selection_bounding_rect.setRight(max(selection_bounding_rect.right(), bounding_rect.right()))

                        widget_offset: Dict[int, QPoint] = {}
                        for widget in self._selected_widgets:
                            widget_offset[id(widget)] = (widget.mapToScene(QPoint(0, 0)) - selection_bounding_rect.topLeft()).toPoint()

                        self._mouse_edit_data = WidgetMouseEditData(
                            action=WidgetMouseEditData.Action.Move,
                            move_data=WidgetMouseEditData.MoveData(
                                cursor_start=self.mapToScene(event.pos()).toPoint(),
                                widget_offset_to_bounding_rect=widget_offset,
                                selection_bouding_rect=selection_bounding_rect.toRect()
                            )
                        )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        event.accept()
        if self._mouse_down_start is None:
            return

        mouse_release_widget: Optional[QGraphicsItem] = self.hmi_widget_at(event.pos())
        if not isinstance(mouse_release_widget, BaseHMIWidget):
            mouse_release_widget = None

        # Check if right-click
        if event.button() == Qt.MouseButton.RightButton:
            if self._mouse_down_widget is mouse_release_widget:
                self._signals.right_click.emit(mouse_release_widget, event)

        elif event.button() == Qt.MouseButton.LeftButton:
            if event.pos() == self._mouse_down_start:
                self._rubberband_active = False

            if self._rubberband_active:
                # Rubber band select logic
                rubberband_rect = self._compute_rubber_band_rect(self._mouse_down_start, event.pos())
                area = rubberband_rect.width() * rubberband_rect.height()
                if area > self.MIN_RUBBERBAND_AREA:
                    selected: List[BaseHMIWidget] = []
                    rubberband_rect_mapped_to_scene = self.mapToScene(rubberband_rect).boundingRect().toRect()
                    for widget in self.iterate_hmi_widgets():
                        widget_rect = widget.mapToScene(widget.boundingRect()).boundingRect().toRect()
                        if rubberband_rect_mapped_to_scene.contains(widget_rect):
                            selected.append(widget)
                    self.select_widgets(selected)
            else:
                if self._mouse_down_widget is mouse_release_widget:
                    has_moved = False
                    if self._mouse_edit_data is not None:
                        if self._mouse_edit_data.action == WidgetMouseEditData.Action.Move:
                            if event.pos() != self._mouse_down_start:
                                has_moved = True

                    if not has_moved:
                        self._signals.left_click.emit(mouse_release_widget, event)

                        if mouse_release_widget is None:
                            self.deselect_all_widgets()  # Will emit selection_changed
                    else:
                        self._resize_scene()

        self._mouse_down_widget = None
        self._mouse_down_start = None
        self._rubberband.setVisible(False)
        self._rubberband_active = False
        self._mouse_edit_data = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def iterate_hmi_widgets(self) -> Generator[BaseHMIWidget, None, None]:
        for item in self.scene().items():
            if isinstance(item, BaseHMIWidget):
                yield item

    def _read_drag_data(self, mime_data: QMimeData) -> Optional[Type[BaseHMIWidget]]:
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if drag_data is None:
            return None
        if drag_data.type != ScrutinyDragData.DataType.HMIWidgetClass:
            return None

        widget_class = HMILibrary.load_from_name(drag_data.data_copy['class'])
        if widget_class is None:
            return None
        return widget_class

    def _set_drop_placeholder_pos(self, scene_pos: QPointF) -> None:
        size = self._drop_placeholder.get_size()
        mapped_pos = scene_pos - QPointF(size.width() / 2, size.height() / 2)
        snapped_pos = self._snap_to_grid(self.mapToScene(mapped_pos.toPoint()), size)
        self._drop_placeholder.setPos(snapped_pos)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        widget_class = self._read_drag_data(event.mimeData())
        if widget_class is None:
            return

        self._drop_placeholder.set_size(widget_class.default_size())
        self._drop_placeholder.setVisible(True)
        self._set_drop_placeholder_pos(self.mapToScene(event.pos()))
        event.accept()
        event.setDropAction(Qt.DropAction.CopyAction)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._drop_placeholder.setVisible(False)
        event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._set_drop_placeholder_pos(self.mapToScene(event.pos()))
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        self._drop_placeholder.setVisible(False)
        self._set_drop_placeholder_pos(self.mapToScene(event.pos()))
        widget_class = self._read_drag_data(event.mimeData())
        if widget_class is None:
            return
        event.accept()
        event.setDropAction(Qt.DropAction.CopyAction)
        self._signals.drop_widget_class.emit(widget_class, self._drop_placeholder.pos().toPoint())

    @property
    def signals(self) -> _Signals:
        return self._signals
