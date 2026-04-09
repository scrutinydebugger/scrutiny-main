#    hmi_component.py
#        Human Machine Interface component. Lets the user build a visual dashboard with graphical
#        elements tied to a watchable.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['HMIComponent']

from PySide6.QtCore import QRectF, Qt, Signal, QPointF, QRect, QPoint, QObject, QSize
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QVBoxLayout, QGraphicsScene, QGraphicsView, QGraphicsItem, QWidget, QGraphicsSceneMouseEvent, QMenu
from PySide6.QtGui import QIcon, QKeyEvent, QMouseEvent, QPainter, QResizeEvent
import enum
import functools
from dataclasses import dataclass

from scrutiny import sdk
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.app_settings import app_settings
from scrutiny import tools

from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, HandlePosition
from scrutiny.gui.components.locals.hmi.hmi_widgets.text_label_hmi_widget import TextLabelHMIWidget

from scrutiny.tools.typing import *


class Mode(enum.Enum):
    Display = enum.auto()
    Edit = enum.auto()


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


class Grid(QGraphicsItem):
    GRID_SPACING = 16

    _view: QGraphicsView
    _visible: bool

    def __init__(self, view: QGraphicsView) -> None:
        super().__init__()
        self._visible = False
        self._view = view

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def boundingRect(self) -> QRectF:
        return self.mapRectToScene(self._view.viewport().rect())

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setPen(scrutiny_get_theme().palette().text().color())
        zone = self.boundingRect().toRect()

        for x in range(zone.left(), zone.right(), self.GRID_SPACING):
            for y in range(zone.top(), zone.bottom(), self.GRID_SPACING):
                painter.drawPoint(QPointF(x, y))


class HMIView(QGraphicsView):

    _mouse_down_widget: Optional[BaseHMIWidget]

    class _Signals(QObject):
        mouse_move = Signal(object)
        mouse_down_void = Signal()
        right_click_widget = Signal(object, object)

    _signals: _Signals

    @tools.copy_type(QGraphicsView.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._signals = self._Signals()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.setSceneRect(QRect(QPoint(0, 0), event.size()))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        event.accept()
        self._signals.mouse_move.emit(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        mouse_down_item = self.itemAt(event.pos())
        if isinstance(mouse_down_item, BaseHMIWidget):
            self._mouse_down_widget = mouse_down_item
        else:
            if event.button() == Qt.MouseButton.LeftButton:
                self._signals.mouse_down_void.emit()
            self._mouse_down_widget = None

        super().mousePressEvent(event)  # Pass down to items

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        mouse_down_item = self.itemAt(event.pos())
        if isinstance(mouse_down_item, BaseHMIWidget):
            if self._mouse_down_widget is mouse_down_item:
                if event.button() == Qt.MouseButton.RightButton:
                    self._signals.right_click_widget.emit(mouse_down_item, event)

        self._mouse_down_widget = None
        return super().mouseReleaseEvent(event)

    @property
    def signals(self) -> _Signals:
        return self._signals


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
    mousedown_start: QPoint
    resize_data: Optional[ResizeData] = None
    move_data: Optional[MoveData] = None


class HMIComponent(ScrutinyGUIBaseLocalComponent):
    instance_name: str

    _NAME = "Human Machine Interface"
    _TYPE_ID = "hmi"

    _mode: Mode
    _scene: QGraphicsScene
    _view: HMIView
    _grid: Grid

    _mouse_edit_data: Optional[WidgetMouseEditData]
    _selected_widget: Optional[BaseHMIWidget]

# region inherited methods
    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.TestSquare)

    def setup(self) -> None:
        self._mode = Mode.Display
        self._scene = QGraphicsScene()
        self._view = HMIView(self._scene)
        self._view.setMouseTracking(True)

        self._grid = Grid(self._view)

        self._scene.addItem(self._grid)

        self.text_widget = TextLabelHMIWidget(self)
        self._mouse_edit_data = None
        self._selected_widget = None

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_widget._make_slot_config_widget())
        layout.addWidget(self._view)
        self._view.signals.mouse_move.connect(self._view_mouse_move_slot)
        self._view.signals.mouse_down_void.connect(self._view_mouse_down_void_slot)
        self._view.signals.right_click_widget.connect(self._view_right_click_slot)
        self.add(self.text_widget)

        self.set_mode(Mode.Edit)

    def ready(self) -> None:
        pass

    def teardown(self) -> None:
        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget):
                item.destroy()

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def add(self, widget: BaseHMIWidget) -> None:
        self._scene.addItem(widget)
        widget.signals.mousedown.connect(self._hmi_widget_mousedown_slot)
        widget.signals.mouseup.connect(self._hmi_widget_mouseup_slot)

    def select_widget(self, widget: BaseHMIWidget) -> None:
        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget) and item is not widget:
                item.set_selected(False)

        self._selected_widget = widget
        widget.set_selected(True)

    def toggle_select_widget(self, widget: BaseHMIWidget) -> None:
        if self._selected_widget is widget:
            self.deselect_all_widgets()
        else:
            self.select_widget(widget)

    def deselect_all_widgets(self) -> None:
        self._selected_widget = None
        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget):
                item.set_selected(False)

    def set_mode(self, mode: Mode) -> None:
        self._mode = mode
        self._mouse_edit_data = None
        edit_mode = (mode == Mode.Edit)
        for item in self._scene.items():
            if isinstance(item, BaseHMIWidget):
                item.show_resize_handles(edit_mode)
                item.update()

    def _view_mouse_down_void_slot(self) -> None:
        self.deselect_all_widgets()

    def _view_right_click_slot(self, widget: BaseHMIWidget, event: QMouseEvent) -> None:
        if self._mode != Mode.Edit:
            return

        menu = QMenu()
        remove_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")
        edit_action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Edit")

        remove_action.triggered.connect(functools.partial(self._delete_widget, widget))

        menu.exec(self._view.mapToGlobal(event.pos()))

    def _view_mouse_move_slot(self, event: QMouseEvent) -> None:
        cursor = Qt.CursorShape.ArrowCursor
        if self._mode == Mode.Edit:
            if self._mouse_edit_data is not None:
                if self._mouse_edit_data.action == WidgetMouseEditData.Action.Move:
                    assert self._mouse_edit_data.move_data is not None
                    pos_offsetted = event.pos().toPointF() - self._mouse_edit_data.move_data.offset
                    x = round(pos_offsetted.x() / self._grid.GRID_SPACING, 0) * self._grid.GRID_SPACING
                    y = round(pos_offsetted.y() / self._grid.GRID_SPACING, 0) * self._grid.GRID_SPACING
                    max_x = ((self._view.sceneRect().width() - self._mouse_edit_data.widget.boundingRect().width()) // Grid.GRID_SPACING) * Grid.GRID_SPACING
                    max_y = ((self._view.sceneRect().height() - self._mouse_edit_data.widget.boundingRect().height()) // Grid.GRID_SPACING) * Grid.GRID_SPACING
                    x = min(max(x, 0), max_x)
                    y = min(max(y, 0), max_y)
                    self._mouse_edit_data.widget.setPos(x, y)

                elif self._mouse_edit_data.action == WidgetMouseEditData.Action.Resize:
                    assert self._mouse_edit_data.resize_data is not None
                    previous_pos = self._mouse_edit_data.widget.pos().toPoint()
                    previous_size = self._mouse_edit_data.widget.get_size()
                    new_pos = QPoint(previous_pos)
                    new_size = QSize(previous_size)
                    handle = self._mouse_edit_data.resize_data.handle_clicked
                    cursor = RESIZE_CURSOR_MAP[self._mouse_edit_data.resize_data.handle_clicked]

                    # Clip event to grid limits
                    clipped_event_pos = QPoint(
                        min(max(event.pos().x(), 0), (self._view.width() // Grid.GRID_SPACING) * Grid.GRID_SPACING),
                        min(max(event.pos().y(), 0), (self._view.height() // Grid.GRID_SPACING) * Grid.GRID_SPACING)
                    )

                    diff_point = self._view.mapToScene(clipped_event_pos).toPoint() - self._mouse_edit_data.resize_data.original_pos
                    diff_size = QSize(
                        int(round(diff_point.x() / Grid.GRID_SPACING, 0) * Grid.GRID_SPACING),
                        int(round(diff_point.y() / Grid.GRID_SPACING, 0) * Grid.GRID_SPACING)
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
                        new_size = QSize(self._mouse_edit_data.resize_data.original_size - diff_size)
                        new_pos = self._mouse_edit_data.resize_data.original_pos + QPoint(diff_size.width(), diff_size.height())
                    elif handle == HandlePosition.MIDLEFT:
                        new_size = QSize(self._mouse_edit_data.resize_data.original_size.width() - diff_size.width(), previous_size.height())
                        new_pos = QPoint(self._mouse_edit_data.resize_data.original_pos.x() + diff_size.width(), previous_pos.y())
                    elif handle == HandlePosition.BOTTOMLEFT:
                        new_size = QSize(self._mouse_edit_data.resize_data.original_size.width() - diff_size.width(), diff_size.height())
                        new_pos = QPoint(self._mouse_edit_data.resize_data.original_pos.x() + diff_size.width(), previous_pos.y())

                    if new_size.width() >= Grid.GRID_SPACING and new_size.height() >= Grid.GRID_SPACING:
                        self._mouse_edit_data.widget.setPos(new_pos)
                        self._mouse_edit_data.widget.set_size(new_size)
                    elif new_size.width() >= Grid.GRID_SPACING:
                        self._mouse_edit_data.widget.setPos(QPoint(new_pos.x(), previous_pos.y()))
                        self._mouse_edit_data.widget.set_size(QSize(new_size.width(), previous_size.height()))
                    elif new_size.height() >= Grid.GRID_SPACING:
                        self._mouse_edit_data.widget.setPos(QPoint(previous_pos.x(), new_pos.y()))
                        self._mouse_edit_data.widget.set_size(QSize(previous_size.width(), new_size.height()))
                    else:
                        pass    # Leave untouched

            else:
                item = self._view.itemAt(event.pos())
                if isinstance(item, BaseHMIWidget):
                    local_pos = item.mapFromScene(self._view.mapFromScene(event.pos()))
                    for handle, rect in item.resize_handles_coordinates().items():
                        if rect.contains(local_pos):
                            cursor = RESIZE_CURSOR_MAP[handle]
                            break

        self.setCursor(cursor)

    def _hmi_widget_mousedown_slot(self, widget: BaseHMIWidget, event: QGraphicsSceneMouseEvent) -> None:
        if not event.button() == Qt.MouseButton.LeftButton:
            return

        # event.pos() is relative to the widget pos
        if self._mode == Mode.Edit:
            pos = event.pos().toPoint()
            resize_handles = widget.resize_handles_coordinates()
            resize_handle: Optional[HandlePosition] = None
            for handle, rect in resize_handles.items():
                if rect.contains(pos):
                    resize_handle = handle
                    break

            mouse_down_start = widget.mapToScene(event.pos()).toPoint()
            if resize_handle:
                self._mouse_edit_data = WidgetMouseEditData(
                    widget=widget,
                    action=WidgetMouseEditData.Action.Resize,
                    mousedown_start=mouse_down_start,
                    resize_data=WidgetMouseEditData.ResizeData(
                        handle_clicked=resize_handle,
                        original_pos=QPoint(widget.pos().toPoint()),
                        original_size=QSize(widget.get_size())
                    )
                )
            else:
                self._mouse_edit_data = WidgetMouseEditData(
                    widget=widget,
                    action=WidgetMouseEditData.Action.Move,
                    mousedown_start=mouse_down_start,
                    move_data=WidgetMouseEditData.MoveData(
                        offset=pos
                    )
                )

        else:
            self._mouse_edit_data = None

    def _hmi_widget_mouseup_slot(self, widget: BaseHMIWidget, event: QGraphicsSceneMouseEvent) -> None:
        if not event.button() == Qt.MouseButton.LeftButton:
            return
        # event.pos is relative to the widget
        if self._mouse_edit_data is not None:
            if self._mouse_edit_data.widget is widget and widget.mapToScene(event.pos()).toPoint() == self._mouse_edit_data.mousedown_start:
                self.toggle_select_widget(widget)
        self._mouse_edit_data = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def _delete_widget(self, widget: BaseHMIWidget) -> None:
        if self._selected_widget is widget:
            self._selected_widget = None
        widget.destroy()
        self._scene.removeItem(widget)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            if self._selected_widget is not None:
                self._delete_widget(self._selected_widget)

        return super().keyPressEvent(event)

# endregion
