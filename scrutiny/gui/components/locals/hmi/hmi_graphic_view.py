#    hmi_graphic_view.py
#        An extensions of the QGraphicsView that display the HMI dashboard
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['HMIGraphicView']

from dataclasses import dataclass
import enum

from PySide6.QtCore import Qt, Signal, QRect, QPoint, QObject, QMimeData, QSize
from PySide6.QtWidgets import (QGraphicsView, QGraphicsItem, QWidget, QRubberBand)
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent, QMouseEvent, QPainter, QResizeEvent

from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.components.locals.hmi.hmi_library import HMILibrary
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, HandlePosition
from scrutiny.gui.components.locals.hmi.hmi_edit_grid import HMIEditGrid


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

    @dataclass
    class MoveData:
        offset: QPoint

    widget: BaseHMIWidget
    action: Action
    resize_data: Optional[ResizeData] = None
    move_data: Optional[MoveData] = None


class HMIGraphicView(QGraphicsView):

    MIN_RUBBERBAND_AREA = 5 * 5

    class _Signals(QObject):
        rubber_band_select_widgets = Signal(list)   # List[BaseHMIWidget]
        right_click = Signal(object, QMouseEvent)    # Optional[BaseHMIWidget], QMouseEvent
        left_click = Signal(object, QMouseEvent)    # Optional[BaseHMIWidget], QMouseEvent
        drop_widget_class = Signal(type, QPoint)

    _signals: _Signals

    _mouse_down_widget: Optional[BaseHMIWidget]
    _mouse_down_start: Optional[QPoint]
    _rubberband: QRubberBand
    _rubberband_active: bool
    _allow_edit_widgets: bool
    _mouse_edit_data: Optional[WidgetMouseEditData]
    _grid: HMIEditGrid

    @tools.copy_type(QGraphicsView.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
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
        self.scene().addItem(self._grid)

    def show_grid(self, val: bool) -> None:
        self._grid.setVisible(val)

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
        super().resizeEvent(event)
        self.setSceneRect(QRect(QPoint(0, 0), event.size()))

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
                        local_pos = item.mapFromScene(self.mapFromScene(event.pos()))
                        for handle, rect in item.resize_handles_coordinates().items():
                            if rect.contains(local_pos):
                                cursor = RESIZE_CURSOR_MAP[handle]
                                break

        self.setCursor(cursor)

    def _view_mousemove_move_widget(self, event: QMouseEvent) -> Qt.CursorShape:
        assert self._mouse_edit_data is not None
        assert self._mouse_edit_data.move_data is not None
        pos_offsetted = event.pos().toPointF() - self._mouse_edit_data.move_data.offset
        x = round(pos_offsetted.x() / self._grid.GRID_SPACING, 0) * self._grid.GRID_SPACING
        y = round(pos_offsetted.y() / self._grid.GRID_SPACING, 0) * self._grid.GRID_SPACING
        max_x = ((self.sceneRect().width() - self._mouse_edit_data.widget.boundingRect().width()) // HMIEditGrid.GRID_SPACING) * HMIEditGrid.GRID_SPACING
        max_y = ((self.sceneRect().height() - self._mouse_edit_data.widget.boundingRect().height()) //
                 HMIEditGrid.GRID_SPACING) * HMIEditGrid.GRID_SPACING
        x = min(max(x, 0), max_x)
        y = min(max(y, 0), max_y)
        self._mouse_edit_data.widget.setPos(x, y)

        return Qt.CursorShape.DragMoveCursor

    def _view_mousemove_resize_widget(self, event: QMouseEvent) -> Qt.CursorShape:
        assert self._mouse_edit_data is not None
        assert self._mouse_edit_data.resize_data is not None

        previous_pos = self._mouse_edit_data.widget.pos().toPoint()
        previous_size = self._mouse_edit_data.widget.get_size()
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
        if new_size.width() >= HMIEditGrid.GRID_SPACING and new_size.height() >= HMIEditGrid.GRID_SPACING:
            self._mouse_edit_data.widget.setPos(new_pos)
            self._mouse_edit_data.widget.set_size(new_size)
        elif new_size.width() >= HMIEditGrid.GRID_SPACING:
            self._mouse_edit_data.widget.setPos(QPoint(new_pos.x(), previous_pos.y()))
            self._mouse_edit_data.widget.set_size(QSize(new_size.width(), previous_size.height()))
        elif new_size.height() >= HMIEditGrid.GRID_SPACING:
            self._mouse_edit_data.widget.setPos(QPoint(previous_pos.x(), new_pos.y()))
            self._mouse_edit_data.widget.set_size(QSize(previous_size.width(), new_size.height()))
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
                    if self._allow_edit_widgets:    # Clicked empty region. Create a rubber band
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
                            widget=self._mouse_down_widget,
                            action=WidgetMouseEditData.Action.Resize,
                            resize_data=WidgetMouseEditData.ResizeData(
                                handle_clicked=resize_handle,
                                original_pos=QPoint(self._mouse_down_widget.pos().toPoint()),
                                original_size=QSize(self._mouse_down_widget.get_size())
                            )
                        )
                    else:
                        self._mouse_edit_data = WidgetMouseEditData(
                            widget=self._mouse_down_widget,
                            action=WidgetMouseEditData.Action.Move,
                            move_data=WidgetMouseEditData.MoveData(
                                offset=pos_mapped_to_widget
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
                    for widget in self._iterate_hmi_wdgets():
                        widget_rect = widget.mapToScene(widget.boundingRect()).boundingRect().toRect()
                        if rubberband_rect_mapped_to_scene.contains(widget_rect):
                            selected.append(widget)
                    self._signals.rubber_band_select_widgets.emit(selected)
            else:
                if self._mouse_down_widget is mouse_release_widget:
                    has_moved = False
                    if self._mouse_edit_data is not None:
                        if self._mouse_edit_data.action == WidgetMouseEditData.Action.Move:
                            if event.pos() != self._mouse_down_start:
                                has_moved = True

                    if not has_moved:
                        self._signals.left_click.emit(mouse_release_widget, event)

        self._mouse_down_widget = None
        self._mouse_down_start = None
        self._rubberband.setVisible(False)
        self._rubberband_active = False
        self._mouse_edit_data = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _iterate_hmi_wdgets(self) -> Generator[BaseHMIWidget, None, None]:
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

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        widget_class = self._read_drag_data(event.mimeData())
        if widget_class is None:
            return

        event.accept()
        event.setDropAction(Qt.DropAction.CopyAction)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.accept()

    def dropEvent(self, event: QDropEvent) -> None:
        widget_class = self._read_drag_data(event.mimeData())
        if widget_class is None:
            return
        event.accept()
        event.setDropAction(Qt.DropAction.CopyAction)
        scene_pos = self.mapToScene(event.position().toPoint()).toPoint()
        self._signals.drop_widget_class.emit(widget_class, scene_pos)

    @property
    def signals(self) -> _Signals:
        return self._signals
