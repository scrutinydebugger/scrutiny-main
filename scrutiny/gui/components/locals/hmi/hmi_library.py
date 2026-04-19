#    hmi_library.py
#        A library of all the HMI widgets avaialble
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import math

from PySide6.QtGui import QMouseEvent, QResizeEvent, QDrag
from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QLabel, QGroupBox, QFrame
from PySide6.QtCore import Qt, QSize

from scrutiny.gui.widgets.scrutiny_hoverable_widget import ScrutinyHoverableWidget
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.components.locals.hmi.hmi_library_category import HMI_LIBARY_CATEGORIES, LibraryCategory
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget

from scrutiny.tools.typing import *

# Do NOT remove those imports
# They enable discovery by reflection.
from .hmi_widgets.text_label_hmi_widget import TextLabelHMIWidget
from .hmi_widgets.gauge_hmi_widget import GaugeHMIWidget
#########################################


class HMILibraryEntryWidget(ScrutinyHoverableWidget):
    """A widget that display the icon of a single HMI widget"""
    ICON_SIZE = 64

    _hmi_widget: Type[BaseHMIWidget]
    _icon_label: QLabel
    _text_label: QLabel

    def __init__(self, hmi_widget: Type[BaseHMIWidget]) -> None:
        super().__init__()
        self._hmi_widget = hmi_widget

        self._icon_label = QLabel()
        pixmap = hmi_widget.get_icon_as_pixmap()
        self._icon_label.setPixmap(pixmap.scaled(QSize(self.ICON_SIZE, self.ICON_SIZE), Qt.AspectRatioMode.KeepAspectRatio))
        self._icon_label.setFixedSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        self._text_label = QLabel(hmi_widget.get_name())
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)

    def get_widget_name(self) -> str:
        return self._hmi_widget.get_name()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._icon_label.geometry().contains(event.pos()):
            drag = QDrag(self)

            drag_data = ScrutinyDragData(
                type=ScrutinyDragData.DataType.HMIWidgetClass,
                data_copy={
                    'class': self._hmi_widget.__name__,
                }
            )
            mime_data = drag_data.to_mime()
            assert mime_data is not None
            drag.setMimeData(mime_data)
            drag.setPixmap(self._icon_label.pixmap())

            drag.exec()

        return super().mousePressEvent(event)


class HMILibraryCategoryWidget(QWidget):
    """A widget that display every HMI widgets in a category"""
    _category: LibraryCategory
    _display_name: str
    _entries: List[HMILibraryEntryWidget]

    _grid_container: QWidget

    def __init__(self, category: LibraryCategory, hmi_widgets: List[Type[BaseHMIWidget]]) -> None:
        super().__init__()
        category_info = HMI_LIBARY_CATEGORIES[category]
        self._category = category
        self._display_name = category_info.display_name
        self._entries = sorted((HMILibraryEntryWidget(hmiw) for hmiw in hmi_widgets), key=lambda x: x.get_widget_name())
        self._grid_container = QWidget()

        layout = QVBoxLayout(self)
        gb = QGroupBox(self._display_name)
        layout.addWidget(gb)
        gb_layout = QVBoxLayout(gb)
        gb_layout.setContentsMargins(0, 0, 0, 0)
        gb_layout.addWidget(self._grid_container)

        self.rebuild_grid_layout()

    def rebuild_grid_layout(self) -> None:
        nb_col = self._grid_container.width() // HMILibraryEntryWidget.ICON_SIZE
        if nb_col == 0:
            return
        nb_row = math.ceil(len(self._entries) / nb_col)

        layout = cast(Optional[QGridLayout], self._grid_container.layout())
        if layout is None:
            layout = QGridLayout(self._grid_container)
        else:
            if layout.columnCount() == nb_col and layout.rowCount() == nb_row:
                return

            for widget in self._entries:
                layout.removeWidget(widget)

        for row in range(nb_row):
            for col in range(nb_col):
                index = row * nb_col + col
                if index < len(self._entries):
                    layout.addWidget(self._entries[index], row, col, Qt.AlignmentFlag.AlignTop)
        self._grid_container.setMaximumWidth(nb_col * HMILibraryEntryWidget.ICON_SIZE)

    def get_display_name(self) -> str:
        return self._display_name

    def get_category(self) -> LibraryCategory:
        return self._category

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.rebuild_grid_layout()


class HMILibrary(QWidget):
    """A widget that display every HMI widgets, classified by categories"""

    def __init__(self) -> None:
        super().__init__()
        widget_classes_per_category: Dict[LibraryCategory, List[Type[BaseHMIWidget]]] = {}
        for c in BaseHMIWidget.__subclasses__():
            category = c.get_category()
            assert category in HMI_LIBARY_CATEGORIES

            if category not in widget_classes_per_category:
                widget_classes_per_category[category] = []
            widget_classes_per_category[category].append(c)

        category_widgets = [HMILibraryCategoryWidget(cat, classes) for cat, classes in widget_classes_per_category.items()]
        category_widgets.sort(key=lambda x: x.get_display_name())

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        for category_widget in category_widgets:
            layout.addWidget(category_widget)

    @classmethod
    def load_from_name(cls, class_name: str) -> Optional[Type[BaseHMIWidget]]:
        for c in BaseHMIWidget.__subclasses__():
            if c.__name__ == class_name:
                return c

        return None
