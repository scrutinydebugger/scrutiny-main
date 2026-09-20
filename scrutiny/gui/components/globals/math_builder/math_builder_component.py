
from PySide6.QtWidgets import QVBoxLayout
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathTreeView

from scrutiny.tools.typing import *


class MathBuilderComponent(ScrutinyGUIBaseGlobalComponent):

    _math_tree: MathTreeView

    def setup(self) -> None:
        self._math_tree = MathTreeView()
        layout = QVBoxLayout(self)
        layout.addWidget(self._math_tree)

    def ready(self) -> None:
        pass

    def teardown(self) -> None:
        pass

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True
