__all__ = ['HMIComponent']

from PySide6.QtCore import QModelIndex, Qt, QModelIndex, Signal
from PySide6.QtWidgets import QVBoxLayout, QGraphicsScene, QGraphicsView
from PySide6.QtGui import QIcon
import enum

from scrutiny import sdk
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.components.locals.base_local_component import ScrutinyGUIBaseLocalComponent
from scrutiny.gui.app_settings import app_settings
from scrutiny import tools

from scrutiny.gui.components.locals.hmi.hmi_widgets.text_label_hmi_widget import TextLabelHMIWidget

from scrutiny.tools.typing import *


class Mode(enum.Enum):
    Display = enum.auto()
    Edit = enum.auto()


class HMIComponent(ScrutinyGUIBaseLocalComponent):
    instance_name: str

    _NAME = "Human Machine Interface"
    _TYPE_ID = "hmi"

    GRID_SPACING = 16

    _mode: Mode
    _scene: QGraphicsScene
    _view: QGraphicsView

# region inherited methods
    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.TestSquare)

    def setup(self) -> None:
        self._mode = Mode.Display
        self._scene = QGraphicsScene()
        self._view = QGraphicsView(self._scene)

        self.text_widget = TextLabelHMIWidget(self.app)
        self._scene.addItem(self.text_widget)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text_widget._make_slot_config_widget())
        layout.addWidget(self._view)

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True

    def visibilityChanged(self, visible: bool) -> None:
        pass

# endregion
