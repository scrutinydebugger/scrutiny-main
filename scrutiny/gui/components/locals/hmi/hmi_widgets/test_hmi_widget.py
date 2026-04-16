__all__ = ['TestHMIWidget']

from PySide6.QtGui import QPainter
from PySide6.QtCore import QSize, QRect, QPoint, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QComboBox


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class TestHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Display
    _NAME = 'Text'
    _ICON = assets.Icons.TestSquare

    _config_widget: QWidget
    _cmb_color: QComboBox

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)

        self._config_widget = QWidget()
        layout = QVBoxLayout(self._config_widget)
        cmb = QComboBox()
        layout.addWidget(cmb)

        palette = scrutiny_get_theme().palette()
        cmb.addItem("accent", palette.accent())
        cmb.addItem("alternateBase", palette.alternateBase())
        cmb.addItem("base", palette.base())
        cmb.addItem("brightText", palette.brightText())
        cmb.addItem("button", palette.button())
        cmb.addItem("buttonText", palette.buttonText())
        cmb.addItem("dark", palette.dark())
        cmb.addItem("highlight", palette.highlight())
        cmb.addItem("highlightedText", palette.highlightedText())
        cmb.addItem("light", palette.light())
        cmb.addItem("link", palette.link())
        cmb.addItem("linkVisited", palette.linkVisited())
        cmb.addItem("mid", palette.mid())
        cmb.addItem("midlight", palette.midlight())
        cmb.addItem("placeholderText", palette.placeholderText())
        cmb.addItem("shadow", palette.shadow())
        cmb.addItem("text", palette.text())
        cmb.addItem("toolTipBase", palette.toolTipBase())
        cmb.addItem("toolTipText", palette.toolTipText())
        cmb.addItem("window", palette.window())
        cmb.addItem("windowText", palette.windowText())

        cmb.currentIndexChanged.connect(self.update)

        self._cmb_color = cmb

    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def draw(self,
             configured: bool,
             values: Dict[str, Union[float, int, bool, None]],
             draw_zone_size: QSize,
             painter: QPainter
             ) -> None:
        color_name = self._cmb_color.currentText()
        brush = self._cmb_color.currentData()
        square = QRect(QPoint(0, 0), draw_zone_size)

        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(square)

        painter.setPen(scrutiny_get_theme().palette().text().color())
        painter.drawText(square, Qt.AlignmentFlag.AlignCenter, color_name)
