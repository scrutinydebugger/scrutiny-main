#    hmi_library.py
#        A library of all the HMI widgets available
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import enum

from PySide6.QtGui import QMouseEvent, QDrag
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout
from PySide6.QtCore import Qt, QSize

from scrutiny.gui.widgets.scrutiny_hoverable_widget import ScrutinyHoverableWidget
from scrutiny.gui.widgets.flow_grid_layout import FlowGridLayout
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget

from scrutiny.tools.typing import *

# Autoload every sub modules of the library so they can be imported by reflection
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.circle_hmi_widget import CircleHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.rectangle_hmi_widget import RectangleHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.line_hmi_widget import LineHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.graphics.text_label_hmi_widget import TextLabelHMIWidget

from scrutiny.gui.components.locals.hmi.hmi_widgets.controls.button_hmi_widget import ButtonHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.controls.slider_hmi_widget import SliderHMIWidget

from scrutiny.gui.components.locals.hmi.hmi_widgets.display.color_indicator_hmi_widget import ColorIndicatorHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.linear_gauge_hmi_widget import LinearGaugeHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.numerical_display_hmi_widget import NumericalDisplayHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.display.radial_gauge_hmi_widget import RadialGaugeHMIWidget


class LibraryCategory(enum.Enum):
    Display = enum.auto()
    Control = enum.auto()
    Graphic = enum.auto()


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
        self._icon_label.setMinimumHeight(self.ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label = QLabel(hmi_widget.get_display_name())
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text_label.setMaximumWidth(self.ICON_SIZE)
        self._text_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon_label)
        layout.addWidget(self._text_label)
        layout.setContentsMargins(0, 0, 0, 0)

    def get_widget_display_name(self) -> str:
        return self._hmi_widget.get_display_name()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._icon_label.geometry().contains(event.pos()):
            # Initiate Drag&Drop
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

    def __init__(self, category: LibraryCategory, display_name: str, hmi_widgets: List[Type[BaseHMIWidget]]) -> None:
        super().__init__()
        self._category = category
        self._display_name = display_name
        entries = sorted((HMILibraryEntryWidget(hmiw) for hmiw in hmi_widgets), key=lambda x: x.get_widget_display_name())

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox(self._display_name)
        layout.addWidget(gb)
        gb_layout = QVBoxLayout(gb)
        grid_widget = QWidget()
        flow = FlowGridLayout(spacing=8, parent=grid_widget)
        flow.setContentsMargins(0, 0, 0, 0)
        for entry in entries:
            flow.addWidget(entry)
        gb_layout.addWidget(grid_widget, alignment=Qt.AlignmentFlag.AlignTop)

    def get_display_name(self) -> str:
        return self._display_name

    def get_category(self) -> LibraryCategory:
        return self._category


class HMILibrary(QWidget):
    """A widget that display every HMI widgets, classified by categories"""

    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout.addWidget(
            HMILibraryCategoryWidget(LibraryCategory.Control, "Control", [
                ButtonHMIWidget,
                SliderHMIWidget
            ])
        )
        layout.addWidget(
            HMILibraryCategoryWidget(LibraryCategory.Display, "Display", [
                NumericalDisplayHMIWidget,
                ColorIndicatorHMIWidget,
                RadialGaugeHMIWidget,
                LinearGaugeHMIWidget
            ])
        )

        layout.addWidget(
            HMILibraryCategoryWidget(LibraryCategory.Graphic, "Graphic", [
                CircleHMIWidget,
                RectangleHMIWidget,
                LineHMIWidget,
                TextLabelHMIWidget
            ])
        )

    @classmethod
    def load_from_class_name(cls, class_name: str) -> Optional[Type[BaseHMIWidget]]:
        for c in BaseHMIWidget.__subclasses__():
            if c.__name__ == class_name:
                return c
        return None

    @classmethod
    def load_from_unique_name(cls, name: str) -> Optional[Type[BaseHMIWidget]]:
        for c in BaseHMIWidget.__subclasses__():
            if c.get_unique_name() == name:
                return c
        return None
